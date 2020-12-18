import os
import logging
from .models import Job, Status, CommandLineToolJob
from .toil_track_utils import ToilTrack
from celery import shared_task
from submitter.factory import JobSubmitterFactory
import json
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware, make_aware, now
import shutil


logger = logging.getLogger(__name__)


def get_aware_datetime(date_str):
    datetime_obj = parse_datetime(str(date_str))
    if not is_aware(datetime_obj):
        datetime_obj = make_aware(datetime_obj)
    return datetime_obj


def get_job_info_path(job_id):
    work_dir = os.path.join(settings.TOIL_WORK_DIR_ROOT, str(job_id))
    job_info_path = os.path.join(work_dir,'.run.info')
    return job_info_path


def save_job_info(job_id, external_id, job_store_location, working_dir, output_directory):
    if os.path.exists(working_dir):
        job_info = {'external_id': external_id,
                    'job_store_location': job_store_location,
                    'working_dir': working_dir,
                    'output_directory': output_directory
                    }
        job_info_path = get_job_info_path(job_id)
        with open(job_info_path,'w') as job_info_file:
            json.dump(job_info,job_info_file)
    else:
        logger.error('Working directory %s does not exist', working_dir)


def on_failure_to_submit(self, exc, task_id, args, kwargs, einfo):
    logger.error('On failure to submit')
    job_id = args[0]
    logger.error('Failed to submit job: %s' % job_id)
    job = Job.objects.get(id=job_id)
    job.status = Status.FAILED
    job.finished = now()
    job.save()
    logger.error('Job Saved')


@shared_task(bind=True, max_retries=3, on_failure=on_failure_to_submit)
def submit_jobs_to_lsf(self, job_id):
    logger.info("Submitting jobs to lsf")
    job = Job.objects.get(id=job_id)
    if job.status == Status.ABORTING:
        return
    try:
        logger.info("Submitting job %s to lsf" % job.id)
        submitter = JobSubmitterFactory.factory(job.type, job_id, job.app, job.inputs, job.root_dir,
                                                job.resume_job_store_location)
        print(submitter)
        external_job_id, job_store_dir, job_work_dir, job_output_dir = submitter.submit()
        logger.info("Job %s submitted to lsf with id: %s" % (job_id, external_job_id))
        save_job_info(job_id, external_job_id, job_store_dir, job_work_dir, job_output_dir)
        job.external_id = external_job_id
        job.job_store_location = job_store_dir
        job.working_dir = job_work_dir
        job.output_directory = job_output_dir
        job.status = Status.PENDING
        job.save()
    except Exception as e:
        logger.info("Failed to submit job %s\n%s" % (job_id, str(e)))
        self.retry(exc=e, countdown=10)


def terminate_job(self, job_id):
    logger.info("Submitting jobs to lsf")


@shared_task(bind=True)
def cleanup_folder(self,path, job_id,is_jobstore):
    logger.info("Cleaning up %s" % path)
    job_obj_list = Job.objects.filter(id__exact=job_id)
    job_obj = None
    if len(job_obj_list) > 0:
        if job_obj_list[0] != None:
            job_obj = job_obj_list[0]
    try:
        shutil.rmtree(path)
        logger.info("Cleaning of %s successful" % path)
        if is_jobstore:
            if job_obj != None:
                job_obj.job_store_clean_up = now()
                job_obj.save()
    except Exception as e:
        error_message = "Failed to remove folder: %s\n%s" % (path,str(e))
        logger.info(error_message)


@shared_task(bind=True)
def check_status_of_jobs(self):
    logger.info('Checking status of jobs on lsf')
    jobs = Job.objects.filter(status__in=(Status.PENDING, Status.RUNNING, Status.CREATED, Status.UNKNOWN)).all()
    for job in jobs:
        if job.status == Status.CREATED:
            job_info_path = get_job_info_path(job.id)
            if os.path.exists(job_info_path):
                try:
                    with open(job_info_path) as job_info_file:
                        job_info_data = json.load(job_info_file)
                    job.external_id = job_info_data['external_id']
                    job.job_store_location = job_info_data['job_store_location']
                    job.working_dir = job_info_data['working_dir']
                    job.output_directory = job_info_data['output_directory']
                    job.status = Status.PENDING
                    job.submitted = now()
                except Exception as e:
                    error_message = "Failed to update job %s from file: %s\n%s" % (job.id, job_info_path,str(e))
                    logger.info(error_message)
        elif job.external_id:
            submiter = JobSubmitterFactory.factory(str(job.id), job.app, job.inputs, job.root_dir,
                                                   job.resume_job_store_location)
            lsf_status_info = submiter.status(job.external_id)
            if lsf_status_info:
                lsf_status, lsf_message = lsf_status_info
                if lsf_status == Status.COMPLETED:
                    outputs, error_message = submiter.get_outputs()
                    if outputs:
                        job.track_cache = None
                        job.outputs = outputs
                        job.status = lsf_status
                        job.finished = now()
                    if error_message:
                        job.message = error_message
                else:
                    job.status = lsf_status
                    job.message = lsf_message
                if lsf_status != Status.PENDING:
                    if not job.submitted:
                        job.submitted = now()
                if lsf_status == Status.FAILED:
                    job.finished = now()
            else:
                logger.info('Job [{}], Failed to retrieve job status for job with external id {}'.format(job.id,
                                                                                                         job.external_id))
                job.message = 'Job [{}], Could not retrieve status'.format(job.id)
        else:
            logger.info('Job [{}] not submitted to lsf'.format(job.id))
            job.status = Status.FAILED
            job.finished = now()
            job.message = 'Job [{}], External id not provided'.format(job.id)
        job.save()


