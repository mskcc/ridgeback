# Generated by Django 2.2.24 on 2023-08-09 10:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orchestrator', '0012_job_base_dir'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='root_permission',
            field=models.CharField(blank=True, max_length=3, null=True),
        ),
    ]