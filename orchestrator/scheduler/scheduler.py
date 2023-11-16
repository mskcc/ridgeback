from enum import IntEnum
from django.conf import settings
from orchestrator.models import Job, Status


class QueueType(IntEnum):
    SHORT = 0
    MEDIUM = 1
    LONG = 2


class Scheduler(object):
    @staticmethod
    def get_jobs_to_submit():
        """
        Walltime:
        SHORT: walltime < 4320
        MEDIUM: 4320 <= walltime < 7200
        LONG: 7200 <= walltime
        """
        short_jobs_count = Job.objects.filter(
            status__gte=Status.SUBMITTING,
            status__lt=Status.COMPLETED,
            leader_walltime__lt=settings.SHORT_JOB_MAX_DURATION,
        ).count()
        medium_jobs_count = Job.objects.filter(
            status__gte=Status.SUBMITTING,
            status__lt=Status.COMPLETED,
            leader_walltime__gte=settings.SHORT_JOB_MAX_DURATION,
            leader_walltime__lt=settings.MEDIUM_JOB_MAX_DURATION,
        ).count()
        long_jobs_count = Job.objects.filter(
            status__gte=Status.SUBMITTING,
            status__lt=Status.COMPLETED,
            leader_walltime__gte=settings.MEDIUM_JOB_MAX_DURATION,
        ).count()
        pending_jobs_short = Job.objects.filter(
            status__lt=Status.SUBMITTING, leader_walltime__lt=settings.SHORT_JOB_MAX_DURATION
        ).order_by("created_date")[: settings.SHORT_JOB_QUEUE - short_jobs_count]
        pending_jobs_medium = Job.objects.filter(
            status__lt=Status.SUBMITTING,
            leader_walltime__gte=settings.SHORT_JOB_MAX_DURATION,
            leader_walltime__lt=settings.MEDIUM_JOB_MAX_DURATION,
        ).order_by("created_date")[: settings.MEDIUM_JOB_QUEUE - medium_jobs_count]
        pending_jobs_long = Job.objects.filter(
            status__lt=Status.SUBMITTING, leader_walltime__gte=settings.MEDIUM_JOB_MAX_DURATION
        ).order_by("created_date")[: settings.LONG_JOB_QUEUE - long_jobs_count]
        jobs_to_submit = []
        jobs_to_submit.extend(pending_jobs_short)
        jobs_to_submit.extend(pending_jobs_medium)
        jobs_to_submit.extend(pending_jobs_long)
        return jobs_to_submit
