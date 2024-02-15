import itertools
from pprint import pprint

from django import views
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.core.exceptions import SuspiciousOperation
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from core.models import Tenant, TranspipeUser
from mooclink.services import get_supported_languages
from subtitles.api.xikolo_api import get_xikolo_course, get_xikolo_course_sections_and_videos
from subtitles.models import Course, IsoLanguage, Subtitle, SubtitleAssignment, Video
from subtitles.models.assigned_language import AssignedLanguage
from subtitles.models.translation_service import TranslationService


class CourseOverView(PermissionRequiredMixin, LoginRequiredMixin, views.View):
    permission_required = ()

    def get(self, request, course_id, tenant_slug=None):
        tenant = Tenant.objects.get(slug=tenant_slug)
        course = Course.objects.get(tenant=tenant, ext_id=course_id)

        selectable_users = TranspipeUser.objects \
            .filter(is_active=True) \
            .filter(tenants=tenant)

        course_languages = list(course.translated_languages)
        videos = Video.objects.filter(course_section__course=course, deprecated=False).order_by('course_section__index', 'index').select_related('course_section')
        subtitles = Subtitle.objects.filter(video__course_section__course=course)\
            .prefetch_related('subtitleassignment_set', 'subtitleassignment_set__user')\
            .order_by('id')

        if not self.request.user.has_perm('core.can_see_all_courses'):
            videos = videos.filter(
                subtitle__subtitleassignment__user=request.user
            )

        subtitle_map = {}

        for subtitle in subtitles:
            subtitle_map[(subtitle.video_id, subtitle.language_id)] = subtitle

        d = []
        order = {
            Subtitle.SubtitleStatus.EDITED: -1,
            Subtitle.SubtitleStatus.PUBLISHED: 0,
            Subtitle.SubtitleStatus.APPROVED: 1,
            Subtitle.SubtitleStatus.IN_PROGRESS: 2,
            Subtitle.SubtitleStatus.AUTO_GENERATED: 3,
            Subtitle.SubtitleStatus.CHANGES_REQUESTED: 4,
            Subtitle.SubtitleStatus.WAITING_FOR_REVIEW: 5,
            Subtitle.SubtitleStatus.INITIAL: 6,
            None: 6,
        }

        def get_css_section(lang, vids):
            value = 0
            for v in vids:
                yo = v['subtitles'][lang]
                if yo:
                    _, yo = yo #.status
                else:
                    yo = order[None]

                # value = max(value, order[yo])
                value = max(value, yo)

            return value

        def get_css_course(lang, section_videos):
            return max(v['combined_result'][lang] for v in section_videos)

        def get_color(obj):
            if isinstance(obj, Subtitle):
                try:
                    return obj, order[obj.status]
                except KeyError:
                    # TODO Check if correct
                    return obj, order[None]

            return None, order[None]

        for course_section, section_videos in itertools.groupby(videos, key=lambda v: v.course_section):
            section_videos = list(section_videos)
            course_section_videos = []

            for section_video in section_videos:
                course_section_videos.append({
                    'video': section_video,
                    'section': course_section,
                    'subtitles': {l: get_color(subtitle_map.get((section_video.pk, l.iso_code))) for l in course_languages},
                    'transcript': get_color(subtitle_map.get((section_video.pk, section_video.original_language_id)))
                })

            d.append({
                'course_section': course_section,
                'videos': course_section_videos,
                'combined_result': {
                    l: get_css_section(l, course_section_videos)
                    for l in course_languages
                },
                'combined_result_transcript': max([v['transcript'][1] for v in course_section_videos]),
            })

        return render(request, "mooclink/course/overview.html", {
            'course': course,
            'languages': course.translated_languages.all(),
            'transcript_language': course.language,
            'tenant': tenant,
            'selectable_users': selectable_users,
            'table_data': d,
            'table_header_transcription': max(v['combined_result_transcript'] for v in d) if d else 6,
            'table_header': {
                l: get_css_course(l, d) for l in course_languages
            },
            'disable_workflow': course.only_manual_provider,
        })

    def post(self, request, course_id, tenant_slug=None):
        tenant = Tenant.objects.get(slug=tenant_slug)

        fetched_course = get_xikolo_course(request, course_id, tenant=tenant)
        get_xikolo_course_sections_and_videos(fetched_course, request)

        return redirect('mooclink.course.overview', tenant_slug, course_id)


