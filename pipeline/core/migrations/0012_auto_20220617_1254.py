# Generated by Django 3.1.4 on 2022-06-17 10:54

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_auto_20210907_0230'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='transpipeuser',
            options={'permissions': (('can_transcript_all_languages', 'Can transcript ALL languages'), ('can_translate_all_languages', 'Can translate ALL languages'), ('can_see_all_courses', 'Can see ALL courses'), ('download_summary', 'Can download summary'), ('can_use_preview_features', 'Can use preview / beta features'), ('see_todo', 'Can see and use Todo / Tasklist'))},
        ),
    ]
