import io

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Subtitle(models.Model):
    """ The subtitles that we translate in our application """

    class SubtitleStatus(models.TextChoices):
        INITIAL = "IT", _("Initial")
        IN_PROGRESS = "IN", _("In Progress")
        AUTO_GENERATED = "AU", _("Auto Generated")
        EDITED = "ED", _("Edited")
        REVIEWED = "RE", _("Reviewed")
        UPLOADED_BY_USER = "UP", _("Uploaded by user")
        PUBLISHED = "PU", _("Published")
        QUEUED = "QU", _("Queued")
        WAITING_FOR_REVIEW = "WA", _("Waiting for review")
        CHANGES_REQUESTED = "CH", _("Changes Requested")
        APPROVED = "AP", _("Approved")

    status = models.CharField(
        max_length=2,
        choices=SubtitleStatus.choices,
        default=SubtitleStatus.IN_PROGRESS,
    )

    class Origin(models.TextChoices):
        MLLP = "MLLP", _("MLLP")
        AWS = "AWS", _("AWS")
        DEEPL = "DEEPL", _("DEEPL")
        MANUAL_UPLOAD = "MANU", _("Manual upload")
        MOOC = "MOOC", _("Downloaded from MOOC platform")

    origin = models.CharField(
        max_length=8, choices=Origin.choices, default=Origin.MANUAL_UPLOAD,
    )

    language = models.ForeignKey("IsoLanguage", on_delete=models.CASCADE)
    video = models.ForeignKey("Video", on_delete=models.CASCADE)
    is_transcript = models.BooleanField()
    last_update = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)

    is_automatic = models.BooleanField(default=True)

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)

    class Meta:
        permissions = (
            ('upload_subtitle_file', "Can upload subtitle file"),
            ('fetch_subtitle', "Can fetch subtitle"),
            ('publish_subtitle_to_xikolo', "Can publish subtitle to xikolo"),
            ('approve_subtitle', "Can approve subtitle"),
            ('request_changes_subtitle', "Request changes"),
            ('start_workflow_subtitle', "Start workflow"),
        )

    @property
    def type(self):
        if self.is_transcript is True:
            return "Transcript"
        else:
            return "Translation"

    @property
    def latest_content(self):
        subtitle_file = self.subtitlefile_set.order_by('-date').first()

        if not subtitle_file:
            return ''

        with io.open(subtitle_file.file.path, "r", encoding="utf-8") as file:
            subtitle_text = file.read()

        return subtitle_text

    @property
    def latest_subtitle_file(self):
        subtitle_file = self.subtitlefile_set.order_by('-date').first()

        if not subtitle_file:
            return None

        return subtitle_file.file.path

    @property
    def active_subtitle_assignments(self):
        return list(sorted(filter(lambda x: x.deleted is None, self.subtitleassignment_set.all()), key=lambda x: x.user_id))
        #.filter(deleted__isnull=True).order_by('user_id')

    @property
    def color_code(self):
        order = {
            Subtitle.SubtitleStatus.PUBLISHED: 0,
            Subtitle.SubtitleStatus.APPROVED: 0,
            Subtitle.SubtitleStatus.IN_PROGRESS: 1,
            Subtitle.SubtitleStatus.AUTO_GENERATED: 2,
            Subtitle.SubtitleStatus.CHANGES_REQUESTED: 2,
            Subtitle.SubtitleStatus.INITIAL: 3,
            None: 3,
        }

        return order.get(self.status, 3)

    def __str__(self):

        return (
            str(self.id)
            + " "
            + str(self.origin)
            + " - "
            + self.type
            + " in "
            + str(self.language)
            + ": "
            + str(self.get_status_display())
        )