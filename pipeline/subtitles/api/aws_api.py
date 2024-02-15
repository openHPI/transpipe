""" Handling of API calls to AWS """
from pprint import pprint
from urllib.request import urlretrieve

import boto3
import requests
import urllib3
import os
import io
import json
import datetime
import certifi
from botocore.exceptions import ClientError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from django.utils.timezone import make_aware
from django_celery_beat.models import PeriodicTask

from core.models import Tenant, TranspipeUser
from mooclink.services import MAPPING_SLIM_TO_FULL, subtitle_status_change_service
from . import get_runtime
from ..models import Subtitle, Video, IsoLanguage, ServiceProviderUse
from ..models.subtitle_file import SubtitleFile
from ..models.awsupload import AWSupload

# Requirements
# deploy mie app
# create mie user in aws
#   cognito -> user pools -> create user with group "mieDevelopersGroup"
#   cognito -> user pools -> app clients -> CHECK Enable username password based authentication (ALLOW_USER_PASSWORD_AUTH)
#   output: username, password
# create iam user for s3
#   output: aws_access_key_id, aws_secret_access_key
# get output from mie stack output page
#   region, client_id, user_pool_id, account_id, dataplane_api_endpoint, dataplane_bucket, workflow_api_endpoint


def connect_mie_app(tenant: Tenant):
    """
    Connect to MIE App API
    returns a token to send in http api requests
    """
    client = boto3.client("cognito-idp", tenant.get_secret('AWS_REGION'))
    response = client.initiate_auth(
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": tenant.get_secret('COGNITO_USER'),
                        "PASSWORD": tenant.get_secret('COGNITO_PASS'), },
        ClientId=tenant.get_secret('MIE_CLIENT_ID'),
    )
    print("connected to mie api")
    return response["AuthenticationResult"]["IdToken"]


def connect_to_s3(tenant: Tenant):
    """
    returns a client to connect to S3 API
    """

    assert tenant, "A tenant has to be given in order to select the credentials."

    s3 = boto3.client(
        "s3",
        region_name=tenant.get_secret('AWS_REGION'),
        aws_access_key_id=tenant.get_secret('S3_ACCESS_KEY_ID'),
        aws_secret_access_key=tenant.get_secret('S3_SECRET_ACCESS_KEY'),
    )
    print("connected to s3")
    return s3


def download_video(video_url, videofilename):
    """ Downloads a video with a video url """

    http = urllib3.PoolManager(ca_certs=certifi.where())
    response = http.request("GET", video_url, preload_content=False)
    new_file = io.open(os.path.join(settings.MEDIA_ROOT + videofilename), "wb")
    for chunk in response.stream(32):
        new_file.write(chunk)
    new_file.close()
    print("video download complete")
    print(settings.MEDIA_ROOT + videofilename)


