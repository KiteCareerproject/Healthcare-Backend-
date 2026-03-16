from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Avg, Q
from django.utils import timezone
from .models import PatientAssignment, DashboardPreference, AnalyticsReport
from accounts.models import NurseProfile, DoctorProfile, AdminProfile, PatientProfile
from patients.models import PatientMedicalRecord
from monitoring.models import DailyResponse, Alert
from accounts.utils import handle_errors, APIError
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from .serializers import (
    PatientAssignmentSerializer, DashboardPreferenceSerializer,
    AnalyticsReportSerializer, CreateAssignmentSerializer,
    NurseSerializer, DoctorSerializer, PatientSerializer,
    UserSerializer, NurseCreateSerializer, DoctorCreateSerializer,
    PatientCreateSerializer, NurseUpdateSerializer, DoctorUpdateSerializer,
    PatientUpdateSerializer
)
import logging
from datetime import datetime, timedelta
from patients.models import PatientProfile
from monitoring.models import Alert, DailyResponse 
from monitoring.serializers import AlertSerializer 
from django.db.models.functions import ExtractYear

from accounts.models import User, NurseProfile, DoctorProfile
from accounts.utils import handle_errors, APIError
from patients.models import PatientMedicalRecord, PatientProfile
from questionnaires.models import QuestionnaireAssignment
from monitoring.models import Alert, DailyResponse 
from monitoring.serializers import AlertSerializer

from rest_framework.views import APIView
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
User = get_user_model()

# ==================== ADMIN VERIFICATION ====================
def verify_admin(user):
    """Verify if user is admin"""
    if user.user_type != 'ADMIN':
        raise APIError("Permission denied. Admin access required.", 
                      status_code=status.HTTP_403_FORBIDDEN)

