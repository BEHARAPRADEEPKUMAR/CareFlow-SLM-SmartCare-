import json
from model import load_model


SYSTEM_PROMPT = """
You are CareFlow-SLM, a healthcare appointment and patient communication assistant.

Your task is to understand the patient's request and convert it into JSON.

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

Return ONLY valid JSON.

The JSON must contain exactly these fields:

{
  "intent": "...",
  "department": null,
  "date": null,
  "time": null,
  "doctor": null,
  "reason": null
}

Do not provide medical diagnosis or medication advice.
IMPORTANT ENTITY RULES:

1. Never invent or guess information.
2. Only extract a doctor name if the user explicitly mentions the doctor's name.
3. Only extract a department if the user explicitly mentions a department or medical specialty.
4. Only extract a date if the user explicitly provides a date or relative date such as today, tomorrow, Monday, or Friday.
5. Only extract a time if the user explicitly provides a time.
6. Only extract a reason if the user explicitly gives a reason for the appointment.
7. If information is not present in the user's message, return null.
8. Do not use example doctor names as real information.

Examples:

User:
I want to book an appointment with a cardiologist tomorrow.

Output:
{
  "intent": "BOOK_APPOINTMENT",
  "department": "Cardiology",
  "date": "tomorrow",
  "time": null,
  "doctor": null,
  "reason": null
}

User:
Can I reschedule my appointment to Friday at 3 PM?

Output:
{
  "intent": "RESCHEDULE_APPOINTMENT",
  "department": null,
  "date": "Friday",
  "time": "15:00",
  "doctor": null,
  "reason": null
}

User:
Cancel my appointment.

Output:
{
  "intent": "CANCEL_APPOINTMENT",
  "department": null,
  "date": null,
  "time": null,
  "doctor": null,
  "reason": null
}
"""


def generate_structured_output(message):
    tokenizer, model = load_model()

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

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
    )

    outputs = model.generate(
        **inputs,
        max_new_tokens=150,
        do_sample=False,
    )

    generated_tokens = outputs[0][inputs["input_ids"].shape[1]:]

    response = tokenizer.decode(
        generated_tokens,
        skip_special_tokens=True,
    ).strip()

    # Try to extract JSON from the model response
    try:
        start = response.find("{")
        end = response.rfind("}")

        if start != -1 and end != -1:
            json_text = response[start:end + 1]
            result = json.loads(json_text)

            # Prevent hallucinated doctor names.
            doctor = result.get("doctor")

            if doctor:
                user_text = message.lower()
                doctor_text = doctor.lower()

                # Keep the doctor only if the user's message
                # explicitly contains the doctor's name.
                if doctor_text not in user_text:
                    result["doctor"] = None

            return result

    except json.JSONDecodeError:
        pass

    return {
        "intent": "GENERAL_QUERY",
        "department": None,
        "date": None,
        "time": None,
        "doctor": None,
        "reason": None,
        "raw_response": response,
    }


if __name__ == "__main__":

    test_message = (
        "I want to book an appointment with a cardiologist tomorrow."
    )

    print("Patient:")
    print(test_message)

    print("\nSLM Structured Output:")

    result = generate_structured_output(test_message)

    print(json.dumps(result, indent=2))