# Generated by Django 3.1.4 on 2022-01-20 14:46

from django.db import migrations
import embed_video.fields


class Migration(migrations.Migration):

    dependencies = [
        ('subtitles', '0035_serviceprovideruse'),
    ]

    operations = [
        migrations.AlterField(
            model_name='video',
            name='video_url_lecturer',
            field=embed_video.fields.EmbedVideoField(blank=True, max_length=1000, null=True),
        ),
        migrations.AlterField(
            model_name='video',
            name='video_url_pip',
            field=embed_video.fields.EmbedVideoField(max_length=1000),
        ),
        migrations.AlterField(
            model_name='video',
            name='video_url_slides',
            field=embed_video.fields.EmbedVideoField(blank=True, max_length=1000, null=True),
        ),
    ]
