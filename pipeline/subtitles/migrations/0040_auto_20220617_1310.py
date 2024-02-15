# Generated by Django 3.1.4 on 2022-06-17 11:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subtitles', '0039_auto_20220617_1254'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subtitle',
            name='origin',
            field=models.CharField(choices=[('MLLP', 'MLLP'), ('AWS', 'AWS'), ('DEEPL', 'DEEPL'), ('MANU', 'Manual upload'), ('MOOC', 'Downloaded from MOOC platform')], default='MANU', max_length=8),
        ),
    ]