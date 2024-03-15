from uuid import uuid4

from django.db import models

from core.exceptions import SecretNotFound
from subtitles.models import Subtitle
from subtitles.models.translation_service import TranslationService


class Tenant(models.Model):
    uuid = models.UUIDField(default=uuid4, unique=True,
                            editable=False, db_index=True)

    slug = models.SlugField(null=True, db_index=True)
    active = models.BooleanField(default=True, db_index=True)
    name = models.CharField(max_length=512)
    all_courses_visible = models.BooleanField(default=True)

    secrets = models.JSONField(default=dict, blank=True)

    aws_active = models.BooleanField(default=True)
    mllp_active = models.BooleanField(default=True)
    deepl_active = models.BooleanField(default=False)
    audescribe_active = models.BooleanField(default=False)

    def get_secret(self, key, raise_exception=True, default=None):
        if key in self.secrets:
            return self.secrets[key]

        if raise_exception:
            raise SecretNotFound(f"Tenant {self.pk}, Secret {key}")

        return default

    # Properties to use as drop-in for settings
    @property
    def XIKOLO_API_URL(self):
        return self.get_secret('XIKOLO_API_URL')

    @property
    def XIKOLO_API_TOKEN(self):
        return self.get_secret('XIKOLO_API_TOKEN')

    @property
    def DATAPLANE_BUCKET(self):
        return self.get_secret('DATAPLANE_BUCKET')

    @property
    def active_cloud_services(self):
        l = []

        if self.aws_active:
            l.append(Subtitle.Origin.AWS)

        if self.mllp_active:
            l.append(Subtitle.Origin.MLLP)

        if self.deepl_active:
            l.append(Subtitle.Origin.DEEPL)

        if self.audescribe_active:
            l.append(Subtitle.Origin.AUDESCRIBE)

        l.append(TranslationService.MANUAL)

        return l

    @property
    def XIKOLO_MAX_PARALLEL_WORKERS(self):
        return self.get_secret('XIKOLO_MAX_PARALLEL_WORKERS')

    @property
    def is_staging(self):
        return 'staging' in self.name.casefold()

    def __str__(self):
        return f"<Tenant:{self.pk} {self.name}>"
