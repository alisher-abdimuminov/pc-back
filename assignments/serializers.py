from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from accounts.models import User

from .models import Assignment, Submission


class AssignmentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)
    submitted = serializers.SerializerMethodField()
    my_submission_id = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            "id",
            "teacher",
            "teacher_name",
            "title",
            "description",
            "file",
            "deadline",
            "groups",
            "submitted",
            "my_submission_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["teacher", "submitted", "my_submission_id"]

    def get_submitted(self, obj):
        r = self.context.get("request")
        return bool(
            r
            and r.user.is_authenticated
            and r.user.role == "student"
            and obj.submissions.filter(student=r.user).exists()
        )

    def get_my_submission_id(self, obj):
        r = self.context.get("request")
        s = (
            obj.submissions.filter(student=r.user).first()
            if r and r.user.is_authenticated and r.user.role == "student"
            else None
        )
        return s.id if s else None

    def validate_groups(self, groups):
        r = self.context["request"]
        if r.user.role == User.Role.TEACHER and any(
            g.teacher_id != r.user.id for g in groups
        ):
            raise serializers.ValidationError(
                "Faqat o'zingizga biriktirilgan guruhlarni tanlang"
            )
        return groups


class SubmissionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    assignment_title = serializers.CharField(source="assignment.title", read_only=True)

    class Meta:
        model = Submission
        fields = [
            "id",
            "assignment",
            "assignment_title",
            "student",
            "student_name",
            "file",
            "submitted_at",
            "grade",
            "feedback",
            "graded_at",
            "graded_by",
        ]
        read_only_fields = [
            "student",
            "submitted_at",
            "grade",
            "feedback",
            "graded_at",
            "graded_by",
        ]


class SubmitSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, f):
        if f.size > settings.MAX_ASSIGNMENT_FILE_BYTES:
            raise serializers.ValidationError("Fayl juda katta")
        return f


class GradeSerializer(serializers.Serializer):
    grade = serializers.FloatField(min_value=0, max_value=100)
    feedback = serializers.CharField(required=False, allow_blank=True)
