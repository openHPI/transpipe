"""Xikolo transpipe API calls"""

import io
import os
from http import HTTPStatus
from typing import List

import celery
import requests
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from sentry_sdk import capture_message

from core.models import Tenant, TranspipeUser
from ..models import Subtitle, SubtitleFile, IsoLanguage, Course, CourseSection, Video
from ..models.course import SyncStatusChoices


def xikolo_download_subtitle_file(request, subtitle):
    tenant: Tenant = subtitle.tenant
    assert tenant

    try:
        # Does the video still exist on the MOOC platform?
        video = get_object_or_404(Video, subtitle=subtitle)

        response_video = requests.get(
            tenant.XIKOLO_API_URL + "videos/" + video.ext_id,
            headers={"Authorization": "Bearer " + tenant.XIKOLO_API_TOKEN},
            data={"key": "value"},
        )
        if response_video.status_code != 200:
            return False

        # Does the course_section still exist on the MOOC platform?
        course_section = get_object_or_404(CourseSection, video=video)
        response_course = requests.get(
            tenant.XIKOLO_API_URL + "courses/" + course_section.course.ext_id,
            headers={"Authorization": "Bearer " + tenant.XIKOLO_API_TOKEN},
            data={"key": "value"},
        )

        # if response_course.status_code == 200:
        #     any(course_section.ext_id == section["id"] for section in response_course.json()["sections"])
        #     # TODO: how to check if ext_id is in sections.
        #     # Is the course section still available
        #     is_in_list = False
        #     for section in response_course.json()["sections"]:
        #         if section["id"] == course_section.ext_id:
        #             is_in_list = True
        #             break
        #     return is_in_list
        # else:
        #     return False

        # Note: Cannot be reached
        # GET /videos/{id}/subtitles/{lang}
        response = requests.get(
            tenant.XIKOLO_API_URL
            + "videos/"
            + subtitle.video.ext_id
            + "/subtitles/"
            + subtitle.language.iso_code,
            headers={"Authorization": f"Bearer {tenant.XIKOLO_API_TOKEN}"},
            data={"key": "value"},
        )
        content = response.text
        if response.status_code == 200 and content != "":
            # Create new subtitle file
            new_subtitle_file = SubtitleFile(
                subtitle=subtitle,
                date=timezone.now(),
                user=request.user,
                tenant=tenant
            )

            # create directory for subtitles if not existing
            os.makedirs(os.path.join(settings.MEDIA_ROOT, "subtitles"), exist_ok=True)

            # Save the name of the new file
            new_subtitle_file.file.name = (
                    settings.MEDIA_ROOT
                    + "subtitles/"
                    + str(subtitle.id)
                    + "_"
                    + str(subtitle.language)
                    + "_"
                    + str(new_subtitle_file.date.strftime("%d%m%y-%H%M%S"))
                    + ".vtt"
            )
            # Write content to a file
            file = io.open(new_subtitle_file.file.path, "w", encoding="utf-8")
            file.write(content)
            file.close()
            # Save the new subtitle file and the subtitle after status change
            subtitle.status = Subtitle.SubtitleStatus.PUBLISHED

            # Check if subtitle from xikolo is automatic
            is_automatic = None
            for subtitle_dict in response_video.json()['subtitles']:
                if subtitle_dict['language'] == subtitle.language.iso_code:
                    is_automatic = subtitle_dict['automatic']
                    break

            if is_automatic is None:
                print("Fetched subtitle was not found in videos/{id} subtitle-list.")
                capture_message("Fetched subtitle was not found in videos/{id} subtitle-list.")
                is_automatic = True

            subtitle.is_automatic = is_automatic
            with transaction.atomic():
                subtitle.save()
                new_subtitle_file.save()

            return True
        else:
            return False

    except (requests.ConnectionError):
        return False


