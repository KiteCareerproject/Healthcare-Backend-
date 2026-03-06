from rest_framework import serializers
from .models import DailyResponse, QuestionResponse, Alert, AlertEscalation, PatientNote
from patients.serializers import PatientMedicalRecordSerializer
from questionnaires.serializers import QuestionSerializer
# Add to your existing serializers.py

# from rest_framework import serializers
from .models import VoiceMessage, VoiceQuestionTemplate
# from patients.models import PatientMedicalRecord
from accounts.models import NurseProfile, DoctorProfile

class QuestionResponseSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.text', read_only=True)
    
    class Meta:
        model = QuestionResponse
        fields = '__all__'

class DailyResponseSerializer(serializers.ModelSerializer):
    responses = QuestionResponseSerializer(many=True, read_only=True)
    patient_name = serializers.CharField(source='patient.patient.first_name', read_only=True)
    
    class Meta:
        model = DailyResponse
        fields = '__all__'

class AlertSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.patient.first_name', read_only=True)
    nurse_name = serializers.CharField(source='assigned_to_nurse.first_name', read_only=True)
    
    class Meta:
        model = Alert
        fields = '__all__'

class PatientNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    
    class Meta:
        model = PatientNote
        fields = '__all__'
    
    def get_author_name(self, obj):
        if obj.author_nurse:
            return f"{obj.author_nurse.first_name} {obj.author_nurse.last_name} (Nurse)"
        elif obj.author_doctor:
            return f"Dr. {obj.author_doctor.first_name} {obj.author_doctor.last_name}"
        return "Unknown"

class SubmitResponseSerializer(serializers.Serializer):
    responses = serializers.ListField(child=serializers.DictField())

class QuestionResponseSubmitSerializer(serializers.Serializer):
    assigned_question_id = serializers.IntegerField()
    answer = serializers.JSONField()
    

class VoiceMessageSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.patient.user.get_full_name', read_only=True)
    nurse_name = serializers.CharField(source='nurse.user.get_full_name', read_only=True, default=None)
    doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True, default=None)
    
    class Meta:
        model = VoiceMessage
        fields = [
            'voice_message_id', 'patient', 'patient_name',
            'nurse', 'nurse_name', 'doctor', 'doctor_name',
            'alert', 'daily_response', 'message_type', 'status',
            'voice_file', 'voice_duration', 'voice_text',
            'tamil_text', 'tamil_voice_file',
            'is_urgent', 'requires_response',
            'sent_at', 'delivered_at', 'read_at', 'replied_at',
            'parent_message'
        ]
        read_only_fields = ['voice_message_id', 'sent_at']

class VoiceQuestionTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoiceQuestionTemplate
        fields = '__all__'

class VoiceResponseSerializer(serializers.Serializer):
    """For submitting voice responses"""
    daily_response_id = serializers.IntegerField(required=False)
    alert_id = serializers.IntegerField(required=False)
    audio_file = serializers.FileField()
    language = serializers.CharField(default='en')
    
    def validate(self, data):
        if not data.get('daily_response_id') and not data.get('alert_id'):
            raise serializers.ValidationError("Either daily_response_id or alert_id is required")
        return data