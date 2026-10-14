
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from rest_framework.routers import DefaultRouter

from doctors.views import DoctorViewSet, DepartmentViewSet
from doctors.doctor_api import DoctorAppointmentsView
from appointments.views import AppointmentViewSet
from chatbot.views import ChatView
from safety.views import SafetyCheckView


router = DefaultRouter()

router.register(
    "doctors",
    DoctorViewSet,
    basename="doctor",
)

router.register(
    "departments",
    DepartmentViewSet,
    basename="department",
)

router.register(
    "appointments",
    AppointmentViewSet,
    basename="appointment",
)


def health(request):
    return JsonResponse({
        "status": "ok",
        "service": "CareFlow-SLM",
    })


urlpatterns = [
    path("admin/", admin.site.urls),

    path("api/auth/", include("users.urls")),

    # Hospital RAG API
    path("api/rag/", include("rag_api.urls")),

    # Appointment reminders API
    path("api/reminders/", include("reminders.urls")),

    # Doctor-specific endpoints
    path("api/doctors/", include("doctors.urls")),

    # General REST API endpoints
    path("api/", include(router.urls)),

    # Chatbot and safety
    path("api/chat/", ChatView.as_view()),
    path("api/safety/check/", SafetyCheckView.as_view()),

    # Health check
    path("api/health/", health),

    # Doctor appointments
    path(
        "api/doctor/appointments/",
        DoctorAppointmentsView.as_view(),
    ),
]
