from datetime import time

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from shapely.geometry import Point, Polygon

from academics.models import Schedule

from .models import (
	Attendance,
	AttendanceAttempt,
	AttendanceRecord,
)


def client_ip(request):
	xff = request.META.get("HTTP_X_FORWARDED_FOR")

	if xff:
		return xff.split(",")[0].strip()

	return request.META.get("REMOTE_ADDR")


def current_step(now=None):
	now = timezone.localtime(now or timezone.now())

	current_time = now.time().replace(tzinfo=None)

	for step, cfg in settings.ATTENDANCE_STEPS.items():
		start_hour, start_minute = map(
			int,
			cfg["start"].split(":"),
		)

		end_hour, end_minute = map(
			int,
			cfg["end"].split(":"),
		)

		start = time(
			start_hour,
			start_minute,
		)

		end = time(
			end_hour,
			end_minute,
		)

		if start <= current_time < end:
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


def point_in_location(
	latitude,
	longitude,
	location,
):
	"""
	DB/browser:
	    latitude, longitude

	Shapely:
	    Point(longitude, latitude)

	location.polygon() ham:
	    [(longitude, latitude), ...]
	"""

	try:
		latitude = float(latitude)
		longitude = float(longitude)
	except (TypeError, ValueError):
		return False

	polygon = Polygon(location.polygon())

	student_point = Point(
		longitude,
		latitude,
	)

	return polygon.covers(student_point)


class FaceVerificationService:
	@staticmethod
	def verify(
		reference_path,
		probe_path,
	):
		try:
			from deepface import DeepFace

			cfg = settings.FACE_VERIFY
			print("ref:", reference_path)
			print("probe:", probe_path)

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


def verify_attendance(
	request,
	student,
	image,
	lat,
	lng,
):
	if student.role != "student":
		raise ValidationError("Faqat student attendance qiladi")

	schedule = today_schedule(student)

	step = current_step()

	ip = client_ip(request)

	user_agent = request.META.get(
		"HTTP_USER_AGENT",
		"",
	)[:2000]

	# Har bir urinish avval auditga yoziladi.
	attempt = AttendanceAttempt.objects.create(
		student=student,
		schedule=schedule,
		step=step,
		image=image,
		ip_address=ip,
		latitude=lat,
		longitude=lng,
		location=(schedule.location if schedule else None),
		user_agent=user_agent,
	)

	def fail(code, message):
		attempt.error_code = code
		attempt.error_message = message

		attempt.save(
			update_fields=[
				"error_code",
				"error_message",
			]
		)

		raise ValidationError(
			{
				"code": code,
				"detail": message,
			}
		)

	# -------------------------
	# SCHEDULE
	# -------------------------

	if not schedule:
		fail(
			"NO_SCHEDULE",
			"Bugun siz uchun aktiv dars jadvali yo'q",
		)

	# -------------------------
	# STEP
	# -------------------------

	if step is None:
		fail(
			"STEP_CLOSED",
			"Hozir attendance step ochiq emas",
		)

	# -------------------------
	# ATTENDANCE
	# -------------------------

	attendance, _ = Attendance.objects.get_or_create(
		student=student,
		schedule=schedule,
		date=timezone.localdate(),
	)

	# -------------------------
	# ALREADY DONE
	# -------------------------

	if AttendanceRecord.objects.filter(
		attendance=attendance,
		step=step,
	).exists():
		fail(
			"ALREADY_VERIFIED",
			"Bu step avval tasdiqlangan",
		)

	# -------------------------
	# LOCATION
	# -------------------------

	if not point_in_location(
		latitude=lat,
		longitude=lng,
		location=schedule.location,
	):
		fail(
			"OUTSIDE_LOCATION",
			"Siz belgilangan hudud ichida emassiz",
		)

	attempt.location_verified = True

	attempt.save(
		update_fields=[
			"location_verified",
		]
	)

	# -------------------------
	# REFERENCE FACE
	# -------------------------

	if not student.image:
		fail(
			"NO_REFERENCE_FACE",
			"HEMIS profil rasmi saqlanmagan",
		)

	# -------------------------
	# FACE VERIFY
	# -------------------------
	#
	import os

	print("student image:", student.image)
	print("student image path:", student.image.path)
	print("exists:", os.path.exists(student.image.path))
	print(
		"size:",
		os.path.getsize(student.image.path)
		if os.path.exists(student.image.path)
		else None,
	)

	print("attempt image:", attempt.image)
	print("attempt path:", attempt.image.path)
	print("attempt exists:", os.path.exists(attempt.image.path))

	result = FaceVerificationService.verify(
		student.image.path,
		attempt.image.path,
	)

	attempt.face_verified = result.get(
		"verified",
		False,
	)

	attempt.liveness_verified = result.get(
		"liveness_verified",
		False,
	)

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
		fail(
			"FACE_MISMATCH",
			result.get("error") or "Yuz tasdiqlanmadi",
		)

	# -------------------------
	# CREATE ATTENDANCE RECORD
	# -------------------------

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
				liveness_verified=(
					result.get(
						"liveness_verified",
						False,
					)
				),
				face_distance=(result.get("distance")),
				face_threshold=(result.get("threshold")),
				user_agent=user_agent,
			)

	except IntegrityError:
		fail(
			"ALREADY_VERIFIED",
			"Bu step avval tasdiqlangan",
		)

	# -------------------------
	# SUCCESS AUDIT
	# -------------------------

	attempt.success = True

	attempt.save(
		update_fields=[
			"success",
		]
	)

	return record
