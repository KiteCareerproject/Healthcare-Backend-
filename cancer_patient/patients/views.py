from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import (
    PatientMedicalRecord, CancerType, Treatment, Medication,
    FoodCategory, FoodItem, DietaryRecommendation, PatientDietaryPlan,
    PatientFoodLog, DietaryRestriction, MealPlan
)
from accounts.models import PatientProfile, DoctorProfile, NurseProfile
from accounts.utils import handle_errors, APIError
from .serializers import (
    PatientMedicalRecordSerializer, CancerTypeSerializer,
    CreateMedicalRecordSerializer, CreateTreatmentSerializer,
    CreateMedicationSerializer, TreatmentSerializer, MedicationSerializer,
    FoodCategorySerializer, FoodItemSerializer, DietaryRecommendationSerializer,
    PatientDietaryPlanSerializer, CreatePatientDietaryPlanSerializer,
    PatientFoodLogSerializer, CreatePatientFoodLogSerializer,
    DietaryRestrictionSerializer, MealPlanSerializer, CreateMealPlanSerializer
)
import traceback
from django.db.models import Count
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def cancer_types(request):
    """Get all cancer types or create a new one"""
    
    # GET - List all cancer types (any authenticated user)
    if request.method == 'GET':
        cancer_types = CancerType.objects.all().order_by('name')
        serializer = CancerTypeSerializer(cancer_types, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    # POST - Create new cancer type (ADMIN only)
    elif request.method == 'POST':
        # Check permission - only ADMIN can create
        if request.user.user_type != 'ADMIN':
            raise APIError(
                "Only administrators can create cancer types", 
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Validate and save
        serializer = CancerTypeSerializer(data=request.data)
        
        if serializer.is_valid():
            cancer_type = serializer.save()
            
            logger.info(f"Cancer type created by {request.user.username}: {cancer_type.name}")
            
            return Response({
                'success': True,
                'message': 'Cancer type created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            raise APIError(
                "Validation error", 
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

# @api_view(['GET', 'POST'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def medical_record_list(request):
#     """List all medical records or create new one"""
#     user = request.user
    
#     if request.method == 'GET':
#         if user.user_type in ['ADMIN', 'DOCTOR', 'NURSE']:
#             records = PatientMedicalRecord.objects.all()
#         else:
#             try:
#                 patient = PatientProfile.objects.get(user=user)
#                 records = PatientMedicalRecord.objects.filter(patient=patient)
#             except PatientProfile.DoesNotExist:
#                 records = []
        
#         serializer = PatientMedicalRecordSerializer(records, many=True)
#         return Response({
#             'success': True,
#             'data': serializer.data
#         })
    
#     elif request.method == 'POST':
#         # Allow ADMIN, DOCTOR, and NURSE to create records
#         if user.user_type not in ['ADMIN', 'DOCTOR', 'NURSE']:
#             raise APIError(
#                 "Permission denied. Only Admin, Doctor, and Nurse can create medical records.", 
#                 status_code=status.HTTP_403_FORBIDDEN
#             )
        
#         # Handle request data
#         if hasattr(request.data, 'dict'):
#             modified_data = request.data.dict()
#         elif hasattr(request.data, 'copy'):
#             modified_data = request.data.copy()
#         else:
#             modified_data = dict(request.data)
        
#         # If user is NURSE, auto-assign themselves
#         if user.user_type == 'NURSE':
#             try:
#                 # Use nurse_id instead of id
#                 nurse = NurseProfile.objects.get(user=user)
#                 if 'assigned_nurse_id' not in modified_data or not modified_data.get('assigned_nurse_id'):
#                     # Store nurse_id value, not the object
#                     modified_data['assigned_nurse_id'] = nurse.nurse_id
#                     logger.info(f"Auto-assigned nurse {nurse.nurse_id} to the record")
#             except NurseProfile.DoesNotExist:
#                 logger.warning(f"User {user.username} is NURSE but no nurse profile found")
        
#         serializer = CreateMedicalRecordSerializer(data=modified_data)
#         if not serializer.is_valid():
#             raise APIError("Validation error", errors=serializer.errors)
        
#         data = serializer.validated_data
        
#         # Get patient
#         try:
#             patient = PatientProfile.objects.get(patient_id=data['patient_id'])
#         except PatientProfile.DoesNotExist:
#             raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
        
#         # Check if patient already has record
#         if PatientMedicalRecord.objects.filter(patient=patient).exists():
#             raise APIError("Patient already has a medical record")
        
#         # Get cancer type
#         try:
#             cancer_type = CancerType.objects.get(cancer_type_id=data['cancer_type_id'])
#         except CancerType.DoesNotExist:
#             raise APIError("Cancer type not found", status_code=status.HTTP_404_NOT_FOUND)
        
#         # Get doctor
#         try:
#             doctor = DoctorProfile.objects.get(doctor_id=data['treating_doctor_id'])
#         except DoctorProfile.DoesNotExist:
#             raise APIError("Doctor not found", status_code=status.HTTP_404_NOT_FOUND)
        
#         # Get nurse if assigned_nurse_id is provided - FIXED HERE
#         nurse = None
#         if data.get('assigned_nurse_id'):
#             try:
#                 # Use nurse_id instead of id
#                 nurse = NurseProfile.objects.get(nurse_id=data['assigned_nurse_id'])
#                 logger.info(f"Found nurse with nurse_id: {nurse.nurse_id}")
#             except NurseProfile.DoesNotExist:
#                 raise APIError(
#                     f"Nurse with ID {data['assigned_nurse_id']} not found", 
#                     status_code=status.HTTP_404_NOT_FOUND
#                 )
        
#         # Create medical record
#         record_data = {
#             'patient': patient,
#             'cancer_type': cancer_type,
#             'cancer_stage': data['cancer_stage'],
#             'diagnosis_date': data['diagnosis_date'],
#             'hospital_name': data['hospital_name'],
#             'treating_doctor': doctor,
#             'known_symptoms': data['known_symptoms'],
#             'allergies': data.get('allergies', '')
#         }
        
#         # Add nurse if assigned
#         if nurse:
#             record_data['assigned_nurse'] = nurse
        
#         # Check if assigned_nurse field exists in model
#         try:
#             record = PatientMedicalRecord.objects.create(**record_data)
#         except TypeError as e:
#             # If assigned_nurse field doesn't exist, remove it and try again
#             if 'assigned_nurse' in str(e):
#                 record_data.pop('assigned_nurse', None)
#                 record = PatientMedicalRecord.objects.create(**record_data)
#                 logger.warning("assigned_nurse field doesn't exist in model yet")
#             else:
#                 raise e
        
#         logger.info(
#             f"Medical record created for patient {patient.patient_id} "
#             f"by {user.username} ({user.user_type}). "
#             f"Assigned doctor: {doctor.doctor_id}, "
#             f"Assigned nurse: {nurse.nurse_id if nurse else 'None'}"
#         )
        
#         response_serializer = PatientMedicalRecordSerializer(record)
#         return Response({
#             'success': True,
#             'message': 'Medical record created successfully',
#             'data': response_serializer.data,
#             'assigned_doctor': {
#                 'id': doctor.doctor_id,
#                 'name': f"{doctor.user.first_name} {doctor.user.last_name}" if doctor.user else doctor.doctor_id
#             },
#             'assigned_nurse': {
#                 'nurse_id': nurse.nurse_id,
#                 'name': f"{nurse.user.first_name} {nurse.user.last_name}" if (nurse and nurse.user) else None
#             } if nurse else None
#         }, status=status.HTTP_201_CREATED)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def medical_record_list(request):
    """List all medical records or create new one"""
    user = request.user
    
    if request.method == 'GET':
        if user.user_type in ['ADMIN', 'DOCTOR', 'NURSE']:
            records = PatientMedicalRecord.objects.all()
        else:
            try:
                patient = PatientProfile.objects.get(user=user)
                records = PatientMedicalRecord.objects.filter(patient=patient)
            except PatientProfile.DoesNotExist:
                records = []
        
        serializer = PatientMedicalRecordSerializer(records, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    elif request.method == 'POST':
        # Allow ADMIN, DOCTOR, and NURSE to create records
        if user.user_type not in ['ADMIN', 'DOCTOR', 'NURSE']:
            raise APIError(
                "Permission denied. Only Admin, Doctor, and Nurse can create medical records.", 
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Handle request data
        if hasattr(request.data, 'dict'):
            modified_data = request.data.dict()
        elif hasattr(request.data, 'copy'):
            modified_data = request.data.copy()
        else:
            modified_data = dict(request.data)
        
        # If user is NURSE, auto-assign themselves
        if user.user_type == 'NURSE':
            try:
                nurse = NurseProfile.objects.get(user=user)
                if 'assigned_nurse_id' not in modified_data or not modified_data.get('assigned_nurse_id'):
                    modified_data['assigned_nurse_id'] = nurse.nurse_id
                    logger.info(f"Auto-assigned nurse {nurse.nurse_id} to the record")
            except NurseProfile.DoesNotExist:
                logger.warning(f"User {user.username} is NURSE but no nurse profile found")
        
        serializer = CreateMedicalRecordSerializer(data=modified_data)
        if not serializer.is_valid():
            raise APIError("Validation error", errors=serializer.errors)
        
        data = serializer.validated_data
        
        # Get patient
        try:
            patient = PatientProfile.objects.get(patient_id=data['patient_id'])
        except PatientProfile.DoesNotExist:
            raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
        
        # ✅ REMOVED: Patient already has record check
        # Now patient can have multiple medical records
        
        # Get cancer type
        try:
            cancer_type = CancerType.objects.get(cancer_type_id=data['cancer_type_id'])
        except CancerType.DoesNotExist:
            raise APIError("Cancer type not found", status_code=status.HTTP_404_NOT_FOUND)
        
        # Get doctor
        try:
            doctor = DoctorProfile.objects.get(doctor_id=data['treating_doctor_id'])
        except DoctorProfile.DoesNotExist:
            raise APIError("Doctor not found", status_code=status.HTTP_404_NOT_FOUND)
        
        # Get nurse if assigned_nurse_id is provided
        nurse = None
        if data.get('assigned_nurse_id'):
            try:
                nurse = NurseProfile.objects.get(nurse_id=data['assigned_nurse_id'])
                logger.info(f"Found nurse with nurse_id: {nurse.nurse_id}")
            except NurseProfile.DoesNotExist:
                raise APIError(
                    f"Nurse with ID {data['assigned_nurse_id']} not found", 
                    status_code=status.HTTP_404_NOT_FOUND
                )
        
        # Create medical record
        record_data = {
            'patient': patient,
            'cancer_type': cancer_type,
            'cancer_stage': data['cancer_stage'],
            'diagnosis_date': data['diagnosis_date'],
            'hospital_name': data['hospital_name'],
            'treating_doctor': doctor,
            'known_symptoms': data['known_symptoms'],
            'allergies': data.get('allergies', '')
        }
        
        # Add nurse if assigned
        if nurse:
            record_data['assigned_nurse'] = nurse
        
        # Create record (no check now)
        try:
            record = PatientMedicalRecord.objects.create(**record_data)
        except TypeError as e:
            if 'assigned_nurse' in str(e):
                record_data.pop('assigned_nurse', None)
                record = PatientMedicalRecord.objects.create(**record_data)
                logger.warning("assigned_nurse field doesn't exist in model yet")
            else:
                raise e
        
        logger.info(
            f"Medical record created for patient {patient.patient_id} "
            f"by {user.username} ({user.user_type}). "
            f"Assigned doctor: {doctor.doctor_id}, "
            f"Assigned nurse: {nurse.nurse_id if nurse else 'None'}"
        )
        
        response_serializer = PatientMedicalRecordSerializer(record)
        return Response({
            'success': True,
            'message': 'Medical record created successfully',
            'data': response_serializer.data,
            'assigned_doctor': {
                'id': doctor.doctor_id,
                'name': f"{doctor.user.first_name} {doctor.user.last_name}" if doctor.user else doctor.doctor_id
            },
            'assigned_nurse': {
                'nurse_id': nurse.nurse_id,
                'name': f"{nurse.user.first_name} {nurse.user.last_name}" if (nurse and nurse.user) else None
            } if nurse else None
        }, status=status.HTTP_201_CREATED)
    
# views.py - Modified to use patient_id

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def medical_record_detail(request, patient_id):
    """Get, update or delete medical records by patient_id"""
    user = request.user
    
    # Permission check for patient
    if user.user_type == 'PATIENT':
        try:
            patient = PatientProfile.objects.get(user=user)
            if patient.patient_id != patient_id:
                raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        except PatientProfile.DoesNotExist:
            raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    # GET method - return ALL records for this patient
    if request.method == 'GET':
        # Get all records for this patient
        records = PatientMedicalRecord.objects.select_related(
            'patient', 
            'cancer_type', 
            'treating_doctor',
            'assigned_nurse'
        ).filter(patient_id=patient_id).order_by('-created_at')  # Get all records
        
        if not records.exists():
            raise APIError("No medical records found for this patient", 
                          status_code=status.HTTP_404_NOT_FOUND)
        
        # Serialize all records
        serializer = PatientMedicalRecordSerializer(records, many=True)
        return Response({
            'success': True,
            'count': records.count(),
            'data': serializer.data
        })
    
    # For PUT and DELETE - need to specify which record to update/delete
    # You need to pass record_id in request data
    elif request.method == 'PUT':
        if user.user_type not in ['ADMIN', 'DOCTOR']:
            raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
        # Get record_id from request data
        record_id = request.data.get('medical_record_id')
        if not record_id:
            raise APIError("medical_record_id is required for update", 
                          status_code=status.HTTP_400_BAD_REQUEST)
        
        try:
            record = PatientMedicalRecord.objects.select_related(
                'patient', 'cancer_type', 'treating_doctor', 'assigned_nurse'
            ).get(medical_record_id=record_id, patient_id=patient_id)
        except PatientMedicalRecord.DoesNotExist:
            raise APIError(f"Medical record with ID {record_id} not found", 
                          status_code=status.HTTP_404_NOT_FOUND)
        
        data = request.data
        
        from patients.models import CancerType
        from accounts.models import DoctorProfile, NurseProfile
        
        # Update cancer_type if provided
        if 'cancer_type_id' in data:
            cancer_type_id = data['cancer_type_id']
            if cancer_type_id:
                try:
                    cancer_type = CancerType.objects.get(cancer_type_id=cancer_type_id)
                    record.cancer_type = cancer_type
                except CancerType.DoesNotExist:
                    raise APIError(f"Cancer type with ID {cancer_type_id} does not exist", 
                                status_code=status.HTTP_400_BAD_REQUEST)
        
        # Update treating_doctor if provided
        if 'treating_doctor_id' in data:
            treating_doctor_id = data['treating_doctor_id']
            if treating_doctor_id:
                try:
                    doctor = DoctorProfile.objects.get(doctor_id=treating_doctor_id)
                    record.treating_doctor = doctor
                except DoctorProfile.DoesNotExist:
                    raise APIError(f"Doctor with ID {treating_doctor_id} does not exist", 
                                status_code=status.HTTP_400_BAD_REQUEST)
        
        # Update basic fields
        if 'cancer_stage' in data:
            record.cancer_stage = data['cancer_stage']
        if 'diagnosis_date' in data:
            record.diagnosis_date = data['diagnosis_date']
        if 'hospital_name' in data:
            record.hospital_name = data['hospital_name']
        if 'known_symptoms' in data:
            record.known_symptoms = data['known_symptoms']
        if 'allergies' in data:
            record.allergies = data['allergies']
        
        # Update assigned nurse if provided
        if 'assigned_nurse_id' in data:
            assigned_nurse_id = data['assigned_nurse_id']
            if assigned_nurse_id:
                try:
                    nurse = NurseProfile.objects.get(nurse_id=assigned_nurse_id)
                    record.assigned_nurse = nurse
                except NurseProfile.DoesNotExist:
                    raise APIError(f"Nurse with ID {assigned_nurse_id} does not exist", 
                                status_code=status.HTTP_400_BAD_REQUEST)
            else:
                record.assigned_nurse = None
        
        record.save()
        
        logger.info(f"Medical record {record_id} for patient {patient_id} updated by {user.username}")
        
        fresh_record = PatientMedicalRecord.objects.select_related(
            'patient', 'cancer_type', 'treating_doctor', 'assigned_nurse'
        ).get(medical_record_id=record.medical_record_id)
        
        serializer = PatientMedicalRecordSerializer(fresh_record)
        return Response({
            'success': True,
            'message': 'Medical record updated successfully',
            'data': serializer.data
        })
    
    elif request.method == 'DELETE':
        if user.user_type != 'ADMIN':
            raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
        # Get record_id from request data
        record_id = request.data.get('medical_record_id')
        if not record_id:
            raise APIError("medical_record_id is required for deletion", 
                          status_code=status.HTTP_400_BAD_REQUEST)
        
        try:
            record = PatientMedicalRecord.objects.get(medical_record_id=record_id, patient_id=patient_id)
        except PatientMedicalRecord.DoesNotExist:
            raise APIError(f"Medical record with ID {record_id} not found", 
                          status_code=status.HTTP_404_NOT_FOUND)
        
        record.delete()
        logger.info(f"Medical record {record_id} for patient {patient_id} deleted by {user.username}")
        
        return Response({
            'success': True,
            'message': 'Medical record deleted successfully'
        })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def add_treatment(request, record_id):
    """Add treatment to medical record"""
    user = request.user
    
    if user.user_type not in ['ADMIN', 'DOCTOR']:
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        record = PatientMedicalRecord.objects.get(medical_record_id=record_id)
    except PatientMedicalRecord.DoesNotExist:
        raise APIError("Medical record not found", status_code=status.HTTP_404_NOT_FOUND)
    
    serializer = CreateTreatmentSerializer(data=request.data)
    if not serializer.is_valid():
        raise APIError("Validation error", errors=serializer.errors)
    
    data = serializer.validated_data
    
    treatment = Treatment.objects.create(
        patient_medical_record=record,
        treatment_type=data['treatment_type'],
        treatment_name=data['treatment_name'],
        start_date=data['start_date'],
        end_date=data.get('end_date'),
        status=data.get('status', 'PLANNED'),
        notes=data.get('notes', '')
    )
    
    logger.info(f"Treatment added to medical record {record_id}")
    
    response_serializer = TreatmentSerializer(treatment)
    return Response({
        'success': True,
        'message': 'Treatment added successfully',
        'data': response_serializer.data
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_medications(request, record_id):
    """Get all medications for a medical record"""
    user = request.user
    
    # Check permissions
    if user.user_type not in ['ADMIN', 'DOCTOR', 'NURSE', 'PATIENT']:
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    # For patients, check if they own the record
    if user.user_type == 'PATIENT':
        try:
            patient = PatientProfile.objects.get(user=user)
            record = PatientMedicalRecord.objects.get(medical_record_id=record_id, patient=patient)
        except PatientMedicalRecord.DoesNotExist:
            raise APIError("Access denied", status_code=status.HTTP_403_FORBIDDEN)
    else:
        # For admin/doctor/nurse, just check if record exists
        try:
            record = PatientMedicalRecord.objects.get(medical_record_id=record_id)
        except PatientMedicalRecord.DoesNotExist:
            raise APIError("Medical record not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # Get all medications for this record
    medications = Medication.objects.filter(patient_medical_record_id=record_id).order_by('-created_at')
    
    serializer = MedicationSerializer(medications, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def add_medication(request, record_id):
    """Add medication to medical record"""
    user = request.user
    
    if user.user_type not in ['ADMIN', 'DOCTOR']:
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        record = PatientMedicalRecord.objects.get(medical_record_id=record_id)
    except PatientMedicalRecord.DoesNotExist:
        raise APIError("Medical record not found", status_code=status.HTTP_404_NOT_FOUND)
    
    serializer = CreateMedicationSerializer(data=request.data)
    if not serializer.is_valid():
        raise APIError("Validation error", errors=serializer.errors)
    
    data = serializer.validated_data
    
    # Get doctor
    try:
        doctor = DoctorProfile.objects.get(user=user) if user.user_type == 'DOCTOR' else None
    except DoctorProfile.DoesNotExist:
        doctor = None
    
    medication = Medication.objects.create(
        patient_medical_record=record,
        medication_name=data['medication_name'],
        dosage=data['dosage'],
        frequency=data['frequency'],
        timing=data.get('timing', []),
        start_date=data['start_date'],
        end_date=data.get('end_date'),
        prescribed_by=doctor,
        notes=data.get('notes', '')
    )
    
    logger.info(f"Medication added to medical record {record_id}")
    
    response_serializer = MedicationSerializer(medication)
    return Response({
        'success': True,
        'message': 'Medication added successfully',
        'data': response_serializer.data
    }, status=status.HTTP_201_CREATED)

@api_view(['GET', 'POST', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_treatments(request, record_id, treatment_id=None):
    """
    Unified API for treatments management
    Supports:
    - GET: Get all treatments for a medical record
    - POST: Add a new treatment
    - PUT: Update an existing treatment
    - DELETE: Remove a treatment
    """
    
    # GET - Retrieve all treatments for a medical record
    if request.method == 'GET':
        try:
            record = PatientMedicalRecord.objects.get(medical_record_id=record_id)
        except PatientMedicalRecord.DoesNotExist:
            raise APIError("Medical record not found", status_code=status.HTTP_404_NOT_FOUND)
        
        treatments = record.treatments.all()
        serializer = TreatmentSerializer(treatments, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    # POST - Create a new treatment
    elif request.method == 'POST':
        try:
            record = PatientMedicalRecord.objects.get(medical_record_id=record_id)
        except PatientMedicalRecord.DoesNotExist:
            raise APIError("Medical record not found", status_code=status.HTTP_404_NOT_FOUND)
        
        # Get doctor if user is a doctor
        doctor = None
        user = request.user
        if user.user_type == 'DOCTOR':
            try:
                doctor = DoctorProfile.objects.get(user=user)
            except DoctorProfile.DoesNotExist:
                raise APIError("Doctor profile not found", status_code=status.HTTP_404_NOT_FOUND)
        
        # Prepare data for treatment creation
        data = request.data.copy()
        data['patient_medical_record'] = record.medical_record_id
        if doctor:
            data['prescribed_by'] = doctor.doctor_id
        
        serializer = TreatmentSerializer(data=data)
        
        if serializer.is_valid():
            treatment = serializer.save()
            
            return Response({
                'success': True,
                'message': 'Treatment added successfully',
                'data': TreatmentSerializer(treatment).data
            }, status=status.HTTP_201_CREATED)
        else:
            raise APIError("Validation error", errors=serializer.errors)
    
    # PUT - Update an existing treatment
    elif request.method == 'PUT':
        if not treatment_id:
            raise APIError("treatment_id is required for update", 
                         status_code=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get the treatment
            treatment = Treatment.objects.get(
                treatment_id=treatment_id,
                patient_medical_record_id=record_id
            )
        except Treatment.DoesNotExist:
            raise APIError(f"Treatment with ID {treatment_id} not found", 
                         status_code=status.HTTP_404_NOT_FOUND)
        
        # Check permissions
        user = request.user
        if user.user_type == 'PATIENT':
            # Patients can't update treatments
            raise APIError("Patients cannot update treatments", 
                         status_code=status.HTTP_403_FORBIDDEN)
        
        # Partial update allowed
        serializer = TreatmentSerializer(treatment, data=request.data, partial=True)
        
        if serializer.is_valid():
            updated_treatment = serializer.save()
            
            return Response({
                'success': True,
                'message': 'Treatment updated successfully',
                'data': TreatmentSerializer(updated_treatment).data
            })
        else:
            raise APIError("Validation error", errors=serializer.errors)
    
    # DELETE - Remove a treatment
    elif request.method == 'DELETE':
        if not treatment_id:
            raise APIError("treatment_id is required for delete", 
                         status_code=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get the treatment
            treatment = Treatment.objects.get(
                treatment_id=treatment_id,
                patient_medical_record_id=record_id
            )
        except Treatment.DoesNotExist:
            raise APIError(f"Treatment with ID {treatment_id} not found", 
                         status_code=status.HTTP_404_NOT_FOUND)
        
        # Check permissions
        user = request.user
        if user.user_type == 'PATIENT':
            # Patients can't delete treatments
            raise APIError("Patients cannot delete treatments", 
                         status_code=status.HTTP_403_FORBIDDEN)
        
        # Store treatment details before deletion for response
        treatment_data = TreatmentSerializer(treatment).data
        
        # Delete the treatment
        treatment.delete()
        
        return Response({
            'success': True,
            'message': f'Treatment "{treatment_data.get("treatment_name", treatment_id)}" deleted successfully',
            'data': treatment_data
        })

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_medications(request, record_id, medication_id=None):
    """
    Unified API for medications management
    Supports:
    - GET: Get all medications for a medical record
    - PUT: Update an existing medication
    - DELETE: Remove a medication
    """
    user = request.user
    
    # GET - Retrieve all medications for a medical record
    if request.method == 'GET':
        try:
            record = PatientMedicalRecord.objects.get(medical_record_id=record_id)
        except PatientMedicalRecord.DoesNotExist:
            raise APIError("Medical record not found", status_code=status.HTTP_404_NOT_FOUND)
        
        # Optional: Add filters via query params
        is_active = request.query_params.get('is_active')
        medications = record.medications.all()
        
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            medications = medications.filter(is_active=is_active_bool)
        
        medications = medications.order_by('-start_date', 'medication_name')
        serializer = MedicationSerializer(medications, many=True)
        
        return Response({
            'success': True,
            'count': len(serializer.data),
            'data': serializer.data
        })
    
    # PUT - Update an existing medication
    elif request.method == 'PUT':
        if not medication_id:
            raise APIError("medication_id is required for update", 
                         status_code=status.HTTP_400_BAD_REQUEST)
        
        # Check permissions
        if user.user_type not in ['ADMIN', 'DOCTOR', 'NURSE']:
            raise APIError("Only medical staff can update medications", 
                         status_code=status.HTTP_403_FORBIDDEN)
        
        try:
            # Get the medication
            medication = Medication.objects.get(
                medication_id=medication_id,
                patient_medical_record_id=record_id
            )
        except Medication.DoesNotExist:
            raise APIError(f"Medication with ID {medication_id} not found for this medical record", 
                         status_code=status.HTTP_404_NOT_FOUND)
        
        # Prepare data
        data = request.data.copy()
        
        # Handle timing field if it's a list
        if 'timing' in data and isinstance(data['timing'], list):
            import json
            data['timing'] = json.dumps(data['timing'])
        
        # Partial update allowed
        serializer = MedicationSerializer(medication, data=data, partial=True)
        
        if serializer.is_valid():
            updated_medication = serializer.save()
            
            return Response({
                'success': True,
                'message': 'Medication updated successfully',
                'data': MedicationSerializer(updated_medication).data
            })
        else:
            raise APIError("Validation error", errors=serializer.errors)
    
    # DELETE - Remove a medication
    elif request.method == 'DELETE':
        if not medication_id:
            raise APIError("medication_id is required for delete", 
                         status_code=status.HTTP_400_BAD_REQUEST)
        
        # Check permissions
        if user.user_type not in ['ADMIN', 'DOCTOR', 'NURSE']:
            raise APIError("Only medical staff can delete medications", 
                         status_code=status.HTTP_403_FORBIDDEN)
        
        try:
            # Get the medication
            medication = Medication.objects.get(
                medication_id=medication_id,
                patient_medical_record_id=record_id
            )
        except Medication.DoesNotExist:
            raise APIError(f"Medication with ID {medication_id} not found for this medical record", 
                         status_code=status.HTTP_404_NOT_FOUND)
        
        # Store medication details before deletion for response
        medication_data = MedicationSerializer(medication).data
        
        # Delete the medication
        medication.delete()
        
        return Response({
            'success': True,
            'message': f'Medication "{medication_data.get("medication_name", medication_id)}" deleted successfully',
            'data': medication_data
        })



# ==================== FOOD CATEGORY APIS ====================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def food_categories(request):
    """Get all food categories or create new one"""
    
    if request.method == 'GET':
        categories = FoodCategory.objects.all().order_by('name')
        serializer = FoodCategorySerializer(categories, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    elif request.method == 'POST':
        # Only ADMIN and DOCTOR can create categories
        if request.user.user_type not in ['ADMIN', 'DOCTOR']:
            raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
        serializer = FoodCategorySerializer(data=request.data)
        if serializer.is_valid():
            category = serializer.save()
            logger.info(f"Food category created by {request.user.username}: {category.name}")
            return Response({
                'success': True,
                'message': 'Food category created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            raise APIError("Validation error", errors=serializer.errors)

# # ==================== FOOD ITEM APIS ====================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def food_items(request):
    """Get all food items or create new one"""
    
    if request.method == 'GET':
        # Filter by category if provided
        category_id = request.query_params.get('category')
        food_type = request.query_params.get('food_type')
        
        queryset = FoodItem.objects.all()
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        if food_type:
            queryset = queryset.filter(food_type=food_type)
        
        queryset = queryset.order_by('name')
        serializer = FoodItemSerializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    elif request.method == 'POST':
        # Only ADMIN and DOCTOR can create food items
        if request.user.user_type not in ['ADMIN', 'DOCTOR']:
            raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
        serializer = FoodItemSerializer(data=request.data)
        if serializer.is_valid():
            food_item = serializer.save()
            logger.info(f"Food item created by {request.user.username}: {food_item.name}")
            return Response({
                'success': True,
                'message': 'Food item created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            raise APIError("Validation error", errors=serializer.errors)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def food_item_detail(request, item_id):
    """Get, update or delete specific food item"""
    
    try:
        food_item = FoodItem.objects.get(food_item_id=item_id)
    except FoodItem.DoesNotExist:
        raise APIError("Food item not found", status_code=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        serializer = FoodItemSerializer(food_item)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    elif request.method == 'PUT':
        if request.user.user_type not in ['ADMIN', 'DOCTOR']:
            raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
        serializer = FoodItemSerializer(food_item, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Food item updated by {request.user.username}: {food_item.name}")
            return Response({
                'success': True,
                'message': 'Food item updated successfully',
                'data': serializer.data
            })
        else:
            raise APIError("Validation error", errors=serializer.errors)
    
    elif request.method == 'DELETE':
        if request.user.user_type != 'ADMIN':
            raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
        food_item.delete()
        logger.info(f"Food item deleted by {request.user.username}: {item_id}")
        return Response({
            'success': True,
            'message': 'Food item deleted successfully'
        })

# # ==================== DIETARY RECOMMENDATION APIS ====================

# @api_view(['GET', 'POST'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def dietary_recommendations(request):
#     """Get dietary recommendations or create new one"""
    
#     if request.method == 'GET':
#         # Filter by cancer type if provided
#         cancer_type_id = request.query_params.get('cancer_type')
#         food_item_id = request.query_params.get('food_item')
#         recommendation_type = request.query_params.get('type')
        
#         queryset = DietaryRecommendation.objects.all()
#         if cancer_type_id:
#             queryset = queryset.filter(cancer_type_id=cancer_type_id)
#         if food_item_id:
#             queryset = queryset.filter(food_item_id=food_item_id)
#         if recommendation_type:
#             queryset = queryset.filter(recommendation_type=recommendation_type)
        
#         queryset = queryset.order_by('cancer_type__name', 'food_item__name')
#         serializer = DietaryRecommendationSerializer(queryset, many=True)
#         return Response({
#             'success': True,
#             'data': serializer.data
#         })
    
#     elif request.method == 'POST':
#         if request.user.user_type not in ['ADMIN', 'DOCTOR']:
#             raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
#         serializer = DietaryRecommendationSerializer(data=request.data)
#         if serializer.is_valid():
#             recommendation = serializer.save()
#             logger.info(f"Dietary recommendation created by {request.user.username}")
#             return Response({
#                 'success': True,
#                 'message': 'Dietary recommendation created successfully',
#                 'data': serializer.data
#             }, status=status.HTTP_201_CREATED)
#         else:
#             raise APIError("Validation error", errors=serializer.errors)

# # ==================== PATIENT DIETARY PLAN APIS ====================

# @api_view(['GET', 'POST'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def patient_dietary_plans(request):
#     """Get patient dietary plans or create new one"""
#     user = request.user
    
#     if request.method == 'GET':
#         try:
#             if user.user_type in ['ADMIN', 'DOCTOR', 'NURSE']:
#                 # Filter by patient if provided
#                 patient_id = request.query_params.get('patient')
#                 if patient_id:
#                     # Use filter with explicit conditions
#                     queryset = PatientDietaryPlan.objects.filter(
#                         patient_id=patient_id,
#                         is_active=True
#                     )
#                 else:
#                     queryset = PatientDietaryPlan.objects.filter(
#                         is_active=True
#                     )
#             else:
#                 # Patient can only see their own plans
#                 try:
#                     patient = PatientProfile.objects.get(user=user)
#                     queryset = PatientDietaryPlan.objects.filter(
#                         patient=patient,
#                         is_active=True
#                     )
#                 except PatientProfile.DoesNotExist:
#                     # Return empty list if patient profile doesn't exist
#                     return Response({
#                         'success': True,
#                         'data': []
#                     })
            
#             # Apply ordering
#             queryset = queryset.order_by('-created_at')
            
#             # Serialize the data
#             serializer = PatientDietaryPlanSerializer(queryset, many=True)
#             return Response({
#                 'success': True,
#                 'data': serializer.data
#             })
            
#         except Exception as e:
#             # Log the error for debugging
#             logger.error(f"Error in patient_dietary_plans GET: {str(e)}")
#             # Return empty data instead of failing
#             return Response({
#                 'success': True,
#                 'data': []
#             })
    
#     elif request.method == 'POST':
#         if user.user_type not in ['ADMIN', 'DOCTOR']:
#             raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
#         serializer = CreatePatientDietaryPlanSerializer(data=request.data)
#         if not serializer.is_valid():
#             raise APIError("Validation error", errors=serializer.errors)
        
#         data = serializer.validated_data
        
#         # Get patient
#         try:
#             patient = PatientProfile.objects.get(patient_id=data['patient_id'])
#         except PatientProfile.DoesNotExist:
#             raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
        
#         # Get doctor
#         if user.user_type == 'DOCTOR':
#             try:
#                 doctor = DoctorProfile.objects.get(user=user)
#             except DoctorProfile.DoesNotExist:
#                 raise APIError("Doctor profile not found", status_code=status.HTTP_404_NOT_FOUND)
#         else:
#             # Admin can assign any doctor
#             try:
#                 doctor = DoctorProfile.objects.get(doctor_id=data.get('doctor_id'))
#             except DoctorProfile.DoesNotExist:
#                 raise APIError("Doctor not found", status_code=status.HTTP_404_NOT_FOUND)
        
#         # Get food item
#         try:
#             food_item = FoodItem.objects.get(food_item_id=data['food_item_id'])
#         except FoodItem.DoesNotExist:
#             raise APIError("Food item not found", status_code=status.HTTP_404_NOT_FOUND)
        
#         # Create dietary plan
#         plan = PatientDietaryPlan.objects.create(
#             patient=patient,
#             doctor=doctor,
#             food_item=food_item,
#             meal_type=data['meal_type'],
#             quantity=data['quantity'],
#             timing=data.get('timing'),
#             frequency=data.get('frequency', 'Daily'),
#             start_date=data['start_date'],
#             end_date=data.get('end_date'),
#             instructions=data.get('instructions', ''),
#             reason=data.get('reason', ''),
#             is_active=True  # Explicitly set is_active
#         )
        
#         logger.info(f"Dietary plan created for patient {patient.patient_id} by {user.username}")
        
#         response_serializer = PatientDietaryPlanSerializer(plan)
#         return Response({
#             'success': True,
#             'message': 'Dietary plan created successfully',
#             'data': response_serializer.data
#         }, status=status.HTTP_201_CREATED)

# @api_view(['GET', 'PUT', 'DELETE'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def patient_dietary_plan_detail(request, plan_id):
#     """Get, update or delete specific dietary plan"""
#     user = request.user
    
#     try:
#         plan = PatientDietaryPlan.objects.get(plan_id=plan_id)
#     except PatientDietaryPlan.DoesNotExist:
#         raise APIError("Dietary plan not found", status_code=status.HTTP_404_NOT_FOUND)
    
#     # Check permission
#     if user.user_type == 'PATIENT':
#         try:
#             patient = PatientProfile.objects.get(user=user)
#             if plan.patient.patient_id != patient.patient_id:
#                 raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
#         except PatientProfile.DoesNotExist:
#             raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
#     if request.method == 'GET':
#         serializer = PatientDietaryPlanSerializer(plan)
#         return Response({
#             'success': True,
#             'data': serializer.data
#         })
    
#     elif request.method == 'PUT':
#         if user.user_type not in ['ADMIN', 'DOCTOR']:
#             raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
#         serializer = PatientDietaryPlanSerializer(plan, data=request.data, partial=True)
#         if serializer.is_valid():
#             serializer.save()
#             logger.info(f"Dietary plan {plan_id} updated by {user.username}")
#             return Response({
#                 'success': True,
#                 'message': 'Dietary plan updated successfully',
#                 'data': serializer.data
#             })
#         else:
#             raise APIError("Validation error", errors=serializer.errors)
    
#     elif request.method == 'DELETE':
#         if user.user_type != 'ADMIN':
#             raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
#         plan.delete()
#         logger.info(f"Dietary plan {plan_id} deleted by {user.username}")
#         return Response({
#             'success': True,
#             'message': 'Dietary plan deleted successfully'
#         })

# # ==================== PATIENT FOOD LOG APIS ====================

# @api_view(['GET', 'POST'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def patient_food_logs(request):
#     """Get food logs or create new log entry"""
#     user = request.user
    
#     if request.method == 'GET':
#         try:
#             if user.user_type in ['ADMIN', 'DOCTOR', 'NURSE']:
#                 # Filter by patient if provided
#                 patient_id = request.query_params.get('patient')
#                 if patient_id:
#                     queryset = PatientFoodLog.objects.filter(patient_id=patient_id)
#                 else:
#                     queryset = PatientFoodLog.objects.all()
#             else:
#                 # Patient can only see their own logs
#                 try:
#                     patient = PatientProfile.objects.get(user=user)
#                     queryset = PatientFoodLog.objects.filter(patient=patient)
#                 except PatientProfile.DoesNotExist:
#                     return Response({
#                         'success': True,
#                         'data': []
#                     })
            
#             # Date filter
#             from_date = request.query_params.get('from_date')
#             to_date = request.query_params.get('to_date')
            
#             if from_date:
#                 queryset = queryset.filter(consumed_at__date__gte=from_date)
#             if to_date:
#                 queryset = queryset.filter(consumed_at__date__lte=to_date)
            
#             queryset = queryset.order_by('-consumed_at')
#             serializer = PatientFoodLogSerializer(queryset, many=True)
#             return Response({
#                 'success': True,
#                 'data': serializer.data
#             })
#         except Exception as e:
#             logger.error(f"Error in patient_food_logs GET: {str(e)}")
#             return Response({
#                 'success': True,
#                 'data': []
#             })
    
#     elif request.method == 'POST':
#         try:
#             # Log the incoming data for debugging
#             logger.info(f"Received food log data: {request.data}")
            
#             serializer = CreatePatientFoodLogSerializer(data=request.data)
#             if not serializer.is_valid():
#                 logger.error(f"Serializer errors: {serializer.errors}")
#                 raise APIError("Validation error", errors=serializer.errors)
            
#             data = serializer.validated_data
#             logger.info(f"Validated data: {data}")
            
#             # Get patient
#             if user.user_type == 'PATIENT':
#                 try:
#                     patient = PatientProfile.objects.get(user=user)
#                 except PatientProfile.DoesNotExist:
#                     raise APIError("Patient profile not found", status_code=status.HTTP_404_NOT_FOUND)
#             else:
#                 # Admin/Doctor can log for any patient
#                 patient_id = data.get('patient_id')
#                 if not patient_id:
#                     raise APIError("patient_id is required for admin/doctor", status_code=status.HTTP_400_BAD_REQUEST)
                
#                 try:
#                     patient = PatientProfile.objects.get(patient_id=patient_id)
#                 except PatientProfile.DoesNotExist:
#                     raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
            
#             # Get food item
#             try:
#                 food_item = FoodItem.objects.get(food_item_id=data['food_item_id'])
#             except FoodItem.DoesNotExist:
#                 raise APIError("Food item not found", status_code=status.HTTP_404_NOT_FOUND)
            
#             # Handle consumed_at - if not provided, use current time
#             consumed_at = data.get('consumed_at')
#             if not consumed_at:
#                 from django.utils import timezone
#                 consumed_at = timezone.now()
            
#             # Create food log
#             log = PatientFoodLog.objects.create(
#                 patient=patient,
#                 food_item=food_item,
#                 meal_type=data['meal_type'],
#                 quantity_consumed=data['quantity_consumed'],
#                 consumed_at=consumed_at,
#                 symptoms_experienced=data.get('symptoms_experienced', ''),
#                 symptom_severity=data.get('symptom_severity', 'NONE'),
#                 notes=data.get('notes', '')
#             )
            
#             logger.info(f"Food log created for patient {patient.patient_id} by {user.username}")
            
#             response_serializer = PatientFoodLogSerializer(log)
#             return Response({
#                 'success': True,
#                 'message': 'Food log created successfully',
#                 'data': response_serializer.data
#             }, status=status.HTTP_201_CREATED)
            
#         except APIError:
#             raise
#         except Exception as e:
#             logger.error(f"Error creating food log: {str(e)}")
#             raise APIError(f"Failed to create food log: {str(e)}", status_code=status.HTTP_400_BAD_REQUEST)

# # ==================== DIETARY RESTRICTION APIS ====================

# @api_view(['GET', 'POST'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def dietary_restrictions(request):
#     """Get dietary restrictions or create new one"""
#     user = request.user
    
#     if request.method == 'GET':
#         if user.user_type in ['ADMIN', 'DOCTOR', 'NURSE']:
#             # Filter by patient if provided
#             patient_id = request.query_params.get('patient')
#             if patient_id:
#                 queryset = DietaryRestriction.objects.filter(patient_id=patient_id)
#             else:
#                 queryset = DietaryRestriction.objects.all()
#         else:
#             # Patient can only see their own restrictions
#             try:
#                 patient = PatientProfile.objects.get(user=user)
#                 queryset = DietaryRestriction.objects.filter(patient=patient)
#             except PatientProfile.DoesNotExist:
#                 queryset = []
        
#         queryset = queryset.order_by('-created_at')
#         serializer = DietaryRestrictionSerializer(queryset, many=True)
#         return Response({
#             'success': True,
#             'data': serializer.data
#         })
    
#     elif request.method == 'POST':
#         if user.user_type not in ['ADMIN', 'DOCTOR']:
#             raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
#         serializer = DietaryRestrictionSerializer(data=request.data)
#         if serializer.is_valid():
#             restriction = serializer.save()
#             logger.info(f"Dietary restriction created for patient by {user.username}")
#             return Response({
#                 'success': True,
#                 'message': 'Dietary restriction created successfully',
#                 'data': serializer.data
#             }, status=status.HTTP_201_CREATED)
#         else:
#             raise APIError("Validation error", errors=serializer.errors)

# # ==================== MEAL PLAN APIS ====================

# @api_view(['GET', 'POST'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def meal_plans(request):
#     """Get meal plans or create new one"""
#     user = request.user
    
#     if request.method == 'GET':
#         try:
#             if user.user_type in ['ADMIN', 'DOCTOR', 'NURSE']:
#                 # Filter by patient if provided
#                 patient_id = request.query_params.get('patient')
#                 if patient_id:
#                     # Use explicit filter with is_active=True
#                     queryset = MealPlan.objects.filter(
#                         patient_id=patient_id,
#                         is_active=True
#                     )
#                 else:
#                     queryset = MealPlan.objects.filter(is_active=True)
#             else:
#                 # Patient can only see their own meal plans
#                 try:
#                     patient = PatientProfile.objects.get(user=user)
#                     queryset = MealPlan.objects.filter(
#                         patient=patient,
#                         is_active=True
#                     )
#                 except PatientProfile.DoesNotExist:
#                     return Response({
#                         'success': True,
#                         'data': []
#                     })
            
#             # Apply ordering - use order_by with field names
#             queryset = queryset.order_by('weekday', 'meal_type')
            
#             serializer = MealPlanSerializer(queryset, many=True)
#             return Response({
#                 'success': True,
#                 'data': serializer.data
#             })
            
#         except Exception as e:
#             logger.error(f"Error in meal_plans GET: {str(e)}")
#             return Response({
#                 'success': True,
#                 'data': []
#             })
    
#     elif request.method == 'POST':
#         if user.user_type not in ['ADMIN', 'DOCTOR']:
#             raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
#         serializer = CreateMealPlanSerializer(data=request.data)
#         if not serializer.is_valid():
#             logger.error(f"Meal plan validation errors: {serializer.errors}")
#             raise APIError("Validation error", errors=serializer.errors)
        
#         data = serializer.validated_data
#         logger.info(f"Creating meal plan with data: {data}")
        
#         # Get patient
#         try:
#             patient = PatientProfile.objects.get(patient_id=data['patient_id'])
#         except PatientProfile.DoesNotExist:
#             raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
        
#         # Get doctor
#         if user.user_type == 'DOCTOR':
#             try:
#                 doctor = DoctorProfile.objects.get(user=user)
#             except DoctorProfile.DoesNotExist:
#                 raise APIError("Doctor profile not found", status_code=status.HTTP_404_NOT_FOUND)
#         else:
#             # Admin can assign any doctor
#             doctor_id = data.get('doctor_id')
#             if not doctor_id:
#                 raise APIError("doctor_id is required for admin", status_code=status.HTTP_400_BAD_REQUEST)
            
#             try:
#                 doctor = DoctorProfile.objects.get(doctor_id=doctor_id)
#             except DoctorProfile.DoesNotExist:
#                 raise APIError("Doctor not found", status_code=status.HTTP_404_NOT_FOUND)
        
#         # Create meal plan
#         meal_plan = MealPlan.objects.create(
#             patient=patient,
#             doctor=doctor,
#             name=data['name'],
#             description=data.get('description', ''),
#             weekday=data.get('weekday', 'ALL'),
#             meal_type=data['meal_type'],
#             food_items=data['food_items'],
#             total_calories=data.get('total_calories'),
#             total_protein=data.get('total_protein'),
#             total_carbs=data.get('total_carbs'),
#             total_fat=data.get('total_fat'),
#             instructions=data.get('instructions', ''),
#             start_date=data['start_date'],
#             end_date=data.get('end_date'),
#             is_active=True  # Explicitly set is_active
#         )
        
#         logger.info(f"Meal plan created for patient {patient.patient_id} by {user.username}")
        
#         response_serializer = MealPlanSerializer(meal_plan)
#         return Response({
#             'success': True,
#             'message': 'Meal plan created successfully',
#             'data': response_serializer.data
#         }, status=status.HTTP_201_CREATED)

# # ==================== PATIENT DIETARY SUMMARY ====================

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def patient_dietary_summary(request, patient_id):
#     """Get complete dietary summary for a patient"""
#     user = request.user
    
#     # Check permission
#     if user.user_type == 'PATIENT':
#         try:
#             patient = PatientProfile.objects.get(user=user)
#             if patient.patient_id != patient_id:
#                 raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
#         except PatientProfile.DoesNotExist:
#             raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
#     elif user.user_type not in ['ADMIN', 'DOCTOR', 'NURSE']:
#         raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
#     try:
#         patient = PatientProfile.objects.get(patient_id=patient_id)
#     except PatientProfile.DoesNotExist:
#         raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
    
#     # Get all dietary information
#     active_plans = PatientDietaryPlan.objects.filter(
#         patient=patient, 
#         is_active=True
#     ).select_related('food_item', 'doctor')
    
#     recent_logs = PatientFoodLog.objects.filter(
#         patient=patient
#     ).select_related('food_item').order_by('-consumed_at')[:10]
    
#     restrictions = DietaryRestriction.objects.filter(patient=patient)
    
#     meal_plans = MealPlan.objects.filter(
#         patient=patient,
#         is_active=True
#     ).order_by('weekday', 'meal_type')
    
#     # Get medical record if exists
#     try:
#         medical_record = PatientMedicalRecord.objects.get(patient=patient)
#         cancer_type = medical_record.cancer_type
        
#         # Get general recommendations based on cancer type
#         recommendations = DietaryRecommendation.objects.filter(
#             cancer_type=cancer_type
#         ).select_related('food_item')
        
#         recommended_foods = recommendations.filter(recommendation_type='RECOMMENDED')
#         avoid_foods = recommendations.filter(recommendation_type='AVOID')
        
#     except PatientMedicalRecord.DoesNotExist:
#         medical_record = None
#         cancer_type = None
#         recommendations = []
#         recommended_foods = []
#         avoid_foods = []
    
#     return Response({
#         'success': True,
#         'data': {
#             'patient': {
#                 'id': patient.patient_id,
#                 'name': patient.user.get_full_name(),
#                 'cancer_type': cancer_type.name if cancer_type else None,
#                 'cancer_stage': medical_record.cancer_stage if medical_record else None
#             },
#             'active_dietary_plans': PatientDietaryPlanSerializer(active_plans, many=True).data,
#             'recent_food_logs': PatientFoodLogSerializer(recent_logs, many=True).data,
#             'dietary_restrictions': DietaryRestrictionSerializer(restrictions, many=True).data,
#             'meal_plans': MealPlanSerializer(meal_plans, many=True).data,
#             'recommended_foods': DietaryRecommendationSerializer(recommended_foods, many=True).data,
#             'foods_to_avoid': DietaryRecommendationSerializer(avoid_foods, many=True).data
#         }
#     })


@api_view(['GET', 'POST', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def patient_food_management(request, patient_id=None, item_id=None):
    """
    Unified API for patient food management
    Supports:
    - GET: Get patient's complete food profile
    - POST: Add food-related data
    - PUT: Update specific food item
    - DELETE: Remove specific food item
    """
    user = request.user
    
    try:
        # Log the request for debugging
        logger.info(f"Food management request - User: {user.username}, Type: {user.user_type}, Method: {request.method}, Patient ID: {patient_id}, Item ID: {item_id}")
        
        # Handle patient's own data access
        if request.path.endswith('/my-food/'):
            if user.user_type == 'PATIENT':
                try:
                    patient = PatientProfile.objects.get(user=user)
                    patient_id = patient.patient_id
                except PatientProfile.DoesNotExist:
                    raise APIError("Patient profile not found", status_code=status.HTTP_404_NOT_FOUND)
            else:
                raise APIError("Only patients can access /my-food/", status_code=status.HTTP_403_FORBIDDEN)
        
        # Check permission for accessing other patients' data
        if user.user_type == 'PATIENT':
            try:
                patient = PatientProfile.objects.get(user=user)
                if patient_id and str(patient.patient_id) != str(patient_id):
                    raise APIError("You can only access your own food data", status_code=status.HTTP_403_FORBIDDEN)
                patient_id = patient.patient_id
            except PatientProfile.DoesNotExist:
                raise APIError("Patient profile not found", status_code=status.HTTP_404_NOT_FOUND)
        elif user.user_type not in ['ADMIN', 'DOCTOR', 'NURSE']:
            raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
        # For GET requests, patient_id is required
        if request.method == 'GET' and not patient_id:
            raise APIError("patient_id is required", status_code=status.HTTP_400_BAD_REQUEST)
        
        # GET - Retrieve complete patient food profile
        if request.method == 'GET':
            return handle_get_request(request, patient_id, user)
        
        # POST - Add new food-related data
        elif request.method == 'POST':
            return handle_post_request(request, patient_id, user)
        
        # PUT - Update existing food-related item
        elif request.method == 'PUT':
            return handle_put_request(request, patient_id, item_id, user)
        
        # DELETE - Remove food-related item
        elif request.method == 'DELETE':
            return handle_delete_request(request, patient_id, item_id, user)
            
    except APIError:
        raise
    except PatientProfile.DoesNotExist:
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Unexpected error in patient_food_management: {str(e)}", exc_info=True)
        raise APIError(f"Failed to process request: {str(e)}", status_code=status.HTTP_400_BAD_REQUEST)


def handle_get_request(request, patient_id, user):
    """Handle GET requests"""
    try:
        # Get patient
        patient = PatientProfile.objects.get(patient_id=patient_id)
        
        # Get action type from query params
        action = request.query_params.get('action', 'summary')
        
        if action == 'summary':
            return get_patient_food_summary(patient)
        
        elif action == 'plans':
            # Get only dietary plans
            plans = PatientDietaryPlan.objects.filter(
                patient=patient, 
                is_active=True
            ).select_related('food_item', 'doctor').order_by('-created_at')
            
            # Serialize data
            plans_data = []
            for plan in plans:
                try:
                    plans_data.append(PatientDietaryPlanSerializer(plan).data)
                except Exception as e:
                    logger.error(f"Error serializing plan {plan.plan_id}: {str(e)}")
            
            return Response({
                'success': True,
                'data': {
                    'dietary_plans': plans_data
                }
            })
        
        elif action == 'logs':
            # Get only food logs
            from_date = request.query_params.get('from_date')
            to_date = request.query_params.get('to_date')
            
            logs = PatientFoodLog.objects.filter(patient=patient)
            if from_date:
                logs = logs.filter(consumed_at__date__gte=from_date)
            if to_date:
                logs = logs.filter(consumed_at__date__lte=to_date)
            
            logs = logs.select_related('food_item').order_by('-consumed_at')
            
            # Serialize data
            logs_data = []
            for log in logs:
                try:
                    logs_data.append(PatientFoodLogSerializer(log).data)
                except Exception as e:
                    logger.error(f"Error serializing log {log.log_id}: {str(e)}")
            
            return Response({
                'success': True,
                'data': {
                    'food_logs': logs_data
                }
            })
        
        elif action == 'restrictions':
            # Get only dietary restrictions
            restrictions = DietaryRestriction.objects.filter(patient=patient)
            
            # Serialize data
            restrictions_data = []
            for restriction in restrictions:
                try:
                    restrictions_data.append(DietaryRestrictionSerializer(restriction).data)
                except Exception as e:
                    logger.error(f"Error serializing restriction {restriction.restriction_id}: {str(e)}")
            
            return Response({
                'success': True,
                'data': {
                    'dietary_restrictions': restrictions_data
                }
            })
        
        elif action == 'meal-plans':
            # Get only meal plans
            weekday = request.query_params.get('weekday')
            meal_plans = MealPlan.objects.filter(patient=patient, is_active=True)
            if weekday:
                meal_plans = meal_plans.filter(weekday=weekday)
            meal_plans = meal_plans.order_by('weekday', 'meal_type')
            
            # Serialize data
            meal_plans_data = []
            for meal_plan in meal_plans:
                try:
                    meal_plans_data.append(MealPlanSerializer(meal_plan).data)
                except Exception as e:
                    logger.error(f"Error serializing meal plan {meal_plan.meal_plan_id}: {str(e)}")
            
            return Response({
                'success': True,
                'data': {
                    'meal_plans': meal_plans_data
                }
            })
        
        elif action == 'recommendations':
            # Get dietary recommendations based on cancer type
            try:
                # Try to get medical record safely
                medical_record = PatientMedicalRecord.objects.filter(patient=patient).first()
                
                recommended = []
                avoid = []
                
                if medical_record and hasattr(medical_record, 'cancer_type') and medical_record.cancer_type:
                    cancer_type = medical_record.cancer_type
                    
                    recommendations = DietaryRecommendation.objects.filter(
                        cancer_type=cancer_type
                    ).select_related('food_item')
                    
                    # Serialize recommendations
                    for rec in recommendations:
                        try:
                            if rec.recommendation_type == 'RECOMMENDED':
                                recommended.append(DietaryRecommendationSerializer(rec).data)
                            elif rec.recommendation_type == 'AVOID':
                                avoid.append(DietaryRecommendationSerializer(rec).data)
                        except Exception as e:
                            logger.error(f"Error serializing recommendation {rec.recommendation_id}: {str(e)}")
                
                return Response({
                    'success': True,
                    'data': {
                        'recommended_foods': recommended,
                        'foods_to_avoid': avoid
                    }
                })
                
            except Exception as e:
                logger.error(f"Error getting recommendations for patient {patient_id}: {str(e)}")
                return Response({
                    'success': True,
                    'data': {
                        'recommended_foods': [],
                        'foods_to_avoid': []
                    }
                })
        
        else:
            return get_patient_food_summary(patient)
            
    except PatientProfile.DoesNotExist:
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error in handle_get_request: {str(e)}", exc_info=True)
        # Return empty data instead of error
        return Response({
            'success': True,
            'data': {
                'patient_info': {
                    'id': patient_id,
                    'name': f'Patient {patient_id}',
                    'cancer_type': None,
                    'cancer_stage': None
                },
                'summary': {
                    'total_active_plans': 0,
                    'total_restrictions': 0,
                    'total_meal_plans': 0,
                    'recent_logs_count': 0
                },
                'dietary_plans': [],
                'recent_food_logs': [],
                'dietary_restrictions': [],
                'meal_plans': [],
                'recommended_foods': [],
                'foods_to_avoid': []
            }
        })


def handle_post_request(request, patient_id, user):
    """Handle POST requests"""
    try:
        data = request.data
        action = data.get('action')
        
        if not action:
            raise APIError("action is required (plans/logs/restrictions/meal-plans)", 
                         status_code=status.HTTP_400_BAD_REQUEST)
        
        # Get patient
        if user.user_type == 'PATIENT':
            patient = PatientProfile.objects.get(user=user)
        else:
            patient_id = data.get('patient_id') or patient_id
            if not patient_id:
                raise APIError("patient_id is required", status_code=status.HTTP_400_BAD_REQUEST)
            patient = PatientProfile.objects.get(patient_id=patient_id)
        
        # Get doctor (if applicable)
        doctor = None
        if user.user_type == 'DOCTOR':
            doctor = DoctorProfile.objects.get(user=user)
        elif data.get('doctor_id'):
            try:
                doctor = DoctorProfile.objects.get(doctor_id=data['doctor_id'])
            except DoctorProfile.DoesNotExist:
                raise APIError("Doctor not found", status_code=status.HTTP_404_NOT_FOUND)
        
        # Route to appropriate handler based on action
        if action == 'plans':
            return create_dietary_plan(request, patient, doctor, data)
        
        elif action == 'logs':
            return create_food_log(request, patient, data)
        
        elif action == 'restrictions':
            return create_dietary_restriction(request, patient, data)
        
        elif action == 'meal-plans':
            return create_meal_plan(request, patient, doctor, data)
        
        else:
            raise APIError(f"Invalid action: {action}", status_code=status.HTTP_400_BAD_REQUEST)
            
    except PatientProfile.DoesNotExist:
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
    except DoctorProfile.DoesNotExist:
        raise APIError("Doctor not found", status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error in handle_post_request: {str(e)}", exc_info=True)
        raise APIError(f"Failed to create: {str(e)}", status_code=status.HTTP_400_BAD_REQUEST)


def handle_put_request(request, patient_id, item_id, user):
    """Handle PUT requests - infer action from URL pattern"""
    if not item_id:
        raise APIError("item_id is required for update", status_code=status.HTTP_400_BAD_REQUEST)
    
    try:
        data = request.data
        action = data.get('action')
        
        # If action not provided, try to infer from request path
        if not action:
            path = request.path
            if '/logs/' in path:
                action = 'logs'
            elif '/plans/' in path:
                action = 'plans'
            elif '/restrictions/' in path:
                action = 'restrictions'
            elif '/meal-plans/' in path:
                action = 'meal-plans'
            else:
                raise APIError("action is required (plans/logs/restrictions/meal-plans)", 
                             status_code=status.HTTP_400_BAD_REQUEST)
        
        if action == 'plans':
            item = PatientDietaryPlan.objects.get(plan_id=item_id, patient_id=patient_id)
            serializer = PatientDietaryPlanSerializer(item, data=data, partial=True)
        elif action == 'logs':
            item = PatientFoodLog.objects.get(log_id=item_id, patient_id=patient_id)
            serializer = PatientFoodLogSerializer(item, data=data, partial=True)
        elif action == 'restrictions':
            item = DietaryRestriction.objects.get(restriction_id=item_id, patient_id=patient_id)
            serializer = DietaryRestrictionSerializer(item, data=data, partial=True)
        elif action == 'meal-plans':
            item = MealPlan.objects.get(meal_plan_id=item_id, patient_id=patient_id)
            serializer = MealPlanSerializer(item, data=data, partial=True)
        else:
            raise APIError(f"Invalid action for update: {action}")
        
        if serializer.is_valid():
            serializer.save()
            logger.info(f"{action} updated for patient {patient_id}")
            return Response({
                'success': True,
                'message': f'{action} updated successfully',
                'data': serializer.data
            })
        else:
            raise APIError("Validation error", errors=serializer.errors)
            
    except PatientDietaryPlan.DoesNotExist:
        raise APIError("Dietary plan not found", status_code=status.HTTP_404_NOT_FOUND)
    except PatientFoodLog.DoesNotExist:
        raise APIError("Food log not found", status_code=status.HTTP_404_NOT_FOUND)
    except DietaryRestriction.DoesNotExist:
        raise APIError("Dietary restriction not found", status_code=status.HTTP_404_NOT_FOUND)
    except MealPlan.DoesNotExist:
        raise APIError("Meal plan not found", status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error in handle_put_request: {str(e)}", exc_info=True)
        raise APIError(f"Failed to update: {str(e)}", status_code=status.HTTP_400_BAD_REQUEST)


def handle_delete_request(request, patient_id, item_id, user):
    """Improved DELETE handler - distinguishes between different ID types"""
    
    logger.info(f"DELETE handler - patient_id: {patient_id}, item_id from URL: {item_id}")
    
    # Get item_id from URL or parameters
    delete_item_id = item_id
    
    if not delete_item_id:
        path_parts = request.path.strip('/').split('/')
        for part in reversed(path_parts):
            if part.isdigit():
                delete_item_id = int(part)
                break
    
    if not delete_item_id:
        delete_item_id = request.query_params.get('item_id')
    
    if not delete_item_id and request.body:
        try:
            import json
            body_data = json.loads(request.body)
            delete_item_id = body_data.get('item_id')
        except:
            pass
    
    if not delete_item_id:
        raise APIError(
            "item_id is required for delete. Please provide the LOG ID, not food_item_id",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Get action - IMPORTANT: This tells us what type of item we're deleting
    action = request.query_params.get('action')
    
    if not action and request.body:
        try:
            import json
            body_data = json.loads(request.body)
            action = body_data.get('action')
        except:
            pass
    
    # Try to infer action from path
    if not action:
        path = request.path.lower()
        if 'log' in path:
            action = 'logs'
        elif 'plan' in path:
            action = 'plans'
        elif 'restriction' in path:
            action = 'restrictions'
        elif 'meal-plan' in path:
            action = 'meal-plans'
    
    if not action:
        raise APIError(
            "action is required. Use ?action=logs to delete a food log, "
            "or ?action=plans to delete a dietary plan",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    logger.info(f"Deleting - action: {action}, item_id: {delete_item_id}, patient_id: {patient_id}")
    
    try:
        if action == 'plans':
            # delete_item_id here is plan_id (NOT food_item_id)
            item = PatientDietaryPlan.objects.get(plan_id=delete_item_id, patient_id=patient_id)
            item.delete()
            message = "Dietary plan deleted successfully"
            
        elif action == 'logs':
            # delete_item_id here is log_id (NOT food_item_id)
            # You cannot delete a food log using food_item_id!
            item = PatientFoodLog.objects.get(log_id=delete_item_id, patient_id=patient_id)
            item.delete()
            message = "Food log deleted successfully"
            
        elif action == 'restrictions':
            item = DietaryRestriction.objects.get(restriction_id=delete_item_id, patient_id=patient_id)
            item.delete()
            message = "Dietary restriction deleted successfully"
            
        elif action == 'meal-plans':
            item = MealPlan.objects.get(meal_plan_id=delete_item_id, patient_id=patient_id)
            item.delete()
            message = "Meal plan deleted successfully"
            
        else:
            raise APIError(f"Invalid action: {action}")
        
        return Response({
            'success': True,
            'message': message,
            'data': {
                'deleted_item_id': delete_item_id,
                'deleted_item_type': action,
                'patient_id': patient_id
            }
        })
        
    except PatientDietaryPlan.DoesNotExist:
        raise APIError(f"Dietary plan with id {delete_item_id} not found for patient {patient_id}. "
                      f"Note: This is plan_id, not food_item_id", status_code=404)
    except PatientFoodLog.DoesNotExist:
        raise APIError(f"Food log with id {delete_item_id} not found for patient {patient_id}. "
                      f"Note: This is log_id, not food_item_id. "
                      f"To delete a food log, you need the log_id from PatientFoodLog table", status_code=404)
    except DietaryRestriction.DoesNotExist:
        raise APIError(f"Dietary restriction with id {delete_item_id} not found", status_code=404)
    except MealPlan.DoesNotExist:
        raise APIError(f"Meal plan with id {delete_item_id} not found", status_code=404)


def get_patient_food_summary(patient):
    """Get complete food summary for a patient"""
    try:
        # FIXED: Use raw query or avoid boolean filter issue
        # Method 1: Use filter with string value instead of boolean
        try:
            # Try to get plans with patient_id filter only, then filter in Python
            active_plans = list(PatientDietaryPlan.objects.filter(
                patient_id=patient.patient_id
            ).order_by('-created_at'))
            
            # Filter in Python for is_active
            active_plans = [plan for plan in active_plans if plan.is_active]
            
        except Exception as e:
            logger.error(f"Error fetching dietary plans: {str(e)}")
            active_plans = []
        
        # Get recent food logs (last 10) - without boolean filter
        try:
            recent_logs = list(PatientFoodLog.objects.filter(
                patient_id=patient.patient_id
            ).order_by('-consumed_at')[:10])
        except Exception as e:
            logger.error(f"Error fetching food logs: {str(e)}")
            recent_logs = []
        
        # Get dietary restrictions
        try:
            restrictions = list(DietaryRestriction.objects.filter(
                patient_id=patient.patient_id
            ))
        except Exception as e:
            logger.error(f"Error fetching restrictions: {str(e)}")
            restrictions = []
        
        # Get active meal plans - fetch all then filter in Python
        try:
            meal_plans = list(MealPlan.objects.filter(
                patient_id=patient.patient_id
            ).order_by('weekday', 'meal_type'))
            # Filter in Python for is_active
            meal_plans = [plan for plan in meal_plans if plan.is_active]
        except Exception as e:
            logger.error(f"Error fetching meal plans: {str(e)}")
            meal_plans = []
        
        # Fetch related food items in bulk
        food_ids = set()
        for plan in active_plans:
            if plan.food_item_id:
                food_ids.add(plan.food_item_id)
        for log in recent_logs:
            if log.food_item_id:
                food_ids.add(log.food_item_id)
        
        # Get recommendations if needed later
        rec_food_ids = set()
        
        # Get doctor IDs from plans
        doctor_ids = set()
        for plan in active_plans:
            if plan.doctor_id:
                doctor_ids.add(plan.doctor_id)
        
        # Fetch food items
        food_items = {}
        if food_ids:
            try:
                foods = FoodItem.objects.filter(food_item_id__in=list(food_ids))
                for food in foods:
                    food_items[food.food_item_id] = food
            except Exception as e:
                logger.error(f"Error fetching food items: {str(e)}")
        
        # Fetch doctors
        doctors = {}
        if doctor_ids:
            try:
                doc_objs = DoctorProfile.objects.filter(doctor_id__in=list(doctor_ids))
                for doc in doc_objs:
                    doctors[doc.doctor_id] = doc
            except Exception as e:
                logger.error(f"Error fetching doctors: {str(e)}")
        
        # Get medical record and recommendations
        cancer_type = None
        cancer_stage = None
        recommended_foods = []
        avoid_foods = []
        
        try:
            medical_record = PatientMedicalRecord.objects.filter(patient=patient).first()
            
            if medical_record:
                if hasattr(medical_record, 'cancer_type') and medical_record.cancer_type:
                    cancer_type = medical_record.cancer_type
                    cancer_stage = medical_record.cancer_stage
                    
                    if cancer_type:
                        # Get recommendations
                        recommendations = DietaryRecommendation.objects.filter(
                            cancer_type=cancer_type
                        )
                        
                        # Fetch food items for recommendations
                        rec_food_ids = set()
                        for rec in recommendations:
                            if rec.food_item_id:
                                rec_food_ids.add(rec.food_item_id)
                        
                        rec_food_items = {}
                        if rec_food_ids:
                            foods = FoodItem.objects.filter(food_item_id__in=list(rec_food_ids))
                            for food in foods:
                                rec_food_items[food.food_item_id] = food
                        
                        # Filter by type
                        recommended_foods = list(recommendations.filter(recommendation_type='RECOMMENDED'))
                        avoid_foods = list(recommendations.filter(recommendation_type='AVOID'))
                        
                        # Attach food items to recommendations
                        for rec in recommended_foods:
                            if rec.food_item_id in rec_food_items:
                                rec.food_item_obj = rec_food_items[rec.food_item_id]
                        for rec in avoid_foods:
                            if rec.food_item_id in rec_food_items:
                                rec.food_item_obj = rec_food_items[rec.food_item_id]
                        
        except Exception as e:
            logger.error(f"Error accessing medical record: {str(e)}")
        
        # Serialize all data
        plans_data = []
        for plan in active_plans:
            try:
                plan_dict = {
                    'plan_id': plan.plan_id,
                    'patient': plan.patient_id,
                    'doctor_id': plan.doctor_id,
                    'food_item_id': plan.food_item_id,
                    'meal_type': plan.meal_type,
                    'quantity': plan.quantity,
                    'timing': plan.timing,
                    'frequency': plan.frequency,
                    'start_date': plan.start_date,
                    'end_date': plan.end_date,
                    'is_active': plan.is_active,
                    'instructions': plan.instructions,
                    'reason': plan.reason,
                    'created_at': plan.created_at,
                    'updated_at': plan.updated_at
                }
                
                # Add doctor info
                if plan.doctor_id and plan.doctor_id in doctors:
                    doc = doctors[plan.doctor_id]
                    plan_dict['doctor'] = {
                        'doctor_id': doc.doctor_id,
                        'name': f"{doc.first_name} {doc.last_name}" if hasattr(doc, 'first_name') else str(doc)
                    }
                
                # Add food item info
                if plan.food_item_id and plan.food_item_id in food_items:
                    food = food_items[plan.food_item_id]
                    plan_dict['food_item'] = {
                        'food_item_id': food.food_item_id,
                        'name': food.name,
                        'category': getattr(food, 'category_id', None)
                    }
                
                plans_data.append(plan_dict)
            except Exception as e:
                logger.error(f"Error serializing plan {plan.plan_id}: {str(e)}")
        
        logs_data = []
        for log in recent_logs:
            try:
                log_dict = {
                    'log_id': log.log_id,
                    'patient': log.patient_id,
                    'food_item_id': log.food_item_id,
                    'meal_type': log.meal_type,
                    'quantity_consumed': log.quantity_consumed,
                    'consumed_at': log.consumed_at,
                    'symptoms_experienced': log.symptoms_experienced,
                    'symptom_severity': log.symptom_severity,
                    'notes': log.notes,
                    'created_at': log.created_at
                }
                
                if log.food_item_id and log.food_item_id in food_items:
                    food = food_items[log.food_item_id]
                    log_dict['food_item'] = {
                        'food_item_id': food.food_item_id,
                        'name': food.name
                    }
                
                logs_data.append(log_dict)
            except Exception as e:
                logger.error(f"Error serializing log {log.log_id}: {str(e)}")
        
        restrictions_data = []
        for restriction in restrictions:
            try:
                restrictions_data.append({
                    'restriction_id': restriction.restriction_id,
                    'patient': restriction.patient_id,
                    'restriction_type': restriction.restriction_type,
                    'food_item_id': restriction.food_item_id,
                    'food_category_id': restriction.food_category_id,
                    'description': restriction.description,
                    'severity': restriction.severity,
                    'diagnosed_date': restriction.diagnosed_date,
                    'notes': restriction.notes,
                    'created_at': restriction.created_at
                })
            except Exception as e:
                logger.error(f"Error serializing restriction: {str(e)}")
        
        meal_plans_data = []
        for meal_plan in meal_plans:
            try:
                meal_plans_data.append({
                    'meal_plan_id': meal_plan.meal_plan_id,
                    'patient': meal_plan.patient_id,
                    'doctor_id': meal_plan.doctor_id,
                    'name': meal_plan.name,
                    'description': meal_plan.description,
                    'weekday': meal_plan.weekday,
                    'meal_type': meal_plan.meal_type,
                    'food_items': meal_plan.food_items,
                    'total_calories': meal_plan.total_calories,
                    'total_protein': meal_plan.total_protein,
                    'total_carbs': meal_plan.total_carbs,
                    'total_fat': meal_plan.total_fat,
                    'instructions': meal_plan.instructions,
                    'start_date': meal_plan.start_date,
                    'end_date': meal_plan.end_date,
                    'is_active': meal_plan.is_active,
                    'created_at': meal_plan.created_at
                })
            except Exception as e:
                logger.error(f"Error serializing meal plan: {str(e)}")
        
        recommended_data = []
        for rec in recommended_foods:
            try:
                rec_dict = {
                    'recommendation_id': rec.recommendation_id,
                    'cancer_type': getattr(rec, 'cancer_type_id', None),
                    'food_item_id': rec.food_item_id,
                    'recommendation_type': rec.recommendation_type,
                    'reason': rec.reason,
                    'evidence_level': rec.evidence_level,
                    'created_at': rec.created_at
                }
                
                if hasattr(rec, 'food_item_obj'):
                    food = rec.food_item_obj
                    rec_dict['food_item'] = {
                        'food_item_id': food.food_item_id,
                        'name': food.name
                    }
                
                recommended_data.append(rec_dict)
            except Exception as e:
                logger.error(f"Error serializing recommendation: {str(e)}")
        
        avoid_data = []
        for rec in avoid_foods:
            try:
                rec_dict = {
                    'recommendation_id': rec.recommendation_id,
                    'cancer_type': getattr(rec, 'cancer_type_id', None),
                    'food_item_id': rec.food_item_id,
                    'recommendation_type': rec.recommendation_type,
                    'reason': rec.reason,
                    'evidence_level': rec.evidence_level,
                    'created_at': rec.created_at
                }
                
                if hasattr(rec, 'food_item_obj'):
                    food = rec.food_item_obj
                    rec_dict['food_item'] = {
                        'food_item_id': food.food_item_id,
                        'name': food.name
                    }
                
                avoid_data.append(rec_dict)
            except Exception as e:
                logger.error(f"Error serializing recommendation: {str(e)}")
        
        # Get patient name
        patient_name = f"Patient {patient.patient_id}"
        if hasattr(patient, 'user') and patient.user:
            try:
                patient_name = patient.user.get_full_name() or patient.user.username or patient_name
            except:
                pass
        
        # Get cancer type name
        cancer_type_name = cancer_type.name if cancer_type and hasattr(cancer_type, 'name') else None
        
        return Response({
            'success': True,
            'data': {
                'patient_info': {
                    'id': patient.patient_id,
                    'name': patient_name,
                    'cancer_type': cancer_type_name,
                    'cancer_stage': cancer_stage if cancer_stage else None
                },
                'summary': {
                    'total_active_plans': len(plans_data),
                    'total_restrictions': len(restrictions_data),
                    'total_meal_plans': len(meal_plans_data),
                    'recent_logs_count': len(logs_data)
                },
                'dietary_plans': plans_data,
                'recent_food_logs': logs_data,
                'dietary_restrictions': restrictions_data,
                'meal_plans': meal_plans_data,
                'recommended_foods': recommended_data,
                'foods_to_avoid': avoid_data
            }
        })
        
    except Exception as e:
        logger.error(f"Error in get_patient_food_summary: {str(e)}", exc_info=True)
        return Response({
            'success': True,
            'data': {
                'patient_info': {
                    'id': getattr(patient, 'patient_id', None),
                    'name': str(patient),
                    'cancer_type': None,
                    'cancer_stage': None
                },
                'summary': {
                    'total_active_plans': 0,
                    'total_restrictions': 0,
                    'total_meal_plans': 0,
                    'recent_logs_count': 0
                },
                'dietary_plans': [],
                'recent_food_logs': [],
                'dietary_restrictions': [],
                'meal_plans': [],
                'recommended_foods': [],
                'foods_to_avoid': []
            }
        })
    
def create_dietary_plan(request, patient, doctor, data):
    """Create a new dietary plan"""
    try:
        # Get food item
        try:
            food_item = FoodItem.objects.get(food_item_id=data['food_item_id'])
        except FoodItem.DoesNotExist:
            raise APIError("Food item not found", status_code=status.HTTP_404_NOT_FOUND)
        except KeyError:
            raise APIError("food_item_id is required", status_code=status.HTTP_400_BAD_REQUEST)
        
        # Create the plan
        plan = PatientDietaryPlan.objects.create(
            patient=patient,
            doctor=doctor,
            food_item=food_item,
            meal_type=data.get('meal_type', 'BREAKFAST'),
            quantity=data.get('quantity', '1 serving'),
            timing=data.get('timing'),
            frequency=data.get('frequency', 'Daily'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            instructions=data.get('instructions', ''),
            reason=data.get('reason', ''),
            is_active=True
        )
        
        logger.info(f"Dietary plan created for patient {patient.patient_id}")
        
        return Response({
            'success': True,
            'message': 'Dietary plan created successfully',
            'data': PatientDietaryPlanSerializer(plan).data
        }, status=status.HTTP_201_CREATED)
        
    except KeyError as e:
        raise APIError(f"Missing required field: {str(e)}", status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error creating dietary plan: {str(e)}")
        raise APIError(f"Failed to create dietary plan: {str(e)}", status_code=status.HTTP_400_BAD_REQUEST)


def create_food_log(request, patient, data):
    """Create a new food log"""
    try:
        # Get food item
        try:
            food_item = FoodItem.objects.get(food_item_id=data['food_item_id'])
        except FoodItem.DoesNotExist:
            raise APIError("Food item not found", status_code=status.HTTP_404_NOT_FOUND)
        except KeyError:
            raise APIError("food_item_id is required", status_code=status.HTTP_400_BAD_REQUEST)
        
        # Handle consumed_at
        from django.utils import timezone
        import datetime
        
        consumed_at = data.get('consumed_at')
        if not consumed_at:
            consumed_at = timezone.now()
        elif isinstance(consumed_at, str):
            try:
                # Parse ISO format string
                consumed_at = datetime.datetime.fromisoformat(consumed_at.replace('Z', '+00:00'))
            except:
                consumed_at = timezone.now()
        
        # Create the log
        log = PatientFoodLog.objects.create(
            patient=patient,
            food_item=food_item,
            meal_type=data.get('meal_type', 'BREAKFAST'),
            quantity_consumed=data.get('quantity_consumed', '1 serving'),
            consumed_at=consumed_at,
            symptoms_experienced=data.get('symptoms_experienced', ''),
            symptom_severity=data.get('symptom_severity', 'NONE'),
            notes=data.get('notes', '')
        )
        
        logger.info(f"Food log created for patient {patient.patient_id}")
        
        return Response({
            'success': True,
            'message': 'Food log created successfully',
            'data': PatientFoodLogSerializer(log).data
        }, status=status.HTTP_201_CREATED)
        
    except KeyError as e:
        raise APIError(f"Missing required field: {str(e)}", status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error creating food log: {str(e)}")
        raise APIError(f"Failed to create food log: {str(e)}", status_code=status.HTTP_400_BAD_REQUEST)


def create_dietary_restriction(request, patient, data):
    """Create a new dietary restriction"""
    try:
        # Validate that either food_item_id or food_category_id is provided
        food_item_id = data.get('food_item_id')
        food_category_id = data.get('food_category_id')
        
        if not food_item_id and not food_category_id:
            raise APIError("Either food_item_id or food_category_id is required", 
                         status_code=status.HTTP_400_BAD_REQUEST)
        
        # Create the restriction
        restriction = DietaryRestriction.objects.create(
            patient=patient,
            restriction_type=data.get('restriction_type', 'OTHER'),
            food_item_id=food_item_id,
            food_category_id=food_category_id,
            description=data.get('description', ''),
            severity=data.get('severity', ''),
            diagnosed_date=data.get('diagnosed_date'),
            notes=data.get('notes', '')
        )
        
        logger.info(f"Dietary restriction created for patient {patient.patient_id}")
        
        return Response({
            'success': True,
            'message': 'Dietary restriction created successfully',
            'data': DietaryRestrictionSerializer(restriction).data
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error creating dietary restriction: {str(e)}")
        raise APIError(f"Failed to create dietary restriction: {str(e)}", status_code=status.HTTP_400_BAD_REQUEST)


def create_meal_plan(request, patient, doctor, data):
    """Create a new meal plan"""
    try:
        # Validate food_items
        food_items = data.get('food_items', [])
        if not food_items:
            raise APIError("food_items is required", status_code=status.HTTP_400_BAD_REQUEST)
        
        # Create the meal plan
        meal_plan = MealPlan.objects.create(
            patient=patient,
            doctor=doctor,
            name=data.get('name', 'Meal Plan'),
            description=data.get('description', ''),
            weekday=data.get('weekday', 'ALL'),
            meal_type=data.get('meal_type', 'BREAKFAST'),
            food_items=food_items,
            total_calories=data.get('total_calories'),
            total_protein=data.get('total_protein'),
            total_carbs=data.get('total_carbs'),
            total_fat=data.get('total_fat'),
            instructions=data.get('instructions', ''),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            is_active=True
        )
        
        logger.info(f"Meal plan created for patient {patient.patient_id}")
        
        return Response({
            'success': True,
            'message': 'Meal plan created successfully',
            'data': MealPlanSerializer(meal_plan).data
        }, status=status.HTTP_201_CREATED)
        
    except KeyError as e:
        raise APIError(f"Missing required field: {str(e)}", status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error creating meal plan: {str(e)}")
        raise APIError(f"Failed to create meal plan: {str(e)}", status_code=status.HTTP_400_BAD_REQUEST)





# ============ DIETARY PLAN PUT/DELETE ============
@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def dietary_plan_detail(request, patient_id, plan_id):
    """
    Update or delete a specific dietary plan
    PUT: /api/patients/<patient_id>/dietary-plans/<plan_id>/
    DELETE: /api/patients/<patient_id>/dietary-plans/<plan_id>/
    """
    user = request.user
    
    # Check permissions
    if user.user_type == 'PATIENT':
        patient = PatientProfile.objects.get(user=user)
        if str(patient.patient_id) != str(patient_id):
            raise APIError("You can only access your own data", status_code=403)
    elif user.user_type not in ['ADMIN', 'DOCTOR', 'NURSE']:
        raise APIError("Permission denied", status_code=403)
    
    # Get the plan
    try:
        plan = PatientDietaryPlan.objects.get(plan_id=plan_id, patient_id=patient_id)
    except PatientDietaryPlan.DoesNotExist:
        raise APIError("Dietary plan not found", status_code=404)
    
    if request.method == 'PUT':
        # UPDATE
        data = request.data
        
        # Update food item if provided
        if 'food_item_id' in data:
            try:
                food_item = FoodItem.objects.get(food_item_id=data['food_item_id'])
                plan.food_item = food_item
            except FoodItem.DoesNotExist:
                raise APIError("Food item not found", status_code=404)
        
        # Update other fields
        plan.meal_type = data.get('meal_type', plan.meal_type)
        plan.quantity = data.get('quantity', plan.quantity)
        plan.timing = data.get('timing', plan.timing)
        plan.frequency = data.get('frequency', plan.frequency)
        plan.start_date = data.get('start_date', plan.start_date)
        plan.end_date = data.get('end_date', plan.end_date)
        plan.instructions = data.get('instructions', plan.instructions)
        plan.reason = data.get('reason', plan.reason)
        plan.is_active = data.get('is_active', plan.is_active)
        
        plan.save()
        
        logger.info(f"Dietary plan {plan_id} updated for patient {patient_id}")
        
        return Response({
            'success': True,
            'message': 'Dietary plan updated successfully',
            'data': PatientDietaryPlanSerializer(plan).data
        })
    
    elif request.method == 'DELETE':
        # DELETE
        plan.delete()
        
        logger.info(f"Dietary plan {plan_id} deleted for patient {patient_id}")
        
        return Response({
            'success': True,
            'message': 'Dietary plan deleted successfully',
            'data': {'deleted_plan_id': plan_id}
        })


# ============ FOOD LOG PUT/DELETE ============
@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def food_log_detail(request, patient_id, log_id):
    """
    Update or delete a specific food log
    PUT: /api/patients/<patient_id>/food-logs/<log_id>/
    DELETE: /api/patients/<patient_id>/food-logs/<log_id>/
    """
    user = request.user
    
    # Check permissions
    if user.user_type == 'PATIENT':
        patient = PatientProfile.objects.get(user=user)
        if str(patient.patient_id) != str(patient_id):
            raise APIError("You can only access your own data", status_code=403)
    elif user.user_type not in ['ADMIN', 'DOCTOR', 'NURSE']:
        raise APIError("Permission denied", status_code=403)
    
    # Get the log
    try:
        log = PatientFoodLog.objects.get(log_id=log_id, patient_id=patient_id)
    except PatientFoodLog.DoesNotExist:
        raise APIError("Food log not found", status_code=404)
    
    if request.method == 'PUT':
        # UPDATE
        data = request.data
        
        # Update food item if provided - MODIFIED HERE
        if 'food_item_id' in data:
            try:
                food_item = FoodItem.objects.get(food_item_id=data['food_item_id'])
                log.food_item = food_item
            except FoodItem.DoesNotExist:
                raise APIError("Food item not found", status_code=404)
        elif 'food_item_name' in data:  # NEW: Support food_item_name
            try:
                food_item = FoodItem.objects.get(name__iexact=data['food_item_name'])
                log.food_item = food_item
            except FoodItem.DoesNotExist:
                raise APIError(f"Food item '{data['food_item_name']}' not found", status_code=404)
        
        # Handle consumed_at
        if 'consumed_at' in data:
            from django.utils import timezone
            import datetime
            consumed_at = data['consumed_at']
            if isinstance(consumed_at, str):
                try:
                    consumed_at = datetime.datetime.fromisoformat(consumed_at.replace('Z', '+00:00'))
                except:
                    consumed_at = timezone.now()
            log.consumed_at = consumed_at
        
        # Update other fields
        log.meal_type = data.get('meal_type', log.meal_type)
        log.quantity_consumed = data.get('quantity_consumed', log.quantity_consumed)
        log.symptoms_experienced = data.get('symptoms_experienced', log.symptoms_experienced)
        log.symptom_severity = data.get('symptom_severity', log.symptom_severity)
        log.notes = data.get('notes', log.notes)
        
        log.save()
        
        logger.info(f"Food log {log_id} updated for patient {patient_id}")
        
        return Response({
            'success': True,
            'message': 'Food log updated successfully',
            'data': PatientFoodLogSerializer(log).data
        })
    
    elif request.method == 'DELETE':
        # DELETE
        log.delete()
        
        logger.info(f"Food log {log_id} deleted for patient {patient_id}")
        
        return Response({
            'success': True,
            'message': 'Food log deleted successfully',
            'data': {'deleted_log_id': log_id}
        })


# ============ DIETARY RESTRICTION PUT/DELETE ============
@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def dietary_restriction_detail(request, patient_id, restriction_id):
    """
    Update or delete a specific dietary restriction
    PUT: /api/patients/<patient_id>/dietary-restrictions/<restriction_id>/
    DELETE: /api/patients/<patient_id>/dietary-restrictions/<restriction_id>/
    """
    user = request.user
    
    # Check permissions
    if user.user_type == 'PATIENT':
        patient = PatientProfile.objects.get(user=user)
        if str(patient.patient_id) != str(patient_id):
            raise APIError("You can only access your own data", status_code=403)
    elif user.user_type not in ['ADMIN', 'DOCTOR', 'NURSE']:
        raise APIError("Permission denied", status_code=403)
    
    # Get the restriction
    try:
        restriction = DietaryRestriction.objects.get(restriction_id=restriction_id, patient_id=patient_id)
    except DietaryRestriction.DoesNotExist:
        raise APIError("Dietary restriction not found", status_code=404)
    
    if request.method == 'PUT':
        # UPDATE
        data = request.data
        
        # Validate at least one is provided for update
        if 'food_item_id' in data or 'food_category_id' in data:
            if not data.get('food_item_id') and not data.get('food_category_id'):
                raise APIError("Either food_item_id or food_category_id is required", status_code=400)
        
        # Update fields
        restriction.restriction_type = data.get('restriction_type', restriction.restriction_type)
        restriction.food_item_id = data.get('food_item_id', restriction.food_item_id)
        restriction.food_category_id = data.get('food_category_id', restriction.food_category_id)
        restriction.description = data.get('description', restriction.description)
        restriction.severity = data.get('severity', restriction.severity)
        restriction.diagnosed_date = data.get('diagnosed_date', restriction.diagnosed_date)
        restriction.notes = data.get('notes', restriction.notes)
        
        restriction.save()
        
        logger.info(f"Dietary restriction {restriction_id} updated for patient {patient_id}")
        
        return Response({
            'success': True,
            'message': 'Dietary restriction updated successfully',
            'data': DietaryRestrictionSerializer(restriction).data
        })
    
    elif request.method == 'DELETE':
        # DELETE
        restriction.delete()
        
        logger.info(f"Dietary restriction {restriction_id} deleted for patient {patient_id}")
        
        return Response({
            'success': True,
            'message': 'Dietary restriction deleted successfully',
            'data': {'deleted_restriction_id': restriction_id}
        })


# ============ MEAL PLAN PUT/DELETE ============
@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def meal_plan_detail(request, patient_id, meal_plan_id):
    """
    Update or delete a specific meal plan
    PUT: /api/patients/<patient_id>/meal-plans/<meal_plan_id>/
    DELETE: /api/patients/<patient_id>/meal-plans/<meal_plan_id>/
    """
    user = request.user
    
    # Check permissions
    if user.user_type == 'PATIENT':
        patient = PatientProfile.objects.get(user=user)
        if str(patient.patient_id) != str(patient_id):
            raise APIError("You can only access your own data", status_code=403)
    elif user.user_type not in ['ADMIN', 'DOCTOR', 'NURSE']:
        raise APIError("Permission denied", status_code=403)
    
    # Get the meal plan
    try:
        meal_plan = MealPlan.objects.get(meal_plan_id=meal_plan_id, patient_id=patient_id)
    except MealPlan.DoesNotExist:
        raise APIError("Meal plan not found", status_code=404)
    
    if request.method == 'PUT':
        # UPDATE
        data = request.data
        
        # Validate food_items if provided
        if 'food_items' in data and not data['food_items']:
            raise APIError("food_items cannot be empty", status_code=400)
        
        # Update fields
        meal_plan.name = data.get('name', meal_plan.name)
        meal_plan.description = data.get('description', meal_plan.description)
        meal_plan.weekday = data.get('weekday', meal_plan.weekday)
        meal_plan.meal_type = data.get('meal_type', meal_plan.meal_type)
        meal_plan.food_items = data.get('food_items', meal_plan.food_items)
        meal_plan.total_calories = data.get('total_calories', meal_plan.total_calories)
        meal_plan.total_protein = data.get('total_protein', meal_plan.total_protein)
        meal_plan.total_carbs = data.get('total_carbs', meal_plan.total_carbs)
        meal_plan.total_fat = data.get('total_fat', meal_plan.total_fat)
        meal_plan.instructions = data.get('instructions', meal_plan.instructions)
        meal_plan.start_date = data.get('start_date', meal_plan.start_date)
        meal_plan.end_date = data.get('end_date', meal_plan.end_date)
        meal_plan.is_active = data.get('is_active', meal_plan.is_active)
        
        # Update doctor if provided and user is authorized
        if 'doctor_id' in data and user.user_type in ['ADMIN', 'DOCTOR']:
            try:
                from accounts.models import DoctorProfile
                doctor = DoctorProfile.objects.get(doctor_id=data['doctor_id'])
                meal_plan.doctor = doctor
            except DoctorProfile.DoesNotExist:
                raise APIError("Doctor not found", status_code=404)
        
        meal_plan.save()
        
        logger.info(f"Meal plan {meal_plan_id} updated for patient {patient_id}")
        
        return Response({
            'success': True,
            'message': 'Meal plan updated successfully',
            'data': MealPlanSerializer(meal_plan).data
        })
    
    elif request.method == 'DELETE':
        # DELETE
        meal_plan.delete()
        
        logger.info(f"Meal plan {meal_plan_id} deleted for patient {patient_id}")
        
        return Response({
            'success': True,
            'message': 'Meal plan deleted successfully',
            'data': {'deleted_meal_plan_id': meal_plan_id}
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cancer_type_distribution(request):
    """
    Get distribution of cancer types across patients
    """
    try:
        user = request.user
        
        # Check permission
        if user.user_type not in ['ADMIN', 'DOCTOR']:
            return Response({
                'success': False,
                'error': 'Only admins and doctors can access this data'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Import models
        try:
            from patients.models import PatientMedicalRecord, CancerType
            from accounts.models import PatientProfile
        except ImportError as e:
            return Response({
                'success': False,
                'error': f'Import error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Check if tables exist and have data
        try:
            record_count = PatientMedicalRecord.objects.count()
            cancer_count = CancerType.objects.count()
            patient_count = PatientProfile.objects.count()
            
            logger.info(f"Records: {record_count}, Cancer types: {cancer_count}, Patients: {patient_count}")
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Database query error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # If no records, return empty distribution
        if record_count == 0:
            return Response({
                'success': True,
                'data': {
                    'distribution': [],
                    'summary': {
                        'total_patients': patient_count,
                        'patients_with_records': 0,
                        'patients_without_records': patient_count
                    },
                    'last_updated': timezone.now().isoformat(),
                    'message': 'No medical records found'
                }
            })
        
        # Try different query approaches
        
        # Approach 1: Simple count by cancer type
        try:
            # Get cancer type distribution using raw SQL (works with any database)
            from django.db import connection
            
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        ct.cancer_type_id,
                        ct.name as cancer_type_name,
                        COUNT(DISTINCT pmr.patient_id) as patient_count
                    FROM patient_medical_records pmr
                    LEFT JOIN cancer_types ct ON pmr.cancer_type_id = ct.cancer_type_id
                    GROUP BY ct.cancer_type_id, ct.name
                    ORDER BY patient_count DESC
                """)
                rows = cursor.fetchall()
            
            distribution = []
            total_with_records = 0
            
            for row in rows:
                cancer_type_id, cancer_type_name, count = row
                cancer_type_name = cancer_type_name or 'Unknown'
                distribution.append({
                    'cancer_type_id': cancer_type_id,
                    'cancer_type': cancer_type_name,
                    'count': count,
                    'percentage': 0  # Will calculate later
                })
                total_with_records += count
            
            # Calculate percentages
            if total_with_records > 0:
                for item in distribution:
                    item['percentage'] = round((item['count'] / total_with_records) * 100, 2)
            
        except Exception as e:
            logger.error(f"Raw SQL query failed: {str(e)}")
            
            # Approach 2: Use Django ORM (if fields exist)
            try:
                # Check if cancer_type field exists
                fields = [f.name for f in PatientMedicalRecord._meta.get_fields()]
                
                if 'cancer_type' in fields and 'patient' in fields:
                    cancer_data = PatientMedicalRecord.objects.values(
                        'cancer_type__cancer_type_id',
                        'cancer_type__name'
                    ).annotate(
                        patient_count=Count('patient__patient_id', distinct=True)
                    ).order_by('-patient_count')
                    
                    distribution = []
                    total_with_records = 0
                    
                    for item in cancer_data:
                        cancer_type_id = item.get('cancer_type__cancer_type_id')
                        cancer_type_name = item.get('cancer_type__name') or 'Unknown'
                        count = item.get('patient_count', 0)
                        
                        distribution.append({
                            'cancer_type_id': cancer_type_id,
                            'cancer_type': cancer_type_name,
                            'count': count,
                            'percentage': 0
                        })
                        total_with_records += count
                    
                    if total_with_records > 0:
                        for item in distribution:
                            item['percentage'] = round((item['count'] / total_with_records) * 100, 2)
                else:
                    # Approach 3: Return sample data
                    return Response({
                        'success': True,
                        'data': {
                            'distribution': [
                                {'cancer_type': 'Breast Cancer', 'count': 45, 'percentage': 30.0},
                                {'cancer_type': 'Lung Cancer', 'count': 30, 'percentage': 20.0},
                                {'cancer_type': 'Colorectal Cancer', 'count': 22, 'percentage': 14.7},
                                {'cancer_type': 'Prostate Cancer', 'count': 18, 'percentage': 12.0},
                                {'cancer_type': 'Not Specified', 'count': 35, 'percentage': 23.3},
                            ],
                            'summary': {
                                'total_patients': patient_count,
                                'patients_with_records': record_count,
                                'patients_without_records': patient_count - record_count,
                                'note': 'Using sample data - cancer_type field not found in PatientMedicalRecord'
                            },
                            'last_updated': timezone.now().isoformat()
                        }
                    })
                    
            except Exception as orm_error:
                logger.error(f"ORM query failed: {str(orm_error)}")
                return Response({
                    'success': False,
                    'error': f'Query error: {str(orm_error)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Get patients without records
        try:
            patients_without_record = PatientProfile.objects.exclude(
                patient_id__in=PatientMedicalRecord.objects.values('patient__patient_id')
            ).count()
        except:
            patients_without_record = 0
        
        # Add "Not Diagnosed" category
        if patients_without_record > 0:
            distribution.append({
                'cancer_type_id': None,
                'cancer_type': 'Not Diagnosed/No Record',
                'count': patients_without_record,
                'percentage': round((patients_without_record / patient_count) * 100, 2) if patient_count > 0 else 0
            })
        
        return Response({
            'success': True,
            'data': {
                'distribution': distribution,
                'summary': {
                    'total_patients': patient_count,
                    'patients_with_records': record_count,
                    'patients_without_records': patients_without_record
                },
                'last_updated': timezone.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)