from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from accounts.models import User
from accounts.permissions import IsAdmin, IsTeacherOrAdmin

from .models import Group, Location, Schedule
from .serializers import (
    GroupSerializer,
    LocationSerializer,
    ScheduleSerializer,
    StudentListSerializer,
)


class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer

    def get_permissions(self):
        return (
            [IsAdmin()]
            if self.action not in {"list", "retrieve"}
            else [IsAuthenticated()]
        )

    def get_queryset(self):
        u = self.request.user
        qs = Group.objects.select_related("teacher").all().order_by("name")
        if u.role == User.Role.TEACHER:
            return qs.filter(teacher=u)
        if u.role == User.Role.STUDENT:
            return qs.filter(pk=u.group_id)
        return qs


class StudentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudentListSerializer
    permission_classes = [IsTeacherOrAdmin]

    def get_queryset(self):
        qs = (
            User.objects.filter(role=User.Role.STUDENT)
            .select_related("group")
            .order_by("full_name")
        )
        u = self.request.user
        if u.role == User.Role.TEACHER:
            qs = qs.filter(group__teacher=u)
        gid = self.request.query_params.get("group")
        return qs.filter(group_id=gid) if gid else qs


class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all().order_by("name")
    serializer_class = LocationSerializer

    def get_permissions(self):
        return (
            [IsAdmin()]
            if self.action not in {"list", "retrieve"}
            else [IsAuthenticated()]
        )


class ScheduleViewSet(viewsets.ModelViewSet):
    serializer_class = ScheduleSerializer

    def get_permissions(self):
        return (
            [IsAdmin()]
            if self.action not in {"list", "retrieve"}
            else [IsAuthenticated()]
        )

    def get_queryset(self):
        qs = (
            Schedule.objects.prefetch_related("groups")
            .select_related("location")
            .all()
            .order_by("weekday")
        )
        u = self.request.user
        if u.role == User.Role.TEACHER:
            return qs.filter(groups__teacher=u).distinct()
        if u.role == User.Role.STUDENT:
            return qs.filter(groups=u.group).distinct()
        return qs
