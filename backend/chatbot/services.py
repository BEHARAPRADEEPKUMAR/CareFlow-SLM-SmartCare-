from datetime import date, datetime, timedelta
import calendar
import re
from pathlib import Path
import sys
from safety.services import check_safety
from chatbot.symptom_triage import analyze_symptoms
from chatbot.home_care import get_home_care, format_home_care
from django.utils import timezone
from django.db.models import Q
from django.core import signing
from django.core.cache import cache

from appointments.models import Appointment
from doctors.models import Doctor, DoctorAvailability
from reminders.services import create_appointment_reminder
from django.db import models

# ============================================================
# PROJECT PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# ============================================================
# SLM
# ============================================================

from chatbot.slm_service import run_slm


# ============================================================
# RAG
# ============================================================

from rag.retriever import RAGRetriever


_rag_retriever = None


def get_rag_retriever():
    """
    Load the RAG retriever once and reuse it.
    """

    global _rag_retriever

    if _rag_retriever is None:
        _rag_retriever = RAGRetriever()

    return _rag_retriever


def query_rag(question, top_k=3):
    """
    Search the hospital knowledge base.
    """

    retriever = get_rag_retriever()

    return retriever.search(
        question,
        top_k=top_k,
    )


def build_rag_response(question, results):
    """
    Return hospital information only when the retrieved
    section is relevant to the question.
    """

    if not results:
        return (
            "I couldn't find this information in the CareFlow "
            "hospital knowledge base. Please contact the hospital "
            "for confirmation."
        )

    question_text = question.lower().strip()
    best_result = results[0]
    answer_text = best_result.get("text", "").strip()
    section = best_result.get("section", "").lower()
    score = best_result.get("score", 0.0)

    if not answer_text or score < 0.35:
        return (
            "I couldn't find sufficiently relevant information "
            "in the CareFlow hospital knowledge base. "
            "Please contact the hospital for confirmation."
        )

    # Match specific hospital questions to their relevant sections.
    section_keywords = {
        "location and operating hours": [
            "location", "address", "where is", "where are",
            "opening hours", "operating hours", "working hours",
            "hospital timings", "hospital time", "open 24",
        ],
        "hospital services": [
            "department", "departments", "services",
            "specialties", "specialities",
        ],
        "cardiology": [
            "cardiology", "heart specialist", "cardiologist",
        ],
        "dermatology": [
            "dermatology", "skin specialist", "dermatologist",
        ],
        "orthopedics": [
            "orthopedics", "orthopedic", "bone specialist",
        ],
        "general medicine": [
            "general medicine", "general physician",
        ],
        "emergency safety": [
            "emergency", "urgent medical help",
        ],
    }

    # Identify the section expected by the question.
    expected_sections = [
        name
        for name, keywords in section_keywords.items()
        if any(keyword in question_text for keyword in keywords)
    ]

    if expected_sections and not any(
        expected in section for expected in expected_sections
    ):
        return (
            "I couldn't find a sufficiently relevant answer "
            "to that question in the CareFlow hospital "
            "knowledge base. Please contact the hospital "
            "for confirmation."
        )

    # Do not return unrelated content for unknown details.
    unknown_detail_keywords = [
        "phone number", "contact number", "telephone",
        "exact address", "street address",
    ]

    if any(
        keyword in question_text
        for keyword in unknown_detail_keywords
    ):
        if (
            "location and operating hours" not in section
            or "not been configured" in answer_text.lower()
        ):
            return (
                "That information is not currently configured "
                "in the CareFlow hospital knowledge base."
            )

    return (
        "According to the CareFlow hospital information: "
        f"{answer_text}"
    )


# ============================================================
# SAFETY
# ============================================================

def safety_level(message):
    """
    Safety layer for CareFlow-SLM.

    The system is an appointment and communication
    assistant, not a diagnostic system.
    """

    text = message.lower()

    emergency_words = [
        "heart attack",
        "chest pain",
        "can't breathe",
        "cannot breathe",
        "difficulty breathing",
        "stroke",
        "unconscious",
        "severe bleeding",
        "suicide",
        "overdose",
    ]

    medical_words = [
        "diagnose",
        "diagnosis",
        "prescription",
        "prescribe",
        "medicine",
        "medication",
        "symptoms",
        "disease",
        "treatment",
    ]

    if any(word in text for word in emergency_words):
        return {
            "level": "EMERGENCY",
            "message": (
                "This may be a medical emergency. Call your local emergency number "
                "now or have someone take you to the nearest emergency department. "
                "Do not drive yourself if you have severe chest pain, difficulty "
                "breathing, or stroke symptoms. If you swallowed a harmful chemical, "
                "contact emergency services or a poison-control service immediately; "
                "do not induce vomiting or try to neutralize it unless a professional "
                "tells you to."
            ),
        }

    if any(word in text for word in medical_words):
        return {
            "level": "SAFE_WITH_LIMIT",
            "message": (
                "I can help with appointments and hospital "
                "information, but I cannot diagnose conditions "
                "or prescribe treatment."
            ),
        }

    return {
        "level": "SAFE",
        "message": "",
    }


# ============================================================
# FALLBACK INTENT DETECTION
# ============================================================

def detect_intent(message):
    """
    Rule-based fallback.

    The SLM is the primary intent detector.
    This function is used only if SLM inference fails.
    """

    text = message.lower().strip()

    # --------------------------------------------------------
    # Emergency
    # --------------------------------------------------------

    if any(word in text for word in [
        "emergency",
        "urgent medical",
        "chest pain",
        "difficulty breathing",
        "can't breathe",
        "cannot breathe",
        "severe bleeding",
        "unconscious",
    ]):
        return "EMERGENCY"

    # --------------------------------------------------------
    # Cancellation
    # --------------------------------------------------------

    if re.search(r"\bcancel\b", text) and re.search(r"\b(appointment|booking|reservation|all)\b", text):
        return "CANCEL_APPOINTMENT"

    # --------------------------------------------------------
    # Rescheduling
    # --------------------------------------------------------

    if (
        re.search(r"\breschedul(?:e|ing|ed)\b", text)
        or re.search(r"\bres?he?dul(?:e|ing|ed)\b", text)
        or re.search(r"\b(change|move|shift|postpone)\b.*\bappointment\b", text)
    ):
        return "RESCHEDULE_APPOINTMENT"

    # --------------------------------------------------------
    # Doctor availability
    # --------------------------------------------------------

    if any(word in text for word in [
        "doctor available",
        "doctor availability",
        "is doctor",
        "is dr",
        "available tomorrow",
        "available today",
    ]):
        return "DOCTOR_AVAILABILITY"

    # --------------------------------------------------------
    # Booking
    # --------------------------------------------------------

    if any(word in text for word in [
        "book appointment",
        "book an appointment",
        "make an appointment",
        "schedule appointment",
        "schedule an appointment",
        "want an appointment",
    ]):
        return "BOOK_APPOINTMENT"

    # --------------------------------------------------------
    # Appointment reminder
    #
    # IMPORTANT:
    # Keep this BEFORE CHECK_APPOINTMENT because
    # "my appointment" also appears in reminder requests.
    # --------------------------------------------------------

    if any(word in text for word in [
        "remind me",
        "reminder",
        "set a reminder",
        "set reminder",
        "remind me about my appointment",
        "remind me of my appointment",
        "appointment reminder",
    ]):
        return "APPOINTMENT_REMINDER"

    # --------------------------------------------------------
    # Hospital FAQ / RAG
    # --------------------------------------------------------

    if any(word in text for word in [
        "what should i bring",
        "what do i need to bring",
        "documents",
        "document required",
        "documents required",
        "hospital hours",
        "working hours",
        "what time does the hospital",
        "can i ask",
        "do you diagnose",
        "diagnosis",
        "prescribe",
        "hospital policy",
        "appointment policy",
        "how does the hospital",
        "what are the hospital",
    ]):
        return "HOSPITAL_FAQ"

    # --------------------------------------------------------
    # Existing appointments
    # --------------------------------------------------------

    if any(word in text for word in [
        "my appointments",
        "my appointment",
        "show appointments",
        "show my appointments",
        "appointment details",
        "appointment status",
        "upcoming appointment",
        "upcoming appointments",
    ]):
        return "CHECK_APPOINTMENT"

    # --------------------------------------------------------
    # Medical query
    # --------------------------------------------------------

    if any(word in text for word in [
        "symptoms",
        "medicine",
        "medication",
        "treatment",
        "disease",
        "pain",
        "fever",
        "headache",
        "medical advice",
    ]):
        return "MEDICAL_QUERY"

    return "GENERAL_QUERY"


# ============================================================
# SLM INTENT
# ============================================================

def get_slm_intent(message):
    """
    Run the CareFlow Small Language Model.
    """

    try:
        result = run_slm(message)
        return result

    except Exception as exc:

        print(
            f"SLM inference failed: {exc}"
        )

        return None


# ============================================================
# DATE RESOLUTION
# ============================================================

def resolve_requested_date(requested_date):
    """
    Resolve natural-language and numeric dates.

    Supported:
        today
        tomorrow
        yesterday
        10/10/2026       # DD/MM/YYYY
        10-10-2026       # DD-MM-YYYY
        2026-10-10       # YYYY-MM-DD
        October 10, 2026
        Oct 10
        Monday ... Sunday
        this Monday
        next Monday

    Numeric dates use the Indian day-first convention.
    """
    if not requested_date:
        return None

    requested = str(requested_date).strip().lower()
    today = timezone.localtime().date()

    # Relative dates
    relative_dates = {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "yesterday": today - timedelta(days=1),
    }

    if requested in relative_dates:
        return relative_dates[requested]

    # Numeric dates.
    # IMPORTANT: DD/MM/YYYY must be checked before MM/DD/YYYY.
    numeric_formats = (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%m/%d/%Y",
        "%m-%d-%Y",
    )

    for fmt in numeric_formats:
        try:
            return datetime.strptime(requested, fmt).date()
        except ValueError:
            continue

    # Month name and day, with or without year
    month_formats = (
        "%B %d, %Y",
        "%B %d",
        "%b %d, %Y",
        "%b %d",
    )

    for fmt in month_formats:
        try:
            parsed = datetime.strptime(requested, fmt).date()

            if "%Y" not in fmt:
                parsed = parsed.replace(year=today.year)

                # If the date has already passed, assume next year.
                if parsed < today:
                    parsed = parsed.replace(year=today.year + 1)

            return parsed

        except ValueError:
            continue

    # Weekday names
    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    # "this Monday" means the upcoming or current Monday.
    if requested.startswith("this "):
        weekday_name = requested[5:].strip()

        if weekday_name in weekdays:
            days_ahead = (
                weekdays[weekday_name] - today.weekday()
            ) % 7

            return today + timedelta(days=days_ahead)

    # "next Monday" means the Monday in the following week.
    if requested.startswith("next "):
        weekday_name = requested[5:].strip()

        if weekday_name in weekdays:
            days_ahead = (
                weekdays[weekday_name] - today.weekday()
            ) % 7

            if days_ahead == 0:
                days_ahead = 7
            else:
                days_ahead += 7

            return today + timedelta(days=days_ahead)

    # A weekday without a prefix means the next occurrence,
    # including today if today has that weekday.
    if requested in weekdays:
        days_ahead = (
            weekdays[requested] - today.weekday()
        ) % 7

        return today + timedelta(days=days_ahead)

    return None


# ============================================================
# TIME RESOLUTION
# ============================================================

def resolve_requested_time(requested_time):
    """
    Convert SLM time output into HH:MM:SS.

    Examples:
        9 AM
        9:30 AM
        15:00
        3 PM
    """

    if not requested_time:
        return None

    requested = (
        str(requested_time)
        .strip()
        .upper()
    )

    requested = re.sub(r"(?<=\d)\.(?=\d)", ":", requested)
    requested = re.sub(r"\s+", " ", requested).strip()

    formats = [
        "%I:%M %p",
        "%I %p",
        "%H:%M",
        "%H:%M:%S",
    ]

    for time_format in formats:

        try:

            parsed = datetime.strptime(
                requested,
                time_format,
            )

            return parsed.time().replace(
                second=0,
                microsecond=0,
            )

        except ValueError:
            continue

    return None


# ============================================================
# NORMALIZE TIME
# ============================================================

def normalize_time_value(value):
    """
    Normalize different time formats into a Python time.

    Examples:
        3 PM
        3:00 PM
        15:00
        15:00:00
    """

    if not value:
        return None

    text = (
        str(value)
        .strip()
        .upper()
    )

    # Accept times such as 1.30 PM / 1.30PM.
    text = re.sub(r"(?<=\d)\.(?=\d)", ":", text)
    text = re.sub(r"\s+", " ", text).strip()

    formats = [
        "%I:%M %p",
        "%I %p",
        "%H:%M",
        "%H:%M:%S",
    ]

    for fmt in formats:

        try:

            parsed = datetime.strptime(
                text,
                fmt,
            )

            return parsed.time().replace(
                second=0,
                microsecond=0,
            )

        except ValueError:
            continue

    return None


# ============================================================
# SERIALIZE APPOINTMENT
# ============================================================

def serialize_appointment(appointment):

    doctor = appointment.doctor

    return {
        "id": appointment.id,

        "doctor_id": doctor.id,

        "doctor_name": doctor.name,

        "department": (
            doctor.department.name
            if doctor.department
            else ""
        ),

        "department_name": (
            doctor.department.name
            if doctor.department
            else ""
        ),

        "qualification": doctor.qualification,

        "experience_years": doctor.experience_years,

        "date": str(
            appointment.appointment_date
        ),

        "time": str(
            appointment.appointment_time
        ),

        "status": appointment.status,

        "consultation_fee": str(
            doctor.consultation_fee
        ),
    }


# ============================================================
# GET CURRENT PATIENT APPOINTMENTS
# ============================================================

def mark_past_appointments_completed(user=None):
    """Mark elapsed appointments COMPLETED using the configured local timezone.

    This follows the requested app behavior: once the appointment date/time has
    passed, a still-active appointment is shown as COMPLETED. It does not change
    CANCELLED appointments or appointments belonging to another patient.
    """
    now = timezone.localtime()
    current_time = now.time().replace(tzinfo=None, second=0, microsecond=0)
    past = Appointment.objects.filter(
        status__in=["SCHEDULED", "CONFIRMED", "RESCHEDULED"]
    ).filter(
        Q(appointment_date__lt=now.date())
        | Q(appointment_date=now.date(), appointment_time__lt=current_time)
    )
    if user is not None and getattr(user, "is_authenticated", False):
        past = past.filter(patient=user)
    past.update(status="COMPLETED")


def _suggest_available_slots(
    department=None,
    requested_date=None,
    doctor_name=None,
    limit=25,
    user=None,
):
    """Return available slots in a rolling five-day window.

    The default window is today through four days from today. As each day passes,
    the window naturally rolls forward, so one new future day is added. If the
    user explicitly requests a later date, that date becomes the start of the
    five-day window. Past dates are never offered.
    """
    mark_past_appointments_completed()
    today = timezone.localtime().date()
    target_date = resolve_requested_date(requested_date) if requested_date else today
    if target_date is None or target_date < today:
        target_date = today

    results = []
    seen = set()
    for offset in range(5):
        day = target_date + timedelta(days=offset)
        slots = get_booking_options(
            department=department,
            requested_date=day.isoformat(),
            doctor_name=doctor_name,
            user=user,
        )
        for slot in slots:
            if doctor_name:
                clean = re.sub(r"\b(?:Dr\.?|Doctor)\s*", "", str(doctor_name), flags=re.IGNORECASE).strip()
                if clean and clean.lower() not in slot.get("doctor_name", "").lower():
                    continue
            slot_date = str(slot.get("date") or slot.get("appointment_date") or day.isoformat())
            slot_time = str(slot.get("time") or slot.get("appointment_time") or "")
            doctor = str(slot.get("doctor_id") or slot.get("doctor_name") or "")
            identity = (doctor, slot_date, slot_time)
            if identity in seen:
                continue
            seen.add(identity)
            results.append(slot)

    # Sort the combined five-day result chronologically. Some schedule sources
    # may return dates in a different order, so do not rely on query ordering.
    def _slot_sort_key(slot):
        raw_date = str(slot.get("date") or slot.get("appointment_date") or "")
        raw_time = str(slot.get("time") or slot.get("appointment_time") or "")
        try:
            parsed_date = resolve_requested_date(raw_date)
        except Exception:
            parsed_date = None
        if parsed_date is None:
            parsed_date = date.max
        try:
            parsed_time = datetime.strptime(raw_time[:5], "%H:%M").time()
        except (TypeError, ValueError):
            try:
                parsed_time = datetime.strptime(raw_time, "%I:%M %p").time()
            except (TypeError, ValueError):
                parsed_time = datetime.max.time()
        return (parsed_date, parsed_time, str(slot.get("doctor_name") or ""))

    results.sort(key=_slot_sort_key)
    return results[:limit]


