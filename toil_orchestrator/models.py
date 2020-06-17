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
    UNKNOWN = 5


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True)
    output_directory = models.CharField(null=True, blank=True, max_length=400)


class Job(BaseModel):
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
    working_dir_clean_up = models.DateTimeField(blank=True, null=True)
    started = models.DateTimeField(blank=True, null=True)
    submitted = models.DateTimeField(blank=True, null=True)
    finished = models.DateTimeField(blank=True, null=True)
    track_cache = JSONField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.status != Status.CREATED:
            if not self.submitted:
                self.submitted = self.created_date
            if self.status != Status.PENDING:
                if not self.started:
                    self.started = self.created_date
        if self.status == Status.COMPLETED or self.status == Status.FAILED:
            if not self.finished:
                self.finished = self.modified_date
        super().save(*args, **kwargs)


class CommandLineToolJob(BaseModel):
    root = models.ForeignKey(Job, blank=False, null=False, on_delete=models.CASCADE)
    status = models.IntegerField(choices=[(status.value, status.name) for status in Status], default=0)
    started = models.DateTimeField(blank=True, null=True)
    submitted = models.DateTimeField(blank=True, null=True)
    finished = models.DateTimeField(blank=True, null=True)
    job_name = models.CharField(max_length=100)
    job_id = models.CharField(max_length=20)
    details = JSONField(blank=True, null=True)
