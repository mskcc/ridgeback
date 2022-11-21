# Generated by Django 2.2.24 on 2022-11-18 23:08

from django.db import migrations, models
import orchestrator.models


class Migration(migrations.Migration):

    dependencies = [
        ("orchestrator", "0008_auto_20221005_0957"),
    ]

    operations = [
        migrations.AlterField(
            model_name="commandlinetooljob",
            name="status",
            field=models.IntegerField(
                choices=[
                    (0, "CREATED"),
                    (1, "SUBMITTING"),
                    (2, "SUBMITTED"),
                    (3, "PENDING"),
                    (4, "RUNNING"),
                    (5, "COMPLETED"),
                    (6, "FAILED"),
                    (7, "TERMINATED"),
                    (8, "UNKNOWN"),
                    (9, "SUSPENDED"),
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
                    (1, "SUBMITTING"),
                    (2, "SUBMITTED"),
                    (3, "PENDING"),
                    (4, "RUNNING"),
                    (5, "COMPLETED"),
                    (6, "FAILED"),
                    (7, "TERMINATED"),
                    (8, "UNKNOWN"),
                    (9, "SUSPENDED"),
                ],
                default=orchestrator.models.Status(0),
            ),
        ),
    ]