def aws_start_transcription_only(video_id, initiator_id=None):
    video = Video.objects.get(pk=video_id)
    tenant: Tenant = video.tenant

    videofilename = str(video.id) + ".mp4"
    videodir = os.path.join(settings.MEDIA_ROOT, 'tmp')
    os.makedirs(videodir, exist_ok=True)

    local_video_path = os.path.join(videodir, videofilename)

    urlretrieve(video.video_url, local_video_path)

    try:
        video_duration, video_frame_count = get_runtime(local_video_path)
    except Exception:
        video_duration, video_frame_count = 0, 0

    s3 = connect_to_s3(tenant=tenant)
    print(tenant.DATAPLANE_BUCKET)
    s3.upload_file(
        local_video_path,
        tenant.DATAPLANE_BUCKET,
        videofilename,
    )
    # delete local video after uploading it to s3
    if os.path.isfile(local_video_path):
        os.remove(local_video_path)
    else:
        print("The file does not exist")

    mie_token = connect_mie_app(tenant=tenant)

    asset_response = requests.post(
        url=tenant.get_secret('DATAPLANE_API_ENDPOINT') + "create",
        headers={
            "Content-Type": "application/json",
            "Authorization": mie_token
        },
        json={
            'Name': f"{video.pk}",
            'Input': {
                'S3Bucket': tenant.DATAPLANE_BUCKET,
                'S3Key': videofilename,
            }
        }
    )
    asset_response.raise_for_status()

    with open(os.path.join(settings.BASE_DIR, "subtitles", "api", "aws_config_transcript.json"), "r") as f:
        workflow_config = json.load(f)

    workflow_config["Input"] = asset_response.json()

    asset_id = workflow_config["Input"]["AssetId"]

    try:
        transcribe_language = MAPPING_SLIM_TO_FULL[video.original_language.iso_code]
    except KeyError:
        raise ValueError(f"{video.original_language.iso_code} is currently WIP")

    workflow_config["Configuration"]["CaptionFileStage2"]["WebToSRTCaptions"]["TargetLanguageCodes"] = [video.original_language.iso_code]
    workflow_config["Configuration"]["CaptionFileStage2"]["WebToVTTCaptions"]["TargetLanguageCodes"] = [video.original_language.iso_code]
    workflow_config["Configuration"]["WebCaptionsStage2"]["WebCaptions"]["SourceLanguageCode"] = video.original_language.iso_code
    workflow_config["Configuration"]["TranslateStage2"]["TranslateWebCaptions"]["SourceLanguageCode"] = video.original_language.iso_code
    workflow_config["Configuration"]["defaultAudioStage2"]["Transcribe"]["TranscribeLanguage"] = transcribe_language

    mie_response = requests.post(
        url=tenant.get_secret('WORKFLOW_API_ENDPOINT') + "workflow/execution",
        headers={
            "Content-Type": "application/json",
            "Authorization": mie_token
        },
        json=workflow_config
    )
    mie_response.raise_for_status()

    with transaction.atomic():
        aws_upload = AWSupload(
            video=video,
            asset_id=asset_id,
            upload_date=timezone.now(),
            source_lang=video.original_language.iso_code,
            aws_config=workflow_config,
            tenant=tenant,
        )
        aws_upload.save()

        su = ServiceProviderUse(
            tenant=tenant,
            video=video,
            service_provider=ServiceProviderUse.ServiceProvider.AWS_TRANSCRIPTION,
            initiated_by_id=initiator_id,
        )

        su.data = {
            'AWS_WORKFLOW': "AWS_MIE_TRANSCRIPTION_v1",
            'source_language': video.original_language.iso_code,
            'video_duration': video_duration,
            'video_frame_count': video_frame_count,
        }
        su.save()

        video.workflow_data['service_provider_use'] = {
            'id': su.pk,
        }

        video.workflow_status = "AWS_INITIATED"
        video.workflow_data['asset_id'] = asset_id
        video.workflow_data['aws_upload_id'] = aws_upload.pk
        video.save()


