# Generated by Django 2.2.28 on 2024-09-25 22:37

from django.db import migrations, models
import orchestrator.models


class Migration(migrations.Migration):

    dependencies = [
        ("orchestrator", "0014_merge_20240612_1111"),
    ]

    operations = [
        migrations.AlterField(
            model_name="commandlinetooljob",
            name="status",
            field=models.IntegerField(
                choices=[
                    (0, "CREATED"),
                    (1, "PREPARING"),
                    (2, "SUBMITTING"),
                    (3, "SUBMITTED"),
                    (4, "PENDING"),
                    (5, "RUNNING"),
                    (6, "COMPLETED"),
                    (7, "FAILED"),
                    (8, "TERMINATED"),
                    (9, "UNKNOWN"),
                    (10, "SUSPENDED"),
                ],
                default=orchestrator.models.Status(0),
            ),
        ),
        migrations.AlterField(
            model_name="job",
            name="status",
            field=models.IntegerField(
                choices=[
                    (0, "CREATED"),
                    (1, "PREPARING"),
                    (2, "SUBMITTING"),
                    (3, "SUBMITTED"),
                    (4, "PENDING"),
                    (5, "RUNNING"),
                    (6, "COMPLETED"),
                    (7, "FAILED"),
                    (8, "TERMINATED"),
                    (9, "UNKNOWN"),
                    (10, "SUSPENDED"),
                ],
                default=orchestrator.models.Status(0),
            ),
        ),
    ]
