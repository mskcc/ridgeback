from rest_framework import serializers
from .models import Job, CommandLineToolJob


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ('id', 'created_date', 'app', 'inputs', 'outputs')


class CommandLineToolJobSerializer(serializers.ModelSerializer):

    class Meta:
        model = CommandLineToolJob
        fields = ('id', 'root', 'status', 'job_name', 'details')
