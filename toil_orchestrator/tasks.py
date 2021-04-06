import os
import json
import logging
from datetime import timedelta
from celery import shared_task
from batch_systems.lsf_client import LSFClient
from submitter.jobsubmitter import JobSubmitter
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware, make_aware, now
from .toil_track_utils import ToilTrack
from .models import Job, Status, CommandLineToolJob
import shutil
from ridgeback.settings import MAX_RUNNING_JOBS


logger = logging.getLogger(__name__)


def get_aware_datetime(date_str):
    datetime_obj = parse_datetime(str(date_str))
    if not is_aware(datetime_obj):
        datetime_obj = make_aware(datetime_obj)
    return datetime_obj


def get_job_info_path(job_id):
    work_dir = os.path.join(settings.TOIL_WORK_DIR_ROOT, str(job_id))
    job_info_path = os.path.join(work_dir, '.run.info')
    return job_info_path


def get_message(job_obj):
    job_message = {}
    if job_obj.message:
        if type(job_obj.message) == str:
            job_message = json.loads(job_obj.message)
        else:
            job_message = job_obj.message
    return job_message


def set_message(job_obj, message_obj):
    message_str = json.dumps(message_obj, sort_keys=True, indent=1, cls=DjangoJSONEncoder)
    job_obj.message = message_str
    job_obj.save(update_fields=['message'])


def update_message_by_key(job_obj, key, value):
    message = get_message(job_obj)
    message[key] = value
    set_message(job_obj, message)


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
    update_message_by_key(job,'info','Failed to submit job')
    job.finished = now()
    job.save()


@shared_task
def submit_pending_jobs():
    jobs_running = len(Job.objects.filter(status__in=(Status.RUNNING, Status.PENDING)))
    jobs_to_submit = MAX_RUNNING_JOBS - jobs_running
    if jobs_to_submit <= 0:
        return

    job_ids = Job.objects.filter(status=Status.CREATED).order_by("created_date").values_list('pk', flat=True)[
              :jobs_to_submit]

    Job.objects.filter(pk__in=list(job_ids)).update(status=Status.PENDING)

    for job_id in job_ids:
        submit_job_to_lsf.delay(job_id)


@shared_task(bind=True,
             autoretry_for=(Exception,),
             retry_jitter=True,
             retry_backoff=360,
             retry_kwargs={"max_retries": 4},
             on_failure=on_failure_to_submit)
def submit_job_to_lsf(self, job_id):
    logger.info("Submitting job %s to lsf" % str(job_id))
    job = Job.objects.get(pk=job_id)
    submitter = JobSubmitter(str(job.id), job.app, job.inputs, job.root_dir, job.resume_job_store_location,
                             job.walltime, job.memlimit)
    external_job_id, job_store_dir, job_work_dir, job_output_dir = submitter.submit()
    logger.info("Job %s submitted to lsf with id: %s" % (str(job.id), external_job_id))
    save_job_info(str(job.id), external_job_id, job_store_dir, job_work_dir, job_output_dir)
    job.external_id = external_job_id
    job.job_store_location = job_store_dir
    job.working_dir = job_work_dir
    job.output_directory = job_output_dir
    log_path = os.path.join(job_work_dir, 'lsf.log')
    update_message_by_key(job, 'log', log_path)
    job.save(update_fields=['external_id',
                            'job_store_location',
                            'working_dir',
                            'output_directory',
                            ])


@shared_task(bind=True, max_retries=10, retry_jitter=True, retry_backoff=60)
def abort_job(self, job_id):
    logger.info("Abort job %s" % job_id)
    job = Job.objects.get(id=job_id)
    try:
        if job.status in (Status.PENDING, Status.RUNNING,):
            submitter = JobSubmitter(job_id, job.app, job.inputs, job.root_dir, job.resume_job_store_location)
            job_killed = submitter.abort(job_id)
            if job_killed:
                job.status = Status.ABORTED
                job.save()
                return
            else:
                logger.info("Failed to abort job %s" % job_id)
                raise Exception("Failed to abort job %s" % job_id)
        elif job.status == Status.CREATED:
            job.status = Status.ABORTED
            job.save()
            return
        elif job.status == Status.UNKNOWN:
            logger.info("Job aborting %s is unknown" % job_id)
            raise Exception("Job aborting %s but still not submitted" % job_id)
        else:
            logger.info("Job %s already in final state %s", job_id, job.status)
            return
    except Exception as e:
        logger.info("Error happened %s. Retrying..." % str(e))
        self.retry(exc=e, countdown=10)


