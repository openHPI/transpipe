# Generated by Django 3.1.4 on 2021-06-04 12:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('subtitles', '0020_auto_20210420_1246'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='comment',
            options={'ordering': ['-created']},
        ),
        migrations.AlterModelOptions(
            name='subtitle',
            options={'permissions': (('upload_subtitle_file', 'Can upload subtitle file'), ('fetch_subtitle', 'Can fetch subtitle'), ('publish_subtitle_to_xikolo', 'Can publish subtitle to xikolo'), ('approve_subtitle', 'Can approve subtitle'), ('request_changes_subtitle', 'Request changes'), ('start_workflow_subtitle', 'Start workflow'))},
        ),
    ]
