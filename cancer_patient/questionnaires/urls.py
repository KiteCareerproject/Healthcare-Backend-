from django.urls import path
from . import views

urlpatterns = [
    path('questions/', views.question_list, name='question_list'),
    path('questions/<int:question_id>/', views.question_detail, name='question_detail'),
    path('categories/', views.get_categories, name='categories'),
    path('assignments/', views.create_assignment, name='create_assignment'),
    path('assignments/<int:assignment_id>/', views.update_assignment, name='update-assignment'),
    path('assignments/patient/<int:patient_id>/', views.get_patient_assignments, name='patient_assignments'),
    path('assignments/patients/<int:patient_id>/', views.assignment_detail, name='patient_assignments'),
    path('assignments/patients/<int:patient_id>/delete-all/', views.delete_all_assignments, name='delete_all_assignments'),

    # Patient submission endpoints
    path('patient/questionnaire/submit/',views.submit_questionnaire_responses, name='submit_questionnaire'),
    # path('patient/questionnaire/save-progress/', views.save_questionnaire_progress, name='save_questionnaire_progress'),

    # Admin APIs for viewing responses
    path('admin/responses/', views.get_all_patient_responses, name='admin-all-responses'),
    path('admin/responses/<str:response_id>/', views.get_response_detail, name='admin-response-detail'),
    path('admin/patients/<str:patient_id>/responses/', views.get_patient_response_history, name='admin-patient-history'),
    
    # Admin notifications
    path('api/admin/notifications/', views.get_admin_notifications, name='admin-notifications'),
    
]