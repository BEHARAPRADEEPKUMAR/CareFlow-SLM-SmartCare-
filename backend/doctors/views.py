
from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import date as date_type, datetime
from appointments.models import Appointment
from .models import Department, Doctor, DoctorAvailability
from .serializers import DepartmentSerializer, DoctorSerializer


class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Department.objects.all().order_by("name")
    serializer_class = DepartmentSerializer


class DoctorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Doctor.objects.select_related("department")
        .filter(is_active=True)
        .order_by("name")
    )
    serializer_class = DoctorSerializer
    permission_classes = [AllowAny]


def get_doctor_for_user(user):
    """Return the doctor profile belonging to the authenticated user."""
    try:
        return Doctor.objects.select_related("department").get(
            user=user,
            is_active=True,
        )
    except Doctor.DoesNotExist:
        return None


def serialize_availability(item):
    weekdays = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]
    return {
        "id": item.id,
        "doctor_id": item.doctor_id,
        "date": item.date.isoformat() if item.date else None,
        "weekday": item.weekday,
        "weekday_name": (
            item.date.strftime("%A")
            if item.date
            else weekdays[item.weekday]
            if item.weekday is not None
            else None
        ),
        "start_time": item.start_time.strftime("%H:%M"),
        "end_time": item.end_time.strftime("%H:%M"),
        "slot_minutes": item.slot_minutes,
        "slot_duration": item.slot_minutes,
        "is_active": item.is_active,
    }


class DoctorAvailabilityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        doctor = get_doctor_for_user(request.user)

        if doctor is None:
            return Response(
                {"error": "Your account is not linked to an active doctor profile."},
                status=status.HTTP_403_FORBIDDEN,
            )

        items = DoctorAvailability.objects.filter(
            doctor=doctor,
            is_active=True,
        ).order_by("date", "weekday", "start_time")

        return Response([serialize_availability(item) for item in items])

    def post(self, request):
        doctor = get_doctor_for_user(request.user)
        if doctor is None:
            return Response(
                {"error": "Your account is not linked to an active doctor profile."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data

        try:
            selected_date = date_type.fromisoformat(str(data.get("date", "")))
            start_time = datetime.strptime(
                str(data.get("start_time", "")), "%H:%M"
            ).time()
            end_time = datetime.strptime(
                str(data.get("end_time", "")), "%H:%M"
            ).time()
            slot_duration = int(data.get("slot_duration", 30))
        except (TypeError, ValueError):
            return Response(
                {
                    "error": (
                        "Provide date as YYYY-MM-DD, start_time and end_time "
                        "as HH:MM, and a valid slot_duration."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if selected_date < timezone.localdate():
            return Response(
                {"error": "Availability cannot be released for a past date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if start_time >= end_time:
            return Response(
                {"error": "End time must be later than start time."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if slot_duration not in (15, 20, 30, 45, 60):
            return Response(
                {"error": "slot_duration must be 15, 20, 30, 45, or 60."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_minutes = start_time.hour * 60 + start_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute

        if (end_minutes - start_minutes) < slot_duration:
            return Response(
                {"error": "The availability period must fit at least one appointment."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reject overlapping active date-specific availability.
        overlapping = DoctorAvailability.objects.filter(
            doctor=doctor,
            date=selected_date,
            is_active=True,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )

        if overlapping.exists():
            return Response(
                {"error": "These hours overlap with availability already released for this date."},
                status=status.HTTP_409_CONFLICT,
            )

        item = DoctorAvailability.objects.create(
            doctor=doctor,
            date=selected_date,
            weekday=selected_date.weekday(),
            start_time=start_time,
            end_time=end_time,
            slot_minutes=slot_duration,
            is_active=True,
        )

        return Response(
            {
                "message": "Date-specific availability released successfully.",
                "availability": serialize_availability(item),
            },
            status=status.HTTP_201_CREATED,
        )


class DoctorAvailabilityDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        doctor = get_doctor_for_user(request.user)

        if doctor is None:
            return Response(
                {"error": "Your account is not linked to an active doctor profile."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            item = DoctorAvailability.objects.get(pk=pk, doctor=doctor)
        except DoctorAvailability.DoesNotExist:
            return Response(
                {"error": "Availability not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Weekly availability may cover future appointments. Do not disable
        # it if a non-cancelled, non-completed appointment falls in its hours.
        appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_time__gte=item.start_time,
            appointment_time__lt=item.end_time,
        ).exclude(
            status__in=["CANCELLED", "COMPLETED"]
        )

        # Django's week_day numbering: Sunday=1, Monday=2, ..., Saturday=7.
        django_weekday = (item.weekday + 1) % 7 + 1
        appointments = appointments.filter(
            appointment_date__week_day=django_weekday
        )

        if appointments.exists():
            return Response(
                {
                    "error": (
                        "This weekly availability overlaps with appointments. "
                        "Keep it active until those appointments are handled."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        item.is_active = False
        item.save(update_fields=["is_active"])

        return Response(
            {"message": "Availability disabled successfully."},
            status=status.HTTP_200_OK,
        )


class DoctorAppointmentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        doctor = get_doctor_for_user(request.user)

        if doctor is None:
            return Response(
                {"error": "Only doctors can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        appointments = (
            Appointment.objects
            .select_related("doctor", "doctor__department", "patient")
            .filter(doctor=doctor)
            .order_by("appointment_date", "appointment_time")
        )

        result = []

        for appointment in appointments:
            patient_profile = getattr(
                appointment.patient, "patient_profile", None
            )

            result.append({
                "id": appointment.id,
                "patient_id": appointment.patient.id,
                "patient_name": (
                    appointment.patient.get_full_name()
                    or getattr(patient_profile, "full_name", "")
                    or appointment.patient.email
                ),
                "patient_email": appointment.patient.email,
                "patient_mobile": (
                    getattr(patient_profile, "mobile", "")
                    or getattr(patient_profile, "phone", "")
                ),
                "doctor_id": appointment.doctor.id,
                "doctor_name": appointment.doctor.name,
                "department": appointment.doctor.department.name,
                "appointment_date": str(appointment.appointment_date),
                "appointment_time": str(appointment.appointment_time),
                "status": appointment.status,
                "reason": appointment.reason,
            })

        return Response(result)