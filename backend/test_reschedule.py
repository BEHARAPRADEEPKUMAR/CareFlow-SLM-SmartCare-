
from users.models import PatientProfile
from chatbot.services import run_chat, _clear_reschedule_context

profiles = list(
    PatientProfile.objects.select_related("user").all()
)

print("\n=== Available patient accounts ===")
for i, profile in enumerate(profiles, start=1):
    print(f"{i}. {profile.user.username} (user_id={profile.user_id})")

if not profiles:
    print("No patient profiles found.")
else:
    choice = input("\nEnter patient number: ").strip()
    user = profiles[int(choice) - 1].user

    messages = [
        "Reschedule my next appointment with Dr. Vikram Singh to another available slot",
        "reshedule Dr. Arjun Mehta appointment",
    ]

    for message in messages:
        print("\n" + "=" * 60)
        print("USER:", message)

        try:
            _clear_reschedule_context(user)
            result = run_chat(message, user=user)

            print("\nBOT RESPONSE:")
            print(result.get("response", result))
            print("\nINTENT:", result.get("intent"))
            print("ACTION:", result.get("action"))
            print("AVAILABLE SLOTS:", result.get("available_slots", []))

        except Exception as exc:
            print("ERROR:", type(exc).__name__, str(exc))

        finally:
            _clear_reschedule_context(user)