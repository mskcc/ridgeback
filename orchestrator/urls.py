from django.urls import path, include
from rest_framework import routers
from .views.job_view import JobViewSet, JobAbortViewSet
from .views.cmdlinetooljob_view import JobCmdLineToolViewSet


router = routers.DefaultRouter()

router.register('jobs', JobViewSet)
router.register('jobs/abort', JobAbortViewSet)
router.register('status', JobCmdLineToolViewSet)


urlpatterns = [
    path('', include(router.urls)),
]