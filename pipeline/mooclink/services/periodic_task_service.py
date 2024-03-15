import json
from datetime import datetime, timedelta

from django_celery_beat.models import IntervalSchedule, PeriodicTask


class PeriodicTaskService:

    @classmethod
    def create_periodic_task(cls, service_type, task, video, start_time=None, end_time=None):
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=10,
            period=IntervalSchedule.MINUTES,
        )

        if PeriodicTask.objects.filter(name=f"Check AWS StandaloneTranslation for video={video.pk}").count():
            return

        periodic = PeriodicTask.objects.create(
            interval=schedule,
            name=f'Check AWS StandaloneTranslation for video={video.pk}',
            task=task,
            start_time=datetime.now() + timedelta(minutes=15),
            kwargs=json.dumps({
                'tenant_id': video.tenant_id,
                'video_id': video.pk,
            })
        )

        return periodic