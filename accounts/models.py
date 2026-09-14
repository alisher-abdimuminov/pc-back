from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        TEACHER = "teacher", "Teacher"
        STUDENT = "student", "Student"

    full_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    passport_number = models.CharField(max_length=100, blank=True)
    group = models.ForeignKey(
        "academics.Group",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="students",
    )
    birth_date = models.CharField(max_length=50, blank=True)
    course = models.CharField(max_length=100, blank=True)
    faculty = models.CharField(max_length=255, blank=True)
    payment_method = models.CharField(max_length=100, blank=True)
    gpa = models.FloatField(null=True, blank=True, help_text="HEMIS GPA")
    image = models.ImageField(upload_to="users/%Y/%m/", null=True, blank=True)
    hemis_image_url = models.URLField(max_length=1000, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        if self.role != self.Role.STUDENT:
            self.group = None
            self.course = ""
            self.faculty = ""
            self.payment_method = ""
            self.gap = None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name or self.username
