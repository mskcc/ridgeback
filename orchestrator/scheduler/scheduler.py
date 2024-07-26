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
        skip_the_queue_jobs_count = Job.objects.filter(
            metadata__pipeline_name__in=settings.SKIP_THE_QUEUE_JOBS,
            status__gte=Status.SUBMITTING,
            status__lt=Status.COMPLETED,
            walltime__gte=settings.MEDIUM_JOB_MAX_DURATION,
        ).count()
        short_jobs_count = Job.objects.filter(
            status__gte=Status.SUBMITTING,
            status__lt=Status.COMPLETED,
            walltime__lt=settings.SHORT_JOB_MAX_DURATION,
        ).count()
        medium_jobs_count = Job.objects.filter(
            status__gte=Status.SUBMITTING,
            status__lt=Status.COMPLETED,
            walltime__gte=settings.SHORT_JOB_MAX_DURATION,
            walltime__lt=settings.MEDIUM_JOB_MAX_DURATION,
        ).count()
        long_jobs_count = Job.objects.filter(
            status__gte=Status.SUBMITTING,
            status__lt=Status.COMPLETED,
            walltime__gte=settings.MEDIUM_JOB_MAX_DURATION,
        ).exclude(metadata__pipeline_name__in=settings.SKIP_THE_QUEUE_JOBS).count()
        pending_jobs_short = Job.objects.filter(
            status__lt=Status.SUBMITTING, walltime__lt=settings.SHORT_JOB_MAX_DURATION
        ).order_by("created_date")[: max(settings.SHORT_JOB_QUEUE - short_jobs_count, 0)]
        pending_jobs_medium = Job.objects.filter(
            status__lt=Status.SUBMITTING,
            walltime__gte=settings.SHORT_JOB_MAX_DURATION,
            walltime__lt=settings.MEDIUM_JOB_MAX_DURATION,
        ).order_by("created_date")[: max(settings.MEDIUM_JOB_QUEUE - medium_jobs_count, 0)]
        total_long_jobs_count = skip_the_queue_jobs_count + long_jobs_count
        pending_jobs_long = (
            Job.objects.filter(status__lt=Status.SUBMITTING, walltime__gte=settings.MEDIUM_JOB_MAX_DURATION)
            .order_by("created_date")
            .exclude(metadata__pipeline_name__in=settings.SKIP_THE_QUEUE_JOBS)[
                : max(settings.LONG_JOB_QUEUE - total_long_jobs_count, 0)
            ]
        )
        jobs_to_submit = []
        # Add Skip the queue jobs
        skip_the_queue = Job.objects.filter(
            metadata__pipeline_name__in=settings.SKIP_THE_QUEUE_JOBS,
            walltime__gte=settings.MEDIUM_JOB_MAX_DURATION,
            status__lt=Status.SUBMITTING,
        )
        if skip_the_queue:
            jobs_to_submit.extend(skip_the_queue)
        # _______________________________________________________________
        jobs_to_submit.extend(pending_jobs_short)
        jobs_to_submit.extend(pending_jobs_medium)
        jobs_to_submit.extend(pending_jobs_long)
        return jobs_to_submit
