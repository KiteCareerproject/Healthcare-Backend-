# from rest_framework import status
# from rest_framework.decorators import api_view, permission_classes
# from rest_framework.permissions import AllowAny, IsAuthenticated
# from rest_framework.response import Response
# from django.contrib.auth import authenticate
# from .models import User, PatientProfile, NurseProfile, DoctorProfile, AdminProfile
# from .serializers import UserSerializer, PatientProfileSerializer, RegisterSerializer, LoginSerializer
# from .utils import handle_errors, APIError
# import logging

# logger = logging.getLogger(__name__)

# @api_view(['POST'])
# @permission_classes([AllowAny])
# @handle_errors
# def register(request):
#     """Register a new patient"""
#     serializer = RegisterSerializer(data=request.data)
    
#     if not serializer.is_valid():
#         raise APIError("Validation error", errors=serializer.errors)
    
#     data = serializer.validated_data
    
#     # Check if user exists
#     if User.objects.filter(username=data['username']).exists():
#         raise APIError("Username already taken")
    
#     if User.objects.filter(email=data['email']).exists():
#         raise APIError("Email already registered")
    
#     if User.objects.filter(phone_number=data['phone_number']).exists():
#         raise APIError("Phone number already registered")
    
#     # Create user
#     user = User.objects.create_user(
#         username=data['username'],
#         password=data['password'],
#         email=data['email'],
#         phone_number=data['phone_number'],
#         user_type='PATIENT'
#     )
    
#     # Create patient profile
#     patient = PatientProfile.objects.create(
#         user=user,
#         first_name=data['first_name'],
#         last_name=data['last_name'],
#         aadhar_number=data['aadhar_number'],
#         date_of_birth=data.get('date_of_birth'),
#         gender=data.get('gender'),
#         address=data.get('address'),
#         emergency_contact_name=data.get('emergency_contact_name'),
#         emergency_contact_phone=data.get('emergency_contact_phone')
#     )
    
#     token = user.generate_token()
    
#     logger.info(f"New patient registered: {user.username}")
    
#     return Response({
#         'success': True,
#         'message': 'Registration successful',
#         'data': {
#             'user_id': user.user_id,
#             'patient_id': patient.patient_id,
#             'token': token
#         }
#     }, status=status.HTTP_201_CREATED)

# @api_view(['POST'])
# @permission_classes([AllowAny])
# @handle_errors
# def login(request):
#     """User login"""
#     serializer = LoginSerializer(data=request.data)
    
#     if not serializer.is_valid():
#         raise APIError("Validation error", errors=serializer.errors)
    
#     data = serializer.validated_data
    
#     user = authenticate(username=data['username'], password=data['password'])
    
#     if not user:
#         raise APIError("Invalid credentials", status_code=status.HTTP_401_UNAUTHORIZED)
    
#     if not user.is_active:
#         raise APIError("Account is disabled", status_code=status.HTTP_403_FORBIDDEN)
    
#     token = user.generate_token()
    
#     # Get profile based on user type
#     profile_data = {}
#     if user.user_type == 'PATIENT':
#         try:
#             profile = PatientProfile.objects.get(user=user)
#             profile_data = {
#                 'patient_id': profile.patient_id,
#                 'name': f"{profile.first_name} {profile.last_name}"
#             }
#         except PatientProfile.DoesNotExist:
#             pass
#     elif user.user_type == 'NURSE':
#         profile = NurseProfile.objects.get(user=user)
#         profile_data = {
#             'nurse_id': profile.nurse_id,
#             'name': f"{profile.first_name} {profile.last_name}"
#         }
#     elif user.user_type == 'DOCTOR':
#         profile = DoctorProfile.objects.get(user=user)
#         profile_data = {
#             'doctor_id': profile.doctor_id,
#             'name': f"Dr. {profile.first_name} {profile.last_name}"
#         }
#     elif user.user_type == 'ADMIN':
#         profile = AdminProfile.objects.get(user=user)
#         profile_data = {
#             'admin_id': profile.admin_id,
#             'name': f"{profile.first_name} {profile.last_name}"
#         }
    
