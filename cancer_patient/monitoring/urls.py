from django.urls import path
from . import views

urlpatterns = [
    path('questionnaire/today/', views.get_today_questionnaire, name='today_questionnaire'),
    path('questionnaire/<int:response_id>/submit/', views.submit_questionnaire, name='submit_questionnaire'),
    path('alerts/', views.get_alerts, name='get_alerts'),
    path('alerts/<int:alert_id>/acknowledge/', views.acknowledge_alert, name='acknowledge_alert'),
    path('patients/<int:patient_id>/notes/', views.add_patient_note, name='add_patient_note'),
    path('patients/<int:patient_id>/responses/', views.get_patient_responses, name='patient_responses'),

    # Voice messaging URLs
    path('voice/nurse/send-question/', views.nurse_send_voice_question, name='nurse_send_voice_question'),
    path('voice/patient/reply/', views.patient_voice_reply, name='patient_voice_reply'),
    path('voice/messages/', views.get_voice_messages, name='get_voice_messages'),
    path('voice/message/<int:message_id>/read/', views.mark_voice_message_read, name='mark_voice_message_read'),
    
    # Voice utility APIs
    path('voice/to-text/', views.voice_to_text_api, name='voice_to_text'),
    path('text/to-voice/', views.text_to_voice_api, name='text_to_voice'),
    path('translate/to-tamil/', views.translate_to_tamil_api, name='translate_to_tamil'),
    
    # Templates
    # path('voice/templates/', views.get_voice_templates, name='get_voice_templates'),

    # Alert URLs
    path('alerts/send/', views.send_alert_to_patient, name='send_alert'),
    path('alerts/bulk-send/', views.send_bulk_alerts, name='bulk_send_alerts'),
    path('alerts/patient/<str:patient_id>/', views.get_patient_alerts, name='patient_alerts'),
    path('alerts/<str:alert_id>/read/', views.mark_alert_read, name='mark_alert_read'),
    path('alerts/<str:alert_id>/acknowledge/', views.acknowledge_alert, name='acknowledge_alert'),
    path('alerts/<str:alert_id>/delete/', views.delete_alert, name='delete_alert'),
    # path('api/alerts/templates/', views.get_alert_templates, name='alert_templates')

]