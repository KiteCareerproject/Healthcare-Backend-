from rest_framework import serializers
from .models import PatientAssignment, DashboardPreference, AnalyticsReport
from accounts.serializers import NurseProfileSerializer, DoctorProfileSerializer, AdminProfileSerializer
from patients.serializers import PatientMedicalRecordSerializer

from accounts.models import User, NurseProfile, DoctorProfile, AdminProfile, PatientProfile
from patients.models import PatientMedicalRecord
from django.contrib.auth.hashers import make_password
from django.db import transaction

class UserSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    phone_number = serializers.CharField(read_only=True, allow_blank=True)
    date_of_birth = serializers.DateField(read_only=True, allow_null=True)
    address = serializers.CharField(read_only=True, allow_blank=True)
    user_type = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 
                 'date_of_birth', 'address', 'user_type', 'is_active']
        read_only_fields = ['id', 'user_type']

# ==================== NURSE SERIALIZERS ====================

class NurseSerializer(serializers.ModelSerializer):
    email = serializers.CharField(source='user.email', read_only=True)
    full_name = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)

    class Meta:
        model = NurseProfile
        fields = [
            'nurse_id',
            'user',
            'full_name',
            'first_name',
            'last_name',
            'email',
            'employee_id',
            'department',
            'qualification',
            'joining_date',
            'created_at',
            'updated_at',
            'is_active'
        ]
        read_only_fields = ['nurse_id', 'created_at', 'updated_at']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

from rest_framework import serializers
from accounts.models import User, NurseProfile
from django.db import transaction
import uuid
from datetime import datetime

class NurseCreateSerializer(serializers.ModelSerializer):
    # User-related fields
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    
    # Optional fields
    phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(write_only=True, required=False, allow_null=True)
    address = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    # Employee ID - make it optional
    employee_id = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    
    class Meta:
        model = NurseProfile
        fields = [
            # Don't include 'user' field here - remove it completely
            'email', 'password', 'first_name', 'last_name',
            'phone_number', 'date_of_birth', 'address',
            'employee_id',  
            'department',
            'qualification',
            'joining_date',  
        ]
        extra_kwargs = {
            # Remove 'user' from extra_kwargs
            'employee_id': {'required': False},
            'department': {'required': True},
            'qualification': {'required': True},
            'joining_date': {'required': True},
        }
    
    def generate_employee_id(self):
        """Generate unique employee ID"""
        # Try UUID based
        for _ in range(5):
            new_id = f"NUR{uuid.uuid4().hex[:6].upper()}"
            if not NurseProfile.objects.filter(employee_id=new_id).exists():
                return new_id
        
        # Fallback to timestamp
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        new_id = f"NUR{timestamp}"
        
        # Ensure uniqueness
        if NurseProfile.objects.filter(employee_id=new_id).exists():
            new_id = f"NUR{timestamp}{uuid.uuid4().hex[:4].upper()}"
        
        return new_id
    
    def validate(self, data):
        # CRITICAL: No 'user' field handling needed now
        
        # Handle employee_id
        emp_id = data.get('employee_id')
        
        # Case 1: Empty string -> convert to None
        if emp_id == '':
            emp_id = None
            data['employee_id'] = None
        
        # Case 2: None -> generate new ID
        if emp_id is None:
            emp_id = self.generate_employee_id()
            data['employee_id'] = emp_id
            print(f" Generated employee_id: {emp_id}")
        
        # Case 3: Provided value -> check uniqueness
        else:
            if NurseProfile.objects.filter(employee_id=emp_id).exists():
                raise serializers.ValidationError(
                    {"employee_id": "Employee ID already exists"}
                )
        
        # Password validation
        password = data.get('password')
        if password and len(password) < 8:
            raise serializers.ValidationError(
                {"password": "Password must be at least 8 characters"}
            )
        
        # Email validation
        email = data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                {"email": "User with this email already exists"}
            )
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        # Extract user data
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        first_name = validated_data.pop('first_name', '')
        last_name = validated_data.pop('last_name', '')
        phone_number = validated_data.pop('phone_number', '')
        date_of_birth = validated_data.pop('date_of_birth', None)
        address = validated_data.pop('address', '')
        
        # Get employee_id (now guaranteed to have a value)
        employee_id = validated_data.pop('employee_id')
        
        # Create username from email
        username = email.split('@')[0]
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Update user with additional fields
        if hasattr(user, 'phone_number'):
            user.phone_number = phone_number
        if hasattr(user, 'date_of_birth'):
            user.date_of_birth = date_of_birth
        if hasattr(user, 'address'):
            user.address = address
        if hasattr(user, 'user_type'):
            user.user_type = 'NURSE'
        user.save()
        
        # Create nurse profile
        nurse = NurseProfile.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            employee_id=employee_id,
            department=validated_data.get('department'),
            qualification=validated_data.get('qualification'),
            joining_date=validated_data.get('joining_date')
        )
        
        return nurse