@shared_task(bind=True)
def suspend_job(self, job_id):
    client = LSFClient()
    client.suspend(job_id)


@shared_task(bind=True)
def unsuspend_job(self, job_id):
    client = LSFClient()
    client.unsuspend(job_id)


def cleanup_jobs(status, time_delta):
    time_threshold = now() - timedelta(days=time_delta)
    jobs = Job.objects.filter(status__in=(status,), modified_date__lte=time_threshold, job_store_clean_up=None,
                              working_dir_clean_up=None)
    for job in jobs:
        cleanup_folders.delay(str(job.id))


@shared_task(bind=True)
def cleanup_completed_jobs(self):
    cleanup_jobs(Status.COMPLETED, settings.CLEANUP_COMPLETED_JOBS)


@shared_task(bind=True)
def cleanup_failed_jobs(self):
    cleanup_jobs(Status.FAILED, settings.CLEANUP_FAILED_JOBS)


@shared_task(bind=True)
def cleanup_folders(self, job_id, job_store=True, work_dir=True):
    logger.info("Cleaning up %s" % job_id)
    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        logger.error("Job with id:%s not found" % job_id)
        return
    if job_store:
        if clean_directory(job.job_store_location):
            job.job_store_clean_up = now()
    if work_dir:
        if clean_directory(job.working_dir):
            job.working_dir_clean_up = now()
    job.save()


def clean_directory(path):
    try:
        shutil.rmtree(path)
    except Exception as e:
        logger.error("Failed to remove folder: %s\n%s" % (path, str(e)))
        return False
    return True


@shared_task(bind=True)
def check_status_of_jobs(self):
    logger.info('Checking status of jobs on lsf')
    jobs = Job.objects.filter(
        status__in=(Status.PENDING, Status.RUNNING, Status.CREATED, Status.UNKNOWN, Status.SUSPENDED)).all()
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
        elif not job.external_id and job.status == Status.PENDING:
            continue
        elif job.external_id:
            submiter = JobSubmitter(str(job.id), job.app, job.inputs, job.root_dir, job.resume_job_store_location)
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
                        update_message_by_key(job,'info',error_message)
                else:
                    job.status = lsf_status
                    update_message_by_key(job,'info',lsf_message)
                if lsf_status != Status.PENDING:
                    if not job.started:
                        job.started = now()
                if lsf_status == Status.FAILED:
                    failed_command_line_tool_jobs = CommandLineToolJob.objects.filter(root__id__exact=job.id, status=Status.FAILED)
                    unknown_command_line_tool_jobs = CommandLineToolJob.objects.filter(root__id__exact=job.id, status=Status.UNKNOWN)
                    failed_jobs = {}
                    unknown_jobs = {}
                    for single_tool_job in failed_command_line_tool_jobs:
                        job_name = single_tool_job.job_name
                        job_id = single_tool_job.job_id
                        if job_name not in failed_jobs:
                            failed_jobs[job_name] = [job_id]
                        else:
                            failed_jobs[job_name].append(job_id)
                            failed_jobs[job_name].sort()
                    for single_tool_job in unknown_command_line_tool_jobs:
                        job_name = single_tool_job.job_name
                        job_id = single_tool_job.job_id
                        if job_name not in unknown_jobs:
                            unknown_jobs[job_name] = [job_id]
                        else:
                            unknown_jobs[job_name].append(job_id)
                            unknown_jobs[job_name].sort()
                    update_message_by_key(job,'failed_jobs',failed_jobs)
                    update_message_by_key(job,'unknown_jobs',unknown_jobs)
                    job.finished = now()
            else:
                logger.info('Job [{}], Failed to retrieve job status for job with external id {}'.format(job.id,job.external_id))
                error_message = 'Job [{}], Could not retrieve status'.format(job.id)
                update_message_by_key(job,'info',error_message)
        else:
            logger.info('Job [{}] not submitted to lsf'.format(job.id))
            job.status = Status.FAILED
            job.finished = now()
            error_message = 'Job [{}], External id not provided'.format(job.id)
            update_message_by_key(job,'info',error_message)
        job.save()


@shared_task(bind=True)
def check_status_of_command_line_jobs(self):
    jobs = Job.objects.filter(status__in=(Status.CREATED, Status.RUNNING))
    for current_job in jobs:
        if current_job.app != None:
            if 'github' in current_job.app:
                github_repo = current_job.app['github']['repository']
                if github_repo:
                    if "access" in github_repo.lower():
                        continue
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
