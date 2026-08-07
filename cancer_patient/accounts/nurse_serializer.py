import json
import uuid
from decimal import Decimal
 
from django.db import transaction
from rest_framework import serializers
 
from .models import NurseProfile, User
 
 
# ===========================================================================
# Helper
# ===========================================================================
 
def _to_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith('['):
            try:
                parsed = json.loads(stripped.replace("'", '"'))
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
        return [s.strip() for s in stripped.split(',') if s.strip()]
    return []
 
 
def _build_media_url(path, request):
    """
    Given a raw relative path like  nurse_profiles/profile_pictures/abc.jpeg
    return a full absolute URL.  Works with or without a request object.
    """
    if not path:
        return None
    p = str(path).replace('\\', '/')
    # Already absolute
    if p.startswith('http') or p.startswith('data:'):
        return p
    if request:
        from django.conf import settings
        media_url = settings.MEDIA_URL.rstrip('/')
        clean = p.lstrip('/')
        # Avoid double "media/media/"
        if clean.startswith('media/'):
            clean = clean[len('media/'):]
        return request.build_absolute_uri(f"{media_url}/{clean}")
    # Fallback — no request in context (e.g. management commands / tests)
    from django.conf import settings
    media_url = settings.MEDIA_URL.rstrip('/')
    clean = p.lstrip('/')
    if clean.startswith('media/'):
        clean = clean[len('media/'):]
    return f"{media_url}/{clean}"
 
 
# ===========================================================================
# UserSerializer
# ===========================================================================
 
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ['user_id', 'username', 'email', 'phone_number',
                  'user_type', 'is_verified', 'created_at']
        read_only_fields = ['user_id', 'created_at']
 
 
# ===========================================================================
# NurseSerializer — READ ONLY (GET / response after create & update)
# ===========================================================================
 
