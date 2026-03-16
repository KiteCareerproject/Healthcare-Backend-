from rest_framework import status
from django.db import models
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import os
from datetime import datetime
from .models import QuestionCategory, Question, QuestionnaireAssignment, AssignedQuestion
from monitoring.models import DailyResponse, QuestionResponse, Alert, PatientNote
from patients.models import PatientMedicalRecord, PatientProfile
from accounts.models import NurseProfile, PatientProfile, User
from accounts.utils import handle_errors, APIError
from .serializers import (
    QuestionCategorySerializer, QuestionSerializer,
    QuestionnaireAssignmentSerializer, CreateQuestionSerializer,
    CreateAssignmentSerializer
)
import logging

logger = logging.getLogger(__name__)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def question_list(request):
    """List all questions or create new question"""
    user = request.user
    
    if request.method == 'GET':
        # Get all questions and filter in Python
        all_questions = Question.objects.all()
        
        # Manual filtering in Python
        questions = [q for q in all_questions if q.is_active]
        
        serializer = QuestionSerializer(questions, many=True)
        return Response({
            'success': True,
            'count': len(questions),
            'data': serializer.data
        })
    
    elif request.method == 'POST':
        # Permission check
        if user.user_type not in ['ADMIN', 'NURSE']:
            raise APIError(
                "Only admins and nurses can create questions",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Validate input
        serializer = CreateQuestionSerializer(data=request.data)
        if not serializer.is_valid():
            raise APIError(
                "Validation error",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        # Get category if provided
        category = None
        if data.get('category_id'):
            try:
                category = QuestionCategory.objects.get(category_id=data['category_id'])
            except QuestionCategory.DoesNotExist:
                logger.warning(f"Category {data['category_id']} not found")
        
        # Create question with all fields
        question = Question.objects.create(
            text=data['text'],
            question_type=data['question_type'],
            category=category,
            options=data.get('options', []),
            scale_min=data.get('scale_min', 1),
            scale_max=data.get('scale_max', 10),
            default_frequency=data.get('default_frequency', 'DAILY'),
            help_text=data.get('help_text', ''),
            is_active=True  # New questions are active by default
        )
        
        logger.info(f"Question created by {user.username}: {question.question_id}")
        
        # Return created question
        response_serializer = QuestionSerializer(question)
        return Response({
            'success': True,
            'message': 'Question created successfully',
            'data': response_serializer.data
        }, status=status.HTTP_201_CREATED)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def question_detail(request, question_id):
    """Get, update or delete question"""
    user = request.user
    
    try:
        question = Question.objects.get(question_id=question_id)
    except Question.DoesNotExist:
        raise APIError("Question not found", status_code=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        serializer = QuestionSerializer(question)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    elif request.method == 'PUT':
        if user.user_type not in ['ADMIN', 'NURSE']:
            raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
        data = request.data
        
        if 'text' in data:
            question.text = data['text']
        if 'is_active' in data:
            question.is_active = data['is_active']
        if 'options' in data:
            question.options = data['options']
        
        question.save()
        
        logger.info(f"Question {question_id} updated")
        
        serializer = QuestionSerializer(question)
        return Response({
            'success': True,
            'message': 'Question updated successfully',
            'data': serializer.data
        })
    
    elif request.method == 'DELETE':
        if user.user_type != 'ADMIN':
            raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
        question.is_active = False
        question.save()
        
        logger.info(f"Question {question_id} deactivated (soft delete)")
        
        return Response({
            'success': True,
            'message': 'Question deleted successfully'
        })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_categories(request):
    """Get all question categories"""
    categories = QuestionCategory.objects.all()
    serializer = QuestionCategorySerializer(categories, many=True)
    return Response({
        'success': True,
        'data': serializer.data
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def create_assignment(request):
    """Create questionnaire assignment for patient"""
    user = request.user
    
    if user.user_type not in ['ADMIN', 'NURSE']:
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    serializer = CreateAssignmentSerializer(data=request.data)
    if not serializer.is_valid():
        raise APIError("Validation error", errors=serializer.errors)
    
    data = serializer.validated_data
    
    # STEP 1: Get the patient profile
    try:
        patient_profile = PatientProfile.objects.get(patient_id=data['patient_id'])
    except PatientProfile.DoesNotExist:
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # STEP 2: Get or create the medical record for this patient
    try:
        # Try to get existing medical record
        patient_medical_record = PatientMedicalRecord.objects.get(patient=patient_profile)
    except PatientMedicalRecord.DoesNotExist:
        patient_medical_record = PatientMedicalRecord.objects.create(
            patient=patient_profile,
        )
        logger.info(f"Created medical record for patient {data['patient_id']}")
    
    # STEP 3: Get nurse
    try:
        if user.user_type == 'NURSE':
            nurse = NurseProfile.objects.get(user=user)
        else:
            # For ADMIN, get first nurse or allow assignment without nurse
            nurse = NurseProfile.objects.first()
            if not nurse:
                nurse = None
    except NurseProfile.DoesNotExist:
        raise APIError("Nurse profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # STEP 4: Create assignment with medical record
    assignment = QuestionnaireAssignment.objects.create(
        patient=patient_medical_record,  # Use medical record, NOT patient profile
        frequency=data['frequency'],
        start_date=data['start_date'],
        end_date=data.get('end_date'),
        assigned_by=nurse  # This might be None if no nurse found
    )
    
    # STEP 5: Add questions
    questions_added = 0
    for idx, question_id in enumerate(data['question_ids']):
        try:
            question = Question.objects.get(question_id=question_id)
            
            # Check if active
            if not question.is_active:
                logger.warning(f"Question {question_id} is not active, skipping")
                continue
                
            AssignedQuestion.objects.create(
                questionnaire_assignment=assignment,
                question=question,
                order=idx + 1,
                is_mandatory=True
            )
            questions_added += 1
        except Question.DoesNotExist:
            logger.warning(f"Question {question_id} not found, skipping")
            continue
    
    if questions_added == 0:
        # If no questions were added, delete the assignment
        assignment.delete()
        raise APIError("No valid questions provided", status_code=status.HTTP_400_BAD_REQUEST)
    
    logger.info(f"Questionnaire assignment created for patient {data['patient_id']} with {questions_added} questions")
    
    # STEP 6: Return response
    response_serializer = QuestionnaireAssignmentSerializer(assignment)
    return Response({
        'success': True,
        'message': 'Assignment created successfully',
        'data': response_serializer.data
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_patient_assignments(request, patient_id):
    """Get all assignments for a patient"""
    try:
        # Use patient_id instead of user_id
        patient = PatientMedicalRecord.objects.get(patient_id=patient_id)
        
    except PatientMedicalRecord.DoesNotExist:
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
    
    assignments = QuestionnaireAssignment.objects.filter(patient=patient)
    serializer = QuestionnaireAssignmentSerializer(assignments, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def submit_questionnaire_responses(request):
    """API for patients to submit their questionnaire responses"""
    
    user = request.user
    
    # Only patients can submit
    if user.user_type != 'PATIENT':
        raise APIError("Only patients can submit questionnaire responses", 
                      status_code=status.HTTP_403_FORBIDDEN)
    
    # Debug
    print("=== SUBMIT QUESTIONNAIRE DEBUG ===")
    print("Content-Type:", request.content_type)
    print("Data:", request.data)
    print("===================================")
    
    # Initialize errors list at the beginning
    errors = []
    
    # Get patient profile and medical record
    try:
        patient_profile = PatientProfile.objects.get(user=user)
        patient_medical = PatientMedicalRecord.objects.get(patient=patient_profile)
    except PatientProfile.DoesNotExist:
        raise APIError("Patient profile not found", status_code=status.HTTP_404_NOT_FOUND)
    except PatientMedicalRecord.DoesNotExist:
        # Auto-create medical record if missing
        patient_medical = PatientMedicalRecord.objects.create(patient=patient_profile)
        logger.info(f"Created medical record for patient {patient_profile.patient_id}")
    
    # Get data from request - try multiple field names
    response_id = None
    responses_data = None
    assignment_id = None
    patient_id_from_request = None
    
    # Check different possible field names in request
    if isinstance(request.data, dict):
        # Get patient_id if sent (optional)
        patient_id_from_request = request.data.get('patient_id')
        
        # Response ID (if continuing an existing response)
        for key in ['response_id', 'responseId', 'daily_response_id', 'dailyResponseId']:
            if key in request.data:
                response_id = request.data[key]
                break
        
        # Assignment ID (if starting new)
        for key in ['assignment_id', 'assignmentId', 'assignment']:
            if key in request.data:
                assignment_id = request.data[key]
                break
        
        # Responses array - try different keys
        if 'answers' in request.data:
            responses_data = request.data['answers']
            print("Found answers directly in 'answers' key")
        elif 'responses' in request.data:
            responses_data = request.data['responses']
            print("Found responses in 'responses' key")
        else:
            for key in ['data', 'question_responses']:
                if key in request.data:
                    responses_data = request.data[key]
                    print(f"Found responses in '{key}' key")
                    break
    
    if not responses_data:
        # Try to find any list in the data that might contain responses
        if isinstance(request.data, dict):
            for key, value in request.data.items():
                if isinstance(value, list) and len(value) > 0:
                    if isinstance(value[0], dict) and any(k in value[0] for k in ['answer', 'question_id']):
                        responses_data = value
                        print(f"Found responses in key: {key}")
                        break
        
        if not responses_data:
            raise APIError(
                "No responses provided. Please include 'responses' or 'answers' array in request.", 
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    print(f"Total responses found: {len(responses_data)}")
    
    # If assignment_id is not provided, try to get from patient's active assignments
    if not assignment_id and not response_id:
        today = timezone.now().date()
        active_assignments = QuestionnaireAssignment.objects.filter(
            patient=patient_medical,
            status='ACTIVE',
            start_date__lte=today
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=today)
        )
        
        if active_assignments.exists():
            assignment = active_assignments.first()
            assignment_id = assignment.assignment_id
            print(f"Auto-selected assignment: {assignment_id}")
        else:
            raise APIError("No active assignment found. Please provide assignment_id.", 
                          status_code=status.HTTP_400_BAD_REQUEST)
    
    today = timezone.now().date()
    
    # CASE 1: Using existing response_id (continuing a saved response)
    if response_id:
        try:
            daily_response = DailyResponse.objects.get(
                response_id=response_id,
                patient=patient_medical
            )
        except DailyResponse.DoesNotExist:
            raise APIError("Response not found", status_code=status.HTTP_404_NOT_FOUND)
        
        if daily_response.is_completed:
            raise APIError("This questionnaire has already been completed", 
                          status_code=status.HTTP_400_BAD_REQUEST)
        
        assignment = daily_response.questionnaire_assignment
    
    # CASE 2: Using assignment_id (starting new)
    elif assignment_id:
        try:
            assignment = QuestionnaireAssignment.objects.get(
                assignment_id=assignment_id,
                patient=patient_medical,
                status='ACTIVE'
            )
        except QuestionnaireAssignment.DoesNotExist:
            raise APIError("Assignment not found or not active", 
                          status_code=status.HTTP_404_NOT_FOUND)
        
        # Check if assignment is within date range
        if assignment.start_date > today:
            raise APIError("This assignment is not yet active", 
                          status_code=status.HTTP_400_BAD_REQUEST)
        
        if assignment.end_date and assignment.end_date < today:
            raise APIError("This assignment has expired", 
                          status_code=status.HTTP_400_BAD_REQUEST)
        
        # Check if already completed today
        existing_responses = list(DailyResponse.objects.filter(
            patient=patient_medical,
            questionnaire_assignment=assignment,
            response_date=today
        ))
        
        completed_exists = False
        for resp in existing_responses:
            if resp.is_completed:
                completed_exists = True
                break
        
        if completed_exists:
            raise APIError("You have already completed this assignment today", 
                          status_code=status.HTTP_400_BAD_REQUEST)
        
        # Create or get existing incomplete response
        if existing_responses:
            daily_response = existing_responses[0]
        else:
            daily_response = DailyResponse.objects.create(
                patient=patient_medical,
                response_date=today,
                questionnaire_assignment=assignment,
                is_completed=False
            )
    
    else:
        # CASE 3: No ID provided - try to find active assignment for today
        active_assignments = QuestionnaireAssignment.objects.filter(
            patient=patient_medical,
            status='ACTIVE',
            start_date__lte=today
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=today)
        )
        
        if not active_assignments.exists():
            raise APIError("No active assignment found for today", 
                          status_code=status.HTTP_404_NOT_FOUND)
        
        # Use the first active assignment
        assignment = active_assignments.first()
        
        # Check if already completed today
        existing_responses = list(DailyResponse.objects.filter(
            patient=patient_medical,
            questionnaire_assignment=assignment,
            response_date=today
        ))
        
        completed_exists = False
        for resp in existing_responses:
            if resp.is_completed:
                completed_exists = True
                break
        
        if completed_exists:
            raise APIError("You have already completed your questionnaire today", 
                          status_code=status.HTTP_400_BAD_REQUEST)
        
        # Create or get existing incomplete response
        if existing_responses:
            daily_response = existing_responses[0]
        else:
            daily_response = DailyResponse.objects.create(
                patient=patient_medical,
                response_date=today,
                questionnaire_assignment=assignment,
                is_completed=False
            )
    
    # Get all assigned questions in order
    assigned_questions_list = list(AssignedQuestion.objects.filter(
        questionnaire_assignment=assignment
    ).select_related('question').order_by('order'))
    
    if not assigned_questions_list:
        raise APIError("No questions found for this assignment", 
                      status_code=status.HTTP_404_NOT_FOUND)
    
    print(f"Found {len(assigned_questions_list)} questions in assignment")
    
    # Create mapping by question_id AND assigned_question_id
    assigned_by_question_id = {}
    assigned_by_id = {}
    
    for aq in assigned_questions_list:
        assigned_by_id[aq.assigned_question_id] = aq
        if aq.question:
            assigned_by_question_id[aq.question.question_id] = aq
            print(f"Question {aq.question.question_id} -> Assigned {aq.assigned_question_id}")
    
    # Process responses
    processed_responses = []
    
    for idx, resp in enumerate(responses_data):
        if isinstance(resp, dict):
            # Try to get question identifier
            question_id = None
            assigned_question_id = None
            
            # Check for various ID fields
            for key in ['assigned_question_id', 'aq_id']:
                if key in resp and resp[key]:
                    assigned_question_id = resp[key]
                    break
            
            for key in ['question_id', 'q_id', 'id']:
                if key in resp and resp[key]:
                    question_id = resp[key]
                    break
            
            # Get answer
            answer = None
            for key in ['answer', 'response', 'value', 'ans']:
                if key in resp:
                    answer = resp[key]
                    break
            
            if answer is None:
                print(f"Warning: No answer found in response {idx}")
                continue
            
            # Find the assigned question
            assigned_question = None
            if assigned_question_id:
                assigned_question = assigned_by_id.get(assigned_question_id)
                if assigned_question:
                    print(f"Found by assigned_question_id: {assigned_question_id}")
            
            if not assigned_question and question_id:
                assigned_question = assigned_by_question_id.get(question_id)
                if assigned_question:
                    print(f"Found by question_id: {question_id} -> assigned: {assigned_question.assigned_question_id}")
            
            if assigned_question:
                processed_responses.append({
                    'assigned_question_id': assigned_question.assigned_question_id,
                    'answer': answer,
                    'original_index': idx
                })
            else:
                error_msg = f"Question ID {question_id or assigned_question_id} not found in assignment"
                print(error_msg)
                errors.append({
                    "index": idx,
                    "error": error_msg,
                    "received": resp
                })
        else:
            # If it's not a dict, assume it's a list of answers in order
            if idx < len(assigned_questions_list):
                processed_responses.append({
                    'assigned_question_id': assigned_questions_list[idx].assigned_question_id,
                    'answer': resp,
                    'original_index': idx
                })
                print(f"Using order {idx} for answer: {resp}")
    
    if not processed_responses:
        raise APIError(
            "No valid responses after processing", 
            errors=errors[:10],
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    print(f"Processed {len(processed_responses)} valid responses")
    
    # Process each response
    saved_responses = []
    
    # Get all assigned questions as dictionary for quick lookup
    all_assigned_questions = {
        aq.assigned_question_id: aq 
        for aq in assigned_questions_list
    }
    
    for item in processed_responses:
        assigned_question_id = item['assigned_question_id']
        answer = item['answer']
        original_index = item.get('original_index', 0)
        
        # Get the assigned question
        assigned_question = all_assigned_questions.get(assigned_question_id)
        
        if not assigned_question:
            errors.append({
                "index": original_index,
                "assigned_question_id": assigned_question_id,
                "error": "Question not found in this assignment"
            })
            continue
        
        question = assigned_question.question
        
        # Handle empty answers
        if answer is None or (isinstance(answer, str) and answer.strip() == ''):
            if assigned_question.is_mandatory:
                errors.append({
                    "index": original_index,
                    "assigned_question_id": assigned_question_id,
                    "question": question.text[:50],
                    "error": "Mandatory question cannot be empty",
                    "received_answer": answer
                })
                continue
            else:
                # Skip optional questions with no answer
                continue
        
        # Validate answer based on question type
        is_valid, error_msg = validate_submit_answer(question, answer)
        if not is_valid:
            errors.append({
                "index": original_index,
                "assigned_question_id": assigned_question_id,
                "question": question.text[:50],
                "error": error_msg,
                "received_answer": answer
            })
            continue
        
        # Save response
        try:
            # Check if response already exists
            existing_response = QuestionResponse.objects.filter(
                daily_response=daily_response,
                assigned_question=assigned_question
            ).first()
            
            response_data = {
                'daily_response': daily_response,
                'assigned_question': assigned_question
            }
            
            # Add the appropriate field based on question type
            if question.question_type == 'YES_NO':
                # Convert various formats to boolean
                if isinstance(answer, bool):
                    bool_val = answer
                elif isinstance(answer, str):
                    bool_val = answer.lower() in ['yes', 'true', 'y', '1', 'ja', 'haan', 'ஆம்']
                elif isinstance(answer, int):
                    bool_val = answer == 1
                else:
                    bool_val = bool(answer)
                response_data['yes_no_response'] = bool_val
                
            elif question.question_type == 'MULTIPLE_CHOICE':
                response_data['multiple_choice_response'] = str(answer)
                
            elif question.question_type == 'SCALE':
                try:
                    val = int(answer)
                    # Ensure within range
                    if question.scale_min and val < question.scale_min:
                        val = question.scale_min
                    if question.scale_max and val > question.scale_max:
                        val = question.scale_max
                    response_data['scale_response'] = val
                except (ValueError, TypeError):
                    response_data['scale_response'] = question.scale_min or 0
                    
            elif question.question_type == 'TEXT':
                response_data['text_response'] = str(answer)
            
            if existing_response:
                # Update existing
                for key, value in response_data.items():
                    if key not in ['daily_response', 'assigned_question']:
                        setattr(existing_response, key, value)
                existing_response.save()
                question_response = existing_response
            else:
                # Create new
                question_response = QuestionResponse.objects.create(**response_data)
            
            saved_responses.append({
                'assigned_question_id': assigned_question_id,
                'question': question.text[:50],
                'answer': get_submit_answer_text(question_response),
                'status': 'saved'
            })
            
        except Exception as e:
            logger.error(f"Error saving response: {str(e)}")
            errors.append({
                "index": original_index,
                "assigned_question_id": assigned_question_id,
                "error": f"Database error: {str(e)[:100]}"
            })
    
    # If there are errors but some responses saved, return partial success
    if errors and saved_responses:
        return Response({
            'success': False,
            'message': 'Some responses could not be saved',
            'errors': errors[:10],
            'data': {
                'response_id': daily_response.response_id,
                'saved_count': len(saved_responses),
                'saved_responses': saved_responses[:5]
            }
        }, status=status.HTTP_207_MULTI_STATUS)
    
    # If all responses failed
    if not saved_responses:
        raise APIError(
            "Failed to save any responses",
            errors=errors[:10],
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if all mandatory questions are answered
    mandatory_questions = [aq for aq in assigned_questions_list if aq.is_mandatory]
    mandatory_question_ids = [aq.assigned_question_id for aq in mandatory_questions]
    
    answered_questions = [r['assigned_question_id'] for r in saved_responses]
    missing_mandatory = set(mandatory_question_ids) - set(answered_questions)
    
    if missing_mandatory:
        # Don't mark as completed yet
        return Response({
            'success': True,
            'message': 'Responses saved. Please answer all mandatory questions.',
            'data': {
                'response_id': daily_response.response_id,
                'saved_count': len(saved_responses),
                'total_mandatory': len(mandatory_question_ids),
                'answered_mandatory': len(set(answered_questions) & set(mandatory_question_ids)),
                'missing_mandatory': list(missing_mandatory)[:5],
                'is_completed': False
            }
        })
    
    # Mark as completed
    daily_response.is_completed = True
    daily_response.completed_at = timezone.now()
    daily_response.save(update_fields=['is_completed', 'completed_at'])
    
    # Check for alerts based on responses
    alerts = []
    try:
        from .alerts import check_response_alerts
        full_responses = QuestionResponse.objects.filter(daily_response=daily_response)
        alerts = check_response_alerts(daily_response, full_responses)
    except ImportError as e:
        logger.warning(f"Alert checking function not available: {e}")
    
    logger.info(f"Questionnaire {daily_response.response_id} completed by patient {patient_profile.patient_id}")
    
    # Format response for output
    response_summary = []
    for qr in QuestionResponse.objects.filter(daily_response=daily_response).select_related('assigned_question__question')[:5]:
        q = qr.assigned_question.question
        response_summary.append({
            'question': q.text[:60] + ('...' if len(q.text) > 60 else ''),
            'answer': get_submit_answer_text(qr),
            'type': q.question_type
        })
    
    # ========== CREATE NOTIFICATION FOR ADMIN ==========
    try:
        from .models import AdminNotification
        
        # Create notification
        notification = AdminNotification.objects.create(
            notification_type='QUESTIONNAIRE_RESPONSE',
            title=f'New Response from Patient {patient_profile.patient_id}',
            message=f'Patient has submitted questionnaire responses on {daily_response.completed_at.strftime("%Y-%m-%d %H:%M")}',
            related_response=daily_response,
            related_patient=patient_profile,
            priority='MEDIUM'
        )
        
        # Send WebSocket notification if available
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'admin_notifications',
                {
                    'type': 'new_patient_response',
                    'data': {
                        'response_id': str(daily_response.response_id),
                        'patient_id': patient_profile.patient_id,
                        'patient_name': f"{patient_profile.user.first_name} {patient_profile.user.last_name}",
                        'submitted_at': daily_response.completed_at.isoformat(),
                        'notification_id': str(notification.notification_id)
                    }
                }
            )
        except Exception as e:
            logger.error(f"WebSocket notification failed: {e}")
            
    except Exception as e:
        logger.error(f"Failed to create admin notification: {e}")
    # ===================================================
    
    return Response({
        'success': True,
        'message': 'Questionnaire submitted successfully',
        'data': {
            'response_id': daily_response.response_id,
            'assignment_id': assignment.assignment_id,
            'submitted_at': daily_response.completed_at,
            'total_responses': len(saved_responses),
            'alerts_generated': len(alerts),
            'responses_preview': response_summary,
            'is_completed': True,
            'admin_notification_created': True
        }
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def save_questionnaire_progress(request):
    """Save partial progress (without marking as completed)"""
    
    user = request.user
    
    if user.user_type != 'PATIENT':
        raise APIError("Only patients can save progress", 
                      status_code=status.HTTP_403_FORBIDDEN)
    
    # Similar to submit but doesn't mark as completed
    # This is useful for saving progress and continuing later
    
    # Get patient
    try:
        patient_profile = PatientProfile.objects.get(user=user)
        patient_medical = PatientMedicalRecord.objects.get(patient=patient_profile)
    except (PatientProfile.DoesNotExist, PatientMedicalRecord.DoesNotExist):
        raise APIError("Patient record not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # Get response_id or assignment_id
    response_id = request.data.get('response_id')
    assignment_id = request.data.get('assignment_id')
    responses_data = request.data.get('responses', [])
    
    if not responses_data:
        raise APIError("No responses provided", status_code=status.HTTP_400_BAD_REQUEST)
    
    today = timezone.now().date()
    
    # Get or create daily response
    if response_id:
        try:
            daily_response = DailyResponse.objects.get(
                response_id=response_id,
                patient=patient_medical
            )
            assignment = daily_response.questionnaire_assignment
        except DailyResponse.DoesNotExist:
            raise APIError("Response not found", status_code=status.HTTP_404_NOT_FOUND)
    elif assignment_id:
        try:
            assignment = QuestionnaireAssignment.objects.get(
                assignment_id=assignment_id,
                patient=patient_medical
            )
            daily_response, created = DailyResponse.objects.get_or_create(
                patient=patient_medical,
                response_date=today,
                questionnaire_assignment=assignment,
                defaults={'is_completed': False}
            )
        except QuestionnaireAssignment.DoesNotExist:
            raise APIError("Assignment not found", status_code=status.HTTP_404_NOT_FOUND)
    else:
        raise APIError("Either response_id or assignment_id is required", 
                      status_code=status.HTTP_400_BAD_REQUEST)
    
    if daily_response.is_completed:
        raise APIError("This questionnaire is already completed", 
                      status_code=status.HTTP_400_BAD_REQUEST)
    
    # Save each response (similar to submit but don't mark completed)
    saved_count = 0
    for resp in responses_data:
        assigned_question_id = resp.get('assigned_question_id') or resp.get('question_id')
        answer = resp.get('answer') or resp.get('response')
        
        if not assigned_question_id or answer is None:
            continue
        
        try:
            assigned_question = AssignedQuestion.objects.get(
                assigned_question_id=assigned_question_id,
                questionnaire_assignment=assignment
            )
        except AssignedQuestion.DoesNotExist:
            continue
        
        question = assigned_question.question
        
        # Update or create response
        response_defaults = {}
        if question.question_type == 'YES_NO':
            response_defaults['yes_no_response'] = bool(answer)
        elif question.question_type == 'MULTIPLE_CHOICE':
            response_defaults['multiple_choice_response'] = str(answer)
        elif question.question_type == 'SCALE':
            response_defaults['scale_response'] = int(answer) if answer else 0
        elif question.question_type == 'TEXT':
            response_defaults['text_response'] = str(answer)
        
        QuestionResponse.objects.update_or_create(
            daily_response=daily_response,
            assigned_question=assigned_question,
            defaults=response_defaults
        )
        saved_count += 1
    
    return Response({
        'success': True,
        'message': f'Progress saved ({saved_count} responses)',
        'data': {
            'response_id': daily_response.response_id,
            'saved_count': saved_count
        }
    })


# Helper functions for submission
def validate_submit_answer(question, answer):
    """Validate answer for submission"""
    if answer is None:
        return False, "Answer cannot be empty"
    
    if question.question_type == 'YES_NO':
        # Accept various formats
        valid_yes = ['yes', 'true', 'y', '1', 'ja', 'haan', True, 1]
        valid_no = ['no', 'false', 'n', '0', 'nahi', False, 0]
        
        ans_str = str(answer).lower() if not isinstance(answer, bool) else ('yes' if answer else 'no')
        
        if ans_str in valid_yes or ans_str in valid_no:
            return True, None
        return False, "Answer must be Yes or No"
    
    elif question.question_type == 'MULTIPLE_CHOICE':
        if str(answer) not in question.options:
            return False, f"Answer must be one of: {', '.join(question.options)}"
        return True, None
    
    elif question.question_type == 'SCALE':
        try:
            val = int(answer)
            if val < question.scale_min or val > question.scale_max:
                return False, f"Answer must be between {question.scale_min} and {question.scale_max}"
            return True, None
        except (ValueError, TypeError):
            return False, "Answer must be a number"
    
    elif question.question_type == 'TEXT':
        if not isinstance(answer, str) and not isinstance(answer, (int, float)):
            return False, "Answer must be text"
        if len(str(answer)) > 1000:
            return False, "Answer too long (max 1000 characters)"
        return True, None
    
    return False, "Invalid question type"


def get_submit_answer_text(question_response):
    """Get human-readable answer text"""
    if hasattr(question_response, 'yes_no_response') and question_response.yes_no_response is not None:
        return 'Yes' if question_response.yes_no_response else 'No'
    elif hasattr(question_response, 'multiple_choice_response') and question_response.multiple_choice_response:
        return question_response.multiple_choice_response
    elif hasattr(question_response, 'scale_response') and question_response.scale_response is not None:
        return str(question_response.scale_response)
    elif hasattr(question_response, 'text_response') and question_response.text_response:
        return question_response.text_response[:100] + ('...' if len(question_response.text_response) > 100 else '')
    return 'N/A'

# ============================
# views.py (add these new APIs)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_all_patient_responses(request):
    """
    API for admin to get all patient responses
    Admin can see all submitted questionnaires with answers
    """
    
    # Check if user is admin
    if request.user.user_type != 'ADMIN':
        raise APIError("Only admins can access this", status_code=status.HTTP_403_FORBIDDEN)
    
    # Get query parameters for filtering
    patient_id = request.query_params.get('patient_id')
    from_date = request.query_params.get('from_date')
    to_date = request.query_params.get('to_date')
    status = request.query_params.get('status')  # completed/pending
    assignment_id = request.query_params.get('assignment_id')
    
    # Base queryset
    responses = DailyResponse.objects.all().select_related(
        'patient__patient__user',
        'questionnaire_assignment'
    ).order_by('-completed_at')
    
    # Apply filters
    if patient_id:
        responses = responses.filter(patient__patient__patient_id=patient_id)
    
    if from_date:
        responses = responses.filter(completed_at__date__gte=from_date)
    
    if to_date:
        responses = responses.filter(completed_at__date__lte=to_date)
    
    if status:
        if status.lower() == 'completed':
            responses = responses.filter(is_completed=True)
        elif status.lower() == 'pending':
            responses = responses.filter(is_completed=False)
    
    if assignment_id:
        responses = responses.filter(questionnaire_assignment__assignment_id=assignment_id)
    
    # Pagination
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    
    start = (page - 1) * page_size
    end = start + page_size
    
    total_count = responses.count()
    paginated_responses = responses[start:end]
    
    # Prepare response data
    data = []
    for response in paginated_responses:
        # Get response count
        response_count = QuestionResponse.objects.filter(daily_response=response).count()
        
        # Get assignment details - FIXED: removed 'name' field
        assignment = response.questionnaire_assignment
        
        data.append({
            'response_id': response.response_id,
            'patient': {
                'id': response.patient.patient.patient_id,
                'name': f"{response.patient.patient.user.first_name} {response.patient.patient.user.last_name}",
                'email': response.patient.patient.user.email
            },
            'assignment': {
                'id': assignment.assignment_id,
                # 'name' field removed - use assignment_id or add any other field that exists
                # You can use assignment_id as display value or add any other field from your model
                'title': f"Assignment {str(assignment.assignment_id)[:8]}",  # Temporary display
                'frequency': assignment.frequency if hasattr(assignment, 'frequency') else None
            },
            'response_date': response.response_date,
            'completed_at': response.completed_at,
            'is_completed': response.is_completed,
            'total_questions': response_count,
            'created_at': response.created_at
        })
    
    return Response({
        'success': True,
        'data': data,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': (total_count + page_size - 1) // page_size
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_response_detail(request, response_id):
    """
    API for admin to view complete response details with all answers
    """
    
    # Check if user is admin
    if request.user.user_type != 'ADMIN':
        raise APIError("Only admins can access this", status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        # Get the daily response
        response = DailyResponse.objects.get(response_id=response_id)
    except DailyResponse.DoesNotExist:
        raise APIError("Response not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # Get all question responses
    question_responses = QuestionResponse.objects.filter(
        daily_response=response
    ).select_related(
        'assigned_question__question',
        'assigned_question__questionnaire_assignment'
    ).order_by('assigned_question__order')
    
    # Get patient info
    patient = response.patient.patient
    patient_user = patient.user
    
    # Prepare detailed response
    responses_list = []
    for qr in question_responses:
        question = qr.assigned_question.question
        responses_list.append({
            'question_id': question.question_id,
            'question_text': question.text,
            'question_type': question.question_type,
            'order': qr.assigned_question.order,
            'is_mandatory': qr.assigned_question.is_mandatory,
            'answer': get_submit_answer_text(qr),
            'options': question.options if question.options else None,
            'scale_range': {
                'min': question.scale_min,
                'max': question.scale_max
            } if question.question_type == 'SCALE' else None
        })
    
    # Mark notification as read if exists
    try:
        from .models import AdminNotification
        AdminNotification.objects.filter(
            related_response=response,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
    except:
        pass
    
    # FIXED: removed 'name' field from assignment_info
    assignment = response.questionnaire_assignment
    
    return Response({
        'success': True,
        'data': {
            'response_info': {
                'response_id': response.response_id,
                'response_date': response.response_date,
                'completed_at': response.completed_at,
                'is_completed': response.is_completed,
                'created_at': response.created_at
            },
            'patient_info': {
                'patient_id': patient.patient_id,
                'name': f"{patient_user.first_name} {patient_user.last_name}",
                'email': patient_user.email,
                'phone': patient.phone_number if hasattr(patient, 'phone_number') else None,
                'date_of_birth': patient.date_of_birth if hasattr(patient, 'date_of_birth') else None,
                'gender': patient.gender if hasattr(patient, 'gender') else None
            },
            'assignment_info': {
                'assignment_id': assignment.assignment_id,
                # 'name' field removed - use assignment_id or add description if available
                'description': assignment.description if hasattr(assignment, 'description') else None,
                'frequency': assignment.frequency if hasattr(assignment, 'frequency') else None,
                'start_date': assignment.start_date if hasattr(assignment, 'start_date') else None,
                'end_date': assignment.end_date if hasattr(assignment, 'end_date') else None
            },
            'responses': responses_list,
            'total_responses': len(responses_list)
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_patient_response_history(request, patient_id):
    """
    API for admin to get response history of a specific patient
    Using simple Django ORM queries that work with MongoDB
    """
    
    # Check if user is admin
    if request.user.user_type != 'ADMIN':
        raise APIError("Only admins can access this", status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        # Get patient
        patient_profile = PatientProfile.objects.get(patient_id=patient_id)
        
        # STEP 1: Get all daily responses for this patient
        # Try different possible relationships
        daily_responses = None
        
        # Try with patient_medical relationship first
        try:
            patient_medical = PatientMedicalRecord.objects.get(patient=patient_profile)
            daily_responses = DailyResponse.objects.filter(
                patient=patient_medical,
                is_completed=True
            ).order_by('-completed_at')[:20]
            print(f"Found {daily_responses.count()} responses via medical record")
        except PatientMedicalRecord.DoesNotExist:
            print("No medical record found")
        
        # If no responses found, try direct patient_id field
        if not daily_responses or daily_responses.count() == 0:
            daily_responses = DailyResponse.objects.filter(
                patient_id=patient_profile.id,
                is_completed=True
            ).order_by('-completed_at')[:20]
            print(f"Found {daily_responses.count()} responses via direct patient_id")
        
        # If still no responses, try with patient_profile id as string
        if not daily_responses or daily_responses.count() == 0:
            daily_responses = DailyResponse.objects.filter(
                patient_id=str(patient_profile.id),
                is_completed=True
            ).order_by('-completed_at')[:20]
            print(f"Found {daily_responses.count()} responses via string patient_id")
        
        history = []
        
        # Process each daily response
        for dr in daily_responses:
            # Get questions for this response
            question_responses = QuestionResponse.objects.filter(
                daily_response=dr
            )[:15]  # Limit to 15 questions per response
            
            questions_list = []
            for qr in question_responses:
                # Get question details
                question_text = "Question not found"
                question_type = None
                answer = None
                
                # Try to get assigned question
                if qr.assigned_question_id:
                    try:
                        # Try to get assigned question
                        from questionnaires.models import AssignedQuestion
                        assigned_q = AssignedQuestion.objects.filter(
                            assigned_question_id=qr.assigned_question_id
                        ).first()
                        
                        if assigned_q and assigned_q.question_id:
                            from questionnaires.models import Question
                            question = Question.objects.filter(
                                question_id=assigned_q.question_id
                            ).first()
                            
                            if question:
                                question_text = question.text
                                question_type = question.question_type
                    except:
                        pass
                
                # Get answer based on type
                if qr.answer_text:
                    answer = qr.answer_text
                elif qr.answer_choice:
                    answer = qr.answer_choice
                elif qr.answer_rating is not None:
                    answer = str(qr.answer_rating)
                elif qr.answer_boolean is not None:
                    answer = 'Yes' if qr.answer_boolean else 'No'
                else:
                    answer = 'No answer'
                
                questions_list.append({
                    'question': question_text[:100] if question_text else 'Question',
                    'answer': answer
                })
            
            # Get assignment details if available
            assignment_info = None
            if dr.questionnaire_assignment_id:
                try:
                    from questionnaires.models import QuestionnaireAssignment
                    assignment = QuestionnaireAssignment.objects.filter(
                        assignment_id=dr.questionnaire_assignment_id
                    ).first()
                    
                    if assignment:
                        assignment_info = {
                            'id': str(assignment.assignment_id),
                            'frequency': assignment.frequency if hasattr(assignment, 'frequency') else 'unknown',
                            'status': assignment.status if hasattr(assignment, 'status') else 'unknown'
                        }
                except:
                    pass
            
            history.append({
                'response_id': str(dr.response_id),
                'completed_at': dr.completed_at,
                'response_date': dr.response_date if hasattr(dr, 'response_date') else dr.completed_at.date(),
                'assignment': assignment_info,
                'total_questions': len(questions_list),
                'questions': questions_list,
                'preview': questions_list[:3]  # First 3 for preview
            })
        
        return Response({
            'success': True,
            'patient': {
                'patient_id': patient_profile.patient_id,
                'name': f"{patient_profile.user.first_name} {patient_profile.user.last_name}",
                'email': patient_profile.user.email
            },
            'total_responses': len(history),
            'data': history
        })
        
    except PatientProfile.DoesNotExist:
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        print(f"Error in get_patient_response_history: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return basic patient info even if responses fail
        try:
            patient_profile = PatientProfile.objects.get(patient_id=patient_id)
            return Response({
                'success': True,
                'patient': {
                    'patient_id': patient_profile.patient_id,
                    'name': f"{patient_profile.user.first_name} {patient_profile.user.last_name}",
                    'email': patient_profile.user.email
                },
                'total_responses': 0,
                'data': [],
                'message': 'Response history temporarily unavailable'
            })
        except:
            return Response({
                'success': False,
                'error': 'Unable to fetch patient data'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_admin_notifications(request):
    """
    API for admin to get all notifications
    """
    
    if request.user.user_type != 'ADMIN':
        raise APIError("Only admins can access this", status_code=status.HTTP_403_FORBIDDEN)
    
    # Get query params
    is_read = request.query_params.get('is_read')
    limit = int(request.query_params.get('limit', 50))
    
    # Base queryset
    try:
        from .models import AdminNotification
        notifications = AdminNotification.objects.all().select_related(
            'related_patient__user',
            'related_response'
        ).order_by('-created_at')
    except:
        return Response({
            'success': True,
            'data': [],
            'message': 'Notification model not available'
        })
    
    # Apply filters
    if is_read is not None:
        is_read_bool = is_read.lower() == 'true'
        notifications = notifications.filter(is_read=is_read_bool)
    
    # Limit results
    notifications = notifications[:limit]
    
    # Format data
    data = []
    for notification in notifications:
        data.append({
            'notification_id': notification.notification_id,
            'type': notification.notification_type,
            'title': notification.title,
            'message': notification.message,
            'priority': notification.priority,
            'is_read': notification.is_read,
            'created_at': notification.created_at,
            'patient': {
                'id': notification.related_patient.patient_id if notification.related_patient else None,
                'name': f"{notification.related_patient.user.first_name} {notification.related_patient.user.last_name}" if notification.related_patient else None
            } if notification.related_patient else None,
            'response_id': notification.related_response.response_id if notification.related_response else None
        })
    
    return Response({
        'success': True,
        'count': len(data),
        'data': data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def export_responses_to_excel(request):
    """
    API to export responses to Excel for admin
    """
    
    if request.user.user_type != 'ADMIN':
        raise APIError("Only admins can access this", status_code=status.HTTP_403_FORBIDDEN)
    
    from_date = request.data.get('from_date')
    to_date = request.data.get('to_date')
    patient_id = request.data.get('patient_id')
    
    # Get responses based on filters
    responses = DailyResponse.objects.filter(is_completed=True)
    
    if from_date:
        responses = responses.filter(completed_at__date__gte=from_date)
    if to_date:
        responses = responses.filter(completed_at__date__lte=to_date)
    if patient_id:
        responses = responses.filter(patient__patient__patient_id=patient_id)
    
    # Create Excel file
    import openpyxl
    from openpyxl.styles import Font, Alignment
    from django.http import HttpResponse
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Patient Responses"
    
    # Headers
    headers = ['Response ID', 'Patient ID', 'Patient Name', 'Assignment', 
               'Completed Date', 'Question', 'Answer', 'Question Type']
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col)
        cell.value = header
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')
    
    row = 2
    for response in responses:
        question_responses = QuestionResponse.objects.filter(
            daily_response=response
        ).select_related('assigned_question__question')
        
        patient_name = f"{response.patient.patient.user.first_name} {response.patient.patient.user.last_name}"
        
        for qr in question_responses:
            ws.cell(row=row, column=1, value=str(response.response_id))
            ws.cell(row=row, column=2, value=response.patient.patient.patient_id)
            ws.cell(row=row, column=3, value=patient_name)
            ws.cell(row=row, column=4, value=response.questionnaire_assignment.name)
            ws.cell(row=row, column=5, value=response.completed_at.strftime('%Y-%m-%d %H:%M'))
            ws.cell(row=row, column=6, value=qr.assigned_question.question.text)
            ws.cell(row=row, column=7, value=get_submit_answer_text(qr))
            ws.cell(row=row, column=8, value=qr.assigned_question.question.question_type)
            row += 1
    
    # Adjust column widths
    for col in range(1, 9):
        ws.column_dimensions[chr(64 + col)].width = 20
    
    # Create response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=patient_responses.xlsx'
    
    wb.save(response)
    return response
# ==========================

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
import io
from datetime import datetime

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def generate_patient_report(request, patient_id):
    """Generate a Word document report for a patient's questionnaire responses"""
    user = request.user
    
    # Check permission - only admin and nurse can access
    if user.user_type not in ['ADMIN', 'NURSE']:
        raise APIError("Permission denied. Only admins and nurses can access reports.", 
                      status_code=status.HTTP_403_FORBIDDEN)
    
    # Get query parameters
    assignment_id = request.query_params.get('assignment_id')
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    # STEP 1: Get patient medical record
    try:
        # Try to find by medical_record_id first
        patient_medical = PatientMedicalRecord.objects.filter(
            medical_record_id=patient_id
        ).first()
        
        if not patient_medical:
            # Try to find by patient_id (if it's a PatientProfile ID)
            patient_profile = PatientProfile.objects.filter(patient_id=patient_id).first()
            if patient_profile:
                patient_medical = PatientMedicalRecord.objects.filter(
                    patient=patient_profile
                ).first()
        
        if not patient_medical:
            raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        logger.error(f"Error finding patient: {str(e)}")
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # STEP 2: Get patient profile
    patient_profile = patient_medical.patient
    
    # STEP 3: Get assignments
    assignments_query = QuestionnaireAssignment.objects.filter(
        patient=patient_medical
    ).select_related('assigned_by')
    
    # Filter by assignment if provided
    if assignment_id:
        assignments_query = assignments_query.filter(assignment_id=assignment_id)
    
    # Filter by date range if provided
    if start_date and end_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            assignments_query = assignments_query.filter(
                created_at__date__gte=start,
                created_at__date__lte=end
            )
        except ValueError:
            raise APIError("Invalid date format. Use YYYY-MM-DD", 
                          status_code=status.HTTP_400_BAD_REQUEST)
    
    assignments = assignments_query.order_by('-created_at')
    
    if not assignments.exists():
        raise APIError("No assignments found for this patient", 
                      status_code=status.HTTP_404_NOT_FOUND)
    
    # STEP 4: Create Word document
    doc = Document()
    
    # Set document properties
    doc.core_properties.author = user.username
    doc.core_properties.title = f"Patient Report - {patient_profile.first_name} {patient_profile.last_name}"
    
    # Add header
    section = doc.sections[0]
    header = section.header
    header_para = header.paragraphs[0]
    header_para.text = "HealthMonitor - Patient Questionnaire Report"
    header_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    
    # Add title
    title = doc.add_heading('Assignment Response Report', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # ===== PATIENT INFORMATION SECTION =====
    doc.add_heading('Patient Information', level=1)
    
    # Create patient info table
    patient_table = doc.add_table(rows=1, cols=2)
    patient_table.style = 'Light Grid Accent 1'
    patient_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    # Add patient details
    patient_data = [
        ('Name:', f"{patient_profile.first_name} {patient_profile.last_name}"),
        ('Patient ID:', str(patient_profile.patient_id)),
        ('Medical Record ID:', str(patient_medical.medical_record_id)),
    ]
    
    # Add age if available
    if patient_profile.date_of_birth:
        age = calculate_age(patient_profile.date_of_birth)
        patient_data.append(('Age:', age))
    
    # Add gender if available
    if patient_profile.gender:
        patient_data.append(('Gender:', patient_profile.gender))
    
    # Add contact if available
    contact_info = None
    if hasattr(patient_profile, 'phone') and patient_profile.phone:
        contact_info = patient_profile.phone
    elif hasattr(patient_profile, 'phone_number') and patient_profile.phone_number:
        contact_info = patient_profile.phone_number
    elif hasattr(patient_profile, 'mobile') and patient_profile.mobile:
        contact_info = patient_profile.mobile
    
    if contact_info:
        patient_data.append(('Contact:', contact_info))
    
    # Add email if available
    if hasattr(patient_profile, 'user') and patient_profile.user and patient_profile.user.email:
        patient_data.append(('Email:', patient_profile.user.email))
    
    # Add cancer info if available
    if hasattr(patient_medical, 'cancer_type') and patient_medical.cancer_type:
        cancer_name = patient_medical.cancer_type.name if hasattr(patient_medical.cancer_type, 'name') else str(patient_medical.cancer_type)
        patient_data.append(('Cancer Type:', cancer_name))
    
    if hasattr(patient_medical, 'cancer_stage') and patient_medical.cancer_stage:
        patient_data.append(('Cancer Stage:', patient_medical.cancer_stage))
    
    if patient_medical.diagnosis_date:
        patient_data.append(('Diagnosis Date:', patient_medical.diagnosis_date.strftime('%Y-%m-%d')))
    
    # Fill patient table
    for field, value in patient_data:
        row_cells = patient_table.add_row().cells
        row_cells[0].text = field
        row_cells[1].text = value
        # Make field names bold
        row_cells[0].paragraphs[0].runs[0].font.bold = True
    
    # Remove first empty row
    patient_table._tbl.remove(patient_table.rows[0]._tr)
    
    doc.add_paragraph()  # Add spacing
    
    # ===== PROCESS EACH ASSIGNMENT =====
    total_responses = 0
    
    # Import response models
    from monitoring.models import DailyResponse, QuestionResponse
    
    for assignment in assignments:
        # Assignment header
        doc.add_heading(f'Assignment Information', level=1)
        
        # Create assignment info table
        assign_table = doc.add_table(rows=1, cols=2)
        assign_table.style = 'Light Grid Accent 1'
        
        # Status display
        status_text = assignment.get_status_display() if hasattr(assignment, 'get_status_display') else assignment.status
        freq_text = assignment.get_frequency_display() if hasattr(assignment, 'get_frequency_display') else assignment.frequency
        
        # End date text
        end_date_text = assignment.end_date.strftime('%Y-%m-%d') if assignment.end_date else 'Ongoing'
        
        # Assigned by
        assigned_by_text = 'N/A'
        if hasattr(assignment, 'assigned_by') and assignment.assigned_by:
            if hasattr(assignment.assigned_by, 'user') and assignment.assigned_by.user:
                assigned_by_text = assignment.assigned_by.user.get_full_name() or assignment.assigned_by.user.username
            else:
                assigned_by_text = str(assignment.assigned_by)
        
        assignment_data = [
            ('Assignment ID:', str(assignment.assignment_id)),
            ('Status:', status_text),
            ('Frequency:', freq_text),
            ('Period:', f"{assignment.start_date} to {end_date_text}"),
            ('Created:', assignment.created_at.strftime('%Y-%m-%d %H:%M')),
            ('Assigned By:', assigned_by_text),
        ]
        
        # Fill assignment table
        for field, value in assignment_data:
            row_cells = assign_table.add_row().cells
            row_cells[0].text = field
            row_cells[1].text = value
            row_cells[0].paragraphs[0].runs[0].font.bold = True
        
        # Remove first empty row
        assign_table._tbl.remove(assign_table.rows[0]._tr)
        
        doc.add_paragraph()  # Add spacing
        
        # ===== GET RESPONSES FOR THIS ASSIGNMENT =====
        doc.add_heading('Responses', level=2)
        
        daily_responses = DailyResponse.objects.filter(
            questionnaire_assignment=assignment,
            patient=patient_medical
        ).order_by('-response_date')
        
        if daily_responses.exists():
            # Create responses table
            response_table = doc.add_table(rows=1, cols=3)
            response_table.style = 'Colorful Grid'
            
            # Add header row
            header_cells = response_table.rows[0].cells
            header_cells[0].text = 'Date'
            header_cells[1].text = 'Question'
            header_cells[2].text = 'Answer'
            
            # Style header
            for cell in header_cells:
                cell.paragraphs[0].runs[0].font.bold = True
                cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
            
            # Add response rows
            for daily in daily_responses:
                question_responses = QuestionResponse.objects.filter(
                    daily_response=daily
                ).select_related('assigned_question', 'assigned_question__question')
                
                for qr in question_responses:
                    row_cells = response_table.add_row().cells
                    
                    # Date
                    row_cells[0].text = daily.response_date.strftime('%Y-%m-%d')
                    
                    # Question text
                    question_text = qr.assigned_question.question.text
                    if len(question_text) > 100:
                        question_text = question_text[:100] + "..."
                    row_cells[1].text = question_text
                    
                    # Answer based on type
                    answer_text = 'N/A'
                    if qr.yes_no_response is not None:
                        answer_text = 'Yes' if qr.yes_no_response else 'No'
                    elif qr.multiple_choice_response:
                        answer_text = qr.multiple_choice_response
                    elif qr.scale_response is not None:
                        answer_text = str(qr.scale_response)
                    elif qr.text_response:
                        answer_text = qr.text_response
                    
                    if len(answer_text) > 100:
                        answer_text = answer_text[:100] + "..."
                    row_cells[2].text = answer_text
                    
                    total_responses += 1
        else:
            # No responses message
            no_resp_para = doc.add_paragraph()
            no_resp_para.add_run('No responses recorded for this assignment.').italic = True
        
        doc.add_page_break()  # Add page break after each assignment
    
    # ===== SUMMARY SECTION =====
    doc.add_heading('Summary', level=1)
    
    summary_table = doc.add_table(rows=1, cols=2)
    summary_table.style = 'Light Grid Accent 1'
    
    summary_data = [
        ('Total Responses:', str(total_responses)),
        ('Report Generated:', timezone.now().strftime('%Y-%m-%d %H:%M:%S')),
        ('Generated By:', "Admin" if user.user_type == 'ADMIN' else f"Nurse: {user.get_full_name() or user.username}"),
    ]
    
    # Add date range if provided
    if start_date and end_date:
        summary_data.insert(0, ('Date Range:', f"{start_date} to {end_date}"))
    
    # Fill summary table
    for field, value in summary_data:
        row_cells = summary_table.add_row().cells
        row_cells[0].text = field
        row_cells[1].text = value
        row_cells[0].paragraphs[0].runs[0].font.bold = True
    
    # Remove first empty row
    summary_table._tbl.remove(summary_table.rows[0]._tr)
    
    # Add footer
    footer = doc.sections[0].footer
    footer_para = footer.paragraphs[0]
    footer_para.text = f"Generated by HealthMonitor | {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # STEP 5: Save document to bytes buffer
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    # STEP 6: Create filename
    filename = f"patient_report_{patient_profile.first_name}_{patient_profile.last_name}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.docx"
    filename = filename.replace(' ', '_')
    
    # STEP 7: Return file response
    response = FileResponse(
        buffer,
        as_attachment=True,
        filename=filename,
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    
    # Log the action
    logger.info(f"Report generated for patient {patient_id} by {user.username}")
    
    return response


# Helper function to calculate age
def calculate_age(birth_date):
    """Calculate age from birth date"""
    if not birth_date:
        return 'N/A'
    
    today = timezone.now().date()
    age = today.year - birth_date.year
    
    # Adjust if birthday hasn't occurred this year
    if today.month < birth_date.month or (today.month == birth_date.month and today.day < birth_date.day):
        age -= 1
    
    return str(age)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def generate_assignment_report(request, assignment_id):
    """Generate a Word document report for a specific assignment"""
    user = request.user
    
    # Check permission
    if user.user_type not in ['ADMIN', 'NURSE']:
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    # Get assignment
    try:
        assignment = QuestionnaireAssignment.objects.select_related(
            'patient', 'patient__patient'
        ).get(assignment_id=assignment_id)
    except QuestionnaireAssignment.DoesNotExist:
        raise APIError("Assignment not found", status_code=status.HTTP_404_NOT_FOUND)
    
    patient_medical = assignment.patient
    patient_profile = patient_medical.patient
    
    # FIXED: Get responses using the correct relationship
    responses = []
    
    # Try different ways to get responses
    try:
        # Method 1: Check if there's a related manager
        if hasattr(assignment, 'responses'):
            responses = assignment.responses.all()
        elif hasattr(assignment, 'answers'):
            responses = assignment.answers.all()
        elif hasattr(assignment, 'patient_responses'):
            responses = assignment.patient_responses.all()
        else:
            # Method 2: Try direct import with different model names
            try:
                from .models import Response as ResponseModel
                if hasattr(ResponseModel, 'objects'):
                    responses = ResponseModel.objects.filter(assignment=assignment)
            except (ImportError, AttributeError):
                try:
                    from .models import Answer
                    if hasattr(Answer, 'objects'):
                        responses = Answer.objects.filter(assignment=assignment)
                except (ImportError, AttributeError):
                    try:
                        from .models import PatientResponse
                        if hasattr(PatientResponse, 'objects'):
                            responses = PatientResponse.objects.filter(assignment=assignment)
                    except (ImportError, AttributeError):
                        responses = []
    except Exception as e:
        logger.error(f"Error getting responses: {str(e)}")
        responses = []
    
    # Convert to list
    responses_list = list(responses) if responses else []
    
    # Create Word document
    doc = Document()
    
    # Add title
    title = doc.add_heading('Assignment Response Report', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Patient info
    doc.add_heading('Patient Information', level=1)
    doc.add_paragraph(f"Name: {patient_profile.first_name} {patient_profile.last_name}")
    doc.add_paragraph(f"Patient ID: {patient_profile.patient_id}")
    doc.add_paragraph(f"Medical Record ID: {patient_medical.medical_record_id}")
    
    # Assignment info
    doc.add_heading('Assignment Information', level=1)
    doc.add_paragraph(f"Assignment ID: {assignment.assignment_id}")
    
    status_text = assignment.get_status_display() if hasattr(assignment, 'get_status_display') else assignment.status
    doc.add_paragraph(f"Status: {status_text}")
    
    freq_text = assignment.get_frequency_display() if hasattr(assignment, 'get_frequency_display') else assignment.frequency
    doc.add_paragraph(f"Frequency: {freq_text}")
    
    doc.add_paragraph(f"Period: {assignment.start_date} to {assignment.end_date or 'Ongoing'}")
    doc.add_paragraph(f"Created: {assignment.created_at.strftime('%Y-%m-%d %H:%M')}")
    
    # Responses
    doc.add_heading('Responses', level=1)
    
    if responses_list:
        # Create table
        table = doc.add_table(rows=1, cols=3)
        table.style = 'Light Grid Accent 1'
        
        # Header
        header_cells = table.rows[0].cells
        header_cells[0].text = 'Question'
        header_cells[1].text = 'Answer'
        header_cells[2].text = 'Submitted'
        
        for cell in header_cells:
            cell.paragraphs[0].runs[0].font.bold = True
        
        # Add responses
        for response in responses_list:
            row_cells = table.add_row().cells
            
            # Get question text
            question_text = 'N/A'
            if hasattr(response, 'question'):
                if hasattr(response.question, 'text'):
                    question_text = response.question.text
                elif hasattr(response.question, 'question_text'):
                    question_text = response.question.question_text
            
            question_text = question_text[:100] + "..." if len(question_text) > 100 else question_text
            row_cells[0].text = question_text
            
            # Get answer
            answer_text = 'N/A'
            if hasattr(response, 'answer') and response.answer:
                answer_text = str(response.answer)
            elif hasattr(response, 'response') and response.response:
                answer_text = str(response.response)
            elif hasattr(response, 'value') and response.value:
                answer_text = str(response.value)
            
            if len(answer_text) > 200:
                answer_text = answer_text[:200] + "..."
            row_cells[1].text = answer_text
            
            # Get submitted date
            submitted_date = '-'
            if hasattr(response, 'submitted_at') and response.submitted_at:
                submitted_date = response.submitted_at.strftime('%Y-%m-%d %H:%M')
            elif hasattr(response, 'created_at') and response.created_at:
                submitted_date = response.created_at.strftime('%Y-%m-%d %H:%M')
            elif hasattr(response, 'response_date') and response.response_date:
                submitted_date = response.response_date.strftime('%Y-%m-%d %H:%M')
            
            row_cells[2].text = submitted_date
        
        # Remove header row from count
        if len(table.rows) > 1:
            # Don't remove, just note that header is there
            pass
    else:
        doc.add_paragraph("No responses recorded for this assignment.")
    
    # Summary
    doc.add_heading('Summary', level=1)
    doc.add_paragraph(f"Total Responses: {len(responses_list)}")
    
    # Footer
    footer = doc.sections[0].footer
    footer_para = footer.paragraphs[0]
    footer_para.text = f"Generated by {user.get_full_name() or user.username} | {timezone.now().strftime('%Y-%m-%d %H:%M')}"
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Save to buffer
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    # Filename
    filename = f"assignment_{assignment_id}_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.docx"
    
    # Create response with download headers
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_patient_response_summary(request, patient_id):
    """Get summary of patient responses (JSON format)"""
    user = request.user
    
    if user.user_type not in ['ADMIN', 'NURSE']:
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    # Get patient
    try:
        patient_medical = PatientMedicalRecord.objects.filter(
            medical_record_id=patient_id
        ).first()
        
        if not patient_medical:
            patient_profile = PatientProfile.objects.filter(patient_id=patient_id).first()
            if patient_profile:
                patient_medical = PatientMedicalRecord.objects.filter(patient=patient_profile).first()
        
        if not patient_medical:
            raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
    except Exception:
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # FIXED: Get assignments with responses using correct relationships
    assignments = QuestionnaireAssignment.objects.filter(
        patient=patient_medical
    )
    
    # Calculate total responses by checking all possible response relationships
    total_responses = 0
    assignments_data = []
    
    for assignment in assignments:
        # Try different ways to get responses
        responses = []
        
        # Method 1: Check related managers
        if hasattr(assignment, 'responses'):
            try:
                responses = list(assignment.responses.all())
            except:
                responses = []
        elif hasattr(assignment, 'answers'):
            try:
                responses = list(assignment.answers.all())
            except:
                responses = []
        elif hasattr(assignment, 'patient_responses'):
            try:
                responses = list(assignment.patient_responses.all())
            except:
                responses = []
        
        total_responses += len(responses)
        
        # Build assignment data
        assignment_data = {
            'assignment_id': assignment.assignment_id,
            'status': assignment.status,
            'frequency': assignment.frequency,
            'start_date': assignment.start_date,
            'end_date': assignment.end_date,
            'response_count': len(responses),
            'responses': []
        }
        
        # Add response details
        for response in responses:
            response_data = {
                'question_id': None,
                'question_text': 'N/A',
                'question_type': 'N/A',
                'answer': None,
                'submitted_at': None
            }
            
            # Get question info
            if hasattr(response, 'question'):
                if hasattr(response.question, 'question_id'):
                    response_data['question_id'] = response.question.question_id
                if hasattr(response.question, 'text'):
                    response_data['question_text'] = response.question.text
                elif hasattr(response.question, 'question_text'):
                    response_data['question_text'] = response.question.question_text
                if hasattr(response.question, 'question_type'):
                    response_data['question_type'] = response.question.question_type
            
            # Get answer
            if hasattr(response, 'answer'):
                response_data['answer'] = response.answer
            elif hasattr(response, 'response'):
                response_data['answer'] = response.response
            elif hasattr(response, 'value'):
                response_data['answer'] = response.value
            
            # Get submitted date
            if hasattr(response, 'submitted_at'):
                response_data['submitted_at'] = response.submitted_at
            elif hasattr(response, 'created_at'):
                response_data['submitted_at'] = response.created_at
            elif hasattr(response, 'response_date'):
                response_data['submitted_at'] = response.response_date
            
            assignment_data['responses'].append(response_data)
        
        assignments_data.append(assignment_data)
    
    # Count completed assignments
    completed_assignments = sum(1 for a in assignments if a.status == 'COMPLETED')
    
    summary = {
        'patient_info': {
            'patient_id': patient_medical.patient.patient_id,
            'name': f"{patient_medical.patient.first_name} {patient_medical.patient.last_name}",
            'medical_record_id': patient_medical.medical_record_id,
        },
        'assignments': assignments_data,
        'total_assignments': assignments.count(),
        'completed_assignments': completed_assignments,
        'total_responses': total_responses
    }
    
    return Response({
        'success': True,
        'data': summary
    })