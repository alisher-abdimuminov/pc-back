from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Attendance, AttendanceAttempt, AttendanceRecord


@admin.register(Attendance)
class AttendanceModelAdmin(ModelAdmin):
	list_display = ["student", "schedule", "date"]


@admin.register(AttendanceAttempt)
class AttendanceAttemptModelAdmin(ModelAdmin):
	list_display = ("student", "schedule", "step", "attepmted_at")
	search_fields = ("student__username",)


@admin.register(AttendanceRecord)
class AttendanceRecordModelAdmin(ModelAdmin):
	list_display = ["attendance", "step", "face_verified", "location_verified"]
