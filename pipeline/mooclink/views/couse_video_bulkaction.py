import itertools
import json
from datetime import datetime, timedelta
from operator import itemgetter

from django import views
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django_celery_beat.models import IntervalSchedule, PeriodicTask

from core.exceptions import SecretNotFound
from core.models import Tenant, TranspipeUser
from mooclink.services.aws_translation_service import AwsTranslationService
from mooclink.services.deepl_translation_service import DeeplTranslationService
from subtitles.api.xikolo_api import publish_subtitle_to_xikolo
from subtitles.models import Course, Video, IsoLanguage, Subtitle, SubtitleAssignment, AssignedLanguage
from subtitles.models.translation_service import TranslationService


class CourseSubscribe(PermissionRequiredMixin, LoginRequiredMixin, views.View):
    permission_required = ()

    def post(self, request, course_id, tenant_slug=None):
        tenant = Tenant.objects.get(slug=tenant_slug)

        course = Course.objects.get(tenant=tenant, ext_id=course_id)

        action = request.POST['action']

        if course in request.user.assigned_courses.all():
            request.user.assigned_courses.remove(course)
            message = "Course unsubscribed"
        else:
            request.user.assigned_courses.add(course)
            message = "Course subscribed"

        request.user.save()
        messages.success(request, message)

        return redirect('mooclink.course.overview', tenant_slug, course.ext_id)


class CourseBulkActionConfirmation(PermissionRequiredMixin, LoginRequiredMixin, views.View):
    permission_required = ('subtitles.assign_user',)

    def post(self, request, course_id, tenant_slug=None):
        tenant = Tenant.objects.get(slug=tenant_slug)

        course = Course.objects.get(tenant=tenant, ext_id=course_id)

        action = request.POST['action']

        if action == 'notify_persons':
            subtitle_assignments = SubtitleAssignment.objects\
                .filter(subtitle__video__course_section__course=course, notification_sent__isnull=True, deleted__isnull=True)\
                .order_by('user__email', 'subtitle__video__course_section__index', 'subtitle__video__index') \
                .all()

            with transaction.atomic():
                user: TranspipeUser
                url = f"{request.scheme}://{request.get_host()}{reverse('mooclink.course.overview', args=[tenant.slug, course.ext_id])}"

                for user, assignments in itertools.groupby(subtitle_assignments, key=lambda a: a.user):
                    message = render_to_string('mails/new_assigned_course.html', {
                        'request': request,
                        'user': user,
                        'assignments': assignments,
                        'url': url,
                    })

                    user.email_user(
                        subject="Videos Assigned",
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                    )

                    subtitle_assignments.update(notification_sent=timezone.now())

            messages.success(request, "Persons notified")

            return redirect('mooclink.course.overview', tenant.slug, course.ext_id)

        transcript_video_ids = request.POST.getlist('transcripts')
        videos_to_transcript = Video.objects \
            .filter(pk__in=transcript_video_ids) \
            .filter(tenant=tenant)

        translate_video_ids = request.POST.getlist('translations')
        videos_to_translate = []

        for m in translate_video_ids:
            iso_code, video_id = m.split('-', 1)
            language = IsoLanguage.objects.get(iso_code=iso_code)
            video = Video.objects.get(pk=video_id, tenant=tenant)

            videos_to_translate.append((language, video))

        if user_ids := request.POST.getlist('persons'):
            user_to_assign = TranspipeUser.objects.filter(pk__in=user_ids).all()
        else:
            user_to_assign = []

        return render(request, "mooclink/course/bulk_confirmation.html", {
            'videos_to_transcript': videos_to_transcript,
            'videos_to_translate': videos_to_translate,
            'human_action': action,
            'course': course,
            'action': action,
            'tenant': tenant,
            'user_to_assign': user_to_assign
        })


