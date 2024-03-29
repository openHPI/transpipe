# Generated by Django 3.1.4 on 2023-02-13 04:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_tenant_deepl_active'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='transpipeuser',
            options={'permissions': (('can_transcript_all_languages', 'Can transcript ALL languages'), ('can_translate_all_languages', 'Can translate ALL languages'), ('can_see_all_courses', 'Can see ALL courses'), ('download_summary', 'Can download summary'), ('can_use_preview_features', 'Can use preview / beta features'), ('see_todo', 'Can see and use Todo / Tasklist'), ('can_see_service_provider_usage', 'Can see Service Provider Usage'))},
        ),
    ]
