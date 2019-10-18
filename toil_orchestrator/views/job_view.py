from toil_orchestrator.models import Job
from toil_orchestrator.serializers import JobSerializer
from toil_orchestrator.tasks import submit_jobs_to_lsf
from submitter.jobsubmitter import JobSubmitter
from rest_framework import mixins
from rest_framework import status
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response



class JobViewSet(mixins.CreateModelMixin,
                 mixins.DestroyModelMixin,
                 mixins.RetrieveModelMixin,
                 mixins.UpdateModelMixin,
                 mixins.ListModelMixin,
                 GenericViewSet):
    queryset = Job.objects.all()

    def get_serializer_class(self):
        return JobSerializer

    def create(self, request, *args, **kwargs):
        serializer = JobSerializer(data=request.data)
        if serializer.is_valid():
            response = serializer.save()
            submitter = JobSubmitter('TEST', response.app, response.inputs)
            submitter._prepare_directories()
            command_line = submitter._command_line()
            print(command_line)
            submitter.lsf_client.submit(command_line)
            # .delay(response.data['id'])
            return Response(response, status=status.HTTP_201_CREATED)
