import sys
from pathlib import Path
import json
import re

# ============================================================
# Project root
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from slm.model import load_model


# ============================================================
# CareFlow-SLM System Prompt
# ============================================================

SYSTEM_PROMPT = """
You are CareFlow-SLM, a healthcare appointment communication assistant.

Your job is ONLY to identify the patient's intent.

Allowed intents:
- BOOK_APPOINTMENT
- CANCEL_APPOINTMENT
- RESCHEDULE_APPOINTMENT
- CHECK_APPOINTMENT
- DOCTOR_AVAILABILITY
- HOSPITAL_FAQ
- APPOINTMENT_REMINDER
- GENERAL_QUERY
- MEDICAL_QUERY
- EMERGENCY
- HUMAN_HANDOFF

Return ONLY valid JSON.

Required JSON:
{
  "intent": "INTENT_NAME",
  "department": null,
  "date": null,
  "time": null,
  "new_date": null,
  "new_time": null,
  "doctor": null,
  "reason": null
}

Important:
- Do NOT calculate or convert dates.
- Do NOT convert times.
- Do NOT invent dates, times, doctors, departments, or reasons.
- Preserve date/time wording exactly as the patient wrote it.
- For RESCHEDULE_APPOINTMENT, date/time refer to the OLD appointment.
- new_date/new_time refer to the NEW requested appointment.
- If a value is not explicitly provided, return null.
- reason must always be null.
- Do not diagnose.
- Do not prescribe medicine.
- Return JSON only.
"""


# ============================================================
# Allowed intents
# ============================================================

ALLOWED_INTENTS = {
    "BOOK_APPOINTMENT",
    "CANCEL_APPOINTMENT",
    "RESCHEDULE_APPOINTMENT",
    "CHECK_APPOINTMENT",
    "DOCTOR_AVAILABILITY",
    "HOSPITAL_FAQ",
    "APPOINTMENT_REMINDER",
    "GENERAL_QUERY",
    "MEDICAL_QUERY",
    "EMERGENCY",
    "HUMAN_HANDOFF",
}


# ============================================================
# Default result
# ============================================================

def _default_result():
    """
    Safe fallback structure.
    """

    return {
        "intent": "GENERAL_QUERY",
        "department": None,
        "date": None,
        "time": None,
        "new_date": None,
        "new_time": None,
        "doctor": None,
        "reason": None,
    }


# ============================================================
# Deterministic fallback intent detection
# ============================================================

