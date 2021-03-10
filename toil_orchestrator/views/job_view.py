from toil_orchestrator.models import Job, Status
from toil_orchestrator.serializers import JobSerializer, JobSubmitSerializer, JobResumeSerializer, JobIdsSerializer, JobStatusSerializer
from toil_orchestrator.tasks import abort_job
from rest_framework import mixins
from rest_framework import status
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import action


class JobViewSet(mixins.CreateModelMixin,
                 mixins.DestroyModelMixin,
                 mixins.RetrieveModelMixin,
                 mixins.UpdateModelMixin,
                 mixins.ListModelMixin,
                 GenericViewSet):
    queryset = Job.objects.order_by('created_date').all()

    def get_serializer_class(self):
        return JobSerializer

    def validate_and_save(self, data):
        serializer = JobSerializer(data=data)
        if serializer.is_valid():
            response = serializer.save()
            response = JobSerializer(response)
            return Response(response.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(request_body=JobResumeSerializer, responses={status.HTTP_201_CREATED: JobSerializer})
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None, *args, **kwargs):
        resume_data = request.data
        try:
            parent_job = Job.objects.get(id=pk)
            if parent_job.job_store_clean_up != None:
                return Response("The job store of the job indicated to be resumed has been cleaned up",
                                status=status.HTTP_410_GONE)
            resume_data['app'] = parent_job.app
            resume_data['inputs'] = parent_job.inputs
            resume_data['resume_job_store_location'] = parent_job.job_store_location
            return self.validate_and_save(resume_data)
        except Job.DoesNotExist:
            return Response("Could not find the indicated job to resume", status=status.HTTP_404_NOT_FOUND)

    @swagger_auto_schema(request_body=JobIdsSerializer(), responses={status.HTTP_200_OK: JobStatusSerializer})
    @action(detail=False, methods=['post'])
    def statuses(self, request):
        serializer = JobIdsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)
        job_ids = serializer.validated_data.get("job_ids")
        job_status_data = {}
        for single_job in self.queryset.filter(id__in=job_ids):
            job_obj = JobSerializer(single_job)
            job_data = job_obj.data
            job_id = job_data["id"]
            job_status_data[job_id] = job_data
        resp_serializer = JobStatusSerializer(data={'jobs':job_status_data})
        if resp_serializer.is_valid():
            return Response(resp_serializer.data)
        else:
            return Response(resp_serializer.errors,
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(responses={status.HTTP_200_OK: JobSerializer})
    @action(detail=True, methods=['get'])
    def abort(self, request, pk=None, *args, **kwargs):
        try:
            job = Job.objects.get(id=pk)
        except Job.DoesNotExist:
            return Response("Job not found", status=status.HTTP_404_NOT_FOUND)
        abort_job.delay(str(pk))
        return Response("Job aborted", status=status.HTTP_200_OK)

    @swagger_auto_schema(request_body=JobSubmitSerializer, responses={status.HTTP_201_CREATED: JobSerializer})
    def create(self, request, *args, **kwargs):
        return self.validate_and_save(request.data)

    def list(self, request, *args, **kwargs):
        queryset = Job.objects.order_by('created_date').all()
        status_param = request.query_params.get('status')
        if status_param:
            if status_param not in [s.name for s in Status]:
                return Response({'details': 'Invalid status value %s: expected values %s' % (
                status_param, [s.name for s in Status])}, status=status.HTTP_400_BAD_REQUEST)
            queryset = queryset.filter(status=Status[status_param].value)
        page = self.paginate_queryset(queryset)
        serializer = JobSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        if request.user.is_superuser:
            return super().destroy(request, *args, **kwargs)
        else:
            return Response("Only admins can delete job objects", status=status.HTTP_401_UNAUTHORIZED)

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
