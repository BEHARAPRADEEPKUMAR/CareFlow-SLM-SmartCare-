from django.db import models
from appointments.models import Appointment


class Reminder(models.Model):

    REMINDER_TYPES = [
        ("APPOINTMENT", "Appointment Reminder"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SENT", "Sent"),
        ("CANCELLED", "Cancelled"),
    ]

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="reminders",
    )

    reminder_type = models.CharField(
        max_length=30,
        choices=REMINDER_TYPES,
        default="APPOINTMENT",
    )

    reminder_date = models.DateField()

    reminder_time = models.TimeField()

    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    sent_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = [
            "reminder_date",
            "reminder_time",
        ]

    def __str__(self):
        return (
            f"Reminder for appointment "
            f"{self.appointment_id} - "
            f"{self.reminder_date} "
            f"{self.reminder_time}"
        )