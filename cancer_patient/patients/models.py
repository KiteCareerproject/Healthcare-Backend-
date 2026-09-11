from djongo import models
from accounts.models import PatientProfile, DoctorProfile, NurseProfile

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
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='medical_records')
    cancer_type = models.ForeignKey(CancerType, on_delete=models.PROTECT)
    cancer_stage = models.CharField(max_length=10, choices=CANCER_STAGES)
    diagnosis_date = models.DateField()
    hospital_name = models.CharField(max_length=300)
    treating_doctor = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, related_name='patients')
    known_symptoms = models.TextField()
    allergies = models.TextField(blank=True)
    assigned_nurse = models.ForeignKey(NurseProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='medical_records')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'patient_medical_records'
        ordering = ['-created_at'] 
    
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
    
class FoodCategory(models.Model):
    category_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)  # e.g., Fruits, Vegetables, Dairy, etc.
    description = models.TextField(blank=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'food_categories'
    
    def __str__(self):
        return self.name

class FoodItem(models.Model):
    FOOD_TYPES = [
        ('VEG', 'Vegetarian'),
        ('NON_VEG', 'Non-Vegetarian'),
        ('VEGAN', 'Vegan'),
        ('EGG', 'Eggitarian'),
    ]
    
    food_item_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(FoodCategory, on_delete=models.PROTECT, related_name='food_items')
    food_type = models.CharField(max_length=20, choices=FOOD_TYPES, default='VEG')
    nutritional_info = models.JSONField(default=dict)  # Store nutrients like protein, carbs, etc.
    common_allergen = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    benefits = models.TextField(blank=True)  # General health benefits
    precautions = models.TextField(blank=True)  # General precautions
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'food_items'
    
    def __str__(self):
        return self.name

class DietaryRecommendation(models.Model):
    RECOMMENDATION_TYPES = [
        ('RECOMMENDED', 'Recommended'),
        ('AVOID', 'Avoid'),
        ('CAUTION', 'Caution'),
        ('LIMIT', 'Limit Intake'),
    ]
    
    CANCER_STAGES = [
        ('STAGE_0', 'Stage 0'),
        ('STAGE_1', 'Stage I'),
        ('STAGE_2', 'Stage II'),
        ('STAGE_3', 'Stage III'),
        ('STAGE_4', 'Stage IV'),
        ('ALL', 'All Stages'),
    ]
    
    recommendation_id = models.AutoField(primary_key=True)
    cancer_type = models.ForeignKey(CancerType, on_delete=models.CASCADE, related_name='dietary_recommendations')
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name='recommendations')
    recommendation_type = models.CharField(max_length=20, choices=RECOMMENDATION_TYPES)
    applicable_stages = models.JSONField(default=list)  # List of stages this applies to
    reason = models.TextField()  # Why recommended or avoided
    scientific_evidence = models.TextField(blank=True)  # References or studies
    preparation_method = models.TextField(blank=True)  # How to prepare if recommended
    alternatives = models.TextField(blank=True)  # Alternative foods if avoiding
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'dietary_recommendations'
        unique_together = ['cancer_type', 'food_item', 'recommendation_type']
    
    def __str__(self):
        return f"{self.cancer_type.name} - {self.food_item.name}: {self.recommendation_type}"

class PatientDietaryPlan(models.Model):
    MEAL_TYPES = [
        ('BREAKFAST', 'Breakfast'),
        ('LUNCH', 'Lunch'),
        ('DINNER', 'Dinner'),
        ('SNACK', 'Snack'),
        ('SUPPLEMENT', 'Supplement'),
    ]
    
    plan_id = models.AutoField(primary_key=True)
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='dietary_plans')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, related_name='prescribed_diets')
    food_item = models.ForeignKey(FoodItem, on_delete=models.PROTECT)
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPES)
    quantity = models.CharField(max_length=100)  # e.g., "1 cup", "100g", "1 medium"
    timing = models.TimeField(null=True, blank=True)  # Specific time if needed
    frequency = models.CharField(max_length=100, default="Daily")  # Daily, Weekly, etc.
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    instructions = models.TextField(blank=True)  # Special instructions
    reason = models.TextField(blank=True)  # Why this food is prescribed
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'patient_dietary_plans'
    
    def __str__(self):
        return f"DietPlan {self.plan_id}: {self.patient.user.get_full_name()} - {self.food_item.name}"

