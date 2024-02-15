from django.conf import settings
from django.db import models


class SubtitleFile(models.Model):
    """ Model for versioning of subtitles files"""

    subtitle = models.ForeignKey("Subtitle", on_delete=models.CASCADE)
    date = models.DateTimeField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    file = models.FileField(upload_to="subtitles/", null=True, max_length=500)

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)

    def __str__(self):
        return str(self.subtitle.language) + " Version from " + str(self.date)