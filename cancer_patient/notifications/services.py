from celery import shared_task
from django.utils import timezone
from .models import ReminderSchedule, Notification
from accounts.models import User, PatientProfile
from patients.models import PatientMedicalRecord
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_reminders():
    """Send scheduled reminders to patients"""
    now = timezone.now()
    current_time = now.time()
    current_day = now.weekday()
    
    schedules = ReminderSchedule.objects.filter(
        is_active=True,
        time__hour=current_time.hour,
        time__minute=current_time.minute
    )
    
    for schedule in schedules:
        if current_day in schedule.days_of_week:
            try:
                # Create notification
                user = schedule.patient.patient.user
                
                if schedule.reminder_type == 'QUESTIONNAIRE':
                    title = "Questionnaire Reminder"
                    message = "Please complete your daily health questionnaire"
                elif schedule.reminder_type == 'MEDICATION' and schedule.medication:
                    title = "Medication Reminder"
                    message = f"Time to take {schedule.medication.medication_name} ({schedule.medication.dosage})"
                else:
                    continue
                
                Notification.objects.create(
                    recipient=user,
                    notification_type=schedule.reminder_type,
                    title=title,
                    message=message,
                    related_patient=schedule.patient
                )
                
                schedule.last_triggered = now
                schedule.save()
                
                logger.info(f"Reminder sent to patient {schedule.patient.patient_id}")
                
            except Exception as e:
                logger.error(f"Failed to send reminder: {str(e)}")