import os
import logging
from .models import Job, Status, CommandLineToolJob
from .toil_track_utils import ToilTrack
from celery import shared_task
from submitter.jobsubmitter import JobSubmitter
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware, make_aware, now


logger = logging.getLogger(__name__)


def get_aware_datetime(date_str):
    datetime_obj = parse_datetime(str(date_str))
    if not is_aware(datetime_obj):
        datetime_obj = make_aware(datetime_obj)
    return datetime_obj


def on_failure_to_submit(self, exc, task_id, args, kwargs, einfo):
    job_id = args[0]
    logger.error('Failed to submit job: %s' % job_id)
    job = Job.objects.get(id=job_id)
    job.status = Status.FAILED
    job.save()


def submit_jobs_to_lsf(job_id):
    logger.info("Submitting jobs to lsf")
    print("Submit jobs 1")
    job = Job.objects.get(id=job_id)
    try:
        print("Submit jobs 2", job.app)
        logger.info("Submitting job %s to lsf" % job.id)
        submitter = JobSubmitter(job_id, job.app, job.inputs, job.root_dir)
        print("Submit jobs 3")
        external_job_id, job_store_dir, job_work_dir = submitter.submit()
        logger.info("Job %s submitted to lsf with id: %s" % (job_id, external_job_id))
        print("Submit jobs 4")
        job.external_id = external_job_id
        job.job_store_location = job_store_dir
        job.working_dir = job_work_dir
        print("Submit jobs 5")
        job.output_directory = os.path.join(job_work_dir, 'outputs')
        job.status = Status.PENDING
        print("Submit jobs 6")
        job.save()
    except Exception as e:
        print("Submit jobs ERROR", e)
        logger.info("Failed to submit job %s" % job_id)
        # self.retry(exc=e, countdown=10)


@shared_task(bind=True)
def check_status_of_jobs(self):
    logger.info('Checking status of jobs on lsf')
    jobs = Job.objects.filter(status__in=(Status.PENDING, Status.RUNNING)).all()
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
        else:
            logger.info('Job %s not submitted to lsf' % str(job.id))
            job.status = Status.FAILED
            job.outputs = {'error': 'External id not provided %s' % str(job.id)}
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
                        keys_to_modify = ['started','submitted','finished','status','details']
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
                                                    old_value = single_tool_module.__dict__[single_key][single_detail_key]
                                                if single_detail_key in ['job_cpu','job_memory']:
                                                    if old_value:
                                                        last_record = old_value[-1]
                                                        if last_record[1] != single_detail_value:
                                                            new_record = (str(now()),single_detail_value)
                                                            single_tool_module.__dict__[single_key][single_detail_key].append(new_record)
                                                            updated = True
                                                    else:
                                                        new_record = (str(now()),single_detail_value)
                                                        single_tool_module.__dict__[single_key][single_detail_key] = [new_record]
                                                        updated = True
                                                else:
                                                    if old_value != single_detail_value:
                                                        single_tool_module.__dict__[single_key][single_detail_key] = single_detail_value
                                                        updated = True
                                    else:
                                        if single_key in ['started','submitted','finished']:
                                            if single_tool_module.__dict__[single_key] != None:
                                                continue
                                                if get_aware_datetime(single_tool_module.__dict__[single_key]) == get_aware_datetime(key_value):
                                                    continue
                                        single_tool_module.__dict__[single_key] = key_value
                                        updated = True
            if not already_exists:
                if details:
                    for single_detail_key in ['job_cpu','job_memory']:
                        if single_detail_key in details:
                            single_detail_value = details[single_detail_key]
                            if single_detail_value:
                                new_record = (str(now()),single_detail_value)
                                details[single_detail_key] = [new_record]
                single_tool_module = CommandLineToolJob(root=current_job,status=status, started=started, submitted=submitted,finished=finished,job_name=single_command_line_tool['name'],job_id=single_command_line_tool['id'],details=details)
                updated = True
            if updated:
                single_tool_module.save()

