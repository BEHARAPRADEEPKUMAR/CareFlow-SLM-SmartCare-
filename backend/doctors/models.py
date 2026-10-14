from django.conf import settings
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Doctor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="doctor_profile")
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True, default="")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="doctors")
    qualification = models.CharField(max_length=200, blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Dr. {self.name}"


class DoctorAvailability(models.Model):
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name="availability",
    )
    # Date-specific availability; NULL means a legacy weekly schedule.
    date = models.DateField(null=True, blank=True)
    weekday = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="0=Monday ... 6=Sunday for recurring availability",
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_minutes = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        day = self.date or self.weekday
        return f"{self.doctor} — {day}: {self.start_time}-{self.end_time}"