def _fallback_intent(message):
    """
    Deterministic fallback used when the SLM does not return
    valid JSON.

    The fallback is intentionally focused on the CareFlow
    healthcare appointment domain.

    This is NOT a replacement for the SLM.

    It protects the workflow when a small model produces
    malformed output.
    """

    text = message.lower().strip()

    # --------------------------------------------------------
    # Emergency
    # --------------------------------------------------------

    emergency_phrases = [
        "emergency",
        "severe chest pain",
        "chest pain",
        "difficulty breathing",
        "can't breathe",
        "cannot breathe",
        "shortness of breath",
        "unconscious",
        "fainted",
        "heavy bleeding",
        "severe bleeding",
        "stroke",
        "heart attack",
        "suicidal",
        "overdose",
    ]

    if any(
        phrase in text
        for phrase in emergency_phrases
    ):
        return "EMERGENCY"

    # --------------------------------------------------------
    # Appointment reminders
    # --------------------------------------------------------

    reminder_phrases = [
        "remind me",
        "set a reminder",
        "appointment reminder",
        "reminder for my appointment",
        "remind me about my appointment",
    ]

    if any(
        phrase in text
        for phrase in reminder_phrases
    ):
        return "APPOINTMENT_REMINDER"

    # --------------------------------------------------------
    # Rescheduling
    # --------------------------------------------------------

    reschedule_phrases = [
        "reschedule",
        "change my appointment",
        "move my appointment",
        "change the appointment time",
        "change the appointment date",
    ]

    if any(
        phrase in text
        for phrase in reschedule_phrases
    ):
        return "RESCHEDULE_APPOINTMENT"

    # --------------------------------------------------------
    # Cancellation
    # --------------------------------------------------------

    cancel_phrases = [
        "cancel my appointment",
        "cancel the appointment",
        "cancel appointment",
        "i want to cancel",
        "please cancel",
    ]

    if any(
        phrase in text
        for phrase in cancel_phrases
    ):
        return "CANCEL_APPOINTMENT"

    # --------------------------------------------------------
    # Doctor availability
    # --------------------------------------------------------

    availability_phrases = [
        "is the doctor available",
        "is dr",
        "doctor available",
        "doctor availability",
        "available doctor",
        "which doctor is available",
        "who is available",
        "available tomorrow",
        "available today",
    ]

    if any(
        phrase in text
        for phrase in availability_phrases
    ):
        return "DOCTOR_AVAILABILITY"

    # --------------------------------------------------------
    # Booking
    # --------------------------------------------------------

    booking_phrases = [
        "book an appointment",
        "book appointment",
        "schedule an appointment",
        "schedule appointment",
        "make an appointment",
        "i want an appointment",
        "i need an appointment",
    ]

    if any(
        phrase in text
        for phrase in booking_phrases
    ):
        return "BOOK_APPOINTMENT"

    # --------------------------------------------------------
    # Hospital FAQ
    #
    # Important for RAG.
    # --------------------------------------------------------

    faq_phrases = [
        "what documents",
        "which documents",
        "documents should i bring",
        "documents do i need",
        "what should i bring",
        "what do i need to bring",
        "what should i carry",
        "what do i need",
        "hospital timings",
        "hospital hours",
        "opening hours",
        "working hours",
        "visiting hours",
        "where is the hospital",
        "hospital address",
        "appointment policy",
        "cancellation policy",
        "rescheduling policy",
        "insurance",
        "payment methods",
        "payment options",
        "consultation fee",
        "what is the fee",
        "how much does it cost",
        "patient guidelines",
        "hospital guidelines",
        "department information",
        "departments available",
    ]

    if any(
        phrase in text
        for phrase in faq_phrases
    ):
        return "HOSPITAL_FAQ"

    # --------------------------------------------------------
    # Appointment checking
    # --------------------------------------------------------

    check_phrases = [
        "check my appointment",
        "check appointment",
        "my appointment details",
        "appointment details",
        "when is my appointment",
        "what time is my appointment",
        "show my appointment",
        "show appointments",
    ]

    if any(
        phrase in text
        for phrase in check_phrases
    ):
        return "CHECK_APPOINTMENT"

    # --------------------------------------------------------
    # Medical query
    # --------------------------------------------------------

    medical_phrases = [
        "what medicine",
        "which medicine",
        "what medication",
        "which medication",
        "symptoms",
        "what disease",
        "medical advice",
        "medical question",
    ]

    if any(
        phrase in text
        for phrase in medical_phrases
    ):
        return "MEDICAL_QUERY"

    # --------------------------------------------------------
    # General query
    # --------------------------------------------------------

    return "GENERAL_QUERY"


# ============================================================
# JSON extraction
# ============================================================

def _extract_json(text):
    """
    Extract a JSON object from model output.

    Always returns a dictionary when successful.
    """

    if text is None:
        raise ValueError(
            "SLM returned empty output."
        )

    text = str(text).strip()

    if not text:
        raise ValueError(
            "SLM returned empty output."
        )

    # --------------------------------------------------------
    # Complete JSON
    # --------------------------------------------------------

    try:

        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed

        # Sometimes a model returns a JSON string containing
        # another JSON object.
        if isinstance(parsed, str):

            nested = parsed.strip()

            try:

                nested_parsed = json.loads(
                    nested
                )

                if isinstance(
                    nested_parsed,
                    dict,
                ):
                    return nested_parsed

            except json.JSONDecodeError:
                pass

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # JSON object surrounded by text
    # --------------------------------------------------------

    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL,
    )

    if match:

        json_text = match.group(0)

        try:

            parsed = json.loads(
                json_text
            )

            if isinstance(
                parsed,
                dict,
            ):
                return parsed

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "SLM did not return a valid JSON object."
    )


# ============================================================
# Clean value
# ============================================================

def _clean_value(value):
    """
    Convert empty strings to None.
    """

    if value is None:
        return None

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return None

    return value


# ============================================================
# Validate result
# ============================================================