class CourseSettingsView(PermissionRequiredMixin, LoginRequiredMixin, views.View):
    permission_required = ('subtitles.change_settings',)

    def get(self, request, course_id, tenant_slug=None):
        tenant = Tenant.objects.get(slug=tenant_slug)
        course = Course.objects.get(tenant=tenant, ext_id=course_id)

        return render(request, "mooclink/course/settings.html", {
            'course': course,
            'supported_translation_services': tenant.active_cloud_services,
            'tenant': tenant,
            'available_languages': IsoLanguage.objects.all(),
        })

    def post(self, request, course_id, tenant_slug=None):
        tenant = Tenant.objects.get(slug=tenant_slug)
        course = Course.objects.get(tenant=tenant, ext_id=course_id)

        if request.POST.get('action') == 'delete_assigned_language':
            delete_asid = request.POST['delete_asid']
            assigned_language = AssignedLanguage.objects.get(course__tenant=tenant, pk=delete_asid)
            assigned_language.delete()

            messages.success(request, "Language removed")

            return redirect('mooclink.course.settings', tenant_slug=tenant_slug, course_id=course_id)

        if request.POST['transcription-service'] not in tenant.active_cloud_services:
            messages.error(request, f"Selected Service Provider `{request.POST['transcription-service']}` "
                                    f"is not supported in this tenant")
        else:
            course.transcription_service = request.POST['transcription-service']

        course.language = IsoLanguage.objects.get(iso_code=request.POST['course-language'])

        course.save()

        for assigned_id in request.POST.getlist('assigned_id'):
            assigned_language = AssignedLanguage.objects.get(course__tenant=tenant, pk=assigned_id)
            mandatory = True if request.POST.get(f'mandatory-{assigned_id}') else False

            service_provider = request.POST.get(f'service-provider-{assigned_id}')
            assert service_provider in TranslationService.values, f"Unknown service provider `{service_provider}`"
            assigned_language.translation_service = service_provider

            assigned_language.required = mandatory
            assigned_language.save()

        messages.success(request, "Settings saved.")

        return redirect('mooclink.course.settings', tenant_slug=tenant_slug, course_id=course_id)


class CourseAddLanguageView(PermissionRequiredMixin, LoginRequiredMixin, views.View):
    permission_required = ('subtitles.change_settings',)

    def get(self, request, course_id, tenant_slug=None):
        tenant = Tenant.objects.get(slug=tenant_slug)
        course = Course.objects.get(tenant=tenant, ext_id=course_id)

        selectable_languages = get_supported_languages(service=course.transcription_service)

        return render(request, "mooclink/course/add_language.html", {
            'course': course,
            'languages': ["German", "Spanish"],
            'all_languages': selectable_languages,
            'supported_translation_services': TranslationService,
            'transcription_service': course.transcription_service,
            'tenant': tenant,
        })

    def post(self, request, course_id, tenant_slug=None):
        tenant = Tenant.objects.get(slug=tenant_slug)
        course = Course.objects.get(tenant=tenant, ext_id=course_id)

        language = IsoLanguage.objects.get(iso_code=request.POST['language'])
        # service_provider = request.POST['service-provider']
        mandatory = (request.POST.get('mandatory', 'no') == 'yes')
        service_provider = course.transcription_service

        course.add_translated_language(language, service_provider=service_provider, required=mandatory)
        course.save()

        messages.success(request, f"Language {language} successfully added.")

        return redirect('mooclink.course.settings', tenant_slug=tenant_slug, course_id=course.ext_id)


class RemoveUserAssignment(PermissionRequiredMixin, LoginRequiredMixin, views.View):
    permission_required = ('subtitles.assign_user',)

    def post(self, request: HttpRequest, tenant_slug, course_id):
        subtitle_id = request.POST['subtitle_id']
        user_id = request.POST['user_id']

        subtitle = Subtitle.objects.get(pk=subtitle_id)
        user = TranspipeUser.objects.get(pk=user_id)

        if not request.user.is_superuser and subtitle.tenant not in request.user.tenants.all():
            raise SuspiciousOperation

        SubtitleAssignment.objects.filter(subtitle=subtitle).update(deleted=timezone.now())

        return HttpResponse("OK")
