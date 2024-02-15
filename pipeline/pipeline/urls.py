"""pipeline URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import sys

from django.contrib import admin
from django.contrib.auth import views
from django.urls import include, path
from django.views.debug import technical_500_response
from django.views.defaults import server_error
from django.views.generic import RedirectView

urlpatterns = [
    path("subtitles/", include("subtitles.urls")),
    path("admin/", admin.site.urls),
    path('accounts/login/', views.LoginView.as_view(redirect_authenticated_user=True), name='login'),
    path('accounts/logout/', views.LogoutView.as_view(next_page='/'), name='logout'),
    path("accounts/", include("django.contrib.auth.urls")),
    path('core/', include("core.urls")),
    path('link/', include("mooclink.urls")),
    path('', RedirectView.as_view(url='subtitles/list/')),
]


# Display (hopefully) helpful stacktrace
def handler500(request):
    if request.user.is_superuser:
        return technical_500_response(request, *sys.exc_info())
    else:
        return server_error(request)

# path("", RedirectView.as_view(url="subtitles/")),
# + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
