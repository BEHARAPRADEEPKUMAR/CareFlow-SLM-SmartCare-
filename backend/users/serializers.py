from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

from .models import PatientProfile, DoctorAccount


User = get_user_model()


class PatientRegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(
        max_length=150
    )

    phone = serializers.CharField(
        max_length=20
    )

    blood_group = serializers.ChoiceField(
        choices=[
            ("A+", "A+"),
            ("A-", "A-"),
            ("B+", "B+"),
            ("B-", "B-"),
            ("AB+", "AB+"),
            ("AB-", "AB-"),
            ("O+", "O+"),
            ("O-", "O-"),
            ("Unknown", "Unknown"),
        ],
        required=True,
    )

    email = serializers.EmailField()

    password = serializers.CharField(
        write_only=True,
        min_length=6
    )

    confirm_password = serializers.CharField(
        write_only=True,
        min_length=6
    )

    def validate_email(self, value):
        value = value.lower().strip()

        if User.objects.filter(
            username=value
        ).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        if User.objects.filter(
            email=value
        ).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        return value

    def validate(self, data):
        if (
            data["password"]
            != data["confirm_password"]
        ):
            raise serializers.ValidationError({
                "confirm_password":
                    "Passwords do not match."
            })

        return data

    def create(self, validated_data):
        validated_data.pop(
            "confirm_password"
        )

        full_name = (
            validated_data["full_name"]
            .strip()
        )

        phone = (
            validated_data["phone"]
            .strip()
        )

        blood_group = validated_data["blood_group"]

        email = (
            validated_data["email"]
            .lower()
            .strip()
        )

        password = validated_data["password"]

        # ---------------------------------------------
        # CREATE DJANGO USER
        # ---------------------------------------------
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=full_name,
        )

        # ---------------------------------------------
        # CREATE PATIENT PROFILE
        # ---------------------------------------------
        PatientProfile.objects.create(
            user=user,
            full_name=full_name,
            phone=phone,
            blood_group=blood_group,
        )

        return user


class PatientLoginSerializer(serializers.Serializer):

    email = serializers.EmailField()

    password = serializers.CharField(
        write_only=True
    )

    def validate(self, data):

        email = (
            data["email"]
            .lower()
            .strip()
        )

        password = data["password"]

        user = authenticate(
            username=email,
            password=password
        )

        if user is None:
            raise serializers.ValidationError(
                "Invalid email or password."
            )

        if not user.is_active:
            raise serializers.ValidationError(
                "This account is inactive."
            )

        patient_profile = (
            PatientProfile.objects
            .filter(user=user)
            .first()
        )

        if not patient_profile:
            raise serializers.ValidationError(
                "This account is not registered as a patient."
            )

        data["user"] = user
        data["profile"] = patient_profile

        return data


class DoctorLoginSerializer(serializers.Serializer):

    email = serializers.EmailField()

    password = serializers.CharField(
        write_only=True
    )

    def validate(self, data):

        email = (
            data["email"]
            .lower()
            .strip()
        )

        password = data["password"]

        user = authenticate(
            username=email,
            password=password
        )

        if user is None:
            raise serializers.ValidationError(
                "Invalid doctor email or password."
            )

        if not user.is_active:
            raise serializers.ValidationError(
                "This account is inactive."
            )

        doctor_account = (
            DoctorAccount.objects
            .select_related("doctor")
            .filter(user=user)
            .first()
        )

        if not doctor_account:
            raise serializers.ValidationError(
                "This account is not registered as a doctor."
            )

        data["user"] = user
        data["doctor_account"] = doctor_account
        data["doctor"] = doctor_account.doctor

        return data