class PatientFoodLog(models.Model):
    SYMPTOM_SEVERITY = [
        ('MILD', 'Mild'),
        ('MODERATE', 'Moderate'),
        ('SEVERE', 'Severe'),
        ('NONE', 'None'),
    ]
    
    log_id = models.AutoField(primary_key=True)
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='food_logs')
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    meal_type = models.CharField(max_length=20, choices=PatientDietaryPlan.MEAL_TYPES)
    quantity_consumed = models.CharField(max_length=100)
    consumed_at = models.DateTimeField()
    symptoms_experienced = models.TextField(blank=True)  # Any symptoms after eating
    symptom_severity = models.CharField(max_length=20, choices=SYMPTOM_SEVERITY, default='NONE')
    notes = models.TextField(blank=True)  # Patient's feedback
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'patient_food_logs'
        ordering = ['-consumed_at']
    
    def __str__(self):
        return f"FoodLog {self.log_id}: {self.patient.user.get_full_name()} - {self.food_item.name} at {self.consumed_at}"

class DietaryRestriction(models.Model):
    RESTRICTION_TYPES = [
        ('ALLERGY', 'Allergy'),
        ('INTOLERANCE', 'Intolerance'),
        ('RELIGIOUS', 'Religious'),
        ('TREATMENT_RELATED', 'Treatment Related'),
        ('OTHER', 'Other'),
    ]
    
    restriction_id = models.AutoField(primary_key=True)
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='dietary_restrictions')
    restriction_type = models.CharField(max_length=20, choices=RESTRICTION_TYPES)
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, null=True, blank=True)
    food_category = models.ForeignKey(FoodCategory, on_delete=models.CASCADE, null=True, blank=True)
    description = models.TextField()
    severity = models.CharField(max_length=50, blank=True)  # e.g., "Severe", "Mild"
    diagnosed_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'dietary_restrictions'
    
    def __str__(self):
        patient_name = self.patient.user.get_full_name()
        if self.food_item:
            return f"Restriction for {patient_name}: {self.food_item.name}"
        elif self.food_category:
            return f"Restriction for {patient_name}: {self.food_category.name} category"
        else:
            return f"Restriction for {patient_name}: {self.description[:50]}"

class MealPlan(models.Model):
    WEEKDAYS = [
        ('MONDAY', 'Monday'),
        ('TUESDAY', 'Tuesday'),
        ('WEDNESDAY', 'Wednesday'),
        ('THURSDAY', 'Thursday'),
        ('FRIDAY', 'Friday'),
        ('SATURDAY', 'Saturday'),
        ('SUNDAY', 'Sunday'),
        ('ALL', 'All Days'),
    ]
    
    meal_plan_id = models.AutoField(primary_key=True)
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='meal_plans')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT)
    name = models.CharField(max_length=200)  # e.g., "Week 1 Diet Plan", "Post-Surgery Diet"
    description = models.TextField(blank=True)
    weekday = models.CharField(max_length=20, choices=WEEKDAYS, default='ALL')
    meal_type = models.CharField(max_length=20, choices=PatientDietaryPlan.MEAL_TYPES)
    food_items = models.JSONField(default=list)  # List of food items with quantities
    total_calories = models.IntegerField(null=True, blank=True)
    total_protein = models.FloatField(null=True, blank=True)  # in grams
    total_carbs = models.FloatField(null=True, blank=True)  # in grams
    total_fat = models.FloatField(null=True, blank=True)  # in grams
    instructions = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'meal_plans'
    
    def __str__(self):
        return f"MealPlan {self.meal_plan_id}: {self.name} for {self.patient.user.get_full_name()}"