def get_patient_appointments(user, active_only=False):
    """
    Return appointments belonging to the authenticated patient only.
    """
    if user is None or not user.is_authenticated:
        return []

    appointments = (
        Appointment.objects
        .filter(patient=user)
        .select_related(
            "doctor",
            "doctor__department",
        )
        .order_by(
            "appointment_date",
            "appointment_time",
        )
    )

    if active_only:
        appointments = appointments.filter(
            status__in=[
                "SCHEDULED",
                "CONFIRMED",
                "RESCHEDULED",
            ]
        )

    return [
        serialize_appointment(appointment)
        for appointment in appointments
    ]


# ============================================================
# EXTRACT DOCTOR FROM MESSAGE
# ============================================================

def extract_doctor_from_message(message, appointments=None):
    """Return an actual doctor name mentioned in the message."""
    if not message:
        return None

    normalized_message = re.sub(
        r"[^a-z0-9\s]", " ", message.lower()
    )
    normalized_message = re.sub(
        r"\s+", " ", normalized_message
    ).strip()

    if appointments is None:
        doctors = Doctor.objects.filter(is_active=True)
    else:
        doctors = [appointment.doctor for appointment in appointments]

    # Prefer longer names first to avoid partial-name matches.
    doctors = sorted(
        doctors,
        key=lambda doctor: len(doctor.name),
        reverse=True,
    )

    for doctor in doctors:
        normalized_name = re.sub(
            r"[^a-z0-9\s]", " ", doctor.name.lower()
        )
        normalized_name = re.sub(
            r"\s+", " ", normalized_name
        ).strip()

        if normalized_name and re.search(
            rf"\b{re.escape(normalized_name)}\b",
            normalized_message,
        ):
            return doctor.name

    return None



def extract_department_from_message(message):
    """Find a department from an explicit name, disease, or symptom."""
    if not message:
        return None

    text = re.sub(r"[^a-z0-9\s]", " ", message.lower())
    text = re.sub(r"\s+", " ", text).strip()

    # Explicit department names and aliases.
    aliases = {
        "orthopedic": "Orthopedics",
        "orthopedics": "Orthopedics",
        "orthopaedic": "Orthopedics",
        "orthopaedics": "Orthopedics",
        "orthopedist": "Orthopedics",
        "orthopaedist": "Orthopedics",
        "cardiology": "Cardiology",
        "cardiologist": "Cardiology",
        "dermatology": "Dermatology",
        "dermatologist": "Dermatology",
        "dermotologist": "Dermatology",  # Common misspelling
        "neurology": "Neurology",
        "neurologist": "Neurology",
        "general medicine": "General Medicine",
        "general physician": "General Medicine",
        "physician": "General Medicine",
        "pulmonology": "Pulmonology",
        "pulmonologist": "Pulmonology",
        "endocrinology": "Endocrinology",
        "endocrinologist": "Endocrinology",
        "gastroenterology": "Gastroenterology / Hepatology",
        "gastroenterologist": "Gastroenterology / Hepatology",
        "hepatology": "Gastroenterology / Hepatology",
        "hepatologist": "Gastroenterology / Hepatology",
        "infectious disease": "Infectious Disease",
    }

    # Match explicit department names stored in the database first.
    departments = list(
        Doctor.objects.filter(is_active=True)
        .exclude(department__isnull=True)
        .values_list("department__name", flat=True)
        .distinct()
    )

    for department_name in departments:
        normalized = re.sub(
            r"[^a-z0-9\s]", " ", department_name.lower()
        )
        normalized = re.sub(r"\s+", " ", normalized).strip()

        if normalized and re.search(
            rf"\b{re.escape(normalized)}\b", text
        ):
            return department_name

    for alias, canonical_name in aliases.items():
        if re.search(rf"\b{re.escape(alias)}\b", text):
            actual_name = next(
                (
                    name for name in departments
                    if name.lower() == canonical_name.lower()
                    or (
                        canonical_name == "Gastroenterology / Hepatology"
                        and "gastroenterology" in name.lower()
                    )
                ),
                None,
            )
            if actual_name:
                return actual_name

    # Disease/symptom-to-specialty mapping.
    # These are demo routing rules, not a medical diagnosis.
    disease_routes = {
        "Dermatology": [
            "acne", "pimples", "rash", "psoriasis",
            "fungal infection", "impetigo", "skin allergy",
        ],
        "Cardiology": [
            "heart condition", "heart disease", "chest pain",
            "hypertension", "high blood pressure",
        ],
        "Neurology": [
            "migraine", "headache", "paralysis",
            "brain hemorrhage",
        ],
        "Orthopedics": [
            "joint pain", "arthritis", "bone pain",
            "fracture", "back pain",
        ],
        "Pulmonology": [
            "asthma", "bronchial asthma", "wheezing",
            "persistent cough", "breathing problem",
            "difficulty breathing", "pneumonia",
        ],
        "Endocrinology": [
            "diabetes", "high blood sugar", "low blood sugar",
            "hyperthyroidism", "hypothyroidism",
            "thyroid problem",
        ],
        "Gastroenterology / Hepatology": [
            "hepatitis", "jaundice", "chronic cholestasis",
            "acid reflux", "gerd", "peptic ulcer",
            "stomach ulcer",
        ],
        "Infectious Disease": [
            "aids", "hiv", "dengue", "malaria",
            "tuberculosis", "typhoid",
        ],
        "General Medicine": [
            "common cold", "cold", "fever", "allergy",
            "urinary tract infection", "uti",
            "drug reaction",
        ],
    }

    # Longer phrases first so specific terms take precedence.
    for department, terms in disease_routes.items():
        for term in sorted(terms, key=len, reverse=True):
            if re.search(rf"\b{re.escape(term)}\b", text):
                actual_name = next(
                    (
                        name for name in departments
                        if name.lower() == department.lower()
                        or (
                            department == "Gastroenterology / Hepatology"
                            and "gastroenterology" in name.lower()
                        )
                    ),
                    None,
                )
                if actual_name:
                    return actual_name

    return None
# ============================================================
# FIND UPCOMING REMINDER APPOINTMENTS
# ============================================================

def get_matching_reminder_appointments(
    message,
    slm_result,
):
    """
    Find active upcoming appointments matching the
    reminder request.

    Examples:

        Remind me about my appointment.
            -> all upcoming appointments

        Remind me tomorrow at 3 PM.
            -> tomorrow at 3 PM

        Remind me about my appointment
        with Dr. Rahul Verma on October 9 at 10 AM.
            -> Rahul Verma, October 9, 10 AM
    """

    now = timezone.localtime()

    # --------------------------------------------------------
    # Active appointments only
    # --------------------------------------------------------

    appointments = (
        Appointment.objects
        .select_related(
            "doctor",
            "doctor__department",
        )
        .filter(
            status__in=[
                "SCHEDULED",
                "CONFIRMED",
                "RESCHEDULED",
            ]
        )
        .filter(
            Q(
                appointment_date__gt=now.date()
            )
            |
            Q(
                appointment_date=now.date(),
                appointment_time__gte=now.time(),
            )
        )
        .order_by(
            "appointment_date",
            "appointment_time",
        )
    )

    # --------------------------------------------------------
    # Extract SLM values
    # --------------------------------------------------------

    requested_date = slm_result.get(
        "date"
    )

    requested_time = slm_result.get(
        "time"
    )

    requested_doctor = slm_result.get(
        "doctor"
    )

    requested_department = slm_result.get(
        "department"
    )

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    if requested_date:

        resolved_date = resolve_requested_date(
            requested_date
        )

        if resolved_date:

            appointments = appointments.filter(
                appointment_date=resolved_date
            )

    # --------------------------------------------------------
    # TIME
    # --------------------------------------------------------

    if requested_time:

        resolved_time = normalize_time_value(
            requested_time
        )

        if resolved_time:

            appointments = appointments.filter(
                appointment_time=resolved_time
            )

    # --------------------------------------------------------
    # DOCTOR FROM SLM
    # --------------------------------------------------------

    if requested_doctor:

        doctor_text = str(
            requested_doctor
        ).strip()

        doctor_words = [
            word
            for word in re.split(
                r"\s+",
                doctor_text,
            )
            if word
        ]

        for word in doctor_words:

            appointments = appointments.filter(
                doctor__name__icontains=word
            )

    # --------------------------------------------------------
    # DOCTOR FROM USER MESSAGE
    #
    # This fixes:
    #
    # "with Dr. Rahul Verma"
    #
    # when the SLM returns doctor=null.
    # --------------------------------------------------------

    else:

        doctor_name = extract_doctor_from_message(
            message,
            appointments=appointments,
        )

        if doctor_name:

            appointments = appointments.filter(
                doctor__name__iexact=doctor_name
            )

    # --------------------------------------------------------
    # DEPARTMENT
    # --------------------------------------------------------

    if requested_department:

        appointments = appointments.filter(
            doctor__department__name__iexact=(
                requested_department
            )
        )

    return list(
        appointments
    )


# ============================================================
# FIND APPOINTMENTS MATCHING SLM DETAILS
# ============================================================


def find_matching_appointments(
    user,
    requested_date=None,
    requested_time=None,
    requested_doctor=None,
    requested_department=None,
):
    """
    Find active appointments belonging to one patient.
    """

    if user is None or not user.is_authenticated:
        return []

    appointments = (
        Appointment.objects
        .filter(
            patient=user,
            status__in=[
                "SCHEDULED",
                "CONFIRMED",
                "RESCHEDULED",
            ],
        )
        .select_related(
            "doctor",
            "doctor__department",
        )
        .order_by(
            "appointment_date",
            "appointment_time",
        )
    )

    resolved_date = resolve_requested_date(requested_date)

    if resolved_date:
        appointments = appointments.filter(
            appointment_date=resolved_date
        )

    resolved_time = resolve_requested_time(requested_time)

    if resolved_time:
        appointments = appointments.filter(
            appointment_time__hour=resolved_time.hour,
            appointment_time__minute=resolved_time.minute,
        )

    if requested_doctor:
        doctor_text = str(requested_doctor).lower().strip()
        doctor_text = doctor_text.replace("dr.", "").replace("dr ", "")
        doctor_text = " ".join(doctor_text.split())

        matching_ids = []

        for appointment in appointments:
            actual_name = (
                appointment.doctor.name.lower().strip()
            )
            actual_name = actual_name.replace("dr.", "").replace("dr ", "")
            actual_name = " ".join(actual_name.split())

            if (
                doctor_text == actual_name
                or doctor_text in actual_name
                or actual_name in doctor_text
            ):
                matching_ids.append(appointment.pk)

        appointments = appointments.filter(
            pk__in=matching_ids
        )

    if requested_department:
        appointments = appointments.filter(
            doctor__department__name__icontains=(
                str(requested_department).strip()
            )
        )

    return [
        serialize_appointment(appointment)
        for appointment in appointments
    ]


# ============================================================
# CHECK DOCTOR SLOT AVAILABILITY
# ============================================================

def is_slot_available(
    doctor_id,
    requested_date,
    requested_time,
    exclude_appointment_id=None,
    user=None,
):
    """Validate a requested slot against the doctor's schedule and bookings."""

    if not requested_date or not requested_time:
        return False

    doctor = (
        Doctor.objects
        .filter(id=doctor_id, is_active=True)
        .first()
    )

    if not doctor:
        return False

    today = timezone.localtime().date()

    # Reject past dates and past times today.
    if requested_date < today:
        return False

    if requested_date == today:
        current_time = timezone.localtime().time().replace(
            tzinfo=None, second=0, microsecond=0
        )
        if requested_time <= current_time:
            return False

    weekday = requested_date.weekday()

    # Prefer date-specific schedules when they exist.
    date_schedules = DoctorAvailability.objects.filter(
        doctor=doctor,
        date=requested_date,
        is_active=True,
    ).order_by("start_time")

    if date_schedules.exists():
        availabilities = date_schedules
    else:
        availabilities = DoctorAvailability.objects.filter(
            doctor=doctor,
            date__isnull=True,
            weekday=weekday,
            is_active=True,
        ).order_by("start_time")

    inside_availability = False

    for availability in availabilities:
        if not (
            availability.start_time
            <= requested_time
            < availability.end_time
        ):
            continue

        slot_minutes = availability.slot_minutes

        if not slot_minutes or slot_minutes <= 0:
            continue

        start_datetime = datetime.combine(
            requested_date,
            availability.start_time,
        )
        requested_datetime = datetime.combine(
            requested_date,
            requested_time,
        )

        elapsed_seconds = (
            requested_datetime - start_datetime
        ).total_seconds()

        elapsed_minutes = elapsed_seconds / 60

        if elapsed_minutes % slot_minutes != 0:
            continue

        inside_availability = True
        break

    if not inside_availability:
        return False

    existing = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=requested_date,
        appointment_time=requested_time,
        status__in=[
            "SCHEDULED",
            "CONFIRMED",
            "RESCHEDULED",
        ],
    )

    if exclude_appointment_id:
        existing = existing.exclude(
            id=exclude_appointment_id
        )

    if existing.exists():
        return False

    # Prevent one patient from holding two active appointments at the same time,
    # even if the appointments are with different doctors.
    if user is not None and getattr(user, "is_authenticated", False):
        patient_existing = Appointment.objects.filter(
            patient=user,
            appointment_date=requested_date,
            appointment_time=requested_time,
            status__in=["SCHEDULED", "CONFIRMED", "RESCHEDULED"],
        )
        if exclude_appointment_id:
            patient_existing = patient_existing.exclude(id=exclude_appointment_id)
        if patient_existing.exists():
            return False

    return True


# ============================================================
# BOOKING OPTIONS
# ============================================================

def get_booking_options(
    department=None,
    requested_date=None,
    doctor_name=None,
    slots_per_doctor=5,
    user=None,
):
    """Return available slots using date-specific schedules first."""

    booking_date = (
        resolve_requested_date(requested_date)
        if requested_date
        else timezone.localtime().date()
    )

    if booking_date is None:
        return []

    today = timezone.localtime().date()

    if booking_date < today:
        return []

    doctors = (
        Doctor.objects
        .filter(is_active=True)
        .select_related("department")
        .order_by("name")
    )

    if department:
        doctors = doctors.filter(
            department__name__iexact=str(department).strip()
        )

    if doctor_name:
        clean_name = re.sub(
            r"\b(?:Dr\.?|Doctor)\s*",
            "",
            str(doctor_name),
            flags=re.IGNORECASE,
        ).strip()

        for word in clean_name.split():
            doctors = doctors.filter(name__icontains=word)

    weekday = booking_date.weekday()
    options = []

    now = timezone.localtime()
    current_time = now.time().replace(
        tzinfo=None, second=0, microsecond=0
    )

    for doctor in doctors:
        date_schedules = DoctorAvailability.objects.filter(
            doctor=doctor,
            date=booking_date,
            is_active=True,
        ).order_by("start_time")

        # A date-specific schedule overrides recurring schedules.
        if date_schedules.exists():
            availabilities = date_schedules
        else:
            availabilities = DoctorAvailability.objects.filter(
                doctor=doctor,
                date__isnull=True,
                weekday=weekday,
                is_active=True,
            ).order_by("start_time")

        doctor_slots = 0
        seen_times = set()

        for availability in availabilities:
            slot_minutes = availability.slot_minutes

            if not slot_minutes or slot_minutes <= 0:
                continue

            current_datetime = datetime.combine(
                booking_date,
                availability.start_time,
            )
            end_datetime = datetime.combine(
                booking_date,
                availability.end_time,
            )

            while current_datetime < end_datetime:
                slot_time = current_datetime.time()

                if (
                    booking_date == today
                    and slot_time <= current_time
                ):
                    current_datetime += timedelta(
                        minutes=slot_minutes
                    )
                    continue

                if slot_time in seen_times:
                    current_datetime += timedelta(
                        minutes=slot_minutes
                    )
                    continue

                seen_times.add(slot_time)

                if is_slot_available(
                    doctor_id=doctor.id,
                    requested_date=booking_date,
                    requested_time=slot_time,
                    user=user,
                ):
                    options.append({
                        "doctor_id": doctor.id,
                        "doctor_name": doctor.name,
                        "department": (
                            doctor.department.name
                            if doctor.department
                            else ""
                        ),
                        "qualification": doctor.qualification,
                        "experience_years": doctor.experience_years,
                        "date": booking_date.isoformat(),
                        "time": slot_time.strftime("%H:%M"),
                        "consultation_fee": str(
                            doctor.consultation_fee
                        ),
                    })

                    doctor_slots += 1

                    if doctor_slots >= slots_per_doctor:
                        break

                current_datetime += timedelta(
                    minutes=slot_minutes
                )

            if doctor_slots >= slots_per_doctor:
                break

    return options



