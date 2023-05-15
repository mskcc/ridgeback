# Generated by Django 2.2.24 on 2023-04-18 14:42

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("orchestrator", "0010_merge_20221222_1603"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="metadata",
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, null=True),
        ),
    ]
