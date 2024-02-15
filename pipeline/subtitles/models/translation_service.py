from django.db import models

from django.utils.translation import gettext_lazy as _


class TranslationService(models.TextChoices):
    MLLP = "MLLP", _("MLLP")
    AWS = "AWS", _("AWS")
    MANUAL = "MANUAL", _("Manual")
    DEEPL = "DEEPL", _("DEEPL")
