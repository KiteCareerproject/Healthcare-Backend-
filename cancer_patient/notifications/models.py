# from djongo import models
# from accounts.models import User
# from patients.models import PatientMedicalRecord, Medication
# from monitoring.models import Alert

# class Notification(models.Model):
#     NOTIFICATION_TYPES = [
#         ('QUESTIONNAIRE', 'Questionnaire Reminder'),
#         ('MEDICATION', 'Medication Reminder'),
#         ('ALERT', 'Alert Notification'),
#         ('MESSAGE', 'Message from Nurse'),
#         ('SYSTEM', 'System Notification'),
#     ]
    
#     PRIORITY_LEVELS = [
#         ('LOW', 'Low'),
#         ('MEDIUM', 'Medium'),
#         ('HIGH', 'High'),
#     ]
    
#     notification_id = models.AutoField(primary_key=True)
#     recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
#     notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
#     priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='MEDIUM')
#     title = models.CharField(max_length=200)
#     message = models.TextField()
    
#     related_patient = models.ForeignKey(PatientMedicalRecord, on_delete=models.SET_NULL, null=True, blank=True)
#     related_alert = models.ForeignKey(Alert, on_delete=models.SET_NULL, null=True, blank=True)
    
#     is_read = models.BooleanField(default=False)
#     is_sent = models.BooleanField(default=False)
#     sent_at = models.DateTimeField(null=True, blank=True)
#     read_at = models.DateTimeField(null=True, blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)
    
#     objects = models.DjongoManager()
    
#     class Meta:
#         db_table = 'notifications'
#         ordering = ['-created_at']
    
#     def __str__(self):
#         return f"Notification {self.notification_id}"

# class ReminderSchedule(models.Model):
#     REMINDER_TYPES = [
#         ('QUESTIONNAIRE', 'Questionnaire Reminder'),
#         ('MEDICATION', 'Medication Reminder'),
#     ]
    
#     schedule_id = models.AutoField(primary_key=True)
#     patient = models.ForeignKey(PatientMedicalRecord, on_delete=models.CASCADE, related_name='reminder_schedules')
#     reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPES)
    
#     medication = models.ForeignKey(Medication, on_delete=models.CASCADE, null=True, blank=True)
    
#     time = models.TimeField()
#     days_of_week = models.JSONField(default=list)
    
#     is_recurring = models.BooleanField(default=True)
#     start_date = models.DateField()
#     end_date = models.DateField(null=True, blank=True)
    
#     is_active = models.BooleanField(default=True)
#     last_triggered = models.DateTimeField(null=True, blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     objects = models.DjongoManager()
    
#     class Meta:
#         db_table = 'reminder_schedules'
    
#     def __str__(self):
#         return f"Schedule {self.schedule_id}"

# class NotificationLog(models.Model):
#     DELIVERY_STATUS = [
#         ('PENDING', 'Pending'),
#         ('SENT', 'Sent'),
#         ('FAILED', 'Failed'),
#         ('DELIVERED', 'Delivered'),
#     ]
    
#     log_id = models.AutoField(primary_key=True)
#     notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='delivery_logs')
#     delivery_method = models.CharField(max_length=20, choices=[
#         ('PUSH', 'Push Notification'),
#         ('SMS', 'SMS'),
#         ('EMAIL', 'Email'),
#         ('IN_APP', 'In-App'),
#     ])
#     status = models.CharField(max_length=20, choices=DELIVERY_STATUS, default='PENDING')
#     error_message = models.TextField(blank=True)
#     retry_count = models.IntegerField(default=0)
#     sent_at = models.DateTimeField(null=True, blank=True)
#     delivered_at = models.DateTimeField(null=True, blank=True)
    
#     objects = models.DjongoManager()
    
#     class Meta:
#         db_table = 'notification_logs'
    
#     def __str__(self):
#         return f"Log {self.log_id}"



# notifications/models.py
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
        ('APPOINTMENT', 'Appointment Reminder'),
        ('VACCINATION', 'Vaccination Update'),
    ]
    
    PRIORITY_LEVELS = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    notification_id = models.AutoField(primary_key=True)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='MEDIUM')
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    related_patient = models.ForeignKey(PatientMedicalRecord, on_delete=models.SET_NULL, null=True, blank=True)
    related_alert = models.ForeignKey(Alert, on_delete=models.SET_NULL, null=True, blank=True)
    
    # WebSocket specific fields
    delivered_via_websocket = models.BooleanField(default=False)
    websocket_delivered_at = models.DateTimeField(null=True, blank=True)
    websocket_retry_count = models.IntegerField(default=0)
    
    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)
    action_url = models.CharField(max_length=500, null=True, blank=True)
    image_url = models.CharField(max_length=500, null=True, blank=True)
    
    # Status fields
    is_read = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)
    is_delivered = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['priority']),
        ]
    
    def __str__(self):
        return f"Notification {self.notification_id} - {self.title}"

class NotificationDelivery(models.Model):
    """Track WebSocket and other delivery methods"""
    DELIVERY_STATUS = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
        ('RETRYING', 'Retrying'),
    ]
    
    DELIVERY_METHODS = [
        ('WEBSOCKET', 'WebSocket'),
        ('PUSH', 'Push Notification'),
        ('SMS', 'SMS'),
        ('EMAIL', 'Email'),
        ('IN_APP', 'In-App'),
    ]
    
    delivery_id = models.AutoField(primary_key=True)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='deliveries')
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_METHODS)
    channel_name = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=DELIVERY_STATUS, default='PENDING')
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'notification_deliveries'
        indexes = [
            models.Index(fields=['notification', 'delivery_method']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Delivery {self.delivery_id} - {self.delivery_method}"

class NotificationPreference(models.Model):
    """User notification preferences"""
    preference_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Channel preferences
    enable_websocket = models.BooleanField(default=True)
    enable_push = models.BooleanField(default=False)
    enable_email = models.BooleanField(default=True)
    enable_sms = models.BooleanField(default=False)
    
    # Type preferences
    notification_types = models.JSONField(default=list)  # List of enabled types
    priority_threshold = models.CharField(max_length=10, choices=Notification.PRIORITY_LEVELS, default='LOW')
    
    # Quiet hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    quiet_hours_timezone = models.CharField(max_length=50, default='UTC')
    
    # Sound preferences
    sound_enabled = models.BooleanField(default=True)
    sound_file = models.CharField(max_length=255, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'notification_preferences'
        unique_together = ['user']
    
    def __str__(self):
        return f"Preferences for {self.user.username}"

class NotificationLog(models.Model):
    """Legacy log model - kept for backward compatibility"""
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