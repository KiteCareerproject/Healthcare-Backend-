from django.urls import path
from . import views

urlpatterns = [
    path('cancer-types/', views.cancer_types, name='cancer_types'),
    path('medical-records/', views.medical_record_list, name='medical_record_list'),
    path('medical-records/<int:patient_id>/', views.medical_record_detail, name='medical_record_detail'),
    path('medical-records/<int:record_id>/', views.medical_record_detail, name='medical_record_detail'),
    path('medical-records/<int:record_id>/treatments/', views.add_treatment, name='add_treatment'),
    path('medical-records/<int:record_id>/medical/', views.get_medications, name='get_medications'),
    path('medical-records/<int:record_id>/medications/', views.add_medication, name='add_medication'),
    path('medical-records/<int:record_id>/treatments/list/', views.get_treatments, name='get_treatments'),
    path('medical-records/<int:record_id>/treatments/list/<int:treatment_id>/', views.get_treatments, name='get_treatments'),
    path('medical-records/<int:record_id>/medications/', views.get_medications, name='get_medications'),
    path('medical-records/<int:record_id>/medications/<int:medication_id>/', views.get_medications, name='medications-detail'),
    
    # ==================== FOOD ITEM URLS ====================
    path('food-categories/', views.food_categories, name='food_categories'),
    path('food-items/', views.food_items, name='food_items'),
    path('food-items/<int:item_id>/', views.food_item_detail, name='food_item_detail'),
    
    path('patient-food/<int:patient_id>/', views.patient_food_management, name='patient_food_management'),
    path('patient-food/<int:patient_id>/<int:item_id>/', views.patient_food_management, name='patient_food_management_detail'),
    
    # Dietary Plans
    path('patients/<int:patient_id>/dietary-plans/<int:plan_id>/', views.dietary_plan_detail, name='dietary-plan-detail'),
    
    # Food Logs
    path('patients/<int:patient_id>/food-logs/<int:log_id>/', views.food_log_detail, name='food-log-detail'),
    
    # Dietary Restrictions
    path('patients/<int:patient_id>/dietary-restrictions/<int:restriction_id>/', views.dietary_restriction_detail, name='dietary-restriction-detail'),
    
    # Meal Plans
    path('patients/<int:patient_id>/meal-plans/<int:meal_plan_id>/', views.meal_plan_detail, name='meal-plan-detail'),

    path('cancer-type-distribution/', views.cancer_type_distribution, name='cancer-type-distribution'),
]