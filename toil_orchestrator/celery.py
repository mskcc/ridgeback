from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from kombu import Exchange, Queue
from django.conf import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ridgeback.settings')

app = Celery('ridgeback_toil')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# app.conf.beat_schedule = {
#     "submit_jobs_to_toil": {
#         "task": "toil_orchestrator.tasks.submit_jobs_to_lsf",
#         "schedule": 60.0
#     }
# }

app.conf.task_routes = {'toil_orchestrator.tasks.submit_jobs_to_lsf': {'queue': settings.RIDGEBACK_DEFAULT_QUEUE},
                        'toil_orchestrator.tasks.cleanup_folder': {'queue': settings.RIDGEBACK_DEFAULT_QUEUE}}
#
# app.conf.task_queues = (
#     Queue('toil', routing_key='submit'),
# )

app.conf.beat_schedule = {
    "check_status_of_jobs": {
        "task": "toil_orchestrator.tasks.check_status_of_jobs",
        "schedule": 60.0,
        "options": {"queue": settings.RIDGEBACK_DEFAULT_QUEUE}
    },
    "check_status_of_command_line_jobs": {
        "task": "toil_orchestrator.tasks.check_status_of_command_line_jobs",
        "schedule": 10.0,
        "options": {"queue": settings.RIDGEBACK_DEFAULT_QUEUE}
    }
}
