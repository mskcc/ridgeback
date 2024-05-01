import os
import json
import shutil
import logging
import tempfile
from datetime import timedelta
from celery import shared_task
from django.conf import settings
from django.utils.timezone import now
from .models import Job, Status, CommandLineToolJob
from lib.memcache_lock import memcache_task_lock, memcache_lock
from submitter.factory import JobSubmitterFactory
from orchestrator.scheduler import Scheduler
from orchestrator.commands import Command, CommandType
from orchestrator.exceptions import RetryException, StopException


logger = logging.getLogger(__name__)


def get_job_info_path(job_id):
    job = Job.objects.get(id=job_id)
    work_dir = os.path.join(settings.PIPELINE_CONFIG[job.metadata["pipeline_name"]]["WORK_DIR_ROOT"], str(job_id))
    job_info_path = os.path.join(work_dir, ".run.info")
    return job_info_path


def save_job_info(job_id, external_id, job_store_location, working_dir, output_directory, metadata={}):
    if os.path.exists(working_dir):
        job_info = {
            "external_id": external_id,
            "job_store_location": job_store_location,
            "working_dir": working_dir,
            "output_directory": output_directory,
        }
        job_info.update(metadata)
        job_info_path = get_job_info_path(job_id)
        with open(job_info_path, "w") as job_info_file:
            json.dump({"meta": "run_info"}, job_info_file)
            job_info_file.write("\n")
        with open(job_info_path, "a") as job_info_file:
            json.dump(job_info, job_info_file)
    else:
        logger.error("Working directory %s does not exist", working_dir)


def on_failure_to_submit(self, exc, task_id, args, kwargs, einfo):
    logger.error("On failure to submit")
    job_id = args[0]
    logger.error("Failed to submit job: %s" % job_id)
    job = Job.objects.get(id=job_id)
    job.fail("Failed to submit job")


def suspend_job(job):
    if Status(job.status).transition(Status.SUSPENDED):
        submitter = JobSubmitterFactory.factory(
            job.type,
            str(job.id),
            job.app,
            job.inputs,
            job.root_dir,
            job.resume_job_store_location,
            log_dir=job.log_dir,
            app_name=job.metadata["pipeline_name"],
        )
        job_suspended = submitter.suspend()
        if not job_suspended:
            raise RetryException("Failed to suspend job: %s" % str(job.id))
        job.update_status(Status.SUSPENDED)
        return


def resume_job(job):
    if Status(job.status) == Status.SUSPENDED:
        submitter = JobSubmitterFactory.factory(
            job.type,
            str(job.id),
            job.app,
            job.inputs,
            job.root_dir,
            job.resume_job_store_location,
            log_dir=job.log_dir,
            app_name=job.metadata["pipeline_name"],
        )
        job_resumed = submitter.resume()
        if not job_resumed:
            raise RetryException("Failed to resume job: %s" % str(job.id))
        job.update_status(Status.RUNNING)
        return
    logger.info(
        "Can't resume job: %s because it is in status %s, not in SUSPENDED" % (Status(job.status).name, str(job.id))
    )


@shared_task
@memcache_lock("rb_submit_pending_jobs")
def process_jobs():
    status_jobs = Job.objects.filter(
        status__in=(
            Status.SUBMITTED,
            Status.PENDING,
            Status.RUNNING,
            Status.UNKNOWN,
        )
    ).values_list("pk", flat=True)
    for job_id in status_jobs:
        # Send CHECK_STATUS commands for Jobs
        command_processor.delay(Command(CommandType.CHECK_STATUS_ON_LSF, str(job_id)).to_dict())

    jobs = Scheduler.get_jobs_to_submit()

    for job in jobs:
        # Send SUBMIT commands for Jobs
        if Status(job.status).transition(Status.SUBMITTING):
            job.update_status(Status.SUBMITTING)
            command_processor.delay(Command(CommandType.SUBMIT, str(job.id)).to_dict())


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
                    logger.info("SUBMIT command for job %s" % command.job_id)
                    submit_job_to_lsf(job)
                elif command.command_type == CommandType.CHECK_STATUS_ON_LSF:
                    logger.info("CHECK_STATUS_ON_LSF command for job %s" % command.job_id)
                    check_job_status(job)
                elif command.command_type == CommandType.CHECK_COMMAND_LINE_STATUS:
                    logger.info("CHECK_COMMAND_LINE_STATUS command for job %s" % command.job_id)
                    check_status_of_command_line_jobs(job)
                elif command.command_type == CommandType.TERMINATE:
                    logger.info("TERMINATE command for job %s" % command.job_id)
                    terminate_job(job)
                elif command.command_type == CommandType.SUSPEND:
                    logger.info("SUSPEND command for job %s" % command.job_id)
                    suspend_job(job)
                elif command.command_type == CommandType.RESUME:
                    logger.info("RESUME command for job %s" % command.job_id)
                    resume_job(job)
                elif command.command_type == CommandType.SET_OUTPUT_PERMISSION:
                    logger.info("Setting output permission for job %s" % command.job_id)
                    set_permission(job)

            else:
                logger.info("Job lock not acquired for job: %s" % command.job_id)
                self.retry()
    except RetryException as e:
        logger.info(
            "Command %s failed. Retrying in %s. Excaption %s" % (command_dict, self.request.retries * 5, str(e))
        )
        raise self.retry(exc=e, countdown=self.request.retries * 5, max_retries=5)
    except StopException as e:
        logger.error("Command %s failed. Not retrying. Excaption %s" % (command_dict, str(e)))


