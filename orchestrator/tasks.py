import os
import json
import shutil
import logging
from datetime import timedelta
from celery import shared_task
from batch_systems.lsf_client import LSFClient
from django.conf import settings
from django.db import transaction
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware, make_aware, now
from .toil_track_utils import ToilTrack
from .models import Job, Status, CommandLineToolJob
from lib.memcache_lock import memcache_task_lock, memcache_lock
from submitter.factory import JobSubmitterFactory
from ridgeback.settings import MAX_RUNNING_JOBS
from orchestrator.commands import Command, CommandType
from orchestrator.exceptions import RetryException, StopException


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


def save_job_info(job_id, external_id, job_store_location, working_dir, output_directory):
    if os.path.exists(working_dir):
        job_info = {'external_id': external_id,
                    'job_store_location': job_store_location,
                    'working_dir': working_dir,
                    'output_directory': output_directory
                    }
        job_info_path = get_job_info_path(job_id)
        with open(job_info_path,'w') as job_info_file:
            json.dump(job_info, job_info_file)
    else:
        logger.error('Working directory %s does not exist', working_dir)


def on_failure_to_submit(self, exc, task_id, args, kwargs, einfo):
    logger.error('On failure to submit')
    job_id = args[0]
    logger.error('Failed to submit job: %s' % job_id)
    job = Job.objects.get(id=job_id)
    job.fail('Failed to submit job')


def suspend_job(job):
    if Status(job.status).transition(Status.SUSPENDED):
        client = LSFClient()
        if not client.suspend(job.external_id):
            raise RetryException("Failed to suspend job: %s" % str(job.id))
        job.update_status(Status.SUSPENDED)
    logger.info("Can't suspend job. Invalid transition from %s to %s for job: %s" % (
    Status(job.status).name, Status.SUSPENDED.name, str(job.id)))


def resume_job(job):
    if Status(job.status) == Status.SUSPENDED:
        client = LSFClient()
        if not client.resume(job.external_id):
            raise RetryException("Failed to resume job: %s" % str(job.id))
        job.update_status(Status.RUNNING)
        return
    logger.info(
        "Can't resume job: %s because it is in status %s, not in SUSPENDED" % (Status(job.status).name, str(job.id)))


@shared_task
@memcache_lock("rb_submit_pending_jobs")
def process_jobs():
    jobs_running = Job.objects.filter(
        status__in=(Status.SUBMITTING, Status.SUBMITTED, Status.PENDING, Status.RUNNING,)).count()
    jobs_to_submit = MAX_RUNNING_JOBS - jobs_running
    if jobs_to_submit <= 0:
        return

    jobs = Job.objects.filter(status=Status.CREATED).order_by("created_date")[
           :jobs_to_submit]

    for job in jobs:
        # Send SUBMIT commands for Jobs
        with transaction.atomic():
            if Status(job.status).transition(Status.SUBMITTING):
                job.update_status(Status.SUBMITTING)
                command_processor.delay(Command(CommandType.SUBMIT, str(job.id)).to_dict())

    status_jobs = Job.objects.filter(
        status__in=(Status.SUBMITTED, Status.PENDING, Status.RUNNING, Status.UNKNOWN,)).values_list('pk', flat=True)
    for job_id in status_jobs:
        # Send CHECK_STATUS commands for Jobs
        command_processor.delay(Command(CommandType.CHECK_STATUS_ON_LSF, job_id).to_dict())


@shared_task(bind=True)
def command_processor(self, command_dict):
    try:
        command = Command.from_dict(command_dict)
        lock_id = "job_lock_%s" % command.job_id
        with memcache_task_lock(lock_id, self.app.oid) as acquired:
            if acquired:
                try:
                    job = Job.objects.get(id=command.job_id)
                except Job.DoesNotExist:
                    return
                if command.command_type == CommandType.SUBMIT:
                    submit_job_to_lsf(job)
                elif command.command_type == CommandType.CHECK_STATUS_ON_LSF:
                    check_job_status(job)
                elif command.command_type == CommandType.ABORT:
                    abort_job(job)
                elif command.command_type == CommandType.SUSPEND:
                    suspend_job(job)
                elif command.command_type == CommandType.RESUME:
                    resume_job(job)
    except RetryException as e:
        logger.warning(
            "Command %s failed. Retrying in %s. Excaption %s" % (command_dict, self.request.retries * 5, str(e)))
        raise self.retry(exc=e, countdown=self.request.retries * 5, max_retries=5)
    except StopException as e:
        logger.error("Command %s failed. Not retrying. Excaption %s" % (command_dict, str(e)))


