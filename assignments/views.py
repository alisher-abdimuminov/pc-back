from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsTeacherOrAdmin

from .models import Assignment, Submission
from .serializers import (
	AssignmentSerializer,
	GradeSerializer,
	SubmissionSerializer,
	SubmitSerializer,
)


class AssignmentViewSet(viewsets.ModelViewSet):
	serializer_class = AssignmentSerializer
	permission_classes = [IsAuthenticated]
	pagination_class = None

	def get_queryset(self):
		qs = (
			Assignment.objects.select_related("teacher")
			.prefetch_related("groups")
			.order_by("-created_at")
		)
		u = self.request.user
		if u.role == User.Role.STUDENT:
			return qs.filter(groups=u.group).distinct()
		if u.role == User.Role.TEACHER:
			return qs.filter(teacher=u)
		return qs

	def perform_create(self, s):
		if self.request.user.role not in {User.Role.TEACHER, User.Role.ADMIN}:
			raise PermissionDenied("Faqat teacher/admin vazifa yaratadi")
		s.save(teacher=self.request.user)

	def perform_update(self, s):
		if (
			self.request.user.role == User.Role.TEACHER
			and s.instance.teacher_id != self.request.user.id
		):
			raise PermissionDenied()
		s.save()

	def destroy(self, request, *a, **kw):
		obj = self.get_object()
		if request.user.role == User.Role.STUDENT:
			raise PermissionDenied()
		return super().destroy(request, *a, **kw)

	@action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
	def submit(self, request, pk=None):
		a = self.get_object()
		u = request.user
		if u.role != User.Role.STUDENT:
			raise PermissionDenied("Faqat student submit qiladi")
		if u.group_id is None or not a.groups.filter(pk=u.group_id).exists():
			raise PermissionDenied("Bu vazifa sizning guruhingizga berilmagan")
		if timezone.now() > a.deadline:
			raise ValidationError("Deadline o'tgan")
		s = SubmitSerializer(data=request.data)
		s.is_valid(raise_exception=True)
		sub, _ = Submission.objects.update_or_create(
			assignment=a, student=u, defaults={"file": s.validated_data["file"]}
		)
		return Response(
			SubmissionSerializer(sub, context={"request": request}).data,
			status=status.HTTP_201_CREATED,
		)


class SubmissionViewSet(viewsets.ReadOnlyModelViewSet):
	serializer_class = SubmissionSerializer
	permission_classes = [IsAuthenticated]
	pagination_class = None

	def get_queryset(self):
		qs = Submission.objects.select_related(
			"assignment", "student", "graded_by"
		).order_by("-submitted_at")
		u = self.request.user
		if u.role == User.Role.STUDENT:
			return qs.filter(student=u)
		if u.role == User.Role.TEACHER:
			return qs.filter(assignment__teacher=u)
		return qs

	@action(detail=True, methods=["post"], permission_classes=[IsTeacherOrAdmin])
	def grade(self, request, pk=None):
		sub = self.get_object()
		u = request.user
		if u.role == User.Role.TEACHER and sub.assignment.teacher_id != u.id:
			raise PermissionDenied()
		s = GradeSerializer(data=request.data)
		s.is_valid(raise_exception=True)
		sub.grade = s.validated_data["grade"]
		sub.feedback = s.validated_data.get("feedback", "")
		sub.graded_by = u
		sub.graded_at = timezone.now()
		sub.save(update_fields=["grade", "feedback", "graded_by", "graded_at"])
		return Response(SubmissionSerializer(sub, context={"request": request}).data)
