from .models import Alert, QuestionResponse
from accounts.models import NurseProfile
import logging

logger = logging.getLogger(__name__)

def check_alert_conditions(daily_response, responses):
    """Check if responses trigger any alerts"""
    alerts = []
    patient = daily_response.patient
    
    # Get assigned nurse
    try:
        nurse = NurseProfile.objects.first()
    except:
        nurse = None
    
    if not nurse:
        logger.warning(f"No nurse assigned for patient {patient.patient_id}")
        return []
    
    for response in responses:
        question = response.question
        alert = None
        
        # Check for critical conditions
        question_text = question.text.lower()
        
        if 'severe pain' in question_text and response.yes_no_response:
            alert = create_alert(
                patient, daily_response, response,
                'HIGH', 'Severe Pain Reported',
                'Patient reported severe pain. Immediate attention required.',
                nurse
            )
        elif 'breathing difficulty' in question_text and response.yes_no_response:
            alert = create_alert(
                patient, daily_response, response,
                'CRITICAL', 'Breathing Difficulty',
                'Patient experiencing breathing difficulty. Emergency attention needed.',
                nurse
            )
        elif 'fever' in question_text and response.yes_no_response:
            alert = create_alert(
                patient, daily_response, response,
                'HIGH', 'High Fever Reported',
                'Patient reported having fever. Medical attention may be needed.',
                nurse
            )
        elif 'pain' in question_text and response.scale_response and response.scale_response >= 7:
            alert = create_alert(
                patient, daily_response, response,
                'HIGH', 'Severe Pain (Scale 7+)',
                f'Patient reported pain level {response.scale_response}/10',
                nurse
            )
        
        if alert:
            alerts.append(alert)
            logger.info(f"Alert created: {alert.alert_id} for patient {patient.patient_id}")
    
    return alerts

def create_alert(patient, daily_response, response, level, title, description, nurse):
    """Create a new alert"""
    alert = Alert.objects.create(
        patient=patient,
        daily_response=daily_response,
        alert_level=level,
        title=title,
        description=description,
        trigger_conditions={
            'question_id': response.question.question_id,
            'response_id': response.question_response_id,
            'response_value': get_response_value(response)
        },
        assigned_to_nurse=nurse,
        status='NEW'
    )
    
    alert.related_responses.add(response)
    
    return alert

def get_response_value(response):
    """Get the actual response value"""
    if response.yes_no_response is not None:
        return 'Yes' if response.yes_no_response else 'No'
    elif response.scale_response:
        return response.scale_response
    elif response.multiple_choice_response:
        return response.multiple_choice_response
    elif response.text_response:
        return response.text_response[:100]
    return None