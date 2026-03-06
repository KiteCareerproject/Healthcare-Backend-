from django.urls import path
from . import views

urlpatterns = [
    path('questions/', views.question_list, name='question_list'),
    path('questions/<int:question_id>/', views.question_detail, name='question_detail'),
    path('categories/', views.get_categories, name='categories'),
    path('assignments/', views.create_assignment, name='create_assignment'),
    path('assignments/patient/<int:patient_id>/', views.get_patient_assignments, name='patient_assignments'),
]