def aws_start_transcription(video_id):
    """ Starts a transcription on aws """
    video = Video.objects.get(pk=video_id)
    tenant: Tenant = video.tenant
    assert tenant

    video = get_object_or_404(Video, pk=video_id)

    videofilename = str(video.id) + ".mp4"
    videodir = os.path.join(settings.MEDIA_ROOT)
    print(videodir)
    print(os.path.join(videodir, videofilename))
    download_video(video.video_url, videofilename)

    # TODO: set source and target languages from user input
    trans_lang = "en-US"  # Transcibe stages
    source_lang = str(video.original_language.iso_code)  # Translate and Webcaption stages 'en'
    target_langs = json.dumps([l.iso_code for l in video.translated_languages])  # Translation stages  '["ar","zh"]'
    output_langs = json.dumps([l.iso_code for l in video.languages])  # convert to vtt and srt files '["ar","zh","en"]'

    workflow_config_file = os.path.join(
        settings.BASE_DIR, "subtitles", "api", "aws_config.json"
    )
    # print("config " + workflow_config_file)

    s3 = connect_to_s3(tenant=tenant)
    print(tenant.DATAPLANE_BUCKET)
    s3.upload_file(
        os.path.join(settings.MEDIA_ROOT, videofilename),
        tenant.DATAPLANE_BUCKET,
        videofilename,
    )
    # delete local video after uploading it to s3
    if os.path.exists(os.path.join(settings.MEDIA_ROOT, videofilename)):
        os.remove(os.path.join(settings.MEDIA_ROOT, videofilename))
    else:
        print("The file does not exist")

    # Create an asset dataplane api
    data = (
        '{"Name": "Name","Input": { "S3Bucket":"'
        + tenant.DATAPLANE_BUCKET
        + '", "S3Key": "'
        + videofilename
        + '"}}'
    )
    mie_token = connect_mie_app(tenant=tenant)
    http = urllib3.PoolManager(ca_certs=certifi.where())
    headers = {"Content-Type": "application/json", "Authorization": mie_token}
    response = http.request(
        "POST",
        tenant.get_secret('DATAPLANE_API_ENDPOINT') + "create",
        body=data.encode("utf-8"),
        headers=headers,
    )
    # print(response.status)
    # print(response.data.decode("utf-8"))
    asset = json.loads(response.data.decode("utf-8"))
    # load workflow_config
    with open(workflow_config_file, "r") as myfile:
        config = myfile.read()
    config = config.replace("XXX_TRANS_LANG_XXX", trans_lang)
    config = config.replace("XXX_SOURCE_LANG_XXX", source_lang)
    config = config.replace("XXX_TARGET_LANGS_XXX", target_langs)
    config = config.replace("XXX_OUTPUT_LANGS_XXX", output_langs)
    workflow_config = json.loads(config)
    # print(asset)
    workflow_config["Input"] = asset
    # print(json.dumps(workflow_config))
    asset_id = workflow_config["Input"]["AssetId"]

    upload_object = AWSupload(
        video=video, asset_id=asset_id, upload_date=timezone.now(),
        tenant=video.tenant,
    )
    upload_object.save()

    # Execute a workflow with workflow config
    http = urllib3.PoolManager(ca_certs=certifi.where())
    headers = {"Content-Type": "application/json", "Authorization": mie_token}
    response = http.request(
        "POST",
        tenant.get_secret('WORKFLOW_API_ENDPOINT') + "workflow/execution",
        body=json.dumps(workflow_config),
        headers=headers,
    )
    # print(response.status)
    # print(json.loads(response.data.decode("utf-8")))
    # Status becomes in progress:
    status_in_progress = Subtitle.SubtitleStatus.IN_PROGRESS

    queue_user = get_object_or_404(TranspipeUser, id=1)

    new_subtitle = Subtitle(
        language=video.original_language,
        video=video,
        is_transcript=True,
        status=status_in_progress,
        origin=Subtitle.Origin.AWS,
        last_update=timezone.now(),
        user=queue_user,
        tenant=tenant,
    )
    new_subtitle.save()
    return


def aws_start_translation(video, selected_language):
    # TODO: Start only a translation for an existing asset
    return


def aws_update_transcription_only(video):
    tenant: Tenant = video.tenant
    mie_token = connect_mie_app(tenant=tenant)

    video.workflow_data['update_count'] = video.workflow_data.get('update_count', 0) + 1
    video.save()

    if not video.workflow_status:
        print("Workflow already finished")
        return

    if video.workflow_data['update_count'] > 32:
        video.workflow_data['canceled'] = str(timezone.now())
        video.workflow_status = None

        if periodic_task_id := video.workflow_data.get('periodic_task_id'):
            PeriodicTask.objects.get(pk=periodic_task_id).delete()
            video.workflow_data['cleared'] = True

        video.save()
        return

    asset_id = video.workflow_data['asset_id']
    source_lang = video.original_language.iso_code

    resp = requests.get(
        url = tenant.get_secret('WORKFLOW_API_ENDPOINT') + "/workflow/execution/asset/" + asset_id,
        headers={
            "Content-Type": "application/json",
            "Authorization": mie_token
        },
    )

    resp.raise_for_status()
    wf_execution_response = resp.json()
    assert len(wf_execution_response) == 1

    wf_execution_response, = wf_execution_response

    pprint(wf_execution_response)

    if wf_execution_response['Status'] == "Complete" and wf_execution_response['CurrentStage'] == "End":
        stage_id = wf_execution_response['Id']
        s3 = connect_to_s3(tenant=tenant)

        s3_captions_path = (
                "private/assets/" + asset_id
                + "/workflows/" + stage_id
                + "/WebCaptionsTranscribe_" + source_lang + ".json"
        )

        s3captions = f"private/assets/{asset_id}/workflows/{stage_id}/Captions_{source_lang}.vtt"

        with transaction.atomic():
            transcription_subtitle = Subtitle.objects.filter(video=video, language=video.original_language, is_transcript=True).order_by('-pk').first()

            if transcription_subtitle:
                transcription_subtitle.origin = Subtitle.Origin.AWS
                transcription_subtitle.is_automatic = True
            else:
                transcription_subtitle = Subtitle(
                    video=video,
                    language=video.original_language,
                    is_transcript=True,
                    is_automatic=True,
                    origin=Subtitle.Origin.AWS,
                    user_id=1,
                    last_update=timezone.now(),
                    tenant=tenant,
                )

            transcription_subtitle.status = Subtitle.SubtitleStatus.AUTO_GENERATED
            transcription_subtitle.save()

            subtitle_file = SubtitleFile(
                subtitle=transcription_subtitle,
                date=timezone.now(),
                user_id=1,
                tenant=tenant,
            )

            dt_str = subtitle_file.date.strftime("%d%m%y-%H%M%S")
            subtitle_file.file.name = os.path.join(settings.MEDIA_ROOT, 'subtitles',
                                f"{transcription_subtitle.id}_{transcription_subtitle.language}_{dt_str}-MS.vtt")
            subtitle_file.save()

            with open(subtitle_file.file.name, "wb") as transcript_f:
                s3.download_fileobj(tenant.DATAPLANE_BUCKET, s3captions, transcript_f)

            video.workflow_status = None
            video.workflow_data['finished'] = str(timezone.now())

            if periodic_task_id := video.workflow_data.get('periodic_task_id'):
                PeriodicTask.objects.get(pk=periodic_task_id).delete()
                video.workflow_data['cleared'] = True

            video.save()

        subtitle_status_change_service.status_changed(transcription_subtitle, Subtitle.SubtitleStatus.IN_PROGRESS)

    else:
        return json.dumps(wf_execution_response)


