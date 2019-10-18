import logging
from .models import Job, Status
from celery import shared_task
from submitter.jobsubmitter import JobSubmitter


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def submit_jobs_to_lsf(self, job_id):
    logger.info("Submitting jobs to lsf")
    job = Job.objects.get(id=job_id)
    try:
        logger.info("Submitting job %s to lsf" % job.id)
        submitter = JobSubmitter(job_id, job.app, job.inputs)
        job_id = submitter.submit()

    except Exception as e:
        self.retry(exc=e, countdown=10)


@shared_task(bind=True)
def check_status_of_jobs(self):
    pass