class NurseSerializer(serializers.ModelSerializer):
    user      = UserSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
 
    email        = serializers.EmailField(source='user.email',       read_only=True)
    username     = serializers.CharField(source='user.username',     read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    is_active    = serializers.BooleanField(source='user.is_active', read_only=True)
 
    profile_picture    = serializers.SerializerMethodField()
    uploaded_documents = serializers.SerializerMethodField()
 
    skills    = serializers.ListField(
        child=serializers.CharField(max_length=100),
        default=list, required=False, allow_empty=True,
    )
    documents = serializers.DictField(default=dict, required=False)
 
    class Meta:
        model  = NurseProfile
        fields = [
            'nurse_id', 'user', 'full_name',
            'first_name', 'last_name',
            'phone_number', 'email', 'username',
            'address', 'date_of_birth', 'aadhar_number', 'gender',
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relation',
            'employee_id', 'department', 'qualification', 'joining_date',
            'shift', 'employment_type', 'years_of_experience', 'is_active',
            'skills', 'assigned_ward', 'supervisor',
            'salary', 'bank_account_number', 'ifsc_code', 'blood_group',
            'documents', 'profile_picture', 'uploaded_documents',
            'created_at', 'updated_at',
        ]
 
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()
 
    def get_profile_picture(self, obj):
        return _build_media_url(obj.profile_picture, self.context.get('request'))
 
    # ✅ FIXED: always builds an absolute URL from the stored relative path
    def get_uploaded_documents(self, obj):
        return _build_media_url(obj.uploaded_documents, self.context.get('request'))
 
 
# ===========================================================================
# NurseCreateSerializer — WRITE (POST)
# ===========================================================================
 
class NurseCreateSerializer(serializers.ModelSerializer):
    email            = serializers.EmailField(write_only=True)
    password         = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True)
    username         = serializers.CharField(write_only=True, required=False)
    is_active        = serializers.BooleanField(required=False, default=True)
 
    profile_picture    = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    uploaded_documents = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
 
    skills    = serializers.ListField(
        child=serializers.CharField(max_length=100),
        default=list, required=False, allow_empty=True,
    )
    documents = serializers.DictField(default=dict, required=False)
 
    class Meta:
        model  = NurseProfile
        fields = [
            'nurse_id', 'first_name', 'last_name', 'phone_number',
            'address', 'date_of_birth', 'aadhar_number', 'gender',
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relation',
            'employee_id', 'department', 'qualification', 'joining_date',
            'shift', 'employment_type', 'years_of_experience', 'is_active',
            'skills', 'assigned_ward', 'supervisor',
            'salary', 'bank_account_number', 'ifsc_code', 'blood_group',
            'documents', 'profile_picture', 'uploaded_documents',
            'email', 'username', 'password', 'confirm_password',
        ]
        read_only_fields = ['nurse_id', 'employee_id', 'created_at', 'updated_at']
        extra_kwargs = {'user': {'required': False, 'read_only': False}}
 
    def validate_phone_number(self, value):
        if value:
            digits = str(value).replace(' ', '')
            if not digits.isdigit():
                raise serializers.ValidationError("Phone number must contain only digits.")
            if len(digits) != 10:
                raise serializers.ValidationError("Phone number must be exactly 10 digits.")
        return value

    # ✅ ADDED: handles "true"/"false" strings from multipart/form-data
    def validate_is_active(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() in ('true', '1', 'yes'):
                return True
            if value.lower() in ('false', '0', 'no'):
                return False
            raise serializers.ValidationError("Must be a boolean (true/false).")
        return bool(value)
 
    def validate_skills(self, value):
        return _to_list(value)
 
    def validate_documents(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Documents must be a dictionary.")
        return value
 
    def validate_profile_picture(self, value):
        # Accept empty string / None → store as None
        return value if value else None
 
    # ✅ ADDED: mirror of validate_profile_picture so empty string → None
    def validate_uploaded_documents(self, value):
        return value if value else None
 
    def validate(self, data):
        if data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."})
        data.setdefault('skills', [])
        data.setdefault('documents', {})
        return data
 
    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('confirm_password')
 
        email              = validated_data.pop('email')
        password           = validated_data.pop('password')
        base_uname         = validated_data.pop('username', email.split('@')[0])
        first_name         = validated_data.pop('first_name')
        last_name          = validated_data.pop('last_name')
        phone              = validated_data.pop('phone_number', '')
        is_active          = validated_data.pop('is_active', True)
        skills             = _to_list(validated_data.pop('skills', []))
        documents          = validated_data.pop('documents', {}) or {}
        profile_picture    = validated_data.pop('profile_picture', None)
        uploaded_documents = validated_data.pop('uploaded_documents', None)
 
        # Debug — remove after confirming fix
        print(f"[NurseCreate] profile_picture length   : {len(profile_picture) if profile_picture else 0}")
        print(f"[NurseCreate] uploaded_documents length: {len(uploaded_documents) if uploaded_documents else 0}")
 
        username = base_uname
        counter  = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_uname}{counter}"
            counter += 1
 
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone,
            user_type='NURSE',
        )
        user.is_active = is_active
        user.save()
 
        employee_id = validated_data.pop('employee_id', None)
        if not employee_id:
            employee_id = f"NUR{uuid.uuid4().hex[:8].upper()}"
 
        nurse = NurseProfile.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone,
            employee_id=employee_id,
            skills=skills,
            documents=documents,
            is_active=is_active,
            profile_picture=profile_picture or None,
            uploaded_documents=uploaded_documents or None,
            **validated_data,
        )
        return nurse
 
 
# ===========================================================================
# NurseUpdateSerializer — WRITE (PATCH)
# ===========================================================================
 