def get_subtitle_from_xikolo_for_video(video, language):
    tenant = video.tenant



    # GET /videos/{id}/subtitles/{lang}
    response = requests.get(
        tenant.XIKOLO_API_URL
        + "videos/"
        + subtitle.video.ext_id
        + "/subtitles/"
        + subtitle.language.iso_code,
        headers={"Authorization": f"Bearer {tenant.XIKOLO_API_TOKEN}"},
        data={"key": "value"},
    )
    content = response.text
    if response.status_code == 200 and content != "":
        # Create new subtitle file
        new_subtitle_file = SubtitleFile(
            subtitle=subtitle,
            date=timezone.now(),
            user=request.user,
            tenant=tenant
        )
        # Save the name of the new file
        new_subtitle_file.file.name = (
                settings.MEDIA_ROOT
                + "subtitles/"
                + str(subtitle.id)
                + "_"
                + str(subtitle.language)
                + "_"
                + str(new_subtitle_file.date.strftime("%d%m%y-%H%M%S"))
                + ".vtt"
        )
        # Write content to a file
        file = io.open(new_subtitle_file.file.path, "w", encoding="utf-8")
        file.write(content)
        file.close()
        # Save the new subtitle file and the subtitle after status change
        subtitle.status = Subtitle.SubtitleStatus.PUBLISHED
        with transaction.atomic():
            subtitle.save()
            new_subtitle_file.save()

def get_video_detail(video_id, request):
    video = Video.objects.get(pk=video_id)
    tenant: Tenant = video.tenant
    try:
        response = requests.get(
            tenant.XIKOLO_API_URL + "videos/" + video.ext_id,
            headers={"Authorization": "Bearer " + tenant.XIKOLO_API_TOKEN},
            data={"key": "value"},
        )
        if response.status_code == 200:
            return response.json()
        else:
            return []
    except (requests.ConnectionError) as exception:
        messages.error(
            request, str(exception) + ": " +
                     tenant.XIKOLO_API_URL + " not available."
        )


def get_course_list(tenant):

    try:
        # GET /courses/
        response = requests.get(
            tenant.XIKOLO_API_URL + "courses",
            headers={"Authorization": "Bearer " + tenant.XIKOLO_API_TOKEN},
            data={"key": "value"},
        )
        next_link = response.links["next"]["url"]
        course_list = []
        if response.status_code == 200:
            course_list = response.json()
            while next_link:
                response = requests.get(
                    next_link,
                    headers={"Authorization": "Bearer " +
                                              tenant.XIKOLO_API_TOKEN},
                    data={"key": "value"},
                )
                if response.status_code == 200:
                    course_list.extend(response.json())
                else:
                    return []
                # Wenn kein next link dann break
                if "next" not in response.links:
                    break
                next_link = response.links["next"]["url"]
        return course_list

    except (requests.ConnectionError, KeyError) as exception:
        raise


def get_xikolo_video_link(video_detail):
    if video_detail["urls"]["hd"]:
        video_url = video_detail["urls"]["hd"]
    elif video_detail["urls"]["sd"]:
        video_url = video_detail["urls"]["sd"]
    elif video_detail["urls"]["hls"]:
        video_url = video_detail["urls"]["hls"]
    else:
        video_url = ""

    return video_url


def select_best_video_stream(xikolo_video_detail: dict, stream='pip'):
    if stream not in {'pip', 'lecturer', 'slides'}:
        raise ValueError("Unknown stream-name provided.")

    if 'streams' not in xikolo_video_detail:
        return get_xikolo_video_link(xikolo_video_detail) if stream == 'pip' else None

    video_stream_dict = xikolo_video_detail['streams'][stream]

    video_url = ""
    for k in ['hd', 'sd', 'hls']:
        if val := video_stream_dict[k]:
            video_url = val
            break

    return video_url


