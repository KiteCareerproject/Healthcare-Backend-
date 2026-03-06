from django.urls import path
from . import views

urlpatterns = [
    path('assign/', views.assign_patient, name='assign_patient'),
    path('nurse/<int:nurse_id>/patients/', views.get_nurse_patients, name='nurse_patients'),
    path('doctor/<int:doctor_id>/patients/', views.get_doctor_patients, name='doctor_patients'),
    path('stats/', views.get_dashboard_stats, name='dashboard_stats'),
    # path('patient_activity/', views.get_patient_activity_detail, name='get_patient_activity_detail'),
    # path('questionnaire_stats/', views.get_questionnaire_stats, name='get_questionnaire_stats'),
    path('reports/generate/', views.generate_report, name='generate_report'),
    path('dashboard/report/stats/', views.get_dashboard_stats_report, name='dashboard-stats'),
    # path('demographics/', views.get_patient_demographics, name='patient-demographics'),
    # path('treatment-outcomes/', views.get_treatment_outcomes, name='treatment-outcomes'),

    # Nurse CRUD
    path('nurses/', views.get_all_nurses, name='list-nurses'),
    path('nurses/create/', views.create_nurse, name='create-nurse'),
    path('nurses/<str:nurse_id>/', views.get_nurse, name='get-nurse'),
    path('nurses/<str:nurse_id>/update/', views.update_nurse, name='update-nurse'),
    path('nurses/<str:nurse_id>/delete/', views.delete_nurse, name='delete-nurse'),
    
    # Doctor CRUD
    path('doctors/', views.get_all_doctors, name='list-doctors'),
    path('doctors/create/', views.create_doctor, name='create-doctor'),
    path('doctors/<str:doctor_id>/', views.get_doctor, name='get-doctor'),
    path('doctors/<str:doctor_id>/update/', views.update_doctor, name='update-doctor'),
    path('doctors/<str:doctor_id>/delete/', views.delete_doctor, name='delete-doctor'),
    
    # Patient CRUD
    path('patients/', views.get_all_patients, name='list-patients'),
    path('patients/create/', views.create_patient, name='create-patient'),
    path('patients/<str:patient_id>/', views.get_patient, name='get-patient'),
    path('patients/<str:patient_id>/update/', views.update_patient, name='update-patient'),
    path('patients/<str:patient_id>/delete/', views.delete_patient, name='delete-patient'),
    
    # Bulk operations
    path('bulk/create-nurses/', views.bulk_create_nurses, name='bulk-create-nurses'),
    path('bulk/assign-patients/', views.bulk_assign_patients, name='bulk-assign-patients'),
]