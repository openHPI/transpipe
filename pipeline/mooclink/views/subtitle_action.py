import json
from datetime import datetime, timedelta
from pprint import pprint

import celery
from django import views
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django_celery_beat.models import IntervalSchedule, PeriodicTask

from core.models import Tenant
from core.tasks import task_mllp_start_transcription
from mooclink.services import subtitle_status_change_service, can_user_view_video
from mooclink.services.aws_translation_service import AwsTranslationService
from mooclink.services.deepl_translation_service import DeeplTranslationService
from subtitles.api.aws_api import aws_update_video_status, aws_download_subtitle_file, aws_restart_workflow
from subtitles.api.mllp_api import mllp_download_subtitle_file, mllp_start_translation, update_mllp_video_status, \
    mllp_status, mllp_delete_media
from subtitles.api.xikolo_api import publish_subtitle_to_xikolo
from subtitles.models import Course, Video, Subtitle, IsoLanguage, AssignedLanguage
from subtitles.models.translation_service import TranslationService


class SubtitleToAction(LoginRequiredMixin, PermissionRequiredMixin, views.View):
    permission_required = ()

    def post(self, request, tenant_slug, course_id, video_id):
        action = request.POST['action']
        subtitle_id = request.POST['subtitle-id']
        language_str = request.POST.get('language')

        tenant = Tenant.objects.get(slug=tenant_slug)
        course = Course.objects.get(tenant=tenant, ext_id=course_id)
        video = Video.objects.get(tenant=tenant, ext_id=video_id)
        tenant = Tenant.objects.get(slug=tenant_slug)

        can_user_view_video(request, video, raise_ex=True)

        if language_str:
            language = IsoLanguage.objects.get(iso_code=language_str)
        else:
            language = None

        if subtitle_id:
            subtitle = Subtitle.objects.get(tenant=tenant, pk=subtitle_id)
        else:
            subtitle = None

        if not subtitle:
            subtitle = Subtitle(
                video=video,
                language=language or video.original_language,
                is_transcript=request.POST.get('is-transcript') is not None,
                user=request.user,
                tenant=tenant,
                last_update=datetime.now()
            )
            subtitle.save()
            messages.info(request, f"Subtitle object created")
            # return redirect('mooclink.video.index', tenant_slug, course_id, video_id)

        previous_status = subtitle.status

        if action == 'delete':
            Subtitle.objects.filter(tenant=tenant, video=video, language=subtitle.language).delete()
            subtitle.is_transcript = True  # disable selection of translation
        elif action == 'mllp_download_subtitle_file':
            r = mllp_download_subtitle_file(
                request, subtitle, tenant=tenant, user=request.user
            )

            pprint(r)

            return JsonResponse({
                'sdf': str(r)
            })
        elif action == 'update_mllp_video_status':
            r = update_mllp_video_status(
                request, video, tenant_id=tenant.pk, user_id=request.user.pk, video_id=video.pk
            )
            pprint(r)

            return JsonResponse({
                'sdf': str(r)
            })
        elif action == 'display_mllp_status':
            r = mllp_status(video)

            return JsonResponse({
                'response': r
            })
        elif action == 'aws_update_video_status':
            r = aws_update_video_status(
                video
            )

            pprint(r)

            return JsonResponse({
                'sdf': str(r)
            })
        elif action == 'aws_download_subtitle_file':
            r = aws_download_subtitle_file(
                subtitle,
            )

            pprint(r)

            return JsonResponse({
                'sdf': str(r)
            })
        elif action == 'aws_restart_workflow':
            r = aws_restart_workflow(
                request,
                video,
            )
            pprint(r)

            return JsonResponse({
                'sdf': str(r)
            })
        elif action == 'aws_fetch_translation_jobs':
            aws_translation_service = AwsTranslationService(tenant=tenant)

            r = aws_translation_service.fetch_translation_jobs(video_id=video.pk)

            return JsonResponse({
                'sdf': str(r)
            })

        elif action == 'request_approval':
            subtitle.status = Subtitle.SubtitleStatus.WAITING_FOR_REVIEW
            subtitle.save()
        elif action == 'request_changes':
            subtitle.status = Subtitle.SubtitleStatus.CHANGES_REQUESTED
            subtitle.save()
        elif action == 'approved':
            subtitle.status = Subtitle.SubtitleStatus.APPROVED
            subtitle.save()
        elif action == 'publish':
            publish_subtitle_to_xikolo(request, subtitle.id)
        elif action == 'restart_workflow':
            if subtitle and not subtitle.is_transcript:
                assigned_language = course.assignedlanguage_set.filter(iso_language__iso_code=request.POST['language'])\
                    .first()
                selected_language = IsoLanguage.objects.get(iso_code=request.POST['language'])

                assert assigned_language

                if assigned_language.translation_service == TranslationService.MLLP:
                    try:
                        mllp_delete_media(video=subtitle.video)
                    except Exception:
                        messages.error(request, "Error while deleting existing media on MLLP")

                    video.workflow_status = "MLLP_INITIATED"
                    mllp_start_translation(request.user, video, selected_language)

                    schedule, created = IntervalSchedule.objects.get_or_create(
                        every=10,
                        period=IntervalSchedule.MINUTES,
                    )

                    periodic = PeriodicTask.objects.create(
                        interval=schedule,
                        name=f'Check mllp for video={video.pk}',
                        task='core.tasks.task_update_mllp_video_status',
                        start_time=datetime.now() + timedelta(minutes=15),
                        kwargs=json.dumps({
                            'video_id': video.pk,
                            'user_id': request.user.pk
                        })
                    )

                    video.workflow_data['type'] = 'MLLP_TRANSCRIPTION_v1'
                    video.workflow_data['periodic_task_id'] = periodic.pk
                    video.workflow_data['initiated'] = str(datetime.utcnow())

                    video.save()
                elif assigned_language.translation_service == TranslationService.AWS:
                    video.workflow_status = "AWS_INITIATED"
                    subtitle.status = Subtitle.SubtitleStatus.IN_PROGRESS
                    subtitle.origin = Subtitle.Origin.AWS
                    subtitle.save()

                    celery.current_app.send_task(
                        'core.tasks.task_aws_start_transcription_only',
                        args=(video.pk, request.user.pk,)
                    )

                    schedule, created = IntervalSchedule.objects.get_or_create(
                        every=10,
                        period=IntervalSchedule.MINUTES,
                    )

                    periodic = PeriodicTask.objects.create(
                        interval=schedule,
                        name=f'Check AWS TranscriptionOnly for video={video.pk}',
                        task='core.tasks.task_aws_update_transcription_only',
                        start_time=datetime.now() + timedelta(minutes=15),
                        kwargs=json.dumps({
                            'video_id': video.pk,
                        })
                    )

                    video.workflow_data['type'] = 'AWS_TRANSCRIPTION_v2'
                    video.workflow_data['periodic_task_id'] = periodic.pk
                    video.workflow_data['initiated'] = str(datetime.utcnow())

                    video.save()
                else:
                    messages.info(request, "Cannot start workflow, since no Service Provider selected.")
            else:
                if course.transcription_service == TranslationService.MLLP:
                    try:
                        mllp_delete_media(video=subtitle.video)
                    except Exception:
                        messages.error(request, "Error while deleting existing media on MLLP")

                    video.workflow_status = "MLLP_INITIATED"
                    subtitle.status = Subtitle.SubtitleStatus.IN_PROGRESS
                    subtitle.save()

                    task_mllp_start_transcription.delay(video.pk, request.user.id)
                    schedule, created = IntervalSchedule.objects.get_or_create(
                        every=10,
                        period=IntervalSchedule.MINUTES,
                    )

                    periodic = PeriodicTask.objects.create(
                        interval=schedule,
                        name=f'Check mllp for video={video.pk}',
                        task='core.tasks.task_update_mllp_video_status',
                        start_time=datetime.now() + timedelta(minutes=15),
                        kwargs=json.dumps({
                            'video_id': video.pk,
                            'user_id': request.user.id,
                        })
                    )

                    video.workflow_data['type'] = 'MLLP_TRANSCRIPTION_v1'
                    video.workflow_data['periodic_task_id'] = periodic.pk
                    video.workflow_data['initiated'] = str(datetime.utcnow())

                    video.save()

                elif course.transcription_service == TranslationService.AWS:
                    # Transcript
                    video.workflow_status = "AWS_INITIATED"
                    subtitle.status = Subtitle.SubtitleStatus.IN_PROGRESS
                    subtitle.save()
                    subtitle.origin = Subtitle.Origin.AWS

                    celery.current_app.send_task(
                        'core.tasks.task_aws_start_transcription_only',
                        args=(video.pk, request.user.pk)
                    )

                    schedule, created = IntervalSchedule.objects.get_or_create(
                        every=10,
                        period=IntervalSchedule.MINUTES,
                    )

                    periodic = PeriodicTask.objects.create(
                        interval=schedule,
                        name=f'Check AWS TranscriptionOnly for video={video.pk}',
                        task='core.tasks.task_aws_update_transcription_only',
                        start_time=datetime.now() + timedelta(minutes=15),
                        kwargs=json.dumps({
                            'video_id': video.pk,
                        })
                    )

                    video.workflow_data['type'] = 'AWS_TRANSCRIPTION_v2'
                    video.workflow_data['periodic_task_id'] = periodic.pk
                    video.workflow_data['initiated'] = str(datetime.utcnow())

                    video.save()
                else:
                    messages.info(request, "Cannot start workflow, since no Service Provider selected.")
        elif action == 'translate_standalone':
            translation_service = AwsTranslationService(tenant=tenant)
            translation_service_deepl = DeeplTranslationService(tenant=tenant)
            original_subtitles = video.subtitle_set.filter(language=video.original_language)
            assert subtitle in original_subtitles

            target_languages = IsoLanguage.objects.filter(iso_code__in=request.POST.getlist('target-languages'))
            aws_languages = []
            deepl_languages = []

            for lang in target_languages:
                assigned_language = AssignedLanguage.objects.get(course=course, iso_language=lang)

                if assigned_language.translation_service == TranslationService.AWS:
                    aws_languages.append(lang)
                elif assigned_language.translation_service == TranslationService.DEEPL:
                    deepl_languages.append(lang)
                else:
                    return HttpResponse(f"Translation provider {assigned_language.translation_service} not supported right now")


            if aws_languages and deepl_languages:
                return HttpResponse("Mixing Translation providers is currently not supported.")

            if aws_languages:
                translation_service.translate(subtitle, target_languages=aws_languages, initiator=request.user)
                video.refresh_from_db(fields=["workflow_data"])

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
                translation_service_deepl.translate(subtitle, target_languages=deepl_languages, initiator=request.user)


            languages_str = ", ".join(str(l) for l in target_languages)

            messages.success(request, f"Translation into {languages_str} queued.")

        elif action == 'set_automatic':
            if request.POST.get('is_automatic') == 'true':
                subtitle.is_automatic = True
            else:
                subtitle.is_automatic = False

            subtitle.save()
            messages.success(request, "Updated automatic translation status")

        if subtitle and subtitle.status != previous_status:
            subtitle_status_change_service.status_changed(subtitle, previous_status)

        redirect_url = reverse(
            'mooclink.video.index',
            kwargs={'tenant_slug': tenant_slug, 'course_id': course_id, 'video_id': video_id}
        )

        return redirect(redirect_url + (f"?language={subtitle.language.iso_code}" if not subtitle.is_transcript else ""))


class VideoWorkflowAction(PermissionRequiredMixin, views.View):
    def post(self, request, tenant_slug, course_id, video_id):
        action = request.POST['action']

        tenant = Tenant.objects.get(slug=tenant_slug)
        course = Course.objects.get(tenant=tenant, ext_id=course_id)
        video = Video.objects.get(tenant=tenant, ext_id=video_id)

        assert tenant in request.user.tenants

        if action == "clear_workflow":
            video.workflow_status = ""

            messages.success(request, "Workflow canceled")

            return redirect("mooclink.video.index", tenant_slug=tenant_slug, course_id=course.ext_id, video_id=video.ext_id)
