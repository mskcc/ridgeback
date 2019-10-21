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
        external_job_id, job_store_dir, job_work_dir = submitter.submit()
        logger.info("Job %s submitted to lsf with id: %s" % (job_id, external_job_id))
        job.external_id = external_job_id
        job.job_store_location = job_store_dir
        job.working_dir = job_work_dir
        job.status = Status.PENDING
        job.save()
    except Exception as e:
        self.retry(exc=e, countdown=10)


@shared_task(bind=True)
def check_status_of_jobs(self):
    pass
