from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AttendanceAttemptViewSet, AttendanceViewSet, check, today

router = DefaultRouter()
router.register("records", AttendanceViewSet, basename="attendance-records")
router.register("attempts", AttendanceAttemptViewSet, basename="attendance-attempts")
urlpatterns = [path("today/", today), path("check/", check)] + router.urls
