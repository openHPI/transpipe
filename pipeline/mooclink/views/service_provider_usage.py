import codecs
import csv
import datetime
import itertools
import math
from collections import namedtuple

from django import views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import SuspiciousOperation
from django.db.models.functions import ExtractQuarter, ExtractYear
from django.http import HttpResponse, HttpRequest
from django.shortcuts import render

from core.models import Tenant
from subtitles.models import ServiceProviderUse, SubtitleAssignment, Subtitle


class ServiceProviderUsageQuarter(LoginRequiredMixin, views.View):
    def get(self, request: HttpRequest):
        if not request.user.has_perm('core.can_see_service_provider_usage'):
            raise SuspiciousOperation

        service_provider_use = ServiceProviderUse.objects

        if tenant_str := request.GET.get('tenant'):
            service_provider_use = service_provider_use.filter(tenant__slug=tenant_str)

        if quarter_str := request.GET.get("quarter"):
            quarter = int(quarter_str[-1])
            year = int(quarter_str[:4])

            service_provider_use = service_provider_use.filter(initiated__year=year, initiated__quarter=quarter)

        service_provider_use = service_provider_use.filter().order_by('initiated').all()

        data = {}
        for ((year, quarter), items) in itertools.groupby(service_provider_use, key=lambda su: (
                su.initiated.year, math.ceil(su.initiated.month / 3.0))):
            data[f"{year}Q{quarter}"] = {
                "list": []
            }

            for (tenant, items) in itertools.groupby(sorted(items, key=lambda su: su.tenant_id),
                                                     key=lambda su: su.tenant):
                l = list(sorted(items, key=lambda i: i.service_provider))

                billing_data = {
                    ServiceProviderUse.ServiceProvider.AWS_TRANSCRIPTION: sum(i.billed_minutes for i in l if
                                                                              i.service_provider == ServiceProviderUse.ServiceProvider.AWS_TRANSCRIPTION),
                    ServiceProviderUse.ServiceProvider.MLLP: sum(
                        i.billed_minutes for i in l if i.service_provider == ServiceProviderUse.ServiceProvider.MLLP),
                    ServiceProviderUse.ServiceProvider.AWS_TRANSLATION: sum(i.billed_characters for i in l if
                                                                            i.service_provider == ServiceProviderUse.ServiceProvider.AWS_TRANSLATION),
                    ServiceProviderUse.ServiceProvider.DEEPL: sum(i.billed_characters for i in l if
                                                                            i.service_provider == ServiceProviderUse.ServiceProvider.DEEPL),
                }

                data[f"{year}Q{quarter}"]["list"].append(
                    (tenant, billing_data)
                )

        selectable_quarter = ServiceProviderUse.objects \
            .annotate(quarter=ExtractQuarter("initiated")) \
            .annotate(year=ExtractYear("initiated")) \
            .values("year", "quarter") \
            .order_by("year", "quarter") \
            .distinct() \
            .all()

        return render(request, "mooclink/service_provider_usage/index.html", {
            "data": data,
            "service_provider": [
                ServiceProviderUse.ServiceProvider.AWS_TRANSCRIPTION,
                ServiceProviderUse.ServiceProvider.AWS_TRANSLATION,
                ServiceProviderUse.ServiceProvider.MLLP,
                ServiceProviderUse.ServiceProvider.DEEPL,
            ],
            "service_provider_units": {
                ServiceProviderUse.ServiceProvider.AWS_TRANSCRIPTION: "minutes",
                ServiceProviderUse.ServiceProvider.AWS_TRANSLATION: "characters",
                ServiceProviderUse.ServiceProvider.MLLP: "minutes",
                ServiceProviderUse.ServiceProvider.DEEPL: "characters",
            },
            'tenants': request.user.tenants.all(),
            "selectable_quarter": [f"{q['year']}Q{q['quarter']}" for q in selectable_quarter],
            'quarter_str': quarter_str,
        })


class ServiceProviderUsage(LoginRequiredMixin, views.View):
    def get(self, request, tenant_slug):
        if not request.user.has_perm("core.can_see_service_provider_usage"):
            raise SuspiciousOperation

        service_provider_use = ServiceProviderUse.objects.filter(tenant__slug=tenant_slug)

        if tenant_str := request.GET.get('tenant'):
            service_provider_use = service_provider_use.filter(tenant__slug=tenant_str)

        service_provider_use = service_provider_use.filter().order_by('initiated').all()

        data = {}
        for (month, items) in itertools.groupby(service_provider_use, key=lambda su: su.initiated.strftime("%B %Y")):
            l = list(sorted(items, key=lambda i: i.service_provider))
            data[month] = {
                'spu_items': l,
                'char_sum': sum(i.data.get('characters', 0) for i in l),
                'duration_sum': round(sum(i.data.get('video_duration', 0.0) for i in l) / 1000.0 / 60.0, 2),
                'billing_data': {
                    ServiceProviderUse.ServiceProvider.AWS_TRANSCRIPTION: sum(i.billed_minutes for i in l if
                                                                              i.service_provider == ServiceProviderUse.ServiceProvider.AWS_TRANSCRIPTION),
                    ServiceProviderUse.ServiceProvider.MLLP: sum(
                        i.billed_minutes for i in l if i.service_provider == ServiceProviderUse.ServiceProvider.MLLP),
                    ServiceProviderUse.ServiceProvider.AWS_TRANSLATION: sum(i.billed_characters for i in l if
                                                                            i.service_provider == ServiceProviderUse.ServiceProvider.AWS_TRANSLATION),
                },
            }

        return render(request, "mooclink/service_provider_usage/tenant_detail.html", {
            'service_provider_use': service_provider_use,
            'data': data,
            'tenants': Tenant.objects.all(),
        })


