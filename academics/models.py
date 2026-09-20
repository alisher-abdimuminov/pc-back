from django.conf import settings
from django.db import models


class Group(models.Model):
	name = models.CharField(max_length=150, unique=True)
	hemis_id = models.PositiveIntegerField(
		null=True,
		blank=True,
		unique=True,
	)
	teacher = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="teaching_groups",
		limit_choices_to={"role": "teacher"},
	)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return self.name


class Location(models.Model):
	name = models.CharField(max_length=255, unique=True)
	point_1 = models.CharField(max_length=100)
	point_2 = models.CharField(max_length=100)
	point_3 = models.CharField(max_length=100)
	point_4 = models.CharField(max_length=100)
	location = models.CharField(max_length=1000, null=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	@staticmethod
	def parse_point(value: str):
		try:
			lat, lng = value.split(",")

			lat = float(lat.strip())
			lng = float(lng.strip())

			if not -90 <= lat <= 90:
				raise ValueError("Latitude noto'g'ri")

			if not -180 <= lng <= 180:
				raise ValueError("Longitude noto'g'ri")

			return lat, lng

		except (ValueError, AttributeError):
			raise ValueError(
				"Koordinata 'latitude,longitude' formatida bo'lishi kerak. "
				"Masalan: 39.654321,66.987654"
			)

	def polygon(self):
		points = [
			self.parse_point(self.point_1),
			self.parse_point(self.point_2),
			self.parse_point(self.point_3),
			self.parse_point(self.point_4),
		]

		# parse_point -> (latitude, longitude)
		# Shapely -> (longitude, latitude)

		return [(lng, lat) for lat, lng in points]

	def __str__(self):
		return self.name


class Schedule(models.Model):
	class Weekday(models.IntegerChoices):
		MONDAY = 0, "Monday"
		TUESDAY = 1, "Tuesday"
		WEDNESDAY = 2, "Wednesday"
		THURSDAY = 3, "Thursday"
		FRIDAY = 4, "Friday"
		SATURDAY = 5, "Saturday"
		SUNDAY = 6, "Sunday"

	weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
	location = models.ForeignKey(
		Location, on_delete=models.PROTECT, related_name="schedules"
	)
	groups = models.ManyToManyField(Group, related_name="schedules")
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"{self.get_weekday_display()} - {self.location}"
