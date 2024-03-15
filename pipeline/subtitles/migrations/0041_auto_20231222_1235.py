from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subtitles', '0040_auto_20220617_1310'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assignedlanguage',
            name='translation_service',
            field=models.CharField(choices=[('MLLP', 'MLLP'), ('AWS', 'AWS'), ('MANUAL', 'Manual'), ('DEEPL', 'DEEPL')], default='MLLP', max_length=255),
        ),
        migrations.AlterField(
            model_name='course',
            name='transcription_service',
            field=models.CharField(choices=[('MLLP', 'MLLP'), ('AWS', 'AWS'), ('MANUAL', 'Manual'), ('DEEPL', 'DEEPL')], default='MANUAL', max_length=255),
        ),
        migrations.AlterField(
            model_name='serviceprovideruse',
            name='service_provider',
            field=models.CharField(choices=[('MLLP', 'MLLP'), ('AWS_TRANSCRIPTION', 'AWS Transcription'), ('AWS_TRANSLATION', 'AWS Translation'), ('DEEPL', 'DEEPL'), ('AUDESCRIBE_TRANSCRIPTION', 'Audescribe Transcription'), ('OTHER', 'Other')], db_index=True, default='OTHER', max_length=128),
        ),
        migrations.AlterField(
            model_name='subtitle',
            name='origin',
            field=models.CharField(choices=[('MLLP', 'MLLP'), ('AWS', 'AWS'), ('DEEPL', 'DEEPL'), ('AUDESCR', 'AUDESCRIBE'), ('MANU', 'Manual upload'), ('MOOC', 'Downloaded from MOOC platform')], default='MANU', max_length=8),
        ),
    ]
