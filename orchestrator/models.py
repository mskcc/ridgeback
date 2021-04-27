import uuid
from enum import IntEnum
from django.db import models
from django.utils import timezone
from django.contrib.postgres.fields import JSONField


def message_default():
    message_default_dict = {
        'log': '',
        'failed_jobs': {},
        'unknown_jobs': {},
        'info': ''
    }
    return message_default_dict


class Status(IntEnum):
    CREATED = 0
    SUBMITTING = 1
    SUBMITTED = 2
    PENDING = 3
    RUNNING = 4
    COMPLETED = 5
    FAILED = 6
    ABORTED = 7
    UNKNOWN = 8
    SUSPENDED = 9

    def transition(self, transition_to):
        if self == self.CREATED:
            if transition_to in (self.SUBMITTING, self.ABORTED,):
                return True
        elif self == self.SUBMITTING:
            if transition_to in (self.SUBMITTED, self.ABORTED):
                return True
        elif self == self.SUBMITTED:
            if transition_to in (
            self.PENDING, self.RUNNING, self.COMPLETED, self.FAILED, self.ABORTED, self.SUSPENDED, self.UNKNOWN):
                return True
        elif self == self.PENDING:
            if transition_to in (self.PENDING, self.RUNNING, self.COMPLETED, self.FAILED, self.ABORTED, self.SUSPENDED, self.UNKNOWN):
                return True
        elif self == self.RUNNING:
            if transition_to in (self.RUNNING, self.COMPLETED, self.FAILED, self.ABORTED, self.SUSPENDED, self.UNKNOWN):
                return True
        elif self in (self.COMPLETED, self.FAILED, self.ABORTED,):
            # Terminal state
            return False
        elif self == self.UNKNOWN:
            # Can transition to all lsf states
            if transition_to in (self.PENDING, self.RUNNING, self.COMPLETED, self.FAILED, self.ABORTED, self.SUSPENDED, self.UNKNOWN):
                return True
        elif self == self.SUSPENDED:
            if transition_to in (self.PENDING, self.RUNNING, self.ABORTED,):
                return True
        return False


class PipelineType(IntEnum):
    CWL = 0
    NEXTFLOW = 1


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True)
    output_directory = models.CharField(null=True, blank=True, max_length=400)


class Job(BaseModel):
    type = models.IntegerField(choices=[(pipeline_type.value, pipeline_type.name) for pipeline_type in PipelineType])
    app = JSONField(null=False)
    external_id = models.CharField(max_length=50, null=True, blank=True)
    root_dir = models.CharField(max_length=1000)
    job_store_location = models.CharField(max_length=1000, null=True, blank=True)
    resume_job_store_location = models.CharField(max_length=1000, null=True, blank=True)
    working_dir = models.CharField(max_length=1000, null=True, blank=True)
    status = models.IntegerField(choices=[(status.value, status.name) for status in Status], default=Status.CREATED)
    message = JSONField(default=message_default)
    inputs = JSONField(blank=True, null=True)
    outputs = JSONField(blank=True, null=True)
    job_store_clean_up = models.DateTimeField(blank=True, null=True)
    working_dir_clean_up = models.DateTimeField(blank=True, null=True)
    started = models.DateTimeField(blank=True, null=True)
    submitted = models.DateTimeField(blank=True, null=True)
    finished = models.DateTimeField(blank=True, null=True)
    track_cache = JSONField(blank=True, null=True)
    walltime = models.IntegerField(blank=True, null=True, default=None)
    memlimit = models.CharField(blank=True, null=True, default=None, max_length=20)

    def submit_to_lsf(self, external_id, job_store_dir, job_work_dir, job_output_dir, log_path):
        self.status = Status.SUBMITTED
        self.external_id = external_id
        self.job_store_location = job_store_dir
        self.working_dir = job_work_dir
        self.output_directory = job_output_dir
        self.log_path = log_path
        self.submitted = timezone.now()
        self.message['log'] = log_path
        self.save(update_fields=['status',
                                 'external_id',
                                 'job_store_location',
                                 'working_dir',
                                 'output_directory',
                                 'submitted',
                                 'message'])

    def update_status(self, lsf_status):
        if self.status == Status.PENDING and lsf_status == Status.RUNNING:
            self.started = timezone.now()
        self.status = lsf_status
        self.save(update_fields=['status', 'started'])

    def complete(self, outputs):
        self.track_cache = None
        self.outputs = outputs
        self.status = Status.COMPLETED
        self.finished = timezone.now()
        self.save()

    def fail(self, error_message, failed_jobs='', unknown_jobs=''):
        self.message['info'] = error_message
        self.message['failed_jobs'] = failed_jobs
        self.message['unknown_jobs'] = unknown_jobs
        self.status = Status.FAILED
        self.finished = timezone.now()
        self.save()

    def abort(self):
        self.status = Status.ABORTED
        self.finished = timezone.now()
        self.save()


class CommandLineToolJob(BaseModel):
    root = models.ForeignKey(Job, blank=False, null=False, on_delete=models.CASCADE)
    status = models.IntegerField(choices=[(status.value, status.name) for status in Status], default=Status.CREATED)
    started = models.DateTimeField(blank=True, null=True)
    submitted = models.DateTimeField(blank=True, null=True)
    finished = models.DateTimeField(blank=True, null=True)
    job_name = models.CharField(max_length=100)
    job_id = models.CharField(max_length=20)
    details = JSONField(blank=True, null=True)
