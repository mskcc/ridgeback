# Generated by Django 2.2.24 on 2022-11-22 00:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orchestrator", "0008_auto_20221005_0957"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="root_permission",
            field=models.CharField(default="750", max_length=3),
        ),
    ]
