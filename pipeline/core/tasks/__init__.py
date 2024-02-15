import logging
from time import sleep

from celery import shared_task

from core.models import TranspipeUser, Tenant
from mooclink.services.aws_translation_service import AwsTranslationService
from subtitles.api.aws_api import aws_start_transcription, aws_update_video_status, aws_start_transcription_only, \
    aws_update_transcription_only
from subtitles.api.mllp_api import mllp_start_transcription, update_mllp_video_status
from subtitles.api.xikolo_api import update_video_detail
from subtitles.models import Video

logger = logging.getLogger('__name__')


@shared_task(bind=True)
def task_mul(self, wait, r, x):
    for i in range(r):
        sleep(wait)
        logger.info(f"iteration {i}/{r}")

    return 'task successfully finished'


@shared_task(bind=True)
def task_update_video_detail(self, local_video_id, ext_video_id):
    result = update_video_detail(local_video_id, ext_video_id)


@shared_task(bind=True)
def task_aws_start_transcription(self, video_id):
    result = aws_start_transcription(video_id=video_id)


@shared_task(bind=True)
def task_aws_start_transcription_only(self, video_id, initiator_id=None):
    result = aws_start_transcription_only(video_id=video_id, initiator_id=initiator_id)


@shared_task(bind=True)
def task_aws_update_transcription_only(self, video_id):
    video = Video.objects.get(pk=video_id)
    result = aws_update_transcription_only(video=video)

    return result


@shared_task(bind=True)
def task_mllp_start_transcription(self, video_id, user_id):
    video = Video.objects.get(id=video_id)
    user = TranspipeUser(id=user_id)
    tenant = video.tenant

    result = mllp_start_transcription(request=None, video=video, tenant=tenant, user=user)


@shared_task(bind=True)
def task_aws_update_video_status(self, video_id):
    result = aws_update_video_status(video=None, video_id=video_id)


@shared_task(bind=True)
def task_update_mllp_video_status(self, video_id, user_id):
    video = Video.objects.get(pk=video_id)

    result = update_mllp_video_status(request=None, video=None, tenant_id=video.tenant_id,
                                      user_id=user_id, video_id=video_id)


@shared_task(bind=True)
def task_update_aws_standalone_translation_status(self, tenant_id, video_id):
    tenant = Tenant.objects.get(id=tenant_id)
    aws_translation_service = AwsTranslationService(tenant=tenant)

    result = aws_translation_service.fetch_translation_jobs(video_id=video_id)
