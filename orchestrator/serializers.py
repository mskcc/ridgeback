from drf_yasg import openapi
from rest_framework import serializers
from .models import Job, CommandLineToolJob, Status
from django.core.exceptions import ValidationError


class AppField(serializers.JSONField):
    def validate_app(app_data):
        if "github" not in app_data:
            if "base64" in app_data:
                raise ValidationError("base64 is not supported", code=501)
            elif "app" in app_data:
                raise ValidationError("app is not supported", code=501)
            else:
                raise ValidationError("Invalid app reference type", code=400)

    default_validators = [validate_app]

    class Meta:
        swagger_schema_fields = {
            "type": openapi.TYPE_OBJECT,
            "title": "App",
            "properties": {
                "github": openapi.Schema(
                    title="github",
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "repository": openapi.Schema(
                            title="repository",
                            type=openapi.TYPE_STRING,
                        ),
                        "entrypoint": openapi.Schema(
                            title="entrypoint",
                            type=openapi.TYPE_STRING,
                        ),
                        "version": openapi.Schema(
                            title="version",
                            type=openapi.TYPE_STRING,
                        ),
                    },
                    required=["repository", "entrypoint"],
                ),
                "base64": openapi.Schema(
                    title="base64",
                    type=openapi.TYPE_STRING,
                ),
                "app": openapi.Schema(
                    title="app",
                    type=openapi.TYPE_STRING,
                ),
            },
        }


class MessageField(serializers.JSONField):
    class Meta:
        swagger_schema_fields = {
            "type": openapi.TYPE_OBJECT,
            "title": "message",
            "properties": {
                "log": openapi.Schema(
                    title="log",
                    type=openapi.TYPE_STRING,
                ),
                "failed_jobs": openapi.Schema(
                    title="failed_jobs",
                    type=openapi.TYPE_OBJECT,
                ),
                "unknown_jobs": openapi.Schema(
                    title="unknown_jobs",
                    type=openapi.TYPE_OBJECT,
                ),
                "info": openapi.Schema(
                    title="info",
                    type=openapi.TYPE_STRING,
                ),
            },
        }


class CommandLineToolJobSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        return Status(obj.status).name

    class Meta:
        model = CommandLineToolJob
        fields = "__all__"


class JobIdsSerializer(serializers.Serializer):
    job_ids = serializers.ListField(
        allow_empty=True,
        child=serializers.UUIDField(required=True),
    )


class JobSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    app = AppField()
    message = MessageField(required=False)
    commandlinetooljob_set = CommandLineToolJobSerializer(many=True, required=False)

    def get_status(self, obj):
        return Status(obj.status).name

    class Meta:
        model = Job
        fields = "__all__"


class JobStatusSerializer(serializers.Serializer):
    jobs = serializers.DictField()


class JobSubmitSerializer(JobSerializer):
    class Meta:
        model = Job
        fields = ("type", "app", "inputs", "root_dir", "log_dir", "log_prefix")


class JobResumeSerializer(JobSerializer):
    class Meta:
        model = Job
        fields = ("root_dir", "log_dir", "log_prefix")
