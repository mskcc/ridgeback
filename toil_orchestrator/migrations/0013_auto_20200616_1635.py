# Generated by Django 2.2.10 on 2020-06-16 20:35

from django.db import migrations
from toil_orchestrator.models import Status

def update_dates(apps, _):
    jobs = apps.get_model('toil_orchestrator', 'Job').objects.all()
    for single_job in jobs:
        if single_job.status == Status.COMPLETED or single_job.status == Status.FAILED:
            if not single_job.finished:
                single_job.finished = single_job.modified_date
            if not single_job.submitted:
                single_job.submitted = single_job.created_date
            if not single_job.started:
                single_job.started = single_job.created_date
            single_job.save()

def revert_dates(apps, _):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('toil_orchestrator', '0012_auto_20200604_1733'),
    ]

    operations = [
        migrations.RunPython(update_dates, revert_dates)
    ]
