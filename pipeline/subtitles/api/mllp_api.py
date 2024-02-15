""" Handling of API calls to MLLP """

import json
import datetime
import os
from urllib.request import urlretrieve

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from core.models import Tenant, TranspipeUser
from mooclink.services import get_supported_languages
from . import get_runtime
from ..models import Subtitle, Video, IsoLanguage, ServiceProviderUse
from ..models.subtitle_file import SubtitleFile
from .libtlp import TLPSpeechClient
from ..models.translation_service import TranslationService


def get_speech_client(tenant: Tenant):
    """Creating the TLPSpeechClient"""
    tlp = TLPSpeechClient(
        tenant.get_secret('MLLP_API_URL'),
        tenant.get_secret('MLLP_MEDIA_PLAYER_URL'),
        tenant.get_secret('MLLP_API_USER'),
        tenant.get_secret('MLLP_API_KEY'),
    )
    return tlp


def update_mllp_video_status(request, video, tenant_id=None, user_id=None, video_id=None):
    """ This function updates the MLLP subtitles when they are still 'in progress' """

    if video_id:
        video = Video.objects.get(pk=video_id)

    if tenant_id:
        tenant = Tenant.objects.get(pk=tenant_id)
    else:
        tenant = None

    if user_id:
        user = TranspipeUser.objects.get(pk=user_id)
    else:
        user = None

    mllp_subtitles_in_progress = Subtitle.objects.filter(
        origin=Subtitle.Origin.MLLP,
        status=Subtitle.SubtitleStatus.IN_PROGRESS,
        video=video,
        last_update__lte=(timezone.now() - datetime.timedelta(minutes=5)),
        tenant=tenant,
    )

    for subtitle in mllp_subtitles_in_progress:
        # If update is older than 5 mins
        if subtitle.last_update <= (timezone.now() - datetime.timedelta(minutes=5)):
            mllp_download_subtitle_file(request, subtitle, tenant, user)


def mllp_delete_media(video, ext_id=None):
    tlp = get_speech_client(tenant=video.tenant)

    tlp.api_ingest_delete(ext_id or video.ext_id)

    return tlp.ret_data


def mllp_start_transcription(request, video, tenant=None, user=None):
    """ This function sends a video to MLLP and inserts a new subtitle object into the database  """

    if not tenant:
        tenant: Tenant = video.tenant

    if not user:
        user = request.user

    #create api call MLLP
    tlp = get_speech_client(tenant=tenant)
    #  Setting manifest options
    tlp.manifest_init(video.ext_id)
    tlp.manifest_set_metadata(
        language=video.original_language.iso_code,
        title=f"{video.course_section.course.title}/{video.title}"
    )
    tlp.manifest_set_main_media_file(video.video_url)

    tlp.manifest_set_options(test_mode=False)

    translated_languages = IsoLanguage.objects.filter(assignedlanguage__course=video.course_section.course)\
        .order_by('description') \
        .distinct()

    supported_languages = get_supported_languages(service=TranslationService.MLLP)

    for lang in translated_languages:
        if lang in supported_languages:
            tlp.manifest_add_subtitles_request(lang.iso_code)
        else:
            # TODO propagate errors somehow to user
            pass

    videofilename = str(video.id) + ".mp4"
    videodir = os.path.join(settings.MEDIA_ROOT, 'tmp')
    os.makedirs(videodir, exist_ok=True)
    local_video_path = os.path.join(videodir, videofilename)

    urlretrieve(video.video_url, local_video_path)

    try:
        video_duration, video_frame_count = get_runtime(local_video_path)
    except Exception:
        video_duration, video_frame_count = 0, 0

    if os.path.isfile(local_video_path):
        os.remove(local_video_path)
    else:
        print("The file does not exist")

    tlp.api_ingest_new()

    print("-->", tlp.get_printable_response_data())

    # Status becomes in progress:
    status_in_progress = Subtitle.SubtitleStatus.IN_PROGRESS

    new_subtitle = Subtitle.objects.filter(video=video, language=video.original_language, is_transcript=True)\
        .order_by('-pk').first()

    if not new_subtitle:
        new_subtitle = Subtitle(
            language=video.original_language,
            video=video,
            is_transcript=True,
            status=status_in_progress,
            origin=Subtitle.Origin.MLLP,
            last_update=timezone.now(),
            user=user,
            tenant=tenant
        )

    new_subtitle.status=status_in_progress
    new_subtitle.origin = Subtitle.Origin.MLLP
    new_subtitle.is_automatic = True
    new_subtitle.user = user

    su = ServiceProviderUse(
        tenant=tenant,
        video=video,
        service_provider=ServiceProviderUse.ServiceProvider.MLLP,
        initiated_by=user,
    )

    su.data = {
        'MLLP_WORKFLOW': "MLLP_NORMAL_v1",
        'source_language': video.original_language.iso_code,
        'video_duration': video_duration,
        'video_frame_count': video_frame_count,
    }
    su.save()

    new_subtitle.save()


