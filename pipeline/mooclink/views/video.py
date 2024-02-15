import io
from datetime import datetime, timedelta
from typing import Set

from dateutil.parser import parse
from django import views
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.core.exceptions import SuspiciousOperation
from django.db.models import Q
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.timezone import make_aware
from django_celery_beat.models import PeriodicTask

from core.models import Tenant, TranspipeUser
from mooclink.services import can_user_view_video
from subtitles.api.xikolo_api import xikolo_download_subtitle_file
from subtitles.models import Course, Video, Comment, IsoLanguage, Subtitle
from subtitles.models.subtitle_file import SubtitleFile


class VideoDetailView(LoginRequiredMixin, PermissionRequiredMixin, views.View):
    permission_required = ()

    def get(self, request, tenant_slug, course_id, video_id):
        tenant = Tenant.objects.get(slug=tenant_slug)
        course = Course.objects.get(tenant=tenant, ext_id=course_id)
        video = Video.objects.get(course_section__course=course, tenant=tenant, ext_id=video_id)

        can_user_view_video(request, video, raise_ex=True)

        language = request.GET.get('language')

        transcript = Subtitle.objects.filter(video=video).filter(is_transcript=True).order_by('-pk').first()

        if language:
            selected_language = IsoLanguage.objects.get(iso_code=language)
            selected_translation = Subtitle.objects \
                .filter(video=video) \
                .filter(is_transcript=False) \
                .filter(language=language) \
                .order_by('-pk') \
                .first()
        else:
            selected_language = None
            selected_translation = None

        if comment_language_str := request.GET.get('comment_language'):
            comment_language = IsoLanguage.objects.get(iso_code=comment_language_str)
        elif selected_language:
            comment_language = selected_language
        else:
            comment_language = video.original_language

        comments = video.comment_set.filter(for_language=comment_language)

        selectable_comment_languages = IsoLanguage.objects \
            .filter(
            Q(comment__video=video) |
            Q(assignedlanguage__course=video.course_section.course) |
            Q(iso_code=(video.original_language.iso_code if video.original_language else None))
        ) \
            .order_by('description') \
            .distinct()

        workflow_duration_exceeded = None
        workflow_start_date = None
        if "initiated" in video.workflow_data:
            initated = parse(video.workflow_data["initiated"])

            workflow_duration_exceeded = (datetime.utcnow() - initated) > timedelta(hours=6)
            workflow_start_date = initated

        return render(request, "mooclink/video/index.html", {
            'course': course,
            'video': video,
            'current_language': selected_language,
            'transcript': transcript,
            'selected_translation': selected_translation,
            'comment_language': comment_language,
            'selected_iso': language,
            'comments': comments,
            'selectable_comment_languages': selectable_comment_languages,
            'tenant': tenant,
            'workflow_duration_exceeded': workflow_duration_exceeded,
            'workflow_start_date': workflow_start_date,
            'debug_flag': settings.DEBUG and False,
        })


