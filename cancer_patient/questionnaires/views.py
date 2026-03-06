from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import QuestionCategory, Question, QuestionnaireAssignment, AssignedQuestion
from patients.models import PatientMedicalRecord
from accounts.models import NurseProfile, PatientProfile
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
        
        question.delete()
        logger.info(f"Question {question_id} deleted")
        
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
        # Create a medical record if it doesn't exist
        # Add default values for any required fields in your PatientMedicalRecord model
        patient_medical_record = PatientMedicalRecord.objects.create(
            patient=patient_profile,
            # Add default values for required fields based on your model
            # For example:
            # blood_group='Unknown',
            # height=0.0,
            # weight=0.0,
            # medical_conditions='',
            # allergies='',
            # medications=''
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
                # Option 1: Raise error
                # raise APIError("No nurse available for assignment")
                
                # Option 2: Allow assignment without nurse (if your model allows null)
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
        patient = PatientMedicalRecord.objects.get(medical_record_id=patient_id)
    except PatientMedicalRecord.DoesNotExist:
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
    
    assignments = QuestionnaireAssignment.objects.filter(patient=patient)
    serializer = QuestionnaireAssignmentSerializer(assignments, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data
    })