def get_xikolo_course(request, course_id, tenant):
    assert tenant

    try:
        # GET /courses/id
        response = requests.get(
            tenant.XIKOLO_API_URL + "courses/" + course_id,
            headers={"Authorization": "Bearer " + tenant.XIKOLO_API_TOKEN},
            data={"key": "value"},
        )

        print("---->", response.text)

        if response.status_code == 200:
            response = response.json()

            try:
                language = IsoLanguage.objects.get(iso_code=response['language'])
            except IsoLanguage.DoesNotExist:
                language = IsoLanguage.objects.get(iso_code="en")

            fetched_course, created = Course.objects.update_or_create(
                tenant=tenant,
                ext_id=response['id'],
                defaults={'title': response['title'],
                          'abstract': response['abstract'],
                          'start_date': response['start-date'],
                          'end_date': response['end-date'],
                          'status': response['status'],
                          'language': language,
                          'tenant': tenant,
                          'sync_status': SyncStatusChoices.SUCCESS,
                          },
            )

            if created:
                # Set language only on newly created courses
                fetched_course.language = language
                fetched_course.save()

            return fetched_course

    except (requests.ConnectionError, KeyError) as exception:
        messages.error(
            request, str(exception) + ": " +
                     tenant.XIKOLO_API_URL + " not available."
        )

    return None


def get_xikolo_course_sections_and_videos(course: Course, request, disable_deep_fetch=False): #ToDo make async when productive
    tenant: Tenant = course.tenant
    assert tenant

    course.sync_status = SyncStatusChoices.IN_PROGRESS
    course.save()

    list_of_videos = []
    try:
        # GET /courses/{id}
        response = requests.get(
            tenant.XIKOLO_API_URL + "courses/" + course.ext_id,
            headers={"Authorization": "Bearer " +
                                      tenant.get_secret('XIKOLO_API_TOKEN')},
            data={"key": "value"},
        )

        if response.status_code == 200:
            j = response.json()

            # Save teacher in course, prefer alternative_teacher_text, but fall back to normal teacher list.
            course.teacher = j["alternative_teacher_text"] or ', '.join(t['name'] for t in j['teachers'])
            course.save()

            fetched_languages = False

            for section_idx, course_section_entry in enumerate(response.json()["sections"]):

                course_section, _ = CourseSection.objects.update_or_create(
                    tenant=tenant,
                    ext_id=course_section_entry["id"],
                    defaults={
                        'ext_id': course_section_entry["id"],
                        'title': course_section_entry["title"],
                        'course': course,
                        'tenant': tenant,
                        'index': section_idx,
                    },
                )

                # Videos in course sections:
                for video_idx, video_entry in enumerate(course_section_entry["videos"]):
                    video_detail = None

                    created_video = create_or_update_video_helper(video_entry, tenant, course.language, course_section, video_detail, video_idx)
                    list_of_videos.append(created_video)

                    if not fetched_languages:
                        languages_of_video = get_video_languages(tenant, video_entry["id"])

                        course.add_languages(l['language'] for l in languages_of_video)
                        fetched_languages = True

                    if created_video and not disable_deep_fetch:
                        if getattr(settings, 'XIKOLO_ASYNC_VIDEO_DETAIL_FETCH', True):
                            celery.current_app.send_task('core.tasks.task_update_video_detail',
                                                         args=(created_video.id, video_entry["id"]))
                        else:
                            update_video_detail(created_video.id, video_entry['id'])

            all_local_videos = Video.objects.filter(course_section__course=course, deprecated=False).order_by('course_section___index', 'index')

            for local_video in all_local_videos:
                if local_video not in list_of_videos:
                    print(f"Need to deprecate video {local_video}")
                    local_video.deprecated = True
                    local_video.save()

            course.sync_status = SyncStatusChoices.SUCCESS
            course.save()

        return list_of_videos

    except (requests.ConnectionError, KeyError) as exception:
        messages.error(
            request, str(exception) + ": " +
                     tenant.get_secret('XIKOLO_API_URL') + " not available."
        )


def create_or_update_video_helper(video_entry, tenant, language, section, detail, video_idx):
    defaults = {
        'ext_id': video_entry["id"],
        'title': video_entry["title"],
        'original_language': language,
        'pub_date': video_entry["start-date"],
        'course_section': section,
        'index': video_idx,
        'item_id': video_entry['item-id'],
        'deprecated': False,
    }

    if detail:
        defaults['video_url_pip'] = select_best_video_stream(detail, 'pip')
        defaults['video_url_lecturer'] =  select_best_video_stream(detail, 'lecturer')
        defaults['video_url_slides'] =  select_best_video_stream(detail, 'slides')
        defaults['summary'] = detail["summary"]

    video, _ = Video.objects.update_or_create(
        ext_id=video_entry["id"],
        tenant=tenant,
        defaults=defaults,
    )

    return video