def _validate_result(result, message):
    """
    Validate and normalize SLM output.
    """

    if not isinstance(
        result,
        dict,
    ):
        result = _default_result()

    fields = [
        "intent",
        "department",
        "date",
        "time",
        "new_date",
        "new_time",
        "doctor",
        "reason",
    ]

    for field in fields:

        if field not in result:
            result[field] = None

        result[field] = _clean_value(
            result[field]
        )

    # --------------------------------------------------------
    # Intent validation
    # --------------------------------------------------------

    if result["intent"] not in ALLOWED_INTENTS:
        result["intent"] = "GENERAL_QUERY"

    user_text = message.lower()

    # --------------------------------------------------------
    # Prevent doctor hallucination
    # --------------------------------------------------------

    doctor = result.get("doctor")

    if doctor:

        if str(
            doctor
        ).lower() not in user_text:

            result["doctor"] = None

    # --------------------------------------------------------
    # Prevent department hallucination
    # --------------------------------------------------------

    department = result.get(
        "department"
    )

    if department:

        if str(
            department
        ).lower() not in user_text:

            result["department"] = None

    # --------------------------------------------------------
    # Never allow model-generated reasons
    # --------------------------------------------------------

    result["reason"] = None

    # --------------------------------------------------------
    # new_date/new_time only apply to rescheduling
    # --------------------------------------------------------

    if (
        result["intent"]
        != "RESCHEDULE_APPOINTMENT"
    ):
        result["new_date"] = None
        result["new_time"] = None

    return result


# ============================================================
# Extract time
# ============================================================

