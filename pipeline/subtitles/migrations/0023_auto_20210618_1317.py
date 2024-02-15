# Generated by Django 3.1.4 on 2021-06-18 11:17

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('subtitles', '0022_auto_20210618_1311'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='course',
            options={'permissions': (('fetch_courses', 'Can fetch courses'), ('download_summary', 'Can download summary'), ('change_settings', 'Can change settings'), ('synchronize_with_xikolo', 'Can synchronize with xikolo'), ('can_do_bulk_operations', 'Can do bulk operations'), ('bulk_start_workflow', 'Can start workflow videos in bulk'), ('bulk_approve', 'Can approve subtitles in bulk'), ('bulk_publish', 'Can publish subtitles in bulk'), ('bulk_disapprove', 'Can revoke approval of subtitles in bulk'), ('bulk_delete', 'Can delete subtitles in bulk'))},
        ),
    ]