class NurseUpdateSerializer(serializers.Serializer):
 
    first_name                 = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    last_name                  = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    phone_number               = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    address                    = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    date_of_birth              = serializers.DateField(required=False, allow_null=True)
    aadhar_number              = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    gender                     = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    blood_group                = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    emergency_contact_name     = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    emergency_contact_phone    = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    emergency_contact_relation = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    department                 = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    qualification              = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    joining_date               = serializers.DateField(required=False, allow_null=True)
    shift                      = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    employment_type            = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    years_of_experience        = serializers.IntegerField(required=False, allow_null=True)
    is_active                  = serializers.BooleanField(required=False, allow_null=True)
    assigned_ward              = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    supervisor                 = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    salary                     = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    bank_account_number        = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ifsc_code                  = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    skills                     = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False, allow_empty=True, default=list,
    )
    documents                  = serializers.DictField(required=False, default=dict)
    # ✅ CharField accepts the base64 string sent from the frontend
    profile_picture            = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    uploaded_documents         = serializers.CharField(required=False, allow_blank=True, allow_null=True)
 
    PROTECTED_FIELDS   = frozenset(['skills', 'documents'])
    SHARED_USER_FIELDS = frozenset(['first_name', 'last_name', 'phone_number'])
 
    def validate_skills(self, value):
        return _to_list(value)
 
    def validate_documents(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Documents must be a dictionary.")
        return value
 
    def validate_phone_number(self, value):
        if value:
            digits = str(value).replace(' ', '')
            if not digits.isdigit():
                raise serializers.ValidationError("Phone number must contain only digits.")
            if len(digits) != 10:
                raise serializers.ValidationError("Phone number must be exactly 10 digits.")
        return value

    # ✅ ADDED: handles "true"/"false" strings from multipart/form-data
    def validate_is_active(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() in ('true', '1', 'yes'):
                return True
            if value.lower() in ('false', '0', 'no'):
                return False
            raise serializers.ValidationError("Must be a boolean (true/false).")
        return bool(value)
 
    # ✅ ADDED: empty string → None so existing document isn't wiped on unrelated updates
    def validate_profile_picture(self, value):
        return value if value else None
 
    def validate_uploaded_documents(self, value):
        return value if value else None
 
    @staticmethod
    def _fix_djongo_fields(instance):
        from django.db.models import Field
        for field in instance._meta.get_fields():
            if not isinstance(field, Field):
                continue
            field_type = type(field).__name__
            if getattr(instance, field.name, None) is None:
                if field_type == 'ArrayField':
                    setattr(instance, field.name, [])
                elif field_type in ('JSONField', 'DictField', 'EmbeddedField'):
                    setattr(instance, field.name, {})
 
    @transaction.atomic
    def update(self, instance, validated_data):
 
        # ── Sync User fields ───────────────────────────────────────────────
        if hasattr(instance, 'user') and instance.user:
            user         = instance.user
            user_changed = False
 
            for field in self.SHARED_USER_FIELDS:
                if field in validated_data and validated_data[field] is not None:
                    setattr(user, field, validated_data[field])
                    user_changed = True
 
            is_active = validated_data.get('is_active')
            if is_active is not None:
                user.is_active = is_active
                user_changed   = True
 
            if user_changed:
                user.save()
 
        # ── Coerce skills / documents ──────────────────────────────────────
        if 'skills' in validated_data:
            validated_data['skills'] = _to_list(validated_data['skills'])
 
        if 'documents' in validated_data:
            docs = validated_data['documents']
            validated_data['documents'] = docs if isinstance(docs, dict) else {}
 
        # Debug — remove after confirming fix
        print(f"[NurseUpdate] uploaded_documents in payload: {'YES' if validated_data.get('uploaded_documents') else 'NO / None'}")
 
        # ── Update NurseProfile fields ─────────────────────────────────────
        for attr, value in validated_data.items():
            if not hasattr(instance, attr):
                continue
            if attr in self.PROTECTED_FIELDS:
                if value is not None:
                    setattr(instance, attr, value)
                continue
            if value is not None:
                setattr(instance, attr, value)
 
        self._fix_djongo_fields(instance)
        instance.save()
        return instance