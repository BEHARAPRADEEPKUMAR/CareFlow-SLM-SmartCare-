from datetime import datetime

from django.db.models import Q

from django.utils import timezone

from django.utils.dateparse import parse_date, parse_time

from rest_framework import viewsets

from rest_framework.exceptions import PermissionDenied

from rest_framework.permissions import IsAuthenticated

from rest_framework.response import Response

from rest_framework import status as http_status

from users.models import PatientProfile, DoctorAccount

from .models import Appointment

from .serializers import AppointmentSerializer

from rest_framework.exceptions import ValidationError

ACTIVE_STATUSES = {"SCHEDULED", "CONFIRMED", "RESCHEDULED"}

FINAL_STATUSES = {"CANCELLED", "COMPLETED"}

def mark_elapsed_appointments_completed():

    """

    Mark active appointments as COMPLETED once their scheduled date/time

    has passed. This runs when the appointment API is accessed.

    """

    now = timezone.localtime()

    today = now.date()

    current_time = now.time().replace(tzinfo=None)

    Appointment.objects.filter(

        Q(appointment_date__lt=today)

        | Q(appointment_date=today, appointment_time__lt=current_time),

        status__in=ACTIVE_STATUSES,

    ).update(status="COMPLETED")

class AppointmentViewSet(viewsets.ModelViewSet):

    serializer_class = AppointmentSerializer

    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        # Refresh lifecycle statuses before returning the appointment list.

        mark_elapsed_appointments_completed()

        user = self.request.user

        queryset = (

            Appointment.objects

            .select_related(

                "doctor",

                "doctor__department",

                "patient",

            )

            .order_by(

                "appointment_date",

                "appointment_time",

            )

        )

        doctor_account = (

            DoctorAccount.objects

            .filter(user=user)

            .select_related("doctor")

            .first()

        )

        if doctor_account:

            return queryset.filter(doctor=doctor_account.doctor)

        patient_profile = PatientProfile.objects.filter(user=user).first()

        if patient_profile:

            return queryset.filter(patient=user)

        return queryset.none()

    def perform_create(self, serializer):

        user = self.request.user

        patient_profile = PatientProfile.objects.filter(user=user).first()

        if not patient_profile:

            raise PermissionDenied(

                "Only registered patients can create appointments."

            )

        appointment_date = serializer.validated_data.get("appointment_date")

        appointment_time = serializer.validated_data.get("appointment_time")

        doctor = serializer.validated_data.get("doctor")

        if appointment_date and appointment_time:

            now = timezone.localtime()

            if (appointment_date, appointment_time) <= (

                now.date(), now.time().replace(tzinfo=None)

            ):

                raise PermissionDenied(

                    "Please choose a future appointment slot."

                )

        # Prevent one patient from holding two active appointments at the same date/time,
        # even when the appointments are with different doctors.
        if Appointment.objects.filter(
            patient=user,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
        ).exclude(status__in=FINAL_STATUSES).exists():
            raise ValidationError({
                "detail": (
                    "You already have an appointment on this date and at this time. "
                    "Please choose another day or time."
                )
            })

        if Appointment.objects.filter(

            doctor=doctor,

            appointment_date=appointment_date,

            appointment_time=appointment_time,

        ).exclude(status__in=FINAL_STATUSES).exists():

            raise PermissionDenied(

                "That slot is already booked. Please select an available slot."

            )

        serializer.save(patient=user)

    def update(self, request, *args, **kwargs):

        appointment = self.get_object()

        user = request.user

        doctor_account = (

            DoctorAccount.objects

            .filter(user=user)

            .select_related("doctor")

            .first()

        )

        patient_profile = PatientProfile.objects.filter(user=user).first()

        # Doctor actions: doctors may change status for their own appointments.

        if doctor_account:

            if appointment.doctor_id != doctor_account.doctor_id:

                raise PermissionDenied(

                    "You can only manage your own appointments."

                )

            new_status = request.data.get("status")

            allowed_statuses = {"CONFIRMED", "COMPLETED", "CANCELLED"}

            if new_status not in allowed_statuses:

                return Response(

                    {

                        "success": False,

                        "message": (

                            "Doctors can only change appointment status to "

                            "CONFIRMED, COMPLETED or CANCELLED."

                        ),

                    },

                    status=http_status.HTTP_400_BAD_REQUEST,

                )

            if appointment.status in FINAL_STATUSES:

                return Response(

                    {

                        "success": False,

                        "message": (

                            f"This appointment is already {appointment.status.lower()}. "

                            "Its status cannot be changed."

                        ),

                    },

                    status=http_status.HTTP_400_BAD_REQUEST,

                )

            appointment.status = new_status

            appointment.save(update_fields=["status", "updated_at"])

            return Response({

                "success": True,

                "message": f"Appointment marked as {new_status}.",

                "appointment": self.get_serializer(appointment).data,

            })

        # Patient actions.

        if patient_profile:

            if appointment.patient_id != user.id:

                raise PermissionDenied(

                    "You can only manage your own appointments."

                )

            new_status = request.data.get("status")

            if new_status == "CANCELLED":

                if appointment.status in FINAL_STATUSES:

                    return Response(

                        {

                            "success": False,

                            "message": (

                                f"This appointment is already "

                                f"{appointment.status.lower()} and cannot be cancelled again."

                            ),

                        },

                        status=http_status.HTTP_400_BAD_REQUEST,

                    )

                appointment.status = "CANCELLED"

                appointment.save(update_fields=["status", "updated_at"])

                return Response({

                    "success": True,

                    "message": "Appointment cancelled successfully.",

                    "appointment": self.get_serializer(appointment).data,

                })

            if new_status in {"RESCHEDULED", "SCHEDULED"}:

                if appointment.status in FINAL_STATUSES:

                    return Response(

                        {

                            "success": False,

                            "action": "BOOK_NEW_APPOINTMENT",

                            "message": (

                                f"This appointment is already "

                                f"{appointment.status.lower()}. "

                                "It cannot be rescheduled. Please select one of "

                                "the available slots below to book a new appointment."

                            ),

                            "appointment": self.get_serializer(appointment).data,

                            "show_available_slots": True,

                        },

                        status=http_status.HTTP_400_BAD_REQUEST,

                    )

                new_date_raw = request.data.get("appointment_date")

                new_time_raw = request.data.get("appointment_time")

                if not new_date_raw or not new_time_raw:

                    return Response(

                        {

                            "success": False,

                            "message": (

                                "Please select a new appointment date and time "

                                "from the available slots below."

                            ),

                            "show_available_slots": True,

                        },

                        status=http_status.HTTP_400_BAD_REQUEST,

                    )

                new_date = parse_date(str(new_date_raw))

                new_time = parse_time(str(new_time_raw))

                if not new_date or not new_time:

                    return Response(

                        {

                            "success": False,

                            "message": "The selected date or time is invalid. Please choose an available slot.",

                            "show_available_slots": True,

                        },

                        status=http_status.HTTP_400_BAD_REQUEST,

                    )

                now = timezone.localtime()

                if (new_date, new_time) <= (

                    now.date(), now.time().replace(tzinfo=None)

                ):

                    return Response(

                        {

                            "success": False,

                            "message": "Please select a future date and time.",

                            "show_available_slots": True,

                        },

                        status=http_status.HTTP_400_BAD_REQUEST,

                    )

                existing = Appointment.objects.filter(

                    doctor=appointment.doctor,

                    appointment_date=new_date,

                    appointment_time=new_time,

                ).exclude(

                    id=appointment.id

                ).exclude(

                    status__in=FINAL_STATUSES

                )

                if existing.exists():

                    return Response(

                        {

                            "success": False,

                            "message": (

                                "That slot is no longer available. "

                                "Please select one of the available slots below."

                            ),

                            "show_available_slots": True,

                        },

                        status=http_status.HTTP_400_BAD_REQUEST,

                    )

                appointment.appointment_date = new_date

                appointment.appointment_time = new_time

                appointment.status = "RESCHEDULED"

                appointment.save(update_fields=[

                    "appointment_date",

                    "appointment_time",

                    "status",

                    "updated_at",

                ])

                return Response({

                    "success": True,

                    "message": "Appointment rescheduled successfully.",

                    "appointment": self.get_serializer(appointment).data,

                })

            return Response(

                {

                    "success": False,

                    "message": (

                        "Patients can only cancel or reschedule appointments."

                    ),

                },

                status=http_status.HTTP_400_BAD_REQUEST,

            )

        return Response(

            {

                "success": False,

                "message": "User role could not be determined.",

            },

            status=http_status.HTTP_403_FORBIDDEN,

        )

    def partial_update(self, request, *args, **kwargs):

        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):

        return Response(

            {

                "success": False,

                "message": (

                    "Appointments cannot be permanently deleted. "

                    "Please cancel the appointment instead."

                ),

            },

            status=http_status.HTTP_400_BAD_REQUEST,

        )
