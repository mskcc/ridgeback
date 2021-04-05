# Generated by Django 2.2.13 on 2021-04-02 17:08

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import orchestrator.models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BaseModel',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_date', models.DateTimeField(auto_now_add=True)),
                ('modified_date', models.DateTimeField(auto_now=True)),
                ('output_directory', models.CharField(blank=True, max_length=400, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Job',
            fields=[
                ('basemodel_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='orchestrator.BaseModel')),
                ('type', models.IntegerField(choices=[(0, 'CWL'), (1, 'NEXTFLOW')])),
                ('app', django.contrib.postgres.fields.jsonb.JSONField()),
                ('external_id', models.CharField(blank=True, max_length=50, null=True)),
                ('root_dir', models.CharField(max_length=1000)),
                ('job_store_location', models.CharField(blank=True, max_length=1000, null=True)),
                ('resume_job_store_location', models.CharField(blank=True, max_length=1000, null=True)),
                ('working_dir', models.CharField(blank=True, max_length=1000, null=True)),
                ('status', models.IntegerField(choices=[(0, 'CREATED'), (1, 'PENDING'), (2, 'RUNNING'), (3, 'COMPLETED'), (4, 'FAILED'), (5, 'ABORTED'), (6, 'UNKNOWN')], default=orchestrator.models.Status(0))),
                ('message', django.contrib.postgres.fields.jsonb.JSONField(default=orchestrator.models.message_default)),
                ('inputs', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
                ('outputs', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
                ('job_store_clean_up', models.DateTimeField(blank=True, null=True)),
                ('working_dir_clean_up', models.DateTimeField(blank=True, null=True)),
                ('started', models.DateTimeField(blank=True, null=True)),
                ('submitted', models.DateTimeField(blank=True, null=True)),
                ('finished', models.DateTimeField(blank=True, null=True)),
                ('track_cache', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
            ],
            bases=('orchestrator.basemodel',),
        ),
        migrations.CreateModel(
            name='CommandLineToolJob',
            fields=[
                ('basemodel_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='orchestrator.BaseModel')),
                ('status', models.IntegerField(choices=[(0, 'CREATED'), (1, 'PENDING'), (2, 'RUNNING'), (3, 'COMPLETED'), (4, 'FAILED'), (5, 'ABORTED'), (6, 'UNKNOWN')], default=orchestrator.models.Status(0))),
                ('started', models.DateTimeField(blank=True, null=True)),
                ('submitted', models.DateTimeField(blank=True, null=True)),
                ('finished', models.DateTimeField(blank=True, null=True)),
                ('job_name', models.CharField(max_length=100)),
                ('job_id', models.CharField(max_length=20)),
                ('details', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
                ('root', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='orchestrator.Job')),
            ],
            bases=('orchestrator.basemodel',),
        ),
    ]
