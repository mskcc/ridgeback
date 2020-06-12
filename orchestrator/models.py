import uuid
from enum import IntEnum
from django.db import models
from django.contrib.postgres.fields import JSONField


class Status(IntEnum):
    CREATED = 0
    PENDING = 1
    RUNNING = 2
    COMPLETED = 3
    FAILED = 4
    UNKOWN = 5


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
    message = models.CharField(max_length=500, null=True, blank=True)
    inputs = JSONField(blank=True, null=True)
    outputs = JSONField(blank=True, null=True)
    job_store_clean_up = models.DateTimeField(blank=True, null=True)
    track_cache = JSONField(blank=True, null=True)


class CommandLineToolJob(BaseModel):
    root = models.ForeignKey(Job, blank=False, null=False, on_delete=models.CASCADE)
    status = models.IntegerField(choices=[(status.value, status.name) for status in Status], default=0)
    started = models.DateTimeField(blank=True, null=True)
    submitted = models.DateTimeField(blank=True, null=True)
    finished = models.DateTimeField(blank=True, null=True)
    job_name = models.CharField(max_length=100)
    job_id = models.CharField(max_length=20)
    details = JSONField(blank=True, null=True)
