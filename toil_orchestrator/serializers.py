from rest_framework import serializers
from .models import Job, CommandLineToolJob, Status


class JobSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        return Status(obj.status).name

    class Meta:
        model = Job
        fields = (
        'id', 'status', 'created_date', 'app', 'inputs', 'outputs', 'root_dir', 'job_store_location', 'working_dir')


class CommandLineToolJobSerializer(serializers.ModelSerializer):

    class Meta:
        model = CommandLineToolJob
        fields = ('id', 'root', 'status', 'job_name', 'details')
