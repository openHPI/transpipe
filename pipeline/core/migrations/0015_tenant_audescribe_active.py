from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_auto_20230213_0505'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='audescribe_active',
            field=models.BooleanField(default=False),
        ),
    ]
