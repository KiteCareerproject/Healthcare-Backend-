from djongo import models
from accounts.models import User, NurseProfile, DoctorProfile, AdminProfile
from patients.models import PatientMedicalRecord

class PatientAssignment(models.Model):
    assignment_id = models.AutoField(primary_key=True)
    nurse = models.ForeignKey(NurseProfile, on_delete=models.CASCADE, related_name='patient_assignments')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='patient_assignments')
    patient = models.ForeignKey(PatientMedicalRecord, on_delete=models.CASCADE, related_name='assignments')
    assigned_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(AdminProfile, on_delete=models.PROTECT)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'patient_assignments'
        unique_together = ['nurse', 'patient']
    
    def __str__(self):
        return f"Assignment {self.assignment_id}"

class DashboardPreference(models.Model):
    DASHBOARD_TYPES = [
        ('NURSE', 'Nurse Dashboard'),
        ('DOCTOR', 'Doctor Dashboard'),
        ('ADMIN', 'Admin Dashboard'),
    ]
    
    preference_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='dashboard_preferences')
    dashboard_type = models.CharField(max_length=10, choices=DASHBOARD_TYPES)
    layout_config = models.JSONField(default=dict)
    widget_visibility = models.JSONField(default=dict)
    refresh_interval = models.IntegerField(default=300)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'dashboard_preferences'
    
    def __str__(self):
        return f"Preference {self.preference_id}"

class AnalyticsReport(models.Model):
    REPORT_TYPES = [
        ('PATIENT_TRENDS', 'Patient Response Trends'),
        ('ALERT_SUMMARY', 'Alert Summary'),
        ('COMPLETION_RATE', 'Monitoring Completion Rate'),
        ('RISK_ANALYSIS', 'Risk Analysis'),
        ('PATIENT_ENGAGEMENT', 'Patient Engagement'),
    ]
    
    report_id = models.AutoField(primary_key=True)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPES)
    generated_by = models.ForeignKey(AdminProfile, on_delete=models.PROTECT)
    parameters = models.JSONField(default=dict)
    data = models.JSONField(default=dict)
    file = models.CharField(max_length=500, blank=True, null=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    date_range_start = models.DateField()
    date_range_end = models.DateField()
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'analytics_reports'
    
    def __str__(self):
        return f"Report {self.report_id}"