def mllp_status(video):
    tenant: Tenant = video.tenant

    tlp = get_speech_client(tenant=tenant)

    tlp.api_status('up-99162cae-cc66-4964-acbe-a26fe398a52a')

    return tlp.ret_data


def mllp_download_subtitle_file(request, subtitle, tenant=None, user=None):
    """ Download subtitle file from MLLP"""

    print("mllp_download_subtitle_file")

    if not tenant:
        tenant: Tenant = subtitle.tenant

    if not user:
        if request:
            user = request.user
        else:
            user = tenant.transpipeuser_set.first()

    # create api call MLLP
    try:
        video = subtitle.video
        # check if subtitle file is available
        tlp = get_speech_client(tenant=tenant)
        tlp.api_langs(video.ext_id)
        print("->", tlp.get_printable_response_data())
        langs = json.loads(tlp.get_printable_response_data())

        # tlp = get_speech_client(tenant=tenant)
        # tlp.api_status('up-8ba89e87-42dc-40a3-b23e-0a703d9ba96a')
        #
        # print("--->", tlp.get_printable_response_data())
        #
        # return

        subtitle_available = False
        for lang in langs["langs"]:
            if lang["lang_code"] == subtitle.language.iso_code:
                subtitle_available = True
        if not subtitle_available:
            return False

        new_subtitle_file = SubtitleFile(
            subtitle=subtitle,
            date=timezone.now(),
            user=user,  # TODO: create auto-download-user or something comparable
            tenant=tenant
        )

        new_subtitle_file.file.name = (
            settings.MEDIA_ROOT
            + "subtitles/"
            + str(subtitle.id)
            + "_"
            + str(subtitle.language)
            + "_"
            + str(new_subtitle_file.date.strftime("%d%m%y-%H%M%S"))
            + ".vtt"
        )

        new_subtitle_file.save()

        subtitle.status = Subtitle.SubtitleStatus.AUTO_GENERATED
        # Update timestamp:
        subtitle.last_update = new_subtitle_file.date
        # save subtitle on DB
        subtitle.save()

        # clear block
        video.workflow_status = None

        # Write response data to file
        tlp.api_get(video.ext_id, subtitle.language.iso_code, form="vtt")
        tlp.save_response_data(new_subtitle_file.file.name)

        with transaction.atomic():
            if periodic_task_id := video.workflow_data.get('periodic_task_id'):
                PeriodicTask.objects.get(pk=periodic_task_id).delete()
                video.workflow_data['cleared'] = True

            video.save()

    except TypeError:
        return False
    return True


def mllp_start_translation(user: TranspipeUser, video, selected_language):
    """Starting the translation of videos using MLLP"""

    tenant: Tenant = user.tenant

    tlp = get_speech_client(tenant=tenant)

    tlp.manifest_init(video.ext_id)
    tlp.manifest_add_subtitles_request(selected_language.iso_code)
    tlp.manifest_set_metadata(
        language=video.original_language.iso_code, title=video.title
    )
    tlp.manifest_set_options(
        generate=True, regenerate="tl", force=False, test_mode=False
    )
    tlp.api_ingest_update()

    print(tlp.get_printable_response_data())

    # Add new subtitle
    new_translation = Subtitle(
        language=selected_language,
        video=video,
        is_transcript=False,
        status=Subtitle.SubtitleStatus.IN_PROGRESS,
        last_update=timezone.now(),
        origin=Subtitle.Origin.MLLP,
        user=user,
        tenant=tenant,
    )
    new_translation.save()
