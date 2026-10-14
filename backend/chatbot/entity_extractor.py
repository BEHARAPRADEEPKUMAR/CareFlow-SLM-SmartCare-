import re
from datetime import datetime, timedelta


DEPARTMENT_ALIASES = {
    "cardiology": "Cardiology",
    "cardiologist": "Cardiology",
    "heart doctor": "Cardiology",

    "dermatology": "Dermatology",
    "dermatologist": "Dermatology",
    "skin doctor": "Dermatology",

    "orthopedics": "Orthopedics",
    "orthopedic": "Orthopedics",
    "orthopaedic": "Orthopedics",
    "bone doctor": "Orthopedics",

    "general medicine": "General Medicine",
    "general physician": "General Medicine",
    "physician": "General Medicine",
    "general doctor": "General Medicine",
}


def extract_department(text):
    text_lower = text.lower()

    for alias, department in DEPARTMENT_ALIASES.items():
        if alias in text_lower:
            return department

    return None


def extract_time(text):
    """
    Extract times such as:

    3 PM
    3:30 PM
    15:00
    10 am
    10:30 am
    """

    pattern = re.compile(
        r"\b("
        r"(?:1[0-2]|0?[1-9])"
        r"(?::[0-5][0-9])?"
        r"\s*(?:am|pm)"
        r"|"
        r"(?:[01]?[0-9]|2[0-3])"
        r":[0-5][0-9]"
        r")\b",
        re.IGNORECASE,
    )

    match = pattern.search(text)

    if not match:
        return None

    value = match.group(1).strip().lower()

    try:
        if "am" in value or "pm" in value:
            parsed = datetime.strptime(
                value.replace(" ", ""),
                "%I:%M%p" if ":" in value else "%I%p",
            )
        else:
            parsed = datetime.strptime(value, "%H:%M")

        return parsed.strftime("%H:%M")

    except ValueError:
        return None


def extract_date(text):
    """
    Supports:

    today
    tomorrow
    day after tomorrow
    Monday / Tuesday / ...
    YYYY-MM-DD
    """

    text_lower = text.lower()
    today = datetime.now().date()

    if "day after tomorrow" in text_lower:
        return (today + timedelta(days=2)).isoformat()

    if "tomorrow" in text_lower:
        return (today + timedelta(days=1)).isoformat()

    if "today" in text_lower:
        return today.isoformat()

    # Explicit YYYY-MM-DD
    match = re.search(
        r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b",
        text,
    )

    if match:
        try:
            date_value = datetime.strptime(
                match.group(0),
                "%Y-%m-%d",
            ).date()

            return date_value.isoformat()

        except ValueError:
            pass

    # Weekday
    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    for day_name, target_day in weekdays.items():

        if re.search(
            rf"\b{day_name}\b",
            text_lower,
        ):
            days_ahead = (
                target_day - today.weekday()
            ) % 7

            if days_ahead == 0:
                days_ahead = 7

            return (
                today + timedelta(days=days_ahead)
            ).isoformat()

    return None


def extract_doctor_name(text):
    """
    Extract doctor names from natural language.

    Examples:
        Dr. Priya Rao
        Doctor Priya Rao
        Is Dr. Priya Rao available?
        Can Doctor Ananya Sharma see me tomorrow?
        I want to consult Dr. Vikram Singh.
    """

    pattern = re.compile(
        r"\b(?:dr\.?|doctor)\s+"
        r"([A-Za-z]+(?:\s+[A-Za-z]+){0,2}?)"
        r"(?=\s+(?:available|see|meet|consult|visit|"
        r"is|at|on|tomorrow|today|this|next|for|in|please|"
        r"can|could|would)\b|[?.!,]|$)",
        re.IGNORECASE,
    )

    match = pattern.search(text)

    if not match:
        return None

    return match.group(1).strip()


def extract_entities(text):
    """
    Extract healthcare appointment entities.
    """

    return {
        "department": extract_department(text),
        "doctor_name": extract_doctor_name(text),
        "date": extract_date(text),
        "time": extract_time(text),
    }