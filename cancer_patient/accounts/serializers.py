# from rest_framework import serializers
# from .models import User, PatientProfile, NurseProfile, DoctorProfile, AdminProfile

# class UserSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = User
#         fields = ['user_id', 'username', 'email', 'phone_number', 'user_type', 'is_verified', 'created_at']
#         read_only_fields = ['user_id', 'created_at']

# class PatientProfileSerializer(serializers.ModelSerializer):
#     user = UserSerializer(read_only=True)
    
#     class Meta:
#         model = PatientProfile
#         fields = '__all__'

# class NurseProfileSerializer(serializers.ModelSerializer):
#     user = UserSerializer(read_only=True)
    
#     class Meta:
#         model = NurseProfile
#         fields = '__all__'

# class DoctorProfileSerializer(serializers.ModelSerializer):
#     user = UserSerializer(read_only=True)
    
#     class Meta:
#         model = DoctorProfile
#         fields = '__all__'

# class AdminProfileSerializer(serializers.ModelSerializer):
#     user = UserSerializer(read_only=True)
    
#     class Meta:
#         model = AdminProfile
#         fields = '__all__'

# class RegisterSerializer(serializers.Serializer):
#     username = serializers.CharField()
#     password = serializers.CharField(write_only=True)
#     email = serializers.EmailField()
#     phone_number = serializers.CharField()
#     first_name = serializers.CharField()
#     last_name = serializers.CharField()
#     aadhar_number = serializers.CharField()
#     date_of_birth = serializers.DateField(required=False)
#     gender = serializers.ChoiceField(choices=['MALE', 'FEMALE', 'OTHER'], required=False)
#     address = serializers.CharField(required=False)
#     emergency_contact_name = serializers.CharField(required=False)
#     emergency_contact_phone = serializers.CharField(required=False)

# class LoginSerializer(serializers.Serializer):
#     username = serializers.CharField()
#     password = serializers.CharField()

from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, PatientProfile, NurseProfile, DoctorProfile, AdminProfile
import re

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['user_id', 'username', 'email', 'phone_number', 'user_type', 'is_verified', 'created_at']
        read_only_fields = ['user_id', 'created_at']

class PatientProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = PatientProfile
        fields = '__all__'
        extra_kwargs = {
            'aadhar_number': {'required': True}  
        }
class NurseProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = NurseProfile
        fields = '__all__'

class DoctorProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = DoctorProfile
        fields = '__all__'

class AdminProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = AdminProfile
        fields = '__all__'

class RegisterSerializer(serializers.Serializer):
    # Common fields for all users
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=6)
    email = serializers.EmailField()
    phone_number = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    user_type = serializers.ChoiceField(choices=['PATIENT', 'NURSE', 'DOCTOR', 'ADMIN'])
    
    # Patient specific fields
    aadhar_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=['MALE', 'FEMALE', 'OTHER'], required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_name = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_phone = serializers.CharField(required=False, allow_blank=True)
    
    # Nurse specific fields
    employee_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    qualification = serializers.CharField(required=False, allow_blank=True)
    department = serializers.CharField(required=False, allow_blank=True)
    
    # Doctor specific fields - ADD employee_id HERE
    employee_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)  # 🔴 ADD THIS
    specialization = serializers.CharField(required=False, allow_blank=True)
    license_number = serializers.CharField(required=False, allow_blank=True)
    joining_date = serializers.DateField(required=False, allow_null=True)
    
    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already taken")
        return value
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value
    
    def validate_phone_number(self, value):
        # Simple phone number validation
        if not re.match(r'^[0-9]{10}$', value):
            raise serializers.ValidationError("Invalid phone number format")
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("Phone number already registered")
        return value
    
    def validate_aadhar_number(self, value):
        if value and PatientProfile.objects.filter(aadhar_number=value).exists():
            raise serializers.ValidationError("Aadhar number already registered")
        return value
    
    def validate_employee_id(self, value):
        """Validate employee_id for doctors"""
        # If employee_id is provided, check if it's unique
        if value and DoctorProfile.objects.filter(employee_id=value).exists():
            raise serializers.ValidationError("Employee ID already registered")
        return value

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

class TokenResponseSerializer(serializers.Serializer):
    """Serializer for token response"""
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=6)

class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)