# ============================================================
# RESCHEDULE CONVERSATION STATE
# ============================================================

RESCHEDULE_CONTEXT_TIMEOUT = 15 * 60
RESCHEDULE_CONFIRMATION_TIMEOUT = 10 * 60


def _reschedule_cache_key(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return f"careflow:reschedule:{user.pk}"


def _set_reschedule_context(user, appointment_id, **extra):
    key = _reschedule_cache_key(user)
    if not key:
        return
    payload = {"appointment_id": appointment_id}
    payload.update(extra)
    cache.set(key, payload, RESCHEDULE_CONTEXT_TIMEOUT)


def _get_reschedule_context(user):
    key = _reschedule_cache_key(user)
    if not key:
        return None
    return cache.get(key)


def _clear_reschedule_context(user):
    key = _reschedule_cache_key(user)
    if key:
        cache.delete(key)


# ============================================================
# HOME-CARE FOLLOW-UP CONTEXT
# ============================================================

HOME_CARE_CONTEXT_TIMEOUT = 30 * 60


def _home_care_cache_key(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return f"careflow:home_care_context:{user.pk}"


def _store_home_care_context(user, matches):
    key = _home_care_cache_key(user)
    if key and matches:
        cache.set(key, matches[:3], HOME_CARE_CONTEXT_TIMEOUT)


def _get_home_care_context(user):
    key = _home_care_cache_key(user)
    if not key:
        return []
    return cache.get(key, []) or []


def _format_avoid_followup(matches):
    lines = [
        "Based on your previous home-care question, here is what the "
        "reference says to avoid:"
    ]
    for row in matches[:3]:
        topic = row.get("condition_or_symptom", "Your previous symptom")
        items = [
            item.strip()
            for item in str(row.get("what_to_avoid", "")).split(";")
            if item.strip()
        ]
        lines.extend(["", f"{topic}:"])
        if items:
            lines.extend(f"  • {item}" for item in items)
        else:
            lines.append("  • No specific avoidance guidance is listed.")
    lines.append(
        "\nThis is general information, not a diagnosis. Contact a "
        "healthcare professional if symptoms worsen or you are concerned."
    )
    return "\n".join(lines)


def _extract_date_time_from_message(message):
    """Extract a date and/or time from a user message."""
    text = str(message or "").strip()

    date_value = None
    time_value = None

    # Numeric dates: 10/10/2026, 10-10-2026, or 2026-10-10.
    numeric_match = re.search(
        r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})\b",
        text,
    )
    if numeric_match:
        date_value = numeric_match.group(0)

    # Month-name dates: October 10 or October 10, 2026.
    if not date_value:
        month_match = re.search(
            r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|"
            r"may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|"
            r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+"
            r"\d{1,2}(?:,?\s+\d{4})?\b",
            text,
            re.IGNORECASE,
        )
        if month_match:
            date_value = month_match.group(0)

    # Day-first month-name dates: 12 Oct, 12 October 2026.
    # Normalize to the month-first format supported by resolve_requested_date.
    if not date_value:
        day_first_match = re.search(
            r"\b(\d{1,2})\s+"
            r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|"
            r"may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|"
            r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
            r"(?:\s+(\d{4}))?\b",
            text,
            re.IGNORECASE,
        )
        if day_first_match:
            day, month, year = day_first_match.groups()
            date_value = f"{month} {day}"
            if year:
                date_value += f", {year}"

    # Relative dates and weekdays.
    if not date_value:
        relative_match = re.search(
            r"\b(?:today|tomorrow|yesterday|"
            r"(?:this|next)\s+"
            r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
            r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            text,
            re.IGNORECASE,
        )
        if relative_match:
            date_value = relative_match.group(0)

    # Times: 3 PM, 3:30 PM, 15:00, 3.30 PM, or 15:00:00.
    time_match = re.search(
        r"\b\d{1,2}(?:(?::|\.)\d{1,2})?\s*(?:AM|PM)\b|"
        r"\b\d{1,2}:\d{2}(?::\d{2})?\b",
        text,
        re.IGNORECASE,
    )
    if time_match:
        time_value = time_match.group(0).strip()

    return date_value, time_value


def _make_confirmation(action, user, appointment_id, **payload):
    data = {
        "action": action,
        "user_id": user.pk if user else None,
        "appointment_id": appointment_id,
        **payload,
    }
    return {
        "token": signing.dumps(data),
        "action": action,
        "appointment_id": appointment_id,
        **payload,
    }


def _load_confirmation(confirmation, user):
    if not isinstance(confirmation, dict):
        return None

    token = confirmation.get("token")
    if not token:
        return None

    try:
        data = signing.loads(
            token,
            max_age=RESCHEDULE_CONFIRMATION_TIMEOUT,
        )
    except signing.BadSignature:
        return None

    if str(data.get("user_id")) != str(user.pk):
        return None

    return data


def _is_yes(message):
    return str(message).strip().lower() in {
        "yes", "yes please", "y", "confirm", "confirmed",
        "sure", "okay", "ok", "proceed", "do it",
    }


def _is_no(message):
    return str(message).strip().lower() in {
        "no", "nope", "n", "cancel", "don't", "do not",
        "stop", "no thanks",
    }


# ============================================================
# CONVERSATION CONTEXT (SCOPED TO ONE CHAT SESSION)
# ============================================================

CONVERSATION_CONTEXT_TIMEOUT = 30 * 60


def _conversation_context_cache_key(user, conversation_id=None):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    # Context is never stored in a user-wide fallback bucket. A caller must
    # supply a concrete chat ID, otherwise ambiguous follow-ups fail closed.
    session_part = str(conversation_id or "").strip()[:100]
    if not session_part:
        return None
    return f"careflow:conversation:{user.pk}:{session_part}"


def _get_conversation_context(user, conversation_id=None):
    key = _conversation_context_cache_key(user, conversation_id)
    if not key:
        return {}
    value = cache.get(key, {})
    return value if isinstance(value, dict) else {}


def _save_conversation_context(user, conversation_id=None, **updates):
    key = _conversation_context_cache_key(user, conversation_id)
    if not key:
        return {}
    context = _get_conversation_context(user, conversation_id)
    context.update({k: v for k, v in updates.items() if v is not None})
    cache.set(key, context, timeout=CONVERSATION_CONTEXT_TIMEOUT)
    return context


def _remember_conversation_department(user, message, conversation_id=None):
    """Remember an explicitly mentioned department/doctor for this chat only."""
    question = str(message or "").lower().strip()
    department = extract_department_from_message(question)
    specialist_aliases = (
        (r"\bcardiologist\b", "Cardiology"),
        (r"\bdermatologist\b", "Dermatology"),
        (r"\borthopedic(?:s)?\b|\borthopaedic(?:s)?\b", "Orthopedics"),
        (r"\bgeneral physician\b", "General Medicine"),
    )
    if not department:
        for pattern, canonical_name in specialist_aliases:
            if re.search(pattern, question):
                department = canonical_name
                break

    explicit_doctor = extract_doctor_from_message(message)
    context = _get_conversation_context(user, conversation_id)
    updates = {}
    if department and re.search(
        r"\b(do you have|does careflow have|does the hospital have|"
        r"which department|is there a|department|specialty|specialist|"
        r"cardiologist|dermatologist|orthopedic|orthopaedic|general physician)\b",
        question,
    ):
        updates["department"] = department
        # Changing the specialty invalidates the previous doctor/slot choices.
        if context.get("department") != department:
            updates["doctor_name"] = ""
            updates["last_slots"] = []
    if explicit_doctor:
        updates["doctor_name"] = explicit_doctor
        doctor = Doctor.objects.filter(name__iexact=explicit_doctor).select_related("department").first()
        if doctor and doctor.department:
            updates["department"] = doctor.department.name
    if updates:
        return _save_conversation_context(user, conversation_id, **updates)
    return context


def _is_previous_doctor_reference(message):
    return bool(re.search(
        r"\b(that doctor|that specialist|that cardiologist|that dermatologist|"
        r"that orthopedic doctor|that orthopaedic doctor|the doctor you mentioned|"
        r"the specialist you mentioned|that one)\b",
        str(message or "").lower(),
    ))


def _apply_previous_department_context(user, message, department, conversation_id=None):
    if not _is_previous_doctor_reference(message):
        return department
    context = _get_conversation_context(user, conversation_id)
    return department or context.get("department") or None


def _needs_department_clarification(user, message, explicit_department, conversation_id=None):
    return (
        _is_previous_doctor_reference(message)
        and not explicit_department
        and not _get_conversation_context(user, conversation_id).get("department")
    )


def _remember_booking_options(user, conversation_id, options, department=None):
    """Remember the exact options previously displayed for time-only follow-ups."""
    if not options:
        return
    safe_options = []
    for slot in options[:100]:
        if not isinstance(slot, dict):
            continue
        # Keep only the slot fields needed to safely match a follow-up.
        safe_options.append({k: slot.get(k) for k in (
            "doctor_id", "doctor", "doctor_name", "department", "department_name",
            "date", "time", "consultation_fee", "fee", "id", "slot_id"
        ) if slot.get(k) is not None})
    if safe_options:
        _save_conversation_context(
            user, conversation_id,
            last_slots=safe_options,
            department=department,
        )

# ============================================================
# MAIN CHAT WORKFLOW
# ============================================================

