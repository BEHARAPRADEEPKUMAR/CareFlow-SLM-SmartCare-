from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from appointments.models import Appointment


class DoctorAppointmentsView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        doctor_account = getattr(
            request.user,
            "doctor_account",
            None,
        )

        if doctor_account is None:
            return Response(
                {
                    "error": "Doctor access required."
                },
                status=403,
            )

        doctor = doctor_account.doctor

        appointments = (
            Appointment.objects
            .select_related(
                "patient",
                "doctor",
                "doctor__department",
            )
            .filter(
                doctor=doctor
            )
            .order_by(
                "appointment_date",
                "appointment_time",
            )
        )

        data = []

        for appointment in appointments:

            profile = getattr(
                appointment.patient,
                "patient_profile",
                None,
            )

            patient_name = (
                profile.full_name
                if profile and profile.full_name
                else (
                    appointment.patient.get_full_name()
                    or appointment.patient.email
                )
            )

            patient_mobile = (
                profile.phone
                if profile
                else ""
            )

            data.append(
                {
                    "id": appointment.id,
                    "patient_name": patient_name,
                    "patient_mobile": patient_mobile,
                    "patient_email": appointment.patient.email,
                    "doctor_name": doctor.name,
                    "department": doctor.department.name,
                    "appointment_date": appointment.appointment_date,
                    "appointment_time": appointment.appointment_time,
                    "status": appointment.status,
                    "reason": appointment.reason,
                }
            )

        return Response(data)