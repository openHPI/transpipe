from pprint import pprint

from celery.result import AsyncResult
from django import views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Permission
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from core.tasks import task_mul
from subtitles.api.mllp_api import mllp_delete_media
from subtitles.models import Video, Course


class ProfileView(LoginRequiredMixin, views.View):

    def get(self, request):
        user_permissions = Permission.objects.filter(user=request.user)
        group_permissions = Permission.objects.filter(group__user=request.user)

        if request.user.is_superuser:
            res: AsyncResult = task_mul.delay(10, 20, 12)

            print("a", res)
            print("a", res.backend)
            print("a", res.result)
            pprint(res._get_task_meta())

        return render(request, "core/profile/index.html", {
            'user_permissions': user_permissions,
            'group_permissions': group_permissions,
            'groups': request.user.groups.all(),
        })


@method_decorator(never_cache, name='dispatch')
class HealthCheckView(views.View):
    def get(self, request):
        # Check database connection
        num_videos = Video.objects.count()
        # use len to iterate over all courses
        num_courses = len(Course.objects.all())

        total = num_videos + num_courses

        return HttpResponse("OK", status=200)
