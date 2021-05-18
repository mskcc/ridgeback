from django.urls import path, include
from rest_framework import routers
from .views.job_view import JobViewSet
from .views.cmdlinetooljob_view import JobCmdLineToolViewSet


router = routers.DefaultRouter()

router.register("jobs", JobViewSet)
router.register("status", JobCmdLineToolViewSet)


urlpatterns = [
    path("", include(router.urls)),
]
