
import csv
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HOME_CARE_FILE = (
    BASE_DIR / "data" / "medical_symptoms" / "home_care.csv"
)


def normalize_text(text):
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def get_home_care(message):
    """
    Return matching home-care reference entries.
    These are general self-care suggestions, not diagnoses.
    """
    text = normalize_text(message)

    if not HOME_CARE_FILE.exists():
        return []

    matches = []

    with HOME_CARE_FILE.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            condition = row.get("condition_or_symptom", "")
            condition_text = normalize_text(condition)

            # Match a condition name or its individual keywords.
            keywords = {
                "common cold": ["cold", "runny nose", "sneezing"],
                "mild cough": ["cough"],
                "mild sore throat": ["sore throat", "throat pain"],
                "mild headache": ["headache"],
                "mild nausea": ["nausea", "feeling sick"],
                "mild diarrhea": ["diarrhea", "loose stools"],
                "mild constipation": ["constipation"],
                "mild skin irritation or itching": [
                    "itching", "itchy skin", "skin irritation"
                ],
                "mild muscle soreness": [
                    "muscle soreness", "muscle pain"
                ],
                "mild menstrual cramps": [
                    "menstrual cramps", "period cramps"
                ],
                "mild dehydration risk": [
                    "dehydration", "dry mouth"
                ],
                "mild seasonal allergy symptoms": [
                    "seasonal allergy", "watery eyes",
                    "itchy eyes", "allergy symptoms"
                ],
            }

            terms = keywords.get(condition_text, [condition])

            if any(
                normalize_text(term) in text
                for term in terms
                if normalize_text(term)
            ):
                matches.append(row)

    return matches


def format_home_care(matches):
    if not matches:
        return (
            "I couldn't find a suitable home-care entry in my "
            "reference file.\n\n"
            "I can help you find a healthcare professional instead."
        )

    def format_items(value):
        if not value:
            return "  • Not specified"

        items = [
            item.strip()
            for item in str(value).split(";")
            if item.strip()
        ]

        if not items:
            return "  • Not specified"

        return "\n".join(
            f"  • {item}" for item in items
        )

    lines = [
        "General home-care information",
        "These measures provide general comfort guidance. "
        "They do not diagnose or cure the cause.",
    ]

    for row in matches[:3]:
        topic = row.get(
            "condition_or_symptom", "General symptoms"
        )

        lines.extend([
            "",
            f"TOPIC: {topic}",
            "",
            "Suggestions:",
            format_items(
                row.get("home_care_suggestions", "")
            ),
            "",
            "What to avoid:",
            format_items(
                row.get("what_to_avoid", "")
            ),
            "",
            "When to seek medical care:",
            format_items(
                row.get("when_to_seek_medical_care", "")
            ),
            "",
            "Suggested specialty: "
            + str(
                row.get(
                    "doctor_specialty_to_consider",
                    "Primary care / General practitioner",
                )
            ),
        ])

    return "\n".join(lines)