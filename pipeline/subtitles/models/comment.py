from django.conf import settings
from django.db import models


class Comment(models.Model):
    """
    Comment represents a single comment assigned to a video.
    """

    video = models.ForeignKey("Video", on_delete=models.CASCADE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created = models.DateTimeField(auto_now_add=True)

    content = models.TextField()
    for_language = models.ForeignKey("subtitles.IsoLanguage", on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"Comment:{self.pk}"
