from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from doctors.models import Department, Doctor, DoctorAvailability

class Command(BaseCommand):
    def handle(self,*args,**kwargs):
        data = {
            "Cardiology":[("Arjun Mehta","MD, Cardiology",12,900),("Priya Rao","MD, DM Cardiology",9,800)],
            "Dermatology":[("Ananya Sharma","MD, Dermatology",8,700)],
            "Neurology":[("Vikram Singh","MD, Neurology",14,1000)],
            "Orthopedics":[("Rahul Verma","MS, Orthopedics",11,850)],
        }
        for dept_name, docs in data.items():
            dept,_=Department.objects.get_or_create(name=dept_name)
            for name,qual,exp,fee in docs:
                doctor,_=Doctor.objects.get_or_create(name=name,department=dept,defaults={"qualification":qual,"experience_years":exp,"consultation_fee":fee})
                for weekday in range(6):
                    DoctorAvailability.objects.get_or_create(doctor=doctor,weekday=weekday,defaults={"start_time":"09:00","end_time":"17:00","slot_minutes":30})
        User.objects.get_or_create(username="demo_patient",defaults={"first_name":"Demo","last_name":"Patient"})
        self.stdout.write(self.style.SUCCESS("Synthetic demo data created."))
