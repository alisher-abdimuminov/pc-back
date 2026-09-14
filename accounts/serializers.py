from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)
    image_url = serializers.SerializerMethodField()

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
            "gpa",
            "image",
            "image_url",
            "role",
            "is_active",
        ]
        read_only_fields = ["image_url"]

    def get_image_url(self, obj):
        if not obj.image:
            return None
        req = self.context.get("request")
        return req.build_absolute_uri(obj.image.url) if req else obj.image.url


class AdminUserUpdateSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        read_only_fields = ["username", "role", "image_url"]
