from django.db import models


class AWSupload(models.Model):
    """ Helper object for handling the AWS API """

    video = models.ForeignKey("Video", on_delete=models.CASCADE)
    asset_id = models.CharField(max_length=200)
    # status = models.IntegerField(null=True)
    stage_id = models.CharField(max_length=200, null=True)
    upload_date = models.DateTimeField(null=True)
    source_lang = models.CharField(max_length=200, default="de")
    # subtitle = models.ForeignKey(Subtitle, on_delete=models.CASCADE, null=True)
    target_langs = models.ManyToManyField("IsoLanguage")

    aws_config = models.JSONField(default=None, null=True, blank=True)

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)


    def __str__(self):
        return str(self.video) + ": " + str(self.asset_id)