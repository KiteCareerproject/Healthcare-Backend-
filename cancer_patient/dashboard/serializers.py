from rest_framework import serializers
from .models import PatientAssignment, DashboardPreference, AnalyticsReport
from accounts.serializers import NurseProfileSerializer, DoctorProfileSerializer, AdminProfileSerializer
from patients.serializers import PatientMedicalRecordSerializer
import uuid
from accounts.models import User, NurseProfile, DoctorProfile, AdminProfile, PatientProfile
from patients.models import PatientMedicalRecord, PatientProfile
from django.contrib.auth.hashers import make_password
from django.db import transaction
from datetime import datetime, timedelta
from django.utils import timezone
from monitoring.models import Alert
from datetime import date
from django.utils import timezone
from decimal import Decimal
from bson.decimal128 import Decimal128

# ==================== USER SERIALIZER ====================
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

# ==================== NURSE SERIALIZERS - ALL FIELDS ====================

class NurseSerializer(serializers.ModelSerializer):
    """Serializer for reading nurse data - ALL FIELDS"""
    
    class Meta:
        model = NurseProfile
        fields = [
            'nurse_id', 'user',
            'full_name', 'first_name', 'last_name', 'phone_number', 'email', 
            'username', 'address', 'date_of_birth', 'aadhar_number', 'gender',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relation',
            'employee_id', 'department', 'qualification', 'joining_date', 
            'shift', 'employment_type', 'years_of_experience', 'is_active',
            'skills', 'assigned_ward', 'supervisor',
            'salary', 'bank_account_number', 'ifsc_code',
            'blood_group',
            'documents', 'profile_picture', 'uploaded_documents',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['nurse_id', 'created_at', 'updated_at']
    
    def to_representation(self, instance):
        """Manually control what data is returned"""
        # Get the user instance
        user = instance.user
        
        # ✅ Safe function to handle any file field
        def safe_file_value(field):
            """Safely get value from file field without causing ValueError"""
            if field is None:
                return None
            try:
                if hasattr(field, 'url'):
                    return field.url
                elif isinstance(field, str):
                    return field
                else:
                    return str(field)
            except (ValueError, AttributeError, TypeError):
                return None
        
        # ✅ Safe function to handle documents (DictField)
        def safe_documents_value(documents):
            """Safely get documents value"""
            if documents is None:
                return {}
            try:
                if isinstance(documents, dict):
                    return documents
                elif isinstance(documents, str):
                    try:
                        import json
                        return json.loads(documents)
                    except:
                        return {}
                else:
                    return {}
            except:
                return {}
        
        # ✅ Safe function to handle skills (ListField)
        def safe_skills_value(skills):
            """Safely get skills value"""
            if skills is None:
                return []
            try:
                if isinstance(skills, list):
                    return skills
                elif isinstance(skills, str):
                    try:
                        import json
                        return json.loads(skills)
                    except:
                        return [s.strip() for s in skills.split(',') if s.strip()]
                else:
                    return []
            except:
                return []
        
        # ✅ Safe function to handle salary (DecimalField)
        def safe_salary_value(salary):
            """Safely get salary value as string"""
            if salary is None:
                return None
            try:
                if hasattr(salary, 'to_decimal'):
                    return str(salary.to_decimal())
                elif hasattr(salary, '__str__'):
                    return str(salary)
                else:
                    return str(salary)
            except:
                return None
        
        # Get safe values for all file fields
        profile_picture = safe_file_value(instance.profile_picture)
        uploaded_documents = safe_file_value(instance.uploaded_documents)
        documents = safe_documents_value(instance.documents)
        skills = safe_skills_value(instance.skills)
        salary = safe_salary_value(instance.salary)
        
        # Return the data as a dictionary
        return {
            # Primary Keys
            'nurse_id': instance.nurse_id,
            'user': instance.user_id,
            
            # Personal Information (from User model)
            'full_name': f"{user.first_name} {user.last_name}".strip(),
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': user.phone_number or "",
            'email': user.email or "",
            'username': user.username,
            
            # ✅ FIXED: is_active from NurseProfile (NOT User)
            'is_active': getattr(instance, 'is_active', True),
            
            # From NurseProfile
            'address': instance.address if instance.address else "",
            'date_of_birth': instance.date_of_birth if instance.date_of_birth else None,
            'aadhar_number': instance.aadhar_number,
            'gender': instance.gender,
            
            # Emergency Contact
            'emergency_contact_name': instance.emergency_contact_name,
            'emergency_contact_phone': instance.emergency_contact_phone,
            'emergency_contact_relation': instance.emergency_contact_relation,
            
            # Employment Information
            'employee_id': instance.employee_id,
            'department': instance.department,
            'qualification': instance.qualification,
            'joining_date': instance.joining_date,
            'shift': instance.shift,
            'employment_type': instance.employment_type,
            'years_of_experience': instance.years_of_experience,
            
            # Skills & Ward Assignment
            'skills': skills,
            'assigned_ward': instance.assigned_ward,
            'supervisor': instance.supervisor,
            
            # Financial Information
            'salary': salary,
            'bank_account_number': instance.bank_account_number,
            'ifsc_code': instance.ifsc_code,
            
            # Additional Fields
            'blood_group': instance.blood_group,
            
            # Documents - Safe handling
            'documents': documents,
            'profile_picture': profile_picture,
            'uploaded_documents': uploaded_documents,
            
            # Timestamps
            'created_at': instance.created_at,
            'updated_at': instance.updated_at,
        }

# accounts/serializers.py

# accounts/serializers.py

import base64
from django.core.files.base import ContentFile

class NurseCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating nurse - ALL FIELDS"""
    
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, style={'input_type': 'password'}, required=False)
    username = serializers.CharField(write_only=True, required=False)
    
    # ✅ Accept base64 string
    profile_picture = serializers.CharField(
        required=False, 
        allow_null=True, 
        allow_blank=True,
        write_only=True
    )
    uploaded_documents = serializers.CharField(
        required=False, 
        allow_null=True, 
        allow_blank=True,
        write_only=True
    )
    
    class Meta:
        model = NurseProfile
        fields = '__all__'
        read_only_fields = ['user', 'nurse_id', 'created_at', 'updated_at']
        extra_kwargs = {
            'employee_id': {'required': False},
            'department': {'required': True},
            'qualification': {'required': True},
            'joining_date': {'required': False},
            'years_of_experience': {'required': False, 'default': 0},
            'skills': {'required': False, 'default': list},
            'salary': {'required': False, 'allow_null': True},
            'profile_picture': {'required': False, 'allow_null': True, 'allow_blank': True},
            'uploaded_documents': {'required': False, 'allow_null': True, 'allow_blank': True},
            'user': {'required': False},
        }
    
    def validate_profile_picture(self, value):
        """Validate and convert base64 to URL or store as base64"""
        if value is None or value == '' or value == 'null':
            return None
        
        # ✅ If it's already a valid base64 string, return as is
        if isinstance(value, str) and (value.startswith('data:image') or value.startswith('data:application')):
            return value
        
        # ✅ If it's a URL, return as is
        if isinstance(value, str) and value.startswith('http'):
            return value
        
        return value
    
    def validate_uploaded_documents(self, value):
        """Validate uploaded documents"""
        if value is None or value == '' or value == 'null':
            return None
        return value
    
    def validate(self, data):
        # Handle profile_picture
        if data.get('profile_picture') in [None, '', 'null']:
            data.pop('profile_picture', None)
        
        if data.get('uploaded_documents') in [None, '', 'null']:
            data.pop('uploaded_documents', None)
        
        data.pop('user', None)
        
        # Set default joining_date
        if 'joining_date' not in data or not data['joining_date']:
            from datetime import date
            data['joining_date'] = date.today()
        
        # Password validation
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        
        if password:
            if password != confirm_password:
                raise serializers.ValidationError({'confirm_password': 'Passwords do not match'})
            if len(password) < 8:
                raise serializers.ValidationError({'password': 'Password must be at least 8 characters'})
        
        # Employee ID
        emp_id = data.get('employee_id')
        if not emp_id:
            data['employee_id'] = self.generate_employee_id()
        
        # Aadhar uniqueness
        aadhar = data.get('aadhar_number')
        if aadhar and NurseProfile.objects.filter(aadhar_number=aadhar).exists():
            raise serializers.ValidationError({'aadhar_number': 'Aadhar number already exists'})
        
        # Email uniqueness
        email = data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'email': 'Email already exists'})
        
        return data
    
    def generate_employee_id(self):
        import uuid
        return f"NUR{uuid.uuid4().hex[:8].upper()}"
    
    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('confirm_password', None)
        
        # ✅ Get profile_picture and uploaded_documents before popping
        profile_picture = validated_data.pop('profile_picture', None)
        uploaded_documents = validated_data.pop('uploaded_documents', None)
        
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        username = validated_data.pop('username', None)
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        phone_number = validated_data.pop('phone_number', '')
        
        if not username:
            username = email.split('@')[0]
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            user_type='NURSE'
        )
        
        # ✅ Create nurse with base64 strings directly
        nurse = NurseProfile.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            email=user.email,                    
            phone_number=user.phone_number, 
            profile_picture=profile_picture,  # Store base64 string
            uploaded_documents=uploaded_documents,  # Store base64 string
            **validated_data
        )
        
        return nurse


class NurseUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating nurse - ALL FIELDS"""
    
    # ✅ FIX: Make email writable (remove read_only=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    username = serializers.CharField(read_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    
    class Meta:
        model = NurseProfile
        fields = [
            # User fields - ✅ email is now writable
            'email', 'username', 'first_name', 'last_name', 'phone_number',
            'date_of_birth', 'address', 'is_active',
            
            # Personal Information
            'aadhar_number', 'gender',
            
            # Emergency Contact
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relation',
            
            # Employment Information
            'employee_id', 'department', 'qualification', 'joining_date',
            'shift', 'employment_type', 'years_of_experience',
            
            # Skills & Ward Assignment
            'skills', 'assigned_ward', 'supervisor',
            
            # Financial Information
            'salary', 'bank_account_number', 'ifsc_code',
            
            # Additional Fields
            'blood_group',
            
            # Documents
            'documents', 'profile_picture', 'uploaded_documents'
        ]
        extra_kwargs = {
            'employee_id': {'required': False, 'allow_blank': True},
            'department': {'required': False, 'allow_blank': True},
            'qualification': {'required': False, 'allow_blank': True},
            'joining_date': {'required': False, 'allow_null': True},
            'shift': {'required': False, 'allow_blank': True},
            'employment_type': {'required': False, 'allow_blank': True},
            'years_of_experience': {'required': False},
            'skills': {'required': False},
            'assigned_ward': {'required': False, 'allow_blank': True},
            'supervisor': {'required': False, 'allow_blank': True},
            'salary': {'required': False, 'allow_null': True},
            'bank_account_number': {'required': False, 'allow_blank': True},
            'ifsc_code': {'required': False, 'allow_blank': True},
            'aadhar_number': {'required': False, 'allow_blank': True},
            'gender': {'required': False, 'allow_blank': True},
            'emergency_contact_name': {'required': False, 'allow_blank': True},
            'emergency_contact_phone': {'required': False, 'allow_blank': True},
            'emergency_contact_relation': {'required': False, 'allow_blank': True},
            'blood_group': {'required': False, 'allow_blank': True},
            'documents': {'required': False},
            'profile_picture': {'required': False, 'allow_blank': True},
            'uploaded_documents': {'required': False},
        }
    
    def validate_email(self, value):
        """Validate email format and uniqueness"""
        if value:
            # Check if email is already taken by another user
            existing = User.objects.filter(email=value).exclude(user_id=self.instance.user_id).first()
            if existing:
                raise serializers.ValidationError(f"Email '{value}' is already taken")
        return value
    
    def validate_phone_number(self, value):
        """Validate phone number format and uniqueness"""
        if value:
            # Remove any non-digit characters
            import re
            value = re.sub(r'[\s\-\(\)\+]', '', value)
            
            # Check if phone is already taken by another user
            existing = User.objects.filter(phone_number=value).exclude(user_id=self.instance.user_id).first()
            if existing:
                raise serializers.ValidationError(f"Phone number '{value}' is already taken")
        return value
    
    def to_internal_value(self, data):
        """Convert skills from string to list before validation"""
        mutable_data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Handle skills conversion
        if 'skills' in mutable_data and mutable_data['skills']:
            skills_value = mutable_data['skills']
            if isinstance(skills_value, str):
                if ',' in skills_value:
                    mutable_data['skills'] = [skill.strip() for skill in skills_value.split(',') if skill.strip()]
                else:
                    mutable_data['skills'] = [skills_value.strip()]
            elif not isinstance(skills_value, list):
                mutable_data['skills'] = []
        
        # Handle salary conversion
        if 'salary' in mutable_data and mutable_data['salary']:
            salary_value = mutable_data['salary']
            if isinstance(salary_value, str):
                try:
                    from decimal import Decimal
                    mutable_data['salary'] = Decimal(salary_value.replace(',', ''))
                except:
                    pass
        
        # Handle years_of_experience conversion
        if 'years_of_experience' in mutable_data and mutable_data['years_of_experience']:
            exp_value = mutable_data['years_of_experience']
            if isinstance(exp_value, str) and exp_value.isdigit():
                mutable_data['years_of_experience'] = int(exp_value)
        
        return super().to_internal_value(mutable_data)
    
    def validate_skills(self, value):
        """Convert skills from string to list if needed"""
        if value is None:
            return []
        if isinstance(value, str):
            if ',' in value:
                return [skill.strip() for skill in value.split(',') if skill.strip()]
            else:
                return [value.strip()] if value.strip() else []
        if not isinstance(value, list):
            return []
        return value
    
    def validate_salary(self, value):
        """Convert salary from string/Decimal128 to Decimal"""
        from decimal import Decimal
        from bson import Decimal128
        
        if value is None:
            return None
        
        if isinstance(value, str):
            try:
                cleaned = value.replace(',', '').replace('$', '')
                return Decimal(cleaned)
            except:
                raise serializers.ValidationError("Salary must be a valid decimal number")
        
        if isinstance(value, Decimal128):
            return value.to_decimal()
        
        if isinstance(value, Decimal):
            return value
        
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        
        raise serializers.ValidationError("Salary must be a valid decimal number")
    
    def validate_years_of_experience(self, value):
        """Validate years of experience"""
        if value is None:
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            raise serializers.ValidationError("Years of experience must be a valid number")
    
    @transaction.atomic
    def update(self, instance, validated_data):
        from bson import Decimal128
        from decimal import Decimal
        
        # Lock rows to prevent race conditions
        user = User.objects.select_for_update().get(pk=instance.user.pk)
        instance = self.Meta.model.objects.select_for_update().get(pk=instance.pk)
        
        # ✅ Update User model fields (including email)
        user_fields = ['first_name', 'last_name', 'phone_number', 'email']
        for field in user_fields:
            if field in validated_data:
                value = validated_data.pop(field)
                if value is not None:
                    # Normalize phone number
                    if field == 'phone_number' and value:
                        import re
                        value = re.sub(r'[\s\-\(\)\+]', '', value)
                    
                    # ✅ Check uniqueness for email and phone
                    if field in ['email', 'phone_number']:
                        existing = User.objects.filter(
                            **{field: value}
                        ).exclude(user_id=user.user_id).first()
                        if existing:
                            raise serializers.ValidationError({
                                field: f"{field.replace('_', ' ').title()} '{value}' is already taken"
                            })
                    
                    setattr(user, field, value)
        
        # ✅ Handle is_active separately - Update BOTH User AND NurseProfile
        if 'is_active' in validated_data:
            is_active_value = validated_data.pop('is_active')
            # ✅ Update User
            user.is_active = is_active_value
            # ✅ Update NurseProfile
            instance.is_active = is_active_value
        
        try:
            user.full_clean()
            user.save()
        except Exception as e:
            if 'duplicate key' in str(e) or '11000' in str(e):
                raise serializers.ValidationError({
                    'email': 'This email is already registered to another user'
                })
            raise e
        
        # ✅ Sync email and phone to NurseProfile
        instance.email = user.email
        instance.phone_number = user.phone_number
        
        # Update NurseProfile fields
        for attr, value in validated_data.items():
            if value is not None and hasattr(instance, attr):
                # Convert Decimal128 to Decimal
                if isinstance(value, Decimal128):
                    value = value.to_decimal()
                elif attr == 'salary':
                    if isinstance(value, str):
                        try:
                            value = Decimal(value.replace(',', '').replace('$', ''))
                        except (ValueError, TypeError):
                            raise serializers.ValidationError({
                                attr: f'Invalid salary format: {value}'
                            })
                elif attr == 'skills':
                    if isinstance(value, str):
                        value = [skill.strip() for skill in value.split(',') if skill.strip()] if value.strip() else []
                    elif not isinstance(value, list):
                        value = []
                setattr(instance, attr, value)
        
        # Ensure fields are proper types
        instance.skills = instance.skills or []
        instance.documents = instance.documents or {}
        
        # Final safety check for Decimal128
        if isinstance(getattr(instance, 'salary', None), Decimal128):
            instance.salary = instance.salary.to_decimal()
        
        # ✅ Validate before saving
        instance.full_clean()
        instance.save()
        instance.user.refresh_from_db()
        
        return instance

# ==================== DOCTOR SERIALIZERS - ALL FIELDS ====================

class DoctorSerializer(serializers.ModelSerializer):
    """Serializer for reading doctor data - ALL FIELDS with License Fields"""
    
    email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True, default='')
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = DoctorProfile
        fields = [
            'doctor_id', 'user', 'full_name',
            'first_name', 'last_name',
            'phone_number', 'email', 'username', 'address', 'date_of_birth',
            'aadhar_number', 'gender', 'is_active',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relation',
            'employee_id', 'department', 'specialization', 'qualification',
            'joining_date', 'shift', 'employment_type', 'years_of_experience',
            'license_number', 'consultation_fee', 'available_days', 'available_time',
            'skills', 'assigned_ward', 'supervisor',
            'salary', 'bank_account_number', 'ifsc_code',
            'blood_group',
            'documents', 'profile_picture', 'uploaded_documents',
            'state_of_licensure',
            'license_expiry_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['doctor_id', 'created_at', 'updated_at']
    
    def get_full_name(self, obj):
        return f"Dr. {obj.user.first_name} {obj.user.last_name}"
    
    def to_representation(self, instance):
        """Safely serialize doctor data with license fields"""
        user = instance.user
        
        def safe_value(field):
            if field is None:
                return None
            try:
                if hasattr(field, 'url'):
                    return field.url
                elif isinstance(field, str):
                    return field
                else:
                    return str(field)
            except (ValueError, AttributeError):
                return str(field) if field else None
        
        return {
            'doctor_id': instance.doctor_id,
            'user': instance.user_id,
            'full_name': f"Dr. {user.first_name} {user.last_name}".strip(),
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': user.phone_number or "",
            'email': user.email or "",
            'username': user.username,
            'is_active': user.is_active,
            'address': instance.address or "",
            'date_of_birth': instance.date_of_birth,
            'aadhar_number': instance.aadhar_number,
            'gender': instance.gender,
            'emergency_contact_name': instance.emergency_contact_name,
            'emergency_contact_phone': instance.emergency_contact_phone,
            'emergency_contact_relation': instance.emergency_contact_relation,
            'employee_id': instance.employee_id,
            'department': instance.department,
            'specialization': instance.specialization,
            'qualification': instance.qualification,
            'joining_date': instance.joining_date,
            'shift': instance.shift,
            'employment_type': instance.employment_type,
            'years_of_experience': instance.years_of_experience,
            'license_number': instance.license_number,
            'consultation_fee': str(instance.consultation_fee) if instance.consultation_fee else None,
            'available_days': instance.available_days if isinstance(instance.available_days, list) else [],
            'available_time': instance.available_time if isinstance(instance.available_time, dict) else {},
            'skills': instance.skills if isinstance(instance.skills, list) else [],
            'assigned_ward': instance.assigned_ward,
            'supervisor': instance.supervisor,
            'salary': str(instance.salary) if instance.salary else None,
            'bank_account_number': instance.bank_account_number,
            'ifsc_code': instance.ifsc_code,
            'blood_group': instance.blood_group,
            'documents': instance.documents if isinstance(instance.documents, dict) else {},
            'profile_picture': safe_value(instance.profile_picture),
            'uploaded_documents': safe_value(instance.uploaded_documents),
            'state_of_licensure': instance.state_of_licensure or "",
            'license_expiry_date': instance.license_expiry_date,
            'created_at': instance.created_at,
            'updated_at': instance.updated_at,
        }


class DoctorCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating doctor - WITH LICENSE FIELDS"""
    
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    username = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = DoctorProfile
        fields = [
            'email', 'password', 'confirm_password', 'username',
            'first_name', 'last_name', 'phone_number', 'address',
            'date_of_birth', 'aadhar_number', 'gender',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relation',
            'employee_id', 'department', 'specialization', 'qualification',
            'joining_date', 'shift', 'employment_type', 'years_of_experience',
            'license_number', 'consultation_fee', 'available_days', 'available_time',
            'state_of_licensure',      # ✅ ADDED
            'license_expiry_date',     # ✅ ADDED
            'skills', 'assigned_ward', 'supervisor',
            'salary', 'bank_account_number', 'ifsc_code',
            'blood_group',
            'documents', 'profile_picture', 'uploaded_documents'
        ]
        extra_kwargs = {
            'employee_id': {'required': False},
            'license_number': {'required': True},
            'qualification': {'required': True},
            'joining_date': {'required': True},
            'years_of_experience': {'required': False, 'default': 0},
            'state_of_licensure': {'required': False, 'allow_blank': True},      # ✅ ADDED
            'license_expiry_date': {'required': False, 'allow_null': True},      # ✅ ADDED
        }
    
    def generate_employee_id(self):
        for _ in range(5):
            new_id = f"DOC{uuid.uuid4().hex[:6].upper()}"
            if not DoctorProfile.objects.filter(employee_id=new_id).exists():
                return new_id
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"DOC{timestamp}{uuid.uuid4().hex[:4].upper()}"
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match'})
        
        if len(data['password']) < 8:
            raise serializers.ValidationError({'password': 'Password must be at least 8 characters'})
        
        phone_number = data.get('phone_number', '')
        if phone_number and phone_number.strip():
            if User.objects.filter(phone_number=phone_number).exists():
                raise serializers.ValidationError({
                    'phone_number': 'Phone number already registered. Please use a different number.'
                })
        
        license_num = data.get('license_number')
        if DoctorProfile.objects.filter(license_number=license_num).exists():
            raise serializers.ValidationError({'license_number': 'License number already exists'})
        
        emp_id = data.get('employee_id')
        if emp_id == '' or emp_id is None:
            data['employee_id'] = self.generate_employee_id()
        elif DoctorProfile.objects.filter(employee_id=emp_id).exists():
            raise serializers.ValidationError({'employee_id': 'Employee ID already exists'})
        
        aadhar = data.get('aadhar_number')
        if aadhar and DoctorProfile.objects.filter(aadhar_number=aadhar).exists():
            raise serializers.ValidationError({'aadhar_number': 'Aadhar number already exists'})
        
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({'email': 'Email already exists'})
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        username = validated_data.pop('username', None)
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        phone_number = validated_data.pop('phone_number', '')
        
        if not username:
            username = email.split('@')[0]
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            user_type='DOCTOR'
        )
        
        doctor = DoctorProfile.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            **validated_data
        )
        
        return doctor


class DoctorUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating doctor - WITH LICENSE FIELDS AND EMAIL"""
    
    # ✅ email - writable now (not read_only)
    email = serializers.EmailField(required=False, allow_blank=True)
    username = serializers.CharField(read_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    
    class Meta:
        model = DoctorProfile
        fields = [
            'email', 'username', 'first_name', 'last_name', 'phone_number',
            'date_of_birth', 'address', 'is_active',
            'aadhar_number', 'gender',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relation',
            'employee_id', 'department', 'specialization', 'qualification',
            'joining_date', 'shift', 'employment_type', 'years_of_experience',
            'license_number', 'consultation_fee', 'available_days', 'available_time',
            'state_of_licensure',
            'license_expiry_date',
            'skills', 'assigned_ward', 'supervisor',
            'salary', 'bank_account_number', 'ifsc_code',
            'blood_group',
            'documents', 'profile_picture', 'uploaded_documents'
        ]
        extra_kwargs = {
            'employee_id': {'required': False, 'allow_blank': True},
            'department': {'required': False, 'allow_blank': True},
            'specialization': {'required': False, 'allow_blank': True},
            'qualification': {'required': False, 'allow_blank': True},
            'joining_date': {'required': False, 'allow_null': True},
            'shift': {'required': False, 'allow_blank': True},
            'employment_type': {'required': False, 'allow_blank': True},
            'years_of_experience': {'required': False},
            'license_number': {'required': False, 'allow_blank': True},
            'consultation_fee': {'required': False, 'allow_null': True},
            'available_days': {'required': False},
            'available_time': {'required': False},
            'state_of_licensure': {'required': False, 'allow_blank': True},
            'license_expiry_date': {'required': False, 'allow_null': True},
            'skills': {'required': False},
            'assigned_ward': {'required': False, 'allow_blank': True},
            'supervisor': {'required': False, 'allow_blank': True},
            'salary': {'required': False, 'allow_null': True},
            'bank_account_number': {'required': False, 'allow_blank': True},
            'ifsc_code': {'required': False, 'allow_blank': True},
            'aadhar_number': {'required': False, 'allow_blank': True},
            'gender': {'required': False, 'allow_blank': True},
            'emergency_contact_name': {'required': False, 'allow_blank': True},
            'emergency_contact_phone': {'required': False, 'allow_blank': True},
            'emergency_contact_relation': {'required': False, 'allow_blank': True},
            'blood_group': {'required': False, 'allow_blank': True},
            'documents': {'required': False},
            'profile_picture': {'required': False, 'allow_blank': True},
            'uploaded_documents': {'required': False},
        }
    
    def validate_consultation_fee(self, value):
        if value is None:
            return None
        if hasattr(value, 'to_decimal'):
            return value.to_decimal()
        if isinstance(value, str):
            try:
                from decimal import Decimal
                return Decimal(value)
            except:
                raise serializers.ValidationError("Consultation fee must be a valid number")
        return value
    
    def validate_salary(self, value):
        if value is None:
            return None
        if hasattr(value, 'to_decimal'):
            return value.to_decimal()
        if isinstance(value, str):
            try:
                from decimal import Decimal
                return Decimal(value)
            except:
                raise serializers.ValidationError("Salary must be a valid number")
        return value
    
    def validate_email(self, value):
        """Validate email format"""
        if value and not isinstance(value, str):
            return value
        if value and '@' not in value:
            raise serializers.ValidationError("Enter a valid email address")
        return value
    
    @transaction.atomic
    def update(self, instance, validated_data):
        user = instance.user
        
        # ✅ Update User fields (including email)
        user_fields = ['first_name', 'last_name', 'phone_number', 'is_active', 'email']
        for field in user_fields:
            if field in validated_data:
                value = validated_data.pop(field)
                if value is not None:
                    setattr(user, field, value)
        
        if 'date_of_birth' in validated_data:
            if hasattr(user, 'date_of_birth'):
                user.date_of_birth = validated_data.pop('date_of_birth')
        
        if 'address' in validated_data:
            if hasattr(user, 'address'):
                user.address = validated_data.pop('address')
        
        user.save()
        
        for attr, value in validated_data.items():
            if value is not None and hasattr(instance, attr):
                setattr(instance, attr, value)
        
        if hasattr(instance.consultation_fee, 'to_decimal'):
            instance.consultation_fee = instance.consultation_fee.to_decimal()
        if hasattr(instance.salary, 'to_decimal'):
            instance.salary = instance.salary.to_decimal()
        
        instance.save()
        instance.user.refresh_from_db()
        
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
            'patient_no',
            'full_name',
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'date_of_birth',
            'age',
            'gender',
            'blood_group',  
            'marital_status',
            'patient_status',  
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
    confirm_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    
    # Patient profile fields
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    date_of_birth = serializers.DateField(write_only=True, required=False, allow_null=True)
    gender = serializers.ChoiceField(write_only=True, choices=['MALE', 'FEMALE', 'OTHER'])
    blood_group = serializers.ChoiceField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
        choices=['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    )
    marital_status = serializers.ChoiceField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
        choices=['SINGLE', 'MARRIED', 'DIVORCED', 'WIDOWED']
    )
    address = serializers.CharField(write_only=True, required=False, allow_blank=True)
    emergency_contact_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    emergency_contact_phone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    emergency_contact_relation = serializers.CharField(write_only=True, required=False, allow_blank=True)
    aadhar_number = serializers.CharField(write_only=True)
    profile_picture = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    
    # Read-only field for age (will be calculated)
    age = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = PatientProfile
        fields = [
            'email', 'password', 'confirm_password', 'phone_number',
            'first_name', 'last_name', 'date_of_birth', 'gender',
            'blood_group', 'marital_status',
            'address', 'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relation', 'aadhar_number', 'profile_picture',
            'age'
        ]
    
    def calculate_age(self, birth_date):
        """Calculate age from date of birth"""
        if not birth_date:
            return None
        
        today = date.today()
        age = today.year - birth_date.year
        
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        
        return age
    
    def validate_date_of_birth(self, value):
        """Validate date of birth"""
        if not value:
            return value
        
        if value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future")
        
        age = self.calculate_age(value)
        if age is not None and age < 1:
            raise serializers.ValidationError("Patient must be at least 1 year old")
        
        if age is not None and age > 120:
            raise serializers.ValidationError("Invalid date of birth - age cannot exceed 120 years")
        
        return value
    
    def generate_unique_phone(self):
        """Generate a unique phone number"""
        import random
        prefixes = ['987654', '998877', '912345', '900000', '888888', '777777', '987654', '987655']
        
        for _ in range(20):
            prefix = random.choice(prefixes)
            suffix = str(random.randint(1000, 9999))
            phone = f"{prefix}{suffix}"
            
            # Check if this phone number is already used
            if not User.objects.filter(phone_number=phone).exists():
                return phone
        
        # Fallback to timestamp-based unique number
        from datetime import datetime
        timestamp = datetime.now().strftime('%d%H%M%S%f')[:8]
        return f"987654{timestamp}"
    
    def validate(self, data):
        # Validate confirm_password
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        
        if password != confirm_password:
            raise serializers.ValidationError({
                'confirm_password': 'Password and Confirm Password do not match'
            })
        
        # Password validation
        if len(data.get('password', '')) < 8:
            raise serializers.ValidationError({"password": "Password must be at least 8 characters"})
        
        # 🔴 CRITICAL FIX: Ensure phone_number is never None
        phone_number = data.get('phone_number')
        
        # If phone_number is None, empty string, or not provided, generate one
        if not phone_number or phone_number == '' or phone_number is None:
            phone_number = self.generate_unique_phone()
            data['phone_number'] = phone_number
            print(f"✅ Generated unique phone number: {phone_number}")
        else:
            # Phone number provided, validate it's unique
            if User.objects.filter(phone_number=phone_number).exists():
                # If the provided phone number is taken, generate a new one
                phone_number = self.generate_unique_phone()
                data['phone_number'] = phone_number
                print(f"⚠️ Phone number was taken, generated: {phone_number}")
        
        # Email validation
        email = data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "User with this email already exists"})
        
        # Aadhar number validation
        aadhar = data.get('aadhar_number')
        if aadhar and PatientProfile.objects.filter(aadhar_number=aadhar).exists():
            raise serializers.ValidationError({"aadhar_number": "Aadhar number already exists"})
        
        # Date of birth validation
        dob = data.get('date_of_birth')
        if dob:
            age = self.calculate_age(dob)
            if age is not None:
                data['calculated_age'] = age
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        # Remove confirm_password
        validated_data.pop('confirm_password')
        
        # Extract user data
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        
        # 🔴 CRITICAL: Ensure phone_number is never None when creating user
        phone_number = validated_data.pop('phone_number', None)
        if phone_number is None or phone_number == '':
            phone_number = self.generate_unique_phone()
            print(f"🔄 Generated phone number in create: {phone_number}")
        
        # Extract patient profile data
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        date_of_birth = validated_data.pop('date_of_birth', None)
        gender = validated_data.pop('gender')
        blood_group = validated_data.pop('blood_group', None)
        marital_status = validated_data.pop('marital_status', None)
        address = validated_data.pop('address', '')
        emergency_contact_name = validated_data.pop('emergency_contact_name', '')
        emergency_contact_phone = validated_data.pop('emergency_contact_phone', '')
        emergency_contact_relation = validated_data.pop('emergency_contact_relation', '')
        aadhar_number = validated_data.pop('aadhar_number')
        profile_picture = validated_data.pop('profile_picture', None)
        
        # Remove calculated_age if present
        validated_data.pop('calculated_age', None)
        
        # Create username from email
        username = email.split('@')[0]
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        # 🔴 Create user with phone_number (never None)
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,  # Always a string, never None
            user_type='PATIENT'
        )
        
        # Create patient profile with all fields
        patient = PatientProfile.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            gender=gender,
            blood_group=blood_group,
            marital_status=marital_status,
            address=address,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
            emergency_contact_relation=emergency_contact_relation,
            aadhar_number=aadhar_number,
            profile_picture=profile_picture,
            patient_status='active'
        )
        
        return patient
    
    def to_representation(self, instance):
        """Add calculated age to response"""
        representation = super().to_representation(instance)
        if instance.date_of_birth:
            representation['age'] = self.calculate_age(instance.date_of_birth)
        else:
            representation['age'] = None
        return representation