class NurseUpdateSerializer(serializers.ModelSerializer):
    # Don't use source='user.field' - define fields normally
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(read_only=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    
    class Meta:
        model = NurseProfile
        fields = [
            'first_name', 'last_name', 'phone_number', 'email', 
            'date_of_birth', 'address',
            'employee_id', 'department', 'qualification', 'joining_date',
            'is_active'
        ]
        extra_kwargs = {
            'employee_id': {'required': False},
            'department': {'required': False},
            'qualification': {'required': False},
            'joining_date': {'required': False},
        }
    
    @transaction.atomic
    def update(self, instance, validated_data):
        # Update user fields
        user = instance.user
        
        # Map of field names to update on user
        user_field_mapping = {
            'first_name': 'first_name',
            'last_name': 'last_name',
            'phone_number': 'phone_number',
            'date_of_birth': 'date_of_birth',
            'address': 'address',
            'is_active': 'is_active'
        }
        
        # Update user fields
        user_updated = False
        for serializer_field, user_field in user_field_mapping.items():
            if serializer_field in validated_data:
                value = validated_data.pop(serializer_field)
                if value is not None:
                    setattr(user, user_field, value)
                    user_updated = True
        
        if user_updated:
            user.save()
        
        # Update nurse profile with remaining fields
        for attr, value in validated_data.items():
            if value is not None and hasattr(instance, attr):
                setattr(instance, attr, value)
        
        instance.save()
        return instance

# ==================== DOCTOR SERIALIZERS ====================

class DoctorSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    
    class Meta:
        model = DoctorProfile
        fields = [
            'doctor_id', 
            'user', 
            'full_name', 
            'first_name',
            'last_name',
            'license_number', 
            'specialization', 
            'qualification', 
            # 'experience_years', 
            # 'consultation_fee', 
            'is_active', 
            'joining_date'
        ]
        read_only_fields = ['doctor_id', 'joining_date']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

class DoctorCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    date_of_birth = serializers.DateField(write_only=True, required=False, allow_null=True)
    address = serializers.CharField(write_only=True, required=False, allow_blank=True)
    employee_id = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)  # Make optional
    
    class Meta:
        model = DoctorProfile
        fields = [
            'email', 'password', 'first_name', 'last_name', 
            'phone_number', 'date_of_birth', 'address',
            'employee_id',  # Include this
            'license_number', 
            'specialization', 
            'qualification', 
            'joining_date'
        ]
        extra_kwargs = {
            'license_number': {'required': False},
            'specialization': {'required': True},
            'qualification': {'required': True},
            'joining_date': {'required': True},
            'employee_id': {'required': False},  # Not required
        }
    
    def generate_employee_id(self):
        """Generate unique employee ID"""
        # Method 1: UUID based
        for _ in range(5):
            new_id = f"DOC{uuid.uuid4().hex[:8].upper()}"
            if not DoctorProfile.objects.filter(employee_id=new_id).exists():
                return new_id
        
        # Method 2: Timestamp based
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        new_id = f"DOC{timestamp}"
        
        # Ensure uniqueness
        if DoctorProfile.objects.filter(employee_id=new_id).exists():
            new_id = f"DOC{timestamp}{uuid.uuid4().hex[:4].upper()}"
        
        return new_id
    
    def validate(self, data):
        errors = {}
    # Handle employee_id (existing code)
        emp_id = data.get('employee_id')
        if emp_id is None or emp_id == '':
            emp_id = self.generate_employee_id()
            data['employee_id'] = emp_id
            print(f" Generated employee_id: {emp_id}")
        else:
            if DoctorProfile.objects.filter(employee_id=emp_id).exists():
                raise serializers.ValidationError(
                    {"employee_id": "Employee ID already exists"}
                )
            
        license_no = data.get('license_number')
        if not license_no or license_no == '':
            # Don't save as null - generate a placeholder or make it optional
            # Option 1: Generate temporary license number
            import uuid
            data['license_number'] = f"TEMP{uuid.uuid4().hex[:8].upper()}"
            print(f" Generated temporary license: {data['license_number']}")
            
            # Option 2: Set to None but model must allow null
            # data['license_number'] = None  # Only if model allows null
        else:
            if DoctorProfile.objects.filter(license_number=license_no).exists():
                errors['license_number'] = "License number already exists"
            # Password validation
            password = data.get('password')
            if not password or len(password) < 8:
                raise serializers.ValidationError(
                    {"password": "Password must be at least 8 characters"}
                )
        
        # Email validation
        email = data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                {"email": "User with this email already exists"}
            )
        
        # PHONE NUMBER VALIDATION - FIX THIS
        phone = data.get('phone_number')
        if phone:
            # Remove if empty string
            if phone == '':
                data['phone_number'] = None
            else:
                # Check if phone number already exists
                if User.objects.filter(phone_number=phone).exists():
                    raise serializers.ValidationError(
                        {"phone_number": "Phone number already exists"}
                    )
        
        # License validation
        license_no = data.get('license_number')
        if license_no and DoctorProfile.objects.filter(license_number=license_no).exists():
            raise serializers.ValidationError(
                {"license_number": "License number already exists"}
            )
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        # Extract user data
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        first_name = validated_data.pop('first_name', '')
        last_name = validated_data.pop('last_name', '')
        phone_number = validated_data.pop('phone_number', None)
        date_of_birth = validated_data.pop('date_of_birth', None)
        address = validated_data.pop('address', '')
        
        # Get employee_id (will be None if not provided)
        employee_id = validated_data.pop('employee_id')
        
        # Create username from email
        username = email.split('@')[0]
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Update user with additional fields
        if hasattr(user, 'phone_number'):
            user.phone_number = phone_number
        if hasattr(user, 'date_of_birth'):
            user.date_of_birth = date_of_birth
        if hasattr(user, 'address'):
            user.address = address
        if hasattr(user, 'user_type'):
            user.user_type = 'DOCTOR'
        
        user.save()
        
        # Create doctor profile
        doctor = DoctorProfile.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            employee_id=employee_id,  # This will be None if not provided
            license_number=validated_data.get('license_number'),
            specialization=validated_data.get('specialization'),
            qualification=validated_data.get('qualification'),
            joining_date=validated_data.get('joining_date')
        )
        
        return doctor

