import json
from datetime import datetime, timedelta

import celery
from dateutil.parser import parse
from django.db import models
from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.timezone import make_aware
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from embed_video.fields import EmbedVideoField

from .iso_language import IsoLanguage
from .subtitle import Subtitle
from .translation_service import TranslationService


class Video(models.Model):
    """ The videos that need to be transcribed and translated """

    title = models.CharField(max_length=200)
    original_language = models.ForeignKey("IsoLanguage", on_delete=models.CASCADE)
    pub_date = models.DateTimeField("date published", null=True, blank=True)
    course_section = models.ForeignKey("CourseSection", on_delete=models.CASCADE)
    video_url_pip = EmbedVideoField(max_length=1000)
    video_url_lecturer = EmbedVideoField(max_length=1000, null=True, blank=True)
    video_url_slides = EmbedVideoField(max_length=1000, null=True, blank=True)
    ext_id = models.CharField(max_length=200, unique=False)
    summary = models.TextField(null=True, blank=True)
    deprecated = models.BooleanField(default=False)
    index = models.IntegerField(null=True, blank=True, db_index=True)
    item_id = models.CharField(max_length=512, unique=False, db_index=True, null=True)

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)

    workflow_status = models.CharField(max_length=255, default=None, null=True, blank=True)
    workflow_data = models.JSONField(default=dict, blank=True)

    class Meta:
        permissions = (
            ('start_translation', "Can start translation"),
            ('start_transcription', "Can start transcription"),
            ('start_standalone_translation', "Can start standalone translation"),
            ('assign_user', "Can assign user to subtitles"),
            ('cancel_workflow', "Can cancel workflow"),
        )
        ordering = ['index']
        unique_together = ['tenant_id', 'ext_id']

    @property
    def number_of_subtitles(self):
        number_of_subtitles = 0
        number_of_subtitles += self.subtitle_set.all().count()
        return number_of_subtitles

    @property
    def number_of_published_subtitles(self):
        number_of_published_subtitles = 0
        number_of_published_subtitles += self.subtitle_set.filter(
            status=Subtitle.SubtitleStatus.PUBLISHED
        ).count()
        return number_of_published_subtitles

    @property
    def existing_languages(self):
        return [l for l in IsoLanguage.objects \
            .filter(subtitle__video=self, subtitle__is_transcript=False) \
            .distinct() if (l in self.languages_of_course)]

    @property
    def languages_of_course(self):
        return self.course_section.course.translated_languages

    @property
    def missing_languages(self):
        course_languages = self.course_section.course.translated_languages.order_by('description').all()
        return [l for l in course_languages if l not in self.existing_languages]

    @property
    def languages(self):
        return IsoLanguage.objects.filter(
            Q(assignedlanguage__course=self.course_section.course) | Q(pk=self.original_language.pk)
        ) \
            .order_by('description') \
            .distinct()

    @property
    def translated_languages(self):
        return IsoLanguage.objects.filter(assignedlanguage__course=self.course_section.course) \
            .order_by('description') \
            .all()

    def get_subtitle(self, language):
        return self.subtitle_set.filter(language=language).order_by('-pk').first()

    @cached_property
    def current_transcript(self):
        return self.subtitle_set.filter(is_transcript=True).order_by('-pk').first()

    @property
    def platform_link(self):
        return f"{self.tenant.get_secret('PLATFORM_URI', raise_exception=False)}/courses/{self.course_section.course.ext_id}/items/{self.item_id}"

    def start_workflow(self, language=None, translate=False, provider='AWS', user=None):
        from core.tasks import task_mllp_start_transcription

        subtitle = self.subtitle_set.filter(language=language).order_by('-pk').first()
        if not subtitle:
            subtitle = Subtitle(
                status=Subtitle.SubtitleStatus.IN_PROGRESS,
                origin=Subtitle.Origin.AWS,
                language=language or self.original_language,
                video=self,
                is_transcript=(self.original_language == language),
                last_update=make_aware(datetime.now()),
                user_id=1,
                tenant=self.tenant,
            )
        subtitle.status = Subtitle.SubtitleStatus.IN_PROGRESS
        subtitle.save()

        course = self.course_section.course

        if course.transcription_service == TranslationService.MLLP:
            self.workflow_status = "MLLP_INITIATED"

            subtitle.status = Subtitle.SubtitleStatus.IN_PROGRESS
            subtitle.save()

            task_mllp_start_transcription.delay(self.pk, user.pk)
            schedule, created = IntervalSchedule.objects.get_or_create(
                every=10,
                period=IntervalSchedule.MINUTES,
            )

            periodic = PeriodicTask.objects.create(
                interval=schedule,
                name=f'Check mllp for video={self.pk}',
                task='core.tasks.task_update_mllp_video_status',
                start_time=datetime.now() + timedelta(minutes=15),
                kwargs=json.dumps({
                    'video_id': self.pk,
                    'user_id': user.id,
                })
            )

            self.workflow_data['type'] = 'MLLP_TRANSCRIPTION_v1'
            self.workflow_data['periodic_task_id'] = periodic.pk
            self.workflow_data['initiated'] = str(datetime.utcnow())

        elif course.transcription_service == TranslationService.AWS:
            self.workflow_status = "AWS_INITIATED"
            subtitle.status = Subtitle.SubtitleStatus.IN_PROGRESS
            subtitle.save()
            subtitle.origin = Subtitle.Origin.AWS

            # TODO restart workflow on translation subtitles should issue standalone translation on aws
            celery.current_app.send_task(
                'core.tasks.task_aws_start_transcription_only',
                args=(self.pk, user.pk if user else None),
            )

            schedule, created = IntervalSchedule.objects.get_or_create(
                every=10,
                period=IntervalSchedule.MINUTES,
            )

            periodic = PeriodicTask.objects.create(
                interval=schedule,
                name=f'Check AWS Transcription2 for video={self.pk}',
                task='core.tasks.task_aws_update_transcription_only',
                start_time=datetime.now() + timedelta(minutes=15),
                kwargs=json.dumps({
                    'video_id': self.pk,
                })
            )

            self.workflow_data['type'] = 'AWS_TRANSCRIPTION_v2'
            self.workflow_data['periodic_task_id'] = periodic.pk
            self.workflow_data['initiated'] = str(datetime.utcnow())

        self.save()

    @property
    def video_url(self):
        return self.video_url_pip or self.video_url_lecturer or self.video_url_lecturer

    @property
    def is_workflow_in_progress(self):
        return self.workflow_status in {'AWS_INITIATED', 'MLLP_INITIATED'}

    @property
    def job_initiated(self):
        try:
            return parse(self.workflow_data["initiated"])
        except Exception:
            return "n/a"

    def __str__(self):
        return self.title
