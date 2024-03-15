from django.urls import path

from mooclink.views.course import CourseOverView, CourseSettingsView, CourseAddLanguageView, RemoveUserAssignment
from mooclink.views.couse_video_bulkaction import CourseBulkActionConfirmation, CourseDoBulkAction, CourseSubscribe
from mooclink.views.main import MainView, MainViewCourse, RedirectByItemId, JobAdminView, JobAdminResetView
from mooclink.views.service_provider_usage import ServiceProviderUsage, TodoView, ServiceProviderUsageCSV, \
    ServiceProviderUsageQuarter
from mooclink.views.subtitle_action import SubtitleToAction
from mooclink.views.video import SaveTranscriptVersion, CancelWorkflowView
from mooclink.views.video import SetWorkflowStatusView
from mooclink.views.video import VideoDetailView, AddCommentToVideoView, FetchFromXikolo

urlpatterns = [
    path('<tenant_slug>/courses/<course_id>/videos/<video_id>/', MainView.as_view(), name='mooclink.main'),
    path('<tenant_slug>/courses/<course_id>/', MainViewCourse.as_view(), name='mooclink.wo_video_id'),
    path('<tenant_slug>/courses/<course_id>/overview/', CourseOverView.as_view(), name='mooclink.course.overview'),
    path('<tenant_slug>/courses/<course_id>/bulk/confirm/', CourseBulkActionConfirmation.as_view(), name='mooclink.course.bulk.confirmation'),
    path('<tenant_slug>/courses/<course_id>/subscribe/', CourseSubscribe.as_view(), name='mooclink.course.subscribe'),
    path('<tenant_slug>/courses/<course_id>/bulk/do/', CourseDoBulkAction.as_view(), name='mooclink.course.bulk.do'),
    path('<tenant_slug>/courses/<course_id>/settings/', CourseSettingsView.as_view(), name='mooclink.course.settings'),
    path('<tenant_slug>/courses/<course_id>/add_language/', CourseAddLanguageView.as_view(), name='mooclink.course.add_language'),
    path('<tenant_slug>/courses/<course_id>/user_assignments/remove/', RemoveUserAssignment.as_view(), name='mooclink.course.remove_assignment'),

    path('<tenant_slug>/courses/<course_id>/videos/<video_id>/details/', VideoDetailView.as_view(), name='mooclink.video.index'),
    path('<tenant_slug>/courses/<course_id>/videos/<video_id>/comments/', AddCommentToVideoView.as_view(), name='mooclink.video.add_comment'),
    path('<tenant_slug>/courses/<course_id>/videos/<video_id>/status/', SetWorkflowStatusView.as_view(), name='mooclink.video.set_status'),
    path('<tenant_slug>/courses/<course_id>/videos/<video_id>/save_transcript/', SaveTranscriptVersion.as_view(), name='mooclink.video.save_transcript'),
    path('<tenant_slug>/courses/<course_id>/videos/<video_id>/fetch_subtitle_from_xikolo/', FetchFromXikolo.as_view(), name='mooclink.video.fetch_subtitle_from_xikolo'),
    path('<tenant_slug>/courses/<course_id>/videos/<video_id>/do_action/', SubtitleToAction.as_view(), name='mooclink.video.do_action'),
    path('<tenant_slug>/videos/<video_id>/workflow/cancel/', CancelWorkflowView.as_view(), name='mooclink.video.workflow.cancel'),

    path('billing/', ServiceProviderUsageQuarter.as_view(), name='mooclink.service_provider_use.index'),
    path('billing/<tenant_slug>/details/', ServiceProviderUsage.as_view(), name='mooclink.service_provider_use.details'),
    path('billing/getcsv/', ServiceProviderUsageCSV.as_view(), name='mooclink.service_provider_use.getcsv'),

    path('tasks/', TodoView.as_view(), name='mooclink.todo.index'),

    # Endpoint for redirecting to course / video by primary-key. Allowed only for admins
    path('debug/get_item/', RedirectByItemId.as_view()),

    path('jobs/', JobAdminView.as_view(), name="mooclink.jobs.index"),
    path('jobs/reset/', JobAdminResetView.as_view(), name="mooclink.jobs.reset"),
]
