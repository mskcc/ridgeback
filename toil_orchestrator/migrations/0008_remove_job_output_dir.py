# Generated by Django 2.2.10 on 2020-03-23 20:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("toil_orchestrator", "0007_auto_20200310_1457"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="job",
            name="output_dir",
        ),
    ]