def aws_restart_workflow(video):
    print("aws_restart_workflow")
    tenant: Tenant = video.tenant
    assert tenant

    mie_token = connect_mie_app(tenant=tenant)
    # TODO get asset id
    upload_object = AWSupload.objects.filter(
        video=video).order_by("-upload_date")[0]
    asset_id = upload_object.asset_id
    # Get stageId of currently executed stage
    http = urllib3.PoolManager(ca_certs=certifi.where())
    headers = {"Content-Type": "application/json", "Authorization": mie_token}
    response = http.request(
        "GET",
        tenant.get_secret('WORKFLOW_API_ENDPOINT') +
        "/workflow/execution/asset/" + asset_id,
        headers=headers,
    )
    stage = json.loads(response.data.decode("utf-8"))
    print(stage)
    stage_id = stage[0]["Id"]

    # GET /workflow/execution/{Id}
    # resume at waiting stage
    body = '{"WaitingStageName":"CaptionEditingWaitStage"}'
    http = urllib3.PoolManager(ca_certs=certifi.where())
    headers = {"Content-Type": "application/json", "Authorization": mie_token}
    response = http.request(
        "PUT",
        tenant.get_secret('WORKFLOW_API_ENDPOINT') +
        "workflow/execution/" + stage_id,
        body=body,
        headers=headers,
    )
    print(response.status)
    upload_object = AWSupload(
        video=video, asset_id=asset_id, stage_id=stage_id, upload_date=timezone.now(),
        tenant=tenant,
    )
    upload_object.save()


def download_json_transcript(request, AWSupload):
    s3 = connect_to_s3(tenant=request.tenant)

    # TODO get json


