from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Attendance, AttendanceAttempt, AttendanceRecord, Location, Schedule


@admin.register(Attendance)
class AttendanceModelAdmin(ModelAdmin):
	list_display = ["student", "schedule", "date"]


@admin.register(AttendanceAttempt)
class AttendanceAttemptModelAdmin(ModelAdmin):
	list_display = []


@admin.register(AttendanceRecord)
class AttendanceRecordModelAdmin(ModelAdmin):
	list_display = ["attendance", "step", "face_verified", "location_verified"]


@admin.register(Location)
class LocationModelAdmin(ModelAdmin):
	list_display = []


@admin.register(Schedule)
class ScheduleModelAdmin(ModelAdmin):
	list_display = []
