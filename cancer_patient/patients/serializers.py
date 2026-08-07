from rest_framework import serializers
from .models import (
    PatientMedicalRecord, CancerType, Treatment, Medication,
    FoodCategory, FoodItem, DietaryRecommendation, PatientDietaryPlan,
    PatientFoodLog, DietaryRestriction, MealPlan
)
from accounts.serializers import PatientProfileSerializer, DoctorProfileSerializer,NurseProfile

class CancerTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CancerType
        fields = ['cancer_type_id', 'name', 'description', 'common_symptoms']
        read_only_fields = ['cancer_type_id']
    
    def validate_name(self, value):
        """Check if cancer type with this name already exists"""
        if CancerType.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Cancer type with this name already exists")
        return value
    
    def validate_common_symptoms(self, value):
        """Validate that common_symptoms is a list"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Common symptoms must be a list")
        return value

class TreatmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Treatment
        fields = '__all__'

class MedicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medication
        fields = '__all__'

class PatientMedicalRecordSerializer(serializers.ModelSerializer):
    patient = PatientProfileSerializer(read_only=True)
    cancer_type = CancerTypeSerializer(read_only=True)
    treating_doctor = DoctorProfileSerializer(read_only=True)
    treatments = TreatmentSerializer(many=True, read_only=True)
    medications = MedicationSerializer(many=True, read_only=True)
    assigned_nurse = serializers.SerializerMethodField()
    
    class Meta:
        model = PatientMedicalRecord
        fields = [
            'medical_record_id', 'patient', 'cancer_type', 'treating_doctor',
            'treatments', 'medications', 'cancer_stage', 'diagnosis_date',
            'hospital_name', 'known_symptoms', 'allergies', 'created_at',
            'updated_at', 'assigned_nurse'  # Add assigned_nurse here
        ]
    
    def get_assigned_nurse(self, obj):
        """Get assigned nurse for this medical record"""
        if obj.assigned_nurse:  # Direct check since field exists
            return {
                'nurse_id': obj.assigned_nurse.nurse_id,
                'name': f"{obj.assigned_nurse.first_name} {obj.assigned_nurse.last_name}".strip()
            }
        return None
    
class CreateMedicalRecordSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()
    cancer_type_id = serializers.IntegerField()
    assigned_nurse_id = serializers.IntegerField(required=False, allow_null=True)
    cancer_stage = serializers.ChoiceField(choices=PatientMedicalRecord.CANCER_STAGES)
    diagnosis_date = serializers.DateField()
    hospital_name = serializers.CharField()
    treating_doctor_id = serializers.IntegerField()
    known_symptoms = serializers.CharField()
    allergies = serializers.CharField(required=False, allow_blank=True)

def validate_assigned_nurse_id(self, value):
        """Validate that nurse exists if provided - using nurse_id"""
        if value:
            try:
                # Use nurse_id instead of id
                NurseProfile.objects.get(nurse_id=value)
            except NurseProfile.DoesNotExist:
                raise serializers.ValidationError(f"Nurse with ID {value} does not exist")
        return value

class CreateTreatmentSerializer(serializers.Serializer):
    treatment_type = serializers.ChoiceField(choices=Treatment.TREATMENT_TYPES)
    treatment_name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=Treatment.STATUS_CHOICES, default='PLANNED')
    notes = serializers.CharField(required=False, allow_blank=True)

class CreateMedicationSerializer(serializers.Serializer):
    medication_name = serializers.CharField()
    dosage = serializers.CharField()
    frequency = serializers.ChoiceField(choices=Medication.FREQUENCY_CHOICES)
    timing = serializers.JSONField(default=list)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


# ===================

class FoodCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodCategory
        fields = ['category_id', 'name', 'description']
        read_only_fields = ['category_id']

class FoodItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = FoodItem
        fields = [
            'food_item_id', 'name', 'category', 'category_name', 'food_type',
            'nutritional_info', 'common_allergen', 'description', 'benefits',
            'precautions', 'created_at', 'updated_at'
        ]
        read_only_fields = ['food_item_id', 'created_at', 'updated_at']
    
    def validate_name(self, value):
        """Check if food item with this name already exists"""
        if FoodItem.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Food item with this name already exists")
        return value

class DietaryRecommendationSerializer(serializers.ModelSerializer):
    cancer_type_name = serializers.CharField(source='cancer_type.name', read_only=True)
    food_item_name = serializers.CharField(source='food_item.name', read_only=True)
    
    class Meta:
        model = DietaryRecommendation
        fields = [
            'recommendation_id', 'cancer_type', 'cancer_type_name', 'food_item',
            'food_item_name', 'recommendation_type', 'applicable_stages', 'reason',
            'scientific_evidence', 'preparation_method', 'alternatives',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['recommendation_id', 'created_at', 'updated_at']

class PatientDietaryPlanSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)
    food_item_name = serializers.CharField(source='food_item.name', read_only=True)
    
    class Meta:
        model = PatientDietaryPlan
        fields = [
            'plan_id', 'patient', 'patient_name', 'doctor', 'doctor_name',
            'food_item', 'food_item_name', 'meal_type', 'quantity', 'timing',
            'frequency', 'start_date', 'end_date', 'is_active', 'instructions',
            'reason', 'created_at', 'updated_at'
        ]
        read_only_fields = ['plan_id', 'created_at', 'updated_at']

class CreatePatientDietaryPlanSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()
    food_item_id = serializers.IntegerField()
    doctor_id = serializers.IntegerField(required=False)
    meal_type = serializers.ChoiceField(choices=PatientDietaryPlan.MEAL_TYPES)
    quantity = serializers.CharField()
    timing = serializers.TimeField(required=False, allow_null=True)
    frequency = serializers.CharField(default='Daily')
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    instructions = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)

class PatientFoodLogSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    food_item_name = serializers.CharField(source='food_item.name', read_only=True)
    
    class Meta:
        model = PatientFoodLog
        fields = [
            'log_id', 'patient', 'patient_name', 'food_item', 'food_item_name',
            'meal_type', 'quantity_consumed', 'consumed_at', 'symptoms_experienced',
            'symptom_severity', 'notes', 'created_at'
        ]
        read_only_fields = ['log_id', 'created_at']

class CreatePatientFoodLogSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField(required=False)
    food_item_id = serializers.IntegerField()
    meal_type = serializers.ChoiceField(choices=PatientDietaryPlan.MEAL_TYPES)
    quantity_consumed = serializers.CharField()
    consumed_at = serializers.DateTimeField(required=False, allow_null=True)
    symptoms_experienced = serializers.CharField(required=False, allow_blank=True)
    symptom_severity = serializers.ChoiceField(
        choices=PatientFoodLog.SYMPTOM_SEVERITY, 
        default='NONE'
    )
    notes = serializers.CharField(required=False, allow_blank=True)

class DietaryRestrictionSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    food_item_name = serializers.CharField(source='food_item.name', read_only=True, allow_null=True)
    food_category_name = serializers.CharField(source='food_category.name', read_only=True, allow_null=True)
    
    class Meta:
        model = DietaryRestriction
        fields = [
            'restriction_id', 'patient', 'patient_name', 'restriction_type',
            'food_item', 'food_item_name', 'food_category', 'food_category_name',
            'description', 'severity', 'diagnosed_date', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['restriction_id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Ensure either food_item or food_category is provided"""
        if not data.get('food_item') and not data.get('food_category'):
            raise serializers.ValidationError(
                "Either food_item or food_category must be provided"
            )
        return data

class MealPlanSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)
    
    class Meta:
        model = MealPlan
        fields = [
            'meal_plan_id', 'patient', 'patient_name', 'doctor', 'doctor_name',
            'name', 'description', 'weekday', 'meal_type', 'food_items',
            'total_calories', 'total_protein', 'total_carbs', 'total_fat',
            'instructions', 'start_date', 'end_date', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['meal_plan_id', 'created_at', 'updated_at']

class CreateMealPlanSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()
    doctor_id = serializers.IntegerField(required=False)
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    weekday = serializers.ChoiceField(choices=MealPlan.WEEKDAYS, default='ALL')
    meal_type = serializers.ChoiceField(choices=PatientDietaryPlan.MEAL_TYPES)
    food_items = serializers.JSONField()
    total_calories = serializers.IntegerField(required=False, allow_null=True)
    total_protein = serializers.FloatField(required=False, allow_null=True)
    total_carbs = serializers.FloatField(required=False, allow_null=True)
    total_fat = serializers.FloatField(required=False, allow_null=True)
    instructions = serializers.CharField(required=False, allow_blank=True)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)