class DoctorUpdateSerializer(serializers.ModelSerializer):
    # User fields - FIXED: Don't use source='user.field' pattern
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(read_only=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    
    class Meta:
        model = DoctorProfile
        fields = [
            'first_name', 'last_name', 'phone_number', 'email', 
            'date_of_birth', 'address',
            'license_number', 
            'specialization', 
            'qualification', 
            # 'experience_years',  # REMOVED
            # 'consultation_fee', 
            'joining_date',
            'is_active'
        ]
        extra_kwargs = {
            'license_number': {'required': False},
            'specialization': {'required': False},
            'qualification': {'required': False},
            'joining_date': {'required': False},
            # 'consultation_fee': {'required': False},
        }
    
    @transaction.atomic
    def update(self, instance, validated_data):
        # Update user fields
        user = instance.user
        user_updated = False
        
        # Map of fields that belong to User model
        user_fields = ['first_name', 'last_name', 'phone_number', 
                      'date_of_birth', 'address', 'is_active']
        
        for field in user_fields:
            if field in validated_data:
                value = validated_data.pop(field)
                if value is not None:
                    setattr(user, field, value)
                    user_updated = True
        
        if user_updated:
            user.save()
        
        # Update doctor profile fields
        for attr, value in validated_data.items():
            if value is not None and hasattr(instance, attr):
                setattr(instance, attr, value)
        
        instance.save()
        return instance

# ==================== PATIENT SERIALIZERS ====================

class PatientSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)

    class Meta:
        model = PatientProfile
        fields = [
            'patient_id',
            'user',
            'full_name',
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'date_of_birth',
            'age',
            'gender',
            'address',
            'emergency_contact_name',
            'emergency_contact_phone',
            'emergency_contact_relation',
            'aadhar_number',
            'profile_picture',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['patient_id', 'created_at', 'updated_at']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    
    def get_age(self, obj):
        if obj.date_of_birth:
            from datetime import date
            today = date.today()
            dob = obj.date_of_birth
            age = today.year - dob.year
            if (today.month, today.day) < (dob.month, dob.day):
                age -= 1
            return age
        return None

class PatientCreateSerializer(serializers.ModelSerializer):
    # User-related fields
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    
    # Patient profile fields
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    date_of_birth = serializers.DateField(write_only=True, required=False, allow_null=True)
    gender = serializers.ChoiceField(write_only=True, choices=['MALE', 'FEMALE', 'OTHER'])
    address = serializers.CharField(write_only=True, required=False, allow_blank=True)
    emergency_contact_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    emergency_contact_phone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    emergency_contact_relation = serializers.CharField(write_only=True, required=False, allow_blank=True)
    aadhar_number = serializers.CharField(write_only=True)
    profile_picture = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    
    class Meta:
        model = PatientProfile
        fields = [
            'email', 'password', 'phone_number',
            'first_name', 'last_name', 'date_of_birth', 'gender',
            'address', 'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relation', 'aadhar_number', 'profile_picture'
        ]
    
    def validate(self, data):
        # Convert empty strings to None
        if 'phone_number' in data and data['phone_number'] == '':
            data['phone_number'] = None
        
        # Password validation
        if len(data.get('password', '')) < 8:
            raise serializers.ValidationError({"password": "Password must be at least 8 characters"})
        
        # Email validation
        email = data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "User with this email already exists"})
        
        # Phone number validation
        phone = data.get('phone_number')
        if phone and User.objects.filter(phone_number=phone).exists():
            raise serializers.ValidationError({"phone_number": "Phone number already exists"})
        
        # Aadhar number validation
        aadhar = data.get('aadhar_number')
        if aadhar and PatientProfile.objects.filter(aadhar_number=aadhar).exists():
            raise serializers.ValidationError({"aadhar_number": "Aadhar number already exists"})
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        # Extract user data
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        phone_number = validated_data.pop('phone_number', None)
        
        # Extract patient profile data
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        date_of_birth = validated_data.pop('date_of_birth', None)
        gender = validated_data.pop('gender')
        address = validated_data.pop('address', '')
        emergency_contact_name = validated_data.pop('emergency_contact_name', '')
        emergency_contact_phone = validated_data.pop('emergency_contact_phone', '')
        emergency_contact_relation = validated_data.pop('emergency_contact_relation', '')
        aadhar_number = validated_data.pop('aadhar_number')
        profile_picture = validated_data.pop('profile_picture', None)
        
        # Create username from email
        username = email.split('@')[0]
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Update user with additional fields
        if hasattr(user, 'phone_number'):
            user.phone_number = phone_number
        if hasattr(user, 'user_type'):
            user.user_type = 'PATIENT'
        user.save()
        
        # Create patient profile
        patient = PatientProfile.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            gender=gender,
            address=address,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
            emergency_contact_relation=emergency_contact_relation,
            aadhar_number=aadhar_number,
            profile_picture=profile_picture
        )
        
        return patient

