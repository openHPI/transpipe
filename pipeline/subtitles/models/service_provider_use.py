from django.db import models

from django.utils.translation import gettext_lazy as _


class ServiceProviderUse(models.Model):
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)
    video = models.ForeignKey("subtitles.Video", db_index=True, blank=True, null=True, on_delete=models.SET_NULL)
    subtitle = models.ForeignKey("subtitles.Subtitle", db_index=True, blank=True, null=True, on_delete=models.SET_NULL)
    subtitle_file = models.ForeignKey("subtitles.SubtitleFile", db_index=True, blank=True, null=True,
                                      on_delete=models.SET_NULL)

    initiated_by = models.ForeignKey("core.TranspipeUser", null=True, blank=True, db_index=True,
                                     on_delete=models.SET_NULL)
    initiated = models.DateTimeField(auto_now_add=True)

    class ServiceProvider(models.TextChoices):
        MLLP = "MLLP", _("MLLP")
        AWS_TRANSCRIPTION = "AWS_TRANSCRIPTION", _("AWS Transcription")
        AWS_TRANSLATION = "AWS_TRANSLATION", _("AWS Translation")
        DEEPL = "DEEPL", _("DEEPL")

        AUDESCRIBE_TRANSCRIPTION = "AUDESCRIBE_TRANSCRIPTION", _("Audescribe Transcription")

        OTHER = "OTHER", _("Other")

    service_provider = models.CharField(max_length=128, db_index=True, choices=ServiceProvider.choices,
                                        default=ServiceProvider.OTHER)

    data = models.JSONField(default=dict, blank=True)

    @property
    def billable_amount_str(self):
        if self.service_provider in {self.ServiceProvider.AWS_TRANSCRIPTION, self.ServiceProvider.MLLP}:
            return f"{self.billed_minutes} min."
        elif self.service_provider in {self.ServiceProvider.AWS_TRANSLATION, self.ServiceProvider.DEEPL}:
            return f"{self.data.get('characters')} chars."
        else:
            return "Unknown metric"

    @property
    def amount(self):
        if self.service_provider in {self.ServiceProvider.AWS_TRANSCRIPTION, self.ServiceProvider.MLLP}:
            return self.billed_minutes
        elif self.service_provider in {self.ServiceProvider.AWS_TRANSLATION, self.ServiceProvider.DEEPL}:
            return self.data.get('characters')
        else:
            return None

    @property
    def metric(self):
        if self.service_provider in {self.ServiceProvider.AWS_TRANSCRIPTION, self.ServiceProvider.MLLP}:
            return "Minutes"
        elif self.service_provider in {self.ServiceProvider.AWS_TRANSLATION, self.ServiceProvider.DEEPL}:
            return "Characters"
        else:
            return None

    @property
    def billed_minutes(self):
        video_duration = self.data.get('video_duration', 0.0)
        if not video_duration:
            return round(self.data.get('video_frame_count', 0.0) / 30.0 / 60.0, 2)

        return round(self.data.get('video_duration', 0.0) / 1000.0 / 60.0, 2)

    @property
    def billed_characters(self):
        return self.data.get('characters', 0)

