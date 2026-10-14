from rest_framework import serializers
from .models import Department, Doctor
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta: model = Department; fields = "__all__"
class DoctorSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    class Meta:
        model = Doctor
        fields = ["id","name","department","department_name","qualification","experience_years","consultation_fee","bio","is_active"]
