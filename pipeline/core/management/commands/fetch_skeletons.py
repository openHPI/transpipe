from pprint import pprint

from django.core.management.base import BaseCommand, CommandError

from core.models import Tenant
from subtitles.api.xikolo_api import get_course_list
from subtitles.models import Course, IsoLanguage
from subtitles.models.course import SyncStatusChoices


class Command(BaseCommand):
    help = 'Fetches something'

    def add_arguments(self, parser):
        parser.add_argument('tenant_slugs', nargs='+', type=str)

    def handle(self, *args, **options):
        for tenant_slug in options['tenant_slugs']:
            try:
                tenant = Tenant.objects.get(slug=tenant_slug)
            except Tenant.DoesNotExist:
                raise CommandError(f'Tenant with slug {tenant_slug} does not exist.')


            l = get_course_list(tenant)

            for course_entry in l:
                iso_language_code = course_entry["language"][0:5]
                print("Language code: " + iso_language_code)
                try:
                    language = IsoLanguage.objects.get(iso_code=iso_language_code)
                except IsoLanguage.DoesNotExist:
                    language = IsoLanguage.objects.get(iso_code='en')

                try:
                    course = Course.objects.get(tenant=tenant, ext_id=course_entry['id'])
                except Course.DoesNotExist:
                    course = Course(
                        tenant=tenant,
                        ext_id=course_entry['id'],
                        sync_status=SyncStatusChoices.SKELETON,
                    )

                course.title = course_entry["title"]
                course.abstract = course_entry["abstract"]
                course.start_date = course_entry["start-date"]
                course.end_date = course_entry["end-date"]
                course.status = course_entry["status"]
                course.language = language

                course.save()