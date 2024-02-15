from typing import List

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse

from core.models import TranspipeUser
from subtitles.models import Subtitle


class SubtitleStatusChangeService:

    def status_changed(self, subtitle: Subtitle, previous_status=None):
        current_status = subtitle.status

        if previous_status == Subtitle.SubtitleStatus.IN_PROGRESS and current_status == Subtitle.SubtitleStatus.AUTO_GENERATED:
            # automatic translation finished
            self.notify_about_finished_workflow(subtitle, previous_status)

        elif current_status == Subtitle.SubtitleStatus.WAITING_FOR_REVIEW:
            # Notify QA Manager
            self.notify_qa_managers(subtitle, previous_status)
        elif current_status == Subtitle.SubtitleStatus.CHANGES_REQUESTED:
            # Notify Assignees + last editor
            self.notify_editors_about_requested_changes(subtitle, previous_status)
        else:
            pass

    def notify_about_finished_workflow(self, subtitle, previous_status):
        video = subtitle.video
        course = video.course_section.course

        users_to_notify: List[TranspipeUser] = list(course.transpipeuser_set.distinct())
        assignees = TranspipeUser.objects.filter(subtitleassignment__subtitle=subtitle).distinct()
        users_to_notify.extend(assignees)

        for user in users_to_notify:
            message = render_to_string('mails/workflow_completed.html', {
                'user': user,
                'course': course,
                'video': video,
                'subtitle': subtitle,
                'url': self.get_overview_url(subtitle.tenant, course),
            })

            user.email_user(
                subject=f"Workflow finished for {course.title} / {video.title}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
            )

    def notify_qa_managers(self, subtitle, previous_status):
        video = subtitle.video
        course = video.course_section.course

        users_to_notify: List[TranspipeUser] = list(course.transpipeuser_set.distinct())
        assignees = TranspipeUser.objects.filter(subtitleassignment__subtitle=subtitle).distinct()
        users_to_notify.extend(assignees)

        for user in set(users_to_notify):
            message = render_to_string('mails/subtitle_waiting_for_review.html', {
                'user': user,
                'course': course,
                'video': video,
                'subtitle': subtitle,
                'url': self.get_video_editor_url(subtitle.tenant, course, video),
            })

            user.email_user(
                subject=f"Video waiting for review {course.title} / {video.title}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
            )

    def notify_editors_about_requested_changes(self, subtitle, previous_status):
        video = subtitle.video
        course = video.course_section.course

        users_to_notify: List[TranspipeUser] = list(course.transpipeuser_set.distinct())
        assignees = TranspipeUser.objects.filter(subtitleassignment__subtitle=subtitle).distinct()
        users_to_notify.extend(assignees)
        # TODO add last editor

        for user in set(users_to_notify):
            message = render_to_string('mails/changes_requested.html', {
                'user': user,
                'course': course,
                'video': video,
                'subtitle': subtitle,
                'url': self.get_overview_url(subtitle.tenant, course),
            })

            user.email_user(
                subject=f"Changes requested for video {course.title} / {video.title}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
            )

    def get_overview_url(self, tenant, course):
        return f"{settings.PUBLIC_ADDRESS}{reverse('mooclink.course.overview', args=[tenant.slug, course.ext_id])}"

    def get_video_editor_url(self, tenant, course, video):
        return f"{settings.PUBLIC_ADDRESS}{reverse('mooclink.video.index', args=[tenant.slug, course.ext_id, video.ext_id])}"
