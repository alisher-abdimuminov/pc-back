from django.contrib.auth import authenticate
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .hemis import get_client, sync_hemis_user
from .models import User
from .permissions import IsAdmin
from .serializers import UserSerializer


def tokens_for(user):
	refresh = RefreshToken.for_user(user)
	return {"access": str(refresh.access_token), "refresh": str(refresh)}


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
	user = authenticate(
		username=request.data.get("username"), password=request.data.get("password")
	)
	if not user:
		return Response({"detail": "Username yoki parol noto'g'ri"}, status=400)
	return Response(
		{
			"user": UserSerializer(user, context={"request": request}).data,
			"tokens": tokens_for(user),
		}
	)


@api_view(["GET"])
@permission_classes([AllowAny])
def hemis_authorize(request):
	kind = request.query_params.get("type", "student")
	if kind not in {"student", "teacher"}:
		return Response(
			{"detail": "type student yoki teacher bo'lishi kerak"}, status=400
		)
	return Response({"authorize_url": get_client(kind).authorization_url()})


@api_view(["POST"])
@permission_classes([AllowAny])
def hemis_callback(request):
	print("----")
	print(request.data)
	print("----")
	code = request.data.get("code")
	kind = request.data.get("type", "student")
	if not code or kind not in {"student", "teacher"}:
		return Response({"detail": "code va to'g'ri type majburiy"}, status=400)
	try:
		client = get_client(kind)
		token = client.get_access_token(code)
		details = client.get_user_details(token)
		user = sync_hemis_user(details, kind)
	except Exception as exc:
		return Response({"detail": str(exc)}, status=400)
	return Response(
		{
			"user": UserSerializer(user, context={"request": request}).data,
			"tokens": tokens_for(user),
		}
	)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
	return Response(UserSerializer(request.user, context={"request": request}).data)


class UserViewSet(viewsets.ModelViewSet):
	serializer_class = UserSerializer
	permission_classes = [IsAdmin]

	http_method_names = [
		"get",
		"patch",
		"head",
		"options",
	]

	def get_queryset(self):
		queryset = (
			User.objects.select_related("group")
			.filter(
				role__in=[
					User.Role.STUDENT,
					User.Role.TEACHER,
				]
			)
			.order_by(
				"full_name",
				"username",
			)
		)

		user_type = self.request.query_params.get("type")

		if user_type == "teacher":
			return queryset.filter(role=User.Role.TEACHER)

		if user_type in [
			"student",
			"talaba",
		]:
			return queryset.filter(role=User.Role.STUDENT)

		return queryset

	def paginate_queryset(self, queryset):
		user_type = self.request.query_params.get("type")

		# Teacher list Select uchun ishlatiladi.
		# Barcha teacherlar bir requestda keladi.
		if user_type == "teacher":
			return None

		return super().paginate_queryset(queryset)
