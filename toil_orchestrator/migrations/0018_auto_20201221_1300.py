# Generated by Django 2.2.10 on 2020-12-21 18:00

from django.db import migrations, models
import toil_orchestrator.models


def migrate_statuses(apps, schema_editor):
    Job = apps.get_model('toil_orchestrator', 'Job')
    jobs = Job.objects.all()
    for job in jobs:
        if job.status == 5:
            job.status = 6
            job.save()


class Migration(migrations.Migration):

    dependencies = [
        ('toil_orchestrator', '0017_auto_20200624_1635'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commandlinetooljob',
            name='status',
            field=models.IntegerField(choices=[(0, 'CREATED'), (1, 'PENDING'), (2, 'RUNNING'), (3, 'COMPLETED'), (4, 'FAILED'), (5, 'ABORTED'), (6, 'UNKNOWN')], default=0),
        ),
        migrations.AlterField(
            model_name='job',
            name='status',
            field=models.IntegerField(choices=[(0, 'CREATED'), (1, 'PENDING'), (2, 'RUNNING'), (3, 'COMPLETED'), (4, 'FAILED'), (5, 'ABORTED'), (6, 'UNKNOWN')], default=toil_orchestrator.models.Status(0)),
        ),
        migrations.RunPython(migrate_statuses)
    ]
