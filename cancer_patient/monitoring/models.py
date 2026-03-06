from djongo import models
from django.utils import timezone
from patients.models import PatientMedicalRecord
from questionnaires.models import Question, AssignedQuestion, QuestionnaireAssignment
from accounts.models import NurseProfile, DoctorProfile

class DailyResponse(models.Model):
    response_id = models.AutoField(primary_key=True)
    patient = models.ForeignKey(PatientMedicalRecord, on_delete=models.CASCADE, related_name='daily_responses')
    response_date = models.DateField(default=timezone.now)
    questionnaire_assignment = models.ForeignKey(QuestionnaireAssignment, on_delete=models.PROTECT)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'daily_responses'
        unique_together = ['patient', 'response_date', 'questionnaire_assignment']
    
    def __str__(self):
        return f"DailyResponse {self.response_id}: Patient {self.patient.patient_id}"

class QuestionResponse(models.Model):
    question_response_id = models.AutoField(primary_key=True)
    daily_response = models.ForeignKey(DailyResponse, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    assigned_question = models.ForeignKey(AssignedQuestion, on_delete=models.PROTECT)
    
    yes_no_response = models.BooleanField(null=True, blank=True)
    multiple_choice_response = models.CharField(max_length=200, blank=True)
    scale_response = models.IntegerField(null=True, blank=True)
    text_response = models.TextField(blank=True)
    
    responded_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'question_responses'
    
    def __str__(self):
        return f"QuestionResponse {self.question_response_id}"

class Alert(models.Model):
    ALERT_LEVELS = [
        ('LOW', 'Low Risk'),
        ('MEDIUM', 'Medium Risk'),
        ('HIGH', 'High Risk'),
        ('CRITICAL', 'Critical'),
    ]
    
    ALERT_STATUS = [
        ('NEW', 'New'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('ESCALATED', 'Escalated'),
    ]
    
    alert_id = models.AutoField(primary_key=True)
    patient = models.ForeignKey(PatientMedicalRecord, on_delete=models.CASCADE, related_name='alerts')
    daily_response = models.ForeignKey(DailyResponse, on_delete=models.CASCADE, related_name='alerts', null=True)
    alert_level = models.CharField(max_length=10, choices=ALERT_LEVELS)
    status = models.CharField(max_length=20, choices=ALERT_STATUS, default='NEW')
    title = models.CharField(max_length=200)
    description = models.TextField()
    trigger_conditions = models.JSONField(default=dict)
    related_responses = models.ManyToManyField(QuestionResponse, blank=True)
    assigned_to_nurse = models.ForeignKey(NurseProfile, on_delete=models.PROTECT, related_name='assigned_alerts')
    escalated_to_doctor = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, null=True, blank=True, related_name='escalated_alerts')
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'alerts'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Alert {self.alert_id}: {self.title}"

class AlertEscalation(models.Model):
    escalation_id = models.AutoField(primary_key=True)
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name='escalations')
    escalated_by = models.ForeignKey(NurseProfile, on_delete=models.PROTECT)
    escalated_to = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT)
    reason = models.TextField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'alert_escalations'
    
    def __str__(self):
        return f"Escalation {self.escalation_id}"

class PatientNote(models.Model):
    note_id = models.AutoField(primary_key=True)
    patient = models.ForeignKey(PatientMedicalRecord, on_delete=models.CASCADE, related_name='notes')
    author_nurse = models.ForeignKey(NurseProfile, on_delete=models.PROTECT, null=True, blank=True)
    author_doctor = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, null=True, blank=True)
    alert = models.ForeignKey(Alert, on_delete=models.SET_NULL, null=True, blank=True, related_name='notes')
    note = models.TextField()
    is_private = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'patient_notes'
    
    def __str__(self):
        return f"Note {self.note_id}"


class VoiceMessage(models.Model):
    """Voice messages between nurse and patient"""
    
    MESSAGE_TYPES = [
        ('QUESTION', 'Question from Nurse'),
        ('REPLY', 'Reply from Patient'),
        ('ALERT', 'Alert Notification'),
    ]
    
    STATUS_CHOICES = [
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('READ', 'Read'),
        ('REPLIED', 'Replied'),
    ]
    
    voice_message_id = models.AutoField(primary_key=True)
    
    # Relationships
    patient = models.ForeignKey(PatientMedicalRecord, on_delete=models.CASCADE, related_name='voice_messages')
    nurse = models.ForeignKey(NurseProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='sent_voice_messages')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='sent_voice_messages')
    
    # For alerts linking
    alert = models.ForeignKey(Alert, on_delete=models.SET_NULL, null=True, blank=True, related_name='voice_messages')
    daily_response = models.ForeignKey(DailyResponse, on_delete=models.SET_NULL, null=True, blank=True, related_name='voice_messages')
    
    # Message content
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='QUESTION')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SENT')
    
    # Voice file
    voice_file = models.FileField(upload_to='voice_messages/%Y/%m/%d/', null=True, blank=True)
    voice_duration = models.IntegerField(default=0)  # Duration in seconds
    voice_text = models.TextField(blank=True)  # Speech-to-text conversion
    
    # Tamil support
    tamil_text = models.TextField(blank=True)  # Tamil translation
    tamil_voice_file = models.FileField(upload_to='voice_messages/tamil/%Y/%m/%d/', null=True, blank=True)
    
    # Metadata
    is_urgent = models.BooleanField(default=False)
    requires_response = models.BooleanField(default=True)
    
    # Timestamps
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    
    # Reference to parent message (for replies)
    parent_message = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'voice_messages'
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"VoiceMessage {self.voice_message_id}: {self.message_type}"
    
    def mark_delivered(self):
        self.status = 'DELIVERED'
        self.delivered_at = timezone.now()
        self.save()
    
    def mark_read(self):
        self.status = 'READ'
        self.read_at = timezone.now()
        self.save()

class VoiceQuestionTemplate(models.Model):
    """Pre-recorded question templates for nurses"""
    
    template_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=200)
    text_content = models.TextField()
    tamil_content = models.TextField(blank=True)
    
    # Voice files
    english_voice = models.FileField(upload_to='voice_templates/english/', null=True, blank=True)
    tamil_voice = models.FileField(upload_to='voice_templates/tamil/', null=True, blank=True)
    
    # For which symptom/question
    related_question = models.ForeignKey(Question, on_delete=models.SET_NULL, null=True, blank=True)
    
    duration = models.IntegerField(default=0)  # Duration in seconds
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'voice_question_templates'
    
    def __str__(self):
        return self.title