class PatientUpdateSerializer(serializers.ModelSerializer):
    # User fields
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(read_only=True)
    is_active = serializers.BooleanField(required=False)
    
    # Patient profile fields
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(required=False, choices=['MALE', 'FEMALE', 'OTHER'])
    address = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_name = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_phone = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_relation = serializers.CharField(required=False, allow_blank=True)
    aadhar_number = serializers.CharField(required=False)
    profile_picture = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    class Meta:
        model = PatientProfile
        fields = [
            'first_name', 'last_name', 'phone_number', 'email', 'is_active',
            'date_of_birth', 'gender', 'address',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relation',
            'aadhar_number', 'profile_picture'
        ]
    
    def validate(self, data):
        # Convert empty phone to None
        if 'phone_number' in data and data['phone_number'] == '':
            data['phone_number'] = None
        
        # Check phone number uniqueness if changed
        phone = data.get('phone_number')
        if phone:
            # Get current user's primary key value
            current_user = self.instance.user
            
            # Dynamically get the primary key field name and value
            pk_name = current_user._meta.pk.name
            pk_value = getattr(current_user, pk_name)
            
            # Check if phone exists excluding current user
            if User.objects.filter(phone_number=phone).exclude(**{pk_name: pk_value}).exists():
                raise serializers.ValidationError({"phone_number": "Phone number already exists"})
        
        # Check aadhar uniqueness if changed
        aadhar = data.get('aadhar_number')
        if aadhar and PatientProfile.objects.filter(aadhar_number=aadhar).exclude(patient_id=self.instance.patient_id).exists():
            raise serializers.ValidationError({"aadhar_number": "Aadhar number already exists"})
        
        return data
    
    @transaction.atomic
    def update(self, instance, validated_data):
        # Update user fields
        user = instance.user
        user_updated = False
        
        user_fields = ['first_name', 'last_name', 'phone_number', 'is_active']
        for field in user_fields:
            if field in validated_data:
                value = validated_data.pop(field)
                if value is not None:
                    setattr(user, field, value)
                    user_updated = True
        
        if user_updated:
            user.save()
        
        # Update patient profile fields
        for attr, value in validated_data.items():
            if value is not None:
                setattr(instance, attr, value)
        
        instance.save()
        return instance