def submit_job_to_lsf(job):
    if Status(job.status).transition(Status.SUBMITTED):
        logger.info("Submitting job %s to lsf" % str(job.id))
        submitter = JobSubmitterFactory.factory(
            job.type,
            str(job.id),
            job.app,
            job.inputs,
            job.root_dir,
            job.resume_job_store_location,
            job.walltime,
            job.memlimit,
            log_dir=job.log_dir,
            app_name=job.metadata["pipeline_name"],
        )
        (
            external_job_id,
            job_store_dir,
            job_work_dir,
            job_output_dir,
        ) = submitter.submit()
        logger.info("Job %s submitted to lsf with id: %s" % (str(job.id), external_job_id))
        job.submit_to_lsf(
            external_job_id,
            job_store_dir,
            job_work_dir,
            job_output_dir,
            os.path.join(job_work_dir, "lsf.log"),
        )
        # Keeping this for debuging purposes
        save_job_info(str(job.id), external_job_id, job_store_dir, job_work_dir, job_output_dir, job.metadata)


def _complete(job, outputs):
    job.complete(outputs)
    command_processor.delay(Command(CommandType.SET_OUTPUT_PERMISSION, str(job.id)).to_dict())


def _fail(job, error_message=""):
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
    job.fail(error_message, failed_jobs, unknown_jobs)


def check_job_status(job):
    if job.status not in (
        Status.SUBMITTED,
        Status.PENDING,
        Status.RUNNING,
        Status.UNKNOWN,
    ):
        return
    submiter = JobSubmitterFactory.factory(
        job.type,
        str(job.id),
        job.app,
        job.inputs,
        job.root_dir,
        job.resume_job_store_location,
        log_dir=job.log_dir,
        app_name=job.metadata["pipeline_name"],
    )
    try:
        lsf_status, lsf_message = submiter.status(job.external_id)
    except Exception:
        # If failed to check status on LSF retry
        raise RetryException("Failed to fetch status for job %s" % (str(job.id)))
    if Status(job.status).transition(lsf_status):
        if lsf_status in (
            Status.SUBMITTED,
            Status.PENDING,
            Status.RUNNING,
            Status.UNKNOWN,
        ):
            job.update_status(lsf_status)

        elif lsf_status in (Status.COMPLETED,):
            outputs, error_message = submiter.get_outputs()
            if outputs:
                _complete(job, outputs)
            else:
                _fail(job, error_message)

        elif lsf_status in (Status.FAILED,):
            _fail(job, lsf_message)

        command_processor.delay(Command(CommandType.CHECK_COMMAND_LINE_STATUS, str(job.id)).to_dict())

    else:
        raise StopException("Invalid transition %s to %s" % (Status(job.status).name, Status(lsf_status).name))


def terminate_job(job):
    if Status(job.status).transition(Status.TERMINATED):
        logger.info("TERMINATE job %s" % str(job.id))
        if job.status in (
            Status.SUBMITTED,
            Status.PENDING,
            Status.RUNNING,
            Status.SUSPENDED,
            Status.UNKNOWN,
        ):
            submitter = JobSubmitterFactory.factory(
                job.type,
                str(job.id),
                job.app,
                job.inputs,
                job.root_dir,
                job.resume_job_store_location,
                log_dir=job.log_dir,
                app_name=job.metadata["pipeline_name"],
            )
            job_killed = submitter.terminate()
            if not job_killed:
                raise RetryException("Failed to TERMINATE job %s" % str(job.id))
        job.terminate()


