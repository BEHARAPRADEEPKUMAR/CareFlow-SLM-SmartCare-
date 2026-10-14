from django.contrib import admin
from .models import Department, Doctor, DoctorAvailability
admin.site.register([Department, Doctor, DoctorAvailability])