class AddCommentToVideoView(LoginRequiredMixin, PermissionRequiredMixin, views.View):
    permission_required = ()

    def post(self, request, tenant_slug, course_id, video_id):
        tenant = Tenant.objects.get(slug=tenant_slug)
        course = Course.objects.get(tenant=tenant, ext_id=course_id)
        video = Video.objects.get(course_section__course=course, tenant=tenant, ext_id=video_id)

        can_user_view_video(request, video, raise_ex=True)

        text = request.POST['text']

        if language_str := request.POST['comment_language']:
            iso_language = IsoLanguage.objects.get(iso_code=language_str)
        else:
            iso_language = None

        comment = Comment(
            video=video,
            created_by=request.user,
            content=text,
            for_language=iso_language
        )

        course = video.course_section.course

        users_to_notify: Set[TranspipeUser] = set(course.transpipeuser_set.distinct())
        assignees = TranspipeUser.objects.filter(subtitleassignment__subtitle__video=video)
        previous_commenter = TranspipeUser.objects.filter(comment__video=video)

        if iso_language:
            assignees = assignees.filter(subtitleassignment__subtitle__language=iso_language)
            previous_commenter = previous_commenter.filter(comment__for_language=iso_language)
        else:
            assignees = assignees.filter(subtitleassignment__subtitle__is_transcript=True)
            previous_commenter = previous_commenter.filter(comment__for_language=video.original_language)

        users_to_notify.update(assignees.distinct())
        users_to_notify.update(previous_commenter.distinct())

        # do not send email to user who created the comment, even if he is subscribed
        users_to_notify.remove(request.user)

        public_url = f"{settings.PUBLIC_ADDRESS}{reverse('mooclink.video.index', args=[tenant.slug, course.ext_id, video.ext_id])}"

        for user in users_to_notify:
            message = render_to_string('mails/new_comment.html', {
                'user': user,
                'course': course,
                'video': video,
                'url': public_url
            })

            user.email_user(
                subject=f"New comment on video {video.title}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL
            )

        comment.save()

        if iso_code := request.POST.get('translation_language'):
            language = IsoLanguage.objects.get(iso_code=iso_code)
        else:
            language = None

        redirect_url = reverse(
            'mooclink.video.index',
            kwargs={'tenant_slug': tenant_slug, 'course_id': course_id, 'video_id': video_id}
        )

        url_parameters = {}
        if language:
            url_parameters['language'] = language.iso_code

        if iso_language:
            url_parameters['comment_language'] = iso_language.iso_code

        return redirect(redirect_url + (f"?{urlencode(url_parameters)}" if url_parameters else ""))


class SetWorkflowStatusView(LoginRequiredMixin, PermissionRequiredMixin, views.View):
    permission_required = ()

    def post(self, request, tenant_slug, course_id, video_id):
        tenant = Tenant.objects.get(slug=tenant_slug)
        course = Course.objects.get(tenant=tenant, ext_id=course_id)
        video = Video.objects.get(course_section__course=course, tenant=tenant, ext_id=video_id)
        status = request.POST['status']

        can_user_view_video(request, video, raise_ex=True)

        transcript = Subtitle.objects.filter(video=video).filter(is_transcript=True).first()

        # IN_PROGRESS = "IN", _("In Progress")
        # AUTO_GENERATED = "AU", _("Auto Generated")
        # REVIEWED = "RE", _("Reviewed")
        # UPLOADED_BY_USER = "UP", _("Uploaded by user")
        # PUBLISHED = "PU", _("Published")

        if status == "auto_generated":
            transcript.status = Subtitle.SubtitleStatus.AUTO_GENERATED
        elif status == "reviewed":
            transcript.status = Subtitle.SubtitleStatus.AUTO_GENERATED

        transcript.save()

        return redirect('mooclink.video.index', tenant_slug, course.ext_id, video.ext_id)


def save_subtitle_version(request, tenant, subtitle, text):
    # for windows systems
    text = text.replace("\r\n", "\n")

    if text == "":
        messages.error(request, "No changes were saved.")
    else:
        new_subtitle_file = SubtitleFile(
            subtitle=subtitle, date=timezone.now(), user=request.user, tenant=tenant
        )
        new_subtitle_file.file.name = (
                settings.MEDIA_ROOT
                + "subtitles/"
                + str(subtitle.id)
                + "_"
                + str(subtitle.language)
                + "_"
                + str(new_subtitle_file.date.strftime("%d%m%y-%H%M%S"))
                + ".vtt"
        )

        try:
            file = io.open(new_subtitle_file.file.path, "w", encoding="utf-8")
            file.write(text)
            file.close()
            subtitle.status = Subtitle.SubtitleStatus.EDITED
            subtitle.save()
            new_subtitle_file.save()

        except Exception:
            raise


