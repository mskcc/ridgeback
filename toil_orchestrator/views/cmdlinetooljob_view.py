from toil_orchestrator.models import CommandLineToolJob
from toil_orchestrator.serializers import CommandLineToolJobSerializer
from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet


class JobCmdLineToolViewSet(mixins.CreateModelMixin,
                            mixins.DestroyModelMixin,
                            mixins.RetrieveModelMixin,
                            mixins.UpdateModelMixin,
                            mixins.ListModelMixin,
                            GenericViewSet):
    queryset = CommandLineToolJob.objects.all()

    def get_serializer_class(self):
        return CommandLineToolJobSerializer
