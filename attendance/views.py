from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import (
	status,
	viewsets,
)
from rest_framework.decorators import (
	api_view,
	permission_classes,
)
from rest_framework.permissions import (
	IsAuthenticated,
)
from rest_framework.response import (
	Response,
)
from rest_framework.views import (
	APIView,
)
from shapely.geometry import Point, Polygon

from accounts.models import User
from accounts.permissions import (
	IsStudent,
	IsTeacherOrAdmin,
)

from .models import (
	Attendance,
	AttendanceAttempt,
)
from .serializers import (
	AttendanceAttemptSerializer,
	AttendanceCheckSerializer,
	AttendanceRecordSerializer,
	AttendanceSerializer,
)
from .services import (
	current_step,
	point_in_location,
	today_schedule,
	verify_attendance,
)


@api_view(["GET"])
@permission_classes([IsStudent])
def today(request):
	schedule = today_schedule(request.user)

	now = timezone.localtime()

	step = current_step(now)

	if not schedule:
		return Response(
			{
				"has_schedule": False,
				"date": timezone.localdate(),
				"steps": [],
			}
		)

	attendance = (
		Attendance.objects.filter(
			student=request.user,
			schedule=schedule,
			date=timezone.localdate(),
		)
		.prefetch_related("records")
		.first()
	)

	done = {record.step for record in attendance.records.all()} if attendance else set()

	steps = []

	for number, config in settings.ATTENDANCE_STEPS.items():
		number = int(number)

		if number in done:
			step_status = "completed"

		elif step == number:
			step_status = "available"

		elif step is not None and number > step:
			step_status = "locked"

		else:
			step_status = "missed"

		steps.append(
			{
				"step": number,
				"start": config["start"],
				"end": config["end"],
				"status": step_status,
			}
		)

	return Response(
		{
			"has_schedule": True,
			"date": timezone.localdate(),
			"server_time": now,
			"schedule_id": schedule.id,
			"location": {
				"id": schedule.location_id,
				"name": schedule.location.name,
			},
			"steps": steps,
		}
	)


@api_view(["POST"])
@permission_classes([IsStudent])
def check(request):
	serializer = AttendanceCheckSerializer(data=request.data)

	serializer.is_valid(raise_exception=True)

	data = serializer.validated_data

	record = verify_attendance(
		request=request,
		student=request.user,
		image=data["face_image"],
		lat=data["latitude"],
		lng=data["longitude"],
	)

	return Response(
		AttendanceRecordSerializer(
			record,
			context={"request": request},
		).data,
		status=status.HTTP_201_CREATED,
	)


class AttendanceViewSet(viewsets.ReadOnlyModelViewSet):
	serializer_class = AttendanceSerializer

	permission_classes = [IsAuthenticated]

	def get_queryset(self):
		queryset = (
			Attendance.objects.select_related(
				"student",
				"schedule",
				"schedule__location",
			)
			.prefetch_related("records")
			.order_by(
				"-date",
				"student__full_name",
			)
		)

		user = self.request.user

		if user.role == User.Role.STUDENT:
			queryset = queryset.filter(student=user)

		elif user.role == User.Role.TEACHER:
			queryset = queryset.filter(student__group__teacher=user)

		group_id = self.request.query_params.get("group")

		date = self.request.query_params.get("date")

		if group_id:
			queryset = queryset.filter(student__group_id=group_id)

		if date:
			queryset = queryset.filter(date=date)

		return queryset.distinct()


class AttendanceAttemptViewSet(viewsets.ReadOnlyModelViewSet):
	serializer_class = AttendanceAttemptSerializer
	permission_classes = [IsTeacherOrAdmin]

	def get_queryset(self):
		qs = AttendanceAttempt.objects.select_related(
			"student",
			"schedule",
			"location",
		).order_by("-attempted_at")

		user = self.request.user

		if user.role == User.Role.TEACHER:
			qs = qs.filter(student__group__teacher=user)

		date = self.request.query_params.get("date")
		status_value = self.request.query_params.get("status")
		error_code = self.request.query_params.get("error_code")
		search = self.request.query_params.get("search")

		if date:
			qs = qs.filter(attempted_at__date=date)

		if status_value == "success":
			qs = qs.filter(success=True)

		elif status_value == "failed":
			qs = qs.filter(success=False)

		if error_code:
			qs = qs.filter(error_code=error_code)

		if search:
			qs = qs.filter(
				Q(student__full_name__icontains=search)
				| Q(student__username__icontains=search)
				| Q(ip_address__icontains=search)
				| Q(location__name__icontains=search)
				| Q(error_code__icontains=search)
				| Q(error_message__icontains=search)
			)

		return qs


class AttendanceLocationCheckView(APIView):
	permission_classes = [IsStudent]

	def post(self, request):
		user = request.user

		# -------------------------
		# GROUP
		# -------------------------

		if not user.group_id:
			return Response(
				{
					"has_class": False,
					"inside": False,
					"message": "Sizga guruh biriktirilmagan.",
				}
			)

		# -------------------------
		# LOCATION INPUT
		# -------------------------

		try:
			latitude = float(request.data.get("latitude"))

			longitude = float(request.data.get("longitude"))

		except (
			TypeError,
			ValueError,
		):
			return Response(
				{"detail": "Location noto‘g‘ri."},
				status=status.HTTP_400_BAD_REQUEST,
			)

		# -------------------------
		# TODAY SCHEDULE
		# -------------------------

		schedule = today_schedule(user)

		if not schedule:
			return Response(
				{
					"has_class": False,
					"inside": False,
					"message": "Bugun siz uchun dars mavjud emas.",
				}
			)

		location = schedule.location

		# -------------------------
		# LOCATION CHECK
		# -------------------------

		inside = point_in_location(
			latitude=latitude,
			longitude=longitude,
			location=location,
		)

		# Debug uchun vaqtincha:
		print(
			"student:",
			latitude,
			longitude,
		)

		print(
			"polygon:",
			Polygon(location.polygon()),
		)

		print(
			"student_point:",
			Point(
				longitude,
				latitude,
			),
		)

		print(
			"inside:",
			inside,
		)

		if not inside:
			return Response(
				{
					"has_class": True,
					"inside": False,
					"schedule_id": schedule.id,
					"location": {
						"id": location.id,
						"name": location.name,
					},
					"message": (
						"Siz dars bo‘ladigan joyda emassiz. "
						"Dars joyiga boring va qaytadan urinib ko‘ring."
					),
				}
			)

		return Response(
			{
				"has_class": True,
				"inside": True,
				"schedule_id": schedule.id,
				"location": {
					"id": location.id,
					"name": location.name,
				},
				"message": "Joylashuv tasdiqlandi.",
			}
		)
