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
    class Meta:
        model = AttendanceAttempt
        fields = "__all__"


class AttendanceCheckSerializer(serializers.Serializer):
    face_image = serializers.ImageField()
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7)

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
