from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from .models import DailyResponse, QuestionResponse, Alert, PatientNote
from patients.models import PatientMedicalRecord, PatientProfile
from questionnaires.models import QuestionnaireAssignment, AssignedQuestion
from accounts.models import NurseProfile, DoctorProfile
from accounts.utils import handle_errors, APIError
from .serializers import (
    DailyResponseSerializer, QuestionResponseSerializer,
    AlertSerializer, PatientNoteSerializer, SubmitResponseSerializer
)
from .alerts import check_alert_conditions
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_today_questionnaire(request):
    """Get today's questionnaire for patient"""
    user = request.user
    
    if user.user_type != 'PATIENT':
        raise APIError("Only patients can access questionnaires", 
                      status_code=status.HTTP_403_FORBIDDEN)
    
    # AUTO-FIX: Check and create patient profile if missing
    try:
        patient = PatientProfile.objects.get(user=user)
    except PatientProfile.DoesNotExist:
        # Create patient profile from user data
        logger.warning(f"Auto-creating missing patient profile for user {user.username}")
        
        # Try to extract name from username or use defaults
        first_name = user.username.capitalize() if user.username else "Patient"
        last_name = ""
        
        patient = PatientProfile.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            aadhar_number=f"TEMP_{user.id}_{timezone.now().timestamp()}"  # Temporary unique value
        )
        logger.info(f"Created patient profile {patient.patient_id} for user {user.username}")
    
    # AUTO-FIX: Check and create medical record if missing
    try:
        medical_record = PatientMedicalRecord.objects.get(patient=patient)
    except PatientMedicalRecord.DoesNotExist:
        logger.warning(f"Auto-creating missing medical record for patient {patient.patient_id}")
        medical_record = PatientMedicalRecord.objects.create(
            patient=patient
            # Add any required fields with defaults
        )
        logger.info(f"Created medical record {medical_record.medical_record_id}")
    
    today = timezone.now().date()
    
    try:
        assignment = QuestionnaireAssignment.objects.get(
            patient=medical_record,
            status='ACTIVE',
            start_date__lte=today
        )
        
        existing_response = DailyResponse.objects.filter(
            patient=medical_record,
            response_date=today,
            questionnaire_assignment=assignment
        ).first()
        
        if existing_response and existing_response.is_completed:
            return Response({
                'success': True,
                'message': 'You have already completed today\'s questionnaire',
                'data': {
                    'already_completed': True,
                    'response': DailyResponseSerializer(existing_response).data
                }
            })
        
        assigned_questions = AssignedQuestion.objects.filter(
            questionnaire_assignment=assignment
        ).select_related('question').order_by('order')
        
        questions_data = []
        for aq in assigned_questions:
            question = aq.question
            questions_data.append({
                'assigned_question_id': aq.assigned_question_id,
                'question_id': question.question_id,
                'text': question.text,
                'question_type': question.question_type,
                'options': question.options if question.question_type == 'MULTIPLE_CHOICE' else [],
                'scale_min': question.scale_min if question.question_type == 'SCALE' else None,
                'scale_max': question.scale_max if question.question_type == 'SCALE' else None,
                'is_mandatory': aq.is_mandatory,
                'order': aq.order
            })
        
        daily_response, created = DailyResponse.objects.get_or_create(
            patient=medical_record,
            response_date=today,
            questionnaire_assignment=assignment,
            defaults={'is_completed': False}
        )
        
        return Response({
            'success': True,
            'data': {
                'response_id': daily_response.response_id,
                'questions': questions_data,
                'total_questions': len(questions_data),
                'completed': existing_response.is_completed if existing_response else False
            }
        })
        
    except QuestionnaireAssignment.DoesNotExist:
        return Response({
            'success': True,
            'message': 'No questionnaire assigned for today',
            'data': {'questions': []}
        })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def submit_questionnaire(request, response_id):
    """Submit questionnaire responses"""
    user = request.user
    
    if user.user_type != 'PATIENT':
        raise APIError("Only patients can submit questionnaires", 
                      status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        daily_response = DailyResponse.objects.get(response_id=response_id)
    except DailyResponse.DoesNotExist:
        raise APIError("Response not found", status_code=status.HTTP_404_NOT_FOUND)
    
    try:
        patient = PatientProfile.objects.get(user=user)
        if daily_response.patient.patient_id != patient.patient_id:
            raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    except PatientProfile.DoesNotExist:
        raise APIError("Patient profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
    if daily_response.is_completed:
        raise APIError("Questionnaire already completed", status_code=status.HTTP_400_BAD_REQUEST)
    
    serializer = SubmitResponseSerializer(data=request.data)
    if not serializer.is_valid():
        raise APIError("Validation error", errors=serializer.errors)
    
    data = serializer.validated_data
    responses = data.get('responses', [])
    
    if not responses:
        raise APIError("No responses provided")
    
    try:
        saved_responses = []
        
        for resp in responses:
            assigned_question_id = resp.get('assigned_question_id')
            answer = resp.get('answer')
            
            if not assigned_question_id or answer is None:
                continue
            
            try:
                assigned_question = AssignedQuestion.objects.get(
                    assigned_question_id=assigned_question_id,
                    questionnaire_assignment=daily_response.questionnaire_assignment
                )
            except AssignedQuestion.DoesNotExist:
                continue
            
            question = assigned_question.question
            
            response_data = {
                'daily_response': daily_response,
                'question': question,
                'assigned_question': assigned_question
            }
            
            if question.question_type == 'YES_NO':
                response_data['yes_no_response'] = answer
            elif question.question_type == 'MULTIPLE_CHOICE':
                response_data['multiple_choice_response'] = answer
            elif question.question_type == 'SCALE':
                response_data['scale_response'] = answer
            elif question.question_type == 'TEXT':
                response_data['text_response'] = answer
            
            question_response = QuestionResponse.objects.create(**response_data)
            saved_responses.append(question_response)
        
        daily_response.is_completed = True
        daily_response.completed_at = timezone.now()
        daily_response.save()
        
        alerts = check_alert_conditions(daily_response, saved_responses)
        
        logger.info(f"Questionnaire {response_id} completed by patient {patient.patient_id}")
        
        return Response({
            'success': True,
            'message': 'Questionnaire submitted successfully',
            'data': {
                'response_id': daily_response.response_id,
                'responses_count': len(saved_responses),
                'alerts_generated': len(alerts)
            }
        })
        
    except Exception as e:
        logger.error(f"Error submitting questionnaire: {str(e)}")
        raise APIError(f"Failed to submit questionnaire: {str(e)}")

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_alerts(request):
    """Get alerts (for nurses/doctors)"""
    user = request.user
    
    if user.user_type not in ['NURSE', 'DOCTOR', 'ADMIN']:
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    status_filter = request.GET.get('status', 'NEW')
    level_filter = request.GET.get('level')
    
    alerts = Alert.objects.all()
    
    if status_filter:
        alerts = alerts.filter(status=status_filter)
    
    if level_filter:
        alerts = alerts.filter(alert_level=level_filter)
    
    if user.user_type == 'NURSE':
        try:
            nurse = NurseProfile.objects.get(user=user)
            alerts = alerts.filter(assigned_to_nurse=nurse)
        except NurseProfile.DoesNotExist:
            pass
    
    alerts = alerts.order_by('-created_at')
    
    serializer = AlertSerializer(alerts, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data,
        'total': alerts.count()
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
# @handle_errors  # Comment this out if handle_errors is not defined
def acknowledge_alert(request, alert_id):
    """Acknowledge an alert"""
    user = request.user
    
    # Check if user has permission
    if user.user_type not in ['NURSE', 'DOCTOR']:
        return Response({
            'success': False,
            'error': 'Permission denied. Only nurses and doctors can acknowledge alerts.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        alert = Alert.objects.get(alert_id=alert_id)
    except Alert.DoesNotExist:
        return Response({
            'success': False,
            'error': f'Alert with ID {alert_id} not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if alert can be acknowledged
    if alert.status != 'NEW':
        return Response({
            'success': False,
            'error': f'Alert already {alert.status.lower()}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Update alert status
    alert.status = 'ACKNOWLEDGED'
    alert.acknowledged_at = timezone.now()
    alert.acknowledged_by = user  # Add this field to track who acknowledged
    alert.save()
    
    logger.info(f"Alert {alert_id} acknowledged by {user.username} (ID: {user.id})")
    
    return Response({
        'success': True,
        'message': 'Alert acknowledged successfully',
        'data': AlertSerializer(alert).context({'request': request}).data
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def add_patient_note(request, patient_id):
    """Add note to patient - FIXED"""
    
    # Debug
    print("=== ADD PATIENT NOTE DEBUG ===")
    print("Content-Type:", request.content_type)
    print("Data:", request.data)
    print("POST:", request.POST)
    print("===============================")
    
    user = request.user
    
    if user.user_type not in ['NURSE', 'DOCTOR']:
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    # Get patient
    try:
        patient = PatientMedicalRecord.objects.get(medical_record_id=patient_id)
    except PatientMedicalRecord.DoesNotExist:
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # ===== FIX: Try multiple field names for note =====
    note_text = None
    
    # Check in request.data (JSON)
    if isinstance(request.data, dict):
        possible_keys = ['note', 'notes', 'text', 'content', 'message', 'Note', 'NOTES']
        for key in possible_keys:
            if key in request.data:
                note_text = request.data[key]
                print(f"Found note with key: {key}")
                break
    
    # Check in request.POST (form-data)
    if not note_text:
        for key in request.POST.keys():
            clean_key = key.strip().replace('"', '').lower()
            if clean_key in ['note', 'notes', 'text', 'content']:
                note_text = request.POST.get(key)
                print(f"Found note in POST with key: {key}")
                break
    
    # Check in query params (as fallback)
    if not note_text:
        note_text = request.query_params.get('note') or request.query_params.get('text')
    
    # ===== Get other fields with flexible names =====
    alert_id = None
    is_private = False
    
    # Alert ID
    if isinstance(request.data, dict):
        for key in request.data.keys():
            if 'alert' in key.lower() and 'id' in key.lower():
                alert_id = request.data[key]
                break
    
    if not alert_id and request.POST:
        for key in request.POST.keys():
            if 'alert' in key.lower() and 'id' in key.lower():
                alert_id = request.POST.get(key)
                break
    
    # Is private
    if isinstance(request.data, dict):
        for key in request.data.keys():
            if 'private' in key.lower():
                val = request.data[key]
                is_private = str(val).lower() in ['true', '1', 'yes', 'on']
                break
    
    if not note_text:
        return Response({
            'success': False,
            'error': 'Note text is required',
            'debug': {
                'received_data': dict(request.data) if isinstance(request.data, dict) else str(request.data),
                'received_post': dict(request.POST) if request.POST else {},
                'query_params': dict(request.query_params)
            },
            'hint': 'Send JSON with key "note" or form-data with key "note"'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Prepare note data
    note_data = {
        'patient': patient,
        'note': note_text,
        'is_private': is_private
    }
    
    # Add author
    if user.user_type == 'NURSE':
        note_data['author_nurse'] = NurseProfile.objects.get(user=user)
    elif user.user_type == 'DOCTOR':
        note_data['author_doctor'] = DoctorProfile.objects.get(user=user)
    
    # Add alert if provided
    if alert_id:
        try:
            alert = Alert.objects.get(alert_id=alert_id)
            note_data['alert'] = alert
        except Alert.DoesNotExist:
            pass
    
    # Create note
    note = PatientNote.objects.create(**note_data)
    
    logger.info(f"Note added to patient {patient_id} by {user.username}")
    
    return Response({
        'success': True,
        'message': 'Note added successfully',
        'data': PatientNoteSerializer(note).data
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_patient_responses(request, patient_id):
    """Get all responses for a patient"""
    user = request.user
    
    if user.user_type not in ['NURSE', 'DOCTOR', 'ADMIN']:
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        patient = PatientMedicalRecord.objects.get(medical_record_id=patient_id)
    except PatientMedicalRecord.DoesNotExist:
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
    
    responses = DailyResponse.objects.filter(patient=patient).order_by('-response_date')
    serializer = DailyResponseSerializer(responses, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data
    })




# ===============================================================

# Add these imports at the top
from .voice_services import VoiceService, VoiceMessagingService
from .models import VoiceMessage, VoiceQuestionTemplate
from .serializers import VoiceMessageSerializer, VoiceResponseSerializer, VoiceQuestionTemplateSerializer
from patients.models import PatientProfile 

# Initialize services
voice_service = VoiceService()
voice_messaging = VoiceMessagingService()

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def nurse_send_voice_question(request):
    """Nurse sends voice question to patient - FIXED MODEL MISMATCH"""
    
    # Debug
    print("=== REQUEST DEBUG ===")
    print("Content-Type:", request.content_type)
    print("FILES keys:", list(request.FILES.keys()))
    print("POST keys:", list(request.POST.keys()))
    print("====================")
    
    if request.user.user_type != 'NURSE':
        return Response({
            'success': False,
            'error': 'Only nurses can send questions'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get nurse
    try:
        nurse = NurseProfile.objects.get(user=request.user)
    except NurseProfile.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Nurse profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Clean field names
    patient_id = None
    for key in request.POST.keys():
        clean_key = key.strip().replace('"', '').replace(' ', '').lower()
        if 'patient' in clean_key and 'id' in clean_key:
            patient_id = request.POST.get(key)
            break
    
    audio_file = None
    for key in request.FILES.keys():
        clean_key = key.strip().replace('"', '').replace(' ', '').lower()
        if 'audio' in clean_key or 'file' in clean_key:
            audio_file = request.FILES.get(key)
            break
    
    if not patient_id:
        return Response({
            'success': False,
            'error': 'Patient ID is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not audio_file:
        return Response({
            'success': False,
            'error': 'Audio file is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # ===== FIX: Get BOTH patient models =====
    from patients.models import PatientProfile, PatientMedicalRecord
    
    try:
        # Get PatientProfile (your data)
        patient_profile = PatientProfile.objects.get(patient_id=patient_id)
        
        # Get PatientMedicalRecord (what VoiceMessage expects)
        # Assuming there's a relation between them
        patient_medical = PatientMedicalRecord.objects.get(patient=patient_profile)
        
    except PatientProfile.DoesNotExist:
        return Response({
            'success': False,
            'error': f'Patient with ID {patient_id} not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except PatientMedicalRecord.DoesNotExist:
        # Create medical record if it doesn't exist
        patient_medical = PatientMedicalRecord.objects.create(
            patient=patient_profile,
            # Add other required fields with defaults
        )
    
    # Create voice message using PatientMedicalRecord
    from monitoring.voice_services import VoiceMessagingService
    voice_messaging = VoiceMessagingService()
    
    result = voice_messaging.create_voice_message(
        audio_file=audio_file,
        patient=patient_medical,  # ← Pass PatientMedicalRecord, not PatientProfile
        nurse=nurse,
        message_type='QUESTION'
    )
    
    if not result['success']:
        return Response({
            'success': False,
            'error': result.get('error', 'Failed to create voice message')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'success': True,
        'message': 'Voice question sent successfully',
        'data': {
            'message_id': result['voice_message'].voice_message_id,
            'patient_id': patient_id
        }
    }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def patient_voice_reply(request):
    """Patient replies with voice to nurse's question - FIXED"""
    
    # Debug
    print("=== PATIENT REPLY DEBUG ===")
    print("FILES keys:", list(request.FILES.keys()))
    print("POST keys:", list(request.POST.keys()))
    print("Data:", request.data)
    print("===========================")
    
    if request.user.user_type != 'PATIENT':
        return Response({
            'success': False,
            'error': 'Only patients can reply'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get patient
    try:
        patient_profile = PatientProfile.objects.get(user=request.user)
        patient = PatientMedicalRecord.objects.get(patient=patient_profile)
    except (PatientProfile.DoesNotExist, PatientMedicalRecord.DoesNotExist):
        return Response({
            'success': False,
            'error': 'Patient record not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # ===== FIX: Try multiple field names for audio file =====
    audio_file = None
    
    # Check all possible keys in FILES
    for key in request.FILES.keys():
        clean_key = key.strip().replace('"', '').replace(' ', '').lower()
        if 'audio' in clean_key or 'file' in clean_key or 'voice' in clean_key:
            audio_file = request.FILES.get(key)
            print(f"Found audio file with key: {key}")
            break
    
    # If still not found, try request.data (for base64)
    if not audio_file and isinstance(request.data, dict):
        for key in request.data.keys():
            clean_key = key.strip().replace('"', '').lower()
            if 'audio' in clean_key or 'file' in clean_key:
                # Handle base64 encoded audio
                audio_data = request.data.get(key)
                if audio_data and isinstance(audio_data, str):
                    # You'd need to decode base64 here
                    pass
    
    # Get other fields with cleaned names
    voice_message_id = None
    daily_response_id = None
    
    for key in request.data.keys():
        clean_key = key.strip().replace('"', '').replace(' ', '').lower()
        if 'voice' in clean_key and 'message' in clean_key and 'id' in clean_key:
            voice_message_id = request.data.get(key)
        elif 'daily' in clean_key and 'response' in clean_key and 'id' in clean_key:
            daily_response_id = request.data.get(key)
    
    # Also check POST
    for key in request.POST.keys():
        clean_key = key.strip().replace('"', '').replace(' ', '').lower()
        if 'voice' in clean_key and 'message' in clean_key and 'id' in clean_key:
            voice_message_id = request.POST.get(key)
        elif 'daily' in clean_key and 'response' in clean_key and 'id' in clean_key:
            daily_response_id = request.POST.get(key)
    
    if not audio_file:
        return Response({
            'success': False,
            'error': 'Audio file required',
            'debug': {
                'received_files': list(request.FILES.keys()),
                'received_post': list(request.POST.keys()),
                'received_data': list(request.data.keys()) if isinstance(request.data, dict) else []
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Find original message
    original_message = None
    if voice_message_id:
        try:
            original_message = VoiceMessage.objects.get(voice_message_id=voice_message_id)
        except VoiceMessage.DoesNotExist:
            pass
    
    # Find daily response
    daily_response = None
    if daily_response_id:
        try:
            daily_response = DailyResponse.objects.get(response_id=daily_response_id)
        except DailyResponse.DoesNotExist:
            pass
    
    # Create reply
    result = voice_messaging.create_voice_message(
        audio_file=audio_file,
        patient=patient,
        nurse=original_message.nurse if original_message else None,
        message_type='REPLY',
        daily_response=daily_response
    )
    
    if not result['success']:
        return Response({
            'success': False,
            'error': result.get('error', 'Failed to create reply')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    voice_reply = result['voice_message']
    
    # Link to original message
    if original_message:
        voice_reply.parent_message = original_message
        voice_reply.save()
        original_message.status = 'REPLIED'
        original_message.replied_at = timezone.now()
        original_message.save()
    
    return Response({
        'success': True,
        'message': 'Voice reply sent successfully',
        'data': VoiceMessageSerializer(voice_reply, context={'request': request}).data
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_voice_messages(request):
    """Get voice messages based on user type"""
    
    user = request.user
    status_filter = request.GET.get('status')
    
    if user.user_type == 'PATIENT':
        try:
            patient_profile = PatientProfile.objects.get(user=user)
            patient = PatientMedicalRecord.objects.get(patient=patient_profile)
            messages = voice_messaging.get_patient_voice_messages(
                patient.medical_record_id, 
                status_filter
            )
        except:
            messages = []
            
    elif user.user_type == 'NURSE':
        try:
            nurse = NurseProfile.objects.get(user=user)
            messages = voice_messaging.get_nurse_voice_messages(
                nurse.nurse_id,
                status_filter
            )
        except:
            messages = []
            
    elif user.user_type == 'DOCTOR':
        # Doctors can see escalated messages
        messages = VoiceMessage.objects.filter(
            doctor__user=user
        ).order_by('-sent_at')
        if status_filter:
            messages = messages.filter(status=status_filter)
    
    else:
        messages = []
    
    serializer = VoiceMessageSerializer(messages, many=True, context={'request': request})
    
    return Response({
        'success': True,
        'data': serializer.data,
        'total': len(serializer.data)
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_voice_message_read(request, message_id):
    """Mark voice message as read"""
    
    try:
        message = VoiceMessage.objects.get(voice_message_id=message_id)
    except VoiceMessage.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Message not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check permission
    user = request.user
    if user.user_type == 'PATIENT':
        try:
            patient_profile = PatientProfile.objects.get(user=user)
            if message.patient.patient.patient_id != patient_profile.patient_id:
                return Response({'success': False, 'error': 'Permission denied'})
        except:
            return Response({'success': False, 'error': 'Permission denied'})
    
    elif user.user_type == 'NURSE':
        if message.nurse and message.nurse.user != user:
            return Response({'success': False, 'error': 'Permission denied'})
    
    message.mark_read()
    
    return Response({
        'success': True,
        'message': 'Marked as read'
    })

import io
import imageio_ffmpeg
from pydub import AudioSegment
from django.core.files.uploadedfile import InMemoryUploadedFile

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def voice_to_text_api(request):
    """Convert uploaded voice to text - FIXED with MP3 Support"""
    
    # Debug
    print("=== VOICE TO TEXT DEBUG ===")
    print("FILES keys:", list(request.FILES.keys()))
    print("POST keys:", list(request.POST.keys()))
    print("Data keys:", list(request.data.keys()) if isinstance(request.data, dict) else [])
    print("===========================")
    
    # ===== FIX: Try multiple field names =====
    audio_file = None
    
    # Check all possible keys in FILES
    for key in request.FILES.keys():
        clean_key = key.strip().replace('"', '').replace(' ', '').lower()
        if 'audio' in clean_key or 'file' in clean_key or 'voice' in clean_key or 'sound' in clean_key:
            audio_file = request.FILES.get(key)
            print(f"Found audio file with key: {key}")
            break
    
    # Get language
    language = 'en-IN'  # Default
    # ... (your existing language code)
    
    if not audio_file:
        return Response({
            'success': False,
            'error': 'Audio file required',
            'debug': {
                'received_files': list(request.FILES.keys()),
                'hint': 'Send with key "Audio file" in form-data'
            }
        }, status=400)
    
    # ===== MP3 to WAV Conversion with imageio-ffmpeg =====
    file_name = audio_file.name.lower()
    file_content = audio_file.read()
    
    if file_name.endswith('.mp3'):
        print(f"Converting MP3 to WAV: {audio_file.name}")
        
        try:
            # Get FFmpeg path from imageio-ffmpeg
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            AudioSegment.converter = ffmpeg_path
            AudioSegment.ffprobe = ffmpeg_path.replace('ffmpeg.exe', 'ffprobe.exe')
            
            # Convert
            audio = AudioSegment.from_mp3(io.BytesIO(file_content))
            
            wav_io = io.BytesIO()
            audio.export(wav_io, format='wav')
            wav_io.seek(0)
            
            # Create new file
            audio_file = InMemoryUploadedFile(
                wav_io,
                'audio_file',
                audio_file.name.replace('.mp3', '.wav'),
                'audio/wav',
                wav_io.getbuffer().nbytes,
                None
            )
            print("MP3 to WAV conversion successful!")
            
        except Exception as e:
            print(f"Error converting MP3: {str(e)}")
            return Response({
                'success': False,
                'error': 'MP3 conversion failed',
                'debug': {
                    'solution': 'Install FFmpeg: winget install ffmpeg'
                }
            }, status=400)
    
    # Convert speech to text
    result = voice_service.speech_to_text(audio_file, language)
    return Response(result)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def text_to_voice_api(request):
    """Convert text to voice - FIXED"""
    
    # Debug
    print("=== TEXT TO VOICE DEBUG ===")
    print("Content-Type:", request.content_type)
    print("Data:", request.data)
    print("POST:", request.POST)
    print("============================")
    
    # ===== FIX: Try multiple field names for text =====
    text = None
    
    # Check in request.data (for JSON)
    if isinstance(request.data, dict):
        # Try all possible keys
        possible_keys = [
            'text', 'Text', 'TEXT', 
            'message', 'Message', 
            'content', 'Content',
            'input', 'Input',
            'words', 'sentence'
        ]
        
        for key in possible_keys:
            if key in request.data:
                text = request.data[key]
                print(f"Found text with key: {key}")
                break
    
    # Check in request.POST (for form-data)
    if not text:
        for key in request.POST.keys():
            clean_key = key.strip().replace('"', '').lower()
            if clean_key in ['text', 'message', 'content', 'words']:
                text = request.POST.get(key)
                print(f"Found text in POST with key: {key}")
                break
    
    # Check in query params (for GET-like)
    if not text:
        text = request.query_params.get('text') or request.query_params.get('message')
    
    # ===== FIX: Try multiple field names for language =====
    language = 'en'
    
    if isinstance(request.data, dict):
        for key in ['language', 'lang', 'Language', 'LANG']:
            if key in request.data:
                language = request.data[key]
                break
    
    if not text:
        return Response({
            'success': False,
            'error': 'Text required',
            'debug': {
                'received_data': dict(request.data) if isinstance(request.data, dict) else str(request.data),
                'received_post': dict(request.POST) if request.POST else {},
                'hint': 'Send JSON with key "text" or form-data with key "text"'
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Convert text to speech
    result = voice_service.text_to_speech(text, language)
    
    if result['success']:
        return Response({
            'success': True,
            'audio': result['audio'],
            'format': result['format']
        })
    else:
        return Response({
            'success': False,
            'error': result.get('error', 'Conversion failed')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def translate_to_tamil_api(request):
    """Translate English text to Tamil - FIXED"""
    
    # Debug
    print("=== TRANSLATE TO TAMIL DEBUG ===")
    print("Content-Type:", request.content_type)
    print("Data:", request.data)
    print("POST:", request.POST)
    print("================================")
    
    # ===== FIX: Try multiple field names for text =====
    text = None
    
    # Check in request.data (for JSON)
    if isinstance(request.data, dict):
        # Try all possible keys
        possible_keys = [
            'text', 'Text', 'TEXT', 
            'message', 'Message', 
            'content', 'Content',
            'input', 'Input',
            'english', 'English',
            'sentence', 'Sentence'
        ]
        
        for key in possible_keys:
            if key in request.data:
                text = request.data[key]
                print(f"Found text with key: {key}")
                break
    
    # Check in request.POST (for form-data)
    if not text:
        for key in request.POST.keys():
            clean_key = key.strip().replace('"', '').lower()
            if clean_key in ['text', 'message', 'content', 'english', 'sentence']:
                text = request.POST.get(key)
                print(f"Found text in POST with key: {key}")
                break
    
    # Check in query params
    if not text:
        text = request.query_params.get('text') or request.query_params.get('message') or request.query_params.get('english')
        if text:
            print("Found text in query params")
    
    if not text:
        return Response({
            'success': False,
            'error': 'Text required',
            'debug': {
                'received_data': dict(request.data) if isinstance(request.data, dict) else str(request.data),
                'received_post': dict(request.POST) if request.POST else {},
                'query_params': dict(request.query_params)
            },
            'hint': 'Send JSON with key "text" or form-data with key "text"'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Translate
    result = voice_service.translate_to_tamil(text)
    
    return Response(result)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_voice_templates(request):
    """Get voice question templates for nurses - WITH ERROR HANDLING"""
    
    if request.user.user_type != 'NURSE':
        return Response({
            'success': False,
            'error': 'Only nurses can access templates'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # FIX: Proper filter
        templates = VoiceQuestionTemplate.objects.filter(is_active=True)
        
        # Debug count
        count = templates.count()
        print(f"Found {count} active templates")
        
        serializer = VoiceQuestionTemplateSerializer(templates, many=True)
        
        return Response({
            'success': True,
            'count': count,
            'data': serializer.data
        })
        
    except Exception as e:
        print(f"Error in get_voice_templates: {e}")
        
        # Fallback: Try without filter
        try:
            templates = VoiceQuestionTemplate.objects.all()
            serializer = VoiceQuestionTemplateSerializer(templates, many=True)
            return Response({
                'success': True,
                'warning': 'Filter failed, returning all templates',
                'data': serializer.data
            })
        except Exception as e2:
            return Response({
                'success': False,
                'error': f'Database error: {str(e2)}'
            }, status=500)