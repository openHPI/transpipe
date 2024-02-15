"""
Views module in our pipeline project.

TBD.

"""
from django import views
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpRequest
from django.shortcuts import redirect
from django.utils.http import urlencode
from django.views import generic

from core.models import Tenant
from .api.xikolo_api import get_xikolo_course_sections_and_videos
from .models import Course
from .models.course import SyncStatusChoices


class ListCoursesWithFilter(PermissionRequiredMixin, generic.ListView):
    template_name = "subtitles/index.html"
    context_object_name = "course_list"
    paginate_by = 15

    permission_required = "subtitles.view_course"

    def get_queryset(self):

        query = self.request.GET.get("q")
        tenant_filter_s = self.request.GET.get('t')
        tenant_filter = None

        if tenant_filter_s:
            tenant_filter = Tenant.objects.get(slug=tenant_filter_s)

        course_list = Course.objects.order_by("title")

        if not self.request.user.is_superuser:
            course_list = course_list.filter(
                Q(tenant__in=self.request.user.tenants.all()) | Q(tenant__all_courses_visible=True)
            )

        if not self.request.user.has_perm('core.can_see_all_courses'):
            course_list = course_list.filter(
                coursesection__video__subtitle__subtitleassignment__user=self.request.user
            )

        if not self.request.user.has_perm('subtitles.see_skeletons'):
            course_list = course_list.exclude(sync_status=SyncStatusChoices.SKELETON)

        if query:
            # TODO include instructor
            course_list = Course.objects.filter(
                Q(title__icontains=query)
                | Q(language__description__icontains=query)
                | Q(teacher__icontains=query)
            )
            self.paginate_by = 0

        if tenant_filter:
            course_list = course_list.filter(tenant=tenant_filter)

        return course_list.distinct()

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        selectable_tenants = Tenant.objects.order_by('name')
        if not self.request.user.is_superuser:
            selectable_tenants = selectable_tenants.filter(tenants_list=self.request.user)

        query_dict = {}

        if tenant := self.request.GET.get("t"):
            query_dict["t"] = tenant

        context['selectable_tenants'] = selectable_tenants
        context['query_string'] = urlencode(query_dict)

        return context


class FetchCourseView(PermissionRequiredMixin, views.View):
    permission_required = ('subtitles.add_course', 'subtitles.see_skeletons',)

    def post(self, request: HttpRequest):
        course_id = request.POST['add_course']

        course = Course.objects.get(pk=course_id)

        if not request.user.is_superuser and course.tenant not in request.user.tenants.all():
            raise PermissionDenied(f"You do not have the required permission to add a course to {course.tenant}")

        added_course = get_xikolo_course_sections_and_videos(course, request, disable_deep_fetch=False)

        if added_course:
            messages.success(request, f"Added course {course.title}")

            return redirect('mooclink.course.overview', course.tenant.slug, course.ext_id)
        else:
            messages.error(request, f"An error occurred")

            return redirect('subtitles:index')
