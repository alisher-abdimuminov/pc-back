from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Attendance, AttendanceAttempt, AttendanceRecord


@admin.register(Attendance)
class AttendanceModelAdmin(ModelAdmin):
	list_display = ["student", "schedule", "date"]


@admin.register(AttendanceAttempt)
class AttendanceAttemptModelAdmin(ModelAdmin):
	list_display = ("student", "schedule", "step", "attempted_at")
	search_fields = ("student__username",)


@admin.register(AttendanceRecord)
class AttendanceRecordModelAdmin(ModelAdmin):
	list_display = ["attendance__student", "step", "face_verified", "location_verified"]
	search_fields = (
		"attendance__student__full_name",
		"attendance__student__username",
	)
