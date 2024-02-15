from django.conf import settings
from django.db import models


class SubtitleAssignment(models.Model):
    user = models.ForeignKey("core.TranspipeUser", db_index=True, on_delete=models.CASCADE)
    subtitle = models.ForeignKey("subtitles.Subtitle", db_index=True, on_delete=models.CASCADE)

    notification_sent = models.DateTimeField(default=None, null=True, blank=True, db_index=True)
    deleted = models.DateTimeField(default=None, null=True, blank=True, db_index=True)

    assigned_by = models.ForeignKey("core.TranspipeUser", db_index=True, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="created_subtitle_assignments")
