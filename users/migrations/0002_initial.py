# Generated migration — add device_id to bluelink_users
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='device_id',
            field=models.CharField(
                max_length=256,
                blank=True,
                null=True,
                default=None,
                help_text='Bound device ID — set on first login, locked after that'
            ),
        ),
    ]