#     logger.info(f"User logged in: {user.username}")
    
#     return Response({
#         'success': True,
#         'message': 'Login successful',
#         'data': {
#             'user_id': user.user_id,
#             'username': user.username,
#             'user_type': user.user_type,
#             'token': token,
#             'profile': profile_data
#         }
#     })

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def get_profile(request):
#     """Get user profile"""
#     user = request.user
    
#     if user.user_type == 'PATIENT':
#         profile = PatientProfile.objects.get(user=user)
#         serializer = PatientProfileSerializer(profile)
#     elif user.user_type == 'NURSE':
#         profile = NurseProfile.objects.get(user=user)
#         serializer = NurseProfileSerializer(profile)
#     elif user.user_type == 'DOCTOR':
#         profile = DoctorProfile.objects.get(user=user)
#         serializer = DoctorProfileSerializer(profile)
#     elif user.user_type == 'ADMIN':
#         profile = AdminProfile.objects.get(user=user)
#         serializer = AdminProfileSerializer(profile)
#     else:
#         serializer = UserSerializer(user)
    
#     return Response({
#         'success': True,
#         'data': serializer.data
#     })

# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def logout(request):
#     """Logout user"""
#     logger.info(f"User logged out: {request.user.username}")
#     return Response({
#         'success': True,
#         'message': 'Logout successful'
#     })


from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User, PatientProfile, NurseProfile, DoctorProfile, AdminProfile
from .serializers import (
    UserSerializer, PatientProfileSerializer, NurseProfileSerializer,
    DoctorProfileSerializer, AdminProfileSerializer,
    RegisterSerializer, LoginSerializer
)
from .utils import handle_errors, APIError
import logging

logger = logging.getLogger(__name__)

def get_tokens_for_user(user):
    """Generate tokens for user"""
    refresh = RefreshToken.for_user(user)
    
    # Add custom claims
    refresh['user_type'] = user.user_type
    refresh['username'] = user.username
    
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh)
    }

def get_profile_data(user):
    """Get profile data based on user type"""
    profile_data = {
        'user_id': user.user_id,
        'username': user.username,
        'email': user.email,
        'phone_number': user.phone_number,
        'user_type': user.user_type
    }
    
    try:
        if user.user_type == 'PATIENT':
            profile = PatientProfile.objects.get(user=user)
            profile_data.update({
                'patient_id': profile.patient_id,
                'first_name': profile.first_name,
                'last_name': profile.last_name,
                'name': f"{profile.first_name} {profile.last_name}",
                'aadhar_number': profile.aadhar_number,
                'date_of_birth': profile.date_of_birth,
                'gender': profile.gender,
                'address': profile.address
            })
        elif user.user_type == 'NURSE':
            profile = NurseProfile.objects.get(user=user)
            profile_data.update({
                'nurse_id': profile.nurse_id,
                'first_name': profile.first_name,
                'last_name': profile.last_name,
                'name': f"{profile.first_name} {profile.last_name}",
                'qualification': profile.qualification,
                'experience_years': profile.experience_years,
                'department': profile.department
            })
        elif user.user_type == 'DOCTOR':
            profile = DoctorProfile.objects.get(user=user)
            profile_data.update({
                'doctor_id': profile.doctor_id,
                'first_name': profile.first_name,
                'last_name': profile.last_name,
                'name': f"Dr. {profile.first_name} {profile.last_name}",
                'specialization': profile.specialization,
                'license_number': profile.license_number,
                'consultation_fee': profile.consultation_fee,
                'available_days': profile.available_days
            })
        elif user.user_type == 'ADMIN':
            profile = AdminProfile.objects.get(user=user)
            profile_data.update({
                'admin_id': profile.admin_id,
                'first_name': profile.first_name,
                'last_name': profile.last_name,
                'name': f"{profile.first_name} {profile.last_name}"
            })
    except Exception as e:
        logger.error(f"Error fetching profile: {str(e)}")
    
    return profile_data

