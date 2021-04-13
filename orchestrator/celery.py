from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings
from celery.schedules import crontab

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ridgeback.settings')

app = Celery('ridgeback_orchestrator')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

app.conf.task_routes = {'orchestrator.tasks.submit_job_to_lsf': {'queue':
                                                                      settings.RIDGEBACK_SUBMIT_JOB_LSF_QUEUE},
                        'orchestrator.tasks.cleanup_folders': {'queue':
                                                                    settings.RIDGEBACK_ACTION_QUEUE},
                        'orchestrator.tasks.resume_job': {'queue':
                                                              settings.RIDGEBACK_ACTION_QUEUE},
                        'orchestrator.tasks.suspend_job': {'queue':
                                                              settings.RIDGEBACK_ACTION_QUEUE},
                        'orchestrator.tasks.abort_job': {'queue':
                                                              settings.RIDGEBACK_ACTION_QUEUE}}

app.conf.beat_schedule = {
    "check_status_of_jobs": {
        "task": "orchestrator.tasks.check_status_of_jobs",
        "schedule": 47.0,
        "options": {"queue": settings.RIDGEBACK_CHECK_STATUS_QUEUE}
    },
    "submit_pending_jobs": {
        "task": "orchestrator.tasks.submit_pending_jobs",
        "schedule": 60.0 * 5,
        "options": {"queue": settings.RIDGEBACK_SUBMIT_JOB_QUEUE}
    },
    "check_status_of_command_line_jobs": {
        "task": "orchestrator.tasks.check_status_of_command_line_jobs",
        "schedule": 60.0,
        "options": {"queue": settings.RIDGEBACK_CHECK_STATUS_QUEUE}
    },
    "cleanup_completed_jobs": {
        "task": "orchestrator.tasks.cleanup_completed_jobs",
        "schedule": crontab(hour='0',
                            ),
        "options": {"queue": settings.RIDGEBACK_CLEANUP_QUEUE}
    },
    "cleanup_failed_jobs": {
        "task": "orchestrator.tasks.cleanup_failed_jobs",
        "schedule": crontab(hour='6',
                            ),
        "options": {"queue": settings.RIDGEBACK_CLEANUP_QUEUE}
    }
}