@shared_task(bind=True)
def check_status_of_command_line_jobs(self):
    jobs = Job.objects.filter(status__in=(Status.CREATED, Status.RUNNING))
    for current_job in jobs:
        current_job_str = current_job.track_cache
        job_updated = False
        if current_job_str:
            track_cache = json.loads(current_job_str)
        else:
            track_cache = { 'current_jobs': [], 'jobs_path': {}, 'jobs': {}, 'worker_jobs': {} }
            job_updated = True
        jobstore_path = current_job.job_store_location
        workdir_path = current_job.working_dir
        toil_track_obj = ToilTrack(jobstore_path,workdir_path,False,0,False,None)
        cache_current_jobs = track_cache['current_jobs']
        cache_jobs_path = track_cache['jobs_path']
        cache_jobs = track_cache['jobs']
        cache_worker_jobs = track_cache['worker_jobs']
        toil_track_obj.current_jobs = cache_current_jobs
        toil_track_obj.jobs_path = cache_jobs_path
        toil_track_obj.jobs = cache_jobs
        toil_track_obj.worker_jobs = cache_worker_jobs
        job_status = toil_track_obj.check_status()
        if toil_track_obj.current_jobs != track_cache['current_jobs']:
            track_cache['current_jobs'] = toil_track_obj.current_jobs
            job_updated = True
        if toil_track_obj.jobs_path != track_cache['jobs_path']:
            track_cache['jobs_path'] = toil_track_obj.jobs_path
            job_updated = True
        if toil_track_obj.jobs != track_cache['jobs']:
            track_cache['jobs'] = toil_track_obj.jobs
            job_updated = True
        if toil_track_obj.worker_jobs != track_cache['worker_jobs']:
            track_cache['worker_jobs'] = toil_track_obj.worker_jobs
            job_updated = True
        if job_updated:
            current_job.track_cache = json.dumps(track_cache,sort_keys=True,indent=1,cls=DjangoJSONEncoder)
            current_job.save()
        for single_command_line_tool in job_status:
            commandLineToolJobs = CommandLineToolJob.objects.filter(job_id__exact=single_command_line_tool['id'])
            finished = single_command_line_tool['finished']
            started = single_command_line_tool['started']
            submitted = single_command_line_tool['submitted']
            status = single_command_line_tool['status']
            details = single_command_line_tool['details']
            already_exists = False
            updated = False
            single_tool_module = None
            if len(commandLineToolJobs) != 0:
                if commandLineToolJobs[0] != None:
                    already_exists = True
                    single_tool_module = commandLineToolJobs[0]
                    if single_tool_module.status != Status.COMPLETED and single_tool_module != Status.FAILED:
                        keys_to_modify = ['started', 'submitted', 'finished', 'status', 'details']
                        for single_key in keys_to_modify:
                            key_value = single_command_line_tool[single_key]
                            if key_value:
                                if key_value != single_tool_module.__dict__[single_key]:
                                    if single_key == 'details':
                                        for single_detail_key in key_value:
                                            single_detail_value = key_value[single_detail_key]
                                            if single_detail_value != None:
                                                old_value = None
                                                if single_detail_key in single_tool_module.__dict__[single_key]:
                                                    old_value = single_tool_module.__dict__[single_key][
                                                        single_detail_key]
                                                if single_detail_key in ['job_cpu', 'job_memory']:
                                                    if old_value:
                                                        last_record = old_value[-1]
                                                        if last_record[1] != single_detail_value:
                                                            new_record = (str(now()), single_detail_value)
                                                            single_tool_module.__dict__[single_key][
                                                                single_detail_key].append(new_record)
                                                            updated = True
                                                    else:
                                                        new_record = (str(now()), single_detail_value)
                                                        single_tool_module.__dict__[single_key][single_detail_key] = [
                                                            new_record]
                                                        updated = True
                                                else:
                                                    if old_value != single_detail_value:
                                                        single_tool_module.__dict__[single_key][
                                                            single_detail_key] = single_detail_value
                                                        updated = True
                                    else:
                                        if single_key in ['started', 'submitted', 'finished']:
                                            if single_tool_module.__dict__[single_key] != None:
                                                continue
                                                if get_aware_datetime(
                                                        single_tool_module.__dict__[single_key]) == get_aware_datetime(
                                                        key_value):
                                                    continue
                                        single_tool_module.__dict__[single_key] = key_value
                                        updated = True
            if not already_exists:
                if details:
                    for single_detail_key in ['job_cpu', 'job_memory']:
                        if single_detail_key in details:
                            single_detail_value = details[single_detail_key]
                            if single_detail_value:
                                new_record = (str(now()),single_detail_value)
                                details[single_detail_key] = [new_record]
                single_tool_module = CommandLineToolJob(root=current_job, status=status, started=started,
                                                        submitted=submitted, finished=finished,
                                                        job_name=single_command_line_tool['name'],
                                                        job_id=single_command_line_tool['id'], details=details)
                updated = True
            if updated:
                single_tool_module.save()
    commandLineToolJobs = CommandLineToolJob.objects.filter(status__in=(Status.RUNNING,Status.PENDING))
    for single_command_line_tool in commandLineToolJobs:
        if single_command_line_tool.root.status != Status.RUNNING:
            single_command_line_tool.__dict__['status'] = Status.UNKNOWN
            single_command_line_tool.save()
