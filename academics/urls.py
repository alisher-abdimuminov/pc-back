from rest_framework.routers import DefaultRouter

from .views import GroupViewSet, LocationViewSet, ScheduleViewSet, StudentViewSet

router = DefaultRouter()
router.register("groups", GroupViewSet, basename="group")
router.register("students", StudentViewSet, basename="student")
router.register("locations", LocationViewSet, basename="location")
router.register("schedules", ScheduleViewSet, basename="schedule")
urlpatterns = router.urls