def get_video_languages(tenant: Tenant, ext_video_id) -> List[str]:
    """
    @param tenant: Tenant
    @param ext_video_id: Video-UUID
    @return: List of language codes
    """

    response = requests.get(
        tenant.XIKOLO_API_URL + "videos/" + ext_video_id,
        headers={"Authorization": "Bearer " + tenant.XIKOLO_API_TOKEN},
        data={},
    )

    response.raise_for_status()

    j = response.json()

    subtitle_language_list = j["subtitles"]

    return subtitle_language_list


def update_video_detail(local_video_id, ext_video_id):
    print(f"update_video_detail {local_video_id=} {ext_video_id=}")
    video = Video.objects.get(pk=local_video_id)

    assert video.ext_id == ext_video_id
    tenant = video.tenant

    # todo add service-user
    dummy_user = tenant.transpipeuser_set.first() or TranspipeUser.objects.get(username='robert')

    response = requests.get(
        tenant.XIKOLO_API_URL + "videos/" + ext_video_id,
        headers={"Authorization": "Bearer " + tenant.XIKOLO_API_TOKEN},
        data={"key": "value"},
    )

    response.raise_for_status()

    j = response.json()

    video.summary = j['summary']
    video.video_url_pip = select_best_video_stream(j, 'pip')
    video.video_url_lecturer = select_best_video_stream(j, 'lecturer')
    video.video_url_slides = select_best_video_stream(j, 'slides')

    subtitle_language_list = j["subtitles"]

    for subtitle_dict in subtitle_language_list:
        # get iso language object:
        subtitle_lang = IsoLanguage.objects.get(iso_code=subtitle_dict['language'])
        is_automatic = subtitle_dict.get('automatic', True)

        # Check if subtitle is transcript or translation:
        if video.original_language == subtitle_lang:
            is_transcript = True
        else:
            is_transcript = False
            # TODO: Language may be new for course, and needs to be added to set of AssignedLanguages of course.

        # Case 1: new subtitle
        if not Subtitle.objects.filter(
                video=video, language=subtitle_lang, is_transcript=is_transcript
        ):
            # create new subtitle
            subtitle = Subtitle(
                language=subtitle_lang,
                video=video,
                is_transcript=is_transcript,
                status=Subtitle.SubtitleStatus.PUBLISHED,
                last_update=timezone.now(),
                origin=Subtitle.Origin.MOOC,
                user=dummy_user,
                tenant=tenant,
                is_automatic=is_automatic,
            )
            subtitle.save()
            # save webvtt content in subtitle file
            subtitle_file = SubtitleFile(
                subtitle=subtitle, date=timezone.now(), user=dummy_user, tenant=tenant
            )

            # create directory for subtitles if not existing
            os.makedirs(os.path.join(settings.MEDIA_ROOT, "subtitles"), exist_ok=True)

            subtitle_file.file.name = os.path.join(
                settings.MEDIA_ROOT,
                "subtitles",
                str(subtitle.id)
                + "_"
                + str(subtitle.language)
                + "_"
                + str(subtitle.last_update.strftime("%d%m%y-%H%M%S"))
                + ".vtt",
            )
            file_content = get_subtitle_webvtt_content(
                str(video.ext_id), str(
                    subtitle.language.iso_code), request=None, tenant=tenant
            )

            new_file = io.open(
                subtitle_file.file.name, "w", encoding="utf-8")
            new_file.write(file_content)
            new_file.close()
            subtitle_file.save()
            print(
                "Video "
                + str(video)
                + ": Video: "
                + video.ext_id
                + ": Saved new subtitle"
            )
        # Case 2: subtitle already exists: do nothing

    video.save()


