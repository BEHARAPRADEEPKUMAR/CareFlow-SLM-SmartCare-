
from datetime import datetime, timedelta

from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.models import Appointment

from .models import Reminder
from .serializers import ReminderSerializer
from .services import process_due_reminders


ACTIVE_APPOINTMENT_STATUSES = [
    "SCHEDULED",
    "CONFIRMED",
    "RESCHEDULED",
]


class ReminderListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reminders = Reminder.objects.select_related(
            "appointment",
            "appointment__doctor",
        )

        if hasattr(request.user, "patient_profile"):
            reminders = reminders.filter(
                appointment__patient=request.user,
            )
        elif hasattr(request.user, "doctor_profile"):
            reminders = reminders.filter(
                appointment__doctor__user=request.user,
            )
        else:
            # Do not expose other patients' reminders.
            reminders = reminders.none()

        reminders = reminders.order_by(
            "reminder_date",
            "reminder_time",
        )

        serializer = ReminderSerializer(
            reminders,
            many=True,
        )
        return Response(serializer.data)

    def post(self, request):
        if not hasattr(request.user, "patient_profile"):
            return Response(
                {"error": "Only patients can create reminders."},
                status=status.HTTP_403_FORBIDDEN,
            )

        appointment_id = request.data.get("appointment")

        if not appointment_id:
            return Response(
                {"error": "appointment is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            appointment = (
                Appointment.objects
                .select_related("doctor")
                .get(
                    id=appointment_id,
                    patient=request.user,
                    status__in=ACTIVE_APPOINTMENT_STATUSES,
                )
            )
        except (Appointment.DoesNotExist, ValueError, TypeError):
            return Response(
                {"error": "Active appointment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        existing = Reminder.objects.filter(
            appointment=appointment,
            reminder_type="APPOINTMENT",
            status="PENDING",
        ).first()

        if existing:
            return Response(
                {
                    "message": "Reminder already exists.",
                    "reminder": ReminderSerializer(existing).data,
                },
                status=status.HTTP_200_OK,
            )

        appointment_datetime = datetime.combine(
            appointment.appointment_date,
            appointment.appointment_time,
        )

        if timezone.is_naive(appointment_datetime):
            appointment_datetime = timezone.make_aware(
                appointment_datetime,
                timezone.get_current_timezone(),
            )

        reminder_datetime = (
            appointment_datetime - timedelta(days=1)
        )

        message = (
            f"Reminder: You have an appointment with "
            f"Dr. {appointment.doctor.name} on "
            f"{appointment.appointment_date} at "
            f"{appointment.appointment_time}."
        )

        reminder = Reminder.objects.create(
            appointment=appointment,
            reminder_type="APPOINTMENT",
            reminder_date=reminder_datetime.date(),
            reminder_time=reminder_datetime.time(),
            message=message,
            status="PENDING",
        )

        return Response(
            ReminderSerializer(reminder).data,
            status=status.HTTP_201_CREATED,
        )


class ProcessReminderWorkflowView(APIView):
    # IsAdminUser requires an authenticated active staff user.
    permission_classes = [IsAdminUser]

    def post(self, request):
        processed = process_due_reminders()

        return Response(
            {
                "workflow": "appointment_reminder",
                "processed_count": len(processed),
                "processed": processed,
            },
            status=status.HTTP_200_OK,
        )
