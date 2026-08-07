from djongo import models
from patients.models import PatientMedicalRecord, CancerType
from accounts.models import NurseProfile, AdminProfile   
from django.contrib.auth import get_user_model

User = get_user_model()

class QuestionCategory(models.Model):
    category_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'question_categories'
    
    def __str__(self):
        return f"Category {self.category_id}: {self.name}"

class Question(models.Model):
    QUESTION_TYPES = [
        ('YES_NO', 'Yes/No'),
        ('MULTIPLE_CHOICE', 'Multiple Choice'),
        ('SCALE', 'Scale (1-10)'),
        ('TEXT', 'Text Input'),
    ]
    
    FREQUENCY_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('BIWEEKLY', 'Twice a week'),
        ('MONTHLY', 'Monthly'),
    ]
    
    question_id = models.AutoField(primary_key=True)
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    category = models.ForeignKey(QuestionCategory, on_delete=models.SET_NULL, null=True, related_name='questions')
    options = models.JSONField(default=list)
    scale_min = models.IntegerField(default=1)
    scale_max = models.IntegerField(default=10)
    is_active = models.BooleanField(default=True)
    default_frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='DAILY')
    help_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'questions'
    
    def __str__(self):
        return f"Question {self.question_id}: {self.text[:50]}..."

class QuestionnaireAssignment(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
    ]
    
    assignment_id = models.AutoField(primary_key=True)
    patient = models.ForeignKey(PatientMedicalRecord, on_delete=models.CASCADE, related_name='questionnaire_assignments')
    frequency = models.CharField(max_length=20, choices=Question.FREQUENCY_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    assigned_by = models.ForeignKey(NurseProfile, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'questionnaire_assignments'
    
    def __str__(self):
        return f"Assignment {self.assignment_id}: Patient {self.patient.patient_id}"

class AssignedQuestion(models.Model):
    assigned_question_id = models.AutoField(primary_key=True)
    questionnaire_assignment = models.ForeignKey(QuestionnaireAssignment, on_delete=models.CASCADE, related_name='assigned_questions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    order = models.IntegerField()
    is_mandatory = models.BooleanField(default=True)
    conditional_on_question = models.ForeignKey(Question, on_delete=models.SET_NULL, null=True, blank=True, related_name='conditional_questions')
    conditional_answer = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'assigned_questions'
        ordering = ['order']
    
    def __str__(self):
        return f"AssignedQuestion {self.assigned_question_id}"


