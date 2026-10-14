import json
import random
from pathlib import Path


OUTPUT_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "train.jsonl"


SYSTEM_PROMPT = """You are CareFlow-SLM, a healthcare appointment and patient communication assistant.

Your task is to understand the patient's message and return ONLY valid JSON.

Allowed intents:
BOOK_APPOINTMENT
RESCHEDULE_APPOINTMENT
CANCEL_APPOINTMENT
CHECK_APPOINTMENT
DOCTOR_AVAILABILITY
HOSPITAL_FAQ
APPOINTMENT_REMINDER
GENERAL_QUERY
MEDICAL_QUERY
EMERGENCY
HUMAN_HANDOFF

Return these fields:

{
  "intent": "...",
  "department": null,
  "date": null,
  "time": null,
  "new_date": null,
  "new_time": null,
  "doctor": null,
  "reason": null
}

Do not provide diagnosis, prescriptions, or treatment recommendations.
"""


def example(message, intent, department=None, date=None, time=None,
            new_date=None, new_time=None, doctor=None, reason=None):

    output = {
        "intent": intent,
        "department": department,
        "date": date,
        "time": time,
        "new_date": new_date,
        "new_time": new_time,
        "doctor": doctor,
        "reason": reason,
    }

    return {
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": message,
            },
            {
                "role": "assistant",
                "content": json.dumps(output, ensure_ascii=False),
            },
        ]
    }


