from django.conf import settings
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsStudent, IsTeacherOrAdmin

from .models import Attendance, AttendanceAttempt
from .serializers import (
    AttendanceAttemptSerializer,
    AttendanceCheckSerializer,
    AttendanceRecordSerializer,
    AttendanceSerializer,
)
from .services import current_step, today_schedule, verify_attendance


@api_view(["GET"])
@permission_classes([IsStudent])
def today(request):
    schedule = today_schedule(request.user)
    now = timezone.localtime()
    step = current_step(now)
    if not schedule:
        return Response(
            {"has_schedule": False, "date": timezone.localdate(), "steps": []}
        )
    attendance = (
        Attendance.objects.filter(
            student=request.user, schedule=schedule, date=timezone.localdate()
        )
        .prefetch_related("records")
        .first()
    )
    done = {r.step for r in attendance.records.all()} if attendance else set()
    steps = []
    for n, cfg in settings.ATTENDANCE_STEPS.items():
        n = int(n)
        if n in done:
            st = "completed"
        elif step == n:
            st = "available"
        elif step is not None and n > step:
            st = "locked"
        else:
            st = "missed"
        steps.append(
            {"step": n, "start": cfg["start"], "end": cfg["end"], "status": st}
        )
    return Response(
        {
            "has_schedule": True,
            "date": timezone.localdate(),
            "server_time": now,
            "schedule_id": schedule.id,
            "location": {"id": schedule.location_id, "name": schedule.location.name},
            "steps": steps,
        }
    )


@api_view(["POST"])
@permission_classes([IsStudent])
def check(request):
    s = AttendanceCheckSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    d = s.validated_data
    rec = verify_attendance(
        request, request.user, d["face_image"], d["latitude"], d["longitude"]
    )
    return Response(
        AttendanceRecordSerializer(rec, context={"request": request}).data, status=201
    )


class AttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = (
            Attendance.objects.select_related(
                "student", "schedule", "schedule__location"
            )
            .prefetch_related("records")
            .order_by("-date", "student__full_name")
        )
        u = self.request.user
        if u.role == User.Role.STUDENT:
            qs = qs.filter(student=u)
        elif u.role == User.Role.TEACHER:
            qs = qs.filter(student__group__teacher=u)
        gid = self.request.query_params.get("group")
        date = self.request.query_params.get("date")
        if gid:
            qs = qs.filter(student__group_id=gid)
        if date:
            qs = qs.filter(date=date)
        return qs.distinct()


class AttendanceAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AttendanceAttemptSerializer
    permission_classes = [IsTeacherOrAdmin]

    def get_queryset(self):
        qs = AttendanceAttempt.objects.select_related(
            "student", "schedule", "location"
        ).order_by("-attempted_at")
        u = self.request.user
        if u.role == User.Role.TEACHER:
            qs = qs.filter(student__group__teacher=u)
        return qs
