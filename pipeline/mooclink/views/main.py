from django import views
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.core.exceptions import SuspiciousOperation
from django.http import HttpRequest
from django.shortcuts import render, redirect

from core.models import Tenant
from subtitles.api.xikolo_api import get_xikolo_course_sections_and_videos, update_video_detail, get_xikolo_course
from subtitles.models import Course, Video
from subtitles.models.course import SyncStatusChoices


class MainView(PermissionRequiredMixin, LoginRequiredMixin, views.View):
    permission_required = ()

    @classmethod
    def resync_course(cls, request, course):
        videos = get_xikolo_course_sections_and_videos(
            course=course,
            request=request,
            disable_deep_fetch=False
        )

        return videos

    def get(self, request, tenant_slug, course_id, video_id):
        tenant = Tenant.objects.get(slug=tenant_slug)

        video = None

        course = Course.objects.filter(tenant=tenant, ext_id=course_id).exclude(sync_status=SyncStatusChoices.SKELETON)\
            .first()

        if not course:
            messages.error(request, f"Course not found.")

        if course:
            try:
                video = Video.objects.get(course_section__course=course, tenant=tenant, ext_id=video_id)
            except Video.DoesNotExist:
                self.resync_course(request, course)

                video = Video.objects.filter(course_section__course=course, tenant=tenant, ext_id=video_id).first()

                if video:
                    update_video_detail(video.pk, video_id)

            if not video:
                messages.error(request,
                               f"Video list for course `{course}` refetched, but video with id={video_id} not found.")

        if course and video:
            return redirect('mooclink.video.index', course.tenant.slug, course.ext_id, video.ext_id)

        return render(request, "mooclink/main.html", {
            'tenant': tenant,
            'course': course,
            'video': video,
            'course_id': course_id,
            'video_id': video_id,
        })

    def post(self, request, tenant_slug, course_id, video_id):
        if not request.user.has_perm('subtitles.add_course'):
            messages.error(request, "Missing permission to add a new course")

            return redirect('mooclink.main', tenant_slug, course_id, video_id)

        tenant = Tenant.objects.get(slug=tenant_slug)

        course = get_xikolo_course(request, course_id, tenant=tenant)

        if course:
            messages.success(request, "Added to transpipe")
        else:
            messages.error(request, "Course cannot be found on remote server")

        return redirect('mooclink.main', tenant_slug, course_id, video_id)


class MainViewCourse(PermissionRequiredMixin, LoginRequiredMixin, views.View):
    permission_required = ()

    def get(self, request, tenant_slug, course_id):
        tenant = Tenant.objects.get(slug=tenant_slug)
        course = None

        course = Course.objects.filter(tenant=tenant, ext_id=course_id).exclude(sync_status=SyncStatusChoices.SKELETON)\
            .first()


        if course:
            return redirect('mooclink.course.overview', tenant_slug, course.ext_id)
        else:
            messages.error(request, f"Course not found.")

        return render(request, "mooclink/main.html", {
            'tenant': tenant,
            'course': course,
            'video': None,
            'course_id': course_id,
            'video_id': None,
        })

    def post(self, request: HttpRequest, tenant_slug, course_id):
        tenant = Tenant.objects.get(slug=tenant_slug)

        if not request.user.has_perm('subtitles.add_course'):
            messages.error(request, "Missing permission to add a new course")

            return redirect('mooclink.wo_video_id', tenant_slug, course_id)

        course = get_xikolo_course(request, course_id, tenant=tenant)

        if course:
            messages.success(request, "Course added to transpipe. Fetching Videos.")
            videos = MainView.resync_course(request, course)

            messages.info(request, f"Found {len(videos)} Videos. Subtitles will be fetched in the next minutes.")

            return redirect('mooclink.course.overview', tenant_slug, course.ext_id)
        else:
            messages.error(request, "Course cannot be found on remote server")

        return redirect('mooclink.wo_video_id', tenant_slug, course_id)


class RedirectByItemId(PermissionRequiredMixin, LoginRequiredMixin, views.View):
    permission_required = ()

    def get(self, request: HttpRequest):
        if not request.user.is_superuser:
            raise SuspiciousOperation

        if 'video_id' in request.GET:
            video = Video.objects.get(pk=request.GET['video_id'])

            return redirect('mooclink.video.index', video.tenant.slug, video.ext_id)

        if 'course_id' in request.GET:
            course = Course.objects.get(pk=request.GET['course_id'])

            return redirect('mooclink.course.overview', course.tenant.slug, course.ext_id)
