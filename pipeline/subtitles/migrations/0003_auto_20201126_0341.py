# Generated by Django 3.1.3 on 2020-11-26 02:41

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('subtitles', '0002_auto_20201126_0302'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='course',
            options={'permissions': (('fetch_courses', 'Can fetch courses'), ('download_summary', 'Can download summary'))},
        ),
        migrations.AlterModelOptions(
            name='subtitle',
            options={'permissions': (('upload_subtitle_file', 'Can upload subtitle file'), ('fetch_subtitle', 'Can fetch subtitle'), ('publish_subtitle_to_xikolo', 'Can publish subtitle to xikolo'))},
        ),
        migrations.AlterModelOptions(
            name='video',
            options={'permissions': (('start_translation', 'Can start translation'), ('start_transcription', 'Can start transcription'))},
        ),
    ]
