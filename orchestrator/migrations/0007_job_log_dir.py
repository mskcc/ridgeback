# Generated by Django 2.2.24 on 2022-03-22 14:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orchestrator", "0006_delete_jobcommands"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="log_dir",
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
    ]
