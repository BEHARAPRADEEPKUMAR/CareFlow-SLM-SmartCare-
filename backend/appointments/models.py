import uuid
from django.contrib.auth.models import User
from django.db import models
from doctors.models import Doctor

class Appointment(models.Model):
    STATUS_CHOICES = [
    ("SCHEDULED", "Scheduled"),
    ("CONFIRMED", "Confirmed"),
    ("COMPLETED", "Completed"),
    ("CANCELLED", "Cancelled"),
    ("RESCHEDULED", "Rescheduled"),
    ]
    appointment_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="appointments")
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name="appointments")
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    status = models.CharField(
    max_length=20,
    choices=STATUS_CHOICES,
    default="SCHEDULED",
    )
    reason = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: ordering = ["appointment_date","appointment_time"]