def aws_update_video_status(video, video_id=None):
    """ This function updates the AWS subtitles when they are still 'in progress' """
    print("aws_update_video_status")

    if video_id:
        video = Video.objects.get(pk=video_id)

    tenant: Tenant = video.tenant

    aws_subtitles_in_progress_count = Subtitle.objects.filter(
        origin=Subtitle.Origin.AWS,
        status=Subtitle.SubtitleStatus.IN_PROGRESS,
        video=video,
        #last_update__lte=(timezone.now() - datetime.timedelta(minutes=5)),
    ).count()
    if (aws_subtitles_in_progress_count == 0):
        print("skipp")
        return

    # check status of transcript if aws status = "waiting" download json
    # Get stageID of currently executed stage
    aws_transcript = Subtitle.objects.filter(
        origin=Subtitle.Origin.AWS,
        video=video,
        is_transcript=True,
        #last_update__lte=(timezone.now() - datetime.timedelta(minutes=5)),
    )[0]
    aws_upload = AWSupload.objects.filter(video=video)[0]
    mie_token = connect_mie_app(tenant=tenant)
    http = urllib3.PoolManager(ca_certs=certifi.where())
    headers = {"Content-Type": "application/json", "Authorization": mie_token}
    response = http.request(
        "GET",
        tenant.get_secret('WORKFLOW_API_ENDPOINT') +
        "/workflow/execution/asset/" + aws_upload.asset_id,
        headers=headers,
    )
    stage = json.loads(response.data.decode("utf-8"))
    print("--->", stage)
    print(stage[0]["Status"])
    aws_upload.stage_id = stage[0]["Id"]
    aws_upload.upload_date = timezone.now()
    aws_upload.save()
    if stage[0]["Status"] == "Waiting" and aws_transcript.status == Subtitle.SubtitleStatus.IN_PROGRESS:
        s3 = connect_to_s3(tenant=tenant)
        # download json and improve json
        # s3_captions_path = ("private/assets/"+ aws_upload.asset_id+ "/workflows/"+ aws_upload.stage_id+ "/WebCaptionsTranscribe_"+ aws_upload.source_lang+ ".json")
        s3_captions_path = (
            "private/assets/" + aws_upload.asset_id
            + "/workflows/" + aws_upload.stage_id
            + "/WebCaptionsTranscribe_" + aws_upload.source_lang + ".json"
        )
        aws_transcript = Subtitle.objects.filter(
            origin=Subtitle.Origin.AWS, video=video, is_transcript=True,
        )[0]
        new_subtitle_file = SubtitleFile(
            subtitle=aws_transcript,
            date=timezone.now(),
            user_id=1,  # TODO: create auto-download-user or something comparable
            tenant=tenant,
        )
        new_subtitle_file.file.name = (
            settings.MEDIA_ROOT
            + "subtitles/"
            + str(aws_transcript.id)
            + "_"
            + str(aws_transcript.language)
            + "_"
            + str(new_subtitle_file.date.strftime("%d%m%y-%H%M%S"))
            + ".vtt"
        )
        new_subtitle_file.save()
        aws_transcript.status = Subtitle.SubtitleStatus.AUTO_GENERATED
        aws_transcript.last_update = new_subtitle_file.date
        aws_transcript.save()

        with open(new_subtitle_file.file.name, "wb") as transscript:
            s3.download_fileobj(
                tenant.DATAPLANE_BUCKET, s3_captions_path, transscript)

        # clear block
        with transaction.atomic():
            video.workflow_status = None
            if periodic_task_id := video.workflow_data.get('periodic_task_id'):
                PeriodicTask.objects.get(pk=periodic_task_id).delete()
                video.workflow_data['cleared'] = True

            video.save()

        # TODO: use json and parse json to webvtt
        ## aws_restart_workflow(video) Why is this needed?
        return
    # restart workflow
    elif stage[0]["Status"] == "Waiting" and aws_transcript.status == Subtitle.SubtitleStatus.REVIEWED:
        aws_restart_workflow(video)

    elif stage[0]["Status"] == "Complete":
        aws_subtitles = Subtitle.objects.filter(
            origin=Subtitle.Origin.AWS,
            status=Subtitle.SubtitleStatus.IN_PROGRESS,
            video=video,
            is_transcript=False,
            last_update__lte=(timezone.now() - datetime.timedelta(minutes=5)),
        )
        for subtitle in aws_subtitles:
            aws_download_subtitle_file(subtitle)
        # TODO: download needed because json could not be converted right now.
        aws_download_subtitle_file(aws_transcript)

    return


def upload_improved_transcript(video):
    # get reviewed transcript

    tenant: Tenant = video.tenant
    assert tenant

    aws_transcript = Subtitle.objects.filter(
        origin=Subtitle.Origin.AWS, video=video, is_transcript=True,
    )[0]
    json_transcript = (
        SubtitleFile.objects.filter(subtitle=self.object.id)
        .order_by("-date")
        .first()
    )
    # load upload object to get right location for reviewed transcript
    upload_object = AWSupload.objects.filter(
        video=video).order_by("-upload_date")[0]
    s3_captions_path = (
        "private/assets/"
        + aws_upload.asset_id
        + "/workflows/"
        + aws_upload.stage_id
        + "/WebCaptionsTranscribe_"
        + aws_upload.source_lang
        + ".json"
    )
    # Upload reviewed transcript
    s3 = connect_to_s3(tenant=tenant)
    s3.upload_file(json_transcript.file.path,
                   tenant.DATAPLANE_BUCKET, s3_captions_path)


