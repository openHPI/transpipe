# Generated by Django 3.1.4 on 2021-04-07 18:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subtitles', '0016_auto_20210407_0153'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='ext_id',
            field=models.CharField(max_length=200),
        ),
        migrations.AlterField(
            model_name='coursesection',
            name='ext_id',
            field=models.CharField(max_length=200),
        ),
        migrations.AlterField(
            model_name='video',
            name='ext_id',
            field=models.CharField(max_length=200),
        ),
        migrations.AlterField(
            model_name='video',
            name='item_id',
            field=models.CharField(db_index=True, max_length=512, null=True),
        ),
    ]
