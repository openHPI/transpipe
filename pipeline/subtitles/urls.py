"""
urls module in our pipeline project.

TBD.


"""

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

app_name = "subtitles"
urlpatterns = [
    # /subtitles/
    path("", login_required(views.ListCoursesWithFilter.as_view()), name="index"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(template_name="registration/logged_out.html"),
        name="logout",
    ),
    # path("userdetails/", views.user_details, name="user_details"),
    path("list/", views.ListCoursesWithFilter.as_view(), name="listcourses"),
    path('fetch_course/', views.FetchCourseView.as_view(), name='fetch_course'),
]
