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
    alert.acknowledged_by = user  
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
from deep_translator import GoogleTranslator  

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def voice_to_text_api(request):
    """Convert voice to text with optional translation"""
    
    # Debug
    print("=== VOICE TO TEXT DEBUG ===")
    print("FILES keys:", list(request.FILES.keys()))
    print("POST keys:", list(request.POST.keys()))
    
    # Get audio file
    audio_file = None
    for key in request.FILES.keys():
        if 'audio' in key.lower() or 'file' in key.lower():
            audio_file = request.FILES.get(key)
            break
    
    if not audio_file:
        return Response({'success': False, 'error': 'Audio file required'}, status=400)
    
    # ===== GET PARAMETERS =====
    # Source language (what language is spoken in audio)
    source_lang = request.POST.get('source_language') or 'ta-IN'  # Default: Tamil
    
    # Target language (what language output should be)
    target_lang = request.POST.get('target_language') or 'en-IN'  # Default: English
    
    # Whether to translate
    translate = request.POST.get('translate', 'true').lower() == 'true'
    
    print(f" Source: {source_lang}, Target: {target_lang}, Translate: {translate}")
    
    # ===== STEP 1: Speech to Text in SOURCE language =====
    # Extract source language code (ta-IN -> ta, en-IN -> en)
    source_code = source_lang.split('-')[0] if '-' in source_lang else source_lang
    
    # Call your STT with source language
    stt_result = voice_service.speech_to_text(audio_file, language=source_lang)
    
    if not stt_result.get('success'):
        return Response(stt_result)
    
    transcribed_text = stt_result['text']
    print(f" Transcribed ({source_code}): {transcribed_text}")
    
    # ===== STEP 2: Translate if needed =====
    if translate and source_code != target_lang.split('-')[0]:
        try:
            # Extract target language code
            target_code = target_lang.split('-')[0] if '-' in target_lang else target_lang
            
            # Translate
            translator = GoogleTranslator(source=source_code, target=target_code)
            translated_text = translator.translate(transcribed_text)
            
            print(f" Translated ({source_code}→{target_code}): {translated_text}")
            
            return Response({
                'success': True,
                'original_text': transcribed_text,
                'original_language': source_lang,
                'text': translated_text,
                'language': target_lang,
                'translated': True
            })
        except Exception as e:
            print(f"Translation error: {e}")
            # Fallback to original text
            return Response({
                'success': True,
                'text': transcribed_text,
                'language': source_lang,
                'translated': False,
                'error': f'Translation failed: {e}'
            })
    else:
        # No translation needed
        return Response({
            'success': True,
            'text': transcribed_text,
            'language': source_lang,
            'translated': False
        })



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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_alert_to_patient(request):
    """Send an alert to a specific patient with notifications"""
    
    from rest_framework import status
    from django.core.mail import send_mail
    from django.conf import settings
    from datetime import datetime
    from notifications.models import Notification, NotificationDelivery
    
    # Only nurses, doctors, and admins can send alerts
    if request.user.user_type not in ['NURSE', 'DOCTOR', 'ADMIN']:
        return Response({
            'success': False,
            'error': 'Permission denied. Only nurses, doctors, and admins can send alerts.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Debug
    print("=== SEND ALERT DEBUG ===")
    print("Content-Type:", request.content_type)
    print("Data:", request.data)
    print("========================")
    
    # Extract data
    patient_id = None
    if isinstance(request.data, dict):
        patient_id = request.data.get('patient_id') or request.data.get('patientId')
    
    # Alert level (priority)
    alert_level = 'MEDIUM'
    possible_level_keys = ['priority', 'level', 'severity', 'alert_level', 'urgent']
    
    if isinstance(request.data, dict):
        for key in possible_level_keys:
            if key in request.data:
                val = request.data[key]
                if isinstance(val, str):
                    val = val.upper()
                allowed_levels = ['LOW', 'MEDIUM', 'HIGH', 'URGENT']
                if val in allowed_levels:
                    alert_level = val
                break
    
    # Title
    title = None
    if isinstance(request.data, dict):
        title = request.data.get('title') or request.data.get('subject')
    
    # Description (message)
    description = None
    if isinstance(request.data, dict):
        description = request.data.get('message') or request.data.get('description') or request.data.get('content')
    
    # Status
    alert_status = 'PENDING'
    if isinstance(request.data, dict):
        alert_status = request.data.get('status', 'PENDING').upper()
        allowed_status = ['PENDING', 'ACKNOWLEDGED', 'RESOLVED', 'ESCALATED']
        if alert_status not in allowed_status:
            alert_status = 'PENDING'
    
    # Send via channels
    send_via = request.data.get('send_via', ['WEBSOCKET'])
    if isinstance(send_via, str):
        send_via = [send_via]
    
    # Action URL (optional)
    action_url = request.data.get('action_url', None)
    
    # Trigger conditions
    trigger_conditions = {}
    if isinstance(request.data, dict):
        trigger_conditions = request.data.get('trigger_conditions', {})
    
    # Validate required fields
    if not patient_id:
        return Response({
            'success': False,
            'error': 'Patient ID is required',
            'debug': {
                'received_data': dict(request.data) if isinstance(request.data, dict) else str(request.data),
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not title:
        return Response({
            'success': False,
            'error': 'Alert title is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not description:
        return Response({
            'success': False,
            'error': 'Alert description/message is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get patient medical record
    try:
        patient_medical = None
        patient_profile = None
        patient_user = None
        
        # Try to find by medical_record_id
        patient_medical = PatientMedicalRecord.objects.filter(medical_record_id=patient_id).first()
        
        if not patient_medical:
            # Try by patient profile ID
            patient_profile = PatientProfile.objects.filter(patient_id=patient_id).first()
            if patient_profile:
                patient_medical = PatientMedicalRecord.objects.filter(patient=patient_profile).first()
                patient_user = patient_profile.user
        
        if not patient_medical:
            # Try by user ID
            if str(patient_id).isdigit():
                try:
                    from accounts.models import User
                    user = User.objects.get(id=int(patient_id))
                    if user.user_type == 'PATIENT':
                        patient_profile = PatientProfile.objects.get(user=user)
                        patient_medical = PatientMedicalRecord.objects.get(patient=patient_profile)
                        patient_user = user
                except:
                    pass
        
        if not patient_medical:
            return Response({
                'success': False,
                'error': f'Patient with ID {patient_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # If patient_user is still None, try to get it
        if not patient_user and patient_medical.patient:
            patient_user = patient_medical.patient.user
            patient_profile = patient_medical.patient
            
    except Exception as e:
        logger.error(f"Error finding patient: {str(e)}")
        return Response({
            'success': False,
            'error': f'Error finding patient: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Create the alert
    try:
        alert = Alert.objects.create(
            patient=patient_medical,
            title=title,
            description=description,
            alert_level=alert_level,
            status=alert_status,
            trigger_conditions=trigger_conditions
        )
        
        # ===== CREATE NOTIFICATION =====
        notifications_sent = {
            'websocket': False,
            'email': False,
            'push': False,
            'sms': False,
            'in_app': False
        }
        
        try:
            # Create the notification record
            notification = Notification.objects.create(
                recipient=patient_user,
                notification_type='ALERT',
                priority=alert_level,
                title=title,
                message=description,
                related_patient=patient_medical,
                related_alert=alert,
                action_url=action_url,
                is_sent=False,
                is_delivered=False,
                metadata={
                    'created_by': request.user.username,
                    'created_by_type': request.user.user_type,
                    'alert_id': alert.alert_id,
                    'alert_level': alert_level,
                    'trigger_conditions': trigger_conditions
                }
            )
            
            logger.info(f"Notification {notification.notification_id} created for patient {patient_id}")
            
            # ===== SEND VIA DIFFERENT CHANNELS =====
            
            # 1. WebSocket (Real-time)
            if 'WEBSOCKET' in send_via or 'websocket' in send_via:
                try:
                    # Create delivery record
                    delivery = NotificationDelivery.objects.create(
                        notification=notification,
                        delivery_method='WEBSOCKET',
                        status='PENDING',
                        channel_name=f'user_{patient_user.id}'
                    )
                    
                    # Try to send via WebSocket
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync
                    
                    channel_layer = get_channel_layer()
                    
                    # Send to user's personal channel
                    group_name = f'user_{patient_user.id}'
                    async_to_sync(channel_layer.group_send)(
                        group_name,
                        {
                            'type': 'send_notification',
                            'notification_id': notification.notification_id,
                            'title': title,
                            'message': description,
                            'priority': alert_level,
                            'notification_type': 'ALERT',
                            'action_url': action_url,
                            'timestamp': datetime.now().isoformat()
                        }
                    )
                    
                    # Update delivery status
                    delivery.status = 'SENT'
                    delivery.sent_at = datetime.now()
                    delivery.save()
                    
                    # Update notification
                    notification.delivered_via_websocket = True
                    notification.websocket_delivered_at = datetime.now()
                    notification.is_sent = True
                    notification.sent_at = datetime.now()
                    notification.save()
                    
                    notifications_sent['websocket'] = True
                    logger.info(f"WebSocket notification sent to user {patient_user.id}")
                    
                except Exception as e:
                    logger.error(f"WebSocket delivery failed: {str(e)}")
                    NotificationDelivery.objects.create(
                        notification=notification,
                        delivery_method='WEBSOCKET',
                        status='FAILED',
                        error_message=str(e),
                        retry_count=1
                    )
            
            # 2. Email
            if 'EMAIL' in send_via or 'email' in send_via:
                try:
                    if patient_user and patient_user.email:
                        # Create delivery record
                        delivery = NotificationDelivery.objects.create(
                            notification=notification,
                            delivery_method='EMAIL',
                            status='PENDING'
                        )
                        
                        # Send email
                        email_subject = f"[{alert_level}] {title}"
                        email_message = f"""
                        Dear {patient_user.get_full_name() or patient_user.username},
                        
                        {description}
                        
                        Alert Details:
                        - Priority: {alert_level}
                        - Type: Alert
                        - Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                        
                        Please log in to your account to view more details.
                        
                        Thank you,
                        Cancer Patient Management System
                        """
                        
                        try:
                            send_mail(
                                subject=email_subject,
                                message=email_message,
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[patient_user.email],
                                fail_silently=True,
                            )
                            
                            delivery.status = 'SENT'
                            delivery.sent_at = datetime.now()
                            delivery.save()
                            
                            notifications_sent['email'] = True
                            logger.info(f"Email sent to {patient_user.email}")
                        except Exception as email_error:
                            delivery.status = 'FAILED'
                            delivery.error_message = str(email_error)
                            delivery.save()
                            logger.warning(f"Email failed: {str(email_error)}")
                    else:
                        logger.warning(f"Patient {patient_id} has no email")
                except Exception as e:
                    logger.error(f"Email delivery error: {str(e)}")
            
            # 3. In-App Notification
            if 'IN_APP' in send_via or 'in_app' in send_via:
                try:
                    delivery = NotificationDelivery.objects.create(
                        notification=notification,
                        delivery_method='IN_APP',
                        status='SENT',
                        sent_at=datetime.now()
                    )
                    notifications_sent['in_app'] = True
                    logger.info("In-app notification created")
                except Exception as e:
                    logger.error(f"In-app delivery error: {str(e)}")
            
            # 4. Push Notification (if configured)
            if 'PUSH' in send_via or 'push' in send_via:
                try:
                    # Check if user has FCM token
                    if hasattr(patient_user, 'fcm_token') and patient_user.fcm_token:
                        # Add your Firebase push notification logic here
                        # This requires Firebase configuration
                        NotificationDelivery.objects.create(
                            notification=notification,
                            delivery_method='PUSH',
                            status='PENDING',
                            channel_name=patient_user.fcm_token
                        )
                        logger.info(f"Push notification would be sent to {patient_user.fcm_token}")
                    else:
                        logger.warning(f"User {patient_user.id} has no FCM token")
                except Exception as e:
                    logger.error(f"Push notification error: {str(e)}")
            
            # 5. SMS (if configured)
            if 'SMS' in send_via or 'sms' in send_via:
                try:
                    if patient_profile and patient_profile.phone:
                        NotificationDelivery.objects.create(
                            notification=notification,
                            delivery_method='SMS',
                            status='PENDING'
                        )
                        logger.info(f"SMS would be sent to {patient_profile.phone}")
                    else:
                        logger.warning(f"Patient {patient_id} has no phone")
                except Exception as e:
                    logger.error(f"SMS error: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
        
        # Return success response
        return Response({
            'success': True,
            'message': f'Alert sent to patient successfully',
            'data': {
                'alert_id': alert.alert_id,
                'title': alert.title,
                'description': alert.description,
                'alert_level': alert.alert_level,
                'status': alert.status,
                'created_at': alert.created_at,
                'trigger_conditions': alert.trigger_conditions,
                'notification': {
                    'id': notification.notification_id if 'notification' in locals() else None,
                    'notifications_sent': notifications_sent
                }
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error creating alert: {str(e)}")
        return Response({
            'success': False,
            'error': f'Failed to create alert: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from notifications.models import Notification, NotificationDelivery, NotificationPreference
from django.utils import timezone

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_bulk_alerts(request):
    """Send alerts to multiple patients at once with notifications"""
    
    from rest_framework import status
    
    if request.user.user_type not in ['NURSE', 'DOCTOR', 'ADMIN']:
        return Response({
            'success': False,
            'error': 'Permission denied'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get data
    patient_ids = request.data.get('patient_ids', [])
    title = request.data.get('title')
    message = request.data.get('message')
    alert_level = request.data.get('priority', 'MEDIUM')  # Changed to alert_level
    send_via = request.data.get('send_via', ['WEBSOCKET', 'IN_APP'])
    action_url = request.data.get('action_url', None)
    
    if not patient_ids or not isinstance(patient_ids, list):
        return Response({
            'success': False,
            'error': 'List of patient IDs is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not title or not message:
        return Response({
            'success': False,
            'error': 'Title and message are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Track results
    successful = []
    failed = []
    notifications_created = []
    
    for patient_id in patient_ids:
        try:
            # Find patient
            patient_medical = None
            patient_user = None
            patient_profile = None
            
            # Try to find by medical_record_id
            patient_medical = PatientMedicalRecord.objects.filter(medical_record_id=patient_id).first()
            
            if not patient_medical:
                patient_profile = PatientProfile.objects.filter(patient_id=patient_id).first()
                if patient_profile:
                    patient_medical = PatientMedicalRecord.objects.filter(patient=patient_profile).first()
                    patient_user = patient_profile.user
            
            if not patient_medical:
                failed.append({'id': patient_id, 'reason': 'Patient not found'})
                continue
            
            # Get user
            if not patient_user and patient_medical.patient:
                patient_user = patient_medical.patient.user
                patient_profile = patient_medical.patient
            
            if not patient_user:
                failed.append({'id': patient_id, 'reason': 'User not found'})
                continue
            
            # Create alert in monitoring
            alert = Alert.objects.create(
                patient=patient_medical,
                title=title,
                description=message,
                alert_level=alert_level,
                status='PENDING',
                trigger_conditions={'bulk_send': True, 'created_by': request.user.username}
            )
            
            # Create notification
            notification = Notification.objects.create(
                recipient=patient_user,
                notification_type='ALERT',
                priority=alert_level,
                title=title,
                message=message,
                related_patient=patient_medical,
                related_alert=alert,
                action_url=action_url,
                is_sent=False,
                is_delivered=False,
                metadata={
                    'created_by': request.user.username,
                    'created_by_type': request.user.user_type,
                    'bulk_send': True,
                    'alert_id': alert.alert_id
                }
            )
            
            notifications_created.append({
                'patient_id': patient_id,
                'notification_id': notification.notification_id,
                'alert_id': alert.alert_id
            })
            
            # Send via different channels
            channel_results = {}
            
            # WebSocket
            if 'WEBSOCKET' in send_via:
                try:
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync
                    
                    channel_layer = get_channel_layer()
                    group_name = f'user_{patient_user.id}'
                    
                    async_to_sync(channel_layer.group_send)(
                        group_name,
                        {
                            'type': 'send_notification',
                            'notification_id': notification.notification_id,
                            'title': title,
                            'message': message,
                            'priority': alert_level,
                            'notification_type': 'ALERT',
                            'action_url': action_url,
                            'timestamp': timezone.now().isoformat()
                        }
                    )
                    
                    # Update delivery
                    NotificationDelivery.objects.create(
                        notification=notification,
                        delivery_method='WEBSOCKET',
                        status='SENT',
                        sent_at=timezone.now(),
                        channel_name=group_name
                    )
                    
                    notification.delivered_via_websocket = True
                    notification.websocket_delivered_at = timezone.now()
                    notification.is_sent = True
                    notification.sent_at = timezone.now()
                    notification.save()
                    
                    channel_results['websocket'] = True
                    
                except Exception as e:
                    logger.error(f"WebSocket failed for patient {patient_id}: {str(e)}")
                    NotificationDelivery.objects.create(
                        notification=notification,
                        delivery_method='WEBSOCKET',
                        status='FAILED',
                        error_message=str(e)
                    )
                    channel_results['websocket'] = False
            
            # Email
            if 'EMAIL' in send_via:
                try:
                    from django.core.mail import send_mail
                    from django.conf import settings
                    
                    if patient_user.email:
                        email_subject = f"[{alert_level}] {title}"
                        email_message = f"""
                        Dear {patient_user.get_full_name() or patient_user.username},
                        
                        {message}
                        
                        Alert Details:
                        - Priority: {alert_level}
                        - Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
                        
                        Please log in to your account to view more details.
                        
                        Thank you,
                        Cancer Patient Management System
                        """
                        
                        send_mail(
                            subject=email_subject,
                            message=email_message,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[patient_user.email],
                            fail_silently=True,
                        )
                        
                        NotificationDelivery.objects.create(
                            notification=notification,
                            delivery_method='EMAIL',
                            status='SENT',
                            sent_at=timezone.now()
                        )
                        
                        channel_results['email'] = True
                    else:
                        channel_results['email'] = False
                        
                except Exception as e:
                    logger.error(f"Email failed for patient {patient_id}: {str(e)}")
                    channel_results['email'] = False
            
            # In-App
            if 'IN_APP' in send_via:
                NotificationDelivery.objects.create(
                    notification=notification,
                    delivery_method='IN_APP',
                    status='SENT',
                    sent_at=timezone.now()
                )
                channel_results['in_app'] = True
            
            successful.append({
                'id': patient_id,
                'notification_id': notification.notification_id,
                'alert_id': alert.alert_id,
                'channels': channel_results
            })
            
        except Exception as e:
            logger.error(f"Error sending alert to patient {patient_id}: {str(e)}")
            failed.append({'id': patient_id, 'reason': str(e)})
    
    logger.info(f"Bulk alerts sent by {request.user.username}: {len(successful)} successful, {len(failed)} failed")
    
    return Response({
        'success': True,
        'message': f'Alerts sent to {len(successful)} patients',
        'data': {
            'successful': successful,
            'failed': failed,
            'notifications_created': notifications_created,
            'total_notifications': len(notifications_created)
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_patient_alerts(request, patient_id):
    """Get all alerts for a specific patient with notifications"""
    
    user = request.user
    
    # For PATIENT users, find their actual patient_id from database
    if user.user_type == 'PATIENT':
        try:
            # Get the patient profile for this user
            patient_profile = PatientProfile.objects.get(user=user)
            actual_patient_id = patient_profile.patient_id
            
            # Check if the requested patient_id matches their actual patient_id
            if int(patient_id) != int(actual_patient_id):
                return Response({
                    'success': False,
                    'error': f'You can only view your own alerts. Your patient_id is {actual_patient_id}',
                    'your_patient_id': actual_patient_id,
                    'requested_id': patient_id
                }, status=status.HTTP_403_FORBIDDEN)
                
        except PatientProfile.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Patient profile not found for this user'
            }, status=status.HTTP_404_NOT_FOUND)
    
    # For other roles (NURSE, DOCTOR, ADMIN), allow access
    elif user.user_type not in ['NURSE', 'DOCTOR', 'ADMIN']:
        return Response({
            'success': False,
            'error': 'Permission denied'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Find patient medical record
    try:
        patient_medical = None
        patient_user = None
        
        # First try: patient_id might be the actual patient_id from PatientProfile
        patient_profile = PatientProfile.objects.filter(patient_id=patient_id).first()
        
        if patient_profile:
            patient_medical = PatientMedicalRecord.objects.filter(patient=patient_profile).first()
            patient_user = patient_profile.user
        
        # Second try: patient_id might be medical_record_id
        if not patient_medical:
            patient_medical = PatientMedicalRecord.objects.filter(medical_record_id=patient_id).first()
            if patient_medical and patient_medical.patient:
                patient_user = patient_medical.patient.user
        
        if not patient_medical:
            return Response({
                'success': False,
                'error': f'Patient not found with identifier: {patient_id}'
            }, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Get alerts - FIXED: Use filter normally
    alerts = Alert.objects.filter(patient=patient_medical).order_by('-created_at')
    
    # Get notifications - FIXED: Avoid complex filtering
    # Get all notifications first, then filter in Python
    all_notifications = Notification.objects.filter(
        recipient=patient_user,
        notification_type='ALERT'
    ).select_related('related_alert').order_by('-created_at')
    
    # Apply filters in Python instead of database
    notifications = []
    for notif in all_notifications:
        notifications.append(notif)
    
    # Optional filters - apply in Python
    status_filter = request.GET.get('status')
    if status_filter:
        if status_filter == 'READ':
            alerts = [a for a in alerts if a.status != 'PENDING']
            notifications = [n for n in notifications if n.is_read]
        elif status_filter == 'UNREAD':
            alerts = [a for a in alerts if a.status == 'PENDING']
            notifications = [n for n in notifications if not n.is_read]
    
    alert_level_filter = request.GET.get('priority')
    if alert_level_filter:
        alerts = [a for a in alerts if a.alert_level == alert_level_filter]
        notifications = [n for n in notifications if n.priority == alert_level_filter]
    
    # If patient is viewing, mark as read automatically
    if user.user_type == 'PATIENT':
        # Update alerts - FIXED: Update one by one
        for alert in alerts:
            if hasattr(alert, 'status') and alert.status == 'PENDING':
                alert.status = 'DELIVERED'
                alert.acknowledged_at = timezone.now()
                alert.save()
        
        # Update notifications - FIXED: Update one by one
        for notification in notifications:
            if not notification.is_read:
                notification.is_read = True
                notification.read_at = timezone.now()
                notification.save()
                
                # Update delivery status
                try:
                    delivery = NotificationDelivery.objects.filter(
                        notification=notification,
                        delivery_method='IN_APP'
                    ).first()
                    if delivery:
                        delivery.status = 'DELIVERED'
                        delivery.delivered_at = timezone.now()
                        delivery.save()
                except:
                    pass
    
    # Combine data
    combined_data = []
    
    # Add alerts
    for alert in alerts:
        # Find related notification
        related_notification = None
        for notif in notifications:
            if notif.related_alert and notif.related_alert.alert_id == alert.alert_id:
                related_notification = notif
                break
        
        combined_data.append({
            'type': 'alert',
            'id': alert.alert_id,
            'title': alert.title,
            'message': alert.description,
            'priority': alert.alert_level,
            'status': alert.status,
            'created_at': alert.created_at,
            'read_at': alert.acknowledged_at,
            'notification_id': related_notification.notification_id if related_notification else None,
            'is_read': related_notification.is_read if related_notification else (alert.status != 'PENDING'),
            'action_url': related_notification.action_url if related_notification else None
        })
    
    # Add notifications without alerts
    for notification in notifications:
        if not notification.related_alert:
            combined_data.append({
                'type': 'notification',
                'id': notification.notification_id,
                'title': notification.title,
                'message': notification.message,
                'priority': notification.priority,
                'status': 'READ' if notification.is_read else 'SENT',
                'created_at': notification.created_at,
                'read_at': notification.read_at,
                'notification_id': notification.notification_id,
                'is_read': notification.is_read,
                'action_url': notification.action_url
            })
    
    # Sort by created_at
    combined_data.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Calculate counts
    total_unread = len([x for x in combined_data if not x.get('is_read', False)])
    alerts_count = len([x for x in combined_data if x['type'] == 'alert'])
    notifications_count = len([x for x in combined_data if x['type'] == 'notification'])
    
    return Response({
        'success': True,
        'data': combined_data,
        'summary': {
            'total': len(combined_data),
            'unread': total_unread,
            'alerts_count': alerts_count,
            'notifications_count': notifications_count
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_alert_read(request, alert_id):
    """Mark an alert as read by patient"""
    
    user = request.user
    
    try:
        alert = Alert.objects.select_related('patient__patient').get(alert_id=alert_id)
    except Alert.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Alert not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check permission for PATIENT
    if user.user_type == 'PATIENT':
        try:
            patient_profile = PatientProfile.objects.get(user=user)
            alert_patient_id = alert.patient.patient.patient_id
            
            # This check is CORRECT - it prevents unauthorized access
            if alert_patient_id != patient_profile.patient_id:
                return Response({
                    'success': False,
                    'error': f'This alert does not belong to you'
                }, status=status.HTTP_403_FORBIDDEN)
                
        except PatientProfile.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Patient profile not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    # For NURSE, DOCTOR, ADMIN - allow access
    elif user.user_type not in ['NURSE', 'DOCTOR', 'ADMIN']:
        return Response({
            'success': False,
            'error': 'Permission denied'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Mark alert as read
    alert.status = 'READ'
    alert.acknowledged_at = timezone.now()
    alert.save()
    
    # Update notification if exists
    try:
        notification = Notification.objects.filter(related_alert=alert).first()
        if notification:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
    except Exception as e:
        logger.warning(f"Error updating notification: {e}")
    
    return Response({
        'success': True,
        'message': 'Alert marked as read',
        'data': {
            'alert_id': alert.alert_id,
            'status': alert.status,
            'acknowledged_at': alert.acknowledged_at
        }
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_alert(request, alert_id):
    """Delete an alert and its related notifications (admin only)"""
    
    if request.user.user_type != 'ADMIN':
        return Response({
            'success': False,
            'error': 'Only admins can delete alerts'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        alert = Alert.objects.get(alert_id=alert_id)
        
        # Delete related notifications
        notifications = Notification.objects.filter(related_alert=alert)
        notifications_count = notifications.count()
        notifications.delete()
        
        # Delete alert
        alert.delete()
        
        logger.info(f"Alert {alert_id} and {notifications_count} notifications deleted by admin {request.user.username}")
        
        return Response({
            'success': True,
            'message': f'Alert and {notifications_count} notifications deleted successfully',
            'data': {
                'alert_id': alert_id,
                'deleted_notifications': notifications_count
            }
        })
        
    except Alert.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Alert not found'
        }, status=status.HTTP_404_NOT_FOUND)