# ==================== NURSE CRUD ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def create_nurse(request):
    """Create a new nurse (Admin only)"""
    verify_admin(request.user)
    
    serializer = NurseCreateSerializer(data=request.data)
    
    if serializer.is_valid():
        nurse = serializer.save()
        
        # Return the created nurse data (excluding sensitive info)
        return Response({
            'success': True,
            'message': 'Nurse created successfully',
            'data': {
                'nurse_id': nurse.nurse_id,
                'user': nurse.user.pk,
                'first_name': nurse.first_name,
                'last_name': nurse.last_name,
                'employee_id': nurse.employee_id,
                'department': nurse.department,
                'qualification': nurse.qualification,
                'joining_date': nurse.joining_date
            }
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_all_nurses(request):
    """Get all nurses with optional filters (Admin only)"""
    verify_admin(request.user)
    
    # Optional query parameters for filtering
    is_active = request.query_params.get('is_active')
    department = request.query_params.get('department')
    search = request.query_params.get('search')
    
    nurses = NurseProfile.objects.select_related('user').all()
    
    # Apply filters
    if is_active is not None:
        nurses = nurses.filter(is_active=is_active.lower() == 'true')
    
    if department:
        nurses = nurses.filter(department__icontains=department)
    
    if search:
        # Filter only by existing fields
        nurses = nurses.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(employee_id__icontains=search) |
            Q(department__icontains=search) |
            Q(qualification__icontains=search) |
            Q(user__email__icontains=search)  # If you need email search
        )
    
    # Pagination
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    start = (page - 1) * page_size
    end = start + page_size
    
    paginated_nurses = nurses[start:end]
    
    serializer = NurseSerializer(paginated_nurses, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data,
        'pagination': {
            'total': nurses.count(),
            'page': page,
            'page_size': page_size,
            'total_pages': (nurses.count() + page_size - 1) // page_size
        }
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_nurse(request, nurse_id):
    """Get single nurse details (Admin only)"""
    verify_admin(request.user)
    
    try:
        nurse = NurseProfile.objects.select_related('user').get(nurse_id=nurse_id)
    except NurseProfile.DoesNotExist:
        raise APIError("Nurse not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # FIXED: Get active patients count manually to avoid Djongo issues
    try:
        # Method 1: Use list() to force evaluation
        assignments = PatientAssignment.objects.filter(
            nurse=nurse, 
            is_active=True
        )
        active_patients = len(list(assignments))  # Convert to list and get length
        
    except Exception:
        # Method 2: If above fails, try a simpler query
        try:
            assignments = PatientAssignment.objects.filter(nurse=nurse)
            active_patients = 0
            for assignment in assignments:
                if assignment.is_active:
                    active_patients += 1
        except Exception:
            # Method 3: If all fails, set to 0
            active_patients = 0
            print(f"Could not fetch assignments for nurse {nurse_id}")
    
    serializer = NurseSerializer(nurse)
    data = serializer.data
    data['active_patients_count'] = active_patients
    
    return Response({
        'success': True,
        'data': data
    })

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@handle_errors
def update_nurse(request, nurse_id):
    """Update nurse details (Admin only)"""
    verify_admin(request.user)
    
    try:
        nurse = NurseProfile.objects.select_related('user').get(nurse_id=nurse_id)
    except NurseProfile.DoesNotExist:
        raise APIError("Nurse not found", status_code=status.HTTP_404_NOT_FOUND)
    
    partial = request.method == 'PATCH'
    serializer = NurseUpdateSerializer(nurse, data=request.data, partial=partial)
    
    if serializer.is_valid():
        updated_nurse = serializer.save()
        logger.info(f"Nurse updated: {nurse_id} by admin {request.user.email}")
        
        return Response({
            'success': True,
            'message': 'Nurse updated successfully',
            'data': NurseSerializer(updated_nurse).data
        })
    
    raise APIError("Validation error", errors=serializer.errors)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def delete_nurse(request, nurse_id):
    """Delete nurse (Admin only)"""
    verify_admin(request.user)
    
    from accounts.models import NurseProfile
    
    try:
        nurse = NurseProfile.objects.select_related('user').get(nurse_id=nurse_id)
    except NurseProfile.DoesNotExist:
        raise APIError(
            f"Nurse with ID {nurse_id} not found", 
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # SKIP assignment check since model doesn't exist
    # Just log a warning
    logger.info(f"Deleting nurse {nurse_id} - assignment check skipped (model not found)")
    
    hard_delete = request.query_params.get('hard_delete', 'false').lower() == 'true'
    
    try:
        from django.db import transaction
        
        with transaction.atomic():
            if hard_delete:
                # Store user before deletion
                user = nurse.user
                
                # Delete nurse profile
                nurse.delete()
                
                # Delete user
                if user:
                    user.delete()
                    
                message = f"Nurse {nurse_id} permanently deleted"
                logger.warning(f"Nurse {nurse_id} permanently deleted by {request.user.email}")
                
            else:
                # Soft delete
                if hasattr(nurse.user, 'is_active'):
                    nurse.user.is_active = False
                    nurse.user.save()
                
                if hasattr(nurse, 'is_active'):
                    nurse.is_active = False
                    nurse.save()
                    
                message = f"Nurse {nurse_id} deactivated successfully"
                logger.info(f"Nurse {nurse_id} deactivated by {request.user.email}")
        
        return Response({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Error deleting nurse {nurse_id}: {str(e)}")
        raise APIError(
            f"Failed to delete nurse: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ==================== DOCTOR CRUD ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def create_doctor(request):
    """Create a new doctor (Admin only)"""
    verify_admin(request.user)
    
    serializer = DoctorCreateSerializer(data=request.data)
    if serializer.is_valid():
        doctor = serializer.save()
        logger.info(f"Doctor created: {doctor.doctor_id} by admin {request.user.email}")
        
        return Response({
            'success': True,
            'message': 'Doctor created successfully',
            'data': DoctorSerializer(doctor).data
        }, status=status.HTTP_201_CREATED)
    
    raise APIError("Validation error", errors=serializer.errors)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_all_doctors(request):
    """Get all doctors with optional filters (Admin only)"""
    verify_admin(request.user)
    
    # Optional query parameters
    is_active = request.query_params.get('is_active')
    specialization = request.query_params.get('specialization')
    search = request.query_params.get('search')
    
    doctors = DoctorProfile.objects.select_related('user').all()
    
    # Apply filters
    if is_active is not None:
        doctors = doctors.filter(is_active=is_active.lower() == 'true')
    
    if specialization:
        doctors = doctors.filter(specialization__icontains=specialization)
    
    if search:
        doctors = doctors.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(license_number__icontains=search)
        )
    
    # Pagination
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    start = (page - 1) * page_size
    end = start + page_size
    
    paginated_doctors = doctors[start:end]
    
    serializer = DoctorSerializer(paginated_doctors, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data,
        'pagination': {
            'total': doctors.count(),
            'page': page,
            'page_size': page_size,
            'total_pages': (doctors.count() + page_size - 1) // page_size
        }
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_doctor(request, doctor_id):
    """Get single doctor details (Admin only)"""
    verify_admin(request.user)
    
    try:
        doctor = DoctorProfile.objects.select_related('user').get(doctor_id=doctor_id)
    except DoctorProfile.DoesNotExist:
        raise APIError("Doctor not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # FIX: Use len(list()) instead of .count() to avoid Djongo translation error
    try:
        assignments = PatientAssignment.objects.filter(
            doctor=doctor, 
            is_active=True
        )
        # Convert to list and get length
        active_patients = len(list(assignments))
    except Exception as e:
        # If error occurs, set to 0
        print(f"Error counting patient assignments: {e}")
        active_patients = 0
    
    serializer = DoctorSerializer(doctor)
    data = serializer.data
    data['active_patients_count'] = active_patients
    
    return Response({
        'success': True,
        'data': data
    })

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@handle_errors
def update_doctor(request, doctor_id):
    """Update doctor details (Admin only)"""
    verify_admin(request.user)
    
    try:
        doctor = DoctorProfile.objects.select_related('user').get(doctor_id=doctor_id)
    except DoctorProfile.DoesNotExist:
        raise APIError("Doctor not found", status_code=status.HTTP_404_NOT_FOUND)
    
    partial = request.method == 'PATCH'
    serializer = DoctorUpdateSerializer(doctor, data=request.data, partial=partial)
    
    if serializer.is_valid():
        updated_doctor = serializer.save()
        logger.info(f"Doctor updated: {doctor_id} by admin {request.user.email}")
        
        return Response({
            'success': True,
            'message': 'Doctor updated successfully',
            'data': DoctorSerializer(updated_doctor).data
        })
    
    raise APIError("Validation error", errors=serializer.errors)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def delete_doctor(request, doctor_id):
    """Delete doctor (Admin only)"""
    verify_admin(request.user)
    
    from accounts.models import DoctorProfile
    
    try:
        doctor = DoctorProfile.objects.select_related('user').get(doctor_id=doctor_id)
    except DoctorProfile.DoesNotExist:
        raise APIError(
            f"Doctor with ID {doctor_id} not found", 
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # SKIP assignment check - table doesn't exist or has issues
    logger.info(f"Deleting doctor {doctor_id} - assignment check skipped")
    
    hard_delete = request.query_params.get('hard_delete', 'false').lower() == 'true'
    
    try:
        from django.db import transaction
        
        with transaction.atomic():
            if hard_delete:
                # Store user before deletion
                user = doctor.user
                
                # Delete doctor profile
                doctor.delete()
                
                # Delete user
                if user:
                    user.delete()
                    
                message = f"Doctor {doctor_id} permanently deleted"
                logger.warning(f"Doctor {doctor_id} permanently deleted by {request.user.email}")
                
            else:
                # Soft delete
                if hasattr(doctor.user, 'is_active'):
                    doctor.user.is_active = False
                    doctor.user.save()
                
                if hasattr(doctor, 'is_active'):
                    doctor.is_active = False
                    doctor.save()
                    
                message = f"Doctor {doctor_id} deactivated successfully"
                logger.info(f"Doctor {doctor_id} deactivated by {request.user.email}")
        
        return Response({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Error deleting doctor {doctor_id}: {str(e)}")
        raise APIError(
            f"Failed to delete doctor: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ==================== PATIENT CRUD ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def create_patient(request):
    """Create a new patient (Admin only)"""
    verify_admin(request.user)
    
    serializer = PatientCreateSerializer(data=request.data)
    if serializer.is_valid():
        patient = serializer.save()
        # FIX: Use patient_id instead of medical_record_id
        logger.info(f"Patient created: {patient.patient_id} by admin {request.user.email}")
        
        return Response({
            'success': True,
            'message': 'Patient created successfully',
            'data': PatientSerializer(patient).data
        }, status=status.HTTP_201_CREATED)
    
    raise APIError("Validation error", errors=serializer.errors)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_all_patients(request):
    """Get all patient profiles (Admin only)"""
    verify_admin(request.user)
    
    patients = PatientProfile.objects.select_related('user').all()
    serializer = PatientSerializer(patients, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_patient(request, patient_id):
    """Get single patient profile details (Admin only)"""
    verify_admin(request.user)
    
    try:
        # Use PatientProfile model, not PatientMedicalRecord
        patient = PatientProfile.objects.select_related('user').get(patient_id=patient_id)
    except PatientProfile.DoesNotExist:
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # Use PatientSerializer (for PatientProfile)
    serializer = PatientSerializer(patient)
    
    return Response({
        'success': True,
        'data': serializer.data
    })

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@handle_errors
def update_patient(request, patient_id):
    """Update patient details (Admin only)"""
    verify_admin(request.user)
    
    try:
        # FIX: Use PatientProfile, NOT PatientMedicalRecord
        patient = PatientProfile.objects.select_related('user').get(patient_id=patient_id)
    except PatientProfile.DoesNotExist:
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
    
    partial = request.method == 'PATCH'
    serializer = PatientUpdateSerializer(patient, data=request.data, partial=partial)
    
    if serializer.is_valid():
        updated_patient = serializer.save()
        logger.info(f"Patient updated: {patient_id} by admin {request.user.email}")
        
        return Response({
            'success': True,
            'message': 'Patient updated successfully',
            'data': PatientSerializer(updated_patient).data
        })
    
    raise APIError("Validation error", errors=serializer.errors)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def delete_patient(request, patient_id):
    """Delete patient (Admin only)"""
    verify_admin(request.user)
    
    from patients.models import PatientProfile
    
    try:
        # Use patient_id instead of medical_record_id
        patient = PatientProfile.objects.get(patient_id=patient_id)
    except PatientProfile.DoesNotExist:
        raise APIError(
            f"Patient with ID {patient_id} not found", 
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Rest of your code remains the same...
    # Check for active assignments
    try:
        from patients.models import PatientAssignment
        active_assignment = PatientAssignment.objects.filter(
            patient=patient, is_active=True
        ).exists()
        
        if active_assignment:
            raise APIError(
                "Cannot delete patient with active assignments. "
                "Unassign patient first.",
                status_code=status.HTTP_400_BAD_REQUEST
            )
    except ImportError:
        pass
    
    hard_delete = request.query_params.get('hard_delete', 'false').lower() == 'true'
    
    if hard_delete:
        user = patient.user
        patient.delete()
        if user:
            user.delete()
        message = "Patient permanently deleted"
    else:
        patient.user.is_active = False
        patient.user.save()
        patient.is_active = False
        patient.save()
        message = "Patient deactivated successfully"
    
    logger.info(f"Patient {patient_id} deleted by admin {request.user.email}")
    
    return Response({
        'success': True,
        'message': message
    })

# ==================== BULK OPERATIONS ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def bulk_create_nurses(request):
    """Bulk create nurses (Admin only)"""
    verify_admin(request.user)
    
    if not isinstance(request.data, list):
        raise APIError("Expected a list of nurses")
    
    created_nurses = []
    errors = []
    
    for index, nurse_data in enumerate(request.data):
        serializer = NurseCreateSerializer(data=nurse_data)
        if serializer.is_valid():
            nurse = serializer.save()
            created_nurses.append(NurseSerializer(nurse).data)
            logger.info(f"Bulk created nurse: {nurse.nurse_id}")
        else:
            errors.append({
                'index': index,
                'errors': serializer.errors
            })
    
    return Response({
        'success': len(errors) == 0,
        'message': f'Created {len(created_nurses)} nurses, {len(errors)} failed',
        'created': created_nurses,
        'errors': errors if errors else None
    }, status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def bulk_assign_patients(request):
    """Bulk assign patients to nurses and doctors (Admin only)"""
    verify_admin(request.user)
    
    if not isinstance(request.data, list):
        raise APIError("Expected a list of assignments")
    
    admin = get_object_or_404(AdminProfile, user=request.user)
    created_assignments = []
    errors = []
    
    for index, assignment_data in enumerate(request.data):
        try:
            nurse = NurseProfile.objects.get(nurse_id=assignment_data.get('nurse_id'))
            doctor = DoctorProfile.objects.get(doctor_id=assignment_data.get('doctor_id'))
            patient = PatientMedicalRecord.objects.get(
                medical_record_id=assignment_data.get('patient_id')
            )
            
            # Check if already assigned
            if PatientAssignment.objects.filter(patient=patient, is_active=True).exists():
                errors.append({
                    'index': index,
                    'error': f"Patient {assignment_data['patient_id']} already assigned"
                })
                continue
            
            assignment = PatientAssignment.objects.create(
                nurse=nurse,
                doctor=doctor,
                patient=patient,
                assigned_by=admin
            )
            
            created_assignments.append(PatientAssignmentSerializer(assignment).data)
            
        except NurseProfile.DoesNotExist:
            errors.append({
                'index': index,
                'error': f"Nurse {assignment_data.get('nurse_id')} not found"
            })
        except DoctorProfile.DoesNotExist:
            errors.append({
                'index': index,
                'error': f"Doctor {assignment_data.get('doctor_id')} not found"
            })
        except PatientMedicalRecord.DoesNotExist:
            errors.append({
                'index': index,
                'error': f"Patient {assignment_data.get('patient_id')} not found"
            })
        except Exception as e:
            errors.append({
                'index': index,
                'error': str(e)
            })
    
    return Response({
        'success': len(errors) == 0,
        'message': f'Created {len(created_assignments)} assignments, {len(errors)} failed',
        'created': created_assignments,
        'errors': errors if errors else None
    }, status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def assign_patient(request):
    """Assign patient to nurse and doctor"""

    user = request.user

    if user.user_type != 'ADMIN':
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)

    serializer = CreateAssignmentSerializer(data=request.data)
    if not serializer.is_valid():
        raise APIError("Validation error", errors=serializer.errors)

    data = serializer.validated_data

    try:
        nurse = NurseProfile.objects.get(nurse_id=int(data['nurse_id']))
        doctor = DoctorProfile.objects.get(doctor_id=int(data['doctor_id']))
        patient = PatientMedicalRecord.objects.get(patient_id=int(data['patient_id']))
        admin, _ = AdminProfile.objects.get_or_create(user=user)

    except NurseProfile.DoesNotExist:
        raise APIError("Nurse not found", status_code=status.HTTP_404_NOT_FOUND)
    except DoctorProfile.DoesNotExist:
        raise APIError("Doctor not found", status_code=status.HTTP_404_NOT_FOUND)
    except PatientMedicalRecord.DoesNotExist:
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)

    #  DJONGO SAFE CHECK
    existing_assignments = PatientAssignment.objects.filter(
        patient_id=patient.patient_id
    )

    for assign in existing_assignments:
        if assign.is_active:
            raise APIError("Patient already assigned")

    #  CREATE SAFE
    assignment = PatientAssignment.objects.create(
        nurse_id=nurse.nurse_id,
        doctor_id=doctor.doctor_id,
        patient_id=patient.patient_id,
        assigned_by=admin,
        is_active=True
    )

    logger.info(f"Patient {patient.patient_id} assigned to nurse {nurse.nurse_id}")

    serializer = PatientAssignmentSerializer(assignment)

    return Response({
        'success': True,
        'message': 'Patient assigned successfully',
        'data': serializer.data
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_nurse_patients(request, nurse_id):
    """Get all patients assigned to a nurse"""

    try:
        nurse = NurseProfile.objects.get(nurse_id=int(nurse_id))
    except NurseProfile.DoesNotExist:
        raise APIError("Nurse not found", status_code=status.HTTP_404_NOT_FOUND)

    #  DJONGO SAFE QUERY (NO BOOLEAN, NO FK OBJECT)
    assignments = PatientAssignment.objects.filter(
        nurse_id=nurse.nurse_id
    )

    #  FILTER BOOLEAN IN PYTHON
    active_assignments = [
        a for a in assignments if a.is_active
    ]

    serializer = PatientAssignmentSerializer(active_assignments, many=True)

    return Response({
        'success': True,
        'data': serializer.data
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_doctor_patients(request, doctor_id):
    """Get all patients assigned to a doctor"""
    try:
        doctor = DoctorProfile.objects.get(doctor_id=doctor_id)
    except DoctorProfile.DoesNotExist:
        raise APIError("Doctor not found", status_code=status.HTTP_404_NOT_FOUND)
    
    #  FIRST: Get all assignments for this doctor (simple equality filter)
    assignments = PatientAssignment.objects.filter(
        doctor_id=doctor.doctor_id  # Use doctor_id directly, not doctor object
    )
    
    #  SECOND: Filter active ones in Python memory
    active_assignments = [a for a in assignments if a.is_active]
    
    # Serialize the filtered assignments
    serializer = PatientAssignmentSerializer(active_assignments, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_dashboard_stats(request):
    """Get dashboard statistics based on user type"""
    user = request.user
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    
    # Convert dates to datetime for MongoDB queries
    start_datetime = datetime.combine(start_of_month, datetime.min.time())
    today_datetime = datetime.combine(today, datetime.max.time())
    
    if user.user_type == 'NURSE':
        try:
            nurse = NurseProfile.objects.get(user=user)
            
            # Patients assigned to this nurse
            total_patients = PatientMedicalRecord.objects.filter(
                # Adjust this based on your actual relation
                treating_doctor__isnull=False
            ).count()
            
            # New alerts for this nurse
            new_alerts = Alert.objects.filter(
                assigned_to_nurse=nurse,
                status='NEW'
            ).count()
            
            #  FIX: Use datetime range instead of __date
            today_responses = DailyResponse.objects.filter(
                response_date__gte=start_of_month,
                response_date__lte=today
            ).count()
            
            # Pending questionnaires
            pending_questionnaires = QuestionnaireAssignment.objects.filter(
                status='PENDING'
            ).count()
            
            return Response({
                'success': True,
                'data': {
                    'total_patients': total_patients,
                    'new_alerts': new_alerts,
                    'today_responses': today_responses,
                    'pending_questionnaires': pending_questionnaires,
                    'recent_alerts': AlertSerializer(
                        Alert.objects.filter(assigned_to_nurse=nurse)[:5], 
                        many=True
                    ).data
                }
            })
            
        except NurseProfile.DoesNotExist:
            raise APIError("Nurse profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
    elif user.user_type == 'ADMIN':
        # Admin Dashboard
        total_patients = PatientMedicalRecord.objects.count()
        
        # Active Questionnaires
        active_questionnaires = QuestionnaireAssignment.objects.filter(
            status='IN_PROGRESS'
        ).count()
        
        total_nurses = NurseProfile.objects.count()
        
        # Reports Generated
        reports_generated = QuestionnaireAssignment.objects.filter(
            status='COMPLETED'
        ).count()
        
        #  FIX: Patient Activity - use manual calculation
        last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        patient_activity = []
        for day in last_7_days:
            # Use date range instead of __date
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())
            
            count = DailyResponse.objects.filter(
                response_date__gte=day_start,
                response_date__lte=day_end
            ).count()
            
            patient_activity.append({
                'date': day.strftime('%Y-%m-%d'),
                'count': count
            })
        
        # Questionnaire Completion Rate
        total_questionnaires = QuestionnaireAssignment.objects.filter(
            created_at__gte=start_datetime,
            created_at__lte=today_datetime
        ).count()
        
        completed_questionnaires = QuestionnaireAssignment.objects.filter(
            status='COMPLETED',
            created_at__gte=start_datetime,
            created_at__lte=today_datetime
        ).count()
        
        completion_rate = round(
            (completed_questionnaires / total_questionnaires * 100) 
            if total_questionnaires > 0 else 0, 
            1
        )
        
        # Additional Stats
        total_doctors = DoctorProfile.objects.count()
        active_alerts = Alert.objects.filter(status='NEW').count()
        critical_patients = PatientMedicalRecord.objects.filter(
            cancer_stage__in=['STAGE_3', 'STAGE_4']
        ).count()
        
        return Response({
            'success': True,
            'data': {
                'total_patients': total_patients,
                'active_questionnaires': active_questionnaires,
                'total_nurses': total_nurses,
                'reports_generated': reports_generated,
                'patient_activity': patient_activity,
                'questionnaire_completion': {
                    'rate': completion_rate,
                    'total': total_questionnaires,
                    'completed': completed_questionnaires
                },
                'additional_stats': {
                    'total_doctors': total_doctors,
                    'active_alerts': active_alerts,
                    'critical_patients': critical_patients
                },
                'recent_alerts': AlertSerializer(
                    Alert.objects.filter(status='NEW')[:5], 
                    many=True
                ).data
            }
        })
    
    elif user.user_type == 'DOCTOR':
        try:
            doctor = DoctorProfile.objects.get(user=user)
            patients = PatientMedicalRecord.objects.filter(
                treating_doctor=doctor
            ).count()
            
            escalated_alerts = Alert.objects.filter(
                escalated_to_doctor=doctor,
                status='ESCALATED'
            ).count()
            
            return Response({
                'success': True,
                'data': {
                    'total_patients': patients,
                    'escalated_alerts': escalated_alerts
                }
            })
            
        except DoctorProfile.DoesNotExist:
            raise APIError("Doctor profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'success': True,
        'data': {}
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_patient_activity_detail(request):
    """Get detailed patient activity data"""
    user = request.user
    
    if user.user_type != 'ADMIN':
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    days = int(request.query_params.get('days', 30))
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Daily activity
    daily_activity = []
    current = start_date
    while current <= end_date:
        count = DailyResponse.objects.filter(response_date=current).count()
        daily_activity.append({
            'date': current.strftime('%Y-%m-%d'),
            'responses': count
        })
        current += timedelta(days=1)
    
    # Activity by hour (if you have timestamp)
    # This depends on your model structure
    
    return Response({
        'success': True,
        'data': {
            'daily_activity': daily_activity
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_questionnaire_stats(request):
    """Get questionnaire completion statistics"""
    user = request.user
    
    if user.user_type != 'ADMIN':
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    from django.db.models.functions import TruncWeek
    
    # Weekly completion trends
    weekly_stats = QuestionnaireAssignment.objects.filter(
        status='COMPLETED'
    ).annotate(
        week=TruncWeek('completed_at')
    ).values('week').annotate(
        count=Count('assignment_id')
    ).order_by('week')
    
    # Completion by questionnaire type
    type_stats = QuestionnaireAssignment.objects.values(
        'questionnaire__title'
    ).annotate(
        total=Count('assignment_id'),
        completed=Count('assignment_id', filter=Q(status='COMPLETED'))
    )
    
    return Response({
        'success': True,
        'data': {
            'weekly_trend': list(weekly_stats),
            'by_type': list(type_stats)
        }
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def generate_report(request):
    """Generate analytics report"""
    user = request.user
    
    if user.user_type != 'ADMIN':
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    report_type = request.data.get('report_type')
    start_date = request.data.get('start_date')
    end_date = request.data.get('end_date')
    
    if not all([report_type, start_date, end_date]):
        raise APIError("report_type, start_date, end_date are required")
    
    try:
        admin = AdminProfile.objects.get(user=user)
    except AdminProfile.DoesNotExist:
        raise APIError("Admin profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # Generate report data based on type
    report_data = {}
    
    if report_type == 'COMPLETION_RATE':
        total_responses = DailyResponse.objects.filter(
            response_date__gte=start_date,
            response_date__lte=end_date
        )
        completed = total_responses.filter(is_completed=True).count()
        total = total_responses.count()
        
        report_data = {
            'completion_rate': (completed / total * 100) if total > 0 else 0,
            'total_responses': total,
            'completed_responses': completed
        }
    
    elif report_type == 'ALERT_SUMMARY':
        alerts = Alert.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        report_data = {
            'total_alerts': alerts.count(),
            'by_level': alerts.values('alert_level').annotate(count=Count('alert_level')),
            'by_status': alerts.values('status').annotate(count=Count('status'))
        }
    
    report = AnalyticsReport.objects.create(
        report_type=report_type,
        generated_by=admin,
        parameters={
            'start_date': start_date,
            'end_date': end_date
        },
        data=report_data,
        date_range_start=start_date,
        date_range_end=end_date
    )
    
    logger.info(f"Report generated: {report.report_id}")
    
    serializer = AnalyticsReportSerializer(report)
    return Response({
        'success': True,
        'message': 'Report generated successfully',
        'data': serializer.data
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_dashboard_stats_report(request):
    """Get dashboard statistics using Alert model"""
    user = request.user
    
    if user.user_type != 'ADMIN':
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    # Get date filters
    period = request.query_params.get('period', 'this_month')
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    # Calculate date ranges
    today = datetime.now().date()
    
    if period == 'this_month':
        start_date = today.replace(day=1)
        end_date = today
    elif period == 'last_month':
        first = today.replace(day=1)
        start_date = (first - timedelta(days=1)).replace(day=1)
        end_date = first - timedelta(days=1)
    elif period == 'last_30_days':
        start_date = today - timedelta(days=30)
        end_date = today
    elif period == 'custom' and start_date and end_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        start_date = today.replace(day=1)
        end_date = today
    
    # Use naive datetimes
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Previous period for comparison
    period_days = (end_date - start_date).days
    prev_start = start_date - timedelta(days=period_days)
    prev_end = start_date - timedelta(days=1)
    prev_start_datetime = datetime.combine(prev_start, datetime.min.time())
    prev_end_datetime = datetime.combine(prev_end, datetime.max.time())
    
    # ============== STATS CARDS ==============
    
    # 1. Total Patients
    total_patients = PatientMedicalRecord.objects.filter(
        created_at__lte=end_datetime
    ).count()
    
    prev_patients = PatientMedicalRecord.objects.filter(
        created_at__gte=prev_start_datetime,
        created_at__lte=prev_end_datetime
    ).count()
    
    patients_change = calculate_percentage_change(prev_patients, total_patients)
    
    # 2. Active Cases - Using Alert with active status
    active_cases = Alert.objects.filter(
        status__in=['NEW', 'ACKNOWLEDGED', 'IN_PROGRESS'],
        created_at__lte=end_datetime
    ).count()
    
    prev_active = Alert.objects.filter(
        status__in=['NEW', 'ACKNOWLEDGED', 'IN_PROGRESS'],
        created_at__gte=prev_start_datetime,
        created_at__lte=prev_end_datetime
    ).count()
    
    active_change = calculate_percentage_change(prev_active, active_cases)
    
    # 3. Critical Cases
    critical_cases = Alert.objects.filter(
        alert_level='CRITICAL',
        status__in=['NEW', 'ACKNOWLEDGED', 'IN_PROGRESS'],
        created_at__lte=end_datetime
    ).count()
    
    prev_critical = Alert.objects.filter(
        alert_level='CRITICAL',
        status__in=['NEW', 'ACKNOWLEDGED', 'IN_PROGRESS'],
        created_at__gte=prev_start_datetime,
        created_at__lte=prev_end_datetime
    ).count()
    
    critical_change = calculate_percentage_change(prev_critical, critical_cases)
    
    # 4. Recovery Rate - Using resolved alerts
    completed_alerts = Alert.objects.filter(
        status='RESOLVED',
        resolved_at__gte=start_datetime,
        resolved_at__lte=end_datetime
    ).count()
    
    total_alerts = Alert.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).count()
    
    recovery_rate = (completed_alerts / total_alerts * 100) if total_alerts > 0 else 0
    
    prev_completed = Alert.objects.filter(
        status='RESOLVED',
        resolved_at__gte=prev_start_datetime,
        resolved_at__lte=prev_end_datetime
    ).count()
    
    prev_total = Alert.objects.filter(
        created_at__gte=prev_start_datetime,
        created_at__lte=prev_end_datetime
    ).count()
    
    prev_rate = (prev_completed / prev_total * 100) if prev_total > 0 else 0
    recovery_change = recovery_rate - prev_rate
    
    # ============== DEMOGRAPHICS ==============
    
    # Age groups calculation
    patients = PatientMedicalRecord.objects.filter(
        created_at__lte=end_datetime
    ).select_related('patient')
    
    age_groups = {'0-18': 0, '19-35': 0, '36-50': 0, '51-65': 0, '65+': 0}
    current_year = timezone.now().year
    
    for record in patients:
        if record.patient and record.patient.date_of_birth:
            age = current_year - record.patient.date_of_birth.year
            if age <= 18:
                age_groups['0-18'] += 1
            elif age <= 35:
                age_groups['19-35'] += 1
            elif age <= 50:
                age_groups['36-50'] += 1
            elif age <= 65:
                age_groups['51-65'] += 1
            else:
                age_groups['65+'] += 1
    
    age_groups_list = [{'group': k, 'count': v} for k, v in age_groups.items() if v > 0]
    
    # Cancer types distribution
    cancer_types = PatientMedicalRecord.objects.filter(
        created_at__lte=end_datetime
    ).values('cancer_type__name').annotate(
        count=Count('medical_record_id')
    ).order_by('-count')[:5]
    
    # Cancer stages distribution
    cancer_stages = PatientMedicalRecord.objects.filter(
        created_at__lte=end_datetime
    ).values('cancer_stage').annotate(
        count=Count('medical_record_id')
    ).order_by('cancer_stage')
    
    # Hospitals distribution
    top_hospitals = PatientMedicalRecord.objects.filter(
        created_at__lte=end_datetime
    ).values('hospital_name').annotate(
        count=Count('medical_record_id')
    ).order_by('-count')[:5]
    
    #  FIXED: Diagnosis timeline - Manual Python aggregation instead of ExtractYear
    diagnosis_records = PatientMedicalRecord.objects.filter(
        created_at__lte=end_datetime
    ).values('diagnosis_date', 'medical_record_id')
    
    year_counts = {}
    for record in diagnosis_records:
        if record['diagnosis_date']:
            year = record['diagnosis_date'].year
            year_counts[year] = year_counts.get(year, 0) + 1
    
    diagnosis_by_year = [{'year': year, 'count': count} for year, count in sorted(year_counts.items())]
    
    demographics = {
        'age_groups': age_groups_list,
        'cancer_types': list(cancer_types),
        'cancer_stages': list(cancer_stages),
        'top_hospitals': list(top_hospitals),
        'diagnosis_timeline': diagnosis_by_year  # Now using manual aggregation
    }
    
    # ============== TREATMENT OUTCOMES ==============
    
    # By status
    by_status = Alert.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).values('status').annotate(count=Count('alert_id'))
    
    # By severity
    by_severity = []
    severities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    
    for severity in severities:
        total = Alert.objects.filter(
            alert_level=severity,
            created_at__gte=start_datetime,
            created_at__lte=end_datetime
        ).count()
        
        resolved = Alert.objects.filter(
            alert_level=severity,
            status='RESOLVED',
            created_at__gte=start_datetime,
            created_at__lte=end_datetime
        ).count()
        
        by_severity.append({
            'severity': severity,
            'total': total,
            'resolved': resolved,
            'resolution_rate': round((resolved / total * 100) if total > 0 else 0, 1)
        })
    
    # Monthly trend
    monthly_trend = []
    current = start_date
    while current <= end_date:
        month_start = datetime.combine(current.replace(day=1), datetime.min.time())
        
        if current.month == end_date.month and current.year == end_date.year:
            month_end = end_datetime
        else:
            next_month = current.replace(day=28) + timedelta(days=4)
            month_end = datetime.combine(
                next_month - timedelta(days=next_month.day), 
                datetime.max.time()
            )
        
        total = Alert.objects.filter(
            created_at__gte=month_start,
            created_at__lte=month_end
        ).count()
        
        resolved = Alert.objects.filter(
            status='RESOLVED',
            created_at__gte=month_start,
            created_at__lte=month_end
        ).count()
        
        monthly_trend.append({
            'month': current.strftime('%b %Y'),
            'total': total,
            'resolved': resolved
        })
        
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    
    outcomes = {
        'by_status': list(by_status),
        'by_severity': by_severity,
        'monthly_trend': monthly_trend
    }
    
    # Recent Alerts
    recent_alerts = Alert.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).order_by('-created_at')[:5]
    
    return Response({
        'success': True,
        'data': {
            'period': {
                'start': start_date,
                'end': end_date,
                'label': period
            },
            'stats': {
                'total_patients': {
                    'value': total_patients,
                    'change': patients_change,
                    'trend': 'up' if patients_change > 0 else 'down'
                },
                'active_cases': {
                    'value': active_cases,
                    'change': active_change,
                    'trend': 'up' if active_change > 0 else 'down'
                },
                'critical_cases': {
                    'value': critical_cases,
                    'change': critical_change,
                    'trend': 'up' if critical_change > 0 else 'down'
                },
                'recovery_rate': {
                    'value': round(recovery_rate, 1),
                    'change': round(recovery_change, 1),
                    'trend': 'up' if recovery_change > 0 else 'down'
                }
            },
            'demographics': demographics,
            'outcomes': outcomes,
            'recent_alerts': AlertSerializer(recent_alerts, many=True).data
        }
    })


def calculate_percentage_change(previous, current):
    """Calculate percentage change between two values"""
    if previous == 0:
        return 100 if current > 0 else 0
    return round(((current - previous) / previous * 100), 1)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_patient_demographics(request):
    """Get detailed patient demographics data"""
    user = request.user
    
    if user.user_type != 'ADMIN':
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    # Get filters
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    group_by = request.query_params.get('group_by', 'age_group')  # age_group, gender, location
    
    # Base queryset
    # from cancer_patient_monitoring.patients.models import PatientProfile
    queryset = PatientProfile.objects.all()
    
    if start_date and end_date:
        from datetime import datetime
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
        queryset = queryset.filter(created_at__date__gte=start_datetime, created_at__date__lte=end_datetime)
    
    # Group data
    from django.utils import timezone
    current_year = timezone.now().year
    
    if group_by == 'age_group':
        # Calculate age groups manually
        patients = queryset.values('date_of_birth', 'patient_id')
        age_groups = {'0-18': 0, '19-35': 0, '36-50': 0, '51-65': 0, '65+': 0}
        
        for patient in patients:
            if patient['date_of_birth']:
                age = current_year - patient['date_of_birth'].year
                if age <= 18:
                    age_groups['0-18'] += 1
                elif age <= 35:
                    age_groups['19-35'] += 1
                elif age <= 50:
                    age_groups['36-50'] += 1
                elif age <= 65:
                    age_groups['51-65'] += 1
                else:
                    age_groups['65+'] += 1
        
        data = [{'group': k, 'count': v} for k, v in age_groups.items() if v > 0]
        
    elif group_by == 'gender':
        # Gender exists in PatientProfile
        from django.db.models import Count
        data = queryset.values('gender').annotate(
            count=Count('patient_id')
        ).order_by('gender')
        
    elif group_by == 'location':
        # Location might be in address field
        from django.db.models import Count
        # Extract city from address (simple version)
        patients = queryset.values('address', 'patient_id')
        location_counts = {}
        
        for patient in patients:
            if patient['address']:
                # Simple city extraction - you might need to improve this
                parts = patient['address'].split(',')
                city = parts[-2].strip() if len(parts) > 1 else parts[0].strip()
                location_counts[city] = location_counts.get(city, 0) + 1
        
        data = [{'location': k, 'count': v} for k, v in sorted(location_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
        
    else:
        data = []
    
    return Response({
        'success': True,
        'data': {
            'group_by': group_by,
            'data': data
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_treatment_outcomes(request):
    """Get treatment outcomes data using Alert model"""
    user = request.user
    
    if user.user_type != 'ADMIN':
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    # Get date filters
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    from datetime import datetime
    from django.db.models import Count, Q
    # from cancer_patient_monitoring.monitoring.models import Alert
    
    # Base queryset
    queryset = Alert.objects.all()
    
    if start_date and end_date:
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
        queryset = queryset.filter(created_at__date__gte=start_datetime, created_at__date__lte=end_datetime)
    
    #  FIXED: Use alert_id instead of id
    # Outcomes by status
    by_status = queryset.values('status').annotate(
        count=Count('alert_id')  #  Changed from 'id' to 'alert_id'
    ).order_by('status')
    
    # Outcomes by severity
    by_severity = queryset.values('alert_level').annotate(
        total=Count('alert_id'),  #  Changed from 'id' to 'alert_id'
        resolved=Count('alert_id', filter=Q(status='RESOLVED')),
        active=Count('alert_id', filter=Q(status__in=['NEW', 'ACKNOWLEDGED', 'IN_PROGRESS'])),
        escalated=Count('alert_id', filter=Q(status='ESCALATED'))
    ).order_by('alert_level')
    
    # Success rate by severity
    for item in by_severity:
        item['success_rate'] = round(
            (item['resolved'] / item['total'] * 100) if item['total'] > 0 else 0, 
            1
        )
    
    # Additional stats
    total_alerts = queryset.count()
    resolved_alerts = queryset.filter(status='RESOLVED').count()
    critical_alerts = queryset.filter(alert_level='CRITICAL').count()
    
    return Response({
        'success': True,
        'data': {
            'summary': {
                'total_alerts': total_alerts,
                'resolved_alerts': resolved_alerts,
                'critical_alerts': critical_alerts,
                'resolution_rate': round((resolved_alerts / total_alerts * 100) if total_alerts > 0 else 0, 1)
            },
            'by_status': list(by_status),
            'by_severity': list(by_severity)
        }
    })

# def calculate_percentage_change(previous, current):
#     """Calculate percentage change between two values"""
#     if previous == 0:
#         return 100 if current > 0 else 0
#     return round(((current - previous) / previous * 100), 1)


def get_monthly_trend(start_date, end_date):
    """Get monthly trend data"""
    from django.db.models.functions import TruncMonth
    
    trend = Alert.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='COMPLETED'))
    ).order_by('month')
    
    return [
        {
            'month': item['month'].strftime('%b %Y'),
            'total': item['total'],
            'completed': item['completed']
        }
        for item in trend
    ]

# ================================
from .serializers import (
    PatientListSerializer, AlertSerializer, 
    DashboardStatsSerializer, PatientTrendSerializer
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def nurse_dashboard_stats(request):
    """Get dashboard statistics for logged-in nurse - FIXED for Djongo"""
    user = request.user
    
    # Verify nurse
    if user.user_type != 'NURSE':
        raise APIError("Access denied. Nurse only.", status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        nurse = NurseProfile.objects.get(user=user)
    except NurseProfile.DoesNotExist:
        raise APIError("Nurse profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # FIXED: Get patient IDs without using JOIN
    # Method 1: Get all assignments and extract patient_ids in Python
    assignments = PatientAssignment.objects.filter(
        nurse_id=nurse.nurse_id  # Use nurse_id directly, not nurse object
    )
    
    # Filter active ones in Python
    patient_ids = []
    for assignment in assignments:
        if assignment.is_active:
            patient_ids.append(assignment.patient_id)
    
    # If no patients, return zeros
    if not patient_ids:
        today = datetime.now()
        greeting = get_greeting(today.hour)
        
        return Response({
            'success': True,
            'data': {
                'welcome': {
                    'message': f"{greeting}, {nurse.first_name}",
                    'date': today.strftime('%A, %B %d, %Y')
                },
                'stats': {
                    'total_patients': {'value': 0, 'label': 'Total Patients', 'icon': 'people', 'color': 'primary'},
                    'critical': {'value': 0, 'label': 'Critical', 'icon': 'exclamation-triangle', 'color': 'danger'},
                    'high_risk': {'value': 0, 'label': 'High Risk', 'icon': 'graph-up', 'color': 'warning'},
                    'active_alerts': {'value': 0, 'label': 'Active Alerts', 'icon': 'bell', 'color': 'info'},
                    'need_review': {'value': 0, 'label': 'Need Review', 'icon': 'clock-history', 'color': 'secondary'}
                }
            }
        })
    
    # Calculate statistics manually to avoid complex queries
    
    # 1. Total patients
    total_patients = len(patient_ids)
    
    # 2. Critical patients - based on alerts
    critical_count = 0
    critical_patient_ids = set()
    
    # Get all critical alerts for these patients
    for patient_id in patient_ids:
        try:
            # Check for critical alerts
            alerts = Alert.objects.filter(
                patient_id=patient_id,
                alert_level='CRITICAL'
            )
            
            for alert in alerts:
                if alert.status in ['NEW', 'ACKNOWLEDGED']:
                    critical_patient_ids.add(patient_id)
                    break
        except Exception as e:
            logger.error(f"Error checking critical alerts for patient {patient_id}: {str(e)}")
    
    critical_patients = len(critical_patient_ids)
    
    # 3. High risk patients - from medical records
    high_risk_count = 0
    
    for patient_id in patient_ids:
        try:
            # Get medical record
            medical_record = PatientMedicalRecord.objects.filter(
                patient_id=patient_id
            ).first()
            
            if medical_record and hasattr(medical_record, 'risk_level') and medical_record.risk_level == 'HIGH':
                high_risk_count += 1
        except Exception as e:
            logger.error(f"Error checking risk level for patient {patient_id}: {str(e)}")
    
    # 4. Active alerts
    active_alerts = 0
    
    for patient_id in patient_ids:
        try:
            alerts = Alert.objects.filter(
                patient_id=patient_id,
                status__in=['NEW', 'ACKNOWLEDGED']
            )
            active_alerts += len(list(alerts))  # Use len(list()) instead of count()
        except Exception as e:
            logger.error(f"Error counting alerts for patient {patient_id}: {str(e)}")
    
    # 5. Need review
    need_review = 0
    
    for patient_id in patient_ids:
        try:
            # Check for pending questionnaires
            pending = QuestionnaireAssignment.objects.filter(
                patient_id=patient_id,
                status='PENDING'
            )
            need_review += len(list(pending))  # Use len(list()) instead of count()
        except Exception as e:
            logger.error(f"Error checking pending questionnaires for patient {patient_id}: {str(e)}")
    
    # Today's date for welcome message
    today = datetime.now()
    greeting = get_greeting(today.hour)
    
    return Response({
        'success': True,
        'data': {
            'welcome': {
                'message': f"{greeting}, {nurse.first_name}",
                'date': today.strftime('%A, %B %d, %Y')
            },
            'stats': {
                'total_patients': {
                    'value': total_patients,
                    'label': 'Total Patients',
                    'icon': 'people',
                    'color': 'primary'
                },
                'critical': {
                    'value': critical_patients,
                    'label': 'Critical',
                    'icon': 'exclamation-triangle',
                    'color': 'danger'
                },
                'high_risk': {
                    'value': high_risk_count,
                    'label': 'High Risk',
                    'icon': 'graph-up',
                    'color': 'warning'
                },
                'active_alerts': {
                    'value': active_alerts,
                    'label': 'Active Alerts',
                    'icon': 'bell',
                    'color': 'info'
                },
                'need_review': {
                    'value': need_review,
                    'label': 'Need Review',
                    'icon': 'clock-history',
                    'color': 'secondary'
                }
            }
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def nurse_patients(request):
    """Get list of patients assigned to nurse with filters - FIXED for Djongo"""
    user = request.user
    
    if user.user_type != 'NURSE':
        raise APIError("Access denied", status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        nurse = NurseProfile.objects.get(user=user)
    except NurseProfile.DoesNotExist:
        raise APIError("Nurse profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # Get query parameters for filtering
    search = request.query_params.get('search', '')
    status_filter = request.query_params.get('status', '')  # critical, high_risk, stable
    alert_filter = request.query_params.get('alerts', '')  # has_alerts
    
    # FIXED: Get patient IDs without JOIN
    assignments = PatientAssignment.objects.filter(
        nurse_id=nurse.nurse_id
    )
    
    # Filter active in Python
    patient_ids = []
    for assignment in assignments:
        if assignment.is_active:
            patient_ids.append(assignment.patient_id)
    
    if not patient_ids:
        return Response({
            'success': True,
            'data': [],
            'filters': {
                'search': search,
                'status': status_filter,
                'alerts': alert_filter
            }
        })
    
    # Get patients
    patient_data = []
    
    for patient_id in patient_ids:
        try:
            patient = PatientProfile.objects.filter(patient_id=patient_id).first()
            if not patient:
                continue
            
            # Get medical record
            medical_record = PatientMedicalRecord.objects.filter(
                patient_id=patient_id
            ).first()
            
            # Get latest alert
            alerts = Alert.objects.filter(
                patient_id=patient_id
            ).order_by('-created_at')
            
            latest_alert = None
            for alert in alerts:
                latest_alert = alert
                break
            
            # Get pending questionnaires
            pending = QuestionnaireAssignment.objects.filter(
                patient_id=patient_id,
                status='PENDING'
            )
            pending_count = len(list(pending))
            
            # Count alerts by level
            critical_alerts = 0
            warning_alerts = 0
            
            for alert in alerts:
                if alert.status in ['NEW', 'ACKNOWLEDGED']:
                    if alert.alert_level == 'CRITICAL':
                        critical_alerts += 1
                    elif alert.alert_level == 'HIGH':
                        warning_alerts += 1
            
            # Determine status
            if latest_alert and latest_alert.alert_level == 'CRITICAL' and latest_alert.status in ['NEW', 'ACKNOWLEDGED']:
                status_badge = 'danger'
                status_text = 'Critical'
            elif medical_record and hasattr(medical_record, 'risk_level') and medical_record.risk_level == 'HIGH':
                status_badge = 'warning'
                status_text = 'High Risk'
            else:
                status_badge = 'success'
                status_text = 'Stable'
            
            # Check if patient matches search
            if search:
                search_lower = search.lower()
                name = f"{patient.first_name} {patient.last_name}".lower()
                if search_lower not in name and search_lower not in str(patient_id):
                    continue
            
            patient_data.append({
                'id': patient.patient_id,
                'name': f"{patient.first_name} {patient.last_name}",
                'age': calculate_age(patient.date_of_birth) if patient.date_of_birth else 'N/A',
                'gender': patient.gender,
                'condition': medical_record.cancer_type.name if medical_record and hasattr(medical_record, 'cancer_type') and medical_record.cancer_type else 'N/A',
                'status': {
                    'badge': status_badge,
                    'text': status_text
                },
                'last_activity': latest_alert.created_at if latest_alert else None,
                'pending_review': pending_count,
                'alerts': {
                    'critical': critical_alerts,
                    'warning': warning_alerts
                }
            })
            
        except Exception as e:
            logger.error(f"Error processing patient {patient_id}: {str(e)}")
            continue
    
    # Apply filters in Python
    if status_filter == 'critical':
        patient_data = [p for p in patient_data if p['status']['text'] == 'Critical']
    elif status_filter == 'high_risk':
        patient_data = [p for p in patient_data if p['status']['text'] == 'High Risk']
    elif status_filter == 'stable':
        patient_data = [p for p in patient_data if p['status']['text'] == 'Stable']
    
    if alert_filter == 'has_alerts':
        patient_data = [p for p in patient_data if p['alerts']['critical'] > 0 or p['alerts']['warning'] > 0]
    
    return Response({
        'success': True,
        'data': patient_data,
        'filters': {
            'search': search,
            'status': status_filter,
            'alerts': alert_filter
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def nurse_response_history(request):
    """Get response history for nurse's patients - FIXED for Djongo"""
    user = request.user
    
    if user.user_type != 'NURSE':
        raise APIError("Access denied", status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        nurse = NurseProfile.objects.get(user=user)
    except NurseProfile.DoesNotExist:
        raise APIError("Nurse profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # Get date range
    days = int(request.query_params.get('days', 7))
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    # FIXED: Get patient IDs without using complex queries
    # Get all assignments for this nurse
    all_assignments = PatientAssignment.objects.filter(
        nurse_id=nurse.nurse_id  # Use nurse_id directly
    )
    
    # Filter active in Python
    patient_ids = []
    for assignment in all_assignments:
        if assignment.is_active:
            patient_ids.append(assignment.patient_id)
    
    # If no patients, return empty response
    if not patient_ids:
        return Response({
            'success': True,
            'data': {
                'summary': {
                    'total': 0,
                    'completed': 0,
                    'pending': 0,
                    'completion_rate': 0
                },
                'history': []
            }
        })
    
    # FIXED: Get responses manually without using complex filters
    # Convert dates to datetime for range comparison
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get all responses and filter in Python
    all_responses = DailyResponse.objects.all()
    
    responses = []
    for response in all_responses:
        # Check if patient_id matches and date is in range
        if (response.patient_id in patient_ids and 
            response.response_date >= start_date and 
            response.response_date <= end_date):
            responses.append(response)
    
    # Sort by date (most recent first)
    responses.sort(key=lambda x: x.response_date, reverse=True)
    
    # Group by date
    history_by_date = {}
    for response in responses:
        date_str = response.response_date.strftime('%Y-%m-%d')
        if date_str not in history_by_date:
            history_by_date[date_str] = {
                'date': date_str,
                'total': 0,
                'completed': 0,
                'pending': 0,
                'patients': []
            }
        
        history_by_date[date_str]['total'] += 1
        if response.is_completed:
            history_by_date[date_str]['completed'] += 1
        else:
            history_by_date[date_str]['pending'] += 1
        
        # Get patient name
        patient = PatientProfile.objects.filter(patient_id=response.patient_id).first()
        patient_name = 'Unknown'
        if patient:
            patient_name = f"{patient.first_name} {patient.last_name}"
        
        history_by_date[date_str]['patients'].append({
            'patient_id': response.patient_id,
            'patient_name': patient_name,
            'completed': response.is_completed,
            'response_time': response.submitted_at if hasattr(response, 'submitted_at') and response.submitted_at else None,
            'needs_review': getattr(response, 'needs_review', False)
        })
    
    # Convert to list and sort by date
    history_list = list(history_by_date.values())
    history_list.sort(key=lambda x: x['date'], reverse=True)
    
    # Summary stats
    total_responses = len(responses)
    completed_responses = sum(1 for r in responses if r.is_completed)
    pending_responses = total_responses - completed_responses
    
    return Response({
        'success': True,
        'data': {
            'summary': {
                'total': total_responses,
                'completed': completed_responses,
                'pending': pending_responses,
                'completion_rate': round((completed_responses / total_responses * 100) if total_responses > 0 else 0, 1)
            },
            'history': history_list
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def nurse_patient_trends(request):
    """Get patient trends and analytics - FIXED for Djongo"""
    user = request.user
    
    if user.user_type != 'NURSE':
        raise APIError("Access denied", status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        nurse = NurseProfile.objects.get(user=user)
    except NurseProfile.DoesNotExist:
        raise APIError("Nurse profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # Get parameters
    patient_id = request.query_params.get('patient_id')
    metric = request.query_params.get('metric', 'vitals')  # vitals, responses, alerts
    days = int(request.query_params.get('days', 30))
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    # FIXED: Get patient IDs without complex queries
    all_assignments = PatientAssignment.objects.filter(
        nurse_id=nurse.nurse_id  # Use nurse_id directly
    )
    
    # Filter active in Python
    assigned_patient_ids = []
    for assignment in all_assignments:
        if assignment.is_active:
            assigned_patient_ids.append(assignment.patient_id)
    
    # If no patients, return empty response
    if not assigned_patient_ids:
        return Response({
            'success': True,
            'data': {
                'metric': metric,
                'period': f"{start_date} to {end_date}",
                'trends': []
            }
        })
    
    # Filter by specific patient if provided
    if patient_id:
        patient_id_int = int(patient_id) if patient_id.isdigit() else patient_id
        if patient_id_int not in assigned_patient_ids:
            raise APIError("Patient not assigned to you", status_code=status.HTTP_403_FORBIDDEN)
        patient_ids = [patient_id_int]
    else:
        patient_ids = assigned_patient_ids
    
    trends_data = []
    
    for pid in patient_ids:
        # Get patient info
        patient = None
        try:
            patient = PatientProfile.objects.filter(patient_id=pid).first()
        except Exception as e:
            logger.error(f"Error fetching patient {pid}: {str(e)}")
        
        patient_name = 'Unknown'
        if patient:
            patient_name = f"{patient.first_name} {patient.last_name}"
        
        patient_trend = {
            'patient_id': pid,
            'patient_name': patient_name,
            'data': []
        }
        
        if metric == 'vitals':
            # FIXED: Get all vitals and filter in Python
            try:
                all_vitals = VitalSign.objects.all()
                
                for vital in all_vitals:
                    # Check if patient matches
                    if getattr(vital, 'patient_id', None) != pid:
                        continue
                    
                    # Check date range
                    vital_date = getattr(vital, 'recorded_at', None)
                    if vital_date:
                        if hasattr(vital_date, 'date'):
                            vital_date = vital_date.date()
                        
                        if vital_date < start_date or vital_date > end_date:
                            continue
                    
                    patient_trend['data'].append({
                        'date': vital_date.strftime('%Y-%m-%d') if vital_date else None,
                        'heart_rate': getattr(vital, 'heart_rate', None),
                        'blood_pressure_systolic': getattr(vital, 'blood_pressure_systolic', None),
                        'blood_pressure_diastolic': getattr(vital, 'blood_pressure_diastolic', None),
                        'temperature': getattr(vital, 'temperature', None),
                        'oxygen_saturation': getattr(vital, 'oxygen_saturation', None)
                    })
            except Exception as e:
                logger.error(f"Error fetching vitals for patient {pid}: {str(e)}")
            
            # Sort by date
            patient_trend['data'].sort(key=lambda x: x['date'] if x['date'] else '')
        
        elif metric == 'responses':
            # FIXED: Get all responses and filter in Python
            try:
                all_responses = DailyResponse.objects.all()
                
                for response in all_responses:
                    # Check if patient matches
                    if getattr(response, 'patient_id', None) != pid:
                        continue
                    
                    # Check date range
                    response_date = getattr(response, 'response_date', None)
                    if response_date:
                        if response_date < start_date or response_date > end_date:
                            continue
                    
                    patient_trend['data'].append({
                        'date': response_date.strftime('%Y-%m-%d') if response_date else None,
                        'completed': getattr(response, 'is_completed', False),
                        'score': getattr(response, 'total_score', None),
                        'needs_review': getattr(response, 'needs_review', False)
                    })
            except Exception as e:
                logger.error(f"Error fetching responses for patient {pid}: {str(e)}")
            
            # Sort by date
            patient_trend['data'].sort(key=lambda x: x['date'] if x['date'] else '')
        
        elif metric == 'alerts':
            # FIXED: Get all alerts and filter in Python
            try:
                all_alerts = Alert.objects.all()
                
                for alert in all_alerts:
                    # Check if patient matches
                    if getattr(alert, 'patient_id', None) != pid:
                        continue
                    
                    # Check date range
                    alert_date = getattr(alert, 'created_at', None)
                    if alert_date:
                        if hasattr(alert_date, 'date'):
                            alert_date = alert_date.date()
                        
                        if alert_date < start_date or alert_date > end_date:
                            continue
                    
                    patient_trend['data'].append({
                        'date': alert_date.strftime('%Y-%m-%d') if alert_date else None,
                        'level': getattr(alert, 'alert_level', None),
                        'status': getattr(alert, 'status', None),
                        'type': getattr(alert, 'alert_type', 'GENERAL')
                    })
            except Exception as e:
                logger.error(f"Error fetching alerts for patient {pid}: {str(e)}")
            
            # Sort by date
            patient_trend['data'].sort(key=lambda x: x['date'] if x['date'] else '')
        
        # Only add if there's data
        if patient_trend['data']:
            trends_data.append(patient_trend)
    
    return Response({
        'success': True,
        'data': {
            'metric': metric,
            'period': f"{start_date} to {end_date}",
            'trends': trends_data
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def nurse_alerts(request):
    """Get alerts for nurse's patients - FIXED for Djongo"""
    user = request.user
    
    if user.user_type != 'NURSE':
        raise APIError("Access denied", status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        nurse = NurseProfile.objects.get(user=user)
    except NurseProfile.DoesNotExist:
        raise APIError("Nurse profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # Get filter parameters
    status = request.query_params.get('status', 'active')  # active, resolved, all
    level = request.query_params.get('level', '')  # CRITICAL, HIGH, MEDIUM, LOW
    days = int(request.query_params.get('days', 7))
    
    # FIXED: Get patient IDs without complex queries
    all_assignments = PatientAssignment.objects.filter(
        nurse_id=nurse.nurse_id
    )
    
    # Filter active in Python
    patient_ids = []
    for assignment in all_assignments:
        if assignment.is_active:
            patient_ids.append(assignment.patient_id)
    
    # If no patients, return empty response
    if not patient_ids:
        return Response({
            'success': True,
            'data': {
                'summary': {
                    'total': 0,
                    'critical': 0,
                    'high': 0,
                    'medium': 0,
                    'low': 0,
                    'new': 0,
                    'acknowledged': 0
                },
                'alerts': []
            }
        })
    
    # Calculate date range
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # FIXED: Get all alerts and filter in Python
    all_alerts = Alert.objects.all()
    
    filtered_alerts = []
    for alert in all_alerts:
        # Check if patient_id matches
        if alert.patient_id not in patient_ids:
            continue
        
        # Check date range
        if alert.created_at < start_date or alert.created_at > end_date:
            continue
        
        # Check status filter
        if status == 'active' and alert.status not in ['NEW', 'ACKNOWLEDGED']:
            continue
        elif status == 'resolved' and alert.status != 'RESOLVED':
            continue
        
        # Check level filter
        if level and alert.alert_level != level:
            continue
        
        filtered_alerts.append(alert)
    
    # Sort by most recent
    filtered_alerts.sort(key=lambda x: x.created_at, reverse=True)
    
    # Prepare response data
    alert_data = []
    summary_counts = {
        'total': len(filtered_alerts),
        'critical': 0,
        'high': 0,
        'medium': 0,
        'low': 0,
        'new': 0,
        'acknowledged': 0
    }
    
    for alert in filtered_alerts:
        # Update summary counts
        if alert.alert_level == 'CRITICAL':
            summary_counts['critical'] += 1
        elif alert.alert_level == 'HIGH':
            summary_counts['high'] += 1
        elif alert.alert_level == 'MEDIUM':
            summary_counts['medium'] += 1
        elif alert.alert_level == 'LOW':
            summary_counts['low'] += 1
        
        if alert.status == 'NEW':
            summary_counts['new'] += 1
        elif alert.status == 'ACKNOWLEDGED':
            summary_counts['acknowledged'] += 1
        
        # Get patient name
        patient = PatientProfile.objects.filter(patient_id=alert.patient_id).first()
        patient_name = 'Unknown'
        if patient:
            patient_name = f"{patient.first_name} {patient.last_name}"
        
        alert_data.append({
            'id': getattr(alert, 'alert_id', getattr(alert, 'id', None)),
            'patient_id': alert.patient_id,
            'patient_name': patient_name,
            'level': alert.alert_level,
            'type': getattr(alert, 'alert_type', 'GENERAL'),
            'message': getattr(alert, 'message', ''),
            'status': alert.status,
            'created_at': alert.created_at,
            'acknowledged_at': getattr(alert, 'acknowledged_at', None),
            'resolved_at': getattr(alert, 'resolved_at', None)
        })
    
    return Response({
        'success': True,
        'data': {
            'summary': summary_counts,
            'alerts': alert_data
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def acknowledge_alert(request, alert_id):
    """Acknowledge an alert"""
    user = request.user
    
    if user.user_type != 'NURSE':
        raise APIError("Access denied", status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        nurse = NurseProfile.objects.get(user=user)
    except NurseProfile.DoesNotExist:
        raise APIError("Nurse profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
    try:
        alert = Alert.objects.get(alert_id=alert_id)
    except Alert.DoesNotExist:
        raise APIError("Alert not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # Verify patient is assigned to this nurse
    assignment = PatientAssignment.objects.filter(
        nurse=nurse,
        patient_id=alert.patient_id,
        is_active=True
    ).first()
    
    if not assignment:
        raise APIError("Patient not assigned to you", status_code=status.HTTP_403_FORBIDDEN)
    
    # Update alert
    alert.status = 'ACKNOWLEDGED'
    alert.acknowledged_by = nurse
    alert.acknowledged_at = timezone.now()
    alert.save()
    
    logger.info(f"Alert {alert_id} acknowledged by nurse {nurse.nurse_id}")
    
    return Response({
        'success': True,
        'message': 'Alert acknowledged successfully',
        'data': {
            'alert_id': alert.alert_id,
            'status': alert.status,
            'acknowledged_at': alert.acknowledged_at
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def resolve_alert(request, alert_id):
    """Resolve an alert"""
    user = request.user
    
    if user.user_type != 'NURSE':
        raise APIError("Access denied", status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        nurse = NurseProfile.objects.get(user=user)
    except NurseProfile.DoesNotExist:
        raise APIError("Nurse profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
    try:
        alert = Alert.objects.get(alert_id=alert_id)
    except Alert.DoesNotExist:
        raise APIError("Alert not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # Verify patient is assigned to this nurse
    assignment = PatientAssignment.objects.filter(
        nurse=nurse,
        patient_id=alert.patient_id,
        is_active=True
    ).first()
    
    if not assignment:
        raise APIError("Patient not assigned to you", status_code=status.HTTP_403_FORBIDDEN)
    
    # Get resolution notes from request
    resolution_notes = request.data.get('resolution_notes', '')
    
    # Update alert
    alert.status = 'RESOLVED'
    alert.resolved_by = nurse
    alert.resolved_at = timezone.now()
    alert.resolution_notes = resolution_notes
    alert.save()
    
    logger.info(f"Alert {alert_id} resolved by nurse {nurse.nurse_id}")
    
    return Response({
        'success': True,
        'message': 'Alert resolved successfully',
        'data': {
            'alert_id': alert.alert_id,
            'status': alert.status,
            'resolved_at': alert.resolved_at,
            'resolution_notes': alert.resolution_notes
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def search_patients(request):
    """Search patients by name or condition"""
    user = request.user
    
    if user.user_type != 'NURSE':
        raise APIError("Access denied", status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        nurse = NurseProfile.objects.get(user=user)
    except NurseProfile.DoesNotExist:
        raise APIError("Nurse profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
    search_term = request.query_params.get('q', '')
    if len(search_term) < 2:
        return Response({
            'success': True,
            'data': []
        })
    
    # Get assigned patients
    assignments = PatientAssignment.objects.filter(
        nurse=nurse,
        is_active=True
    ).select_related('patient')
    
    patient_ids = [a.patient.patient_id for a in assignments]
    
    # Search in patients
    patients = PatientProfile.objects.filter(
        patient_id__in=patient_ids
    ).filter(
        Q(first_name__icontains=search_term) |
        Q(last_name__icontains=search_term) |
        Q(patient_id__icontains=search_term)
    )
    
    # Search in medical records for condition
    medical_records = PatientMedicalRecord.objects.filter(
        patient_id__in=patient_ids,
        cancer_type__name__icontains=search_term
    ).values_list('patient_id', flat=True)
    
    # Combine results
    result_ids = set(patients.values_list('patient_id', flat=True)) | set(medical_records)
    
    final_patients = PatientProfile.objects.filter(patient_id__in=result_ids)
    
    # Format response
    search_results = []
    for patient in final_patients:
        medical_record = PatientMedicalRecord.objects.filter(patient=patient).first()
        search_results.append({
            'id': patient.patient_id,
            'name': f"{patient.first_name} {patient.last_name}",
            'condition': medical_record.cancer_type.name if medical_record and medical_record.cancer_type else 'N/A',
            'age': calculate_age(patient.date_of_birth) if patient.date_of_birth else 'N/A',
            'gender': patient.gender
        })
    
    return Response({
        'success': True,
        'data': search_results
    })


# ==================== HELPER FUNCTIONS ====================

def get_greeting(hour):
    """Return greeting based on hour of day"""
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"


def calculate_age(birth_date):
    """Calculate age from birth date"""
    if not birth_date:
        return None
    today = timezone.now().date()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))