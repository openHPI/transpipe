# Generated by Django 3.1.4 on 2021-04-16 11:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subtitles', '0018_auto_20210409_0420'),
    ]

    operations = [
        migrations.AddField(
            model_name='subtitle',
            name='is_automatic',
            field=models.BooleanField(default=True),
        ),
    ]
