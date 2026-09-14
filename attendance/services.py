from datetime import time

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from academics.models import Schedule

from .models import Attendance, AttendanceAttempt, AttendanceRecord


def client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")


def point_in_polygon(lat, lng, polygon):
    x, y = lng, lat
    inside = False
    n = len(polygon)
    for i in range(n):
        lat1, lng1 = polygon[i]
        lat2, lng2 = polygon[(i + 1) % n]
        x1, y1 = lng1, lat1
        x2, y2 = lng2, lat2
        if (y1 > y) != (y2 > y):
            xinters = (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-15) + x1
            if x < xinters:
                inside = not inside
    return inside


def current_step(now=None):
    now = timezone.localtime(now or timezone.now())
    t = now.time().replace(tzinfo=None)
    for step, cfg in settings.ATTENDANCE_STEPS.items():
        sh, sm = map(int, cfg["start"].split(":"))
        eh, em = map(int, cfg["end"].split(":"))
        if time(sh, sm) <= t < time(eh, em):
            return int(step)
    return None


def today_schedule(student, now=None):
    now = timezone.localtime(now or timezone.now())
    if not student.group_id:
        return None
    return (
        Schedule.objects.filter(
            is_active=True,
            weekday=now.weekday(),
            groups=student.group,
            location__is_active=True,
        )
        .select_related("location")
        .first()
    )


class FaceVerificationService:
    @staticmethod
    def verify(reference_path, probe_path):
        try:
            from deepface import DeepFace

            cfg = settings.FACE_VERIFY
            result = DeepFace.verify(
                img1_path=reference_path,
                img2_path=probe_path,
                model_name=cfg["MODEL_NAME"],
                detector_backend=cfg["DETECTOR_BACKEND"],
                distance_metric=cfg["DISTANCE_METRIC"],
                enforce_detection=True,
                align=True,
                anti_spoofing=cfg["ANTI_SPOOFING"],
                silent=True,
            )
            return {
                "verified": bool(result.get("verified")),
                "liveness_verified": True if cfg["ANTI_SPOOFING"] else False,
                "distance": result.get("distance"),
                "threshold": result.get("threshold"),
            }
        except Exception as exc:
            return {
                "verified": False,
                "liveness_verified": False,
                "distance": None,
                "threshold": None,
                "error": str(exc),
            }


def verify_attendance(request, student, image, lat, lng):
    if student.role != "student":
        raise ValidationError("Faqat student attendance qiladi")
    schedule = today_schedule(student)
    step = current_step()
    ip = client_ip(request)
    ua = request.META.get("HTTP_USER_AGENT", "")[:2000]
    attempt = AttendanceAttempt.objects.create(
        student=student,
        schedule=schedule,
        step=step,
        image=image,
        ip_address=ip,
        latitude=lat,
        longitude=lng,
        location=schedule.location if schedule else None,
        user_agent=ua,
    )

    def fail(code, msg):
        attempt.error_code = code
        attempt.error_message = msg
        attempt.save(update_fields=["error_code", "error_message"])
        raise ValidationError({"code": code, "detail": msg})

    if not schedule:
        fail("NO_SCHEDULE", "Bugun siz uchun aktiv dars jadvali yo'q")
    if step is None:
        fail("STEP_CLOSED", "Hozir attendance step ochiq emas")
    attendance, _ = Attendance.objects.get_or_create(
        student=student, schedule=schedule, date=timezone.localdate()
    )
    if AttendanceRecord.objects.filter(attendance=attendance, step=step).exists():
        fail("ALREADY_VERIFIED", "Bu step avval tasdiqlangan")
    if not point_in_polygon(float(lat), float(lng), schedule.location.polygon()):
        fail("OUTSIDE_LOCATION", "Siz belgilangan hudud ichida emassiz")
    attempt.location_verified = True
    attempt.save(update_fields=["location_verified"])
    if not student.image:
        fail("NO_REFERENCE_FACE", "HEMIS profil rasmi saqlanmagan")
    result = FaceVerificationService.verify(student.image.path, attempt.image.path)
    attempt.face_verified = result.get("verified", False)
    attempt.liveness_verified = result.get("liveness_verified", False)
    attempt.face_distance = result.get("distance")
    attempt.face_threshold = result.get("threshold")
    attempt.save(
        update_fields=[
            "face_verified",
            "liveness_verified",
            "face_distance",
            "face_threshold",
        ]
    )
    if not result.get("verified"):
        fail("FACE_MISMATCH", result.get("error") or "Yuz tasdiqlanmadi")
    try:
        with transaction.atomic():
            record = AttendanceRecord.objects.create(
                attendance=attendance,
                step=step,
                image=attempt.image.name,
                ip_address=ip,
                latitude=lat,
                longitude=lng,
                location=schedule.location,
                face_verified=True,
                location_verified=True,
                liveness_verified=result.get("liveness_verified", False),
                face_distance=result.get("distance"),
                face_threshold=result.get("threshold"),
                user_agent=ua,
            )
    except IntegrityError:
        fail("ALREADY_VERIFIED", "Bu step avval tasdiqlangan")
    attempt.success = True
    attempt.save(update_fields=["success"])
    return record
