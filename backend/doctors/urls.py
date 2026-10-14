
from django.urls import path

from .views import (
    DoctorAppointmentsView,
    DoctorAvailabilityDetailView,
    DoctorAvailabilityView,
)

urlpatterns = [
    path(
        "availability/",
        DoctorAvailabilityView.as_view(),
        name="doctor-availability",
    ),
    path(
        "availability/<int:pk>/",
        DoctorAvailabilityDetailView.as_view(),
        name="doctor-availability-detail",
    ),
    path(
        "appointments/",
        DoctorAppointmentsView.as_view(),
        name="doctor-appointments",
    ),
]