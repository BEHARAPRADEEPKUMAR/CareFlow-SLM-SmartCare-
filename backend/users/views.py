from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    PatientRegisterSerializer,
    PatientLoginSerializer,
    DoctorLoginSerializer,
)


class PatientRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PatientRegisterSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.save()

        token, _ = Token.objects.get_or_create(
            user=user
        )

        profile = user.patient_profile

        return Response(
            {
                "success": True,
                "message": "Patient account created successfully.",
                "token": token.key,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": profile.full_name,
                    "phone": profile.phone,
                    "role": "patient",
                },
            },
            status=status.HTTP_201_CREATED,
        )


class PatientLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PatientLoginSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.validated_data["user"]
        profile = serializer.validated_data["profile"]

        token, _ = Token.objects.get_or_create(
            user=user
        )

        return Response(
            {
                "success": True,
                "message": (
                    f"Welcome to CareFlow, "
                    f"{profile.full_name}!"
                ),
                "token": token.key,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": profile.full_name,
                    "phone": profile.phone,
                    "role": "patient",
                },
            },
            status=status.HTTP_200_OK,
        )


class DoctorLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DoctorLoginSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.validated_data["user"]
        doctor = serializer.validated_data["doctor"]

        token, _ = Token.objects.get_or_create(
            user=user
        )

        return Response(
            {
                "success": True,
                "message": (
                    f"Welcome Dr. {doctor.name}!"
                ),
                "token": token.key,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": doctor.name,
                    "role": "doctor",
                    "doctor_id": doctor.id,
                    "department": (
                        doctor.department.name
                        if doctor.department
                        else ""
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )