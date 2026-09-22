from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
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

	# Bu monitoring endpointda bitta guruhdagi
	# barcha talabalar birdan chiqishi kerak.
	# Global DRF pagination bu endpointga ta'sir qilmaydi.
	pagination_class = None

	def list(self, request, *args, **kwargs):
		user = request.user

		group_id = request.query_params.get("group")
		date_value = request.query_params.get("date")

		# ----------------------------------
		# GROUP REQUIRED
		# ----------------------------------

		if not group_id:
			return Response([])

		# ----------------------------------
		# DATE
		# ----------------------------------

		if date_value:
			selected_date = parse_date(date_value)

			if not selected_date:
				return Response(
					{"detail": "Sana noto‘g‘ri formatda."},
					status=status.HTTP_400_BAD_REQUEST,
				)
		else:
			selected_date = timezone.localdate()

		# ----------------------------------
		# STUDENTS
		# ----------------------------------

		students = (
			User.objects.filter(
				role=User.Role.STUDENT,
				group_id=group_id,
			)
			.select_related("group")
			.order_by(
				"full_name",
				"username",
			)
		)

		# Teacher faqat o‘ziga biriktirilgan
		# guruh talabalarini ko‘ra oladi.
		if user.role == User.Role.TEACHER:
			students = students.filter(group__teacher=user)

		student_list = list(students)

		if not student_list:
			return Response([])

		student_ids = [student.id for student in student_list]

		# ----------------------------------
		# ATTENDANCE FOR SELECTED DATE
		# ----------------------------------

		attendances = (
			Attendance.objects.filter(
				student_id__in=student_ids,
				date=selected_date,
			)
			.select_related(
				"student",
				"schedule",
				"schedule__location",
			)
			.prefetch_related("records")
		)

		# student_id -> records
		records_by_student = {}

		for attendance in attendances:
			if attendance.student_id not in records_by_student:
				records_by_student[attendance.student_id] = []

			records_by_student[attendance.student_id].extend(
				list(attendance.records.all())
			)

		# ----------------------------------
		# RESPONSE
		# ----------------------------------

		result = []

		for student in student_list:
			records = records_by_student.get(
				student.id,
				[],
			)

			serialized_records = AttendanceRecordSerializer(
				records,
				many=True,
				context={"request": request},
			).data

			result.append(
				{
					# Monitoring row ID sifatida
					# student ID ishlatamiz.
					"id": student.id,
					"student": student.id,
					"student_name": (student.full_name or student.username),
					"student_username": student.username,
					"group": student.group_id,
					"group_name": (student.group.name if student.group else None),
					"date": selected_date,
					"records": serialized_records,
				}
			)

		return Response(result)

	def retrieve(
		self,
		request,
		*args,
		**kwargs,
	):
		return super().retrieve(
			request,
			*args,
			**kwargs,
		)

	def get_queryset(self):
		"""
		Retrieve yoki boshqa ichki foydalanish uchun
		eski querysetni saqlab qolamiz.
		"""

		qs = (
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
			qs = qs.filter(student=user)

		elif user.role == User.Role.TEACHER:
			qs = qs.filter(student__group__teacher=user)

		return qs.distinct()


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
