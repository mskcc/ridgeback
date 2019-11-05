import os
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
        submitter = JobSubmitter(job_id, job.app, job.inputs, job.root_dir)
        external_job_id, job_store_dir, job_work_dir = submitter.submit()
        logger.info("Job %s submitted to lsf with id: %s" % (job_id, external_job_id))
        job.external_id = external_job_id
        job.job_store_location = job_store_dir
        job.working_dir = job_work_dir
        job.output_directory = os.path.join(job_work_dir, 'outputs')
        job.status = Status.PENDING
        job.save()
    except Exception as e:
        self.retry(exc=e, countdown=10)


@shared_task(bind=True)
def check_status_of_jobs(self):
    logger.info('Checking status of jobs on lsf')
    jobs = Job.objects.filter(status__in=(Status.PENDING, Status.CREATED, Status.RUNNING)).all()
    for job in jobs:
        submiter = JobSubmitter(str(job.id), job.app, job.inputs, job.root_dir)
        if job.external_id:
            lsf_status = submiter.status(job.external_id)
            if lsf_status == 'PEND':
                job.status = Status.PENDING
            elif lsf_status == 'RUN':
                job.status = Status.RUNNING
            elif lsf_status == 'DONE':
                job.status = Status.COMPLETED
                outputs = submiter.get_outputs()
                job.outputs = outputs
            else:
                job.status = Status.FAILED
                job.outputs = {'error': 'LSF status %s' % lsf_status}
            job.save()
        else:
            logger.info('Job %s not submitted to lsf' % str(job.id))
