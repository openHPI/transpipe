# Generated by Django 3.1.4 on 2021-06-18 11:11

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('subtitles', '0021_auto_20210604_1455'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='course',
            options={'permissions': (('fetch_courses', 'Can fetch courses'), ('download_summary', 'Can download summary'), ('change_settings', 'Can change settings'), ('synchronize_with_xikolo', 'Can synchronize with xikolo'))},
        ),
    ]
