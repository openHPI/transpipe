# Generated by Django 3.1.4 on 2022-06-17 11:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_auto_20220617_1254'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='deepl_active',
            field=models.BooleanField(default=False),
        ),
    ]
