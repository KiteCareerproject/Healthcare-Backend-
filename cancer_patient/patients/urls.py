from django.urls import path
from . import views

urlpatterns = [
    path('cancer-types/', views.cancer_types, name='cancer_types'),
    path('medical-records/', views.medical_record_list, name='medical_record_list'),
    path('medical-records/<int:record_id>/', views.medical_record_detail, name='medical_record_detail'),
    path('medical-records/<int:record_id>/treatments/', views.add_treatment, name='add_treatment'),
    path('medical-records/<int:record_id>/medications/', views.add_medication, name='add_medication'),
    path('medical-records/<int:record_id>/treatments/list/', views.get_treatments, name='get_treatments'),
    path('medical-records/<int:record_id>/medications/list/', views.get_medications, name='get_medications'),
]