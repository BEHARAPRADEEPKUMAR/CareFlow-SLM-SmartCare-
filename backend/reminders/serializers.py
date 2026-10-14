from rest_framework import serializers
from .models import Reminder


class ReminderSerializer(serializers.ModelSerializer):

    appointment_details = serializers.SerializerMethodField()

    class Meta:
        model = Reminder

        fields = [
            "id",
            "appointment",
            "appointment_details",
            "reminder_type",
            "reminder_date",
            "reminder_time",
            "message",
            "status",
            "created_at",
            "sent_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "sent_at",
            "appointment_details",
        ]

    def get_appointment_details(self, obj):
        appointment = obj.appointment

        return {
            "doctor": appointment.doctor.name,
            "date": str(
                appointment.appointment_date
            ),
            "time": str(
                appointment.appointment_time
            ),
            "status": appointment.status,
        }