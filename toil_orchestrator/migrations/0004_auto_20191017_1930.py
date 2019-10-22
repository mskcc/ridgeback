# Generated by Django 2.2.2 on 2019-10-17 19:30

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('toil_orchestrator', '0003_auto_20191017_1929'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='inputs',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='job',
            name='outputs',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
    ]
