from django.db import models


class IsoLanguage(models.Model):
    """
    IsoLanguage represents the Language of a subtitle or video.
    """

    iso_code = models.CharField(primary_key=True, max_length=5)
    description = models.CharField(max_length=200)
    is_rtl = models.BooleanField(default=False)

    def __str__(self):
        return self.description