def build_dataset():
    examples = []

    # ---------------------------------------------------------
    # BOOK APPOINTMENT
    # ---------------------------------------------------------

    booking_examples = [
        (
            "I want to book an appointment with cardiology tomorrow at 3 PM.",
            "Cardiology",
            "tomorrow",
            "3 PM",
        ),
        (
            "Book me a dermatologist appointment tomorrow afternoon.",
            "Dermatology",
            "tomorrow",
            None,
        ),
        (
            "I need to see a cardiologist tomorrow at 10 AM.",
            "Cardiology",
            "tomorrow",
            "10 AM",
        ),
        (
            "Can you schedule an appointment with dermatology at 2 PM tomorrow?",
            "Dermatology",
            "tomorrow",
            "2 PM",
        ),
        (
            "I need an orthopedic appointment tomorrow at 11 AM.",
            "Orthopedics",
            "tomorrow",
            "11 AM",
        ),
        (
            "Please book a general medicine appointment tomorrow at 4 PM.",
            "General Medicine",
            "tomorrow",
            "4 PM",
        ),
        (
            "I want to schedule a pediatrics appointment tomorrow.",
            "Pediatrics",
            "tomorrow",
            None,
        ),
        (
            "Can I book an ENT appointment tomorrow at 1 PM?",
            "ENT",
            "tomorrow",
            "1 PM",
        ),
        (
            "Schedule cardiology for October 8 at 10 AM.",
            "Cardiology",
            "October 8",
            "10 AM",
        ),
        (
            "Book dermatology for October 9 at 3 PM.",
            "Dermatology",
            "October 9",
            "3 PM",
        ),
        (
            "I need an appointment with orthopedics at 9 AM tomorrow.",
            "Orthopedics",
            "tomorrow",
            "9 AM",
        ),
        (
            "Please schedule general medicine tomorrow afternoon.",
            "General Medicine",
            "tomorrow",
            None,
        ),
    ]

    for message, department, date, time in booking_examples:
        examples.append(
            example(
                message,
                "BOOK_APPOINTMENT",
                department=department,
                date=date,
                time=time,
            )
        )

    # ---------------------------------------------------------
    # RESCHEDULE
    # ---------------------------------------------------------

    reschedule_examples = [
        (
            "Reschedule my cardiology appointment tomorrow at 3 PM to October 8 at 10 AM.",
            "Cardiology",
            "tomorrow",
            "3 PM",
            "October 8",
            "10 AM",
        ),
        (
            "Move my dermatology appointment tomorrow at 2 PM to October 9 at 4 PM.",
            "Dermatology",
            "tomorrow",
            "2 PM",
            "October 9",
            "4 PM",
        ),
        (
            "Can you change my orthopedic appointment from tomorrow at 11 AM to October 10 at 3 PM?",
            "Orthopedics",
            "tomorrow",
            "11 AM",
            "October 10",
            "3 PM",
        ),
        (
            "Please reschedule my cardiology visit tomorrow at 9 AM to Friday at 2 PM.",
            "Cardiology",
            "tomorrow",
            "9 AM",
            "Friday",
            "2 PM",
        ),
        (
            "Move my appointment tomorrow at 10 AM to October 8 at 11 AM.",
            None,
            "tomorrow",
            "10 AM",
            "October 8",
            "11 AM",
        ),
        (
            "I want to change my appointment from tomorrow at 3 PM to Friday at 10 AM.",
            None,
            "tomorrow",
            "3 PM",
            "Friday",
            "10 AM",
        ),
    ]

    for (
        message,
        department,
        date,
        time,
        new_date,
        new_time,
    ) in reschedule_examples:
        examples.append(
            example(
                message,
                "RESCHEDULE_APPOINTMENT",
                department=department,
                date=date,
                time=time,
                new_date=new_date,
                new_time=new_time,
            )
        )

    # ---------------------------------------------------------
    # CANCEL
    # ---------------------------------------------------------

    cancel_examples = [
        (
            "Cancel my cardiology appointment tomorrow at 9 AM.",
            "Cardiology",
            "tomorrow",
            "9 AM",
        ),
        (
            "Please cancel my dermatology appointment tomorrow at 3 PM.",
            "Dermatology",
            "tomorrow",
            "3 PM",
        ),
        (
            "I want to cancel my orthopedic appointment tomorrow at 11 AM.",
            "Orthopedics",
            "tomorrow",
            "11 AM",
        ),
        (
            "Cancel my appointment tomorrow at 10 AM.",
            None,
            "tomorrow",
            "10 AM",
        ),
        (
            "Please remove my cardiology booking tomorrow at 4 PM.",
            "Cardiology",
            "tomorrow",
            "4 PM",
        ),
        (
            "I cannot attend my appointment tomorrow at 2 PM. Cancel it.",
            None,
            "tomorrow",
            "2 PM",
        ),
    ]

    for message, department, date, time in cancel_examples:
        examples.append(
            example(
                message,
                "CANCEL_APPOINTMENT",
                department=department,
                date=date,
                time=time,
            )
        )

    # ---------------------------------------------------------
    # CHECK APPOINTMENT
    # ---------------------------------------------------------

    check_examples = [
        (
            "What time is my appointment tomorrow?",
            "tomorrow",
            None,
        ),
        (
            "Do I have an appointment tomorrow at 3 PM?",
            "tomorrow",
            "3 PM",
        ),
        (
            "Show me my upcoming appointment.",
            None,
            None,
        ),
        (
            "What is my next appointment?",
            None,
            None,
        ),
        (
            "Can you check my appointment for tomorrow?",
            "tomorrow",
            None,
        ),
        (
            "Tell me when my cardiology appointment is.",
            None,
            None,
        ),
    ]

    for message, date, time in check_examples:
        examples.append(
            example(
                message,
                "CHECK_APPOINTMENT",
                date=date,
                time=time,
            )
        )

    # ---------------------------------------------------------
    # DOCTOR AVAILABILITY
    # ---------------------------------------------------------

    availability_examples = [
        (
            "Is Dr. Arjun Mehta available tomorrow?",
            "tomorrow",
            None,
            "Arjun Mehta",
        ),
        (
            "Is Dr. Priya Rao available tomorrow at 10 AM?",
            "tomorrow",
            "10 AM",
            "Priya Rao",
        ),
        (
            "Does Dr. Rahul Verma have any slots tomorrow?",
            "tomorrow",
            None,
            "Rahul Verma",
        ),
        (
            "Can I see if Dr. Arjun Mehta is free at 3 PM tomorrow?",
            "tomorrow",
            "3 PM",
            "Arjun Mehta",
        ),
        (
            "Is there a cardiologist available tomorrow?",
            "tomorrow",
            None,
            None,
        ),
        (
            "Who is available in dermatology tomorrow?",
            "tomorrow",
            None,
            None,
        ),
    ]

    for message, date, time, doctor in availability_examples:
        examples.append(
            example(
                message,
                "DOCTOR_AVAILABILITY",
                date=date,
                time=time,
                doctor=doctor,
            )
        )

    # ---------------------------------------------------------
    # APPOINTMENT REMINDER
    # ---------------------------------------------------------

    reminder_examples = [
        (
            "Remind me about my appointment tomorrow at 10 AM.",
            "tomorrow",
            "10 AM",
        ),
        (
            "Please set a reminder for my appointment tomorrow.",
            "tomorrow",
            None,
        ),
        (
            "I need a reminder for my cardiology appointment tomorrow at 3 PM.",
            "tomorrow",
            "3 PM",
        ),
        (
            "Set an appointment reminder for tomorrow at 9 AM.",
            "tomorrow",
            "9 AM",
        ),
        (
            "Don't let me forget my appointment tomorrow.",
            "tomorrow",
            None,
        ),
    ]

    for message, date, time in reminder_examples:
        examples.append(
            example(
                message,
                "APPOINTMENT_REMINDER",
                date=date,
                time=time,
            )
        )

    # ---------------------------------------------------------
    # HOSPITAL FAQ
    # ---------------------------------------------------------

    faq_examples = [
        "What documents should I bring to my appointment?",
        "What documents are required for an appointment?",
        "Do I need to bring my ID?",
        "What should I carry when visiting the hospital?",
        "What are the hospital appointment rules?",
        "What departments are available?",
        "What services does cardiology provide?",
        "What does the dermatology department do?",
        "What are the patient guidelines?",
        "What should patients do before an appointment?",
        "Do I need previous medical records?",
        "What payment documents should I bring?",
    ]

    for message in faq_examples:
        examples.append(
            example(
                message,
                "HOSPITAL_FAQ",
            )
        )

    # ---------------------------------------------------------
    # GENERAL QUERY
    # ---------------------------------------------------------

    general_examples = [
        "Hello",
        "Hi",
        "Good morning",
        "How can you help me?",
        "What can you do?",
        "Tell me about CareFlow.",
        "I need help with an appointment.",
        "Can you help me?",
    ]

    for message in general_examples:
        examples.append(
            example(
                message,
                "GENERAL_QUERY",
            )
        )

    # ---------------------------------------------------------
    # MEDICAL QUERY
    # ---------------------------------------------------------

    medical_examples = [
        "What medicine should I take for a headache?",
        "Can you diagnose my stomach pain?",
        "What treatment should I take for my fever?",
        "Tell me which medicine is best for my symptoms.",
        "Can you prescribe something for my pain?",
        "What treatment do I need?",
    ]

    for message in medical_examples:
        examples.append(
            example(
                message,
                "MEDICAL_QUERY",
            )
        )

    # ---------------------------------------------------------
    # EMERGENCY
    # ---------------------------------------------------------

    emergency_examples = [
        "I need emergency medical help.",
        "I have severe chest pain.",
        "This is an emergency.",
        "I am having difficulty breathing.",
        "I need immediate medical assistance.",
        "I have severe bleeding and need help.",
        "Please help me with an emergency.",
    ]

    for message in emergency_examples:
        examples.append(
            example(
                message,
                "EMERGENCY",
            )
        )

    # ---------------------------------------------------------
    # HUMAN HANDOFF
    # ---------------------------------------------------------

    handoff_examples = [
        "I want to speak to a human.",
        "Connect me with a hospital staff member.",
        "Can I talk to a receptionist?",
        "I need to contact a human agent.",
        "Please transfer me to hospital staff.",
    ]

    for message in handoff_examples:
        examples.append(
            example(
                message,
                "HUMAN_HANDOFF",
            )
        )

    random.shuffle(examples)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        for item in examples:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Dataset created successfully.")
    print(f"Examples: {len(examples)}")
    print(f"File: {OUTPUT_FILE}")


if __name__ == "__main__":
    build_dataset()