# Generated by Django 3.1.4 on 2021-01-21 14:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('subtitles', '0005_comment'),
    ]

    operations = [
        migrations.AddField(
            model_name='comment',
            name='for_language',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='subtitles.isolanguage'),
        ),
    ]
