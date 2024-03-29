# Generated by Django 2.2.10 on 2020-06-24 19:27

from django.db import migrations
from toil_orchestrator.models import message_default
import json
from django.core.serializers.json import DjangoJSONEncoder


def update_message(apps, _):
    jobs = apps.get_model("toil_orchestrator", "Job").objects.all()
    message_obj = message_default()
    for single_job in jobs:
        message = single_job.message
        if message:
            try:
                json.loads(message)
            except:
                message_obj["info"] = message
                single_job.tmp_message = json.dumps(message_obj, sort_keys=True, indent=1, cls=DjangoJSONEncoder)
                single_job.save()


def revert_message(apps, _):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("toil_orchestrator", "0014_job_tmp_message"),
    ]

    operations = [migrations.RunPython(update_message, revert_message)]
