from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
	fieldsets = UserAdmin.fieldsets + (
		(
			"PC",
			{
				"fields": (
					"full_name",
					"phone_number",
					"passport_number",
					"group",
					"birth_date",
					"course",
					"faculty",
					"payment_method",
					"gpa",
					"image",
					"hemis_image_url",
					"role",
				)
			},
		),
	)
	list_display = ("username", "full_name", "role", "group", "is_active")