def set_permission(job):
    failed_to_set = None
    dirs = job.root_dir.replace(job.base_dir, "").split("/")
    permission_str = job.root_permission
    permissions_dir = job.base_dir
    for d in dirs:
        failed_to_set = False
        permissions_dir = "/".join([permissions_dir, d]).replace("//", "/")
        try:
            permission_octal = int(permission_str, 8)
        except Exception:
            raise TypeError("Could not convert %s to permission octal" % str(permission_str))
        try:
            os.chmod(permissions_dir, permission_octal)
            for root, dirs, files in os.walk(permissions_dir):
                for single_dir in dirs:
                    if oct(os.lstat(os.path.join(root, single_dir)).st_mode)[-3:] != permission_octal:
                        logger.info(f"Setting permissions for {os.path.join(root, single_dir)}")
                        os.chmod(os.path.join(root, single_dir), permission_octal)
                for single_file in files:
                    if oct(os.lstat(os.path.join(root, single_file)).st_mode)[-3:] != permission_octal:
                        logger.info(f"Setting permissions for {os.path.join(root, single_file)}")
                        os.chmod(os.path.join(root, single_file), permission_octal)
        except Exception:
            logger.error(f"Failed to set permissions for directory {permissions_dir}")
            failed_to_set = True
            continue
        else:
            logger.info(f"Permissions set for directory {permissions_dir}")
            break
    if failed_to_set:
        raise RuntimeError("Failed to change permission of directory %s" % permissions_dir)


# Cleaning jobs


@shared_task(bind=True)
def full_cleanup_jobs(self):
    cleanup_jobs(Status.COMPLETED, settings.FULL_CLEANUP_JOBS)
    cleanup_jobs(Status.FAILED, settings.FULL_CLEANUP_JOBS)


@shared_task(bind=True)
def cleanup_completed_jobs(self):
    cleanup_jobs(Status.COMPLETED, settings.CLEANUP_COMPLETED_JOBS, exclude=["input.json", "lsf.log"])


@shared_task(bind=True)
def cleanup_failed_jobs(self):
    cleanup_jobs(Status.FAILED, settings.CLEANUP_FAILED_JOBS, exclude=["input.json", "lsf.log"])


@shared_task(bind=True)
def cleanup_TERMINATED_jobs(self):
    cleanup_jobs(Status.TERMINATED, settings.CLEANUP_TERMINATED_JOBS, exclude=["input.json", "lsf.log"])


def cleanup_jobs(status, time_delta, exclude=[]):
    time_threshold = now() - timedelta(days=time_delta)
    jobs = Job.objects.filter(
        status__in=(status,),
        finished__lte=time_threshold,
        job_store_clean_up__isnull=True,
        working_dir_clean_up__isnull=True,
    )
    for job in jobs:
        cleanup_folders.delay(str(job.id), exclude=exclude)


@shared_task(bind=True)
def cleanup_folders(self, job_id, exclude, job_store=True, work_dir=True):
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
        if clean_directory(job.working_dir, exclude=exclude):
            job.working_dir_clean_up = now()
    job.save()


def clean_directory(path, exclude=[]):
    with tempfile.TemporaryDirectory() as tmpdirname:
        for f in exclude:
            src = os.path.join(path, f)
            if os.path.exists(src):
                shutil.copy(src, tmpdirname)
        try:
            shutil.rmtree(path)
        except Exception as e:
            logger.error("Failed to remove folder: %s\n%s" % (path, str(e)))
            return False
        """
        Return excluded files to previous location
        """
        if exclude:
            os.makedirs(path, exist_ok=True)
            for f in exclude:
                src = os.path.join(tmpdirname, f)
                if os.path.exists(src):
                    shutil.copy(src, path)
        return True


# Check CommandLineJob statuses


def update_command_line_jobs(command_line_jobs, root):
    for job_id, job_obj in command_line_jobs.items():
        try:
            command_line_job = CommandLineToolJob.objects.get(job_id=job_id)
            command_line_job.status = job_obj["status"]
            command_line_job.started = job_obj["started"]
            command_line_job.submitted = job_obj["submitted"]
            command_line_job.finished = job_obj["finished"]
            command_line_job.details = job_obj["details"]
            command_line_job.save()
        except CommandLineToolJob.DoesNotExist:
            CommandLineToolJob.objects.create(
                root=root,
                job_id=job_id,
                status=job_obj["status"],
                started=job_obj["started"],
                submitted=job_obj["submitted"],
                finished=job_obj["finished"],
                job_name=job_obj["name"],
                details=job_obj["details"],
            )


def check_status_of_command_line_jobs(job):
    submiter = JobSubmitterFactory.factory(
        job.type,
        str(job.id),
        job.app,
        job.inputs,
        job.root_dir,
        job.resume_job_store_location,
        log_dir=job.log_dir,
        app_name=job.metadata["pipeline_name"],
    )
    track_cache_str = job.track_cache
    command_line_status = submiter.get_commandline_status(track_cache_str)
    command_line_jobs = {}
    if command_line_status:
        command_line_jobs_str, new_track_cache_str = command_line_status
        new_track_cache = json.loads(new_track_cache_str)
        command_line_jobs = json.loads(command_line_jobs_str)
        job.track_cache = new_track_cache
        job.save()
    if command_line_jobs:
        update_command_line_jobs(command_line_jobs, job)
