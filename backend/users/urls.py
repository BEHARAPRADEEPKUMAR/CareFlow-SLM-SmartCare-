from django.urls import path

from .views import (
    PatientRegisterView,
    PatientLoginView,
    DoctorLoginView,
)

urlpatterns = [
    path(
        "register/",
        PatientRegisterView.as_view(),
        name="patient-register",
    ),
    path(
        "login/patient/",
        PatientLoginView.as_view(),
        name="patient-login",
    ),
    path(
        "login/doctor/",
        DoctorLoginView.as_view(),
        name="doctor-login",
    ),
]