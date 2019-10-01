import logging
from .models import Job, Status
from celery import shared_task


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def submit_jobs_to_lsf(self):
    logger.info("Submitting jobs to lsf")
    jobs = Job.objects.filter(status=Status.CREATED)
    for job in jobs:
        try:
            logger.info("Submitting job %s to lsf" % job.id)
        except Exception as e:
            self.retry(exc=e, countdown=10)


@shared_task(bind=True)
def check_status_of_jobs(self):
    pass
