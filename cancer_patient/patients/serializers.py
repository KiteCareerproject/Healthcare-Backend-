from rest_framework import serializers
from .models import CancerType, PatientMedicalRecord, Treatment, Medication
from accounts.serializers import PatientProfileSerializer, DoctorProfileSerializer

class CancerTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CancerType
        fields = ['cancer_type_id', 'name', 'description', 'common_symptoms']
        read_only_fields = ['cancer_type_id']
    
    def validate_name(self, value):
        """Check if cancer type with this name already exists"""
        if CancerType.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Cancer type with this name already exists")
        return value
    
    def validate_common_symptoms(self, value):
        """Validate that common_symptoms is a list"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Common symptoms must be a list")
        return value

class TreatmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Treatment
        fields = '__all__'

class MedicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medication
        fields = '__all__'

class PatientMedicalRecordSerializer(serializers.ModelSerializer):
    patient = PatientProfileSerializer(read_only=True)
    cancer_type = CancerTypeSerializer(read_only=True)
    treating_doctor = DoctorProfileSerializer(read_only=True)
    treatments = TreatmentSerializer(many=True, read_only=True)
    medications = MedicationSerializer(many=True, read_only=True)
    
    class Meta:
        model = PatientMedicalRecord
        fields = '__all__'

class CreateMedicalRecordSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()
    cancer_type_id = serializers.IntegerField()
    cancer_stage = serializers.ChoiceField(choices=PatientMedicalRecord.CANCER_STAGES)
    diagnosis_date = serializers.DateField()
    hospital_name = serializers.CharField()
    treating_doctor_id = serializers.IntegerField()
    known_symptoms = serializers.CharField()
    allergies = serializers.CharField(required=False, allow_blank=True)

class CreateTreatmentSerializer(serializers.Serializer):
    treatment_type = serializers.ChoiceField(choices=Treatment.TREATMENT_TYPES)
    treatment_name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=Treatment.STATUS_CHOICES, default='PLANNED')
    notes = serializers.CharField(required=False, allow_blank=True)

class CreateMedicationSerializer(serializers.Serializer):
    medication_name = serializers.CharField()
    dosage = serializers.CharField()
    frequency = serializers.ChoiceField(choices=Medication.FREQUENCY_CHOICES)
    timing = serializers.JSONField(default=list)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)