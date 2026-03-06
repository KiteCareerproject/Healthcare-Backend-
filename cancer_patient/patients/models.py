from djongo import models
from accounts.models import PatientProfile, DoctorProfile

class CancerType(models.Model):
    cancer_type_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    common_symptoms = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'cancer_types'
    
    def __str__(self):
        return f"CancerType {self.cancer_type_id}: {self.name}"

class PatientMedicalRecord(models.Model):
    CANCER_STAGES = [
        ('STAGE_0', 'Stage 0'),
        ('STAGE_1', 'Stage I'),
        ('STAGE_2', 'Stage II'),
        ('STAGE_3', 'Stage III'),
        ('STAGE_4', 'Stage IV'),
    ]
    
    medical_record_id = models.AutoField(primary_key=True)
    patient = models.OneToOneField(PatientProfile, on_delete=models.CASCADE, related_name='medical_record')
    cancer_type = models.ForeignKey(CancerType, on_delete=models.PROTECT)
    cancer_stage = models.CharField(max_length=10, choices=CANCER_STAGES)
    diagnosis_date = models.DateField()
    hospital_name = models.CharField(max_length=300)
    treating_doctor = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, related_name='patients')
    known_symptoms = models.TextField()
    allergies = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'patient_medical_records'
    
    def __str__(self):
        return f"MedicalRecord {self.medical_record_id}: Patient {self.patient.patient_id}"

class Treatment(models.Model):
    TREATMENT_TYPES = [
        ('CHEMO', 'Chemotherapy'),
        ('RADIATION', 'Radiation Therapy'),
        ('SURGERY', 'Surgery'),
        ('IMMUNO', 'Immunotherapy'),
        ('HORMONE', 'Hormone Therapy'),
        ('TARGETED', 'Targeted Therapy'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed'),
        ('PAUSED', 'Paused'),
    ]
    
    treatment_id = models.AutoField(primary_key=True)
    patient_medical_record = models.ForeignKey(PatientMedicalRecord, on_delete=models.CASCADE, related_name='treatments')
    treatment_type = models.CharField(max_length=20, choices=TREATMENT_TYPES)
    treatment_name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'treatments'
    
    def __str__(self):
        return f"Treatment {self.treatment_id}: {self.treatment_name}"

class Medication(models.Model):
    FREQUENCY_CHOICES = [
        ('ONCE', 'Once daily'),
        ('TWICE', 'Twice daily'),
        ('THRICE', 'Thrice daily'),
        ('FOUR', 'Four times daily'),
        ('AS_NEEDED', 'As needed'),
    ]
    
    medication_id = models.AutoField(primary_key=True)
    patient_medical_record = models.ForeignKey(PatientMedicalRecord, on_delete=models.CASCADE, related_name='medications')
    medication_name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    timing = models.JSONField(default=list)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    prescribed_by = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'medications'
    
    def __str__(self):
        return f"Medication {self.medication_id}: {self.medication_name}"