def submit_job_to_lsf(job):
    if Status(job.status).transition(Status.SUBMITTED):
        logger.info("Submitting job %s to lsf" % str(job.id))
        submitter = JobSubmitterFactory.factory(job.type, str(job.id), job.app, job.inputs, job.root_dir,
                                                job.resume_job_store_location, job.walltime, job.memlimit)
        external_job_id, job_store_dir, job_work_dir, job_output_dir = submitter.submit()
        logger.info("Job %s submitted to lsf with id: %s" % (str(job.id), external_job_id))
        job.submit_to_lsf(external_job_id, job_store_dir, job_work_dir, job_output_dir, os.path.join(job_work_dir, 'lsf.log'))
        # Keeping this for debuging purposes
        save_job_info(str(job.id), external_job_id, job_store_dir, job_work_dir, job_output_dir)


def _complete(job, outputs):
    job.complete(outputs)


def _fail(job, error_message=""):
    failed_command_line_tool_jobs = CommandLineToolJob.objects.filter(root__id__exact=job.id,
                                                                      status=Status.FAILED)
    unknown_command_line_tool_jobs = CommandLineToolJob.objects.filter(root__id__exact=job.id,
                                                                       status=Status.UNKNOWN)
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
    job.fail(error_message, failed_jobs, unknown_jobs)


def check_job_status(job):
    if job.status not in (Status.SUBMITTED, Status.PENDING, Status.RUNNING, Status.UNKNOWN,):
        return
    submiter = JobSubmitterFactory.factory(job.type, str(job.id), job.app, job.inputs, job.root_dir,
                                           job.resume_job_store_location)
    try:
        lsf_status, lsf_message = submiter.status(job.external_id)
    except Exception:
        # If failed to check status on LSF retry
        raise RetryException('Failed to fetch status for job %s' % (str(job.id)))
    if Status(job.status).transition(lsf_status):
        if lsf_status in (Status.SUBMITTED, Status.PENDING, Status.RUNNING, Status.UNKNOWN,):
            job.update_status(lsf_status)

        elif lsf_status in (Status.COMPLETED,):
            outputs, error_message = submiter.get_outputs()
            if outputs:
                _complete(job, outputs)
            else:
                _fail(job, error_message)

        elif lsf_status in (Status.FAILED,):
            _fail(job, lsf_message)

    else:
        logger.warning('Invalid transition %s to %s' % (Status(job.status).name, Status(lsf_status).name))
        raise StopException('Invalid transition %s to %s' % (Status(job.status).name, Status(lsf_status).name))


def abort_job(job):
    if Status(job.status).transition(Status.ABORTED):
        logger.info("Abort job %s" % str(job.id))
        if job.status in (Status.SUBMITTED, Status.PENDING, Status.RUNNING, Status.SUSPENDED, Status.UNKNOWN):
            submitter = JobSubmitterFactory.factory(job.type, str(job.id), job.app, job.inputs, job.root_dir,
                                                    job.resume_job_store_location)
            job_killed = submitter.abort(job.external_id)
            if not job_killed:
                raise RetryException("Failed to abort job %s" % str(job.id))
        job.abort()


# Cleaning jobs


@shared_task(bind=True)
def cleanup_completed_jobs(self):
    cleanup_jobs(Status.COMPLETED, settings.CLEANUP_COMPLETED_JOBS)


@shared_task(bind=True)
def cleanup_failed_jobs(self):
    cleanup_jobs(Status.FAILED, settings.CLEANUP_FAILED_JOBS)


def cleanup_jobs(status, time_delta):
    time_threshold = now() - timedelta(days=time_delta)
    jobs = Job.objects.filter(status__in=(status,), modified_date__lte=time_threshold, job_store_clean_up=None,
                              working_dir_clean_up=None)
    for job in jobs:
        cleanup_folders.delay(str(job.id))


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
            track_cache = {'current_jobs': [], 'jobs_path': {}, 'jobs': {}, 'worker_jobs': {}}
            job_updated = True
        jobstore_path = current_job.job_store_location
        workdir_path = current_job.working_dir
        toil_track_obj = ToilTrack(jobstore_path, workdir_path, False, 0, False, None)
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
    commandLineToolJobs = CommandLineToolJob.objects.filter(status__in=(Status.RUNNING, Status.PENDING))
    for single_command_line_tool in commandLineToolJobs:
        if single_command_line_tool.root.status != Status.RUNNING:
            single_command_line_tool.__dict__['status'] = Status.UNKNOWN
            single_command_line_tool.save()