def _extract_time(text):
    """
    Extract a time while preserving the user's wording.

    Examples:
        4 PM
        4:30 PM
        10 AM
        15:00
    """

    pattern = (
        r"\b(?:"
        r"[0-9]{1,2}"
        r"(?::[0-9]{2})?"
        r"\s*(?:AM|PM)"
        r"|"
        r"[0-9]{1,2}:[0-9]{2}"
        r")\b"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(0).strip()


# ============================================================
# Extract date phrase
# ============================================================

def _extract_date_phrase(text):
    """
    Extract common human-readable date phrases.

    The value is returned exactly as written.
    """

    patterns = [

        r"\b(?:today|tomorrow|yesterday)\b",

        r"\b(?:this|next)\s+"
        r"(?:monday|tuesday|wednesday|thursday|friday|"
        r"saturday|sunday)\b",

        r"\b(?:monday|tuesday|wednesday|thursday|friday|"
        r"saturday|sunday)\b",

        r"\b(?:"
        r"jan(?:uary)?|"
        r"feb(?:ruary)?|"
        r"mar(?:ch)?|"
        r"apr(?:il)?|"
        r"may|"
        r"jun(?:e)?|"
        r"jul(?:y)?|"
        r"aug(?:ust)?|"
        r"sep(?:tember)?|"
        r"oct(?:ober)?|"
        r"nov(?:ember)?|"
        r"dec(?:ember)?"
        r")\s+\d{1,2}(?:,\s*\d{4})?\b",

        r"\b\d{4}-\d{2}-\d{2}\b",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            return match.group(0).strip()

    return None


# ============================================================
# Extract doctor name
# ============================================================

def _extract_doctor_name(text):
    """
    Extract a doctor name from phrases such as:

        Dr. Rahul Verma
        Doctor Rahul Verma
    """

    patterns = [

        r"\bdr\.?\s+"
        r"([A-Z][a-z]+"
        r"(?:\s+[A-Z][a-z]+){1,2})",

        r"\bdoctor\s+"
        r"([A-Z][a-z]+"
        r"(?:\s+[A-Z][a-z]+){1,2})",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
        )

        if match:
            return match.group(1).strip()

    return None


# ============================================================
# Reminder guardrail
# ============================================================

def _force_reminder_intent(
    message,
    result,
):
    """
    Force reminder intent when explicit reminder language
    is present.
    """

    if not isinstance(
        result,
        dict,
    ):
        result = _default_result()

    text = message.lower()

    reminder_phrases = [
        "remind me",
        "set a reminder",
        "appointment reminder",
        "reminder for my appointment",
        "remind me about my appointment",
    ]

    if any(
        phrase in text
        for phrase in reminder_phrases
    ):
        result["intent"] = (
            "APPOINTMENT_REMINDER"
        )

    return result


# ============================================================
# Preserve date phrase
# ============================================================

def _preserve_date_phrase(
    message,
    result,
):
    """
    Never allow the small model to invent a calendar year.
    """

    if not isinstance(
        result,
        dict,
    ):
        result = _default_result()

    extracted_date = _extract_date_phrase(
        message
    )

    if extracted_date:
        result["date"] = extracted_date

    return result


# ============================================================
# Reschedule field extraction
# ============================================================

def _extract_reschedule_fields(
    message,
    result,
):
    """
    Deterministically extract OLD and NEW appointment
    date/time values.
    """

    if not isinstance(
        result,
        dict,
    ):
        result = _default_result()

    text = message.strip()

    # --------------------------------------------------------
    # OLD date/time -> NEW date/time
    # --------------------------------------------------------

    split_match = re.search(
        r"\bto\b",
        text,
        re.IGNORECASE,
    )

    if split_match:

        before = text[
            :split_match.start()
        ]

        after = text[
            split_match.end():
        ]

        old_date = _extract_date_phrase(
            before
        )

        old_time = _extract_time(
            before
        )

        new_date = _extract_date_phrase(
            after
        )

        new_time = _extract_time(
            after
        )

        if old_date:
            result["date"] = old_date

        if old_time:
            result["time"] = old_time

        if new_date:
            result["new_date"] = new_date

        if new_time:
            result["new_time"] = new_time

    else:

        # ----------------------------------------------------
        # Example:
        #
        # Reschedule my appointment to Friday
        # at 3 PM.
        # ----------------------------------------------------

        new_date = _extract_date_phrase(
            text
        )

        new_time = _extract_time(
            text
        )

        if new_date:
            result["new_date"] = new_date

        if new_time:
            result["new_time"] = new_time

        result["date"] = None
        result["time"] = None

    return result


# ============================================================
# Generate structured SLM output
# ============================================================

def generate_structured_output(message):
    """
    Generate structured intent/entity information
    using CareFlow-SLM.

    If the SLM produces malformed output, a deterministic
    domain fallback is used so the application continues
    working.
    """

    # --------------------------------------------------------
    # Load SLM
    # --------------------------------------------------------

    tokenizer, model = load_model()

    # --------------------------------------------------------
    # Build prompt
    # --------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": message,
        },
    ]

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    # --------------------------------------------------------
    # Tokenize
    # --------------------------------------------------------

    inputs = tokenizer(
        text,
        return_tensors="pt",
    )

    # --------------------------------------------------------
    # Generate
    # --------------------------------------------------------

    outputs = model.generate(
        **inputs,
        max_new_tokens=180,
        do_sample=False,
    )

    # --------------------------------------------------------
    # Extract generated tokens
    # --------------------------------------------------------

    generated_tokens = outputs[0][
        inputs["input_ids"].shape[1]:
    ]

    # --------------------------------------------------------
    # Decode
    # --------------------------------------------------------

    response_text = tokenizer.decode(
        generated_tokens,
        skip_special_tokens=True,
    )

    # --------------------------------------------------------
    # Parse model output
    # --------------------------------------------------------

    slm_parse_failed = False

    try:

        result = _extract_json(
            response_text
        )

    except Exception as exc:

        print(
            f"SLM JSON parsing failed: {exc}"
        )

        result = _default_result()

        slm_parse_failed = True

    # --------------------------------------------------------
    # If SLM failed, use deterministic domain fallback
    # --------------------------------------------------------

    if slm_parse_failed:

        fallback_intent = _fallback_intent(
            message
        )

        result["intent"] = fallback_intent

    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    result = _validate_result(
        result,
        message,
    )

    # --------------------------------------------------------
    # Reminder guardrail
    # --------------------------------------------------------

    result = _force_reminder_intent(
        message,
        result,
    )

    # --------------------------------------------------------
    # Preserve date
    # --------------------------------------------------------

    result = _preserve_date_phrase(
        message,
        result,
    )

    # --------------------------------------------------------
    # Extract doctor
    # --------------------------------------------------------

    doctor_name = _extract_doctor_name(
        message
    )

    if doctor_name:
        result["doctor"] = doctor_name

    # --------------------------------------------------------
    # Extract time
    # --------------------------------------------------------

    user_time = _extract_time(
        message
    )

    if user_time:
        result["time"] = user_time

    # --------------------------------------------------------
    # Reschedule
    # --------------------------------------------------------

    if (
        result["intent"]
        == "RESCHEDULE_APPOINTMENT"
    ):

        result = _extract_reschedule_fields(
            message,
            result,
        )

    return result


# ============================================================
# Direct testing
# ============================================================

if __name__ == "__main__":

    test_messages = [

        "I want to book an appointment with a cardiologist tomorrow.",

        "Cancel my appointment.",

        "Can I reschedule my appointment to Friday at 3 PM?",

        "Reschedule my appointment tomorrow at 4 PM to October 8 at 10 AM.",

        "Reschedule my appointment tomorrow at 3 PM to Friday at 10 AM.",

        "Remind me about my appointment tomorrow at 10 AM.",

        "What documents should I bring?",

        "What are the hospital timings?",

    ]

    for message in test_messages:

        print("\n========================================")

        print("Patient:")

        print(message)

        print("========================================")

        try:

            result = generate_structured_output(
                message
            )

            print("\nSLM:")

            print(
                json.dumps(
                    result,
                    indent=2,
                )
            )

        except Exception as exc:

            print("\nSLM ERROR:")

            print(exc)