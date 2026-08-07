from rest_framework import serializers
from .models import QuestionCategory, Question, QuestionnaireAssignment, AssignedQuestion
from django.contrib.auth import get_user_model
from patients.models import PatientMedicalRecord
from accounts.models import NurseProfile

User = get_user_model()

class QuestionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionCategory
        fields = '__all__'

class QuestionSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Question
        fields = '__all__'

class AssignedQuestionSerializer(serializers.ModelSerializer):
    question_details = QuestionSerializer(source='question', read_only=True)
    
    class Meta:
        model = AssignedQuestion
        fields = '__all__'

class QuestionnaireAssignmentSerializer(serializers.ModelSerializer):
    assigned_questions = AssignedQuestionSerializer(many=True, read_only=True)
    patient_name = serializers.CharField(source='patient.patient.first_name', read_only=True)
    
    class Meta:
        model = QuestionnaireAssignment
        fields = '__all__'

class CreateQuestionSerializer(serializers.Serializer):
    text = serializers.CharField()
    question_type = serializers.ChoiceField(choices=Question.QUESTION_TYPES)
    category_id = serializers.IntegerField(required=False)
    options = serializers.JSONField(required=False, default=list)
    scale_min = serializers.IntegerField(required=False, default=1)
    scale_max = serializers.IntegerField(required=False, default=10)
    default_frequency = serializers.ChoiceField(choices=Question.FREQUENCY_CHOICES, default='DAILY')
    help_text = serializers.CharField(required=False, allow_blank=True)

class CreateAssignmentSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()
    frequency = serializers.ChoiceField(choices=Question.FREQUENCY_CHOICES)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    question_ids = serializers.ListField(child=serializers.IntegerField())

class UpdateAssignmentSerializer(serializers.Serializer):
    """Serializer for updating assignment"""
    frequency = serializers.ChoiceField(
        choices=[
            ('once', 'Once'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly')
        ],
        required=False
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=[
            ('active', 'Active'),
            ('paused', 'Paused'),
            ('completed', 'Completed'),
            ('expired', 'Expired')
        ],
        required=False
    )
    question_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=False
    )
    
    def validate(self, data):
        # Check if at least one field is provided
        if not data:
            raise serializers.ValidationError("At least one field must be provided")
        
        # Validate dates if both provided
        if 'start_date' in data and 'end_date' in data:
            if data['end_date'] and data['start_date'] > data['end_date']:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after start date'
                })
        
        return data
    

# ============================= CHAT MASSAGE =======================