class ServiceProviderUsageCSV(LoginRequiredMixin, views.View):
    def get(self, request):
        if not request.user.has_perm("core.can_see_service_provider_usage"):
            raise SuspiciousOperation

        service_provider_use = ServiceProviderUse.objects

        if tenant_str := request.GET.get('tenant'):
            service_provider_use = service_provider_use.filter(tenant__slug=tenant_str)

        if quarter_str := request.GET.get("quarter"):
            quarter = int(quarter_str[-1])
            year = int(quarter_str[:4])

            service_provider_use = service_provider_use.filter(initiated__year=year, initiated__quarter=quarter)

        service_provider_use = service_provider_use.order_by('initiated').all()

        dt_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="service_provider_usage_{dt_str}.csv"'

        fieldnames = [
            'initiation_date',
            'tenant',
            'initiated_by',
            'course',
            'video',
            'item',
            'provider',
            'amount',
            'unit',
        ]

        response.write(codecs.BOM_UTF8)

        writer = csv.DictWriter(response, fieldnames=fieldnames, delimiter=",")
        writer.writeheader()

        for spu in service_provider_use:
            source_language = spu.data.get('source_language', 'UNKNOWN')
            if target_language := spu.data.get("target_language"):
                item = f"translation {source_language} to {target_language}"
            else:
                item = f"transcript to {source_language}"

            writer.writerow({
                "initiation_date": spu.initiated.strftime("%Y-%m-%d %H:%M:%S"),
                "tenant": spu.tenant.name,
                "initiated_by": spu.initiated_by,
                "course": spu.video.course_section.course,
                "video": spu.video,
                "item": item,
                "provider": spu.service_provider,
                "amount": spu.amount,
                "unit": spu.metric,
            })

        return response


TodoAssignmentRow = namedtuple("TodoAssignmentRow", [
    'assignment',
    'subtitle',
    'video',
    'course',
    'action'
])


class TodoView(LoginRequiredMixin, views.View):
    def get(self, request):
        assignments = SubtitleAssignment.objects.filter(user=request.user) \
            .filter(deleted__isnull=True, notification_sent__isnull=False) \
            .order_by('subtitle__video__course_section', 'subtitle__video__index')

        if tenant_filter := request.GET.get("tenant"):
            assignments = assignments.filter(subtitle__tenant__slug=tenant_filter)

        if status_filter := request.GET.get("s"):
            pass
        else:
            assignments = assignments \
                .exclude(subtitle__status=Subtitle.SubtitleStatus.PUBLISHED) \
                .exclude(subtitle__status=Subtitle.SubtitleStatus.APPROVED)

        # store possible selectable courses before filtering further
        selectable_courses = set(a.subtitle.video.course_section.course for a in assignments.all())

        if course_filter := request.GET.get("course"):
            assignments = assignments.filter(subtitle__video__course_section__course__pk=course_filter)

        assignments = assignments.all()
        selectable_tenants = request.user.tenants.all()

        prepared_list = []

        for assignment in assignments:
            subtitle = assignment.subtitle
            video = subtitle.video
            course = video.course_section.course

            action = ""

            if subtitle.status == Subtitle.SubtitleStatus.CHANGES_REQUESTED:
                action += "Changes requested for "
            elif subtitle.status == Subtitle.SubtitleStatus.WAITING_FOR_REVIEW:
                action += "Review of "

            if subtitle.is_transcript:
                action += f"Transcript ({subtitle.language})"
            else:
                action += f"Translation ({subtitle.language})"

            prepared_list.append(TodoAssignmentRow(
                assignment,
                subtitle,
                video,
                course,
                action,
            ))

        # prepared_list = sorted(prepared_list, key=lambda tar: (tar.course.title, tar.video.index))

        return render(request, "mooclink/todo/index.html", {
            'assignments': prepared_list,
            'selectable_tenants': selectable_tenants,
            'selectable_courses': selectable_courses,
            'selectable_status': [
                ('', "Open Tasks"),
                ('all', "All Tasks"),
            ]
        })
