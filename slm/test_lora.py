import json

import torch

from slm.model import load_model


TEST_MESSAGES = [
    "I want to book an appointment with a cardiologist tomorrow at 3 PM.",
    "Please cancel my appointment tomorrow at 9 AM.",
    "Can I reschedule my appointment to October 8 at 10 AM?",
    "Is Dr. Priya Rao available tomorrow?",
    "Remind me about my appointment tomorrow at 10 AM.",
    "What documents should I bring to my appointment?",
    "What are the hospital appointment timings?",
    "I have severe chest pain and difficulty breathing.",
    "I want to check my upcoming appointment.",
    "I need to speak with a human representative.",
]


SYSTEM_PROMPT = """
You are CareFlow-SLM, a healthcare appointment and patient
communication assistant.

Your task is to classify the patient's request and extract
relevant entities.

Return ONLY valid JSON.

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

JSON format:

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
"""


def generate_response(tokenizer, model, message):
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

    device = next(model.parameters()).device

    inputs = {
        key: value.to(device)
        for key, value in inputs.items()
    }

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=150,
            do_sample=False,
            temperature=None,
            top_p=None,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated_tokens = outputs[0][inputs["input_ids"].shape[1]:]

    response = tokenizer.decode(
        generated_tokens,
        skip_special_tokens=True,
    )

    return response.strip()


def main():
    print("=" * 70)
    print("CAREFLOW-SLM LoRA EVALUATION")
    print("=" * 70)

    tokenizer, model = load_model()

    correct = 0

    for index, message in enumerate(TEST_MESSAGES, start=1):

        print()
        print("-" * 70)
        print(f"TEST {index}")
        print(f"INPUT: {message}")
        print("-" * 70)

        response = generate_response(
            tokenizer,
            model,
            message,
        )

        print("MODEL OUTPUT:")
        print(response)

        try:
            parsed = json.loads(response)

            intent = parsed.get("intent")

            print(f"EXTRACTED INTENT: {intent}")

        except Exception:
            print("WARNING: Model did not return valid JSON.")

    print()
    print("=" * 70)
    print("EVALUATION COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()