# ==================== ASSIGNMENT SERIALIZERS ====================

class PatientAssignmentSerializer(serializers.ModelSerializer):
    nurse_details = NurseProfileSerializer(source='nurse', read_only=True)
    doctor_details = DoctorProfileSerializer(source='doctor', read_only=True)
    patient_details = PatientMedicalRecordSerializer(source='patient', read_only=True)
    assigned_by_details = AdminProfileSerializer(source='assigned_by', read_only=True)
    
    class Meta:
        model = PatientAssignment
        fields = '__all__'

class SimplePatientAssignmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    nurse_name = serializers.SerializerMethodField()
    assigned_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = PatientAssignment
        fields = [
            'assignment_id', 
            'patient_id', 
            'patient_name',
            'doctor_id',
            'doctor_name',
            'nurse_id',
            'nurse_name',
            'assigned_date', 
            'is_active', 
            'assigned_by_id', 
            'assigned_by_name'
        ]
    
    def get_patient_name(self, obj):
        try:
            if obj.patient:
                return f"{obj.patient.first_name} {obj.patient.last_name}"
        except:
            pass
        return "Unknown Patient"
    
    def get_doctor_name(self, obj):
        try:
            if obj.doctor:
                return f"{obj.doctor.first_name} {obj.doctor.last_name}"
        except:
            pass
        return "Unknown Doctor"
    
    def get_nurse_name(self, obj):
        try:
            if obj.nurse:
                return f"{obj.nurse.first_name} {obj.nurse.last_name}"
        except:
            pass
        return "Unknown Nurse"
    
    def get_assigned_by_name(self, obj):
        try:
            if obj.assigned_by:
                return f"{obj.assigned_by.first_name} {obj.assigned_by.last_name}"
        except:
            pass
        return "Unknown"

class CreateAssignmentSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField(required=True)
    doctor_id = serializers.IntegerField(required=False, allow_null=True)
    nurse_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate(self, data):
        if not data.get('doctor_id') and not data.get('nurse_id'):
            raise serializers.ValidationError("Either doctor_id or nurse_id must be provided")
        return data

# ==================== DASHBOARD SERIALIZERS ====================

class DashboardPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardPreference
        fields = '__all__'

class AnalyticsReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsReport
        fields = '__all__'