class CourseDoBulkAction(PermissionRequiredMixin, LoginRequiredMixin, views.View):
    permission_required = ('subtitles.can_do_bulk_operations')

    def post(self, request, course_id, tenant_slug=None):
        tenant = Tenant.objects.get(slug=tenant_slug)

        course = Course.objects.get(tenant=tenant, ext_id=course_id)

        action = request.POST['action']

        transcript_video_ids = request.POST.getlist('transcripts')
        videos_to_transcript = Video.objects \
            .filter(pk__in=transcript_video_ids) \
            .filter(tenant=tenant)

        translate_video_ids = request.POST.getlist('translations')
        videos_to_translate = []

        for m in translate_video_ids:
            iso_code, video_id = m.split('-', 1)
            language = IsoLanguage.objects.get(iso_code=iso_code)
            video = Video.objects.get(pk=video_id, tenant=tenant)

            videos_to_translate.append((language, video))

        number_of_affected = 0

        if user_ids := request.POST.getlist('persons'):
            user_to_assign = list(TranspipeUser.objects.filter(pk__in=user_ids).all())
        else:
            user_to_assign = []

        if action == 'approve':
            if not request.user.has_perm('subtitles.bulk_approve'):
                raise PermissionDenied

            for video in videos_to_transcript:
                subtitle = video.current_transcript
                if subtitle:
                    subtitle.status = Subtitle.SubtitleStatus.APPROVED
                    subtitle.save()
                    number_of_affected += 1

            for (language, video) in videos_to_translate:
                subtitle = video.subtitle_set.filter(language=language).first()

                if subtitle:
                    subtitle.status = Subtitle.SubtitleStatus.APPROVED
                    subtitle.save()
                    number_of_affected += 1

        elif action == 'publish':
            if not request.user.has_perm('subtitles.bulk_publish'):
                raise PermissionDenied

            for video in videos_to_transcript:
                subtitle = video.current_transcript
                res = None
                if subtitle:
                    if not settings.DEBUG or tenant.is_staging:
                        res = publish_subtitle_to_xikolo(request, subtitle_id=subtitle.id)
                    else:
                        messages.info(request, "Bulk publishing to non-staging xikolo is disabled in debug-mode")

                    if res is True:
                        number_of_affected += 1

            for (language, video) in videos_to_translate:
                subtitle = video.subtitle_set.filter(language=language).first()
                res = None

                if subtitle:
                    if not settings.DEBUG or tenant.is_staging:
                        res = publish_subtitle_to_xikolo(request, subtitle_id=subtitle.id)
                    else:
                        messages.info(request, "Bulk publishing to non-staging xikolo is disabled in debug-mode")

                    if res is True:
                        number_of_affected += 1

        elif action == 'remove-approval':
            if not request.user.has_perm('subtitles.bulk_disapprove'):
                raise PermissionDenied

            for video in videos_to_transcript:
                subtitle = video.current_transcript
                if subtitle:
                    subtitle.status = Subtitle.SubtitleStatus.CHANGES_REQUESTED
                    subtitle.save()
                    number_of_affected += 1

            for (language, video) in videos_to_translate:
                subtitle = video.subtitle_set.filter(language=language).first()
                if subtitle:
                    subtitle.status = Subtitle.SubtitleStatus.CHANGES_REQUESTED
                    subtitle.save()

                number_of_affected += 1

        elif action == 'start-workflow':
            if not request.user.has_perm('subtitles.bulk_start_workflow'):
                raise PermissionDenied

            for video in videos_to_transcript:
                video.start_workflow(language=video.original_language, user=request.user)
                number_of_affected += 1

            if videos_to_translate:
                if tenant.aws_active:
                    aws_translation_service = AwsTranslationService(tenant=tenant)
                else:
                    aws_translation_service = None

                if tenant.deepl_active:
                    translation_service_deepl = DeeplTranslationService(tenant=tenant)
                else:
                    translation_service_deepl = None

                gp = itertools.groupby(videos_to_translate, key=itemgetter(1))

                video: Video
                for video, grouped in gp:
                    if video.current_transcript.status != Subtitle.SubtitleStatus.PUBLISHED:
                        messages.warning(request, "Cannot start bulk translation of unpublished transcription.")
                        continue

                    aws_languages = []
                    deepl_languages = []

                    # [language for language, _ in grouped]

                    for language, _ in grouped:
                        assigned_lang = AssignedLanguage.objects.get(course=course, iso_language=language)

                        if assigned_lang.translation_service == TranslationService.AWS:
                            aws_languages.append(language)
                        elif assigned_lang.translation_service == TranslationService.DEEPL:
                            deepl_languages.append(language)
                        else:
                            pass

                    if aws_languages:
                        if aws_translation_service is None:
                            messages.error(request, "Translation with AWS requested, but is not activated for this tenant.")
                            continue

                        aws_translation_service.translate(video.current_transcript,
                                                          target_languages=aws_languages,
                                                          initiator=request.user)
                        video.refresh_from_db(fields=["workflow_data", "workflow_status"])

                        schedule, created = IntervalSchedule.objects.get_or_create(
                            every=10,
                            period=IntervalSchedule.MINUTES,
                        )

                        periodic = PeriodicTask.objects.create(
                            interval=schedule,
                            name=f'Check AWS StandaloneTranslation for video={video.pk}',
                            task='core.tasks.task_update_aws_standalone_translation_status',
                            start_time=datetime.now() + timedelta(minutes=15),
                            kwargs=json.dumps({
                                'tenant_id': video.tenant_id,
                                'video_id': video.pk,
                            })
                        )

                        video.workflow_data['type'] = 'AWS_TRANSLATION_S_v1'
                        video.workflow_data['periodic_task_id'] = periodic.pk
                        video.workflow_data['initiated'] = str(datetime.utcnow())
                        video.save()

                    if deepl_languages:
                        if translation_service_deepl is None:
                            messages.error(request, "Translation with DeepL requested, but is not activated for this tenant.")
                            continue

                        translation_service_deepl.translate(video.current_transcript,
                                                          target_languages=deepl_languages,
                                                          initiator=request.user)

                    number_of_affected += 1

        elif action == 'delete':
            if not request.user.has_perm('subtitles.bulk_delete'):
                raise PermissionDenied

            for video in videos_to_transcript:
                video.subtitle_set.filter(is_transcript=True).delete()

                number_of_affected += 1

            for (language, video) in videos_to_translate:
                video.subtitle_set.filter(language=language).delete()
                number_of_affected += 1

            messages.error(request, "Deletion disabled")
        elif action == 'assign_persons':
            for video in videos_to_transcript:
                subtitle = video.current_transcript

                if not subtitle:
                    subtitle = Subtitle(
                        video=video,
                        language=video.original_language,
                        is_transcript=True,
                        user=request.user,
                        tenant=video.tenant,
                        last_update=timezone.now(),
                        status=Subtitle.SubtitleStatus.INITIAL,
                    )

                    subtitle.save()

                for user in user_to_assign:
                    SubtitleAssignment.objects.update_or_create(
                        user=user, subtitle=subtitle,
                        defaults={'deleted': None, 'assigned_by': request.user}
                    )

                number_of_affected += 1

                context = {'executor': request.user,
                           'absolute_url': request.build_absolute_uri(
                               reverse('mooclink.course.overview', args=(tenant_slug, course_id)))
                           }

                template = render_to_string("mooclink/emails/subtitle_assigned.html",
                                            context=context,
                                            request=request)
            for (language, video) in videos_to_translate:
                subtitle = video.subtitle_set.filter(language=language).order_by('-pk').first()

                if not subtitle:
                    subtitle = Subtitle(
                        video=video,
                        language=language,
                        is_transcript=False,
                        user=request.user,
                        tenant=video.tenant,
                        last_update=timezone.now(),
                        status=Subtitle.SubtitleStatus.INITIAL,
                    )

                    subtitle.save()

                for user in user_to_assign:
                    SubtitleAssignment.objects.update_or_create(user=user, subtitle=subtitle, defaults={'deleted': None})

                number_of_affected += 1

        elif action == 'remove-assignment':
            for video in videos_to_transcript:
                subtitle = video.current_transcript

                if subtitle:
                    SubtitleAssignment.objects.filter(subtitle=subtitle).update(deleted=timezone.now())

                    number_of_affected += 1

            for (language, video) in videos_to_translate:
                subtitle = video.subtitle_set.filter(language=language).first()

                if subtitle:
                    SubtitleAssignment.objects.filter(subtitle=subtitle).update(deleted=timezone.now())

                    number_of_affected += 1

        else:
            messages.error(request, f"Action {action} not available")

        if number_of_affected:
            request.user.assigned_courses.add(course)
            request.user.save()

        messages.success(request, f"Changed status of {number_of_affected} Subtitles to {action}d")
        return redirect('mooclink.course.overview', tenant_slug, course.ext_id)
