from datetime import datetime, timedelta

from django.utils import timezone

from .models import Reminder


# ============================================================
# CREATE APPOINTMENT REMINDER
# ============================================================

def create_appointment_reminder(appointment):
    """
    Create an appointment reminder for an active appointment.

    The reminder is scheduled exactly 24 hours before
    the appointment.

    If a pending reminder already exists, return it instead
    of creating a duplicate.
    """

    # --------------------------------------------------------
    # Validate appointment status
    # --------------------------------------------------------

    if appointment.status not in [
        "SCHEDULED",
        "CONFIRMED",
        "RESCHEDULED",
    ]:
        return None, "Appointment is not currently active."

    # --------------------------------------------------------
    # Check for existing pending reminder
    # --------------------------------------------------------

    existing_reminder = Reminder.objects.filter(
        appointment=appointment,
        reminder_type="APPOINTMENT",
        status="PENDING",
    ).first()

    if existing_reminder:

        return (
            existing_reminder,
            "Reminder already exists.",
        )

    # --------------------------------------------------------
    # Build appointment datetime
    # --------------------------------------------------------

    appointment_datetime = datetime.combine(
        appointment.appointment_date,
        appointment.appointment_time,
    )

    appointment_datetime = timezone.make_aware(
        appointment_datetime
    )

    # --------------------------------------------------------
    # Reminder = 24 hours before appointment
    # --------------------------------------------------------

    reminder_datetime = (
        appointment_datetime
        - timedelta(days=1)
    )

    # --------------------------------------------------------
    # Build reminder message
    # --------------------------------------------------------

    message = (
        f"Reminder: You have an appointment "
        f"with Dr. {appointment.doctor.name} "
        f"on {appointment.appointment_date} "
        f"at {appointment.appointment_time}."
    )

    # --------------------------------------------------------
    # Create reminder
    # --------------------------------------------------------

    reminder = Reminder.objects.create(
        appointment=appointment,
        reminder_type="APPOINTMENT",
        reminder_date=reminder_datetime.date(),
        reminder_time=reminder_datetime.time(),
        message=message,
        status="PENDING",
    )

    return (
        reminder,
        "Reminder created successfully.",
    )


# ============================================================
# PROCESS DUE REMINDERS
# ============================================================

def process_due_reminders():
    """
    Process all pending reminders whose scheduled
    date/time has arrived.

    Current implementation simulates notification
    delivery by printing the reminder and changing
    its status from PENDING -> SENT.
    """

    now = timezone.localtime()

    due_reminders = (
        Reminder.objects
        .filter(
            status="PENDING",
            reminder_date__lte=now.date(),
        )
        .filter(
            reminder_time__lte=now.time(),
        )
        .select_related(
            "appointment",
            "appointment__doctor",
        )
    )

    processed = []

    for reminder in due_reminders:

        appointment = reminder.appointment

        doctor = appointment.doctor

        notification = (
            f"REMINDER SENT: "
            f"Appointment with Dr. {doctor.name} "
            f"on {appointment.appointment_date} "
            f"at {appointment.appointment_time}."
        )

        print(notification)

        reminder.status = "SENT"

        reminder.sent_at = now

        reminder.save(
            update_fields=[
                "status",
                "sent_at",
            ]
        )

        processed.append(
            {
                "reminder_id":
                    reminder.id,

                "appointment_id":
                    appointment.id,

                "message":
                    notification,

                "sent_at":
                    now.isoformat(),
            }
        )

    return processed