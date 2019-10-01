from toil_orchestrator.models import Job
from toil_orchestrator.serializers import JobSerializer
from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet


class JobViewSet(mixins.CreateModelMixin,
                 mixins.DestroyModelMixin,
                 mixins.RetrieveModelMixin,
                 mixins.UpdateModelMixin,
                 mixins.ListModelMixin,
                 GenericViewSet):
    queryset = Job.objects.all()

    def get_serializer_class(self):
        return JobSerializer
