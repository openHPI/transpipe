from typing import List

from django.db import models, transaction
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from subtitles.models.assigned_language import AssignedLanguage
from .iso_language import IsoLanguage
from .subtitle import Subtitle
from .translation_service import TranslationService


class SyncStatusChoices(models.TextChoices):
    IN_PROGRESS = "IN_PROGRESS", _("In Progress")
    SUCCESS = "SUCCESS", _("Success")
    ERROR = "ERROR", _("Error")
    INITIAL = "INITIAL", _("Initial")
    SKELETON = "SKELETON", _("Skeleton")

class Course(models.Model):
    """Course represents a course on a mooc plattform.

    API Integration to openHPI missing
    abstract - like on openHPI
    status - like on openHPI
    language - like on openHPI"""

    title = models.CharField(max_length=200)
    abstract = models.TextField(null=True)
    start_date = models.DateTimeField(null=True)
    end_date = models.DateTimeField(null=True)
    status = models.CharField(max_length=200, null=True)
    language = models.ForeignKey("IsoLanguage", on_delete=models.CASCADE)
    ext_id = models.CharField(max_length=200, unique=False)
    teacher = models.CharField(max_length=200, null=True)
    transcription_service = models.CharField(max_length=255, choices=TranslationService.choices,
                                             default=TranslationService.MANUAL)

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)

    sync_status = models.CharField(max_length=200, choices=SyncStatusChoices.choices, default=SyncStatusChoices.INITIAL)

    class Meta:
        permissions = (
            ('fetch_courses', "Can fetch courses"),
            ('download_summary', "Can download summary"),
            ('change_settings', "Can change settings"),
            ('synchronize_with_xikolo', "Can synchronize with xikolo"),
            ('can_do_bulk_operations', "Can do bulk operations"),
            ('bulk_start_workflow', "Can start workflow videos in bulk"),
            ('bulk_approve', "Can approve subtitles in bulk"),
            ('bulk_publish', "Can publish subtitles in bulk"),
            ('bulk_disapprove', "Can revoke approval of subtitles in bulk"),
            ('bulk_delete', "Can delete subtitles in bulk"),
            ('see_skeletons', "Can see skeletons"),
        )

        unique_together = ['tenant_id', 'ext_id']

    @property
    def number_of_course_sections(self):
        number_of_course_sections = self.coursesection_set.all().count()

        return number_of_course_sections

    @property
    def number_of_videos(self):

        number_of_videos = 0
        course_sections = self.coursesection_set.all()

        for course_section in course_sections:
            number_of_videos += course_section.video_set.all().count()

        return number_of_videos

    @property
    def number_of_subtitles(self):

        number_of_subtitles = 0

        for course_section in self.coursesection_set.all():
            for video in course_section.video_set.all():
                number_of_subtitles += video.subtitle_set.all().count()

        return number_of_subtitles

    @property
    def number_of_published_subtitles(self):
        number_of_published_subtitles = 0

        for course_section in self.coursesection_set.all():
            for video in course_section.video_set.all():
                number_of_published_subtitles += video.subtitle_set.filter(
                    status=Subtitle.SubtitleStatus.PUBLISHED
                ).count()

        return number_of_published_subtitles

    def add_translated_language(self, language, service_provider, required):
        if not self.assignedlanguage_set.filter(iso_language=language).count():
            assigned_language = AssignedLanguage(
                course=self,
                iso_language=language,
                translation_service=service_provider,
                required=required
            )

            assigned_language.save()

    @property
    def translated_languages(self):
        return IsoLanguage.objects.filter(assignedlanguage__course=self).order_by('description')

    @cached_property
    def assigned_iso_languages(self) -> List[IsoLanguage]:
        return [assignedlang.iso_language for assignedlang in self.assignedlanguage_set.all()]

    def add_languages(self, languages):
        iso_languages = IsoLanguage.objects.filter(iso_code__in=languages).all()

        with transaction.atomic():
            for language in iso_languages:
                if language == self.language:
                    continue

                if language not in self.assigned_iso_languages:
                    assigned_language = AssignedLanguage(
                        course=self,
                        iso_language=language,
                        translation_service=TranslationService.MANUAL,
                        required=False,
                    )
                    assigned_language.save()

    @property
    def platform_link(self):
        return f"{self.tenant.get_secret('PLATFORM_URI', raise_exception=False)}/courses/{self.ext_id}/sections"

    @property
    def is_skeleton(self):
        return self.sync_status == SyncStatusChoices.SKELETON

    @property
    def only_manual_provider(self):
        disable_workflow = True

        if self.transcription_service != TranslationService.MANUAL:
            disable_workflow = False

        for sp in self.assignedlanguage_set.all():
            if sp.translation_service != TranslationService.MANUAL:
                disable_workflow = False
                break

        return disable_workflow

    def __str__(self):
        return self.title