def get_subtitle_webvtt_content(ext_video_id, language, request=None, tenant=None):
    assert tenant

    try:
        # GET /videos/{id}/subtitles/{lang}
        response = requests.get(
            tenant.get_secret('XIKOLO_API_URL') + "videos/" +
            ext_video_id + "/subtitles/" + language,
            headers={"Authorization": "Bearer " + tenant.XIKOLO_API_TOKEN},
            data={"key": "value"},
        )
        if response.status_code == 200:
            return response.text

    except (requests.ConnectionError) as exception:
        messages.error(
            request, str(exception) + ": " +
                     tenant.XIKOLO_API_URL + " not available."
        )


def get_xikolo_course_list(request):
    tenant: Tenant = request.tenant or get_object_or_404(Tenant, id=1)
    course_list = []
    try:
        # GET /courses/
        response = requests.get(
            tenant.XIKOLO_API_URL + "courses",
            headers={"Authorization": "Bearer " + tenant.XIKOLO_API_TOKEN},
            data={"key": "value"},
        )
        next_link = response.links["next"]["url"]
        course_list_raw = []
        print("next_link")
        if response.status_code == 200:
            course_list_raw = response.json()
            while next_link:
                response = requests.get(
                    next_link,
                    headers={"Authorization": "Bearer " +
                                              tenant.XIKOLO_API_TOKEN},
                    data={"key": "value"},
                )
                if response.status_code == 200:
                    course_list_raw.extend(response.json())
                # Wenn kein next link dann break
                if "next" not in response.links:
                    break
                next_link = response.links["next"]["url"]

            for course_entry in course_list_raw:

                # Get the language:
                iso_language_code = course_entry["language"][0:5]
                print("Language code: " + iso_language_code)
                query_set_lang = IsoLanguage.objects.filter(
                    iso_code=iso_language_code)
                # Check if language exists:
                if query_set_lang:
                    language = get_object_or_404(
                        IsoLanguage, pk=iso_language_code)
                else:
                    # To avoid errors: choose en as default
                    language = get_object_or_404(IsoLanguage, pk="en")

                # Case 1: new course
                if not Course.objects.filter(ext_id=course_entry["id"]).count() > 0:
                    # Create new course if there is none for this external_id
                    # build course object based on API response
                    new_course = Course(
                        title=course_entry["title"],
                        ext_id=course_entry["id"],
                        abstract=course_entry["abstract"],
                        start_date=course_entry["start-date"],
                        end_date=course_entry["end-date"],
                        status=course_entry["status"],
                        language=language,
                        tenant=tenant,
                    )
                    # Add new course to course_list
                    new_course.save()
                    course_list.append(new_course)
                # Case 2: course already exists
                else:
                    # get the existing course object
                    existing_course = get_object_or_404(
                        Course, ext_id=course_entry["id"]
                    )
                    # update existing course
                    existing_course.title = course_entry["title"]
                    existing_course.abstract = course_entry["abstract"]
                    existing_course.start_date = course_entry["start-date"]
                    existing_course.end_date = course_entry["end-date"]
                    existing_course.status = course_entry["status"]
                    existing_course.language = language

                    # Add existing course to list
                    existing_course.save()
                    course_list.append(existing_course)
        print("Course List Updated!")
        return course_list
    except (requests.ConnectionError, KeyError) as exception:
        # messages.error(request, str(exception) + ": " + settings.XIKOLO_API_URL + " not available.")
        print(str(exception) + ": " + tenant.XIKOLO_API_URL + " not available.")