def run_chat(message, user=None, confirmation=None, conversation_id=None):

    mark_past_appointments_completed(user=user)
    message = str(message).strip()

    # IMPORTANT: remember an explicitly named department/doctor before intent
    # routing. A question such as "Do you have a dermatologist?" can be routed
    # by the SLM to different branches across versions; saving context only in
    # the HOSPITAL_FAQ branch made same-chat follow-ups lose their department.
    # This write is scoped to the supplied conversation_id, so a fresh chat does
    # not inherit the previous chat's department.
    _remember_conversation_department(user, message, conversation_id)

    # FAIL CLOSED on unresolved references before the SLM can infer a department.
    # A phrase like "that doctor" must be grounded in this exact conversation,
    # not in a model guess or a different chat's cached context.
    is_booking_followup = bool(re.search(
        r"\b(book|booking|appointment|appointments|available slots|\bslot\b|schedule|see)\b",
        message.lower(),
    ))
    explicit_department_for_followup = extract_department_from_message(message)
    explicit_doctor_for_followup = extract_doctor_from_message(message)
    if (
        is_booking_followup
        and _is_previous_doctor_reference(message)
        and not explicit_department_for_followup
        and not explicit_doctor_for_followup
        and not _get_conversation_context(user, conversation_id).get("department")
    ):
        return {
            "response": (
                "Which specialist did you mean—Cardiology, Dermatology, "
                "Orthopedics, or General Medicine? I don't have the earlier "
                "doctor context available in this chat, so I won't guess or "
                "show appointment slots yet."
            ),
            "intent": "BOOK_APPOINTMENT",
            "action": "DEPARTMENT_CLARIFICATION_REQUIRED",
            "booking_options": [],
            "available_slots": [],
            "safety": {"level": "SAFE"},
        }

    # --------------------------------------------------------
    # HANDLE CONFIRMATION FIRST
    # --------------------------------------------------------

    confirmation_data = _load_confirmation(confirmation, user)

    if confirmation_data and _is_yes(message):
            action = confirmation_data.get("action")

            if action == "BOOK_APPOINTMENT":
                try:
                    from users.models import PatientProfile
                    from django.db import transaction

                    if not PatientProfile.objects.filter(user=user).exists():
                        return {
                            "response": "Only registered patients can book appointments.",
                            "intent": "BOOK_APPOINTMENT",
                            "action": "BOOKING_FAILED",
                            "safety": {"level": "SAFE"},
                        }

                    doctor_id = confirmation_data.get("doctor_id")
                    booking_date = resolve_requested_date(
                        confirmation_data.get("date")
                    )
                    booking_time = normalize_time_value(
                        confirmation_data.get("time")
                    )

                    doctor = Doctor.objects.filter(
                        id=doctor_id,
                        is_active=True,
                    ).select_related("department").first()

                    if not doctor or not booking_date or not booking_time:
                        return {
                            "response": "The booking details are invalid. Please request available slots again.",
                            "intent": "BOOK_APPOINTMENT",
                            "action": "BOOKING_FAILED",
                            "safety": {"level": "SAFE"},
                        }

                    with transaction.atomic():
                        if not is_slot_available(
                            doctor_id=doctor.id,
                            requested_date=booking_date,
                            requested_time=booking_time,
                            user=user,
                        ):
                            return {
                                "response": "That slot is no longer available. Please choose another available slot.",
                                "intent": "BOOK_APPOINTMENT",
                                "action": "BOOKING_SLOT_UNAVAILABLE",
                                "booking_options": _suggest_available_slots(
                                    department=doctor.department.name if doctor.department else None,
                                    requested_date=booking_date.isoformat(),
                                    doctor_name=doctor.name,
                                    limit=25,
                                    user=user,
                                ),
                                "safety": {"level": "SAFE"},
                            }

                        appointment = Appointment.objects.create(
                            patient=user,
                            doctor=doctor,
                            appointment_date=booking_date,
                            appointment_time=booking_time,
                            status="SCHEDULED",
                            reason="",
                        )

                    return {
                        "response": (
                            f"Your appointment with Dr. {doctor.name} has been booked "
                            f"for {booking_date.strftime('%d %b %Y')} at "
                            f"{booking_time.strftime('%I:%M %p').lstrip('0')}."
                        ),
                        "intent": "BOOK_APPOINTMENT",
                        "action": "BOOKING_SUCCESS",
                        "appointment": serialize_appointment(appointment),
                        "safety": {"level": "SAFE"},
                    }

                except Exception as exc:
                    print(f"Booking confirmation failed: {exc}")
                    return {
                        "response": "I couldn't complete the booking. Please try again.",
                        "intent": "BOOK_APPOINTMENT",
                        "action": "BOOKING_FAILED",
                        "safety": {"level": "SAFE"},
                    }

    if confirmation_data and _is_yes(message):
        action = confirmation_data.get("action")
        appointment_id = confirmation_data.get("appointment_id")

        if action == "RESCHEDULE_APPOINTMENT":
            try:
                from users.models import PatientProfile
                if not PatientProfile.objects.filter(user=user).exists():
                    return {
                        "response": "Only patient accounts can reschedule appointments.",
                        "intent": "RESCHEDULE_APPOINTMENT",
                        "action": "RESCHEDULE_FAILED",
                        "safety": {"level": "SAFE"},
                    }

                appointment = (
                    Appointment.objects
                    .select_related("doctor", "doctor__department")
                    .filter(id=appointment_id, patient=user)
                    .first()
                )

                if not appointment:
                    return {
                        "response": (
                            "I couldn't find an active appointment matching those details "
                            "in your account. Please check the doctor's name or choose one "
                            "of your upcoming appointments to reschedule."
                        ),
                        "intent": "RESCHEDULE_APPOINTMENT",
                        "action": "RESCHEDULE_NOT_FOUND",
                        "appointment_options": get_patient_appointments(
                            user, active_only=True
                        ),
                        "available_slots": [],
                        "safety": {"level": "SAFE"},
                    }
                if appointment.status in {"CANCELLED", "COMPLETED"}:
                    slots = _suggest_available_slots(
                        department=appointment.doctor.department.name if appointment.doctor.department else None,
                        requested_date="tomorrow",
                        doctor_name=appointment.doctor.name,
                    )
                    return {
                        "response": (
                            "That appointment is already cancelled or completed and cannot be rescheduled. "
                            "Please select one of the available slots below to book a new appointment."
                        ),
                        "intent": "BOOK_APPOINTMENT",
                        "action": "AVAILABLE_SLOTS",
                        "available_slots": slots,
                        "safety": {"level": "SAFE"},
                    }

                new_date = resolve_requested_date(confirmation_data.get("new_date"))
                new_time = normalize_time_value(confirmation_data.get("new_time"))

                if not new_date or not new_time:
                    return {
                        "response": "The new appointment date or time is invalid. Please try again.",
                        "intent": "RESCHEDULE_APPOINTMENT",
                        "action": "RESCHEDULE_FAILED",
                        "safety": {"level": "SAFE"},
                    }

                if not is_slot_available(
                    doctor_id=appointment.doctor_id,
                    requested_date=new_date,
                    requested_time=new_time,
                    exclude_appointment_id=appointment.id,
                    user=user,
                ):
                    return {
                        "response": (
                            f"The slot on {new_date.isoformat()} at "
                            f"{new_time.strftime('%H:%M')} is no longer available for "
                            f"Dr. {appointment.doctor.name}. Please choose another slot."
                        ),
                        "intent": "RESCHEDULE_APPOINTMENT",
                        "action": "RESCHEDULE_UNAVAILABLE",
                        "appointment_options": [serialize_appointment(appointment)],
                        "new_date": new_date.isoformat(),
                        "new_time": new_time.strftime("%H:%M:%S"),
                        "safety": {"level": "SAFE"},
                    }

                appointment.appointment_date = new_date
                appointment.appointment_time = new_time
                appointment.status = "RESCHEDULED"
                appointment.save(update_fields=["appointment_date", "appointment_time", "status", "updated_at"])
                _clear_reschedule_context(user)

                return {
                    "response": (
                        f"Your appointment with Dr. {appointment.doctor.name} has been "
                        f"rescheduled successfully to {new_date.isoformat()} at "
                        f"{new_time.strftime('%H:%M')}."
                    ),
                    "intent": "RESCHEDULE_APPOINTMENT",
                    "action": "RESCHEDULE_SUCCESS",
                    "appointment_options": [serialize_appointment(appointment)],
                    "safety": {"level": "SAFE"},
                }
            except Exception as exc:
                print(f"Reschedule confirmation failed: {exc}")
                return {
                    "response": "I couldn't complete the rescheduling right now. Please try again.",
                    "intent": "RESCHEDULE_APPOINTMENT",
                    "action": "RESCHEDULE_FAILED",
                    "safety": {"level": "SAFE"},
                    "error": str(exc),
                }

        if action == "CANCEL_APPOINTMENT":
            appointment = (
                Appointment.objects
                .filter(id=appointment_id, patient=user)
                .first()
            )
            if not appointment:
                return {
                    "response": "I couldn't find that appointment in your account.",
                    "intent": "CANCEL_APPOINTMENT",
                    "action": "CANCEL_FAILED",
                    "safety": {"level": "SAFE"},
                }
            if appointment.status in {"CANCELLED", "COMPLETED"}:
                return {
                    "response": "That appointment can no longer be cancelled.",
                    "intent": "CANCEL_APPOINTMENT",
                    "action": "CANCEL_FAILED",
                    "safety": {"level": "SAFE"},
                }
            appointment.status = "CANCELLED"
            appointment.save(update_fields=["status", "updated_at"])
            return {
                "response": "Your appointment has been cancelled successfully.",
                "intent": "CANCEL_APPOINTMENT",
                "action": "CANCEL_SUCCESS",
                "safety": {"level": "SAFE"},
            }

    if confirmation_data and _is_no(message):
        _clear_reschedule_context(user)
        return {
            "response": "Okay, I won't make that change.",
            "intent": confirmation_data.get("action", "GENERAL_QUERY"),
            "action": "CONFIRMATION_CANCELLED",
            "safety": {"level": "SAFE"},
        }

    # --------------------------------------------------------
    # PENDING RESCHEDULE FOLLOW-UP
    # --------------------------------------------------------

    pending = _get_reschedule_context(user)
    pending_date, pending_time = _extract_date_time_from_message(message)

    # A numbered choice is a valid response when the bot has asked the patient
    # to choose one of the suggested reschedule slots. Rebuild the same list so
    # the selection is validated against current database availability.
    if pending and re.fullmatch(r"\s*\d+\s*", message):
        pending_appointment = (
            Appointment.objects
            .select_related("doctor", "doctor__department")
            .filter(id=pending.get("appointment_id"), patient=user)
            .exclude(status__in=["CANCELLED", "COMPLETED"])
            .first()
        )
        if not pending_appointment:
            _clear_reschedule_context(user)
        else:
            offered_slots = _suggest_available_slots(
                department=(pending_appointment.doctor.department.name
                            if pending_appointment.doctor.department else None),
                requested_date=None,
                doctor_name=pending_appointment.doctor.name,
                limit=25,
                user=user,
            )
            choice = int(message.strip())
            if 1 <= choice <= len(offered_slots):
                selected = offered_slots[choice - 1]
                selected_date = resolve_requested_date(selected.get("date"))
                selected_time = normalize_time_value(selected.get("time"))
                if selected_date and selected_time and is_slot_available(
                    doctor_id=pending_appointment.doctor_id,
                    requested_date=selected_date,
                    requested_time=selected_time,
                    exclude_appointment_id=pending_appointment.id,
                    user=user,
                ):
                    confirmation_obj = _make_confirmation(
                        "RESCHEDULE_APPOINTMENT", user, pending_appointment.id,
                        new_date=selected_date.isoformat(),
                        new_time=selected_time.strftime("%H:%M:%S"),
                    )
                    return {
                        "response": (
                            f"The selected slot with Dr. {pending_appointment.doctor.name} is "
                            f"{selected_date.strftime('%d %b %Y')} at "
                            f"{selected_time.strftime('%I:%M %p').lstrip('0')}. "
                            "Would you like me to confirm the reschedule?"
                        ),
                        "intent": "RESCHEDULE_APPOINTMENT",
                        "action": "RESCHEDULE_CONFIRMATION",
                        "appointment_options": [serialize_appointment(pending_appointment)],
                        "available_slots": [selected],
                        "new_date": selected_date.isoformat(),
                        "new_time": selected_time.strftime("%H:%M:%S"),
                        "confirmation": confirmation_obj,
                        "safety": {"level": "SAFE"},
                    }
            return {
                "response": (
                    f"Please choose a slot number between 1 and {len(offered_slots)}. "
                    "The available slots are listed below."
                ),
                "intent": "RESCHEDULE_APPOINTMENT",
                "action": "RESCHEDULE_DETAILS_REQUIRED",
                "appointment_options": [serialize_appointment(pending_appointment)],
                "available_slots": offered_slots,
                "safety": {"level": "SAFE"},
            }

    if pending and (pending_date or pending_time):
        appointment = (
            Appointment.objects
            .select_related("doctor", "doctor__department")
            .filter(id=pending.get("appointment_id"), patient=user)
            .exclude(status__in=["CANCELLED", "COMPLETED"])
            .first()
        )

        if not appointment:
            _clear_reschedule_context(user)
        else:
            resolved_new_date = resolve_requested_date(pending_date) if pending_date else None
            resolved_new_time = normalize_time_value(pending_time) if pending_time else None

            if not resolved_new_date or not resolved_new_time:
                missing = "date" if not resolved_new_date else "time"
                return {
                    "response": f"Please provide the new appointment {missing}.",
                    "intent": "RESCHEDULE_APPOINTMENT",
                    "action": "RESCHEDULE_DETAILS_REQUIRED",
                    "appointment_options": [serialize_appointment(appointment)],
                    "safety": {"level": "SAFE"},
                }

            if not is_slot_available(
                doctor_id=appointment.doctor_id,
                requested_date=resolved_new_date,
                requested_time=resolved_new_time,
                exclude_appointment_id=appointment.id,
                user=user,
            ):
                return {
                    "response": (
                        f"The requested slot on {resolved_new_date.isoformat()} at "
                        f"{resolved_new_time.strftime('%H:%M')} is not available for "
                        f"Dr. {appointment.doctor.name}. Please choose another date or time."
                    ),
                    "intent": "RESCHEDULE_APPOINTMENT",
                    "action": "RESCHEDULE_UNAVAILABLE",
                    "appointment_options": [serialize_appointment(appointment)],
                    "new_date": resolved_new_date.isoformat(),
                    "new_time": resolved_new_time.strftime("%H:%M:%S"),
                    "safety": {"level": "SAFE"},
                }

            confirmation_obj = _make_confirmation(
                "RESCHEDULE_APPOINTMENT",
                user,
                appointment.id,
                new_date=resolved_new_date.isoformat(),
                new_time=resolved_new_time.strftime("%H:%M:%S"),
            )

            return {
                "response": (
                    f"Your appointment with Dr. {appointment.doctor.name} is currently "
                    f"on {appointment.appointment_date} at {appointment.appointment_time}. "
                    f"The new slot on {resolved_new_date.isoformat()} at "
                    f"{resolved_new_time.strftime('%H:%M')} is available. "
                    f"Would you like me to confirm the reschedule?"
                ),
                "intent": "RESCHEDULE_APPOINTMENT",
                "action": "RESCHEDULE_CONFIRMATION",
                "appointment_options": [serialize_appointment(appointment)],
                "new_date": resolved_new_date.isoformat(),
                "new_time": resolved_new_time.strftime("%H:%M:%S"),
                "confirmation": confirmation_obj,
                "safety": {"level": "SAFE"},
            }

    # --------------------------------------------------------
    # Safety FIRST
    # --------------------------------------------------------

    safety = safety_level(
        message
    )

    if safety["level"] == "EMERGENCY":

        return {
            "response":
                safety["message"],

            "intent":
                "EMERGENCY",

            "safety":
                safety,
        }

    # --------------------------------------------------------
    # DETERMINISTIC MEDICAL-SAFETY AND FOLLOW-UP ROUTING
    # --------------------------------------------------------
    lower_message = message.lower().strip()

    # A request to prescribe antibiotics must not fall through to routine
    # cold/cough home-care matching.
    prescription_request = bool(
        re.search(
            r"\b(prescribe|prescription|antibiotics?|give me antibiotics?)\b",
            lower_message,
        )
    )
    if prescription_request:
        return {
            "response": (
                "I can't prescribe antibiotics or determine whether you need them. "
                "Antibiotics are appropriate only for certain infections, so a "
                "qualified healthcare professional should assess your symptoms "
                "and decide on treatment. If you have difficulty breathing, chest "
                "pain, or severe/worsening symptoms, seek urgent medical care."
            ),
            "intent": "MEDICAL_QUERY",
            "action": "PRESCRIPTION_REQUEST_DECLINED",
            "safety": {"level": "SAFE_WITH_LIMIT", "allowed": False},
        }

    # Do not let a clearly unsupported symptom question be misrouted by the SLM
    # to appointment availability.
    explicitly_unsupported_home_care = bool(
        re.search(
            r"\b(symptom not covered|not covered in (?:the )?home[ -]care reference|"
            r"not in (?:the )?home[ -]care reference)\b",
            lower_message,
        )
    )
    if explicitly_unsupported_home_care:
        return {
            "response": (
                "I couldn't find a suitable entry for that symptom in my home-care "
                "reference. I don't want to guess about care that isn't covered. "
                "Please describe the symptom in more detail or contact a qualified "
                "healthcare professional. If symptoms are severe or rapidly worsening, "
                "seek urgent medical care."
            ),
            "intent": "HOME_CARE_NOT_FOUND",
            "action": "HOME_CARE_REFERENCE_MISS",
            "home_care": [],
            "available_slots": [],
            "safety": {"level": "SAFE_WITH_LIMIT", "allowed": True},
        }

    # Resolve common follow-up wording using the last home-care topic saved for
    # this authenticated patient's session. If there is no saved context, ask
    # which symptom they mean instead of triggering an appointment search.
    avoid_followup = bool(
        re.search(
            r"\b(what should i avoid|what should i not do|what to avoid|"
            r"what should i stay away from)\b",
            lower_message,
        )
    )
    if avoid_followup:
        previous_home_care = _get_home_care_context(user)
        if previous_home_care:
            return {
                "response": _format_avoid_followup(previous_home_care),
                "intent": "HOME_CARE_FOLLOW_UP",
                "action": "HOME_CARE_AVOIDANCE",
                "home_care": previous_home_care,
                "safety": {"level": "SAFE_WITH_LIMIT", "allowed": True},
            }
        return {
            "response": (
                "Which symptom are you asking about? For example, a cold, cough, "
                "or headache. I can then check the matching home-care reference."
            ),
            "intent": "HOME_CARE_FOLLOW_UP",
            "action": "CLARIFICATION_REQUIRED",
            "home_care": [],
            "safety": {"level": "SAFE_WITH_LIMIT", "allowed": True},
        }

    # --------------------------------------------------------
    # DETERMINISTIC FAQ / MEDICAL INTENT GUARDS
    # --------------------------------------------------------
    # These checks run before symptom-dataset matching and SLM routing so a
    # general medical question cannot accidentally trigger appointment search.
    lower_message = message.lower().strip()

    if re.search(r"\b(can you diagnose|diagnose my symptoms|give me a diagnosis|what disease do i have)\b", lower_message):
        return {
            "response": (
                "I can't diagnose symptoms or determine what condition you have. "
                "I can share general safety information and help you book a qualified "
                "healthcare professional. Tell me your main symptom and how long it has "
                "been happening, or ask me to help book a doctor."
            ),
            "intent": "MEDICAL_QUERY",
            "action": "DIAGNOSIS_DECLINED",
            "available_slots": [],
            "safety": {"level": "SAFE_WITH_LIMIT", "allowed": False},
        }

    # Prevention questions need prevention advice, not a generic home-care entry.
    if re.search(r"\b(prevent|avoid spreading|stop spreading|spread.*(family|others|people))\b", lower_message) and re.search(r"\b(cold|flu|cough|infection)\b", lower_message):
        return {
            "response": (
                "To reduce spreading a cold to your family: wash your hands often; "
                "cover coughs and sneezes with a tissue or your elbow; avoid close "
                "contact and sharing cups, utensils, or towels while unwell; improve "
                "ventilation when practical; consider wearing a well-fitting mask "
                "around others, especially people at higher risk; clean frequently "
                "touched surfaces; and dispose of used tissues promptly. Stay home "
                "as practical while you feel unwell. Seek medical care for difficulty "
                "breathing, chest pain, dehydration, or severe/worsening symptoms. "
                "This is general guidance, not a diagnosis."
            ),
            "intent": "HOME_CARE",
            "action": "INFECTION_PREVENTION_GUIDANCE",
            "available_slots": [],
            "safety": {"level": "SAFE_WITH_LIMIT", "allowed": True},
        }

    # Fever questions receive basic precautions instead of disease-dataset matches.
    if re.search(r"\b(mild fever|low[- ]grade fever|i have a fever|feeling feverish)\b", lower_message) and not re.search(r"\b(book|schedule|appointment|doctor)\b", lower_message):
        return {
            "response": (
                "For a mild fever, rest, drink fluids, avoid overexertion, and monitor "
                "your temperature and how you feel. Limit close contact with others "
                "while you may be infectious. Contact a healthcare professional if the "
                "fever persists, worsens, or you are concerned. Seek urgent care for "
                "difficulty breathing, chest pain, confusion, severe weakness, or signs "
                "of dehydration. I can't diagnose the cause of a fever from symptoms alone."
            ),
            "intent": "SYMPTOM_TRIAGE",
            "action": "GENERAL_FEVER_PRECAUTIONS",
            "available_slots": [],
            "safety": {"level": "SAFE_WITH_LIMIT", "allowed": True},
        }

    # Hospital facts are configured and should bypass SLM/RAG classification.
    hospital_fact_question = bool(re.search(
        r"\b(where is|where are|located|location|address|street address|"
        r"hospital hours|opening hours|operating hours|working hours|business hours|"
        r"hospital timings|opening time|closing time|what time does .* open|"
        r"what time does .* close|opd|outpatient|doctor consultation|consultation hours|"
        r"doctor timings|doctor hours|open at midnight|emergency hours|phone number|"
        r"contact number|telephone|departments|specialties|specialities)\b",
        lower_message,
    ))
    if hospital_fact_question and not re.search(r"\b(book|schedule|cancel|reschedule|remind me)\b", lower_message):
        if re.search(r"\b(phone number|contact number|telephone|hospital number)\b", lower_message):
            response = "CareFlow Hospital phone number: 9999999999."
        elif re.search(r"\b(address|street address)\b", lower_message) and not re.search(r"\b(where is|where are|located|location)\b", lower_message):
            response = "The exact street address is not currently configured in the CareFlow hospital knowledge base. CareFlow Hospital is associated with Hyderabad, Telangana, India."
        elif re.search(r"\b(where is|where are|located|location)\b", lower_message):
            response = "CareFlow Hospital is associated with Hyderabad, Telangana, India. The exact street address is not currently configured in the hospital knowledge base."
        elif re.search(r"\b(opd|outpatient|doctor consultation|consultation hours|doctor timings|doctor hours)\b", lower_message):
            response = "CareFlow OPD / Doctor Consultation timings are 9:00 AM–8:00 PM, all days. Hospital / emergency services are listed as open 24 hours a day, 7 days a week. The exact street address is not configured."
        elif re.search(r"\b(phone number|contact number|telephone)\b", lower_message):
            response = "CareFlow Hospital phone number: 9999999999."
        elif re.search(r"\b(which|what)\b.*\b(departments|specialties|specialities)\b", lower_message):
            response = "The configured CareFlow hospital departments are Cardiology, Dermatology, Orthopedics, and General Medicine."
        else:
            response = "CareFlow Hospital is open 24 hours a day, 7 days a week (24/7)."
        return {"response": response, "intent": "HOSPITAL_FAQ", "action": "CONFIGURED_HOSPITAL_INFORMATION", "safety": {"level": "SAFE"}, "rag": {"used": False}}

    # If the user explicitly asks to book a doctor because of a symptom, let
    # the booking workflow handle it instead of returning a symptom-only answer.
    explicit_booking_with_symptom = bool(
        re.search(r"\b(book|schedule|make)\b", lower_message)
        and re.search(r"\b(doctor|appointment|visit|consultation)\b", lower_message)
    )

    # --------------------------------------------------------
    # SYMPTOM TRIAGE + APPOINTMENT FOLLOW-UP
    # --------------------------------------------------------
    # Keep this after emergency screening and before SLM intent detection.
    # Appointment-management commands continue through their existing workflow.
    symptom_followup_key = (
        f"careflow:symptom_appointment:{user.pk}"
        if user and getattr(user, "is_authenticated", False)
        else None
    )
    lower_message = message.lower().strip()
    explicit_management_request = bool(
        re.search(r"\b(cancel|cancellation|reschedule|reshedule|remind me|reminder)\b", lower_message)
    )

    # IMPORTANT: Handle "which doctor should I consult?" before symptom/SLM
    # routing. Otherwise the SLM may skip the explanation/consent step and
    # immediately search only the inferred current date.
    asks_which_doctor = bool(re.search(
        r"\b(which|what)\s+(doctor|specialist)\b|"
        r"\b(doctor|specialist)\s+should\s+i\s+(see|consult)\b|"
        r"\bwho\s+should\s+i\s+(see|consult)\b|"
        r"\bwhich\s+department\b",
        lower_message,
    ))
    condition_department = extract_department_from_message(message)
    if (
        asks_which_doctor
        and condition_department
        and not explicit_management_request
        and not explicit_booking_with_symptom
    ):
        condition_details = (
            (r"\b(urinary tract infection|uti)\b", "a possible urinary tract infection (UTI)",
             "A UTI can cause burning or pain while urinating, frequent urges to urinate, or lower abdominal discomfort. A clinician may recommend a urine test to assess the cause."),
            (r"\b(migraine)\b", "possible migraine",
             "Migraine can cause recurring headaches and may also involve nausea or sensitivity to light and sound."),
            (r"\b(arthritis)\b", "possible arthritis",
             "Arthritis can cause joint pain, stiffness, or swelling, but these symptoms can have other causes too."),
            (r"\b(joint pain|joint stiffness)\b", "joint pain or stiffness",
             "Joint pain and stiffness can have several causes, including overuse, injury, or inflammatory conditions."),
            (r"\b(headache|headaches)\b", "headaches",
             "Headaches can have many causes; a clinician can assess their pattern, severity, and associated symptoms."),
        )
        condition_name = None
        condition_detail = None
        for pattern, label, detail in condition_details:
            if re.search(pattern, lower_message):
                condition_name, condition_detail = label, detail
                break

        if symptom_followup_key:
            cache.set(
                symptom_followup_key,
                {"condition": condition_name, "specialty": condition_department},
                timeout=10 * 60,
            )

        condition_intro = f"You mentioned {condition_name}. " if condition_name else "Based on what you described, "
        detail_text = f"{condition_detail} " if condition_detail else ""
        return {
            "response": (
                f"{condition_intro}{detail_text}"
                f"A suitable department to consult is {condition_department}. "
                "This information cannot confirm a diagnosis. "
                "Would you like me to show available appointment slots "
                "for the next five days?"
            ),
            "intent": "SYMPTOM_TRIAGE",
            "action": "SPECIALTY_RECOMMENDATION",
            "recommended_specialty": condition_department,
            "possible_condition": condition_name,
            "available_slots": [],
            "safety": {"level": "SAFE_WITH_LIMIT", "allowed": True},
        }

    # If the patient accepts the symptom-based appointment offer, search real slots.
    if symptom_followup_key and _is_yes(message):
        followup_data = cache.get(symptom_followup_key)

        if isinstance(followup_data, dict):
            requested_specialty = followup_data.get("specialty")
            requested_condition = followup_data.get("condition")
        else:
            # Backward compatibility with older cache entries containing a string.
            requested_specialty = followup_data
            requested_condition = None

        if requested_specialty:
            cache.delete(symptom_followup_key)
            try:
                symptom_slots = _suggest_available_slots(
                    department=requested_specialty,
                    requested_date=None,
                    limit=10,
                    user=user,
                )
            except Exception as exc:
                print(f"Symptom appointment lookup failed: {exc}")
                symptom_slots = []

            if symptom_slots:
                return {
                    "response": (
                        f"I found available appointments in {requested_specialty}. "
                        "These slots can help you consult a clinician about your symptoms. "
                        "Please choose one of the available slots."
                    ),
                    "intent": "BOOK_APPOINTMENT",
                    "action": "AVAILABLE_SLOTS",
                    "recommended_specialty": requested_specialty,
                    "possible_condition": requested_condition,
                    "available_slots": symptom_slots,
                    "safety": {"level": "SAFE_WITH_LIMIT"},
                }
            return {
                "response": (
                    f"I couldn't find an available appointment in {requested_specialty}"
                    " within the current booking window. You can ask me to check "
                    "another date or specialty, or contact the clinic for help."
                ),
                "intent": "BOOK_APPOINTMENT",
                "action": "NO_AVAILABLE_SLOTS",
                "recommended_specialty": requested_specialty,
                "possible_condition": requested_condition,
                "available_slots": [],
                "safety": {"level": "SAFE_WITH_LIMIT"},
            }

    if symptom_followup_key and _is_no(message) and cache.get(symptom_followup_key):
        cache.delete(symptom_followup_key)
        return {
            "response": "No problem. I won't search for an appointment. If you'd like, tell me more about your symptoms or ask about hospital services.",
            "intent": "SYMPTOM_TRIAGE",
            "action": "APPOINTMENT_OFFER_DECLINED",
            "safety": {"level": "SAFE_WITH_LIMIT"},
        }

    if not explicit_management_request and not explicit_booking_with_symptom:
        try:
            symptom_result = analyze_symptoms(message)
        except Exception as exc:
            print(f"Symptom triage lookup failed: {exc}")
            symptom_result = None

        if symptom_result:
            specialty = symptom_result.get("recommended_specialty")
            is_emergency = bool(symptom_result.get("emergency"))

            # Never append routine home-care suggestions to an emergency response.
            if is_emergency:
                return {
                    "response": symptom_result["response"],
                    "intent": "EMERGENCY",
                    "action": "EMERGENCY",
                    "matched_symptoms": symptom_result.get(
                        "matched_symptoms", []
                    ),
                    "possible_conditions": symptom_result.get(
                        "possible_conditions", []
                    ),
                    "recommended_specialty": specialty,
                    "available_slots": [],
                    "safety": {
                        "level": "EMERGENCY",
                        "allowed": False,
                    },
                }

            # Find relevant home-care reference entries.
            try:
                home_care_matches = get_home_care(message)
                home_care_text = (
                    format_home_care(home_care_matches)
                    if home_care_matches
                    else ""
                )
            except Exception as exc:
                print(f"Home-care lookup failed: {exc}")
                home_care_text = ""

            possible_conditions = symptom_result.get("possible_conditions") or []
            primary_condition = (
                possible_conditions[0] if possible_conditions else None
            )

            # Remember the possible condition and specialty for the patient's reply.
            if symptom_followup_key and specialty:
                cache.set(
                    symptom_followup_key,
                    {
                        "condition": primary_condition,
                        "specialty": specialty,
                    },
                    timeout=10 * 60,
                )

            if home_care_matches:
                _store_home_care_context(user, home_care_matches)

            if primary_condition and specialty:
                response_text = (
                    "I recognized these symptoms: "
                    f"{', '.join(symptom_result.get('matched_symptoms', []))}. "
                    f"Your symptoms may be associated with {primary_condition}. "
                    "This is not a confirmed diagnosis; a qualified clinician "
                    "should assess your symptoms. "
                    f"Your health issue may be {primary_condition}. "
                    f"Would you like to book an appointment for this condition "
                    f"with a {specialty} specialist?"
                )
            else:
                response_text = symptom_result["response"]

            if home_care_text:
                response_text = (
                    response_text
                    + "\n\n"
                    + home_care_text
                )

            return {
                "response": response_text,
                "intent": "SYMPTOM_TRIAGE",
                "action": "SYMPTOM_ASSESSMENT",
                "matched_symptoms": symptom_result.get(
                    "matched_symptoms", []
                ),
                "possible_conditions": symptom_result.get(
                    "possible_conditions", []
                ),
                "recommended_specialty": specialty,
                "available_slots": [],
                "home_care": home_care_matches if home_care_text else [],
                "safety": {
                    "level": "SAFE_WITH_LIMIT",
                    "allowed": True,
                },
            }

    # --------------------------------------------------------
    # CONDITION / SPECIALTY QUESTION FALLBACK
    # --------------------------------------------------------
    # For a condition/doctor question, explain briefly and recommend a
    # department first. Only search for appointment slots after the patient
    # explicitly accepts the offer.
    if not explicit_management_request and not explicit_booking_with_symptom:
        asks_which_doctor = bool(re.search(
            r"\b(which|what)\s+(doctor|specialist)\b|"
            r"\b(doctor|specialist)\s+should\s+i\s+(see|consult)\b|"
            r"\bwho\s+should\s+i\s+(see|consult)\b|"
            r"\bwhich\s+department\b",
            lower_message,
        ))
        condition_department = extract_department_from_message(message)

        if asks_which_doctor and condition_department:
            condition_details = (
                (r"\b(urinary tract infection|uti)\b", "a possible urinary tract infection (UTI)",
                 "A UTI can cause burning or pain while urinating, frequent urges to urinate, or lower abdominal discomfort. A clinician may need a urine test to assess the cause."),
                (r"\b(migraine)\b", "possible migraine",
                 "Migraine can cause recurring headaches and may also involve nausea or sensitivity to light and sound."),
                (r"\b(arthritis)\b", "possible arthritis",
                 "Arthritis can cause joint pain, stiffness, and swelling. A clinician can assess the affected joints and determine the cause."),
                (r"\b(joint pain|joint stiffness)\b", "joint pain or stiffness",
                 "Joint pain and stiffness can have several causes, including overuse, injury, or inflammatory conditions."),
                (r"\b(headache|headaches)\b", "headaches",
                 "Headaches can have many causes; a clinician can assess their pattern, severity, and associated symptoms."),
            )
            condition_name = None
            condition_detail = None
            for pattern, label, detail in condition_details:
                if re.search(pattern, lower_message):
                    condition_name = label
                    condition_detail = detail
                    break

            if symptom_followup_key:
                cache.set(
                    symptom_followup_key,
                    {
                        "condition": condition_name,
                        "specialty": condition_department,
                    },
                    timeout=10 * 60,
                )

            condition_intro = (
                f"You mentioned {condition_name}. " if condition_name
                else "Based on what you described, "
            )
            detail_text = f"{condition_detail} " if condition_detail else ""
            return {
                "response": (
                    f"{condition_intro}{detail_text}"
                    f"A suitable department to consult is {condition_department}. "
                    "This information cannot confirm a diagnosis. "
                    "Would you like me to show available appointment slots "
                    f"in {condition_department} for the next five days?"
                ),
                "intent": "SYMPTOM_TRIAGE",
                "action": "SPECIALTY_RECOMMENDATION",
                "recommended_specialty": condition_department,
                "possible_condition": condition_name,
                "available_slots": [],
                "safety": {
                    "level": "SAFE_WITH_LIMIT",
                    "allowed": True,
                },
            }

    # --------------------------------------------------------
    # HOME-CARE FALLBACK
    # Runs only when symptom triage did not return a result.
    # Emergency screening above must remain before this block.
    # --------------------------------------------------------
    if not explicit_management_request and not explicit_booking_with_symptom:
        appointment_words = bool(
            re.search(
                r"\b(book|booking|schedule|appointment|reschedule|cancel|doctor|specialist)\b",
                message.lower(),
            )
        )

        if not appointment_words:
            try:
                home_care_matches = get_home_care(message)
            except Exception as exc:
                print(f"Home-care lookup failed: {exc}")
                home_care_matches = []

            if home_care_matches:
                _store_home_care_context(user, home_care_matches)
                return {
                    "response": format_home_care(home_care_matches),
                    "intent": "HOME_CARE",
                    "action": "HOME_CARE_GUIDANCE",
                    "home_care": home_care_matches,
                    "matched_symptoms": [],
                    "possible_conditions": [],
                    "recommended_specialty": None,
                    "available_slots": [],
                    "safety": {
                        "level": "SAFE_WITH_LIMIT",
                        "allowed": True,
                    },
                }
    message_lower = message.lower().strip()

    direct_appointment_request = bool(
        re.search(
            r"\b(book|schedule|reserve)\b.*\b"
            r"(appointment|doctor|specialist|consultation|visit)\b"
            r"|\b(available slots|show slots|find slots|"
            r"check availability|book an appointment|"
            r"schedule an appointment)\b",
            message_lower,
        )
    )

    condition_details = [
        (
            r"\b(asthma|wheezing|bronchial asthma)\b",
            "Asthma is a condition that affects the airways. "
            "It can cause wheezing, coughing, chest tightness, "
            "or breathlessness. A clinician can assess your symptoms.",
        ),
        (
            r"\b(hepatitis b|hepatitis|jaundice)\b",
            "Hepatitis B is a viral infection that affects the liver. "
            "Medical assessment and appropriate testing can help "
            "determine whether infection is present and what care is needed.",
        ),
        (
            r"\b(acne|pimples)\b",
            "Acne is a common skin condition involving blocked or "
            "inflamed hair follicles. A dermatologist can assess "
            "its severity and discuss suitable treatment options.",
        ),
        (
            r"\b(diabetes|high blood sugar|low blood sugar)\b",
            "Diabetes affects how the body regulates blood glucose. "
            "A healthcare professional can assess your glucose levels "
            "and help you manage the condition.",
        ),
        (
            r"\b(migraine|headaches?)\b",
            "Headaches can have different causes. Recurrent or severe "
            "headaches deserve medical assessment; a clinician can "
            "evaluate the pattern and associated symptoms.",
        ),
        (
            r"\b(arthritis|joint pain|bone pain|fracture|back pain)\b",
            "Joint and bone problems can have several causes. "
            "A clinician can assess the location, duration, and "
            "severity of your symptoms.",
        ),
        (
            r"\b(common cold|runny nose|sneezing|sore throat)\b",
            "Cold-like symptoms commonly affect the nose and throat "
            "and can have different causes. A clinician can assess "
            "persistent or worsening symptoms.",
        ),
        (
            r"\b(fever|high temperature)\b",
            "Fever can occur with many different conditions. "
            "Its cause depends on other symptoms and clinical findings; "
            "seek medical assessment if it persists or worsens.",
        ),
    ]

    matched_condition_info = next(
        (
            details
            for pattern, details in condition_details
            if re.search(pattern, message_lower)
        ),
        None,
    )

    condition_department = extract_department_from_message(message)

    if (
        matched_condition_info
        and condition_department
        and not direct_appointment_request
    ):
        # Remember which specialty the patient was offered, scoped to this chat.
        _save_conversation_context(
            user,
            conversation_id,
            pending_booking_department=condition_department,
        )
        return {
            "response": (
                matched_condition_info
                + f"\n\nThe relevant department may be "
                f"{condition_department}. This information cannot "
                "confirm a diagnosis.\n\n"
                "Would you like me to find an available appointment "
                "with a suitable specialist?"
            ),
            "intent": "CONDITION_INFORMATION",
            "action": "ASK_BEFORE_BOOKING",
            "recommended_specialty": condition_department,
            "booking_options": [],
            "available_slots": [],
            "safety": {"level": "SAFE_WITH_LIMIT"},
        }


    # --------------------------------------------------------
    # SLM PRIMARY INTENT
    # --------------------------------------------------------

    slm_result = get_slm_intent(
        message
    )

    if slm_result:

        intent = slm_result.get(
            "intent"
        )

    else:

        intent = detect_intent(
            message
        )

        slm_result = {
            "intent":
                intent,

            "department":
                None,

            "date":
                None,

            "time":
                None,

            "new_date":
                None,

            "new_time":
                None,

            "doctor":
                None,

            "reason":
                None,
        }

    # Continue the pending specialty offer when the patient confirms with "yes".
    # This only applies within the same conversation and does not book anything.
    pending_context = _get_conversation_context(user, conversation_id)
    pending_department = pending_context.get("pending_booking_department")
    if pending_department and _is_yes(message):
        intent = "DOCTOR_AVAILABILITY"
        slm_result["intent"] = intent
        slm_result["department"] = pending_department
        # Empty string clears this value; the context helper ignores None updates.
        _save_conversation_context(
            user,
            conversation_id,
            pending_booking_department="",
        )

    # Deterministic routing for explicit appointment-management commands.
    # The SLM can misclassify these as CHECK_APPOINTMENT; explicit user wording
    # must take precedence over the model's intent label.
    message_lower = message.lower().strip()

    # Explicit appointment-management wording takes precedence over SLM.
    is_reschedule_request = bool(
        re.search(
            r"\b(reschedule|reshedule|resh?edule|"
            r"rescheduling|rescheduled|resheduled|"
            r"reshedule|reschedule)\b",
            message_lower,
        )
        or re.search(
            r"\b(change|move|shift|postpone)\b.*\bappointment\b",
            message_lower,
        )
        or re.search(
            r"\bappointment\b.*\b(to another|to a different|"
            r"another available|different available)\b",
            message_lower,
        )
    )

    is_cancel_request = bool(
        re.search(r"\b(cancel|cancellation|cancelled|canceled)\b", message_lower)
        and re.search(r"\b(appointment|booking|reservation|all)\b", message_lower)
    )

    is_list_request = bool(
        re.search(r"\b(show|list|view)\b", message_lower)
        and re.search(r"\b(my\s+)?(upcoming\s+)?appointments\b", message_lower)
    )

    is_alternative_slots_request = bool(
        re.search(
            r"\b(another|alternative|different|other|more)\b.*"
            r"\b(appointment|appointments|slot|slots|time|times)\b|"
            r"\b(available appointments|other appointments|more appointments)\b",
            message_lower,
        )
    )

    if is_cancel_request:
        intent = "CANCEL_APPOINTMENT"
        slm_result["intent"] = intent
    elif is_reschedule_request:
        intent = "RESCHEDULE_APPOINTMENT"
        slm_result["intent"] = intent
    elif is_list_request:
        intent = "CHECK_APPOINTMENT"
        slm_result["intent"] = intent
    elif is_alternative_slots_request:
        # A request for alternative slots is an availability query, not a new
        # unconstrained booking or a request to reuse a stale SLM date.
        intent = "DOCTOR_AVAILABILITY"
        slm_result["intent"] = intent
        slm_result["date"] = None
        slm_result["time"] = None

    explicit_booking_request = bool(
        re.search(
            r"\b(book|schedule|make|reserve)\b.*\b(appointment|visit|consultation)\b"
            r"|\bappointment\b.*\b(book|schedule|reserve)\b",
            message_lower,
        )
    )

    # Fee questions are informational, not availability searches. Give this
    # deterministic rule priority over an SLM prediction such as
    # DOCTOR_AVAILABILITY or BOOK_APPOINTMENT.
    consultation_fee_request = bool(
        re.search(r"\b(fee|fees|cost|price|charge|charges|how much)\b", message_lower)
        and re.search(
            r"\b(doctor|consultation|appointment|specialist|visit|cardiologist|"
            r"dermatologist|orthopedic|orthopaedic|physician)\b",
            message_lower,
        )
    )

    hospital_faq_request = bool(
        consultation_fee_request
        or re.search(
            r"\b(where is|where are|located|location|address|"
            r"exact street address|street address|hospital hours|"
            r"opening hours|operating hours|working hours|business hours|"
            r"hospital timings|opening time|closing time|what time does .* open|"
            r"what time does .* close|opd|outpatient|doctor consultation|"
            r"consultation hours|doctor timings|doctor hours|open at midnight|"
            r"emergency hours|phone number|contact number|telephone)\b",
            message_lower,
        )
        or re.search(
            r"\b(which|what)\b.*\b(departments|specialties|specialities|services)\b",
            message_lower,
        )
        or re.search(
            r"\b(do you have|does careflow have|does the hospital have|"
            r"which department|is there a|does careflow offer|does the hospital offer)\b.*\b"
            r"(cardiology|cardiologist|dermatology|dermatologist|"
            r"orthopedics|orthopedic|orthopaedics|orthopaedic|general medicine|general physician)\b",
            message_lower,
        )
        or re.search(
            r"\b(is|are)\b.*\b(hospital|careflow)\b.*\b(open|closed)\b",
            message_lower,
        )
        or re.search(
            r"\b(what should i bring|what do i need to bring|what to bring|"
            r"what documents|documents required|document required|"
            r"bring to my appointment|bring to an appointment)\b",
            message_lower,
        )
        or re.search(
            r"\b(what does|what do|describe|explain)\b.*\b"
            r"(cardiology|cardiologist|dermatology|dermatologist|"
            r"orthopedics|orthopedic|orthopaedics|orthopaedic|"
            r"general medicine|general physician)\b",
            message_lower,
        )
    )

    if (
        hospital_faq_request
        and not explicit_booking_request
        and not is_cancel_request
        and not is_reschedule_request
        and not is_list_request
    ):
        intent = "HOSPITAL_FAQ"
        slm_result["intent"] = intent
    if (
        hospital_faq_request
        and not explicit_booking_request
        and not is_cancel_request
        and not is_reschedule_request
        and not is_list_request
    ):
        intent = "HOSPITAL_FAQ"
        slm_result["intent"] = intent

    # Route explicit specialist-seeking questions using the known department.
    # Keep emergency handling and explicit appointment-management rules intact.
    specialist_request = bool(
        re.search(
            r"\b(which|what)\s+(doctor|specialist|specialty|physician)\b"
            r"|\b(which|what)\s+doctor\s+should\s+i\s+see\b"
            r"|\bwhich\s+specialist\s+should\s+i\s+consult\b"
            r"|\bneed\s+a\s+(doctor|specialist|physician)\b"
            r"|\bconsult\s+a\s+(doctor|specialist|physician)\b"
            r"|\bsee\s+a\s+(doctor|specialist|physician)\b",
            message_lower,
        )
    )

    extracted_department = extract_department_from_message(message)

    if (
        specialist_request
        and extracted_department
        and not is_cancel_request
        and not is_reschedule_request
        and not is_list_request
        and not hospital_faq_request
    ):
        intent = "DOCTOR_AVAILABILITY"
        slm_result["intent"] = intent
        slm_result["department"] = extracted_department
    # ========================================================
    # APPOINTMENT REMINDER
    # ========================================================

    if intent == "APPOINTMENT_REMINDER":

        appointments = (
            get_matching_reminder_appointments(
                message,
                slm_result,
            )
        )

        # ----------------------------------------------------
        # No matching appointment
        # ----------------------------------------------------

        if not appointments:
            return {
                "response": (
                    "I couldn't find an active appointment matching those details "
                    "in your account. No appointment has been changed or booked. "
                    "Please check which account you're signed in with, or say "
                    "'show my upcoming appointments' so we can identify the "
                    "appointment you want to reschedule."
                ),
                "intent": "RESCHEDULE_APPOINTMENT",
                "action": "RESCHEDULE_NOT_FOUND",
                "appointment_options": [],
                "available_slots": [],
                "safety": {"level": "SAFE"},
                "slm": slm_result,
            }

        # ----------------------------------------------------
        # Multiple appointments
        # ----------------------------------------------------

        if len(appointments) > 1:

            return {
                "response": (
                    "You have multiple active appointments "
                    "matching your request. Please choose "
                    "the appointment you want a reminder for."
                ),

                "intent":
                    "APPOINTMENT_REMINDER",

                "safety":
                    {
                        "level": "SAFE"
                    },

                "action":
                    "REMINDER_OPTIONS",

                "appointment_options":
                    [
                        serialize_appointment(a)
                        for a in appointments
                    ],

                "slm":
                    slm_result,
            }

        # ----------------------------------------------------
        # Exactly one appointment
        # ----------------------------------------------------

        appointment = appointments[0]

        # ----------------------------------------------------
        # Create reminder
        # ----------------------------------------------------

        try:

            reminder, reminder_message = (
                create_appointment_reminder(
                    appointment
                )
            )

        except Exception as exc:

            print(
                f"Reminder creation failed: {exc}"
            )

            return {
                "response": (
                    "I couldn't create the reminder "
                    "right now."
                ),

                "intent":
                    "APPOINTMENT_REMINDER",

                "safety":
                    {
                        "level": "SAFE"
                    },

                "action":
                    "REMINDER_FAILED",

                "appointment_options":
                    [
                        serialize_appointment(
                            appointment
                        )
                    ],

                "error":
                    str(exc),

                "slm":
                    slm_result,
            }

        # ----------------------------------------------------
        # Reminder failed
        # ----------------------------------------------------

        if reminder is None:

            return {
                "response":
                    reminder_message,

                "intent":
                    "APPOINTMENT_REMINDER",

                "safety":
                    {
                        "level": "SAFE"
                    },

                "action":
                    "REMINDER_FAILED",

                "appointment_options":
                    [
                        serialize_appointment(
                            appointment
                        )
                    ],

                "slm":
                    slm_result,
            }

        # ----------------------------------------------------
        # Reminder created
        # ----------------------------------------------------

        return {
            "response": (
                f"Your reminder is set for the appointment "
                f"with Dr. {appointment.doctor.name} "
                f"on {appointment.appointment_date} "
                f"at {appointment.appointment_time}. "
                f"The reminder is scheduled for "
                f"{reminder.reminder_date} at "
                f"{reminder.reminder_time}."
            ),

            "intent":
                "APPOINTMENT_REMINDER",

            "safety":
                {
                    "level": "SAFE"
                },

            "action":
                "REMINDER_CREATED",

            "reminder": {

                "id":
                    reminder.id,

                "appointment_id":
                    appointment.id,

                "reminder_date":
                    str(
                        reminder.reminder_date
                    ),

                "reminder_time":
                    str(
                        reminder.reminder_time
                    ),

                "status":
                    reminder.status,

                "message":
                    reminder.message,
            },

            "appointment_options":
                [
                    serialize_appointment(
                        appointment
                    )
                ],

            "slm":
                slm_result,
        }

    # ========================================================
    # CANCEL APPOINTMENT
    # ========================================================

    if intent == "CANCEL_APPOINTMENT":

        requested_date = slm_result.get(
            "date"
        )

        requested_time = slm_result.get(
            "time"
        )

        requested_doctor = slm_result.get(
            "doctor"
        )

        requested_department = slm_result.get(
            "department"
        )

        # Do not rely entirely on the SLM: extract explicit date/time/doctor
        # details from the user's message when a field is missing.
        message_date, message_time = _extract_date_time_from_message(message)
        # Explicit details in the user's text always win over inferred SLM fields.
        if message_date:
            requested_date = message_date
        if message_time:
            requested_time = message_time
        message_doctor = extract_doctor_from_message(message)
        if message_doctor:
            requested_doctor = message_doctor
        if not requested_department:
            requested_department = extract_department_from_message(message)

        if (
            requested_date
            or requested_time
            or requested_doctor
            or requested_department
        ):
            appointments = find_matching_appointments(
                user=user,
                requested_date=requested_date,
                requested_time=requested_time,
                requested_doctor=requested_doctor,
                requested_department=requested_department,
            )

        else:

            appointments = get_patient_appointments(user, active_only=True)

        if not appointments:

            return {
                "response": (
                    "I couldn't find an active appointment "
                    "matching those details."
                ),

                "intent":
                    "CANCEL_APPOINTMENT",

                "safety":
                    {
                        "level": "SAFE"
                    },

                "action":
                    "CANCEL",

                "appointment_options":
                    [],

                "slm":
                    slm_result,
            }

        if len(appointments) == 1:

            appointment = appointments[0]

            return {
                "response": (
                    f"I found your appointment with "
                    f"Dr. {appointment['doctor_name']} "
                    f"on {appointment['date']} at "
                    f"{appointment['time']}. "
                    f"Please confirm that you want to cancel it."
                ),

                "intent":
                    "CANCEL_APPOINTMENT",

                "safety":
                    {
                        "level": "SAFE"
                    },

                "action":
                    "CANCEL_CONFIRMATION",

                "appointment_options":
                    appointments,

                "confirmation": _make_confirmation(
                    "CANCEL_APPOINTMENT", user, appointment["id"]
                ),

                "slm":
                    slm_result,
            }

        return {
            "response": (
                "I found multiple matching appointments. "
                "Please choose the appointment you want to cancel."
            ),

            "intent":
                "CANCEL_APPOINTMENT",

            "safety":
                {
                    "level": "SAFE"
                },

            "action":
                "CANCEL",

            "appointment_options":
                appointments,

            "slm":
                slm_result,
        }

    # ========================================================
    # RESCHEDULE APPOINTMENT
    # ========================================================

    if intent == "RESCHEDULE_APPOINTMENT":

        requested_date = slm_result.get(
            "date"
        )

        requested_time = slm_result.get(
            "time"
        )

        requested_doctor = slm_result.get(
            "doctor"
        )

        requested_department = slm_result.get(
            "department"
        )

        new_date = slm_result.get(
            "new_date"
        )

        new_time = slm_result.get(
            "new_time"
        )

        # Fallback parsing is important for rescheduling: the SLM may omit
        # the current appointment time or confuse it with the requested slot.
        # Split at the destination phrase so current details and new details
        # are extracted independently.
        message_text = str(message or "").strip()
        destination_match = re.search(
            r"\bto\s+(?="
            r"today\b|tomorrow\b|yesterday\b|"
            r"(?:this|next)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|"
            r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
            r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
            r"nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}\b|"
            r"\d{1,2}\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
            r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
            r"nov(?:ember)?|dec(?:ember)?)\s+\d{4}\b|"
            r"\d{1,2}[/-]\d{1,2}[/-]\d{4}\b|"
            r"\d{4}-\d{2}-\d{2}\b|"
            r"\d{1,2}\s*(?:AM|PM)\b"
            r")",
            message_text,
            re.IGNORECASE,
        )
        current_text = message_text[:destination_match.start()] if destination_match else message_text
        destination_text = message_text[destination_match.end():] if destination_match else ""

        current_date_from_text, current_time_from_text = _extract_date_time_from_message(current_text)
        new_date_from_text, new_time_from_text = _extract_date_time_from_message(destination_text)

        # Do not let hallucinated/inferred SLM dates select the wrong existing
        # appointment. Current appointment details come only from the part of
        # the user's message before the destination phrase.
        requested_date = current_date_from_text
        requested_time = current_time_from_text
        message_doctor = extract_doctor_from_message(message_text)
        if message_doctor:
            requested_doctor = message_doctor
        message_department = extract_department_from_message(message_text)
        if message_department:
            requested_department = message_department
        if new_date_from_text:
            new_date = new_date_from_text
        if new_time_from_text:
            new_time = new_time_from_text

        # For vague destinations ("another available slot", "a different
        # slot"), do not trust a date/time guessed by the SLM. The user has
        # not selected a destination yet, so show available slots instead of
        # incorrectly searching today's date.
        vague_destination = bool(re.search(
            r"\b(another\s+(?:available\s+)?(?:slot|time|date)|"
            r"different\s+(?:slot|time|date)|any\s+(?:available\s+)?slot|"
            r"next\s+available\s+slot)\b",
            message_text,
            re.IGNORECASE,
        ))
        if vague_destination and not new_date_from_text and not new_time_from_text:
            new_date = None
            new_time = None

        resolved_new_date = (
            resolve_requested_date(
                new_date
            )
        )

        resolved_new_time = (
            normalize_time_value(
                new_time
            )
        )

        if not resolved_new_date or not resolved_new_time:

            # Identify the existing appointment NOW and keep its ID
            # for the next user message. This fixes the previous
            # problem where "October 10 at 4 PM" was treated as
            # an unrelated new chat request.
            if (
                requested_date
                or requested_time
                or requested_doctor
                or requested_department
            ):
                appointments = find_matching_appointments(
                    requested_date=requested_date,
                    requested_time=requested_time,
                    requested_doctor=requested_doctor,
                    requested_department=requested_department,
                    user=user,
                )
            else:
                appointments = get_patient_appointments(user, active_only=True)

            if not appointments and requested_doctor and requested_date:
                # If the user gave a slightly different current time (for
                # example 1.30 PM instead of 2 PM), use the unique appointment
                # with that doctor on that date rather than losing the context.
                fallback = find_matching_appointments(
                    requested_date=requested_date,
                    requested_doctor=requested_doctor,
                    user=user,
                )
                if len(fallback) == 1:
                    appointments = fallback

            if not appointments:
                slots = _suggest_available_slots(
                    department=requested_department,
                    requested_date="tomorrow",
                    doctor_name=requested_doctor,
                    user=user,
                )
                return {
                    "response": (
                        "I couldn't find an active appointment to reschedule. "
                        "Please select one of the available slots below to book an appointment."
                    ),
                    "intent": "BOOK_APPOINTMENT",
                    "action": "AVAILABLE_SLOTS",
                    "appointment_options": [],
                    "available_slots": slots,
                    "safety": {"level": "SAFE"},
                    "slm": slm_result,
                }

            if len(appointments) > 1:
                # Ask the patient to choose the existing appointment first.
                # List the options in text because the current frontend renders
                # available slots but does not render appointment_options as cards.
                option_lines = []
                for index, option in enumerate(appointments, start=1):
                    option_lines.append(
                        f"{index}. Dr. {option.get('doctor_name', 'Unknown doctor')} — "
                        f"{option.get('date', 'date unavailable')} at "
                        f"{option.get('time', 'time unavailable')} "
                        f"({option.get('department', 'Specialty unavailable')}); "
                        f"status: {option.get('status', 'unknown')}"
                    )
                options_text = "\n".join(option_lines)
                return {
                    "response": (
                        "I found multiple active appointments. Which one would you like "
                        "to reschedule?\n\n"
                        f"{options_text}\n\n"
                        "Reply with the doctor's name, for example: "
                        "'Reschedule Dr. Priya Rao's appointment'. I will show replacement "
                        "slots only after you choose an appointment."
                    ),
                    "intent": "RESCHEDULE_APPOINTMENT",
                    "action": "RESCHEDULE_SELECTION_REQUIRED",
                    "appointment_options": appointments,
                    "available_slots": [],
                    "safety": {"level": "SAFE"},
                    "slm": slm_result,
                }

            appointment = appointments[0]
            _set_reschedule_context(user, appointment["id"])

            missing = "date and time"
            if resolved_new_date and not resolved_new_time:
                missing = "time"
            elif resolved_new_time and not resolved_new_date:
                missing = "date"

            slots = _suggest_available_slots(
                department=requested_department or appointment.get("department"),
                requested_date=None,
                doctor_name=appointment.get("doctor_name"),
                limit=25,
                user=user,
            )
            return {
                "response": (
                    f"I found your appointment with Dr. {appointment['doctor_name']} "
                    f"on {appointment['date']} at {appointment['time']}. "
                    f"Please provide the new appointment {missing}, or select one of the "
                    "available slots for the next five days below."
                ),
                "intent": "RESCHEDULE_APPOINTMENT",
                "action": "RESCHEDULE_DETAILS_REQUIRED",
                "appointment_options": [appointment],
                "available_slots": slots,
                "safety": {"level": "SAFE"},
                "slm": slm_result,
            }

        if (
            requested_date
            or requested_time
            or requested_doctor
            or requested_department
        ):

            appointments = (
                find_matching_appointments(
                    requested_date=requested_date,
                    requested_time=requested_time,
                    requested_doctor=requested_doctor,
                    requested_department=requested_department,
                    user=user,
                )
            )

        else:
            appointments = get_patient_appointments(user, active_only=True)

        if not appointments:
            return {
                "response": (
                    "I couldn't find an active appointment to reschedule "
                    "in your account. No appointment has been booked or changed. "
                    "Please check your upcoming appointments and try again."
                ),
                "intent": "RESCHEDULE_APPOINTMENT",
                "action": "RESCHEDULE_NOT_FOUND",
                "appointment_options": [],
                "available_slots": [],
                "safety": {"level": "SAFE"},
                "slm": slm_result,
            }

        if len(appointments) > 1:

            return {
                "response": (
                    "I found multiple matching appointments. "
                    "Please choose the appointment you want "
                    "to reschedule."
                ),

                "intent":
                    "RESCHEDULE_APPOINTMENT",

                "safety":
                    {
                        "level": "SAFE"
                    },

                "action":
                    "RESCHEDULE",

                "appointment_options":
                    appointments,

                "new_date":
                    resolved_new_date.isoformat(),

                "new_time":
                    resolved_new_time.strftime(
                        "%H:%M:%S"
                    ),

                "slm":
                    slm_result,
            }

        appointment = appointments[0]

        appointment_id = appointment["id"]

        doctor_id = appointment["doctor_id"]

        available = is_slot_available(
            doctor_id=doctor_id,
            requested_date=resolved_new_date,
            requested_time=resolved_new_time,
            exclude_appointment_id=appointment_id,
            user=user,
        )

        if not available:

            return {
                "response": (
                    f"The requested new slot on "
                    f"{resolved_new_date.isoformat()} at "
                    f"{resolved_new_time.strftime('%H:%M')} "
                    f"is not available for Dr. "
                    f"{appointment['doctor_name']}. "
                    f"Please choose another date or time."
                ),

                "intent":
                    "RESCHEDULE_APPOINTMENT",

                "safety":
                    {
                        "level": "SAFE"
                    },

                "action":
                    "RESCHEDULE_UNAVAILABLE",

                "appointment_options":
                    [appointment],

                "new_date":
                    resolved_new_date.isoformat(),

                "new_time":
                    resolved_new_time.strftime(
                        "%H:%M:%S"
                    ),

                "slm":
                    slm_result,
            }

        return {
            "response": (
                f"I found your appointment with "
                f"Dr. {appointment['doctor_name']} "
                f"on {appointment['date']} at "
                f"{appointment['time']}. "
                f"The new slot on "
                f"{resolved_new_date.isoformat()} at "
                f"{resolved_new_time.strftime('%H:%M')} "
                f"is available. "
                f"Please confirm that you want to "
                f"reschedule this appointment."
            ),

            "intent":
                "RESCHEDULE_APPOINTMENT",

            "safety":
                {
                    "level": "SAFE"
                },

            "action":
                "RESCHEDULE_CONFIRMATION",

            "appointment_options":
                [appointment],

            "new_date":
                resolved_new_date.isoformat(),

            "new_time":
                resolved_new_time.strftime(
                    "%H:%M:%S"
                ),

            "confirmation": _make_confirmation(
                "RESCHEDULE_APPOINTMENT",
                user,
                appointment_id,
                new_date=resolved_new_date.isoformat(),
                new_time=resolved_new_time.strftime("%H:%M:%S"),
            ),

            "slm":
                slm_result,
        }

    # ========================================================
    # CHECK APPOINTMENT
    # ========================================================

    if intent == "CHECK_APPOINTMENT":

        appointments = (
            get_patient_appointments(user)
        )

        if not appointments:

            return {
                "response":
                    "You currently have no active appointments.",

                "intent":
                    "CHECK_APPOINTMENT",

                "safety":
                    {
                        "level": "SAFE"
                    },

                "appointment_options":
                    [],
            }

        return {
            "response":
                "Here are your current appointments.",

            "intent":
                "CHECK_APPOINTMENT",

            "safety":
                {
                    "level": "SAFE"
                },

            "appointment_options":
                appointments,

            "slm":
                slm_result,
        }

    # ========================================================
    # DOCTOR AVAILABILITY
    # ========================================================

    if intent == "DOCTOR_AVAILABILITY":
        message_date, _ = _extract_date_time_from_message(message)
        conversation_context = _get_conversation_context(user, conversation_id)
        alternative_request = bool(re.search(
            r"\b(another|alternative|different|other|more)\b.*"
            r"\b(appointment|appointments|slot|slots|time|times)\b|"
            r"\b(available appointments|other appointments|more appointments)\b",
            message.lower(),
        ))

        # Only restrict the search to one day when the patient explicitly
        # mentioned a date (for example, "today", "tomorrow", or "15 Oct").
        # The SLM often fills in today's date even when the patient did not ask
        # for a specific day; do not treat that inferred date as a restriction.
        # Without an explicit date, search the rolling five-day window.
        requested_date = None if alternative_request else message_date

        requested_doctor = (
            extract_doctor_from_message(message)
            or slm_result.get("doctor")
        )

        explicit_department = extract_department_from_message(message)
        department = explicit_department or slm_result.get("department")
        if alternative_request and not department:
            department = conversation_context.get("department") or None
        department = _apply_previous_department_context(
            user, message, department, conversation_id
        )

        if _needs_department_clarification(user, message, explicit_department, conversation_id):
            return {
                "response": (
                    "Which specialist did you mean—Cardiology, Dermatology, "
                    "Orthopedics, or General Medicine? I don't have the earlier "
                    "doctor context available in this chat, so I don't want to "
                    "show you slots for the wrong department."
                ),
                "intent": "DOCTOR_AVAILABILITY",
                "action": "DEPARTMENT_CLARIFICATION_REQUIRED",
                "booking_options": [],
                "safety": {"level": "SAFE"},
                "slm": slm_result,
            }

        if requested_doctor:
            requested_doctor = extract_doctor_from_message(message)

        if alternative_request or not requested_date:
            options = _suggest_available_slots(
                department=department,
                requested_date=None,
                doctor_name=requested_doctor,
                limit=100,
                user=user,
            )
        else:
            options = get_booking_options(
                department=department,
                requested_date=requested_date,
                doctor_name=requested_doctor,
                slots_per_doctor=5,
                user=user,
            )

        resolved_date = resolve_requested_date(requested_date) if requested_date else None

        if not options:
            if requested_date:
                date_label = resolved_date.strftime("%d %b %Y") if resolved_date else str(requested_date)
                response_text = (
                    f"I couldn't find available slots"
                    f"{' with Dr. ' + requested_doctor if requested_doctor else ''}"
                    f"{' in ' + department if department else ''}"
                    f" for {date_label}. Please try another date."
                )
            else:
                response_text = (
                    "I couldn't find available slots in the next five days"
                    f"{' with Dr. ' + requested_doctor if requested_doctor else ''}"
                    f"{' in ' + department if department else ''}. "
                    "Please try another date or specialty."
                )
        elif requested_date:
            date_label = resolved_date.strftime("%d %b %Y") if resolved_date else str(requested_date)
            response_text = f"Here are the available appointment slots for {date_label}."
        else:
            response_text = "Here are the available appointment slots for the next five days."

        _remember_booking_options(user, conversation_id, options, department=department)
        return {
            "response": response_text,
            "intent": "DOCTOR_AVAILABILITY",
            "safety": {"level": "SAFE"},
            "booking_options": options,
            "slm": slm_result,
        }

    # ========================================================
    # BOOK APPOINTMENT
    # ========================================================

    if intent == "BOOK_APPOINTMENT":
        message_date, message_time = _extract_date_time_from_message(message)
        conversation_context = _get_conversation_context(user, conversation_id)
        alternative_request = bool(re.search(
            r"\b(another|alternative|different|other|more)\b.*"
            r"\b(appointment|appointments|slot|slots|time|times)\b|"
            r"\b(available appointments|other appointments|more appointments)\b",
            message.lower(),
        ))

        # Do not use a guessed date for a vague request for alternatives.
        requested_date = (
            None if alternative_request
            else (slm_result.get("date") or message_date or None)
        )

        requested_doctor = extract_doctor_from_message(message)

        department = (
            extract_department_from_message(message)
            or slm_result.get("department")
        )
        if alternative_request and not department:
            department = conversation_context.get("department") or None

        # Carry the previous specialty into follow-up booking requests such
        # as "Can I book an appointment with that doctor tomorrow?"
        explicit_department = extract_department_from_message(message)
        department = _apply_previous_department_context(
            user, message, department, conversation_id
        )

        if _needs_department_clarification(user, message, explicit_department, conversation_id):
            return {
                "response": (
                    "Which specialist did you mean—Cardiology, Dermatology, "
                    "Orthopedics, or General Medicine? I don't have the earlier "
                    "doctor context available in this chat, so I don't want to "
                    "show you slots for the wrong department."
                ),
                "intent": "BOOK_APPOINTMENT",
                "action": "DEPARTMENT_CLARIFICATION_REQUIRED",
                "booking_options": [],
                "safety": {"level": "SAFE"},
                "slm": slm_result,
            }
        if not requested_doctor:
            requested_doctor = None

        # Explicit date: search that date only.
        # No date: offer real slots from the next five days.
        if requested_date:
            options = get_booking_options(
                department=department,
                requested_date=requested_date,
                doctor_name=requested_doctor,
                slots_per_doctor=5,
                user=user,
            )
        else:
            options = _suggest_available_slots(
                department=department,
                requested_date=None,
                doctor_name=requested_doctor,
                limit=25,
                user=user,
            )

        resolved_date = resolve_requested_date(requested_date)

        requested_time = (
            normalize_time_value(slm_result.get("time"))
            or normalize_time_value(message_time)
        )

        # For follow-ups such as "Book the 10:00 AM slot", match only slots
        # actually shown in this same chat. If more than one doctor has that
        # time, show those matching choices instead of guessing.
        context = _get_conversation_context(user, conversation_id)
        is_time_slot_followup = bool(
            requested_time and re.search(
                r"\b(book|choose|select|take|reserve)\b.*\b(slot|appointment|\d{1,2}\s*:?\d{0,2})\b|"
                r"\b(the|that)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)\s+slot\b",
                message.lower(),
            )
        )
        if is_time_slot_followup:
            prior_slots = context.get("last_slots") or []
            matched_slots = [
                slot for slot in prior_slots
                if normalize_time_value(slot.get("time")) == requested_time
            ]
            if not prior_slots:
                return {
                    "response": "I don't have the previously displayed slots available in this chat. Please ask me to show available appointments again, then choose a time.",
                    "intent": "BOOK_APPOINTMENT",
                    "action": "PREVIOUS_SLOTS_NOT_FOUND",
                    "booking_options": [],
                    "safety": {"level": "SAFE"},
                    "slm": slm_result,
                }
            options = matched_slots
            if not options:
                return {
                    "response": f"I couldn't match {requested_time.strftime('%I:%M %p').lstrip('0')} to the slots I showed earlier. Please choose one of the displayed times or ask me to show availability again.",
                    "intent": "BOOK_APPOINTMENT",
                    "action": "SLOT_NOT_FOUND_IN_CONTEXT",
                    "booking_options": [],
                    "safety": {"level": "SAFE"},
                    "slm": slm_result,
                }
            requested_date = options[0].get("date") or requested_date

        if requested_time:
            options.sort(
                key=lambda slot: (
                    normalize_time_value(slot.get("time")) != requested_time,
                    slot.get("date", ""),
                    slot.get("doctor_name", "").lower(),
                    slot.get("time", ""),
                )
            )

        # A selected slot must match a slot shown in this conversation.
        # Ask for confirmation before creating the appointment.
        if is_time_slot_followup and requested_time:
            requested_doctor_lower = (requested_doctor or "").strip().lower()
            requested_date_iso = (
                resolved_date.isoformat() if resolved_date else None
            )

            matching_options = [
                slot for slot in options
                if normalize_time_value(slot.get("time")) == requested_time
                and (
                    not requested_doctor_lower
                    or requested_doctor_lower in slot.get("doctor_name", "").lower()
                )
                and (
                    not requested_date_iso
                    or str(slot.get("date")) == requested_date_iso
                )
            ]

            if len(matching_options) == 1:
                selected_slot = matching_options[0]

                try:
                    selected_date = resolve_requested_date(
                        selected_slot.get("date")
                    )
                    selected_time = normalize_time_value(
                        selected_slot.get("time")
                    )
                    selected_doctor = Doctor.objects.filter(
                        id=selected_slot.get("doctor_id"),
                        is_active=True,
                    ).first()

                    if (
                        selected_doctor
                        and selected_date
                        and selected_time
                        and is_slot_available(
                            doctor_id=selected_doctor.id,
                            requested_date=selected_date,
                            requested_time=selected_time,
                            user=user,
                        )
                    ):
                        confirmation_data = _make_confirmation(
                            "BOOK_APPOINTMENT",
                            user,
                            None,
                            doctor_id=selected_doctor.id,
                            date=selected_date.isoformat(),
                            time=selected_time.strftime("%H:%M"),
                        )

                        return {
                            "response": (
                                f"Please confirm your appointment with "
                                f"Dr. {selected_doctor.name} on "
                                f"{selected_date.strftime('%d %b %Y')} at "
                                f"{selected_time.strftime('%I:%M %p').lstrip('0')}. "
                                f"Reply Yes to confirm or No to cancel."
                            ),
                            "intent": "BOOK_APPOINTMENT",
                            "action": "BOOKING_CONFIRMATION_REQUIRED",
                            "confirmation": confirmation_data,
                            "booking_options": [selected_slot],
                            "safety": {"level": "SAFE"},
                            "slm": slm_result,
                        }

                except (TypeError, ValueError):
                    pass

            elif len(matching_options) > 1:
                return {
                    "response": (
                        "Several doctors have that time available. "
                        "Please specify the doctor's name and appointment date."
                    ),
                    "intent": "BOOK_APPOINTMENT",
                    "action": "SELECT_DOCTOR",
                    "booking_options": matching_options,
                    "safety": {"level": "SAFE"},
                    "slm": slm_result,
                }


        if not options:
            if requested_date:
                date_label = (
                    resolved_date.strftime("%d %b %Y")
                    if resolved_date
                    else str(requested_date)
                )
                response_text = (
                    f"I couldn't find available appointment slots for "
                    f"{date_label}"
                    f"{' in ' + department if department else ''}. "
                    "Please try another date or department."
                )
            else:
                response_text = (
                    "I couldn't find available appointment slots in the "
                    "next five days"
                    f"{' in ' + department if department else ''}. "
                    "Please try another department or date."
                )

            return {
                "response": response_text,
                "intent": "BOOK_APPOINTMENT",
                "safety": {"level": "SAFE"},
                "booking_options": [],
                "slm": slm_result,
            }

        if requested_date:
            date_label = (
                resolved_date.strftime("%d %b %Y")
                if resolved_date
                else str(requested_date)
            )
            response_text = (
                f"Here are the available appointment slots for {date_label}."
            )
        else:
            response_text = (
                "Here are the available appointment slots for the next "
                "five days. Please choose a slot."
            )

        if requested_doctor:
            response_text = (
                f"I found available slots with Dr. {requested_doctor}. "
                + (
                    f"Here are the slots for {date_label}."
                    if requested_date
                    else "Here are the available slots for the next five days."
                )
                + " Please choose a slot."
            )
        elif department:
            response_text = (
                f"I found available {department} appointments. "
                + (
                    f"Here are the slots for {date_label}."
                    if requested_date
                    else "Here are the available slots for the next five days."
                )
                + " Please choose a doctor and slot."
            )

        if requested_time and not any(
            normalize_time_value(slot.get("time")) == requested_time
            for slot in options
        ):
            response_text += (
                f" The requested time "
                f"{requested_time.strftime('%I:%M %p').lstrip('0')} "
                "is not available, so please choose one of the listed times."
            )

        _remember_booking_options(user, conversation_id, options, department=department)
        return {
            "response": response_text,
            "intent": "BOOK_APPOINTMENT",
            "safety": {"level": "SAFE"},
            "booking_options": options,
            "slm": slm_result,
        }
    # ========================================================
    # HOSPITAL FAQ + RAG
    # ========================================================

    if intent == "HOSPITAL_FAQ":
        question = message.lower().strip()

        # Save a department when this FAQ explicitly discusses a specialty.
        # General FAQs (for example, appointment documents) leave the saved
        # department unchanged so the next follow-up can still refer to it.
        _remember_conversation_department(user, question, conversation_id)

        # Resolve contextual consultation-fee questions from actual doctor
        # records. If only a department is known, list fees for its doctors
        # instead of pretending a particular doctor was named.
        fee_question = bool(re.search(
            r"\b(fee|fees|cost|price|charge|charges|how much)\b", question
        ) and re.search(r"\b(doctor|consultation|appointment|that doctor|specialist|visit)\b", question))
        if fee_question and _is_previous_doctor_reference(question):
            context = _get_conversation_context(user, conversation_id)
            doctor_name = context.get("doctor_name")
            department = context.get("department")
            doctors = Doctor.objects.filter(is_active=True).select_related("department")
            if doctor_name:
                doctors = doctors.filter(name__iexact=doctor_name)
            elif department:
                doctors = doctors.filter(department__name__iexact=department)
            fee_rows = list(doctors.order_by("name").values_list("name", "consultation_fee", "department__name")[:20])
            if fee_rows:
                if len(fee_rows) == 1:
                    name, fee, dept = fee_rows[0]
                    response = f"Dr. {name}'s consultation fee is ₹{fee}." + (f" Department: {dept}." if dept else "")
                else:
                    details = "; ".join(f"Dr. {name} ({dept or 'Department not listed'}): ₹{fee}" for name, fee, dept in fee_rows)
                    response = f"I remember you were asking about {department or 'this specialist'}. The listed consultation fees are: {details}. Which doctor would you like to book with?"
                return {
                    "response": response,
                    "intent": "HOSPITAL_FAQ",
                    "action": "CONSULTATION_FEES_FROM_CONTEXT",
                    "safety": {"level": "SAFE"},
                    "rag": {"used": False},
                    "slm": slm_result,
                }
            return {
                "response": "I couldn't find a configured consultation fee for that doctor. Please choose the doctor from the available appointment slots or contact the hospital to confirm the fee.",
                "intent": "HOSPITAL_FAQ",
                "action": "CONSULTATION_FEE_NOT_CONFIGURED",
                "safety": {"level": "SAFE"},
                "rag": {"used": False},
                "slm": slm_result,
            }

        # Answer verified static facts directly instead of relying
        # on semantic similarity for these common questions.

        # The current knowledge base does not specify an official document
        # checklist. Give a clearly labeled general checklist rather than
        # allowing RAG to return an unrelated section about doctor workflows.
        if re.search(
            r"\b(what should i bring|what do i need to bring|what to bring|"
            r"what documents|documents required|document required|"
            r"bring to my appointment|bring to an appointment)\b",
            question,
        ):
            response = (
                "For a routine appointment, a general checklist is: bring "
                "your appointment confirmation, a photo ID, any previous "
                "medical reports or test results, and your current prescription "
                "or medicine list. Bring insurance details if you plan to use "
                "insurance. This is general guidance, not a confirmed CareFlow "
                "Hospital document policy; please contact the hospital to verify "
                "any additional requirements."
            )
        elif re.search(
            r"\b(where is|where are|located|location)\b",
            question,
        ):
            response = (
                "CareFlow Hospital is associated with "
                "Hyderabad, Telangana, India. "
                "The exact street address is not currently "
                "configured in the hospital knowledge base."
            )
        elif re.search(
            r"\b(what services|which services|services provided|"
            r"services offered|hospital services|what does .* provide)\b",
            question,
        ):
            response = (
                "CareFlow Hospital provides Cardiology, Dermatology, "
                "Orthopedics, and General Medicine services. "
                "The system also supports appointment scheduling, "
                "rescheduling, cancellation, patient communication, "
                "and appointment reminders."
            )
        elif re.search(
            r"\b(address|street address)\b",
            question,
        ):
            response = (
                "The exact street address is not currently "
                "configured in the CareFlow hospital knowledge base."
            )

        # OPD-specific questions receive only the OPD schedule.
        elif re.search(
            r"\b(opd|outpatient|doctor consultation|consultation hours|"
            r"doctor timings|doctor hours|see a doctor|consult a doctor)\\b",
            question,
        ) and re.search(
            r"\b(hours|timings|time|when|open|available|consultation|doctor|opd|outpatient)\\b",
            question,
        ):
            response = (
                "CareFlow OPD / Doctor Consultation timings: "
                "9:00 AM–8:00 PM, all days. "
                "Note: You mentioned that Practo lists regular OPD as "
                "Monday–Saturday, 10:00 AM–5:00 PM. The schedules differ, "
                "so please confirm with the hospital before visiting."
            )

        # Midnight/night questions focus on 24-hour hospital services,
        # while clarifying that OPD has separate hours.
        elif re.search(
            r"\b(midnight|late night|at night|overnight|24.?7|"
            r"emergency hours|is .* open|are .* open)\\b",
            question,
        ):
            response = (
                "CareFlow Hospital's emergency / hospital services are "
                "listed as open 24 hours a day, Monday to Sunday. "
                "OPD / Doctor Consultation is listed as 9:00 AM–8:00 PM, "
                "all days."
            )

        # General opening-hours questions include both schedules.
        elif re.search(
            r"\b(opening hours|operating hours|working hours|business hours|"
            r"hospital timings|opening time|closing time|hospital hours|"
            r"what time does .* open|what time does .* close|"
            r"what are the hospital|hospital opening)\\b",
            question,
        ):
            response = (
                "CareFlow Hospital timing information:\\n"
                "• Emergency / Hospital: Open 24 hours a day, Monday to Sunday.\\n"
                "• OPD / Doctor Consultation: 9:00 AM–8:00 PM, all days.\\n"
                "Note: You mentioned that Practo lists regular OPD as "
                "Monday–Saturday, 10:00 AM–5:00 PM. These schedules differ, "
                "so please confirm OPD timings with the hospital before visiting."
            )

        elif re.search(
            r"\b(phone number|contact number|telephone)\b",
            question,
        ):
            response = (
                "CareFlow Hospital phone number: 9999999999."
            )

        elif re.search(
            r"\b(cardiology|cardiologist)\b",
            question,
        ) and re.search(
            r"\b(department|departments|have|offer|provide|specialty|specialities|service|services|does|which|what)\b",
            question,
        ):
            response = (
                "Yes. CareFlow Hospital's Cardiology department "
                "handles heart and cardiovascular-related consultations."
            )

        elif re.search(
            r"\b(dermatology|dermatologist)\b",
            question,
        ) and re.search(
            r"\b(department|departments|have|offer|provide|specialty|specialities)\b",
            question,
        ):
            response = (
                "CareFlow Hospital's Dermatology department handles "
                "skin, hair, and related dermatological consultations."
            )

        elif re.search(
            r"\b(orthopedics|orthopedic)\b",
            question,
        ) and re.search(
            r"\b(department|departments|have|offer|provide|specialty|specialities)\b",
            question,
        ):
            response = (
                "CareFlow Hospital's Orthopedics department handles "
                "bone, joint, muscle, and musculoskeletal consultations."
            )

        elif re.search(
            r"\b(general medicine|general physician)\b",
            question,
        ) and re.search(
            r"\b(department|departments|have|offer|provide|specialty|specialities)\b",
            question,
        ):
            response = (
                "CareFlow Hospital's General Medicine department "
                "provides general medical consultations and "
                "primary healthcare services."
            )

        elif re.search(
            r"\b(which|what)\b.*\b(departments|specialties|specialities)\b",
            question,
        ):
            response = (
                "The configured CareFlow hospital departments are "
                "Cardiology, Dermatology, Orthopedics, and General Medicine."
            )

        else:
            response = None

        if response is not None:
            return {
                "response": response,
                "intent": "HOSPITAL_FAQ",
                "safety": {"level": "SAFE"},
                "rag": {"used": False},
                "slm": slm_result,
            }

        try:

            results = query_rag(
                message,
                top_k=3,
            )

            response = build_rag_response(
                message,
                results,
            )

            return {
                "response":
                    response,

                "intent":
                    "HOSPITAL_FAQ",

                "safety":
                    {
                        "level": "SAFE"
                    },

                "rag": {
                    "used":
                        True,

                    "results":
                        results,
                },

                "slm":
                    slm_result,
            }

        except Exception as exc:

            return {
                "response": (
                    "I couldn't access the hospital "
                    "knowledge base right now."
                ),

                "intent":
                    "HOSPITAL_FAQ",

                "safety":
                    {
                        "level": "SAFE"
                    },

                "rag": {
                    "used":
                        False,

                    "error":
                        str(exc),
                },

                "slm":
                    slm_result,
            }

    # ========================================================
    # MEDICAL QUERY
    # ========================================================

    if intent == "MEDICAL_QUERY":

        return {
            "response": (
                "I can help with appointments and "
                "general hospital information, but I "
                "cannot diagnose medical conditions or "
                "prescribe medicines."
            ),

            "intent":
                "MEDICAL_QUERY",

            "safety":
                safety,

            "slm":
                slm_result,
        }

    # ========================================================
    # GENERAL QUERY
    # ========================================================

    if len(message.strip()) <= 2 and not re.search(r"\b(hi|hey|ok|no|yes)\b", message.lower()):
        return {
            "response": "I didn't understand that message. Please type a question about hospital information, symptoms, doctors, or appointments.",
            "intent": "GENERAL_QUERY",
            "action": "CLARIFICATION_REQUIRED",
            "safety": safety,
            "slm": slm_result,
        }

    return {
        "response": (
            "I can help you with appointments, "
            "doctor availability, rescheduling, "
            "cancellation, reminders and hospital "
            "information."
        ),

        "intent":
            intent,

        "safety":
            safety,

        "slm":
            slm_result,
    }