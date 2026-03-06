from rest_framework import serializers
from .models import QuestionCategory, Question, QuestionnaireAssignment, AssignedQuestion

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