from rest_framework import serializers

from accounts.models import User

from .models import Group, Location, Schedule


class GroupSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)
    student_count = serializers.IntegerField(source="students.count", read_only=True)

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "teacher",
            "teacher_name",
            "student_count",
            "created_at",
        ]

    def validate_teacher(self, v):
        if v and v.role != User.Role.TEACHER:
            raise serializers.ValidationError("Faqat teacher biriktiriladi")
        return v


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = "__all__"


class ScheduleSerializer(serializers.ModelSerializer):
    location_detail = LocationSerializer(source="location", read_only=True)
    group_details = GroupSerializer(source="groups", many=True, read_only=True)

    class Meta:
        model = Schedule
        fields = [
            "id",
            "weekday",
            "location",
            "location_detail",
            "groups",
            "group_details",
            "is_active",
            "created_at",
        ]

    def validate(self, attrs):
        weekday = attrs.get("weekday", getattr(self.instance, "weekday", None))
        groups = attrs.get("groups")
        if groups is not None:
            qs = Schedule.objects.filter(
                weekday=weekday, is_active=True, groups__in=groups
            ).distinct()
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "Tanlangan guruhlardan kamida bittasida shu hafta kuni aktiv jadval mavjud"
                )
        return attrs


class StudentListSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "full_name",
            "phone_number",
            "passport_number",
            "group",
            "group_name",
            "birth_date",
            "course",
            "faculty",
            "payment_method",
            "gap",
            "image",
        ]
