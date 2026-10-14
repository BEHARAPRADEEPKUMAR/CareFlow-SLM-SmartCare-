import re


EMERGENCY_PATTERNS = [
    r"\bheart attack\b",
    r"\bchest pain\b",
    r"\bcan't breathe\b",
    r"\bcannot breathe\b",
    r"\bdifficulty breathing\b",
    r"\bsevere bleeding\b",
    r"\bunconscious\b",
    r"\bstroke\b",
    r"\boverdose\b",
    r"\bsuicid(e|al)\b",
]


def check_safety(message):
    """
    Safety layer for CareFlow-SLM.

    Returns a structured decision that can be consumed
    by the chatbot workflow.
    """

    text = message.lower().strip()

    for pattern in EMERGENCY_PATTERNS:
        if re.search(pattern, text):
            return {
                "safe": False,
                "risk_level": "HIGH",
                "category": "EMERGENCY",
                "action": "EMERGENCY_REDIRECT",
                "message": (
                    "This may be a medical emergency. "
                    "Please contact your local emergency service "
                    "or go to the nearest emergency department "
                    "immediately. CareFlow cannot provide emergency "
                    "medical treatment."
                ),
            }

    return {
        "safe": True,
        "risk_level": "LOW",
        "category": "NORMAL",
        "action": "CONTINUE",
        "message": "",
    }