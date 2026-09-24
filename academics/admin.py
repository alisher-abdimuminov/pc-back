from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Schedule


@admin.register(Schedule)
class ScheduleModelAdmin(ModelAdmin):
	list_display = ["weekday", "shift", "location"]
