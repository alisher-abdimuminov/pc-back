from django.conf import settings
from django.db import models

from academics.models import Location, Schedule


class Attendance(models.Model):
	student = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendances"
	)
	schedule = models.ForeignKey(
		Schedule, on_delete=models.PROTECT, related_name="attendances"
	)
	date = models.DateField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["student", "schedule", "date"],
				name="uniq_student_schedule_date",
			)
		]


class AttendanceRecord(models.Model):
	attendance = models.ForeignKey(
		Attendance, on_delete=models.CASCADE, related_name="records"
	)
	step = models.PositiveSmallIntegerField()
	verified_at = models.DateTimeField(auto_now_add=True)
	image = models.ImageField(upload_to="attendance/%Y/%m/%d/")
	ip_address = models.GenericIPAddressField(null=True, blank=True)
	latitude = models.DecimalField(
		max_digits=18,
		decimal_places=15,
		null=True,
		blank=True,
	)

	longitude = models.DecimalField(
		max_digits=18,
		decimal_places=15,
		null=True,
		blank=True,
	)
	location = models.ForeignKey(
		Location, on_delete=models.PROTECT, related_name="attendance_records"
	)
	face_verified = models.BooleanField(default=False)
	location_verified = models.BooleanField(default=False)
	liveness_verified = models.BooleanField(default=False)
	face_distance = models.FloatField(null=True, blank=True)
	face_threshold = models.FloatField(null=True, blank=True)
	user_agent = models.TextField(blank=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["attendance", "step"], name="uniq_attendance_step"
			)
		]


class AttendanceAttempt(models.Model):
	student = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="attendance_attempts",
	)
	schedule = models.ForeignKey(
		Schedule,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="attendance_attempts",
	)
	step = models.PositiveSmallIntegerField(null=True, blank=True)
	attempted_at = models.DateTimeField(auto_now_add=True)
	image = models.ImageField(
		upload_to="attendance_attempts/%Y/%m/%d/", null=True, blank=True
	)
	ip_address = models.GenericIPAddressField(null=True, blank=True)
	latitude = models.DecimalField(
		max_digits=18,
		decimal_places=15,
		null=True,
		blank=True,
	)

	longitude = models.DecimalField(
		max_digits=18,
		decimal_places=15,
		null=True,
		blank=True,
	)
	location = models.ForeignKey(
		Location,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="attendance_attempts",
	)
	face_verified = models.BooleanField(default=False)
	location_verified = models.BooleanField(default=False)
	liveness_verified = models.BooleanField(default=False)
	success = models.BooleanField(default=False)
	error_code = models.CharField(max_length=100, blank=True)
	error_message = models.TextField(blank=True)
	face_distance = models.FloatField(null=True, blank=True)
	face_threshold = models.FloatField(null=True, blank=True)
	user_agent = models.TextField(blank=True)
