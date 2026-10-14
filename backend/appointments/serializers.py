from rest_framework import serializers

from .models import Appointment


class AppointmentSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(
        source="doctor.name",
        read_only=True,
    )

    department_name = serializers.CharField(
        source="doctor.department.name",
        read_only=True,
    )

    patient_name = serializers.SerializerMethodField()

    patient_email = serializers.EmailField(
        source="patient.email",
        read_only=True,
    )

    patient_mobile = serializers.SerializerMethodField()

    class Meta:
        model = Appointment

        fields = [
            "id",
            "appointment_id",

            # Patient information
            "patient",
            "patient_name",
            "patient_email",
            "patient_mobile",

            # Doctor information
            "doctor",
            "doctor_name",
            "department_name",

            # Appointment information
            "appointment_date",
            "appointment_time",
            "status",
            "reason",

            # Timestamps
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "appointment_id",

            "patient",
            "patient_name",
            "patient_email",
            "patient_mobile",

            "doctor_name",
            "department_name",

            "created_at",
            "updated_at",
        ]

    def get_patient_name(self, obj):
        """
        Get the patient's full name from PatientProfile.
        """

        profile = getattr(
            obj.patient,
            "patientprofile",
            None,
        )

        if profile and profile.full_name:
            return profile.full_name

        return (
            obj.patient.get_full_name()
            or obj.patient.email
        )

    def get_patient_mobile(self, obj):
        """
        Get the patient's phone number from PatientProfile.
        """

        profile = getattr(
            obj.patient,
            "patientprofile",
            None,
        )

        if profile:
            return profile.phone

        return ""

    def validate(self, attrs):
        """
        Prevent double-booking the same doctor
        at the same date and time.
        """

        doctor = (
            attrs.get("doctor")
            or getattr(
                self.instance,
                "doctor",
                None,
            )
        )

        appointment_date = (
            attrs.get("appointment_date")
            or getattr(
                self.instance,
                "appointment_date",
                None,
            )
        )

        appointment_time = (
            attrs.get("appointment_time")
            or getattr(
                self.instance,
                "appointment_time",
                None,
            )
        )

        if (
            doctor
            and appointment_date
            and appointment_time
        ):
            queryset = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
            ).exclude(
                status="CANCELLED"
            )

            # When updating an existing appointment,
            # don't compare the appointment against itself.
            if self.instance:
                queryset = queryset.exclude(
                    pk=self.instance.pk
                )

            if queryset.exists():
                raise serializers.ValidationError(
                    "That doctor already has an appointment at this time."
                )

        return attrs