class SaveTranscriptVersion(LoginRequiredMixin, PermissionRequiredMixin, views.View):
    permission_required = ()

    def post(self, request, tenant_slug, course_id, video_id):
        subtitle_id = request.POST['subtitle-id']

        tenant = Tenant.objects.get(slug=tenant_slug)
        course = Course.objects.get(tenant=tenant, ext_id=course_id)
        video = Video.objects.get(tenant=tenant, ext_id=video_id)

        can_user_view_video(request, video, raise_ex=True)

        if request.POST.get('is-transcript') == 't':
            language = video.original_language
        elif iso_code := request.POST.get('language'):
            language = IsoLanguage.objects.get(iso_code=iso_code)
        else:
            if not subtitle_id:
                raise ValueError("Would create new subtitle without language")
            language = None

        is_transcript = video.original_language == language
        is_automatic = (request.POST.get('is_automatic') == 'true')

        if subtitle_id:
            subtitle = Subtitle.objects.get(tenant=tenant, pk=subtitle_id)
        else:
            subtitle = Subtitle(
                status=Subtitle.SubtitleStatus.UPLOADED_BY_USER,
                origin=Subtitle.Origin.MANUAL_UPLOAD,
                language=language,
                video=video,
                is_transcript=is_transcript,
                last_update=make_aware(datetime.now()),
                user=request.user,
                tenant=tenant,
                is_automatic=is_automatic
            )
            subtitle.save()

        save_subtitle_version(request, tenant, subtitle, request.POST['transcription-content'])
        subtitle.status = subtitle.SubtitleStatus.EDITED
        subtitle.is_automatic = is_automatic
        subtitle.save()

        messages.success(request, f"Changes were saved.")

        redirect_url = reverse(
            'mooclink.video.index',
            kwargs={'tenant_slug': tenant_slug, 'course_id': course_id, 'video_id': video_id}
        )

        redirect_language = request.GET.get('language')

        return redirect(redirect_url + (f"?language={redirect_language}" if redirect_language else ""))


class FetchFromXikolo(LoginRequiredMixin, PermissionRequiredMixin, views.View):
    permission_required = ()

    def post(self, request, tenant_slug, course_id, video_id):
        tenant = Tenant.objects.get(slug=tenant_slug)
        course = Course.objects.get(pk=course_id)
        video = Video.objects.get(pk=video_id)
        language = IsoLanguage.objects.get(iso_code=request.POST['language'])

        can_user_view_video(request, video, raise_ex=True)

        is_transcript = video.original_language == language
        try:
            subtitle = video.subtitle_set.filter(language=language).order_by('-last_update').first()
        except Subtitle.DoesNotExist:
            subtitle = Subtitle(
                status=Subtitle.SubtitleStatus.AUTO_GENERATED,
                origin=Subtitle.Origin.MOOC,
                language=language,
                video=video,
                user=request.user,
                tenant=video.tenant,
                is_transcript=is_transcript,
                last_update=make_aware(datetime.now()),
            )

            subtitle.save()

        xikolo_download_subtitle_file(request, subtitle)

        messages.success(request, f"Subtitle for {language} successfully fetched.")

        language_arg = f"?language={language.iso_code}" if not is_transcript else ""
        return redirect(reverse('mooclink.video.index', args=[tenant_slug, course.ext_id, video.ext_id]) + language_arg)


class CancelWorkflowView(LoginRequiredMixin, PermissionRequiredMixin, views.View):
    permission_required = ('subtitles.cancel_workflow',)

    def post(self, request, tenant_slug, video_id):
        tenant = Tenant.objects.get(slug=tenant_slug)
        video = Video.objects.get(pk=video_id)

        course = video.course_section.course

        if tenant not in request.user.tenants.all():
            raise SuspiciousOperation("No access to this tenant")

        video.workflow_status = None
        if periodic_task_id := video.workflow_data.get('periodic_task_id'):
            PeriodicTask.objects.get(pk=periodic_task_id).delete()
            video.workflow_data['cleared'] = True
            video.workflow_data['cleared_reason'] = "Manual Cancellation"

        video.save()

        messages.success(request, "Workflow cancelled.")

        return redirect("mooclink.video.index", tenant_slug, course.ext_id, video.ext_id)