def process_course_from_xikolo(course, request):
    tenant: Tenant = course.tenant
    # Fetch course sections and videos
    # Get video list to get subtitles
    video_list = get_xikolo_course_sections_and_videos(course, request)
    print("Course " + course.ext_id + ": videos are saved")
    if video_list:
        for video in video_list:
            print("Course " + course.ext_id + ": Video: " + video.ext_id)

            # Fetch all subtitles for every video
            subtitle_language_list = get_video_detail(video.pk, request)[
                "subtitle-languages"
            ]
            for language_entry in subtitle_language_list:
                # get iso language object:
                subtitle_lang = get_object_or_404(
                    IsoLanguage, pk=language_entry[0:5])
                # Check if subtitle is transcript or translation:
                if video.original_language == subtitle_lang:
                    is_transcript = True
                else:
                    is_transcript = False
                # Case 1: new subtitle
                if not Subtitle.objects.filter(
                        video=video, language=subtitle_lang, is_transcript=is_transcript
                ):
                    # create new subtitle
                    subtitle = Subtitle(
                        language=subtitle_lang,
                        video=video,
                        is_transcript=is_transcript,
                        status=Subtitle.SubtitleStatus.PUBLISHED,
                        last_update=timezone.now(),
                        origin=Subtitle.Origin.MOOC,
                        user=request.user,
                        tenant=tenant,
                    )
                    subtitle.save()
                    # save webvtt content in subtitle file
                    subtitle_file = SubtitleFile(
                        subtitle=subtitle, date=timezone.now(), user=request.user, tenant=tenant
                    )

                    # create directory for subtitles if not existing
                    os.makedirs(os.path.join(settings.MEDIA_ROOT, "subtitles"), exist_ok=True)

                    subtitle_file.file.name = os.path.join(
                        settings.MEDIA_ROOT,
                        "subtitles",
                        str(subtitle.id)
                        + "_"
                        + str(subtitle.language)
                        + "_"
                        + str(subtitle.last_update.strftime("%d%m%y-%H%M%S"))
                        + ".vtt",
                    )
                    file_content = get_subtitle_webvtt_content(
                        str(video.ext_id), str(
                            subtitle.language.iso_code), request
                    )

                    new_file = io.open(
                        subtitle_file.file.name, "w", encoding="utf-8")
                    new_file.write(file_content)
                    new_file.close()
                    subtitle_file.save()
                    print(
                        "Course "
                        + course.ext_id
                        + ": Video: "
                        + video.ext_id
                        + ": Saved new subtitle"
                    )
                # Case 2: subtitle already exists: do nothing


def publish_subtitle_to_xikolo(request, subtitle_id):
    subtitle = get_object_or_404(Subtitle, pk=subtitle_id)
    tenant = subtitle.tenant

    automatic = 'true' if subtitle.is_automatic else 'false'
    url = (
            tenant.XIKOLO_API_URL
            + "videos/"
            + subtitle.video.ext_id
            + "/subtitles/"
            + subtitle.language.iso_code
            + f"?automatic={automatic}"
    )
    try:
        # Send subtitle file to API
        # PATCH /videos/{id}/subtitles/{lang}
        latest_version = (
            SubtitleFile.objects.filter(
                subtitle=subtitle).order_by("-date").first()
        )
        with io.open(latest_version.file.path, "r", encoding="utf-8") as file:
            text = file.read()
        encoded_data = text.encode(encoding="UTF-8", errors="strict")
        response = requests.patch(
            url,
            encoded_data,
            headers={
                "Authorization": "Bearer " + tenant.XIKOLO_API_TOKEN,
                "Content-Type": "text/vtt; charset=utf-8",
            },
        )
        # Change status to Published
        if response.status_code == 200:
            subtitle.status = Subtitle.SubtitleStatus.PUBLISHED
            subtitle.save()
            messages.success(request, "Latest subtitle version was published.")

            return True
        else:
            human_error_message = ""
            if response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
                human_error_message = "Please check the validity of the vtt file. "

            messages.error(
                request, f"An error occurred while publishing to {tenant.name}. "
                         f"{human_error_message}"
                         f"(Status code: {response.status_code}, subtitle-id: {subtitle.pk})"
            )

    except FileNotFoundError as exception:
        messages.error(request, f"FileNotFoundError: {exception} (subtitle-id: {subtitle.pk})")
    except requests.ConnectionError as exception:
        messages.error(request, f"ConnectionError: {exception} (subtitle-id: {subtitle.pk})")
