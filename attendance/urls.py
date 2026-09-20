from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
	AttendanceAttemptViewSet,
	AttendanceLocationCheckView,
	AttendanceViewSet,
	check,
	today,
)

router = DefaultRouter()
router.register("records", AttendanceViewSet, basename="attendance-records")
router.register("attempts", AttendanceAttemptViewSet, basename="attendance-attempts")
urlpatterns = [
	path("today/", today),
	path("verify/", check),
	path("location-check/", AttendanceLocationCheckView.as_view()),
] + router.urls
