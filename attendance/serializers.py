from django.conf import settings
from rest_framework import serializers

from .models import Attendance, AttendanceAttempt, AttendanceRecord


class AttendanceRecordSerializer(serializers.ModelSerializer):
	location_name = serializers.CharField(source="location.name", read_only=True)

	class Meta:
		model = AttendanceRecord
		fields = "__all__"


class AttendanceSerializer(serializers.ModelSerializer):
	records = AttendanceRecordSerializer(many=True, read_only=True)
	student_name = serializers.CharField(source="student.full_name", read_only=True)

	class Meta:
		model = Attendance
		fields = [
			"id",
			"student",
			"student_name",
			"schedule",
			"date",
			"records",
			"created_at",
		]


class AttendanceAttemptSerializer(serializers.ModelSerializer):
	student_name = serializers.CharField(
		source="student.full_name",
		read_only=True,
	)

	student_username = serializers.CharField(
		source="student.username",
		read_only=True,
	)

	location_name = serializers.CharField(
		source="location.name",
		read_only=True,
	)

	class Meta:
		model = AttendanceAttempt

		fields = [
			"id",
			"student",
			"student_name",
			"student_username",
			"schedule",
			"step",
			"attempted_at",
			"image",
			"ip_address",
			"latitude",
			"longitude",
			"location",
			"location_name",
			"face_verified",
			"location_verified",
			"liveness_verified",
			"success",
			"error_code",
			"error_message",
			"face_distance",
			"face_threshold",
			"user_agent",
		]


class AttendanceCheckSerializer(serializers.Serializer):
	face_image = serializers.ImageField()
	latitude = serializers.FloatField(
		min_value=-90,
		max_value=90,
	)

	longitude = serializers.FloatField(
		min_value=-180,
		max_value=180,
	)

	def validate_face_image(self, f):
		if f.size > settings.MAX_ATTENDANCE_IMAGE_BYTES:
			raise serializers.ValidationError("Rasm juda katta")
		if getattr(f, "content_type", "") not in {
			"image/jpeg",
			"image/png",
			"image/webp",
		}:
			raise serializers.ValidationError("Faqat jpg/png/webp")
		return f
