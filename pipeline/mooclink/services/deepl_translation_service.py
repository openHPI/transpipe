import html
import io
import math
from io import BytesIO

import requests
import webvtt
from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from subtitles.models import Subtitle, IsoLanguage, SubtitleFile, ServiceProviderUse

'''
VTT -> Webcaptions -> <span> delimited html and vice-versa inspired by 
https://github.com/aws-samples/amazon-translate-video-subtitles-captions-translation
'''


class DeeplTranslationService:

    def __init__(self, tenant):
        self.tenant = tenant
        self.session: requests.Session = None

        self.base_url = self.tenant.get_secret('DEEPL_URL')
        self.auth_key = self.tenant.get_secret('DEEPL_AUTH_KEY')

        self.create_session()

    def create_session(self):
        self.session = requests.Session()

    def format_timeVtt_to_seconds(self, timeHMSf):
        hours, minutes, seconds = (timeHMSf.split(":"))[-3:]
        hours = int(hours)
        minutes = int(minutes)
        seconds = float(seconds)
        timeSeconds = float(3600 * hours + 60 * minutes + seconds)
        return str(timeSeconds)

    def format_seconds_to_timeVtt(self, time_seconds):
        ONE_HOUR = 60 * 60
        ONE_MINUTE = 60
        hours = math.floor(time_seconds / ONE_HOUR)
        remainder = time_seconds - (hours * ONE_HOUR)
        minutes = math.floor(remainder / 60)
        remainder = remainder - (minutes * ONE_MINUTE)
        seconds = math.floor(remainder)
        remainder = remainder - seconds
        millis = remainder
        return str(hours).zfill(2) + ':' + str(minutes).zfill(2) + ':' + str(seconds).zfill(2) + '.' + str(
            math.floor(millis * 1000)).zfill(3)

    def convert_vtt_to_webcaptions(self, vtt_io):
        captions = []

        for vttcaption in webvtt.read_buffer(vtt_io):
            caption = {
                "start": self.format_timeVtt_to_seconds(vttcaption.start),
                "end": self.format_timeVtt_to_seconds(vttcaption.end),
                "caption": vttcaption.text
            }
            captions.append(caption)

        return captions

    def convert_webcaptions_to_vtt(self, captions):
        vtt = 'WEBVTT\n\n'

        for i, caption in enumerate(captions, start=1):
            vtt += f"{i}\n"
            vtt += self.format_seconds_to_timeVtt(float(caption["start"])) + ' --> ' + self.format_seconds_to_timeVtt(
                float(caption["end"])) + '\n'
            vtt += caption["caption"] + '\n\n'

        return vtt.rstrip()

    def convert_webcaptions_to_html(self, captions):
        marker = "<span>"
        inputEntries = map(lambda c: c["caption"], captions)
        inputDelimited = marker.join(inputEntries)

        return inputDelimited

    def DelimitedToWebCaptions(self, sourceWebCaptions, delimitedCaptions, delimiter, maxCaptionLineLength):

        delimitedCaptions = html.unescape(delimitedCaptions)

        entries = delimitedCaptions.split(delimiter)

        outputWebCaptions = []
        for i, c in enumerate(sourceWebCaptions):
            caption = {}
            caption["start"] = c["start"]
            caption["end"] = c["end"]
            caption["caption"] = entries[i]
            caption["sourceCaption"] = c["caption"]
            outputWebCaptions.append(caption)

        return outputWebCaptions

    def add_subtitle_content_to_video(self, video, language, vtt_content):
        new_subtitle = Subtitle.objects.filter(video=video, language=language).order_by('-pk').first()
        if not new_subtitle:
            new_subtitle = Subtitle(
                video=video,
                tenant=video.tenant,
                language=language,
                is_transcript=False,
                user_id=1,
            )
        new_subtitle.status = Subtitle.SubtitleStatus.AUTO_GENERATED
        new_subtitle.is_automatic = True
        new_subtitle.origin = Subtitle.Origin.AWS

        new_subtitle.save()

        # (new_subtitle, created) = Subtitle.objects.update_or_create(
        #     video=video,
        #     tenant=video.tenant,
        #     language=language,
        #     is_transcript=False,
        #     defaults={
        #         'status': Subtitle.SubtitleStatus.AUTO_GENERATED,
        #         'last_update': timezone.now(),
        #         'user_id': 1,
        #         'is_automatic': True,
        #         'origin': Subtitle.Origin.AWS,
        #     }
        # )

        new_subtitle_file = SubtitleFile(
            subtitle=new_subtitle, date=timezone.now(), user_id=1, tenant=video.tenant,
        )

        new_subtitle_file.file.name = (
                settings.MEDIA_ROOT
                + "subtitles/"
                + str(new_subtitle.id)
                + "_"
                + str(new_subtitle.language)
                + "_"
                + str(new_subtitle_file.date.strftime("%d%m%y-%H%M%S"))
                + ".vtt"
        )
        # Write content to a file
        file = io.open(new_subtitle_file.file.path, "w", encoding="utf-8")
        file.write(vtt_content)
        file.close()

        new_subtitle_file.save()

        return new_subtitle, new_subtitle_file

    def translate(self, source_subtitle: Subtitle, target_languages, initiator=None):
        assert isinstance(target_languages, (list, QuerySet))
        assert all(isinstance(l, IsoLanguage) for l in target_languages)

        video = source_subtitle.video

        with open(source_subtitle.latest_subtitle_file, "r", encoding='utf-8') as f:
            webcaptions_source = self.convert_vtt_to_webcaptions(f)

        html_delimited = self.convert_webcaptions_to_html(webcaptions_source)
        count_source_characters = sum(len(w['caption']) for w in webcaptions_source)

        translation_info = {
            'target_languages': [l.iso_code for l in target_languages],
            'subtitle_file_id': source_subtitle.subtitlefile_set.order_by('-date').first().pk,
            'job_ids': {},
            'waiting_job_ids': [],
            'service_provider_use': {},
        }

        for lang in target_languages:
            res = self.session.post(
                self.base_url,
                headers={
                    "Authorization": f"DeepL-Auth-Key {self.auth_key}",
                },
                data={
                    "text": html_delimited,
                    "source_lang": source_subtitle.language.iso_code,
                    "target_lang": lang.iso_code,
                    "tag_handling": "xml",
                }
            )

            res.raise_for_status()

            j = res.json()

            su = ServiceProviderUse(
                tenant=source_subtitle.tenant,
                video=source_subtitle.video,
                service_provider=ServiceProviderUse.ServiceProvider.DEEPL,
                initiated_by=initiator,
            )

            su.data = {
                'DEEPL_WORKFLOW': "DEEPL-STANDALONE_v1",
                'source_language': source_subtitle.language.iso_code,
                'target_language': lang.iso_code,
                'characters': count_source_characters,
            }
            su.save()
            translation_info['service_provider_use'][lang.iso_code] = {
                'id': su.pk,
            }

            delimited_translated_text = j["translations"][0]["text"].replace("</span>", "")

            webcaptions = self.DelimitedToWebCaptions(webcaptions_source, delimited_translated_text, "<span>", 15)
            vtt_content = self.convert_webcaptions_to_vtt(webcaptions)

            self.add_subtitle_content_to_video(
                video=video,
                language=lang,
                vtt_content=vtt_content
            )
