# Generated by Django 2.2.10 on 2020-05-20 21:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("toil_orchestrator", "0009_auto_20200415_2120"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="working_dir_clean_up",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
