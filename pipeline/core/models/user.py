from django.contrib.auth.models import AbstractUser
from django.db import models

from core.utils import get_initials


class TranspipeUser(AbstractUser):
    tenant = models.ForeignKey("Tenant", on_delete=models.CASCADE, default=1)
    tenants = models.ManyToManyField("Tenant", related_name='tenants_list')

    assigned_languages = models.ManyToManyField("subtitles.IsoLanguage", blank=True)
    assigned_courses = models.ManyToManyField("subtitles.Course", blank=True)

    initials = models.CharField(max_length=16)

    @property
    def get_initials(self):
        return self.initials or get_initials(self)

    class Meta:
        permissions = (
            ('can_transcript_all_languages', "Can transcript ALL languages"),
            ('can_translate_all_languages', "Can translate ALL languages"),
            ('can_see_all_courses', "Can see ALL courses"),
            ('download_summary', "Can download summary"),
            ('can_use_preview_features', "Can use preview / beta features"),
            ('see_todo', "Can see and use Todo / Tasklist"),
            ('can_see_service_provider_usage', "Can see Service Provider Usage"),
        )
