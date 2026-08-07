from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, PatientProfile, NurseProfile, DoctorProfile, AdminProfile
import re

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['user_id','username', 'email', 'phone_number', 'user_type', 'is_verified', 'created_at']
        read_only_fields = ['user_id', 'created_at']

class PatientProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = PatientProfile
        fields = '__all__'
        extra_kwargs = {
            'aadhar_number': {'required': True},
            'patient_no': {'read_only': True}  # Auto-generated
        }


class NurseProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = NurseProfile
        fields = '__all__'
        extra_kwargs = {
            'employee_id': {'required': False},  # Auto-generated if not provided
            'aadhar_number': {'required': False},  # Optional
            'salary': {'required': False},
            'bank_account_number': {'required': False},
            'ifsc_code': {'required': False},
            'blood_group': {'required': False},
            'shift': {'required': False},
            'employment_type': {'required': False},
            'assigned_ward': {'required': False},
            'supervisor': {'required': False},
            'skills': {'required': False},
            'documents': {'required': False},
            'profile_picture': {'required': False},
            'uploaded_documents': {'required': False},
        }
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    
    def validate_aadhar_number(self, value):
        """Validate Aadhar number format"""
        if value:
            # Remove any spaces
            value = re.sub(r'\s+', '', value)
            
            # Check if it's 12 digits
            if not re.match(r'^\d{12}$', value):
                raise serializers.ValidationError("Aadhar number must be 12 digits")
            
            # Check for uniqueness (but allow None/blank)
            if NurseProfile.objects.filter(aadhar_number=value).exclude(nurse_id=self.instance.nurse_id if self.instance else None).exists():
                raise serializers.ValidationError("Aadhar number already exists")
        
        return value
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        if value:
            # Remove any spaces or special characters
            value = re.sub(r'[\s\-\(\)\+]', '', value)
            
            # Check if it's 10 digits (Indian number)
            if value.startswith('91'):
                value = value[2:]
            if value.startswith('0'):
                value = value[1:]
            
            if not re.match(r'^\d{10}$', value):
                raise serializers.ValidationError("Phone number must be 10 digits")
        
        return value
    
    def validate_email(self, value):
        """Validate email format"""
        if value:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, value):
                raise serializers.ValidationError("Invalid email format")
        return value
    
    def validate_years_of_experience(self, value):
        """Validate experience years"""
        if value < 0:
            raise serializers.ValidationError("Years of experience cannot be negative")
        if value > 50:
            raise serializers.ValidationError("Years of experience cannot exceed 50")
        return value
    
    def validate_salary(self, value):
        """Validate salary"""
        if value and value < 0:
            raise serializers.ValidationError("Salary cannot be negative")
        return value


class DoctorProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = DoctorProfile
        fields = '__all__'
        extra_kwargs = {
            'employee_id': {'required': False},  # Auto-generated if not provided
            'license_number': {'required': False},  # Auto-generated if not provided
            'aadhar_number': {'required': False},  # Optional
            'consultation_fee': {'required': False},
            'salary': {'required': False},
            'bank_account_number': {'required': False},
            'ifsc_code': {'required': False},
            'blood_group': {'required': False},
            'shift': {'required': False},
            'employment_type': {'required': False},
            'available_days': {'required': False},
            'available_time': {'required': False},
            'assigned_ward': {'required': False},
            'supervisor': {'required': False},
            'skills': {'required': False},
            'years_of_experience': {'required': False},
            'documents': {'required': False},
            'profile_picture': {'required': False},
            'uploaded_documents': {'required': False},
        }
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    
    def get_display_name(self, obj):
        return f"Dr. {obj.first_name} {obj.last_name}"
    
    def validate_aadhar_number(self, value):
        """Validate Aadhar number format"""
        if value:
            # Remove any spaces
            value = re.sub(r'\s+', '', value)
            
            # Check if it's 12 digits
            if not re.match(r'^\d{12}$', value):
                raise serializers.ValidationError("Aadhar number must be 12 digits")
            
            # Check for uniqueness
            if DoctorProfile.objects.filter(aadhar_number=value).exclude(doctor_id=self.instance.doctor_id if self.instance else None).exists():
                raise serializers.ValidationError("Aadhar number already exists")
        
        return value
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        if value:
            # Remove any spaces or special characters
            value = re.sub(r'[\s\-\(\)\+]', '', value)
            
            # Check if it's 10 digits (Indian number)
            if value.startswith('91'):
                value = value[2:]
            if value.startswith('0'):
                value = value[1:]
            
            if not re.match(r'^\d{10}$', value):
                raise serializers.ValidationError("Phone number must be 10 digits")
        
        return value
    
    def validate_email(self, value):
        """Validate email format"""
        if value:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, value):
                raise serializers.ValidationError("Invalid email format")
        return value
    
    def validate_license_number(self, value):
        """Validate license number format"""
        if value and len(value) < 5:
            raise serializers.ValidationError("License number must be at least 5 characters")
        return value
    
    def validate_years_of_experience(self, value):
        """Validate experience years"""
        if value < 0:
            raise serializers.ValidationError("Years of experience cannot be negative")
        if value > 60:
            raise serializers.ValidationError("Years of experience cannot exceed 60")
        return value
    
    def validate_consultation_fee(self, value):
        """Validate consultation fee"""
        if value and value < 0:
            raise serializers.ValidationError("Consultation fee cannot be negative")
        if value and value > 10000:
            raise serializers.ValidationError("Consultation fee cannot exceed 10000")
        return value
    
    def validate_salary(self, value):
        """Validate salary"""
        if value and value < 0:
            raise serializers.ValidationError("Salary cannot be negative")
        return value
    
    def validate_available_days(self, value):
        """Validate available days"""
        valid_days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for day in value:
            if day not in valid_days:
                raise serializers.ValidationError(f"Invalid day: {day}. Valid days are {valid_days}")
        return value


class AdminProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AdminProfile
        fields = '__all__'
        extra_kwargs = {
            'employee_id': {'required': False},  # Auto-generated if not provided
            'role': {'required': False},
        }
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

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
    employee_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)  
    specialization = serializers.CharField(required=False, allow_blank=True)
    license_number = serializers.CharField(required=False, allow_blank=True)
    joining_date = serializers.DateField(required=False, allow_null=True)
    
    def validate(self, data):
        """Check that password and confirm_password match"""
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        
        if password != confirm_password:
            raise serializers.ValidationError({
                'confirm_password': 'Password and Confirm Password do not match'
            })
        
        return data
    
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
            raise serializers.ValidationError("Invalid phone number format. Must be 10 digits")
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("Phone number already registered")
        return value
    
    def validate_aadhar_number(self, value):
        if value and PatientProfile.objects.filter(aadhar_number=value).exists():
            raise serializers.ValidationError("Aadhar number already registered")
        return value
    
    def validate_employee_id(self, value):
        """Validate employee_id for doctors and nurses"""
        if value:
            # Check for doctor
            if DoctorProfile.objects.filter(employee_id=value).exists():
                raise serializers.ValidationError("Employee ID already registered as Doctor")
            # Check for nurse
            if NurseProfile.objects.filter(employee_id=value).exists():
                raise serializers.ValidationError("Employee ID already registered as Nurse")
        return value
    
    # def validate_employee_id(self, value):
    #     """Validate employee_id for doctors"""
    #     # If employee_id is provided, check if it's unique
    #     if value and DoctorProfile.objects.filter(employee_id=value).exists():
    #         raise serializers.ValidationError("Employee ID already registered")
    #     return value

class LoginSerializer(serializers.Serializer):
    # username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField()

class TokenResponseSerializer(serializers.Serializer):
    """Serializer for token response"""
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=6)
    confirm_password = serializers.CharField(required=True)  # Add confirm password
    
    def validate(self, data):
        """Check that new password and confirm password match"""
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'New password and confirm password do not match'
            })
        return data
    
class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)

class ProfileUpdateSerializer(serializers.Serializer):
    """Serializer for updating profile information"""
    
    # Common fields
    first_name = serializers.CharField(max_length=100, required=False)
    last_name = serializers.CharField(max_length=100, required=False)
    phone_number = serializers.CharField(max_length=15, required=False)
    email = serializers.EmailField(required=False)
    address = serializers.CharField(required=False)
    
    # Patient specific
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=['MALE', 'FEMALE', 'OTHER'], required=False)
    emergency_contact_name = serializers.CharField(max_length=200, required=False)
    emergency_contact_phone = serializers.CharField(max_length=15, required=False)
    blood_group = serializers.CharField(max_length=5, required=False)
    
    # Nurse/Doctor specific
    qualification = serializers.CharField(required=False)
    department = serializers.CharField(max_length=100, required=False)
    shift = serializers.CharField(max_length=50, required=False)
    employment_type = serializers.CharField(max_length=50, required=False)
    years_of_experience = serializers.IntegerField(required=False)
    skills = serializers.ListField(child=serializers.CharField(), required=False)
    assigned_ward = serializers.CharField(max_length=100, required=False)
    supervisor = serializers.CharField(max_length=100, required=False)
    
    # Doctor specific
    specialization = serializers.CharField(max_length=200, required=False)
    consultation_fee = serializers.DecimalField(max_digits=8, decimal_places=2, required=False)
    available_days = serializers.ListField(child=serializers.CharField(), required=False)
    
    def validate_phone_number(self, value):
        if value:
            value = re.sub(r'[\s\-\(\)\+]', '', value)
            if value.startswith('91'):
                value = value[2:]
            if value.startswith('0'):
                value = value[1:]
            if not re.match(r'^\d{10}$', value):
                raise serializers.ValidationError("Phone number must be 10 digits")
        return value