def aws_restart_workflow(request, video):
    # TODO: HANDLE JSON TRANSCRIPTS
    # IMPROVEMENT OF TRANSCRIPT NOT POSSIBLE RIGHT NOW
    # if (transcript is reviewed?) --> upload_improved_transcript(video)

    tenant: Tenant = video.tenant

    aws_transcript = Subtitle.objects.filter(
        origin=Subtitle.Origin.AWS, video=video, is_transcript=True,
    )[0]
    upload_object = AWSupload.objects.filter(
        video=video).order_by("-upload_date")[0]
    mie_token = connect_mie_app(tenant=tenant)
    body = '{"WaitingStageName":"CaptionEditingWaitStage"}'
    http = urllib3.PoolManager(ca_certs=certifi.where())
    headers = {"Content-Type": "application/json", "Authorization": mie_token}
    print(tenant.get_secret('WORKFLOW_API_ENDPOINT') +
          'workflow/execution/'+upload_object.stage_id)
    response = http.request('PUT', tenant.get_secret('WORKFLOW_API_ENDPOINT')+'workflow/execution/' +
                            upload_object.stage_id, body=body, headers=headers)
    print(response.status)
    # json.loads(response.data.decode('utf-8'))


def aws_download_subtitle_file(subtitle):
    """ Download subtitle file from MLLP"""
    print("aws_download_subtitle_file")

    tenant: Tenant = subtitle.tenant
    video: Video = subtitle.video
    user: TranspipeUser = subtitle.user

    try:
        upload_object = AWSupload.objects.filter(video=subtitle.video).order_by(
            "-upload_date"
        )[0]
        lang = subtitle.language.iso_code
        print(lang)
        asset_id = upload_object.asset_id
        stage_id = upload_object.stage_id

        for lang_n in ["ar","zh","en"]:
            print("downloading", lang_n)
            lang = IsoLanguage.objects.get(iso_code=lang_n)

            s3captions = (
                "private/assets/"
                + asset_id
                + "/workflows/"
                + stage_id
                + "/Captions_"
                + lang.iso_code
                + ".vtt"
            )

            subtitle = Subtitle.objects.filter(
                    tenant=tenant,
                    video=video,
                    language=lang,
                    origin=Subtitle.Origin.AWS,
            ).order_by('-last_update').first()

            if not subtitle:
                subtitle = Subtitle(
                    tenant=tenant,
                    user=user,
                    language=lang,
                    origin=Subtitle.Origin.AWS,
                    is_transcript=(lang == video.original_language),
                    is_automatic=True,
                    last_update=make_aware(datetime.datetime.now()),
                    video=video
                )
                subtitle.save()

            subtitle.status = Subtitle.SubtitleStatus.AUTO_GENERATED
            subtitle.save()

            new_subtitle_file = SubtitleFile(
                subtitle=subtitle,
                date=timezone.now(),
                user=subtitle.user,  # TODO: create auto-download-user or something comparable
                tenant=tenant,
            )
            new_subtitle_file.file.name = (
                settings.MEDIA_ROOT
                + "subtitles/"
                + str(subtitle.id)
                + "_"
                + str(lang)
                + "_"
                + str(new_subtitle_file.date.strftime("%d%m%y-%H%M%S"))
                + ".vtt"
            )
            new_subtitle_file.save()
            s3 = connect_to_s3(tenant=tenant)
            with open(new_subtitle_file.file.name, "wb") as fi:
                try:
                    s3.download_fileobj(tenant.DATAPLANE_BUCKET, s3captions, fi)
                except ClientError as e:
                    fi.write(f"Error while downloading vtt captions from s3\nError: {e}".encode('utf-8'))

    except TypeError as e:
        print("type", e)
        return False
    return True


def aws_download_video(videodir, videofilename):
    # download for Testing only
    with open(os.path.join(videodir, "download", videofilename), "wb") as f:
        s3.download_fileobj(settings.DATAPLANE_BUCKET, videofilename, f) # TODO: needs tenant information
