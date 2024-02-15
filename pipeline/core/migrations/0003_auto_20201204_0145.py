# Generated by Django 3.1.3 on 2020-12-04 00:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subtitles', '0003_auto_20201126_0341'),
        ('core', '0002_auto_20201123_1420'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='transpipeuser',
            options={'permissions': (('can_transcript_all_languages', 'Can transcript ALL languages'), ('can_translate_all_languages', 'Can translate ALL languages'), ('download_summary', 'Can download summary'))},
        ),
        migrations.AddField(
            model_name='transpipeuser',
            name='assigned_courses',
            field=models.ManyToManyField(to='subtitles.Course'),
        ),
        migrations.AddField(
            model_name='transpipeuser',
            name='assigned_languages',
            field=models.ManyToManyField(to='subtitles.IsoLanguage'),
        ),
    ]