# Generated by Django 2.2.13 on 2021-03-30 13:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("toil_orchestrator", "0018_auto_20201221_1300"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="memlimit",
            field=models.CharField(blank=True, default=None, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="job",
            name="walltime",
            field=models.IntegerField(blank=True, default=None, null=True),
        ),
    ]