# patients/serializers.py

class PatientUpdateSerializer(serializers.ModelSerializer):
    # User fields
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=False)
    is_active = serializers.BooleanField(required=False)
    
    # Patient profile fields
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(required=False, choices=['MALE', 'FEMALE', 'OTHER'])
    blood_group = serializers.ChoiceField(
        required=False,
        allow_blank=True,
        allow_null=True,
        choices=['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    )
    marital_status = serializers.ChoiceField(
        required=False,
        allow_blank=True,
        allow_null=True,
        choices=['SINGLE', 'MARRIED', 'DIVORCED', 'WIDOWED']
    )
    patient_status = serializers.ChoiceField(
        required=False,
        allow_null=False,
        choices=['active', 'inactive', 'recovered'],
        default='active'
    )
    
    # Status reason fields - ✅ Add allow_null=True
    status_reason = serializers.ChoiceField(
        required=False,
        allow_null=True,
        choices=['recovered', 'deceased', 'discontinued']
    )
    recovery_date = serializers.DateField(required=False, allow_null=True)
    recovery_notes = serializers.CharField(required=False, allow_null=True, allow_blank=True)  # ✅ Changed
    death_date = serializers.DateField(required=False, allow_null=True)
    death_cause = serializers.CharField(required=False, allow_null=True, allow_blank=True)  # ✅ Changed
    death_notes = serializers.CharField(required=False, allow_null=True, allow_blank=True)  # ✅ Changed
    discontinuation_date = serializers.DateField(required=False, allow_null=True)
    discontinuation_reason = serializers.CharField(required=False, allow_null=True, allow_blank=True)  # ✅ Changed
    discontinuation_notes = serializers.CharField(required=False, allow_null=True, allow_blank=True)  # ✅ Changed
    
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
            'date_of_birth', 'gender', 'blood_group', 'marital_status', 'patient_status',
            'status_reason', 'recovery_date', 'recovery_notes',
            'death_date', 'death_cause', 'death_notes',
            'discontinuation_date', 'discontinuation_reason', 'discontinuation_notes',
            'address', 'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relation',
            'aadhar_number', 'profile_picture'
        ]
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        if value:
            current_user = self.instance.user
            if User.objects.filter(email=value).exclude(user_id=current_user.user_id).exists():
                raise serializers.ValidationError("User with this email already exists")
        return value
    
    def validate(self, data):
        # Convert empty phone to None
        if 'phone_number' in data and data['phone_number'] == '':
            data['phone_number'] = None
        
        # Convert to lowercase for storage
        if 'patient_status' in data and data['patient_status']:
            data['patient_status'] = data['patient_status'].lower()
        
        # ✅ Handle null values - convert None to empty string for text fields
        text_fields = ['recovery_notes', 'death_cause', 'death_notes', 
                       'discontinuation_reason', 'discontinuation_notes']
        for field in text_fields:
            if field in data and data[field] is None:
                data[field] = ''
        
        # Validate status reason when patient is inactive or recovered
        patient_status = data.get('patient_status')
        status_reason = data.get('status_reason')
        
        if patient_status in ['inactive', 'recovered']:
            if not status_reason:
                raise serializers.ValidationError({
                    "status_reason": "Status reason is required when patient is inactive or recovered"
                })
            
            # Validate based on reason
            if status_reason == 'recovered':
                if not data.get('recovery_date'):
                    raise serializers.ValidationError({
                        "recovery_date": "Recovery date is required for recovered patients"
                    })
            elif status_reason == 'deceased':
                if not data.get('death_date'):
                    raise serializers.ValidationError({
                        "death_date": "Death date is required for deceased patients"
                    })
            elif status_reason == 'discontinued':
                if not data.get('discontinuation_date'):
                    raise serializers.ValidationError({
                        "discontinuation_date": "Discontinuation date is required for discontinued treatment"
                    })
        
        # Clear reason fields when reactivating
        if patient_status == 'active':
            data['status_reason'] = None
            data['recovery_date'] = None
            data['recovery_notes'] = ''
            data['death_date'] = None
            data['death_cause'] = ''
            data['death_notes'] = ''
            data['discontinuation_date'] = None
            data['discontinuation_reason'] = ''
            data['discontinuation_notes'] = ''
        
        # Check phone number uniqueness if changed
        phone = data.get('phone_number')
        if phone:
            current_user = self.instance.user
            pk_name = current_user._meta.pk.name
            pk_value = getattr(current_user, pk_name)
            
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
        
        user_fields = ['first_name', 'last_name', 'phone_number', 'is_active', 'email']
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
        
        # Ensure patient_status is never null
        if not instance.patient_status:
            instance.patient_status = 'active'
        
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



class PatientListSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    condition = serializers.SerializerMethodField()
    
    class Meta:
        model = PatientProfile
        fields = ['patient_id', 'name', 'age', 'gender', 'condition']
    
    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    
    def get_age(self, obj):
        if obj.date_of_birth:
            today = timezone.now().date()
            return today.year - obj.date_of_birth.year
        return None
    
    def get_condition(self, obj):
        medical_record = obj.medical_records.first()
        if medical_record and medical_record.cancer_type:
            return medical_record.cancer_type.name
        return 'N/A'

class AlertSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Alert
        fields = '__all__'
    
    def get_patient_name(self, obj):
        patient = PatientProfile.objects.filter(patient_id=obj.patient_id).first()
        if patient:
            return f"{patient.first_name} {patient.last_name}"
        return 'Unknown'

class DashboardStatsSerializer(serializers.Serializer):
    total_patients = serializers.IntegerField()
    critical = serializers.IntegerField()
    high_risk = serializers.IntegerField()
    active_alerts = serializers.IntegerField()
    need_review = serializers.IntegerField()

class PatientTrendSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()
    patient_name = serializers.CharField()
    data = serializers.ListField()