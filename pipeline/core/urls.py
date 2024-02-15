from django.urls import path

from core.views import ProfileView, HealthCheckView

urlpatterns = [
    path('profile/', ProfileView.as_view(), name='core.profile'),
    path('healthcheck/', HealthCheckView.as_view()),
]
