import os
import logging
from .models import Job, Status, CommandLineToolJob
from .toil_track_utils import ToilTrack
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
        submiter = JobSubmitter(str(job.id), job.app, job.inputs)
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

@shared_task(bind=True)
def check_status_of_command_line_jobs(self):
    jobs = Job.objects.filter(status__in=(Status.CREATED, Status.RUNNING))
    for current_job in jobs:
        track_cache = current_job.track_cache
        if not track_cache:
            track_cache = { 'current_jobs': [], 'jobs_path': {}, 'jobs': {}, 'worker_jobs': {} }
        jobstore_path = current_job.job_store_location
        workdir_path = current_job.working_dir
        roslin_track = ToilTrack(jobstore_path,workdir_path,False,0,False,None)
        cache_current_jobs = track_cache.current_jobs
        cache_jobs_path = track_cache.jobs_path
        cache_jobs = track_cache.jobs
        cache_worker_jobs = track_cache.worker_jobs
        roslin_track = ToilTrack(jobstore_path,workdir_path,False,0,False,None)
        roslin_track.current_jobs = cache_current_jobs
        roslin_track.jobs_path = cache_jobs_path
        roslin_track.jobs = cache_jobs
        roslin_track.worker_jobs = cache_worker_jobs
        job_status = roslin_track.check_status()
        track_cache.current_jobs = roslin_track.current_jobs
        track_cache.jobs_path = roslin_track.jobs_path
        track_cache.jobs = roslin_track.jobs
        track_cache.worker_jobs = roslin_track.worker_jobs
        current_job.track_cache = track_cache
        current_job.save()
        for single_command_line_tool in job_status:
            single_tool_module = CommandLineToolJob(root=current_job,status=single_command_line_tool['status'], started=single_command_line_tool['started'], submitted=single_command_line_tool['submitted'],finished=single_command_line_tool['finished'],job_name=single_command_line_tool['job_name'],job_id=single_command_line_tool['job_id'],details=single_command_line_tool['details'])
            single_tool_module.save()
