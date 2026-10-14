from django.contrib.auth import get_user_model
from doctors.models import Doctor
from users.models import DoctorAccount

User = get_user_model()

doctor_credentials = {
    "Arjun Mehta": "arjun.mehta@careflow.com",
    "Priya Rao": "priya.rao@careflow.com",
    "Ananya Sharma": "ananya.sharma@careflow.com",
    "Vikram Singh": "vikram.singh@careflow.com",
    "Rahul Verma": "rahul.verma@careflow.com",
}

for doctor in Doctor.objects.all():
    email = doctor_credentials.get(doctor.name)

    if not email:
        continue

    user, created = User.objects.get_or_create(
        username=email,
        defaults={
            "email": email,
            "first_name": doctor.name,
        },
    )

    user.email = email
    user.first_name = doctor.name
    user.set_password("Doctor@123")
    user.save()

    doctor.email = email
    doctor.user = user
    doctor.save(update_fields=["email", "user"])

    DoctorAccount.objects.get_or_create(
        user=user,
        doctor=doctor,
    )

    print(
        f"Created/linked: Dr. {doctor.name} | "
        f"{email} | Password: Doctor@123"
    )

print("\nVerification:")

for doctor in Doctor.objects.all():
    print(
        doctor.id,
        "|",
        doctor.name,
        "|",
        doctor.email,
        "| user:",
        doctor.user.email if doctor.user else None,
    )