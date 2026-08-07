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
from uuid import uuid4
from .serializers import (
    PatientAssignmentSerializer, DashboardPreferenceSerializer,
    AnalyticsReportSerializer, CreateAssignmentSerializer,
    NurseSerializer, DoctorSerializer, PatientSerializer,
    UserSerializer, NurseCreateSerializer, DoctorCreateSerializer,
    PatientCreateSerializer, NurseUpdateSerializer, DoctorUpdateSerializer,
    PatientUpdateSerializer
)
from monitoring.models import DailyResponse, QuestionResponse, Alert
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

# accounts/views.py

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_nurse(request):
    data = request.data.copy()
    
    # Remove profile_picture if null/empty
    if 'profile_picture' in data:
        if not data['profile_picture'] or data['profile_picture'] == 'null' or data['profile_picture'] == '':
            del data['profile_picture']
    
    # Remove uploaded_documents if null/empty
    if 'uploaded_documents' in data:
        if not data['uploaded_documents'] or data['uploaded_documents'] == 'null' or data['uploaded_documents'] == '':
            del data['uploaded_documents']
    
    # Remove user field if present
    if 'user' in data:
        del data['user']
    
    # Ensure confirm_password
    if 'confirm_password' not in data and 'password' in data:
        data['confirm_password'] = data['password']
    
    # ✅ Set default joining_date if not provided
    if 'joining_date' not in data or not data['joining_date']:
        from datetime import date
        data['joining_date'] = date.today().isoformat()
    
    # Convert skills
    if 'skills' in data and data['skills']:
        skills_value = data['skills']
        if isinstance(skills_value, str):
            if ',' in skills_value:
                data['skills'] = [skill.strip() for skill in skills_value.split(',') if skill.strip()]
            elif skills_value:
                data['skills'] = [skills_value.strip()]
            else:
                data['skills'] = []
    
    print("Creating nurse with fields:", list(data.keys()))
    print("Joining date:", data.get('joining_date'))
    
    serializer = NurseCreateSerializer(data=data)
    if serializer.is_valid():
        nurse = serializer.save()
        response_serializer = NurseSerializer(nurse)
        return Response({
            'success': True,
            'message': 'Nurse created successfully',
            'data': response_serializer.data
        }, status=201)
    
    print("Validation errors:", serializer.errors)
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_all_nurses(request):
    """Get all nurses with filters"""
    verify_admin(request.user)
    
    # Get all nurses and prefetch user data
    all_nurses = NurseProfile.objects.select_related('user').all()
    
    # Manual filtering in Python (Djongo compatible)
    filtered_nurses = []
    
    # Get filter parameters
    is_active_filter = request.query_params.get('is_active')
    department_filter = request.query_params.get('department')
    shift_filter = request.query_params.get('shift')
    employment_type_filter = request.query_params.get('employment_type')
    blood_group_filter = request.query_params.get('blood_group')
    assigned_ward_filter = request.query_params.get('assigned_ward')
    search_filter = request.query_params.get('search')
    
    for nurse in all_nurses:
        try:
            # Filter by is_active
            if is_active_filter is not None:
                is_active_value = is_active_filter.lower() == 'true'
                nurse_is_active = getattr(nurse, 'is_active', True)
                if nurse_is_active != is_active_value:
                    continue
            
            # Filter by department
            if department_filter:
                nurse_department = getattr(nurse, 'department', '')
                if department_filter.lower() not in nurse_department.lower():
                    continue
            
            # Filter by shift
            if shift_filter:
                nurse_shift = getattr(nurse, 'shift', '')
                if shift_filter.lower() not in nurse_shift.lower():
                    continue
            
            # Filter by employment_type
            if employment_type_filter:
                nurse_employment_type = getattr(nurse, 'employment_type', '')
                if employment_type_filter.lower() not in nurse_employment_type.lower():
                    continue
            
            # Filter by blood_group
            if blood_group_filter:
                nurse_blood_group = getattr(nurse, 'blood_group', '')
                if blood_group_filter.upper() != nurse_blood_group.upper():
                    continue
            
            # Filter by assigned_ward
            if assigned_ward_filter:
                nurse_assigned_ward = getattr(nurse, 'assigned_ward', '')
                if assigned_ward_filter.lower() not in nurse_assigned_ward.lower():
                    continue
            
            # Filter by search
            if search_filter:
                # ✅ FIXED: Get first_name and last_name from User model
                first_name = nurse.user.first_name if nurse.user else ''
                last_name = nurse.user.last_name if nurse.user else ''
                employee_id = getattr(nurse, 'employee_id', '') or ''
                department = getattr(nurse, 'department', '') or ''
                
                full_name = f"{first_name} {last_name}".strip()
                
                search_lower = search_filter.lower()
                if (search_lower not in full_name.lower() and 
                    search_lower not in employee_id.lower() and 
                    search_lower not in department.lower()):
                    continue
            
            filtered_nurses.append(nurse)
            
        except Exception as e:
            print(f"Error filtering nurse: {e}")
            continue
    
    # Pagination
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    total_count = len(filtered_nurses)
    start = (page - 1) * page_size
    end = start + page_size
    
    paginated_nurses = filtered_nurses[start:end]
    
    # Helper function to convert Decimal128 to float/string
    def convert_decimal(value):
        if value is None:
            return None
        # Check if it's Decimal128 (MongoDB)
        if hasattr(value, 'to_decimal'):
            return float(str(value))
        # Check if it's already a decimal.Decimal
        if hasattr(value, 'to_eng_string'):
            return float(str(value))
        return value
    
    # Helper function to get profile picture URL
    def get_profile_picture_url(nurse):
        profile_pic = getattr(nurse, 'profile_picture', None)
        if profile_pic:
            return str(profile_pic)
        if hasattr(nurse, 'user') and nurse.user:
            user_profile_pic = getattr(nurse.user, 'profile_picture', None)
            if user_profile_pic:
                return str(user_profile_pic)
        return None
    
    # Manual serialization to avoid Djongo issues
    nurse_data_list = []
    for nurse in paginated_nurses:
        try:
            # ✅ FIXED: Always get name from User model
            name = f"{nurse.user.first_name} {nurse.user.last_name}".strip() or nurse.user.username
            
            # Get profile picture
            profile_picture = get_profile_picture_url(nurse)
            
            # Get email and phone from User model
            email = ""
            phone = ""
            username = ""
            if nurse.user:
                email = nurse.user.email or ""
                phone = nurse.user.phone_number or ""
                username = nurse.user.username or ""
            
            # Helper to safely get attribute and convert Decimal128
            def safe_get_attr(obj, attr_name):
                value = getattr(obj, attr_name, None)
                return convert_decimal(value)
            
            # ✅ COMPLETE NURSE DATA WITH ALL FIELDS - with Decimal128 conversion
            nurse_data = {
                'nurse_id': nurse.pk,
                'user': nurse.user.pk if nurse.user else None,
                'full_name': name,
                'name': name,
                
                # ✅ FIXED: Always from User model, not from NurseProfile
                'first_name': nurse.user.first_name if nurse.user else "",
                'last_name': nurse.user.last_name if nurse.user else "",
                
                'email': email,
                'phone': phone,
                'phone_number': phone,
                'username': username,
                'is_active': getattr(nurse, 'is_active', True),
                
                # Personal Details (from NurseProfile)
                'address': getattr(nurse, 'address', None),
                'date_of_birth': getattr(nurse, 'date_of_birth', None),
                'aadhar_number': getattr(nurse, 'aadhar_number', None),
                'gender': getattr(nurse, 'gender', None),
                'blood_group': getattr(nurse, 'blood_group', None),
                
                # Emergency Contact
                'emergency_contact_name': getattr(nurse, 'emergency_contact_name', None),
                'emergency_contact_phone': getattr(nurse, 'emergency_contact_phone', None),
                'emergency_contact_relation': getattr(nurse, 'emergency_contact_relation', None),
                
                # Professional Info
                'employee_id': getattr(nurse, 'employee_id', None),
                'department': getattr(nurse, 'department', None),
                'qualification': getattr(nurse, 'qualification', None),
                'joining_date': getattr(nurse, 'joining_date', None),
                'shift': getattr(nurse, 'shift', None),
                'employment_type': getattr(nurse, 'employment_type', None),
                'years_of_experience': safe_get_attr(nurse, 'years_of_experience'),
                'skills': getattr(nurse, 'skills', []),
                'assigned_ward': getattr(nurse, 'assigned_ward', None),
                'supervisor': getattr(nurse, 'supervisor', None),
                
                # Financial Info - Convert Decimal128 to float
                'salary': safe_get_attr(nurse, 'salary'),
                'bank_account_number': getattr(nurse, 'bank_account_number', None),
                'ifsc_code': getattr(nurse, 'ifsc_code', None),
                
                # Licensure/Documents
                'license_number': getattr(nurse, 'license_number', None),
                'state_of_licensure': getattr(nurse, 'state_of_licensure', None),
                'license_expiry_date': getattr(nurse, 'license_expiry_date', None),
                
                # Files
                'profile_picture': profile_picture,
                'uploaded_documents': getattr(nurse, 'uploaded_documents', None),
                
                # Timestamps
                'created_at': getattr(nurse, 'created_at', None),
                'updated_at': getattr(nurse, 'updated_at', None),
            }
            nurse_data_list.append(nurse_data)
        except Exception as e:
            print(f"Error serializing nurse: {e}")
            continue
    
    # ✅ RETURN WITH CACHE CONTROL HEADERS
    return Response({
        'success': True,
        'data': nurse_data_list,
        'pagination': {
            'total': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size if total_count > 0 else 1
        }
    }, headers={
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_nurse(request, nurse_id):
    """Get single nurse with ALL details"""
    verify_admin(request.user)
    
    try:
        # Get nurse by nurse_id (primary key)
        nurse = NurseProfile.objects.select_related('user').get(nurse_id=nurse_id)
        
        # Helper function to get profile picture URL
        def get_profile_picture_url(nurse_obj):
            profile_pic = getattr(nurse_obj, 'profile_picture', None)
            if profile_pic:
                return str(profile_pic)
            if hasattr(nurse_obj, 'user') and nurse_obj.user:
                user_profile_pic = getattr(nurse_obj.user, 'profile_picture', None)
                if user_profile_pic:
                    return str(user_profile_pic)
            return None
        
        # Helper function to convert Decimal128
        def convert_decimal(value):
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return str(value) if value else None
        
        # Get profile picture
        profile_picture = get_profile_picture_url(nurse)
        
        # Get document URL
        uploaded_documents = getattr(nurse, 'uploaded_documents', None)
        if uploaded_documents:
            uploaded_documents = str(uploaded_documents)
        
        # Parse skills
        skills = getattr(nurse, 'skills', [])
        if isinstance(skills, str):
            try:
                import json
                skills = json.loads(skills)
            except:
                skills = [s.strip() for s in skills.split(',') if s.strip()]
        
        nurse_data = {
            'nurse_id': nurse.nurse_id,
            'user': nurse.user.pk if nurse.user else None,
            'full_name': f"{nurse.first_name} {nurse.last_name}".strip(),
            'first_name': nurse.first_name,
            'last_name': nurse.last_name,
            'phone_number': nurse.phone_number,
            'email': nurse.email,
            'username': nurse.user.username if nurse.user else None,
            'is_active': nurse.is_active,
            'address': nurse.address,
            'date_of_birth': nurse.date_of_birth,
            'aadhar_number': nurse.aadhar_number,
            'gender': nurse.gender,
            'emergency_contact_name': nurse.emergency_contact_name,
            'emergency_contact_phone': nurse.emergency_contact_phone,
            'emergency_contact_relation': nurse.emergency_contact_relation,
            'employee_id': nurse.employee_id,
            'department': nurse.department,
            'qualification': nurse.qualification,
            'joining_date': nurse.joining_date,
            'shift': nurse.shift,
            'employment_type': nurse.employment_type,
            'years_of_experience': nurse.years_of_experience,
            'skills': skills,
            'assigned_ward': nurse.assigned_ward,
            'supervisor': nurse.supervisor,
            'salary': convert_decimal(nurse.salary),
            'bank_account_number': nurse.bank_account_number,
            'ifsc_code': nurse.ifsc_code,
            'blood_group': nurse.blood_group,
            'license_number': nurse.license_number,
            'state_of_licensure': nurse.state_of_licensure,
            'license_expiry_date': nurse.license_expiry_date,
            'profile_picture': profile_picture,
            'uploaded_documents': uploaded_documents,
            'created_at': nurse.created_at,
            'updated_at': nurse.updated_at,
        }
        
        return Response({
            'success': True,
            'data': nurse_data
        })
        
    except NurseProfile.DoesNotExist:
        raise APIError("Nurse not found", status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error in get_nurse: {str(e)}")
        import traceback
        traceback.print_exc()
        raise APIError(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


from decimal import Decimal
from bson.decimal128 import Decimal128
from accounts.models import User

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@handle_errors
def update_nurse(request, nurse_id):
    """Update nurse - ALL fields can be updated"""
    verify_admin(request.user)
    
    try:
        nurse = NurseProfile.objects.select_related('user').get(nurse_id=nurse_id)
    except NurseProfile.DoesNotExist:
        raise APIError("Nurse not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # ✅ ADD DEBUG - Print before update
    # print("=" * 60)
    # print(f"🟡 UPDATE NURSE - ID: {nurse_id}")
    # print(f"🟡 Before Update - Experience: {nurse.years_of_experience}")
    # print(f"🟡 Before Update - Blood Group: {nurse.blood_group}")
    # print(f"🟡 Before Update - Gender: {nurse.gender}")
    # print(f"🟡 Received Data: {request.data}")
    
    # Convert salary in request data
    data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
    if 'salary' in data:
        salary_value = data['salary']
        if isinstance(salary_value, str):
            try:
                data['salary'] = Decimal(salary_value.replace(',', ''))
            except:
                pass
        elif isinstance(salary_value, Decimal128):
            data['salary'] = salary_value.to_decimal()
    
    partial = request.method == 'PATCH'
    
    # Check phone_number uniqueness
    if 'phone_number' in data and data['phone_number']:
        phone = data['phone_number']
        existing_user = User.objects.filter(
            phone_number=phone
        ).exclude(user_id=nurse.user.user_id).first()
        
        if existing_user:
            raise APIError(
                f"Phone number '{phone}' is already registered to another user",
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    serializer = NurseUpdateSerializer(nurse, data=data, partial=partial)
    
    if serializer.is_valid():
        updated_nurse = serializer.save()
        
        # ✅ ADD DEBUG - Print after update
        print("🟢 After Update - Calling refresh_from_db()")
        updated_nurse.refresh_from_db()  # ✅ Force refresh from database
        # print(f"🟢 After Update - Experience: {updated_nurse.years_of_experience}")
        # print(f"🟢 After Update - Blood Group: {updated_nurse.blood_group}")
        # print(f"🟢 After Update - Gender: {updated_nurse.gender}")
        # print("=" * 60)
        
        # ✅ Get fresh data from serializer
        serialized_data = NurseSerializer(updated_nurse).data
        # print(f"🟢 Serialized Response: {serialized_data}")
        
        return Response({
            'success': True,
            'message': 'Nurse updated successfully',
            'data': serialized_data
        })
    
    print(f"🔴 Validation Error: {serializer.errors}")
    raise APIError("Validation error", errors=serializer.errors)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def delete_nurse(request, nurse_id):
    """Delete nurse (Admin only) - Permanent deletion from MongoDB"""
    verify_admin(request.user)
    
    try:
        from pymongo import MongoClient
        from bson import ObjectId
        
        client = MongoClient('localhost', 27017)
        db = client['cancer_db']
        
        # Find the nurse
        nurse = db.nurse_profiles.find_one({'nurse_id': int(nurse_id)})
        if not nurse:
            raise APIError(
                f"Nurse with ID {nurse_id} not found", 
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        logger.info(f"Permanently deleting nurse {nurse_id}")
        
        # Get user_id before deletion
        user_id = nurse.get('user')
        
        # Delete nurse profile
        nurse_result = db.nurse_profiles.delete_one({'nurse_id': int(nurse_id)})
        
        # Delete associated user account if exists
        user_deleted = False
        if user_id:
            user_result = db.users.delete_one({'user_id': user_id})
            if user_result.deleted_count > 0:
                user_deleted = True
                logger.info(f"Associated user account {user_id} also deleted")
        
        # Also delete from any other related collections (optional)
        # For example, delete attendance records, salary records, etc.
        attendance_result = db.nurse_attendance.delete_many({'nurse_id': int(nurse_id)})
        if attendance_result.deleted_count > 0:
            logger.info(f"Deleted {attendance_result.deleted_count} attendance records")
        
        # Delete from nurse_schedule collection if exists
        schedule_result = db.nurse_schedule.delete_many({'nurse_id': int(nurse_id)})
        if schedule_result.deleted_count > 0:
            logger.info(f"Deleted {schedule_result.deleted_count} schedule records")
        
        # Delete from nurse_leave_requests if exists
        leave_result = db.nurse_leave_requests.delete_many({'nurse_id': int(nurse_id)})
        if leave_result.deleted_count > 0:
            logger.info(f"Deleted {leave_result.deleted_count} leave requests")
        
        # Delete uploaded files if they exist (optional - if you have file storage)
        # You might want to delete the actual files from storage here
        if nurse.get('profile_picture'):
            # Delete profile picture file from storage
            try:
                import os
                profile_pic_path = nurse.get('profile_picture')
                if profile_pic_path and os.path.exists(profile_pic_path):
                    os.remove(profile_pic_path)
                    logger.info(f"Deleted profile picture: {profile_pic_path}")
            except Exception as e:
                logger.warning(f"Could not delete profile picture: {str(e)}")
        
        if nurse.get('uploaded_documents'):
            # Delete document file from storage
            try:
                import os
                doc_path = nurse.get('uploaded_documents')
                if doc_path and os.path.exists(doc_path):
                    os.remove(doc_path)
                    logger.info(f"Deleted document: {doc_path}")
            except Exception as e:
                logger.warning(f"Could not delete document: {str(e)}")
        
        if nurse_result.deleted_count > 0:
            message = f"Nurse {nurse_id} and all associated data permanently deleted"
            if user_deleted:
                message += f" (including user account {user_id})"
            
            logger.warning(f"Nurse {nurse_id} permanently deleted by {request.user.email}")
            
            return Response({
                'success': True,
                'message': message,
                'data': {
                    'nurse_id': nurse_id,
                    'profile_deleted': True,
                    'user_deleted': user_deleted,
                    'attendance_deleted': attendance_result.deleted_count if attendance_result else 0,
                    'schedule_deleted': schedule_result.deleted_count if schedule_result else 0,
                    'leave_deleted': leave_result.deleted_count if leave_result else 0
                }
            })
        else:
            raise APIError(
                f"Failed to delete nurse {nurse_id}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    except Exception as e:
        logger.error(f"Error deleting nurse {nurse_id}: {str(e)}")
        raise APIError(
            f"Failed to delete nurse: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        

# ==================== DOCTOR CRUD ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_doctor(request):
    data = request.data.copy()
    
    # Keep profile_picture as is (don't remove it)
    # Just ensure it's None if empty
    if 'profile_picture' in data:
        if data['profile_picture'] == 'null' or data['profile_picture'] == '':
            data['profile_picture'] = None
        # If it's base64, keep it as is (no validation)
    
    # Convert skills
    if 'skills' in data and data['skills']:
        if isinstance(data['skills'], str):
            if data['skills']:
                data['skills'] = [s.strip() for s in data['skills'].split(',') if s.strip()]
            else:
                data['skills'] = []
    
    # Convert available_days
    if 'available_days' in data and data['available_days']:
        if isinstance(data['available_days'], str):
            if data['available_days']:
                data['available_days'] = [d.strip() for d in data['available_days'].split(',') if d.strip()]
            else:
                data['available_days'] = []
    
    # Convert available_time
    if 'available_time' in data and data['available_time']:
        time_value = data['available_time']
        if isinstance(time_value, str):
            # Handle different formats
            if '-' in time_value and not time_value.startswith('('):
                parts = time_value.split('-')
                data['available_time'] = {
                    "start": parts[0].strip(),
                    "end": parts[1].strip() if len(parts) > 1 else "17:00"
                }
            else:
                # Default if format not recognized
                data['available_time'] = {"start": "09:00", "end": "17:00"}
    
    # Remove available_time if it's still a string (to avoid error)
    if 'available_time' in data and isinstance(data['available_time'], str):
        data.pop('available_time', None)
    
    serializer = DoctorCreateSerializer(data=data)
    if serializer.is_valid():
        doctor = serializer.save()
        response_serializer = DoctorSerializer(doctor)
        return Response({
            'success': True,
            'message': 'Doctor created successfully',
            'data': response_serializer.data
        }, status=201)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_all_doctors(request):
    """Get all doctors with filters"""
    verify_admin(request.user)
    
    # Get all doctors without any filter first (to avoid Djongo issues)
    all_doctors = DoctorProfile.objects.select_related('user').all()
    
    # Manual filtering in Python (Djongo compatible)
    filtered_doctors = []
    
    # Get filter parameters
    specialization_filter = request.query_params.get('specialization')
    department_filter = request.query_params.get('department')
    shift_filter = request.query_params.get('shift')
    is_active_filter = request.query_params.get('is_active')
    search_filter = request.query_params.get('search')
    blood_group_filter = request.query_params.get('blood_group')
    gender_filter = request.query_params.get('gender')
    employment_type_filter = request.query_params.get('employment_type')
    
    for doctor in all_doctors:
        try:
            # Filter by specialization
            if specialization_filter:
                doctor_specialization = getattr(doctor, 'specialization', '') or ''
                if specialization_filter.lower() not in doctor_specialization.lower():
                    continue
            
            # Filter by department
            if department_filter:
                doctor_department = getattr(doctor, 'department', '') or ''
                if department_filter.lower() not in doctor_department.lower():
                    continue
            
            # Filter by shift
            if shift_filter:
                doctor_shift = getattr(doctor, 'shift', '') or ''
                if shift_filter.lower() not in doctor_shift.lower():
                    continue
            
            # Filter by is_active
            if is_active_filter is not None:
                is_active_value = is_active_filter.lower() == 'true'
                doctor_is_active = getattr(doctor, 'is_active', True)
                if doctor_is_active != is_active_value:
                    continue
            
            # Filter by blood_group
            if blood_group_filter:
                doctor_blood_group = getattr(doctor, 'blood_group', '') or ''
                if blood_group_filter.upper() not in doctor_blood_group.upper():
                    continue
            
            # Filter by gender
            if gender_filter:
                doctor_gender = getattr(doctor, 'gender', '') or ''
                if gender_filter.upper() != doctor_gender.upper():
                    continue
            
            # Filter by employment_type
            if employment_type_filter:
                doctor_employment_type = getattr(doctor, 'employment_type', '') or ''
                if employment_type_filter.lower() not in doctor_employment_type.lower():
                    continue
            
            # ✅ Filter by search (name, email, employee_id, department, specialization)
            if search_filter:
                first_name = doctor.user.first_name if doctor.user else ''
                last_name = doctor.user.last_name if doctor.user else ''
                employee_id = getattr(doctor, 'employee_id', '') or ''
                department = getattr(doctor, 'department', '') or ''
                specialization = getattr(doctor, 'specialization', '') or ''
                email = doctor.user.email if doctor.user else ''
                
                full_name = f"{first_name} {last_name}".strip()
                search_lower = search_filter.lower()
                
                if (search_lower not in full_name.lower() and 
                    search_lower not in employee_id.lower() and 
                    search_lower not in department.lower() and
                    search_lower not in specialization.lower() and
                    search_lower not in email.lower()):
                    continue
            
            filtered_doctors.append(doctor)
            
        except Exception as e:
            print(f"Error filtering doctor: {e}")
            continue
    
    # Pagination
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    total_count = len(filtered_doctors)
    start = (page - 1) * page_size
    end = start + page_size
    
    paginated_doctors = filtered_doctors[start:end]
    
    # Helper function to convert Decimal128 to float/string
    def convert_decimal(value):
        if value is None:
            return None
        if hasattr(value, 'to_decimal'):
            return float(value.to_decimal())
        if hasattr(value, '__class__') and value.__class__.__name__ == 'Decimal128':
            return float(str(value))
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    
    # Helper function to get profile picture URL
    def get_profile_picture_url(doctor):
        profile_pic = getattr(doctor, 'profile_picture', None)
        if profile_pic:
            return str(profile_pic)
        if hasattr(doctor, 'user') and doctor.user:
            user_profile_pic = getattr(doctor.user, 'profile_picture', None)
            if user_profile_pic:
                return str(user_profile_pic)
        return None
    
    # Helper function to safely get attribute
    def safe_get_attr(obj, attr_name):
        value = getattr(obj, attr_name, None)
        return convert_decimal(value)
    
    # Manual serialization to avoid Djongo issues
    doctor_data_list = []
    for doctor in paginated_doctors:
        try:
            # ✅ FIXED: Always get name from User model
            name = f"{doctor.user.first_name} {doctor.user.last_name}".strip() or doctor.user.username
            
            # Get specialization safely
            specialization = getattr(doctor, 'specialization', None)
            if not specialization:
                specialization = getattr(doctor, 'department', None)
            
            # Get consultation_fee and convert Decimal128
            consultation_fee = safe_get_attr(doctor, 'consultation_fee')
            
            # Get salary if exists
            salary = safe_get_attr(doctor, 'salary')
            
            # Get profile picture URL
            profile_picture = get_profile_picture_url(doctor)
            
            # ✅ COMPLETE DOCTOR DATA WITH ALL FIELDS
            doctor_data = {
                'doctor_id': doctor.pk,
                'user': doctor.user.pk if doctor.user else None,
                'name': name,
                'full_name': name,
                
                # ✅ Basic Info (from User model)
                'first_name': doctor.user.first_name if doctor.user else "",
                'last_name': doctor.user.last_name if doctor.user else "",
                'email': doctor.user.email if doctor.user else "",
                'phone': doctor.user.phone_number if doctor.user else "",
                'phone_number': doctor.user.phone_number if doctor.user else "",
                'username': doctor.user.username if doctor.user else "",
                'is_active': getattr(doctor, 'is_active', True),
                
                # ✅ Personal Details
                'address': getattr(doctor, 'address', None),
                'date_of_birth': getattr(doctor, 'date_of_birth', None),
                'aadhar_number': getattr(doctor, 'aadhar_number', None),
                'gender': getattr(doctor, 'gender', None),
                'blood_group': getattr(doctor, 'blood_group', None),
                
                # ✅ Emergency Contact (if exists in DoctorProfile)
                'emergency_contact_name': getattr(doctor, 'emergency_contact_name', None),
                'emergency_contact_phone': getattr(doctor, 'emergency_contact_phone', None),
                'emergency_contact_relation': getattr(doctor, 'emergency_contact_relation', None),
                
                # ✅ Professional Info
                'employee_id': getattr(doctor, 'employee_id', None),
                'department': getattr(doctor, 'department', None),
                'specialization': specialization,
                'qualification': getattr(doctor, 'qualification', None),
                'joining_date': getattr(doctor, 'joining_date', None),
                'shift': getattr(doctor, 'shift', None),
                'employment_type': getattr(doctor, 'employment_type', None),
                'years_of_experience': getattr(doctor, 'years_of_experience', None),
                'license_number': getattr(doctor, 'license_number', None),
                'consultation_fee': consultation_fee,
                'salary': salary,
                'available_days': getattr(doctor, 'available_days', []),
                'available_time': getattr(doctor, 'available_time', {}),
                'skills': getattr(doctor, 'skills', []),
                'assigned_ward': getattr(doctor, 'assigned_ward', None),
                'supervisor': getattr(doctor, 'supervisor', None),
                
                # ✅ Financial Info
                'bank_account_number': getattr(doctor, 'bank_account_number', None),
                'ifsc_code': getattr(doctor, 'ifsc_code', None),
                
                # ✅ Licensure/Documents
                'state_of_licensure': getattr(doctor, 'state_of_licensure', None),
                'license_expiry_date': getattr(doctor, 'license_expiry_date', None),
                
                # ✅ Files
                'profile_picture': profile_picture,
                'uploaded_documents': getattr(doctor, 'uploaded_documents', None),
                'documents': getattr(doctor, 'documents', {}),
                
                # ✅ Timestamps
                'created_at': getattr(doctor, 'created_at', None),
                'updated_at': getattr(doctor, 'updated_at', None),
            }
            doctor_data_list.append(doctor_data)
        except Exception as e:
            print(f"Error serializing doctor {doctor.pk}: {e}")
            continue
    
    # ✅ RETURN WITH CACHE CONTROL HEADERS
    return Response({
        'success': True,
        'data': doctor_data_list,
        'pagination': {
            'total': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size if total_count > 0 else 1
        }
    }, headers={
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_doctor(request, doctor_id):
    """Get single doctor with ALL details"""
    verify_admin(request.user)
    
    try:
        doctor = DoctorProfile.objects.select_related('user').get(doctor_id=doctor_id)
    except DoctorProfile.DoesNotExist:
        raise APIError("Doctor not found", status_code=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'success': True,
        'data': DoctorSerializer(doctor).data
    })


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@handle_errors
def update_doctor(request, doctor_id):
    """Update doctor - ALL fields can be updated"""
    verify_admin(request.user)
    
    try:
        doctor = DoctorProfile.objects.select_related('user').get(doctor_id=doctor_id)
    except DoctorProfile.DoesNotExist:
        raise APIError("Doctor not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # ✅ Convert salary and consultation_fee in request data
    data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
    
    if 'salary' in data:
        salary_value = data['salary']
        if isinstance(salary_value, str):
            try:
                data['salary'] = Decimal(salary_value.replace(',', ''))
            except:
                pass
        elif hasattr(salary_value, 'to_decimal'):
            data['salary'] = salary_value.to_decimal()
    
    if 'consultation_fee' in data:
        fee_value = data['consultation_fee']
        if isinstance(fee_value, str):
            try:
                data['consultation_fee'] = Decimal(fee_value.replace(',', ''))
            except:
                pass
        elif hasattr(fee_value, 'to_decimal'):
            data['consultation_fee'] = fee_value.to_decimal()
    
    partial = request.method == 'PATCH'
    
    # ✅ Check phone_number uniqueness before update
    if 'phone_number' in data and data['phone_number']:
        phone = data['phone_number']
        existing_user = User.objects.filter(
            phone_number=phone
        ).exclude(user_id=doctor.user.user_id).first()
        
        if existing_user:
            raise APIError(
                f"Phone number '{phone}' is already registered to another user",
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    serializer = DoctorUpdateSerializer(doctor, data=data, partial=partial)
    
    if serializer.is_valid():
        updated_doctor = serializer.save()
        
        # ✅ Force sync from User model
        updated_doctor.refresh_from_db()
        
        return Response({
            'success': True,
            'message': 'Doctor updated successfully',
            'data': DoctorSerializer(updated_doctor).data
        }, headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
        })
    
    raise APIError("Validation error", errors=serializer.errors)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def delete_doctor(request, doctor_id):
    """Delete doctor permanently (Admin only)"""
    verify_admin(request.user)
    
    try:
        from pymongo import MongoClient
        
        client = MongoClient('localhost', 27017)
        db = client['cancer_db']
        
        # Find the doctor
        doctor = db.doctor_profiles.find_one({'doctor_id': int(doctor_id)})
        if not doctor:
            raise APIError(
                f"Doctor with ID {doctor_id} not found", 
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        logger.warning(f"Permanently deleting doctor {doctor_id} by {request.user.email}")
        
        # Hard delete - remove from both collections
        user_id = doctor.get('user')
        
        # Delete doctor profile
        doctor_result = db.doctor_profiles.delete_one({'doctor_id': int(doctor_id)})
        
        # Delete associated user account
        user_result = None
        if user_id:
            user_result = db.users.delete_one({'user_id': user_id})
        
        # Optional: Delete associated data (appointments, prescriptions, etc.)
        db.appointments.delete_many({'doctor_id': int(doctor_id)})
        db.prescriptions.delete_many({'doctor_id': int(doctor_id)})
        
        message = f"Doctor {doctor_id} permanently deleted"
        if user_result and user_result.deleted_count > 0:
            message += f" along with user account {user_id}"
        
        logger.warning(f"Doctor {doctor_id} permanently deleted by {request.user.email}")
        
        return Response({
            'success': True,
            'message': message,
            'deleted_doctor': doctor_result.deleted_count > 0,
            'deleted_user': user_result.deleted_count > 0 if user_result else False
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
        # Use patient_id instead of id
        logger.info(f"Patient created: ID={patient.patient_id}, Patient No={patient.patient_no} by admin {request.user.email}")
        
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
    
    patients = PatientProfile.objects.select_related('user').order_by('-user__date_joined').all()
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
        patient = PatientProfile.objects.select_related('user').get(patient_id=patient_id)
    except PatientProfile.DoesNotExist:
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)
    
    # ✅ Get old status for tracking
    old_status = patient.patient_status
    
    # ✅ Convert 'status' to 'patient_status' if present
    data = request.data.copy()
    if 'status' in data:
        data['patient_status'] = data.pop('status')
    
    partial = request.method == 'PATCH'
    serializer = PatientUpdateSerializer(patient, data=data, partial=partial)
    
    if serializer.is_valid():
        updated_patient = serializer.save()
        
        # ✅ Log status change with reason
        new_status = updated_patient.patient_status
        if old_status != new_status:
            logger.info(
                f"Patient status updated: {patient_id} from {old_status} to {new_status} "
                f"by admin {request.user.email}. "
                f"Reason: {updated_patient.status_reason or 'N/A'}"
            )
        
        return Response({
            'success': True,
            'message': 'Patient updated successfully',
            'data': PatientSerializer(updated_patient).data,
            'status_update': {
                'old_status': old_status,
                'new_status': new_status,
                'reason': updated_patient.status_reason if old_status != new_status else None,
                'details': {
                    'recovery_date': updated_patient.recovery_date if updated_patient.status_reason == 'recovered' else None,
                    'death_date': updated_patient.death_date if updated_patient.status_reason == 'deceased' else None,
                    'discontinuation_date': updated_patient.discontinuation_date if updated_patient.status_reason == 'discontinued' else None
                } if old_status != new_status else None
            }
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
        patient_medical = PatientMedicalRecord.objects.get(patient_id=int(data['patient_id']))
        admin, _ = AdminProfile.objects.get_or_create(user=user)

    except NurseProfile.DoesNotExist:
        raise APIError("Nurse not found", status_code=status.HTTP_404_NOT_FOUND)
    except DoctorProfile.DoesNotExist:
        raise APIError("Doctor not found", status_code=status.HTTP_404_NOT_FOUND)
    except PatientMedicalRecord.DoesNotExist:
        raise APIError("Patient not found", status_code=status.HTTP_404_NOT_FOUND)

    # Check existing assignments
    existing_assignments = PatientAssignment.objects.filter(
        patient_id=patient_medical.patient_id
    )

    for assign in existing_assignments:
        if assign.is_active:
            raise APIError("Patient already assigned")

    # Create assignment
    assignment = PatientAssignment.objects.create(
        nurse_id=nurse.nurse_id,
        doctor_id=doctor.doctor_id,
        patient_id=patient_medical.patient_id,
        assigned_by=admin,
        is_active=True
    )

    logger.info(f"Patient {patient_medical.patient_id} assigned to nurse {nurse.nurse_id}")

    # Get serialized data
    serializer = PatientAssignmentSerializer(assignment)
    response_data = serializer.data
    
    # Manually add patient details if not present
    if response_data.get('patient_details') is None:
        from .serializers import PatientSerializer
        patient_profile = patient_medical.patient  # Assuming PatientMedicalRecord has relation to PatientProfile
        response_data['patient_details'] = PatientSerializer(patient_profile).data

    return Response({
        'success': True,
        'message': 'Patient assigned successfully',
        'data': response_data
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


# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def get_dashboard_stats(request):
#     """Get dashboard statistics based on user type"""
#     user = request.user
#     today = timezone.now().date()
#     start_of_month = today.replace(day=1)
    
#     # Convert dates to datetime for MongoDB queries
#     start_datetime = datetime.combine(start_of_month, datetime.min.time())
#     today_datetime = datetime.combine(today, datetime.max.time())
    
#     if user.user_type == 'NURSE':
#         try:
#             nurse = NurseProfile.objects.get(user=user)
            
#             # Patients assigned to this nurse (from PatientMedicalRecord)
#             total_patients = PatientMedicalRecord.objects.filter(
#                 assigned_nurse=nurse
#             ).count()
            
#             # New alerts for this nurse
#             new_alerts = Alert.objects.filter(
#                 assigned_to_nurse=nurse,
#                 status='NEW'
#             ).count()
            
#             # Today responses
#             today_responses = DailyResponse.objects.filter(
#                 response_date__gte=start_of_month,
#                 response_date__lte=today
#             ).count()
            
#             # Pending questionnaires
#             pending_questionnaires = QuestionnaireAssignment.objects.filter(
#                 status='PENDING'
#             ).count()
            
#             # Active patients for this nurse (submitted response in last 7 days)
#             last_7_days_ago = today - timedelta(days=7)
#             last_7_days_start = datetime.combine(last_7_days_ago, datetime.min.time())
            
#             recent_responses = DailyResponse.objects.filter(
#                 response_date__gte=last_7_days_start,
#                 response_date__lte=today_datetime
#             )
            
#             active_patient_ids = set()
#             for response in recent_responses:
#                 try:
#                     if response.patient and response.patient.assigned_nurse == nurse:
#                         if response.patient.patient:
#                             active_patient_ids.add(response.patient.patient.patient_id)
#                 except Exception as e:
#                     continue
            
#             active_patients = len(active_patient_ids)
#             inactive_patients = total_patients - active_patients
            
#             # Get detailed patient list for this nurse
#             nurse_patients = PatientMedicalRecord.objects.filter(assigned_nurse=nurse)
#             patient_details_list = []
            
#             for patient_record in nurse_patients:
#                 try:
#                     patient = patient_record.patient
#                     if patient:
#                         # Check if patient is active
#                         is_active = False
#                         last_response_date = None
                        
#                         patient_responses = DailyResponse.objects.filter(
#                             patient=patient_record,
#                             response_date__gte=last_7_days_start,
#                             response_date__lte=today_datetime
#                         )
#                         is_active = patient_responses.exists()
                        
#                         last_response = DailyResponse.objects.filter(
#                             patient=patient_record
#                         ).order_by('-response_date').first()
#                         if last_response:
#                             last_response_date = last_response.response_date
                        
#                         patient_details_list.append({
#                             'patient_id': patient.patient_id,
#                             'name': f"{patient.first_name} {patient.last_name}".strip() or patient.user.username,
#                             'email': patient.user.email,
#                             'phone': patient.user.phone_number,
#                             'status': 'ACTIVE' if is_active else 'INACTIVE',
#                             'last_response_date': last_response_date,
#                             'gender': patient.gender,
#                             'health_status': patient_record.health_status,
#                             'cancer_stage': patient_record.cancer_stage
#                         })
#                 except Exception as e:
#                     continue
            
#             active_patient_details = [p for p in patient_details_list if p['status'] == 'ACTIVE']
#             inactive_patient_details = [p for p in patient_details_list if p['status'] == 'INACTIVE']
            
#             # Recovery rate for nurse's patients
#             total_patients_with_status = 0
#             improving_patients = 0
            
#             for patient in nurse_patients:
#                 try:
#                     if patient.health_status:
#                         total_patients_with_status += 1
#                         if patient.health_status == 'IMPROVING':
#                             improving_patients += 1
#                 except Exception as e:
#                     continue
            
#             recovery_rate = round(
#                 (improving_patients / total_patients_with_status * 100) 
#                 if total_patients_with_status > 0 else 0, 
#                 1
#             )
            
#             return Response({
#                 'success': True,
#                 'data': {
#                     'total_patients': total_patients,
#                     'new_alerts': new_alerts,
#                     'today_responses': today_responses,
#                     'pending_questionnaires': pending_questionnaires,
#                     'patient_stats': {
#                         'active_patients': active_patients,
#                         'inactive_patients': inactive_patients,
#                         'total_patients': total_patients,
#                         'active_percentage': round((active_patients / total_patients * 100) if total_patients > 0 else 0, 1),
#                         'inactive_percentage': round((inactive_patients / total_patients * 100) if total_patients > 0 else 0, 1)
#                     },
#                     'patient_details': {
#                         'active': {
#                             'count': len(active_patient_details),
#                             'patients': active_patient_details
#                         },
#                         'inactive': {
#                             'count': len(inactive_patient_details),
#                             'patients': inactive_patient_details
#                         }
#                     },
#                     'recovery_stats': {
#                         'recovery_rate': recovery_rate,
#                         'improving_patients': improving_patients,
#                         'total_patients_tracked': total_patients_with_status,
#                         'remaining_patients': total_patients_with_status - improving_patients
#                     },
#                     'recent_alerts': AlertSerializer(
#                         Alert.objects.filter(assigned_to_nurse=nurse)[:5], 
#                         many=True
#                     ).data
#                 }
#             })
            
#         except NurseProfile.DoesNotExist:
#             raise APIError("Nurse profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
#     elif user.user_type == 'ADMIN':
#         # Admin Dashboard
#         # ========== Total Counts from Profile Models ==========
#         total_patients = PatientProfile.objects.count()
#         total_doctors = DoctorProfile.objects.count()
#         total_nurses = NurseProfile.objects.count()
        
#         # ========== Active Patients (submitted response in last 7 days) ==========
#         last_7_days_ago = today - timedelta(days=7)
#         last_7_days_start = datetime.combine(last_7_days_ago, datetime.min.time())
        
#         recent_responses = DailyResponse.objects.filter(
#             response_date__gte=last_7_days_start,
#             response_date__lte=today_datetime
#         )
        
#         active_patient_ids = set()
#         for response in recent_responses:
#             try:
#                 if response.patient and response.patient.patient:
#                     active_patient_ids.add(response.patient.patient.patient_id)
#             except Exception as e:
#                 continue
        
#         active_patients = len(active_patient_ids)
#         inactive_patients = total_patients - active_patients
        
#         # ========== Active Questions ==========
#         active_question_ids = set()
#         for response in recent_responses:
#             try:
#                 question_responses = QuestionResponse.objects.filter(daily_response=response)
#                 for qr in question_responses:
#                     if qr.assigned_question:
#                         active_question_ids.add(qr.assigned_question.pk)
#             except Exception as e:
#                 continue
        
#         active_questions = len(active_question_ids)
        
#         # ========== Active Questionnaires ==========
#         active_questionnaires = QuestionnaireAssignment.objects.filter(
#             status='IN_PROGRESS'
#         ).count()
        
#         # ========== Reports Generated ==========
#         reports_generated = QuestionnaireAssignment.objects.filter(
#             status='COMPLETED'
#         ).count()
        
#         # ========== Staff Statistics ==========
#         # Active Doctors - Have at least one patient in PatientMedicalRecord
#         active_doctor_ids = PatientMedicalRecord.objects.filter(
#             treating_doctor__isnull=False
#         ).values_list('treating_doctor', flat=True).distinct()
#         active_doctors = len(active_doctor_ids)
#         inactive_doctors = total_doctors - active_doctors
        
#         # Active Nurses - Have at least one patient in PatientMedicalRecord
#         active_nurse_ids = PatientMedicalRecord.objects.filter(
#             assigned_nurse__isnull=False
#         ).values_list('assigned_nurse', flat=True).distinct()
#         active_nurses = len(active_nurse_ids)
#         inactive_nurses = total_nurses - active_nurses
        
#         # ========== Doctor Details with Active/Inactive Status ==========
#                 # ========== Doctor Details with Active/Inactive Status ==========
#         doctor_details_list = []
#         for doctor in DoctorProfile.objects.all():
#             try:
#                 # Check if doctor has any patients
#                 has_patients = PatientMedicalRecord.objects.filter(treating_doctor=doctor).exists()
                
#                 # Get patient count for this doctor
#                 patient_count = PatientMedicalRecord.objects.filter(treating_doctor=doctor).count()
                
#                 # Get assigned patients list
#                 assigned_patients = []
#                 patient_records = PatientMedicalRecord.objects.filter(treating_doctor=doctor)
#                 for pr in patient_records:
#                     if pr.patient:
#                         assigned_patients.append({
#                             'patient_id': pr.patient.patient_id,
#                             'name': f"{pr.patient.first_name} {pr.patient.last_name}".strip() or pr.patient.user.username
#                         })
                
#                 doctor_details_list.append({
#                     'doctor_id': doctor.pk,  # Changed from doctor.id to doctor.pk
#                     'name': f"{doctor.user.first_name} {doctor.user.last_name}".strip() or doctor.user.username,
#                     'email': doctor.user.email,
#                     'phone': doctor.user.phone_number,
#                     'specialization': getattr(doctor, 'specialization', None),
#                     'status': 'ACTIVE' if has_patients else 'INACTIVE',
#                     'patient_count': patient_count,
#                     'assigned_patients': assigned_patients[:10]  # Limit to 10
#                 })
#             except Exception as e:
#                 print(f"Error processing doctor {doctor.pk}: {e}")  # Changed from doctor.id to doctor.pk
#                 continue
        
#         active_doctor_details = [d for d in doctor_details_list if d['status'] == 'ACTIVE']
#         inactive_doctor_details = [d for d in doctor_details_list if d['status'] == 'INACTIVE']
        
#         # ========== Nurse Details with Active/Inactive Status ==========
#                 # ========== Nurse Details with Active/Inactive Status ==========
#         nurse_details_list = []
#         for nurse in NurseProfile.objects.all():
#             try:
#                 # Check if nurse has any patients
#                 has_patients = PatientMedicalRecord.objects.filter(assigned_nurse=nurse).exists()
                
#                 # Get patient count for this nurse
#                 patient_count = PatientMedicalRecord.objects.filter(assigned_nurse=nurse).count()
                
#                 # Get assigned patients list
#                 assigned_patients = []
#                 patient_records = PatientMedicalRecord.objects.filter(assigned_nurse=nurse)
#                 for pr in patient_records:
#                     if pr.patient:
#                         assigned_patients.append({
#                             'patient_id': pr.patient.patient_id,
#                             'name': f"{pr.patient.first_name} {pr.patient.last_name}".strip() or pr.patient.user.username
#                         })
                
#                 nurse_details_list.append({
#                     'nurse_id': nurse.pk,  # Changed from nurse.id to nurse.pk
#                     'name': f"{nurse.user.first_name} {nurse.user.last_name}".strip() or nurse.user.username,
#                     'email': nurse.user.email,
#                     'phone': nurse.user.phone_number,
#                     'status': 'ACTIVE' if has_patients else 'INACTIVE',
#                     'patient_count': patient_count,
#                     'assigned_patients': assigned_patients[:10]  # Limit to 10
#                 })
#             except Exception as e:
#                 print(f"Error processing nurse {nurse.pk}: {e}")  # Changed from nurse.id to nurse.pk
#                 continue
        
#         active_nurse_details = [n for n in nurse_details_list if n['status'] == 'ACTIVE']
#         inactive_nurse_details = [n for n in nurse_details_list if n['status'] == 'INACTIVE']
        
#         # ========== Patient Details with Active/Inactive Status ==========
#         from datetime import date as date_module
        
#                 # ========== Patient Details with Active/Inactive Status ==========
#         from datetime import date as date_module
        
#         def calculate_age(birth_date):
#             if birth_date:
#                 today_date = date_module.today()
#                 return today_date.year - birth_date.year - (
#                     (today_date.month, today_date.day) < (birth_date.month, birth_date.day)
#                 )
#             return None
        
#         patient_details_list = []
#         for patient in PatientProfile.objects.all():
#             try:
#                 # Get patient medical record
#                 medical_record = PatientMedicalRecord.objects.filter(patient=patient).first()
                
#                 # Check if patient has any response in last 7 days
#                 has_recent_response = False
#                 last_response_date = None
                
#                 if medical_record:
#                     # Check for responses in last 7 days
#                     recent_patient_responses = DailyResponse.objects.filter(
#                         patient=medical_record,
#                         response_date__gte=last_7_days_start,
#                         response_date__lte=today_datetime
#                     )
#                     has_recent_response = recent_patient_responses.exists()
                    
#                     # Get last response date
#                     last_response = DailyResponse.objects.filter(
#                         patient=medical_record
#                     ).order_by('-response_date').first()
#                     if last_response:
#                         last_response_date = last_response.response_date
                
#                 # Get nurse and doctor names
#                 nurse_name = None
#                 doctor_name = None
#                 if medical_record:
#                     if medical_record.assigned_nurse:
#                         nurse_name = f"{medical_record.assigned_nurse.user.first_name} {medical_record.assigned_nurse.user.last_name}".strip() or medical_record.assigned_nurse.user.username
#                     if medical_record.treating_doctor:
#                         doctor_name = f"{medical_record.treating_doctor.user.first_name} {medical_record.treating_doctor.user.last_name}".strip() or medical_record.treating_doctor.user.username
                
#                 # Calculate age
#                 patient_age = None
#                 if patient.date_of_birth:
#                     patient_age = calculate_age(patient.date_of_birth)
                
#                 # Get health status and cancer stage safely (check if fields exist)
#                 health_status = None
#                 cancer_stage = None
#                 if medical_record:
#                     # Try to get health_status if field exists
#                     if hasattr(medical_record, 'health_status'):
#                         health_status = medical_record.health_status
#                     # Try to get cancer_stage if field exists
#                     if hasattr(medical_record, 'cancer_stage'):
#                         cancer_stage = medical_record.cancer_stage
                
#                 patient_info = {
#                     'patient_id': patient.patient_id,
#                     'name': f"{patient.first_name} {patient.last_name}".strip() or patient.user.username,
#                     'email': patient.user.email,
#                     'phone': patient.user.phone_number,
#                     'status': 'ACTIVE' if has_recent_response else 'INACTIVE',
#                     'last_response_date': last_response_date,
#                     'assigned_nurse': nurse_name,
#                     'treating_doctor': doctor_name,
#                     'gender': patient.gender,
#                     'age': patient_age,
#                     'blood_group': getattr(patient, 'blood_group', None),
#                     'address': getattr(patient, 'address', None),
#                     'health_status': health_status,
#                     'cancer_stage': cancer_stage
#                 }
#                 patient_details_list.append(patient_info)
                
#             except Exception as e:
#                 print(f"Error processing patient {patient.pk}: {e}")  # Changed from patient.id to patient.pk
#                 continue
        
#         active_patient_details = [p for p in patient_details_list if p['status'] == 'ACTIVE']
#         inactive_patient_details = [p for p in patient_details_list if p['status'] == 'INACTIVE']
        
#         # ========== Recovery Rate ==========
#                 # ========== Recovery Rate ==========
#         all_patient_records = PatientMedicalRecord.objects.all()
#         total_patients_with_status = 0
#         improving_patients = 0
        
#         for patient_record in all_patient_records:
#             try:
#                 # Check if health_status field exists and has value
#                 if hasattr(patient_record, 'health_status') and patient_record.health_status:
#                     total_patients_with_status += 1
#                     if patient_record.health_status == 'IMPROVING':
#                         improving_patients += 1
#             except Exception as e:
#                 continue
        
#         recovery_rate = round(
#             (improving_patients / total_patients_with_status * 100) 
#             if total_patients_with_status > 0 else 0, 
#             1
#         )
        
#         # ========== Patient Activity - last 7 days ==========
#         last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
#         patient_activity = []
#         for day in last_7_days:
#             day_start = datetime.combine(day, datetime.min.time())
#             day_end = datetime.combine(day, datetime.max.time())
            
#             count = DailyResponse.objects.filter(
#                 response_date__gte=day_start,
#                 response_date__lte=day_end
#             ).count()
            
#             patient_activity.append({
#                 'date': day.strftime('%Y-%m-%d'),
#                 'count': count
#             })
        
#         # ========== Questionnaire Completion Rate ==========
#         total_questionnaires = QuestionnaireAssignment.objects.filter(
#             created_at__gte=start_datetime,
#             created_at__lte=today_datetime
#         ).count()
        
#         completed_questionnaires = QuestionnaireAssignment.objects.filter(
#             status='COMPLETED',
#             created_at__gte=start_datetime,
#             created_at__lte=today_datetime
#         ).count()
        
#         completion_rate = round(
#             (completed_questionnaires / total_questionnaires * 100) 
#             if total_questionnaires > 0 else 0, 
#             1
#         )
        
#         # ========== Additional Stats ==========
#         active_alerts = Alert.objects.filter(status='NEW').count()
#         critical_patients = PatientMedicalRecord.objects.filter(
#             cancer_stage__in=['STAGE_3', 'STAGE_4']
#         ).count()
        
#         # Alert statistics by severity
#         high_severity_alerts = Alert.objects.filter(
#             alert_level='HIGH',
#             status='NEW'
#         ).count()
        
#         medium_severity_alerts = Alert.objects.filter(
#             alert_level='MEDIUM',
#             status='NEW'
#         ).count()
        
#         low_severity_alerts = Alert.objects.filter(
#             alert_level='LOW',
#             status='NEW'
#         ).count()
        
#         # ========== Gender distribution ==========
#         male_patients = PatientProfile.objects.filter(gender='MALE').count()
#         female_patients = PatientProfile.objects.filter(gender='FEMALE').count()
#         other_gender_patients = PatientProfile.objects.filter(gender='OTHER').count()
        
#         # ========== Age group distribution ==========
#         age_groups = {
#             '0-18': 0,
#             '19-30': 0,
#             '31-50': 0,
#             '51-70': 0,
#             '70+': 0
#         }
        
#         for patient_profile in PatientProfile.objects.all():
#             try:
#                 if patient_profile.date_of_birth:
#                     age = calculate_age(patient_profile.date_of_birth)
#                     if age:
#                         if age <= 18:
#                             age_groups['0-18'] += 1
#                         elif age <= 30:
#                             age_groups['19-30'] += 1
#                         elif age <= 50:
#                             age_groups['31-50'] += 1
#                         elif age <= 70:
#                             age_groups['51-70'] += 1
#                         else:
#                             age_groups['70+'] += 1
#             except Exception as e:
#                 continue
        
#         # ========== Cancer stage distribution ==========
#         stage_1 = PatientMedicalRecord.objects.filter(cancer_stage='STAGE_1').count()
#         stage_2 = PatientMedicalRecord.objects.filter(cancer_stage='STAGE_2').count()
#         stage_3 = PatientMedicalRecord.objects.filter(cancer_stage='STAGE_3').count()
#         stage_4 = PatientMedicalRecord.objects.filter(cancer_stage='STAGE_4').count()
        
#         # ========== Response ==========
#         return Response({
#             'success': True,
#             'data': {
#                 # Total Counts
#                 'total_patients': total_patients,
#                 'total_doctors': total_doctors,
#                 'total_nurses': total_nurses,
                
#                 # Questionnaires
#                 'active_questionnaires': active_questionnaires,
#                 'reports_generated': reports_generated,
                
#                 # Patient Activity
#                 'patient_activity': patient_activity,
                
#                 # Questionnaire Completion
#                 'questionnaire_completion': {
#                     'rate': completion_rate,
#                     'total': total_questionnaires,
#                     'completed': completed_questionnaires
#                 },
                
#                 # Additional Stats
#                 'additional_stats': {
#                     'active_alerts': active_alerts,
#                     'critical_patients': critical_patients
#                 },
                
#                 # Recent Alerts
#                 'recent_alerts': AlertSerializer(
#                     Alert.objects.filter(status='NEW')[:5], 
#                     many=True
#                 ).data,
                
#                 # Patient Statistics (Overall)
#                 'patient_stats': {
#                     'active_patients': active_patients,
#                     'inactive_patients': inactive_patients,
#                     'total_patients': total_patients,
#                     'active_percentage': round((active_patients / total_patients * 100) if total_patients > 0 else 0, 1),
#                     'inactive_percentage': round((inactive_patients / total_patients * 100) if total_patients > 0 else 0, 1)
#                 },
                
#                 # Patient Details with Active/Inactive Status
#                 'patient_details': {
#                     'active': {
#                         'count': len(active_patient_details),
#                         'patients': active_patient_details
#                     },
#                     'inactive': {
#                         'count': len(inactive_patient_details),
#                         'patients': inactive_patient_details
#                     }
#                 },
                
#                 # Doctor Statistics
#                 'doctor_stats': {
#                     'total': total_doctors,
#                     'active': active_doctors,
#                     'inactive': inactive_doctors,
#                     'active_percentage': round((active_doctors / total_doctors * 100) if total_doctors > 0 else 0, 1),
#                     'inactive_percentage': round((inactive_doctors / total_doctors * 100) if total_doctors > 0 else 0, 1)
#                 },
                
#                 # Doctor Details with Active/Inactive Status
#                 'doctor_details': {
#                     'active': {
#                         'count': len(active_doctor_details),
#                         'doctors': active_doctor_details
#                     },
#                     'inactive': {
#                         'count': len(inactive_doctor_details),
#                         'doctors': inactive_doctor_details
#                     }
#                 },
                
#                 # Nurse Statistics
#                 'nurse_stats': {
#                     'total': total_nurses,
#                     'active': active_nurses,
#                     'inactive': inactive_nurses,
#                     'active_percentage': round((active_nurses / total_nurses * 100) if total_nurses > 0 else 0, 1),
#                     'inactive_percentage': round((inactive_nurses / total_nurses * 100) if total_nurses > 0 else 0, 1)
#                 },
                
#                 # Nurse Details with Active/Inactive Status
#                 'nurse_details': {
#                     'active': {
#                         'count': len(active_nurse_details),
#                         'nurses': active_nurse_details
#                     },
#                     'inactive': {
#                         'count': len(inactive_nurse_details),
#                         'nurses': inactive_nurse_details
#                     }
#                 },
                
#                 # Question Statistics
#                 'question_stats': {
#                     'active_questions': active_questions,
#                     'total_active_questionnaires': active_questionnaires
#                 },
                
#                 # Recovery Statistics
#                 'recovery_stats': {
#                     'recovery_rate': recovery_rate,
#                     'improving_patients': improving_patients,
#                     'total_patients_tracked': total_patients_with_status,
#                     'remaining_patients': total_patients_with_status - improving_patients
#                 },
                
#                 # Gender Distribution
#                 'gender_distribution': {
#                     'male': male_patients,
#                     'female': female_patients,
#                     'other': other_gender_patients,
#                     'male_percentage': round((male_patients / total_patients * 100) if total_patients > 0 else 0, 1),
#                     'female_percentage': round((female_patients / total_patients * 100) if total_patients > 0 else 0, 1),
#                     'other_percentage': round((other_gender_patients / total_patients * 100) if total_patients > 0 else 0, 1)
#                 },
                
#                 # Age Distribution
#                 'age_distribution': age_groups,
                
#                 # Alert Statistics
#                 'alert_stats': {
#                     'high_severity': high_severity_alerts,
#                     'medium_severity': medium_severity_alerts,
#                     'low_severity': low_severity_alerts,
#                     'total_active': active_alerts
#                 },
                
#                 # Cancer Stage Distribution
#                 'cancer_stage_distribution': {
#                     'stage_1': stage_1,
#                     'stage_2': stage_2,
#                     'stage_3': stage_3,
#                     'stage_4': stage_4,
#                     'early_stage': stage_1 + stage_2,
#                     'late_stage': stage_3 + stage_4
#                 }
#             }
#         })
    
#     elif user.user_type == 'DOCTOR':
#         try:
#             doctor = DoctorProfile.objects.get(user=user)
            
#             # Patients assigned to this doctor (from PatientMedicalRecord)
#             patients = PatientMedicalRecord.objects.filter(
#                 treating_doctor=doctor
#             ).count()
            
#             escalated_alerts = Alert.objects.filter(
#                 escalated_to_doctor=doctor,
#                 status='ESCALATED'
#             ).count()
            
#             # Active patients for this doctor
#             last_7_days_ago = today - timedelta(days=7)
#             last_7_days_start = datetime.combine(last_7_days_ago, datetime.min.time())
#             today_datetime = datetime.combine(today, datetime.max.time())
            
#             recent_responses = DailyResponse.objects.filter(
#                 response_date__gte=last_7_days_start,
#                 response_date__lte=today_datetime
#             )
            
#             active_patient_ids = set()
#             for response in recent_responses:
#                 try:
#                     if response.patient and response.patient.treating_doctor == doctor:
#                         if response.patient.patient:
#                             active_patient_ids.add(response.patient.patient.patient_id)
#                 except Exception as e:
#                     continue
            
#             active_patients = len(active_patient_ids)
#             inactive_patients = patients - active_patients
            
#             # Get detailed patient list for this doctor
#             doctor_patients = PatientMedicalRecord.objects.filter(treating_doctor=doctor)
#             patient_details_list = []
            
#             for patient_record in doctor_patients:
#                 try:
#                     patient = patient_record.patient
#                     if patient:
#                         # Check if patient is active
#                         is_active = False
#                         last_response_date = None
                        
#                         patient_responses = DailyResponse.objects.filter(
#                             patient=patient_record,
#                             response_date__gte=last_7_days_start,
#                             response_date__lte=today_datetime
#                         )
#                         is_active = patient_responses.exists()
                        
#                         last_response = DailyResponse.objects.filter(
#                             patient=patient_record
#                         ).order_by('-response_date').first()
#                         if last_response:
#                             last_response_date = last_response.response_date
                        
#                         patient_details_list.append({
#                             'patient_id': patient.patient_id,
#                             'name': f"{patient.first_name} {patient.last_name}".strip() or patient.user.username,
#                             'email': patient.user.email,
#                             'phone': patient.user.phone_number,
#                             'status': 'ACTIVE' if is_active else 'INACTIVE',
#                             'last_response_date': last_response_date,
#                             'gender': patient.gender,
#                             'health_status': patient_record.health_status,
#                             'cancer_stage': patient_record.cancer_stage
#                         })
#                 except Exception as e:
#                     continue
            
#             active_patient_details = [p for p in patient_details_list if p['status'] == 'ACTIVE']
#             inactive_patient_details = [p for p in patient_details_list if p['status'] == 'INACTIVE']
            
#             # Recovery rate for doctor's patients
#             total_patients_with_status = 0
#             improving_patients = 0
            
#             for patient_record in doctor_patients:
#                 try:
#                     if patient_record.health_status:
#                         total_patients_with_status += 1
#                         if patient_record.health_status == 'IMPROVING':
#                             improving_patients += 1
#                 except Exception as e:
#                     continue
            
#             recovery_rate = round(
#                 (improving_patients / total_patients_with_status * 100) 
#                 if total_patients_with_status > 0 else 0, 
#                 1
#             )
            
#             # Critical patients under this doctor
#             critical_patients = PatientMedicalRecord.objects.filter(
#                 treating_doctor=doctor,
#                 cancer_stage__in=['STAGE_3', 'STAGE_4']
#             ).count()
            
#             return Response({
#                 'success': True,
#                 'data': {
#                     'total_patients': patients,
#                     'escalated_alerts': escalated_alerts,
#                     'patient_stats': {
#                         'active_patients': active_patients,
#                         'inactive_patients': inactive_patients,
#                         'total_patients': patients,
#                         'active_percentage': round((active_patients / patients * 100) if patients > 0 else 0, 1),
#                         'inactive_percentage': round((inactive_patients / patients * 100) if patients > 0 else 0, 1)
#                     },
#                     'patient_details': {
#                         'active': {
#                             'count': len(active_patient_details),
#                             'patients': active_patient_details
#                         },
#                         'inactive': {
#                             'count': len(inactive_patient_details),
#                             'patients': inactive_patient_details
#                         }
#                     },
#                     'recovery_stats': {
#                         'recovery_rate': recovery_rate,
#                         'improving_patients': improving_patients,
#                         'total_patients_tracked': total_patients_with_status,
#                         'remaining_patients': total_patients_with_status - improving_patients
#                     },
#                     'critical_patients': critical_patients
#                 }
#             })
            
#         except DoctorProfile.DoesNotExist:
#             raise APIError("Doctor profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
#     return Response({
#         'success': True,
#         'data': {}
#     })

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
            
            # Patients assigned to this nurse (from PatientMedicalRecord)
            total_patients = PatientMedicalRecord.objects.filter(
                assigned_nurse=nurse
            ).count()
            
            # New alerts for this nurse
            new_alerts = Alert.objects.filter(
                assigned_to_nurse=nurse,
                status='NEW'
            ).count()
            
            # Today responses
            today_responses = DailyResponse.objects.filter(
                response_date__gte=start_of_month,
                response_date__lte=today
            ).count()
            
            # Pending questionnaires
            pending_questionnaires = QuestionnaireAssignment.objects.filter(
                status='PENDING'
            ).count()
            
            # Active patients for this nurse (submitted response in last 7 days)
            last_7_days_ago = today - timedelta(days=7)
            last_7_days_start = datetime.combine(last_7_days_ago, datetime.min.time())
            
            recent_responses = DailyResponse.objects.filter(
                response_date__gte=last_7_days_start,
                response_date__lte=today_datetime
            )
            
            active_patient_ids = set()
            for response in recent_responses:
                try:
                    if response.patient and response.patient.assigned_nurse == nurse:
                        if response.patient.patient:
                            active_patient_ids.add(response.patient.patient.patient_id)
                except Exception as e:
                    continue
            
            active_patients = len(active_patient_ids)
            inactive_patients = total_patients - active_patients
            
            # Get detailed patient list for this nurse
            nurse_patients = PatientMedicalRecord.objects.filter(assigned_nurse=nurse)
            patient_details_list = []
            
            for patient_record in nurse_patients:
                try:
                    patient = patient_record.patient
                    if patient:
                        # Check if patient is active
                        is_active = False
                        last_response_date = None
                        
                        patient_responses = DailyResponse.objects.filter(
                            patient=patient_record,
                            response_date__gte=last_7_days_start,
                            response_date__lte=today_datetime
                        )
                        is_active = patient_responses.exists()
                        
                        last_response = DailyResponse.objects.filter(
                            patient=patient_record
                        ).order_by('-response_date').first()
                        if last_response:
                            last_response_date = last_response.response_date
                        
                        patient_details_list.append({
                            'patient_id': patient.patient_id,
                            'name': f"{patient.first_name} {patient.last_name}".strip() or patient.user.username,
                            'email': patient.user.email,
                            'phone': patient.user.phone_number,
                            'status': 'ACTIVE' if is_active else 'INACTIVE',
                            'last_response_date': last_response_date,
                            'gender': patient.gender,
                            'health_status': patient_record.health_status if hasattr(patient_record, 'health_status') else None,
                            'cancer_stage': patient_record.cancer_stage if hasattr(patient_record, 'cancer_stage') else None
                        })
                except Exception as e:
                    continue
            
            active_patient_details = [p for p in patient_details_list if p['status'] == 'ACTIVE']
            inactive_patient_details = [p for p in patient_details_list if p['status'] == 'INACTIVE']
            
            # Recovery rate for nurse's patients
            total_patients_with_status = 0
            improving_patients = 0
            
            for patient in nurse_patients:
                try:
                    if hasattr(patient, 'health_status') and patient.health_status:
                        total_patients_with_status += 1
                        if patient.health_status == 'IMPROVING':
                            improving_patients += 1
                except Exception as e:
                    continue
            
            recovery_rate = round(
                (improving_patients / total_patients_with_status * 100) 
                if total_patients_with_status > 0 else 0, 
                1
            )
            
            return Response({
                'success': True,
                'data': {
                    'total_patients': total_patients,
                    'new_alerts': new_alerts,
                    'today_responses': today_responses,
                    'pending_questionnaires': pending_questionnaires,
                    'patient_stats': {
                        'active_patients': active_patients,
                        'inactive_patients': inactive_patients,
                        'total_patients': total_patients,
                        'active_percentage': round((active_patients / total_patients * 100) if total_patients > 0 else 0, 1),
                        'inactive_percentage': round((inactive_patients / total_patients * 100) if total_patients > 0 else 0, 1)
                    },
                    'patient_details': {
                        'active': {
                            'count': len(active_patient_details),
                            'patients': active_patient_details
                        },
                        'inactive': {
                            'count': len(inactive_patient_details),
                            'patients': inactive_patient_details
                        }
                    },
                    'recovery_stats': {
                        'recovery_rate': recovery_rate,
                        'improving_patients': improving_patients,
                        'total_patients_tracked': total_patients_with_status,
                        'remaining_patients': total_patients_with_status - improving_patients
                    },
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
        # ========== Total Counts from Profile Models ==========
        total_patients = PatientProfile.objects.count()
        total_doctors = DoctorProfile.objects.count()
        total_nurses = NurseProfile.objects.count()
        
        # ========== Active Patients (submitted response in last 7 days) ==========
        last_7_days_ago = today - timedelta(days=7)
        last_7_days_start = datetime.combine(last_7_days_ago, datetime.min.time())
        
        recent_responses = DailyResponse.objects.filter(
            response_date__gte=last_7_days_start,
            response_date__lte=today_datetime
        )
        
        active_patient_ids = set()
        for response in recent_responses:
            try:
                if response.patient and response.patient.patient:
                    active_patient_ids.add(response.patient.patient.patient_id)
            except Exception as e:
                continue
        
        active_patients = len(active_patient_ids)
        inactive_patients = total_patients - active_patients
        
        # ========== Active Questions ==========
        active_question_ids = set()
        for response in recent_responses:
            try:
                question_responses = QuestionResponse.objects.filter(daily_response=response)
                for qr in question_responses:
                    if qr.assigned_question:
                        active_question_ids.add(qr.assigned_question.pk)
            except Exception as e:
                continue
        
        active_questions = len(active_question_ids)
        
        # ========== Active Questionnaires ==========
        active_questionnaires = QuestionnaireAssignment.objects.filter(
            status='IN_PROGRESS'
        ).count()
        
        # ========== Reports Generated ==========
        reports_generated = QuestionnaireAssignment.objects.filter(
            status='COMPLETED'
        ).count()
        
        # ========== Staff Statistics (Manual count for Djongo compatibility) ==========
        # Active Doctors - Manual count
        active_doctors = 0
        for doctor in DoctorProfile.objects.all():
            try:
                is_active = getattr(doctor, 'is_active', True)
                if is_active:
                    active_doctors += 1
            except Exception as e:
                active_doctors += 1
        inactive_doctors = total_doctors - active_doctors
        
        # Active Nurses - Manual count
        active_nurses = 0
        for nurse in NurseProfile.objects.all():
            try:
                is_active = getattr(nurse, 'is_active', True)
                if is_active:
                    active_nurses += 1
            except Exception as e:
                active_nurses += 1
        inactive_nurses = total_nurses - active_nurses
        
        # ========== Doctor Details with Active/Inactive Status ==========
        doctor_details_list = []
        for doctor in DoctorProfile.objects.all():
            try:
                # Check if doctor is active based on is_active field
                is_doctor_active = getattr(doctor, 'is_active', True)
                
                # Get patient count for this doctor
                patient_count = PatientMedicalRecord.objects.filter(treating_doctor=doctor).count()
                
                # Get assigned patients list (remove duplicates)
                assigned_patients = []
                seen_patients = set()
                patient_records = PatientMedicalRecord.objects.filter(treating_doctor=doctor)
                for pr in patient_records:
                    if pr.patient and pr.patient.patient_id not in seen_patients:
                        seen_patients.add(pr.patient.patient_id)
                        assigned_patients.append({
                            'patient_id': pr.patient.patient_id,
                            'name': f"{pr.patient.first_name} {pr.patient.last_name}".strip() or pr.patient.user.username
                        })
                
                # Get name from doctor fields
                doctor_name = ""
                if hasattr(doctor, 'first_name') and doctor.first_name:
                    doctor_name = f"{doctor.first_name} {doctor.last_name}".strip()
                else:
                    doctor_name = f"{doctor.user.first_name} {doctor.user.last_name}".strip() or doctor.user.username
                
                doctor_details_list.append({
                    'doctor_id': doctor.pk,
                    'name': doctor_name,
                    'email': getattr(doctor, 'email', None) or doctor.user.email,
                    'phone': getattr(doctor, 'phone_number', None) or doctor.user.phone_number,
                    'specialization': getattr(doctor, 'specialization', None),
                    'status': 'ACTIVE' if is_doctor_active else 'INACTIVE',
                    'patient_count': patient_count,
                    'assigned_patients': assigned_patients[:10]
                })
            except Exception as e:
                print(f"Error processing doctor {doctor.pk}: {e}")
                continue
        
        active_doctor_details = [d for d in doctor_details_list if d['status'] == 'ACTIVE']
        inactive_doctor_details = [d for d in doctor_details_list if d['status'] == 'INACTIVE']
        
        # ========== Nurse Details with Active/Inactive Status ==========
        nurse_details_list = []
        for nurse in NurseProfile.objects.all():
            try:
                # Check if nurse is active based on is_active field
                is_nurse_active = getattr(nurse, 'is_active', True)
                
                # Get patient count for this nurse
                patient_count = PatientMedicalRecord.objects.filter(assigned_nurse=nurse).count()
                
                # Get assigned patients list (remove duplicates)
                assigned_patients = []
                seen_patients = set()
                patient_records = PatientMedicalRecord.objects.filter(assigned_nurse=nurse)
                for pr in patient_records:
                    if pr.patient and pr.patient.patient_id not in seen_patients:
                        seen_patients.add(pr.patient.patient_id)
                        assigned_patients.append({
                            'patient_id': pr.patient.patient_id,
                            'name': f"{pr.patient.first_name} {pr.patient.last_name}".strip() or pr.patient.user.username
                        })
                
                # Get name from nurse fields
                nurse_name = ""
                if hasattr(nurse, 'first_name') and nurse.first_name:
                    nurse_name = f"{nurse.first_name} {nurse.last_name}".strip()
                else:
                    nurse_name = f"{nurse.user.first_name} {nurse.user.last_name}".strip() or nurse.user.username
                
                nurse_details_list.append({
                    'nurse_id': nurse.pk,
                    'name': nurse_name,
                    'email': getattr(nurse, 'email', None) or nurse.user.email,
                    'phone': getattr(nurse, 'phone_number', None) or nurse.user.phone_number,
                    'status': 'ACTIVE' if is_nurse_active else 'INACTIVE',
                    'patient_count': patient_count,
                    'assigned_patients': assigned_patients[:10]
                })
            except Exception as e:
                print(f"Error processing nurse {nurse.pk}: {e}")
                continue
        
        active_nurse_details = [n for n in nurse_details_list if n['status'] == 'ACTIVE']
        inactive_nurse_details = [n for n in nurse_details_list if n['status'] == 'INACTIVE']
        
        # ========== Patient Details with Active/Inactive Status ==========
        from datetime import date as date_module
        
        def calculate_age(birth_date):
            if birth_date:
                today_date = date_module.today()
                return today_date.year - birth_date.year - (
                    (today_date.month, today_date.day) < (birth_date.month, birth_date.day)
                )
            return None
        
        patient_details_list = []
        for patient in PatientProfile.objects.all():
            try:
                # Get patient medical record
                medical_record = PatientMedicalRecord.objects.filter(patient=patient).first()
                
                # Check if patient has any response in last 7 days
                has_recent_response = False
                last_response_date = None
                
                if medical_record:
                    # Check for responses in last 7 days
                    recent_patient_responses = DailyResponse.objects.filter(
                        patient=medical_record,
                        response_date__gte=last_7_days_start,
                        response_date__lte=today_datetime
                    )
                    has_recent_response = recent_patient_responses.exists()
                    
                    # Get last response date
                    last_response = DailyResponse.objects.filter(
                        patient=medical_record
                    ).order_by('-response_date').first()
                    if last_response:
                        last_response_date = last_response.response_date
                
                # Get nurse and doctor names
                nurse_name = None
                doctor_name = None
                if medical_record:
                    if medical_record.assigned_nurse:
                        nurse = medical_record.assigned_nurse
                        if hasattr(nurse, 'first_name') and nurse.first_name:
                            nurse_name = f"{nurse.first_name} {nurse.last_name}".strip()
                        else:
                            nurse_name = f"{nurse.user.first_name} {nurse.user.last_name}".strip() or nurse.user.username
                    if medical_record.treating_doctor:
                        doctor = medical_record.treating_doctor
                        if hasattr(doctor, 'first_name') and doctor.first_name:
                            doctor_name = f"{doctor.first_name} {doctor.last_name}".strip()
                        else:
                            doctor_name = f"{doctor.user.first_name} {doctor.user.last_name}".strip() or doctor.user.username
                
                # Calculate age
                patient_age = None
                if patient.date_of_birth:
                    patient_age = calculate_age(patient.date_of_birth)
                
                # Get health status and cancer stage safely
                health_status = None
                cancer_stage = None
                if medical_record:
                    if hasattr(medical_record, 'health_status'):
                        health_status = medical_record.health_status
                    if hasattr(medical_record, 'cancer_stage'):
                        cancer_stage = medical_record.cancer_stage
                
                patient_info = {
                    'patient_id': patient.patient_id,
                    'name': f"{patient.first_name} {patient.last_name}".strip() or patient.user.username,
                    'email': patient.user.email,
                    'phone': patient.user.phone_number,
                    'status': 'ACTIVE' if has_recent_response else 'INACTIVE',
                    'last_response_date': last_response_date,
                    'assigned_nurse': nurse_name,
                    'treating_doctor': doctor_name,
                    'gender': patient.gender,
                    'age': patient_age,
                    'blood_group': getattr(patient, 'blood_group', None),
                    'address': getattr(patient, 'address', None),
                    'health_status': health_status,
                    'cancer_stage': cancer_stage
                }
                patient_details_list.append(patient_info)
                
            except Exception as e:
                print(f"Error processing patient {patient.pk}: {e}")
                continue
        
        active_patient_details = [p for p in patient_details_list if p['status'] == 'ACTIVE']
        inactive_patient_details = [p for p in patient_details_list if p['status'] == 'INACTIVE']
        
        # ========== Recovery Rate ==========
        all_patient_records = PatientMedicalRecord.objects.all()
        total_patients_with_status = 0
        improving_patients = 0
        
        for patient_record in all_patient_records:
            try:
                if hasattr(patient_record, 'health_status') and patient_record.health_status:
                    total_patients_with_status += 1
                    if patient_record.health_status == 'IMPROVING':
                        improving_patients += 1
            except Exception as e:
                continue
        
        recovery_rate = round(
            (improving_patients / total_patients_with_status * 100) 
            if total_patients_with_status > 0 else 0, 
            1
        )
        
        # ========== Patient Activity - last 7 days ==========
        last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        patient_activity = []
        for day in last_7_days:
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
        
        # ========== Questionnaire Completion Rate ==========
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
        
        # ========== Additional Stats ==========
        active_alerts = Alert.objects.filter(status='NEW').count()
        
        # Critical patients count
        critical_patients = 0
        for record in PatientMedicalRecord.objects.all():
            try:
                if hasattr(record, 'cancer_stage') and record.cancer_stage in ['STAGE_3', 'STAGE_4']:
                    critical_patients += 1
            except Exception as e:
                continue
        
        # Alert statistics by severity
        high_severity_alerts = Alert.objects.filter(
            alert_level='HIGH',
            status='NEW'
        ).count()
        
        medium_severity_alerts = Alert.objects.filter(
            alert_level='MEDIUM',
            status='NEW'
        ).count()
        
        low_severity_alerts = Alert.objects.filter(
            alert_level='LOW',
            status='NEW'
        ).count()
        
        # ========== Gender distribution ==========
        male_patients = PatientProfile.objects.filter(gender='MALE').count()
        female_patients = PatientProfile.objects.filter(gender='FEMALE').count()
        other_gender_patients = PatientProfile.objects.filter(gender='OTHER').count()
        
        # ========== Age group distribution ==========
        age_groups = {
            '0-18': 0,
            '19-30': 0,
            '31-50': 0,
            '51-70': 0,
            '70+': 0
        }
        
        for patient_profile in PatientProfile.objects.all():
            try:
                if patient_profile.date_of_birth:
                    age = calculate_age(patient_profile.date_of_birth)
                    if age:
                        if age <= 18:
                            age_groups['0-18'] += 1
                        elif age <= 30:
                            age_groups['19-30'] += 1
                        elif age <= 50:
                            age_groups['31-50'] += 1
                        elif age <= 70:
                            age_groups['51-70'] += 1
                        else:
                            age_groups['70+'] += 1
            except Exception as e:
                continue
        
        # ========== Cancer stage distribution ==========
        stage_1 = 0
        stage_2 = 0
        stage_3 = 0
        stage_4 = 0
        
        for record in PatientMedicalRecord.objects.all():
            try:
                if hasattr(record, 'cancer_stage'):
                    if record.cancer_stage == 'STAGE_1':
                        stage_1 += 1
                    elif record.cancer_stage == 'STAGE_2':
                        stage_2 += 1
                    elif record.cancer_stage == 'STAGE_3':
                        stage_3 += 1
                    elif record.cancer_stage == 'STAGE_4':
                        stage_4 += 1
            except Exception as e:
                continue
        
        # ========== Response ==========
        return Response({
            'success': True,
            'data': {
                # Total Counts
                'total_patients': total_patients,
                'total_doctors': total_doctors,
                'total_nurses': total_nurses,
                
                # Questionnaires
                'active_questionnaires': active_questionnaires,
                'reports_generated': reports_generated,
                
                # Patient Activity
                'patient_activity': patient_activity,
                
                # Questionnaire Completion
                'questionnaire_completion': {
                    'rate': completion_rate,
                    'total': total_questionnaires,
                    'completed': completed_questionnaires
                },
                
                # Additional Stats
                'additional_stats': {
                    'active_alerts': active_alerts,
                    'critical_patients': critical_patients
                },
                
                # Recent Alerts
                'recent_alerts': AlertSerializer(
                    Alert.objects.filter(status='NEW')[:5], 
                    many=True
                ).data,
                
                # Patient Statistics (Overall)
                'patient_stats': {
                    'active_patients': active_patients,
                    'inactive_patients': inactive_patients,
                    'total_patients': total_patients,
                    'active_percentage': round((active_patients / total_patients * 100) if total_patients > 0 else 0, 1),
                    'inactive_percentage': round((inactive_patients / total_patients * 100) if total_patients > 0 else 0, 1)
                },
                
                # Patient Details with Active/Inactive Status
                'patient_details': {
                    'active': {
                        'count': len(active_patient_details),
                        'patients': active_patient_details
                    },
                    'inactive': {
                        'count': len(inactive_patient_details),
                        'patients': inactive_patient_details
                    }
                },
                
                # Doctor Statistics
                'doctor_stats': {
                    'total': total_doctors,
                    'active': active_doctors,
                    'inactive': inactive_doctors,
                    'active_percentage': round((active_doctors / total_doctors * 100) if total_doctors > 0 else 0, 1),
                    'inactive_percentage': round((inactive_doctors / total_doctors * 100) if total_doctors > 0 else 0, 1)
                },
                
                # Doctor Details with Active/Inactive Status
                'doctor_details': {
                    'active': {
                        'count': len(active_doctor_details),
                        'doctors': active_doctor_details
                    },
                    'inactive': {
                        'count': len(inactive_doctor_details),
                        'doctors': inactive_doctor_details
                    }
                },
                
                # Nurse Statistics
                'nurse_stats': {
                    'total': total_nurses,
                    'active': active_nurses,
                    'inactive': inactive_nurses,
                    'active_percentage': round((active_nurses / total_nurses * 100) if total_nurses > 0 else 0, 1),
                    'inactive_percentage': round((inactive_nurses / total_nurses * 100) if total_nurses > 0 else 0, 1)
                },
                
                # Nurse Details with Active/Inactive Status
                'nurse_details': {
                    'active': {
                        'count': len(active_nurse_details),
                        'nurses': active_nurse_details
                    },
                    'inactive': {
                        'count': len(inactive_nurse_details),
                        'nurses': inactive_nurse_details
                    }
                },
                
                # Question Statistics
                'question_stats': {
                    'active_questions': active_questions,
                    'total_active_questionnaires': active_questionnaires
                },
                
                # Recovery Statistics
                'recovery_stats': {
                    'recovery_rate': recovery_rate,
                    'improving_patients': improving_patients,
                    'total_patients_tracked': total_patients_with_status,
                    'remaining_patients': total_patients_with_status - improving_patients
                },
                
                # Gender Distribution
                'gender_distribution': {
                    'male': male_patients,
                    'female': female_patients,
                    'other': other_gender_patients,
                    'male_percentage': round((male_patients / total_patients * 100) if total_patients > 0 else 0, 1),
                    'female_percentage': round((female_patients / total_patients * 100) if total_patients > 0 else 0, 1),
                    'other_percentage': round((other_gender_patients / total_patients * 100) if total_patients > 0 else 0, 1)
                },
                
                # Age Distribution
                'age_distribution': age_groups,
                
                # Alert Statistics
                'alert_stats': {
                    'high_severity': high_severity_alerts,
                    'medium_severity': medium_severity_alerts,
                    'low_severity': low_severity_alerts,
                    'total_active': active_alerts
                },
                
                # Cancer Stage Distribution
                'cancer_stage_distribution': {
                    'stage_1': stage_1,
                    'stage_2': stage_2,
                    'stage_3': stage_3,
                    'stage_4': stage_4,
                    'early_stage': stage_1 + stage_2,
                    'late_stage': stage_3 + stage_4
                }
            }
        })
    
    elif user.user_type == 'DOCTOR':
        try:
            doctor = DoctorProfile.objects.get(user=user)
            
            # Patients assigned to this doctor (from PatientMedicalRecord)
            patients = PatientMedicalRecord.objects.filter(
                treating_doctor=doctor
            ).count()
            
            escalated_alerts = Alert.objects.filter(
                escalated_to_doctor=doctor,
                status='ESCALATED'
            ).count()
            
            # Active patients for this doctor
            last_7_days_ago = today - timedelta(days=7)
            last_7_days_start = datetime.combine(last_7_days_ago, datetime.min.time())
            today_datetime = datetime.combine(today, datetime.max.time())
            
            recent_responses = DailyResponse.objects.filter(
                response_date__gte=last_7_days_start,
                response_date__lte=today_datetime
            )
            
            active_patient_ids = set()
            for response in recent_responses:
                try:
                    if response.patient and response.patient.treating_doctor == doctor:
                        if response.patient.patient:
                            active_patient_ids.add(response.patient.patient.patient_id)
                except Exception as e:
                    continue
            
            active_patients = len(active_patient_ids)
            inactive_patients = patients - active_patients
            
            # Get detailed patient list for this doctor
            doctor_patients = PatientMedicalRecord.objects.filter(treating_doctor=doctor)
            patient_details_list = []
            
            for patient_record in doctor_patients:
                try:
                    patient = patient_record.patient
                    if patient:
                        # Check if patient is active
                        is_active = False
                        last_response_date = None
                        
                        patient_responses = DailyResponse.objects.filter(
                            patient=patient_record,
                            response_date__gte=last_7_days_start,
                            response_date__lte=today_datetime
                        )
                        is_active = patient_responses.exists()
                        
                        last_response = DailyResponse.objects.filter(
                            patient=patient_record
                        ).order_by('-response_date').first()
                        if last_response:
                            last_response_date = last_response.response_date
                        
                        patient_details_list.append({
                            'patient_id': patient.patient_id,
                            'name': f"{patient.first_name} {patient.last_name}".strip() or patient.user.username,
                            'email': patient.user.email,
                            'phone': patient.user.phone_number,
                            'status': 'ACTIVE' if is_active else 'INACTIVE',
                            'last_response_date': last_response_date,
                            'gender': patient.gender,
                            'health_status': patient_record.health_status if hasattr(patient_record, 'health_status') else None,
                            'cancer_stage': patient_record.cancer_stage if hasattr(patient_record, 'cancer_stage') else None
                        })
                except Exception as e:
                    continue
            
            active_patient_details = [p for p in patient_details_list if p['status'] == 'ACTIVE']
            inactive_patient_details = [p for p in patient_details_list if p['status'] == 'INACTIVE']
            
            # Recovery rate for doctor's patients
            total_patients_with_status = 0
            improving_patients = 0
            
            for patient_record in doctor_patients:
                try:
                    if hasattr(patient_record, 'health_status') and patient_record.health_status:
                        total_patients_with_status += 1
                        if patient_record.health_status == 'IMPROVING':
                            improving_patients += 1
                except Exception as e:
                    continue
            
            recovery_rate = round(
                (improving_patients / total_patients_with_status * 100) 
                if total_patients_with_status > 0 else 0, 
                1
            )
            
            # Critical patients under this doctor
            critical_patients = 0
            for record in doctor_patients:
                try:
                    if hasattr(record, 'cancer_stage') and record.cancer_stage in ['STAGE_3', 'STAGE_4']:
                        critical_patients += 1
                except Exception as e:
                    continue
            
            return Response({
                'success': True,
                'data': {
                    'total_patients': patients,
                    'escalated_alerts': escalated_alerts,
                    'patient_stats': {
                        'active_patients': active_patients,
                        'inactive_patients': inactive_patients,
                        'total_patients': patients,
                        'active_percentage': round((active_patients / patients * 100) if patients > 0 else 0, 1),
                        'inactive_percentage': round((inactive_patients / patients * 100) if patients > 0 else 0, 1)
                    },
                    'patient_details': {
                        'active': {
                            'count': len(active_patient_details),
                            'patients': active_patient_details
                        },
                        'inactive': {
                            'count': len(inactive_patient_details),
                            'patients': inactive_patient_details
                        }
                    },
                    'recovery_stats': {
                        'recovery_rate': recovery_rate,
                        'improving_patients': improving_patients,
                        'total_patients_tracked': total_patients_with_status,
                        'remaining_patients': total_patients_with_status - improving_patients
                    },
                    'critical_patients': critical_patients
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
    """Get dashboard statistics using monitoring models - Djongo compatible"""
    user = request.user
    
    if user.user_type != 'ADMIN':
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    # Get date filters
    period = request.query_params.get('period', 'this_month')
    start_date_str = request.query_params.get('start_date')
    end_date_str = request.query_params.get('end_date')
    
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
    elif period == 'custom' and start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
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
    
    # 1. Total Patients - Get all and filter in Python
    all_patients = list(PatientMedicalRecord.objects.all())
    total_patients = len([p for p in all_patients if p.created_at and p.created_at <= end_datetime])
    
    prev_patients = len([p for p in all_patients if p.created_at and prev_start_datetime <= p.created_at <= prev_end_datetime])
    
    patients_change = calculate_percentage_change(prev_patients, total_patients)
    
    # 2. Active Cases - Get all DailyResponses and filter in Python
    all_responses = list(DailyResponse.objects.all())
    
    active_cases = len([
        r for r in all_responses 
        if r.is_completed and r.completed_at and 
        start_datetime <= r.completed_at <= end_datetime
    ])
    
    prev_active = len([
        r for r in all_responses 
        if r.is_completed and r.completed_at and 
        prev_start_datetime <= r.completed_at <= prev_end_datetime
    ])
    
    active_change = calculate_percentage_change(prev_active, active_cases)
    
    # 3. Critical Cases - Get all Alerts and filter in Python
    all_alerts = list(Alert.objects.all())
    
    critical_cases = len([
        a for a in all_alerts 
        if a.alert_level == 'CRITICAL' and 
        a.status in ['NEW', 'ACKNOWLEDGED', 'IN_PROGRESS'] and
        a.created_at and start_datetime <= a.created_at <= end_datetime
    ])
    
    prev_critical = len([
        a for a in all_alerts 
        if a.alert_level == 'CRITICAL' and 
        a.status in ['NEW', 'ACKNOWLEDGED', 'IN_PROGRESS'] and
        a.created_at and prev_start_datetime <= a.created_at <= prev_end_datetime
    ])
    
    critical_change = calculate_percentage_change(prev_critical, critical_cases)
    
    # 4. Recovery Rate
    completed_alerts = len([
        a for a in all_alerts 
        if a.status == 'RESOLVED' and a.resolved_at and
        start_datetime <= a.resolved_at <= end_datetime
    ])
    
    total_alerts = len([
        a for a in all_alerts 
        if a.created_at and start_datetime <= a.created_at <= end_datetime
    ])
    
    recovery_rate = (completed_alerts / total_alerts * 100) if total_alerts > 0 else 0
    
    prev_completed = len([
        a for a in all_alerts 
        if a.status == 'RESOLVED' and a.resolved_at and
        prev_start_datetime <= a.resolved_at <= prev_end_datetime
    ])
    
    prev_total = len([
        a for a in all_alerts 
        if a.created_at and prev_start_datetime <= a.created_at <= prev_end_datetime
    ])
    
    prev_rate = (prev_completed / prev_total * 100) if prev_total > 0 else 0
    recovery_change = recovery_rate - prev_rate
    
    # ============== DOCTOR & NURSE STATISTICS (Djongo-compatible) ==============
    
    # Get ALL users first (Djongo doesn't support complex filters)
    all_users = list(User.objects.all())
    
    # Filter in Python instead of database
    all_doctors = [u for u in all_users if u.user_type and u.user_type.upper() == 'DOCTOR']
    all_nurses = [u for u in all_users if u.user_type and u.user_type.upper() == 'NURSE']
    
    # Debug: Print counts to console
    print(f"=== DOCTOR & NURSE DEBUG ===")
    print(f"Total users in DB: {len(all_users)}")
    print(f"Total doctors found: {len(all_doctors)}")
    print(f"Total nurses found: {len(all_nurses)}")
    
    # Total counts (including inactive)
    total_doctors = len(all_doctors)
    total_nurses = len(all_nurses)
    
    # Active/Inactive counts for doctors
    active_doctors = len([d for d in all_doctors if d.is_active])
    inactive_doctors = total_doctors - active_doctors
    
    # Active/Inactive counts for nurses
    active_nurses = len([n for n in all_nurses if n.is_active])
    inactive_nurses = total_nurses - active_nurses
    
    print(f"Active doctors: {active_doctors}, Inactive: {inactive_doctors}")
    print(f"Active nurses: {active_nurses}, Inactive: {inactive_nurses}")
    
    # Previous period comparison (based on user creation date)
    prev_doctors = len([
        d for d in all_doctors 
        if d.date_joined and prev_start_datetime <= d.date_joined <= prev_end_datetime
    ])
    prev_nurses = len([
        n for n in all_nurses 
        if n.date_joined and prev_start_datetime <= n.date_joined <= prev_end_datetime
    ])
    
    doctors_change = calculate_percentage_change(prev_doctors, total_doctors)
    nurses_change = calculate_percentage_change(prev_nurses, total_nurses)
    
    print(f"Previous doctors: {prev_doctors}, Change: {doctors_change}%")
    print(f"Previous nurses: {prev_nurses}, Change: {nurses_change}%")
    print(f"==========================")
    
    # ============== DEMOGRAPHICS ==============
    
    # Age groups calculation - with proper error handling
    age_groups = {'0-18': 0, '19-35': 0, '36-50': 0, '51-65': 0, '65+': 0}
    current_year = timezone.now().year
    
    for record in all_patients:
        try:
            # Safely check if patient exists and has date_of_birth
            if hasattr(record, 'patient') and record.patient:
                patient = record.patient
                if patient and hasattr(patient, 'date_of_birth') and patient.date_of_birth:
                    age = current_year - patient.date_of_birth.year
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
        except Exception as e:
            # Skip records with missing patient relationship
            continue
    
    age_groups_list = [{'group': k, 'count': v} for k, v in age_groups.items() if v > 0]
    
    # Cancer types distribution - Use Python aggregation
    cancer_type_counts = {}
    for record in all_patients:
        try:
            if record.created_at and record.created_at <= end_datetime:
                cancer_type_name = record.cancer_type.name if record.cancer_type else 'Unknown'
                cancer_type_counts[cancer_type_name] = cancer_type_counts.get(cancer_type_name, 0) + 1
        except Exception as e:
            continue
    
    cancer_types = [
        {'cancer_type__name': k, 'count': v} 
        for k, v in sorted(cancer_type_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    
    # Cancer stages distribution
    stage_counts = {}
    for record in all_patients:
        try:
            if record.created_at and record.created_at <= end_datetime:
                stage = record.cancer_stage or 'Unknown'
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
        except Exception as e:
            continue
    
    cancer_stages = [
        {'cancer_stage': k, 'count': v} 
        for k, v in stage_counts.items()
    ]
    
    # Hospitals distribution
    hospital_counts = {}
    for record in all_patients:
        try:
            if record.created_at and record.created_at <= end_datetime:
                hospital = record.hospital_name or 'Not specified'
                hospital_counts[hospital] = hospital_counts.get(hospital, 0) + 1
        except Exception as e:
            continue
    
    top_hospitals = [
        {'hospital_name': k, 'count': v} 
        for k, v in sorted(hospital_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    
    # Diagnosis timeline
    year_counts = {}
    for record in all_patients:
        try:
            if record.diagnosis_date:
                year = record.diagnosis_date.year
                year_counts[year] = year_counts.get(year, 0) + 1
        except Exception as e:
            continue
    
    diagnosis_by_year = [{'year': year, 'count': count} for year, count in sorted(year_counts.items())]
    
    demographics = {
        'age_groups': age_groups_list,
        'cancer_types': cancer_types,
        'cancer_stages': cancer_stages,
        'top_hospitals': top_hospitals,
        'diagnosis_timeline': diagnosis_by_year
    }
    
    # ============== TREATMENT OUTCOMES ==============
    
    # By status
    status_counts = {}
    for alert in all_alerts:
        try:
            if alert.created_at and start_datetime <= alert.created_at <= end_datetime:
                status_counts[alert.status] = status_counts.get(alert.status, 0) + 1
        except Exception as e:
            continue
    
    by_status = [{'status': k, 'count': v} for k, v in status_counts.items()]
    
    # By severity
    by_severity = []
    severities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    
    for severity in severities:
        total = len([
            a for a in all_alerts 
            if a.alert_level == severity and a.created_at and 
            start_datetime <= a.created_at <= end_datetime
        ])
        
        resolved = len([
            a for a in all_alerts 
            if a.alert_level == severity and a.status == 'RESOLVED' and a.created_at and 
            start_datetime <= a.created_at <= end_datetime
        ])
        
        by_severity.append({
            'severity': severity,
            'total': total,
            'resolved': resolved,
            'resolution_rate': round((resolved / total * 100) if total > 0 else 0, 1)
        })
    
    # Monthly trend - using Python aggregation
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
        
        total = len([
            a for a in all_alerts 
            if a.created_at and month_start <= a.created_at <= month_end
        ])
        
        resolved = len([
            a for a in all_alerts 
            if a.status == 'RESOLVED' and a.created_at and 
            month_start <= a.created_at <= month_end
        ])
        
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
        'by_status': by_status,
        'by_severity': by_severity,
        'monthly_trend': monthly_trend
    }
    
    # ============== RECENT ALERTS ==============
    
    # Recent Alerts - FIXED: Use description instead of message
    recent_alerts = sorted(
        [a for a in all_alerts if a.created_at and start_datetime <= a.created_at <= end_datetime],
        key=lambda x: x.created_at,
        reverse=True
    )[:5]
    
    # Serialize recent alerts manually
    recent_alerts_data = []
    for alert in recent_alerts:
        # Get message from correct field (description is the correct field name)
        message = getattr(alert, 'description', None) or getattr(alert, 'message', 'No description')
        title = getattr(alert, 'title', 'Alert')
        
        recent_alerts_data.append({
            'alert_id': alert.alert_id,
            'alert_level': alert.alert_level,
            'status': alert.status,
            'title': title,
            'message': message,
            'created_at': alert.created_at,
            'resolved_at': alert.resolved_at
        })
    
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
                },
                'doctors': {
                    'total': total_doctors,
                    'active': active_doctors,
                    'inactive': inactive_doctors,
                    'change': doctors_change,
                    'trend': 'up' if doctors_change > 0 else 'down'
                },
                'nurses': {
                    'total': total_nurses,
                    'active': active_nurses,
                    'inactive': inactive_nurses,
                    'change': nurses_change,
                    'trend': 'up' if nurses_change > 0 else 'down'
                }
            },
            'demographics': demographics,
            'outcomes': outcomes,
            'recent_alerts': recent_alerts_data
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