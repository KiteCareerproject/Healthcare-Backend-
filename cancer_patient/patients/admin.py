from django.contrib import admin
from .models import CancerType, PatientMedicalRecord, Treatment, Medication

@admin.register(CancerType)
class CancerTypeAdmin(admin.ModelAdmin):
    list_display = ('cancer_type_id', 'name', 'created_at')
    search_fields = ('name',)

class TreatmentInline(admin.TabularInline):
    model = Treatment
    extra = 0
    fields = ('treatment_id', 'treatment_type', 'treatment_name', 'start_date', 'status')

class MedicationInline(admin.TabularInline):
    model = Medication
    extra = 0
    fields = ('medication_id', 'medication_name', 'dosage', 'frequency', 'is_active')

@admin.register(PatientMedicalRecord)
class PatientMedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('medical_record_id', 'patient_name', 'cancer_type', 'cancer_stage', 'treating_doctor', 'diagnosis_date')
    list_filter = ('cancer_type', 'cancer_stage', 'diagnosis_date')
    search_fields = ('patient__first_name', 'patient__last_name', 'patient__aadhar_number')
    inlines = [TreatmentInline, MedicationInline]
    
    def patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name} (ID: {obj.patient.patient_id})"
    patient_name.short_description = 'Patient'

@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    list_display = ('treatment_id', 'medical_record', 'treatment_name', 'treatment_type', 'start_date', 'status')
    list_filter = ('treatment_type', 'status', 'start_date')
    search_fields = ('treatment_name', 'patient_medical_record__patient__first_name')
    
    def medical_record(self, obj):
        return f"MR-{obj.patient_medical_record.medical_record_id}"
    medical_record.short_description = 'Medical Record'

@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ('medication_id', 'medical_record', 'medication_name', 'dosage', 'frequency', 'is_active')
    list_filter = ('frequency', 'is_active')
    search_fields = ('medication_name', 'patient_medical_record__patient__first_name')
    
    def medical_record(self, obj):
        return f"MR-{obj.patient_medical_record.medical_record_id}"
    medical_record.short_description = 'Medical Record'