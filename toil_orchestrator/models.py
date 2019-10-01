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


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    output_directory = models.CharField(max_length=400)


class Job(BaseModel):
    app = JSONField(null=False)
    external_id = models.CharField(max_length=50)
    status = models.IntegerField(choices=[(status.value, status.name) for status in Status])
    inputs = JSONField(blank=True, null=False)
    outputs = JSONField(blank=True, null=False)


class CommandLineToolJob(BaseModel):
    root = models.ForeignKey(Job, blank=False, null=False, on_delete=models.CASCADE)
    status = models.IntegerField(choices=[(status.value, status.name) for status in Status])
    job_name = models.CharField(max_length=100)
    details = JSONField(blank=True, null=True)
