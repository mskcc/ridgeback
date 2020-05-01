from toil_orchestrator.models import Job, Status
from toil_orchestrator.serializers import JobSerializer
from toil_orchestrator.tasks import submit_jobs_to_lsf
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
    queryset = Job.objects.order_by('created_date').all()

    def get_serializer_class(self):
        return JobSerializer

    def create(self, request, *args, **kwargs):
        serializer = JobSerializer(data=request.data)
        if serializer.is_valid():
            response = serializer.save()
            submit_jobs_to_lsf(str(response.id))
            response = JobSerializer(response)
            return Response(response.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def list(self, request, *args, **kwargs):
        queryset = Job.objects.order_by('created_date').all()
        status_param = request.query_params.get('status')
        if status_param:
            if status_param not in [s.name for s in Status]:
                return Response({'details': 'Invalid status value %s: expected values %s' % (status_param, [s.name for s in Status])}, status=status.HTTP_400_BAD_REQUEST)
            queryset = queryset.filter(status=Status[status_param].value)
        page = self.paginate_queryset(queryset)
        serializer = JobSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


    @property
    def paginator(self):
        """
        The paginator instance associated with the view, or `None`.
        """
        if not hasattr(self, '_paginator'):
            if self.pagination_class is None:
                self._paginator = None
            else:
                self._paginator = self.pagination_class()
        return self._paginator

    def paginate_queryset(self, queryset):
        """
        Return a single page of results, or `None` if pagination is disabled.
        """
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(queryset, self.request, view=self)

    def get_paginated_response(self, data):
        """
        Return a paginated style `Response` object for the given output data.
        """
        assert self.paginator is not None
        return self.paginator.get_paginated_response(data)

