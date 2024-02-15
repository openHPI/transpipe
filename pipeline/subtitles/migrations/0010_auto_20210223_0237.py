# Generated by Django 3.1.4 on 2021-02-23 01:37

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('subtitles', '0009_auto_20210219_0459'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subtitle',
            name='status',
            field=models.CharField(choices=[('IT', 'Initial'), ('IN', 'In Progress'), ('AU', 'Auto Generated'), ('RE', 'Reviewed'), ('UP', 'Uploaded by user'), ('PU', 'Published'), ('QU', 'Queued'), ('WA', 'Waiting for review'), ('CH', 'Changes Requested'), ('AP', 'Approved')], default='IN', max_length=2),
        ),
        migrations.CreateModel(
            name='AssignedLanguage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('required', models.BooleanField(default=False)),
                ('translation_service', models.CharField(choices=[('MLLP', 'MLLP'), ('AWS', 'AWS'), ('MANUAL', 'Manual')], default='MLLP', max_length=255)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='subtitles.course')),
                ('iso_language', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='subtitles.isolanguage')),
            ],
        ),
        migrations.RemoveField(
            model_name='course',
            name='translated_languages',
        ),
        migrations.AddField(
            model_name='course',
            name='translated_languages',
            field=models.ManyToManyField(related_name='translated', through='subtitles.AssignedLanguage', to='subtitles.IsoLanguage'),
        ),
    ]