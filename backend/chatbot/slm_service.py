import sys
from pathlib import Path
import re


BASE_DIR = Path(__file__).resolve().parent.parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


import json
import os
import urllib.request

SLM_URL = os.getenv("SLM_URL", "").rstrip("/")
SLM_API_KEY = os.getenv("SLM_API_KEY", "")

if SLM_URL:
    # Remote model on Azure. No PyTorch needed on this server.
    def generate_structured_output(message):
        request = urllib.request.Request(
            f"{SLM_URL}/predict",
            data=json.dumps({"message": message}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": SLM_API_KEY,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=200) as response:
            return json.loads(response.read().decode("utf-8"))
else:
    # Local model, same behaviour as before.
    from slm.service import generate_structured_output

# ============================================================
# DEPARTMENT ALIASES
# ============================================================

DEPARTMENTS = {
    "cardiologist": "Cardiology",
    "cardiology": "Cardiology",

    "orthopedic": "Orthopedics",
    "orthopedics": "Orthopedics",
    "orthopaedic": "Orthopedics",
    "orthopaedics": "Orthopedics",

    "dermatologist": "Dermatology",
    "dermatology": "Dermatology",

    "pediatrician": "Pediatrics",
    "pediatrics": "Pediatrics",

    "neurologist": "Neurology",
    "neurology": "Neurology",

    "dentist": "Dentistry",
    "dental": "Dentistry",

    "general physician": "General Medicine",
    "general medicine": "General Medicine",
    "physician": "General Medicine",
    "general doctor": "General Medicine",
}


# ============================================================
# DATE KEYWORDS
# ============================================================

DATE_KEYWORDS = [
    "today",
    "tomorrow",
    "yesterday",

    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",

    "next monday",
    "next tuesday",
    "next wednesday",
    "next thursday",
    "next friday",
    "next saturday",
    "next sunday",

    "this monday",
    "this tuesday",
    "this wednesday",
    "this thursday",
    "this friday",
    "this saturday",
    "this sunday",
]


# ============================================================
# NORMALIZE DEPARTMENT
# ============================================================

def _normalize_department(message):
    """
    Determine department ONLY from explicit patient wording.

    This prevents the SLM from inventing a department.
    """

    text = message.lower()

    # Check longer phrases first.
    for keyword in sorted(
        DEPARTMENTS.keys(),
        key=len,
        reverse=True,
    ):

        if re.search(
            rf"\b{re.escape(keyword)}\b",
            text,
        ):
            return DEPARTMENTS[keyword]

    return None


# ============================================================
# NORMALIZE DOCTOR
# ============================================================

def _normalize_doctor(message, result):
    """
    Accept doctor_name or doctor from the SLM.

    The doctor is kept only when the doctor name
    actually appears in the user's message.
    """

    doctor = (
        result.get("doctor_name")
        or result.get("doctor")
    )

    if not doctor:
        return None

    doctor = str(doctor).strip()

    if not doctor:
        return None

    message_lower = message.lower()
    doctor_lower = doctor.lower()

    # Exact full-name match.
    if doctor_lower in message_lower:
        return doctor

    # Support "Dr. Priya Rao" vs "Priya Rao".
    without_dr = re.sub(
        r"^dr\.?\s+",
        "",
        doctor_lower,
    ).strip()

    if without_dr and without_dr in message_lower:
        return doctor.replace(
            "Dr. ",
            "",
        ).replace(
            "dr. ",
            "",
        ).strip()

    return None


# ============================================================
# NORMALIZE DATE
# ============================================================

def _normalize_date(message, result):
    """
    Keep a date only if the user explicitly supplied
    a recognizable date expression.
    """

    user_text = message.lower()

    # Relative / weekday dates.
    for keyword in sorted(
        DATE_KEYWORDS,
        key=len,
        reverse=True,
    ):

        if re.search(
            rf"\b{re.escape(keyword)}\b",
            user_text,
        ):
            return result.get(
                "date"
            ) or keyword

    # ISO date.
    iso_match = re.search(
        r"\b\d{4}-\d{2}-\d{2}\b",
        user_text,
    )

    if iso_match:
        return iso_match.group(0)

    # Dates such as:
    # October 8
    # Oct 8
    # October 8, 2026
    month_match = re.search(
        r"\b("
        r"january|february|march|april|may|june|"
        r"july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
        r")"
        r"\s+\d{1,2}"
        r"(?:,\s*\d{4})?\b",
        user_text,
        re.IGNORECASE,
    )

    if month_match:
        return month_match.group(0)

    # No explicit date.
    return None


# ============================================================
# NORMALIZE TIME
# ============================================================

def _normalize_time(message, result):
    """
    Keep a time only when the user explicitly provided
    a recognizable time expression.
    """

    text = message.lower()

    # 3 PM / 3:30 PM
    am_pm_match = re.search(
        r"\b"
        r"(1[0-2]|0?[1-9])"
        r"(?::([0-5]\d))?"
        r"\s*"
        r"(am|pm)"
        r"\b",
        text,
        re.IGNORECASE,
    )

    if am_pm_match:

        hour = int(
            am_pm_match.group(1)
        )

        minute = (
            int(am_pm_match.group(2))
            if am_pm_match.group(2)
            else 0
        )

        period = (
            am_pm_match.group(3)
            .lower()
        )

        if period == "pm" and hour != 12:
            hour += 12

        if period == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"

    # 15:00 / 09:30
    twenty_four_match = re.search(
        r"\b"
        r"([01]\d|2[0-3])"
        r":"
        r"([0-5]\d)"
        r"\b",
        text,
    )

    if twenty_four_match:

        return (
            f"{int(twenty_four_match.group(1)):02d}:"
            f"{int(twenty_four_match.group(2)):02d}"
        )

    # Natural time periods.
    # We deliberately don't invent an exact clock time.
    if re.search(
        r"\b("
        r"morning|afternoon|evening|night"
        r")\b",
        text,
    ):

        return None

    return None


# ============================================================
# NORMALIZE REASON
# ============================================================

def _normalize_reason(message):
    """
    Do not allow the SLM to invent a reason.

    Reason extraction can be added later using explicit
    patient wording.
    """

    return None


# ============================================================
# NORMALIZE INTENT
# ============================================================

ALLOWED_INTENTS = {
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
}


def _normalize_intent(result):
    """
    Keep only known CareFlow intents.
    """

    intent = result.get(
        "intent"
    )

    if not intent:
        return "GENERAL_QUERY"

    intent = str(
        intent
    ).strip().upper()

    if intent not in ALLOWED_INTENTS:
        return "GENERAL_QUERY"

    return intent


# ============================================================
# NORMALIZE COMPLETE RESULT
# ============================================================

def _normalize_result(message, result):
    """
    Deterministic validation layer after SLM inference.

    Important principle:

        SLM understands the request.
        User message provides the facts.

    The SLM is NOT allowed to invent:
        - doctor
        - department
        - date
        - time
        - reason
    """

    if not isinstance(result, dict):
        result = {}

    normalized = {
        "intent": _normalize_intent(
            result
        ),
        "department": _normalize_department(
            message
        ),
        "doctor": _normalize_doctor(
            message,
            result,
        ),
        "date": _normalize_date(
            message,
            result,
        ),
        "time": _normalize_time(
            message,
            result,
        ),
        "reason": _normalize_reason(
            message
        ),
    }

    # --------------------------------------------------------
    # RESCHEDULE SUPPORT
    # --------------------------------------------------------
    #
    # The model may return:
    #
    # new_date
    # new_time
    #
    # We only preserve them when explicitly present
    # in the user's message.
    # --------------------------------------------------------

    new_date = result.get(
        "new_date"
    )

    new_time = result.get(
        "new_time"
    )

    if new_date:

        date_from_message = _normalize_date(
            message,
            {
                "date": new_date,
            },
        )

        if date_from_message:
            normalized["new_date"] = date_from_message
        else:
            normalized["new_date"] = None

    else:

        normalized["new_date"] = None

    if new_time:

        time_from_message = _normalize_time(
            message,
            {
                "time": new_time,
            },
        )

        if time_from_message:
            normalized["new_time"] = time_from_message
        else:
            normalized["new_time"] = None

    else:

        normalized["new_time"] = None

    return normalized


# ============================================================
# RUN SLM
# ============================================================

def run_slm(message):
    """
    Run CareFlow-SLM and return validated structured output.

    The LoRA model performs intent/entity understanding.

    This service performs deterministic validation afterward.
    """

    try:

        result = generate_structured_output(
            message
        )

        if not isinstance(result, dict):

            raise TypeError(
                "SLM output must be a dictionary."
            )

        return _normalize_result(
            message,
            result,
        )

    except Exception as exc:

        print(
            f"SLM inference failed: {exc}"
        )

        # Safe fallback structure.
        return {
            "intent": "GENERAL_QUERY",
            "department": None,
            "doctor": None,
            "date": None,
            "time": None,
            "reason": None,
            "new_date": None,
            "new_time": None,
        }