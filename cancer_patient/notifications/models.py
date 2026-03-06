from djongo import models
from accounts.models import User
from patients.models import PatientMedicalRecord, Medication
from monitoring.models import Alert

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('QUESTIONNAIRE', 'Questionnaire Reminder'),
        ('MEDICATION', 'Medication Reminder'),
        ('ALERT', 'Alert Notification'),
        ('MESSAGE', 'Message from Nurse'),
        ('SYSTEM', 'System Notification'),
    ]
    
    PRIORITY_LEVELS = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
    ]
    
    notification_id = models.AutoField(primary_key=True)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='MEDIUM')
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    related_patient = models.ForeignKey(PatientMedicalRecord, on_delete=models.SET_NULL, null=True, blank=True)
    related_alert = models.ForeignKey(Alert, on_delete=models.SET_NULL, null=True, blank=True)
    
    is_read = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Notification {self.notification_id}"

class ReminderSchedule(models.Model):
    REMINDER_TYPES = [
        ('QUESTIONNAIRE', 'Questionnaire Reminder'),
        ('MEDICATION', 'Medication Reminder'),
    ]
    
    schedule_id = models.AutoField(primary_key=True)
    patient = models.ForeignKey(PatientMedicalRecord, on_delete=models.CASCADE, related_name='reminder_schedules')
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPES)
    
    medication = models.ForeignKey(Medication, on_delete=models.CASCADE, null=True, blank=True)
    
    time = models.TimeField()
    days_of_week = models.JSONField(default=list)
    
    is_recurring = models.BooleanField(default=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'reminder_schedules'
    
    def __str__(self):
        return f"Schedule {self.schedule_id}"

class NotificationLog(models.Model):
    DELIVERY_STATUS = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('DELIVERED', 'Delivered'),
    ]
    
    log_id = models.AutoField(primary_key=True)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='delivery_logs')
    delivery_method = models.CharField(max_length=20, choices=[
        ('PUSH', 'Push Notification'),
        ('SMS', 'SMS'),
        ('EMAIL', 'Email'),
        ('IN_APP', 'In-App'),
    ])
    status = models.CharField(max_length=20, choices=DELIVERY_STATUS, default='PENDING')
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'notification_logs'
    
    def __str__(self):
        return f"Log {self.log_id}"