# @api_view(['POST'])
# @permission_classes([AllowAny])
# @handle_errors
# def register(request):
#     """Register a new user (patient, nurse, doctor, admin)"""
#     serializer = RegisterSerializer(data=request.data)
    
#     if not serializer.is_valid():
#         raise APIError("Validation error", errors=serializer.errors)
    
#     data = serializer.validated_data
#     user_type = data.get('user_type', 'PATIENT')
    
#     # Check if only admin can create admin accounts
#     if user_type == 'ADMIN':
#         # You can add admin secret check here
#         admin_secret = request.headers.get('X-Admin-Secret')
#         if admin_secret != 'your-admin-secret-key':  # Change this
#             raise APIError("Only admins can create admin accounts")
    
#     # Create user
#     user = User.objects.create_user(
#         username=data['username'],
#         password=data['password'],
#         email=data['email'],
#         phone_number=data['phone_number'],
#         user_type=user_type
#     )
    
#     # Create profile based on user type
#     if user_type == 'PATIENT':
#         patient = PatientProfile.objects.create(
#             user=user,
#             first_name=data.get('first_name', ''),
#             last_name=data.get('last_name', ''),
#             aadhar_number=data.get('aadhar_number'),
#             date_of_birth=data.get('date_of_birth'),
#             gender=data.get('gender'),
#             address=data.get('address'),
#             emergency_contact_name=data.get('emergency_contact_name'),
#             emergency_contact_phone=data.get('emergency_contact_phone')
#         )
#         profile_id = patient.patient_id
        
#     elif user_type == 'NURSE':
#         nurse = NurseProfile.objects.create(
#             user=user,
#             first_name=data.get('first_name', ''),
#             last_name=data.get('last_name', ''),
#             qualification=data.get('qualification'),
#             # experience_years=data.get('experience_years'),
#             department=data.get('department')
#         )
#         profile_id = nurse.nurse_id
        
#     elif user_type == 'DOCTOR':
#         doctor = DoctorProfile.objects.create(
#             user=user,
#             first_name=data.get('first_name', ''),
#             last_name=data.get('last_name', ''),
#             specialization=data.get('specialization'),
#             license_number=data.get('license_number'),
#             # consultation_fee=data.get('consultation_fee'),
#             # available_days=data.get('available_days', [])
#         )
#         profile_id = doctor.doctor_id
        
#     elif user_type == 'ADMIN':
#         admin = AdminProfile.objects.create(
#             user=user,
#             first_name=data.get('first_name', ''),
#             last_name=data.get('last_name', '')
#         )
#         profile_id = admin.admin_id
    
#     # Generate tokens
#     tokens = get_tokens_for_user(user)
    
#     logger.info(f"New {user_type} registered: {user.username}")
    
