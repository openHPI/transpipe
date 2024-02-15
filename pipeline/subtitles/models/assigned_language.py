from django.db import models

from subtitles.models.translation_service import TranslationService


class AssignedLanguage(models.Model):
    course = models.ForeignKey("Course", on_delete=models.CASCADE)
    iso_language = models.ForeignKey("IsoLanguage", on_delete=models.CASCADE)

    required = models.BooleanField(default=False)
    translation_service = models.CharField(max_length=255, choices=TranslationService.choices,
                                           default=TranslationService.MLLP)