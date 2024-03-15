import html
import html
import io
import math
from io import BytesIO
from pprint import pprint
from uuid import uuid4

import boto3
import webvtt
from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from subtitles.models import Subtitle, IsoLanguage, SubtitleFile, Video, ServiceProviderUse

'''
VTT -> Webcaptions -> <span> delimited html and vice-versa inspired by 
https://github.com/aws-samples/amazon-translate-video-subtitles-captions-translation
'''


class AwsTranslationService:

    def __init__(self, tenant):
        self.tenant = tenant
        self.s3 = None
        self.aws_translate = None

        self.connect_to_s3()
        self.connect_to_translate()

        self.s3_bucket = self.tenant.get_secret('AWS_TRANSLATE_S3_BUCKET')

    def connect_to_s3(self):
        """
        returns a client to connect to S3 API
        """

        s3 = boto3.client(
            "s3",
            region_name=self.tenant.get_secret('AWS_REGION'),
            aws_access_key_id=self.tenant.get_secret('S3_ACCESS_KEY_ID'),
            aws_secret_access_key=self.tenant.get_secret('S3_SECRET_ACCESS_KEY'),
        )

        self.s3 = s3
        return s3

    def connect_to_translate(self):
        aws_translate = boto3.client('translate',
                                     region_name=self.tenant.get_secret('AWS_REGION'),
                                     aws_access_key_id=self.tenant.get_secret('AWS_TRANSLATE_KEY_ID'),
                                     aws_secret_access_key=self.tenant.get_secret('AWS_TRANSLATE_ACCESS_KEY'),
                                     )

        self.aws_translate = aws_translate
        return aws_translate

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

    def fetch_translated_subtitle(self, source_subtitle_file_id, job_folder, subtitle_filename, language):
        s3_key = f"{job_folder}{language}.{subtitle_filename}"
        s3_object = self.s3.get_object(Bucket=self.s3_bucket, Key=s3_key)

        source_subtitle_file = SubtitleFile.objects.get(pk=source_subtitle_file_id)

        translated_html_content = s3_object['Body'].read().decode('utf-8')

        with open(source_subtitle_file.file.path, "r", encoding='utf-8') as f:
            webcaptions_source = self.convert_vtt_to_webcaptions(f)

        webcaptions = self.DelimitedToWebCaptions(webcaptions_source, translated_html_content, "<span>", 15)
        vtt_content = self.convert_webcaptions_to_vtt(webcaptions)

        return vtt_content

    def fetch_translation_jobs(self, video_id):
        video = Video.objects.get(pk=video_id)

        a = self.aws_translate.list_text_translation_jobs(Filter={
            'JobName': video.workflow_data['u']
        })

        for completed_job in filter(lambda j: j['JobStatus'] == "COMPLETED", a['TextTranslationJobPropertiesList']):
            pprint(completed_job)

            cont = self.fetch_translated_subtitle(
                source_subtitle_file_id=video.workflow_data['subtitle_file_id'],
                job_folder=completed_job['OutputDataConfig']['S3Uri'].replace(f"s3://{self.s3_bucket}/", ""),
                subtitle_filename=video.workflow_data['s3_subtitle_filename'],
                language=completed_job['TargetLanguageCodes'][0]
            )

            language = IsoLanguage.objects.get(iso_code=completed_job['TargetLanguageCodes'][0])

            self.add_subtitle_content_to_video(
                video=video,
                language=language,
                vtt_content=cont
            )

            try:
                video.workflow_data['waiting_job_ids'].remove(completed_job['JobId'])
            except ValueError:
                pass

        if len(video.workflow_data['waiting_job_ids']) == 0:
            video.workflow_status = None
            if periodic_task_id := video.workflow_data.get('periodic_task_id'):
                PeriodicTask.objects.filter(pk=periodic_task_id).delete()
                video.workflow_data['cleared'] = True

        video.save()

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

        u = uuid4()
        s3_subtitle_filename = f"sub-{source_subtitle.pk}-{u}.html"

        print("Start translation to", target_languages)

        with open(source_subtitle.latest_subtitle_file, "r", encoding='utf-8') as f:
            webcaptions = self.convert_vtt_to_webcaptions(f)

        html_delimited = self.convert_webcaptions_to_html(webcaptions)
        html_delimited_io = BytesIO(html_delimited.encode('utf-8'))
        count_source_characters = sum(len(w['caption']) for w in webcaptions)

        r = self.s3.upload_fileobj(html_delimited_io, Bucket=self.s3_bucket,
                                   Key=f"input-{u}/{s3_subtitle_filename}")

        translation_info = {
            's3_subtitle_filename': s3_subtitle_filename,
            'target_languages': [l.iso_code for l in target_languages],
            'u': str(u),
            'subtitle_file_id': source_subtitle.subtitlefile_set.order_by('-date').first().pk,
            'job_ids': {},
            'waiting_job_ids': [],
            'service_provider_use': {},
        }

        # We need to loop, since TargetLanguageCodes is a list, but aws supports only a single target language.
        for lang in target_languages:
            res = self.aws_translate.start_text_translation_job(
                JobName=f"{u}-{lang.iso_code}",
                ClientToken=f"{u}-{lang.iso_code}",
                InputDataConfig={
                    'S3Uri': f's3://{self.s3_bucket}/input-{u}/',
                    'ContentType': 'text/html'
                },
                OutputDataConfig={
                    'S3Uri': f's3://{self.s3_bucket}/output-{u}/'
                },
                DataAccessRoleArn=self.tenant.get_secret('AWS_TRANSLATE_ROLE_ARN'),
                SourceLanguageCode=source_subtitle.language.iso_code,
                TargetLanguageCodes=[lang.iso_code],
            )

            translation_info['job_ids'][res['JobId']] = lang.iso_code
            translation_info['waiting_job_ids'].append(res['JobId'])

            su = ServiceProviderUse(
                tenant=source_subtitle.tenant,
                video=source_subtitle.video,
                service_provider=ServiceProviderUse.ServiceProvider.AWS_TRANSLATION,
                initiated_by=initiator,
            )

            su.data = {
                'JobId': res['JobId'],
                'AWS_WORKFLOW': "AWS_STANDALONE_v1",
                'source_language': source_subtitle.language.iso_code,
                'target_language': lang.iso_code,
                'characters': count_source_characters,
            }
            su.save()
            translation_info['service_provider_use'][res['JobId']] = {
                'id': su.pk,
            }

        source_subtitle.video.workflow_data = translation_info
        source_subtitle.video.workflow_status = "AWS_INITIATED"
        source_subtitle.video.save()