#     return Response({
#         'success': True,
#         'message': f'{user_type} registration successful',
#         'data': {
#             'user': get_profile_data(user),
#             'tokens': tokens
#         }
#     }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([AllowAny])
@handle_errors
def register(request):
    """Register a new user (patient, nurse, doctor, admin)"""
    serializer = RegisterSerializer(data=request.data)
    
    if not serializer.is_valid():
        raise APIError("Validation error", errors=serializer.errors)
    
    data = serializer.validated_data
    user_type = data.get('user_type', 'PATIENT')
    
    # Check if only admin can create admin accounts
    if user_type == 'ADMIN':
        admin_secret = request.headers.get('X-Admin-Secret')
        if admin_secret != 'your-admin-secret-key':
            raise APIError("Only admins can create admin accounts")
    
    # Create user
    user = User.objects.create_user(
        username=data['username'],
        password=data['password'],
        email=data['email'],
        phone_number=data['phone_number'],
        user_type=user_type
    )
    
    # Create profile based on user type
    if user_type == 'PATIENT':
        # Convert empty strings to None for unique fields
        aadhar_number = data.get('aadhar_number')
        if aadhar_number == '':
            aadhar_number = None
            
        patient = PatientProfile.objects.create(
            user=user,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            aadhar_number=aadhar_number,
            date_of_birth=data.get('date_of_birth'),
            gender=data.get('gender'),
            address=data.get('address'),
            emergency_contact_name=data.get('emergency_contact_name'),
            emergency_contact_phone=data.get('emergency_contact_phone')
        )
        profile_id = patient.patient_id
        
    elif user_type == 'NURSE':
        import uuid
        
        # 🔴 FIX: Handle employee_id for nurse
        employee_id = data.get('employee_id')
        if not employee_id or employee_id == '':
            employee_id = f"NUR{str(uuid.uuid4())[:8].upper()}"
            print(f"Generated nurse employee_id: {employee_id}")
        
        # Handle other fields
        department = data.get('department')
        if department == '':
            department = None
            
        qualification = data.get('qualification')
        if qualification == '':
            qualification = None
        
        nurse = NurseProfile.objects.create(
            user=user,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            employee_id=employee_id,  # Add this field!
            department=department,
            qualification=qualification,
            joining_date=data.get('joining_date')
        )
        profile_id = nurse.nurse_id
        
    elif user_type == 'DOCTOR':
        # Handle employee_id
        employee_id = data.get('employee_id')
        if not employee_id or employee_id == '':
            import uuid
            employee_id = f"DOC{str(uuid.uuid4())[:8].upper()}"
            print(f"Generated employee_id: {employee_id}")
        
        #  FIX: Handle license_number properly
        license_number = data.get('license_number')
        
        # Option 1: If license_number is required, validate it
        if not license_number or license_number == '':
            # Generate a unique license number if not provided
            import uuid
            license_number = f"LIC{str(uuid.uuid4())[:8].upper()}"
            print(f"Generated license_number: {license_number}")
        
        # Handle other fields
        specialization = data.get('specialization')
        if specialization == '':
            specialization = None
            
        joining_date = data.get('joining_date')
        
        doctor = DoctorProfile.objects.create(
            user=user,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            employee_id=employee_id,
            specialization=specialization,
            license_number=license_number,  # Now has a unique value
            joining_date=joining_date,
            department=data.get('department', ''),
            qualification=data.get('qualification', '')
        )
        profile_id = doctor.doctor_id
        
    elif user_type == 'ADMIN':
        admin = AdminProfile.objects.create(
            user=user,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', '')
        )
        profile_id = admin.admin_id
    
    # Generate tokens
    tokens = get_tokens_for_user(user)
    
    logger.info(f"New {user_type} registered: {user.username}")
    
    return Response({
        'success': True,
        'message': f'{user_type} registration successful',
        'data': {
            'user': get_profile_data(user),
            'tokens': tokens
        }
    }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([AllowAny])
@handle_errors
def login(request):
    """User login with token generation"""
    serializer = LoginSerializer(data=request.data)
    
    if not serializer.is_valid():
        raise APIError("Validation error", errors=serializer.errors)
    
    data = serializer.validated_data
    
    user = authenticate(username=data['username'], password=data['password'])
    
    if not user:
        raise APIError("Invalid credentials", status_code=status.HTTP_401_UNAUTHORIZED)
    
    if not user.is_active:
        raise APIError("Account is disabled", status_code=status.HTTP_403_FORBIDDEN)
    
    # Generate tokens
    tokens = get_tokens_for_user(user)
    
    # Get profile data
    profile_data = get_profile_data(user)
    
    logger.info(f"User logged in: {user.username}")
    
    return Response({
        'success': True,
        'message': 'Login successful',
        'data': {
            'user': profile_data,
            'tokens': tokens
        }
    })

@api_view(['POST'])
@permission_classes([AllowAny])
@handle_errors
def refresh_token(request):
    """Refresh access token using refresh token"""
    refresh_token = request.data.get('refresh')
    
    if not refresh_token:
        raise APIError("Refresh token required", status_code=status.HTTP_400_BAD_REQUEST)
    
    try:
        refresh = RefreshToken(refresh_token)
        access_token = str(refresh.access_token)
        
        # Get user data
        user_id = refresh.get('user_id')
        user = User.objects.get(user_id=user_id)
        
        return Response({
            'success': True,
            'data': {
                'access': access_token,
                'user': get_profile_data(user)
            }
        })
        
    except Exception as e:
        raise APIError("Invalid or expired refresh token", 
                      status_code=status.HTTP_401_UNAUTHORIZED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_profile(request):
    """Get user profile"""
    user = request.user
    profile_data = get_profile_data(user)
    
    return Response({
        'success': True,
        'data': profile_data
    })

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@handle_errors
def update_profile(request):
    """Update user profile"""
    user = request.user
    data = request.data
    
    try:
        if user.user_type == 'PATIENT':
            profile = PatientProfile.objects.get(user=user)
            fields = ['first_name', 'last_name', 'address', 'emergency_contact_name', 'emergency_contact_phone']
            for field in fields:
                if field in data:
                    setattr(profile, field, data[field])
            profile.save()
            
        elif user.user_type == 'NURSE':
            profile = NurseProfile.objects.get(user=user)
            fields = ['first_name', 'last_name', 'qualification', 'experience_years', 'department']
            for field in fields:
                if field in data:
                    setattr(profile, field, data[field])
            profile.save()
            
        elif user.user_type == 'DOCTOR':
            profile = DoctorProfile.objects.get(user=user)
            fields = ['first_name', 'last_name', 'specialization', 'consultation_fee', 'available_days']
            for field in fields:
                if field in data:
                    setattr(profile, field, data[field])
            profile.save()
            
        elif user.user_type == 'ADMIN':
            profile = AdminProfile.objects.get(user=user)
            fields = ['first_name', 'last_name']
            for field in fields:
                if field in data:
                    setattr(profile, field, data[field])
            profile.save()
        
        # Update user fields if provided
        user_fields = ['email', 'phone_number']
        for field in user_fields:
            if field in data:
                setattr(user, field, data[field])
        user.save()
        
        logger.info(f"Profile updated for user: {user.username}")
        
        return Response({
            'success': True,
            'message': 'Profile updated successfully',
            'data': get_profile_data(user)
        })
        
    except Exception as e:
        raise APIError(f"Error updating profile: {str(e)}")

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def change_password(request):
    """Change user password"""
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    
    if not old_password or not new_password:
        raise APIError("Old password and new password are required")
    
    if not user.check_password(old_password):
        raise APIError("Old password is incorrect", status_code=status.HTTP_400_BAD_REQUEST)
    
    if len(new_password) < 6:
        raise APIError("New password must be at least 6 characters long")
    
    user.set_password(new_password)
    user.save()
    
    # Generate new tokens
    tokens = get_tokens_for_user(user)
    
    logger.info(f"Password changed for user: {user.username}")
    
    return Response({
        'success': True,
        'message': 'Password changed successfully',
        'data': {
            'tokens': tokens
        }
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def logout(request):
    """Logout user (blacklist refresh token)"""
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
            
        logger.info(f"User logged out: {request.user.username}")
        
    except Exception as e:
        # Even if token blacklist fails, we consider logout successful
        pass
    
    return Response({
        'success': True,
        'message': 'Logout successful'
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_users_by_type(request, user_type):
    """Get all users of a specific type (admin only)"""
    if request.user.user_type != 'ADMIN':
        raise APIError("Only admins can access this", status_code=status.HTTP_403_FORBIDDEN)
    
    valid_types = ['PATIENT', 'NURSE', 'DOCTOR', 'ADMIN']
    if user_type not in valid_types:
        raise APIError(f"Invalid user type. Choose from: {valid_types}")
    
    users = User.objects.filter(user_type=user_type, is_active=True)
    
    profiles = []
    for user in users:
        profiles.append(get_profile_data(user))
    
    return Response({
        'success': True,
        'data': profiles
    })