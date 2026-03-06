from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import PatientMedicalRecord, CancerType, Treatment, Medication
from accounts.models import PatientProfile, DoctorProfile
from accounts.utils import handle_errors, APIError
from .serializers import (
    PatientMedicalRecordSerializer, CancerTypeSerializer,
    CreateMedicalRecordSerializer, CreateTreatmentSerializer,
    CreateMedicationSerializer, TreatmentSerializer, MedicationSerializer
)
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
        if user.user_type not in ['ADMIN', 'DOCTOR']:
            raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
        serializer = CreateMedicalRecordSerializer(data=request.data)
        if not serializer.is_valid():
            raise APIError("Validation error", errors=serializer.errors)
        
        data = serializer.validated_data
        
        # Get patient
        try:
            patient = PatientProfile.objects.get(patient_id=data['patient_id'])
        except PatientProfile.DoesNotExist:
            raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
        
        # Check if patient already has record
        if PatientMedicalRecord.objects.filter(patient=patient).exists():
            raise APIError("Patient already has a medical record")
        
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
        
        # Create medical record
        record = PatientMedicalRecord.objects.create(
            patient=patient,
            cancer_type=cancer_type,
            cancer_stage=data['cancer_stage'],
            diagnosis_date=data['diagnosis_date'],
            hospital_name=data['hospital_name'],
            treating_doctor=doctor,
            known_symptoms=data['known_symptoms'],
            allergies=data.get('allergies', '')
        )
        
        logger.info(f"Medical record created for patient {patient.patient_id}")
        
        response_serializer = PatientMedicalRecordSerializer(record)
        return Response({
            'success': True,
            'message': 'Medical record created successfully',
            'data': response_serializer.data
        }, status=status.HTTP_201_CREATED)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def medical_record_detail(request, record_id):
    """Get, update or delete medical record"""
    user = request.user
    
    try:
        record = PatientMedicalRecord.objects.get(medical_record_id=record_id)
    except PatientMedicalRecord.DoesNotExist:
        raise APIError("Medical record not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # Check permission
    if user.user_type == 'PATIENT':
        try:
            patient = PatientProfile.objects.get(user=user)
            if record.patient.patient_id != patient.patient_id:
                raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        except PatientProfile.DoesNotExist:
            raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        serializer = PatientMedicalRecordSerializer(record)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    elif request.method == 'PUT':
        if user.user_type not in ['ADMIN', 'DOCTOR']:
            raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
        data = request.data
        
        if 'cancer_stage' in data:
            record.cancer_stage = data['cancer_stage']
        if 'hospital_name' in data:
            record.hospital_name = data['hospital_name']
        if 'known_symptoms' in data:
            record.known_symptoms = data['known_symptoms']
        if 'allergies' in data:
            record.allergies = data['allergies']
        
        record.save()
        
        logger.info(f"Medical record {record_id} updated")
        
        serializer = PatientMedicalRecordSerializer(record)
        return Response({
            'success': True,
            'message': 'Medical record updated successfully',
            'data': serializer.data
        })
    
    elif request.method == 'DELETE':
        if user.user_type != 'ADMIN':
            raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
        
        record.delete()
        logger.info(f"Medical record {record_id} deleted")
        
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_treatments(request, record_id):
    """Get all treatments for a medical record"""
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_medications(request, record_id):
    """Get all medications for a medical record"""
    try:
        record = PatientMedicalRecord.objects.get(medical_record_id=record_id)
    except PatientMedicalRecord.DoesNotExist:
        raise APIError("Medical record not found", status_code=status.HTTP_404_NOT_FOUND)
    
    medications = record.medications.all()
    serializer = MedicationSerializer(medications, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data
    })