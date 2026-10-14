from django.contrib.auth.models import User
from django.db import models

from doctors.models import Doctor


class PatientProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="patient_profile",
    )

    full_name = models.CharField(
        max_length=150,
        blank=True,
    )

    phone = models.CharField(
        max_length=20,
        blank=True,
    )

    blood_group = models.CharField(
        max_length=5,
        blank=True,
        default="",
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return (
            self.full_name
            or self.user.get_full_name()
            or self.user.email
            or self.user.username
        )


class DoctorAccount(models.Model):
    """
    Connects an existing Doctor record with
    a Django User account used for doctor login.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="doctor_account",
    )

    doctor = models.OneToOneField(
        Doctor,
        on_delete=models.CASCADE,
        related_name="account",
    )

    def __str__(self):
        return f"Dr. {self.doctor.name}"