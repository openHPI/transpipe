from django.contrib import admin

# from .models import Course, Subtitle, Video, IsoLanguage, CourseSection, CourseItem
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe
from embed_video.admin import AdminVideoMixin

from .models import (
    Course,
    CourseSection,
    Video,
    Subtitle,
    IsoLanguage,
    SubtitleAssignment, ServiceProviderUse,
)
from .models.awsupload import AWSupload
from .models.subtitle_file import SubtitleFile


class VideoInline(admin.StackedInline):
    model = Video
    extra = 1


class CourseSectionInline(admin.StackedInline):
    model = CourseSection
    extra = 1


class CourseTranspipeUserSetInline(admin.TabularInline):
    model = Course.transpipeuser_set.through
    extra = 1


class CourseAdmin(admin.ModelAdmin):
    fields = (
        "title",
        "abstract",
        "start_date",
        "end_date",
        "status",
        "language",
        "ext_id",
        "tenant",
        "sync_status",
    )
    inlines = [CourseTranspipeUserSetInline, CourseSectionInline]

    list_display = ['title', 'tenant']
    list_filter = ['tenant']


class VideoAdmin(AdminVideoMixin, admin.ModelAdmin):
    list_display = ['title', 'get_course', 'tenant']
    list_filter = ['tenant', 'course_section__course', 'deprecated']
    readonly_fields = ['link_to_video', 'link_to_course']

    def get_course(self, obj):
        return obj.course_section.course

    get_course.order_field = 'course'
    get_course.short_description = 'Course of video'

    def link_to_course(self, obj):
        url = reverse('mooclink.course.overview', args=[obj.tenant.slug, obj.course_section.course.ext_id])
        return mark_safe(f"<a href='{url}' target='_blank'>{escape(obj.course_section.course.title)} - Course Overview</a>")

    link_to_course.short_description = "Link to Course Overview"

    def link_to_video(self, obj):
        url = reverse('mooclink.video.index', args=[obj.tenant.slug, obj.course_section.course.ext_id, obj.ext_id])
        return mark_safe(f"<a href='{url}' target='_blank'>{escape(obj.title)} - Editor</a>")

    link_to_video.short_description = "Link to Video Editor"


class SubtitleAdmin(admin.ModelAdmin):
    list_display = ['pk', 'video', 'language', 'status', 'origin', 'is_transcript']
    list_filter = ['video__course_section__course', 'origin', 'language']


class ServiceProviderUseAdmin(admin.ModelAdmin):
    readonly_fields = ['subtitle', 'subtitle_file', 'video', 'initiated_by']

    save_as = True


admin.site.register(Course, CourseAdmin)
admin.site.register(Video, VideoAdmin)
admin.site.register(Subtitle, SubtitleAdmin)
admin.site.register(IsoLanguage)
admin.site.register(CourseSection)
admin.site.register(SubtitleFile)
admin.site.register(AWSupload)
admin.site.register(SubtitleAssignment)
admin.site.register(ServiceProviderUse, ServiceProviderUseAdmin)

# TypeError: 'MediaDefiningClass' object is not iterable
