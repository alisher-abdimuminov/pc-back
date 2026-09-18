from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from rest_framework.exceptions import ValidationError

from academics.models import Group

from .models import User


class HemisClient:
	def __init__(self, authorize_url, access_token_url, resource_owner_url):
		cfg = settings.HEMIS
		self.client_id = cfg["CLIENT_ID"]
		self.client_secret = cfg["CLIENT_SECRET"]
		self.redirect_uri = cfg["REDIRECT_URI"]
		self.authorize_url = authorize_url
		self.access_token_url = access_token_url
		self.resource_owner_url = resource_owner_url

	def authorization_url(self):
		return f"{self.authorize_url}?{urlencode({'client_id': self.client_id, 'redirect_uri': self.redirect_uri, 'response_type': 'code'})}"

	def get_access_token(self, code):
		data = {
			"client_id": self.client_id,
			"client_secret": self.client_secret,
			"code": code,
			"redirect_uri": self.redirect_uri,
			"grant_type": "authorization_code",
		}
		print(self.access_token_url)
		print(data)
		r = requests.post(
			self.access_token_url,
			data={
				"client_id": self.client_id,
				"client_secret": self.client_secret,
				"code": code,
				"redirect_uri": self.redirect_uri,
				"grant_type": "authorization_code",
			},
			timeout=15,
		)
		print(r.text)
		r.raise_for_status()
		data = r.json()
		if not data.get("access_token"):
			raise ValidationError("HEMIS access_token qaytarmadi")
		return data["access_token"]

	def get_user_details(self, token):
		r = requests.get(
			self.resource_owner_url,
			headers={"Authorization": f"Bearer {token}"},
			timeout=15,
		)

		print(r.text)

		r.raise_for_status()
		return r.json()


def get_client(kind):
	c = settings.HEMIS
	if kind == "teacher":
		return HemisClient(
			c["TEACHER_AUTHORIZE_URL"],
			c["TEACHER_ACCESS_TOKEN_URL"],
			c["TEACHER_RESOURCE_OWNER_URL"],
		)
	return HemisClient(
		c["STUDENT_AUTHORIZE_URL"],
		c["STUDENT_ACCESS_TOKEN_URL"],
		c["STUDENT_RESOURCE_OWNER_URL"],
	)


def download_profile_image(user, url):
	if not url or (user.hemis_image_url == url and user.image):
		return
	parsed = urlparse(url)
	if parsed.scheme not in {"http", "https"}:
		raise ValidationError("HEMIS image URL noto'g'ri")
	allowed = settings.HEMIS.get("IMAGE_ALLOWED_HOSTS", [])
	if allowed and parsed.hostname and parsed.hostname.lower() not in allowed:
		raise ValidationError("HEMIS image host ruxsat etilmagan")
	try:
		with requests.get(url, stream=True, timeout=15) as r:
			r.raise_for_status()
			ctype = r.headers.get("content-type", "").split(";")[0].lower()
			if ctype not in {"image/jpeg", "image/png", "image/webp"}:
				raise ValidationError("HEMIS rasm formati qo'llab-quvvatlanmaydi")
			maxb = settings.MAX_HEMIS_IMAGE_BYTES
			chunks = []
			total = 0
			for chunk in r.iter_content(65536):
				total += len(chunk)
				if total > maxb:
					raise ValidationError("HEMIS rasm hajmi juda katta")
				chunks.append(chunk)
		ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[ctype]
		user.image.save(
			f"hemis-{user.username}.{ext}", ContentFile(b"".join(chunks)), save=False
		)
		user.hemis_image_url = url
	except requests.RequestException as exc:
		raise ValidationError(f"HEMIS rasmini yuklab bo'lmadi: {exc}")


def sync_hemis_user(details, kind):
	data = details.get("data") or {}
	is_teacher = kind == "teacher"
	username = details.get("login") if is_teacher else details.get("student_id_number")
	if not username:
		raise ValidationError("HEMIS user ID topilmadi")
	defaults = {
		"full_name": details.get("name") or "",
		"phone_number": details.get("phone") or "",
		"passport_number": details.get("passport_number") or "",
		"birth_date": details.get("birth_date") or "",
		"role": User.Role.TEACHER if is_teacher else User.Role.STUDENT,
	}
	user, _ = User.objects.get_or_create(username=str(username), defaults=defaults)
	for k, v in defaults.items():
		setattr(user, k, v)
	if not is_teacher:
		group_name = ((data.get("group") or {}).get("name") or "").strip()
		if group_name:
			group, _ = Group.objects.get_or_create(name=group_name)
			user.group = group
		user.course = str((data.get("level") or {}).get("name") or "")
		user.faculty = str((data.get("faculty") or {}).get("name") or "")
		user.payment_method = str((data.get("paymentForm") or {}).get("name") or "")
		try:
			user.gap = (
				float(data.get("avg_gpa")) if data.get("avg_gpa") is not None else None
			)
		except (TypeError, ValueError):
			user.gap = None
	download_profile_image(user, details.get("picture_full"))
	user.set_unusable_password()
	user.save()
	return user
