# Generated by Django 2.2.13 on 2021-03-30 10:26

from django.db import migrations, models
import toil_orchestrator.models


class Migration(migrations.Migration):

    dependencies = [
        ("toil_orchestrator", "0018_auto_20201221_1300"),
    ]

    operations = [
        migrations.AlterField(
            model_name="commandlinetooljob",
            name="status",
            field=models.IntegerField(
                choices=[
                    (0, "CREATED"),
                    (1, "PENDING"),
                    (2, "RUNNING"),
                    (3, "COMPLETED"),
                    (4, "FAILED"),
                    (5, "ABORTED"),
                    (6, "UNKNOWN"),
                    (7, "SUSPENDED"),
                ],
                default=toil_orchestrator.models.Status(0),
            ),
        ),
        migrations.AlterField(
            model_name="job",
            name="status",
            field=models.IntegerField(
                choices=[
                    (0, "CREATED"),
                    (1, "PENDING"),
                    (2, "RUNNING"),
                    (3, "COMPLETED"),
                    (4, "FAILED"),
                    (5, "ABORTED"),
                    (6, "UNKNOWN"),
                    (7, "SUSPENDED"),
                ],
                default=toil_orchestrator.models.Status(0),
            ),
        ),
    ]
