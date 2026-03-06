from django.urls import path
from . import views

urlpatterns = [
    path('my/', views.get_my_notifications, name='my_notifications'),
    path('<int:notification_id>/read/', views.mark_as_read, name='mark_read'),
    path('read-all/', views.mark_all_read, name='mark_all_read'),
    path('create/', views.create_notification, name='create_notification'),
    path('reminders/', views.get_reminder_schedules, name='reminder_schedules'),
]