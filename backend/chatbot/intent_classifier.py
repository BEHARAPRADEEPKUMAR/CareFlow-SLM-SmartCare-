import re


INTENTS = [
    "BOOK_APPOINTMENT",
    "RESCHEDULE_APPOINTMENT",
    "CANCEL_APPOINTMENT",
    "CHECK_APPOINTMENT",
    "DOCTOR_AVAILABILITY",
    "HOSPITAL_FAQ",
    "APPOINTMENT_REMINDER",
    "GENERAL_QUERY",
    "MEDICAL_QUERY",
    "EMERGENCY",
    "HUMAN_HANDOFF",
]


def classify_intent(message):
    """
    Temporary rule-based intent classifier.

    This is intentionally implemented first so the complete
    Vertical AI workflow can be tested before connecting the SLM.
    """

    text = message.lower().strip()

    # --------------------------------
    # Emergency
    # --------------------------------
    emergency_words = [
        "heart attack",
        "chest pain",
        "can't breathe",
        "cannot breathe",
        "difficulty breathing",
        "unconscious",
        "severe bleeding",
        "stroke",
        "suicide",
        "overdose",
    ]

    if any(word in text for word in emergency_words):
        return "EMERGENCY"

    # --------------------------------
    # Appointment booking
    # --------------------------------
    booking_words = [
        "book appointment",
        "book an appointment",
        "schedule appointment",
        "schedule an appointment",
        "want to book",
        "need an appointment",
        "make an appointment",
    ]

    if any(word in text for word in booking_words):
        return "BOOK_APPOINTMENT"

    # --------------------------------
    # Rescheduling
    # --------------------------------
    reschedule_words = [
        "reschedule",
        "change my appointment",
        "change appointment",
        "move my appointment",
        "postpone my appointment",
    ]

    if any(word in text for word in reschedule_words):
        return "RESCHEDULE_APPOINTMENT"

    # --------------------------------
    # Cancellation
    # --------------------------------
    cancel_words = [
        "cancel my appointment",
        "cancel appointment",
        "cancel my booking",
        "cancel booking",
    ]

    if any(word in text for word in cancel_words):
        return "CANCEL_APPOINTMENT"

    # --------------------------------
    # Check appointment
    # --------------------------------
    check_words = [
        "my appointment",
        "appointment status",
        "when is my appointment",
        "check my appointment",
        "upcoming appointment",
    ]

    if any(word in text for word in check_words):
        return "CHECK_APPOINTMENT"

    # --------------------------------
    # Doctor availability
    # --------------------------------
    availability_words = [
        "available doctor",
        "doctor available",
        "is doctor",
        "doctor availability",
        "available tomorrow",
        "available today",
        "which doctor",
    ]

    if any(word in text for word in availability_words):
        return "DOCTOR_AVAILABILITY"

    # --------------------------------
    # Reminder
    # --------------------------------
    reminder_words = [
        "remind me",
        "reminder",
        "remind me about",
        "send me a reminder",
    ]

    if any(word in text for word in reminder_words):
        return "APPOINTMENT_REMINDER"

    # --------------------------------
    # Hospital FAQ
    # --------------------------------
    faq_words = [
        "hospital timings",
        "hospital hours",
        "opening hours",
        "visiting hours",
        "documents required",
        "insurance",
        "parking",
        "location",
        "address",
        "facilities",
        "services",
    ]

    if any(word in text for word in faq_words):
        return "HOSPITAL_FAQ"

    # --------------------------------
    # Medical query
    # --------------------------------
    medical_words = [
        "symptom",
        "symptoms",
        "medicine",
        "medication",
        "disease",
        "treatment",
        "diagnosis",
        "pain",
        "fever",
        "headache",
        "cough",
    ]

    if any(word in text for word in medical_words):
        return "MEDICAL_QUERY"

    # --------------------------------
    # Human handoff
    # --------------------------------
    handoff_words = [
        "talk to a doctor",
        "speak to a doctor",
        "human agent",
        "human support",
        "contact support",
        "talk to someone",
    ]

    if any(word in text for word in handoff_words):
        return "HUMAN_HANDOFF"

    return "GENERAL_QUERY"