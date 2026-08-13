from django.contrib.auth.models import AbstractUser
from djongo import models
from django.utils import timezone
import jwt
from django.conf import settings
import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

from django.contrib.auth.models import BaseUserManager

class CustomUserManager(BaseUserManager):

    def get_by_natural_key(self, username):
        return self.get(username=username)

    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError("Username required")

        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        return self.create_user(username, email, password, **extra_fields)
    
class User(AbstractUser):
    USER_TYPES = (
        ('PATIENT', 'Patient'),
        ('NURSE', 'Nurse'),
        ('DOCTOR', 'Doctor'),
        ('ADMIN', 'Administrator'),
    )
    
    user_id = models.AutoField(primary_key=True)
    user_type = models.CharField(max_length=10, choices=USER_TYPES)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = CustomUserManager()
    
    class Meta:
        db_table = 'users'
    
    def __str__(self):
        return f"User {self.user_id}: {self.username} ({self.user_type})"
    
    def generate_token(self):
        try:
            payload = {
                'user_id': self.user_id,
                'username': self.username,
                'user_type': self.user_type,
                'exp': timezone.now() + settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']
            }
            return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        except Exception as e:
            logger.error(f"Token generation failed: {str(e)}")
            raise

class PatientProfile(models.Model):
    
    PATIENT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('recovered', 'Recovered'),
    ]
    
    # Add status reason choices
    STATUS_REASON_CHOICES = [
        ('recovered', 'Recovered - Successfully completed treatment'),
        ('deceased', 'Deceased - Patient expired'),
        ('discontinued', 'Discontinued Treatment - Left against medical advice'),
    ]

    patient_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    patient_no = models.CharField(max_length=20, unique=True, blank=True, editable=False, null=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=(
        ('MALE', 'Male'), ('FEMALE', 'Female'), ('OTHER', 'Other')
    ))
    blood_group = models.CharField(max_length=5, choices=(
        ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-')
    ), blank=True, null=True)
    
    marital_status = models.CharField(max_length=20, choices=(
        ('SINGLE', 'Single'), ('MARRIED', 'Married'),
        ('DIVORCED', 'Divorced'), ('WIDOWED', 'Widowed')
    ), blank=True, null=True)
    
    patient_status = models.CharField(max_length=20, choices=PATIENT_STATUS_CHOICES, default='active')
    
    # Add new fields for status reason
    status_reason = models.CharField(max_length=20, choices=STATUS_REASON_CHOICES, null=True, blank=True)
    
    # Recovery fields
    recovery_date = models.DateField(null=True, blank=True)
    recovery_notes = models.TextField(blank=True, null=True)  # ✅ Added null=True
    
    # Deceased fields
    death_date = models.DateField(null=True, blank=True)
    death_cause = models.TextField(blank=True, null=True)  # ✅ Added null=True
    death_notes = models.TextField(blank=True, null=True)  # ✅ Added null=True
    
    # Discontinued fields
    discontinuation_date = models.DateField(null=True, blank=True)
    discontinuation_reason = models.TextField(blank=True, null=True)  # ✅ Added null=True
    discontinuation_notes = models.TextField(blank=True, null=True)  # ✅ Added null=True
    
    address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True)
    emergency_contact_relation = models.CharField(max_length=50, blank=True)
    aadhar_number = models.CharField(max_length=12, null=True, blank=True)
    profile_picture = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'patient_profiles'
    
    def save(self, *args, **kwargs):
        if not self.patient_no:
            self.patient_no = self.generate_patient_no()
        super().save(*args, **kwargs)
    
    def generate_patient_no(self):
        """
        Generate patient number in format: PT2026030001
        PT + YearMonth + 4-digit sequence
        """
        from django.utils import timezone
        
        now = timezone.now()
        year_month = now.strftime('%Y%m')
        prefix = f"PT{year_month}"
        
        last_patient = PatientProfile.objects.filter(
            patient_no__startswith=prefix
        ).order_by('patient_no').last()
        
        if last_patient and last_patient.patient_no:
            try:
                last_seq = int(last_patient.patient_no[-4:])
                new_seq = last_seq + 1
            except (ValueError, IndexError):
                new_seq = 1
        else:
            new_seq = 1
        
        patient_no = f"{prefix}{new_seq:04d}"
        
        while PatientProfile.objects.filter(patient_no=patient_no).exists():
            new_seq += 1
            patient_no = f"{prefix}{new_seq:04d}"
        
        return patient_no
    
    def __str__(self):
        return f"{self.patient_no} - {self.first_name} {self.last_name}"

class NurseProfile(models.Model):
    nurse_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='nurse_profile')
    
    # Personal Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    aadhar_number = models.CharField(max_length=12, null=True, blank=True)
    gender = models.CharField(max_length=10, choices=(
        ('MALE', 'Male'), ('FEMALE', 'Female'), ('OTHER', 'Other')
    ), null=True, blank=True)
    
    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True)
    emergency_contact_relation = models.CharField(max_length=50, blank=True)
    
    # Employment Information
    employee_id = models.CharField(max_length=50, unique=True)
    department = models.CharField(max_length=100)
    qualification = models.TextField(blank=True)
    joining_date = models.DateField()
    shift = models.CharField(max_length=50, blank=True)  # Morning/Night
    employment_type = models.CharField(max_length=50, blank=True)  # Full-time/Part-time
    years_of_experience = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Skills & Ward Assignment
    skills = models.JSONField(default=list, blank=True)  # e.g., ["ICU", "Pediatrics"]
    assigned_ward = models.CharField(max_length=100, blank=True)
    supervisor = models.CharField(max_length=100, blank=True)
    
    # Financial Information
    salary = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    
    # Additional Fields
    blood_group = models.CharField(max_length=5, choices=(
        ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-')
    ), blank=True, null=True)
    
    # Documents
    documents = models.JSONField(default=dict, blank=True, help_text="""Store all documents in one JSON field:
    {
        "qualification_certificate": "file_path_or_url",
        "nursing_license": "file_path_or_url",
        "id_proof": "file_path_or_url",
        "address_proof": "file_path_or_url",
        "experience_letter": "file_path_or_url",
        "training_certificates": ["file1.pdf", "file2.pdf"],
        "other_documents": ["file1.jpg", "file2.pdf"]
    }
    """)
    profile_picture = models.CharField(max_length=500000, blank=True, null=True)
    uploaded_documents = models.TextField(blank=True, null=True)    
    # Licensure Information 
    state_of_licensure  = models.CharField(max_length=100, blank=True, null=True)
    license_number      = models.CharField(max_length=100, blank=True, null=True)
    license_expiry_date = models.DateField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'nurse_profiles'
    
    def __str__(self):
        return f"Nurse {self.nurse_id}: {self.first_name} {self.last_name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate employee_id if not provided
        if not self.employee_id:
            import uuid
            self.employee_id = f"NUR{str(uuid.uuid4())[:8].upper()}"
        super().save(*args, **kwargs)

class DoctorProfile(models.Model):
    doctor_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    
    # Personal Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    aadhar_number = models.CharField(max_length=12, null=True, blank=True)
    gender = models.CharField(max_length=10, choices=(
        ('MALE', 'Male'), ('FEMALE', 'Female'), ('OTHER', 'Other')
    ), null=True, blank=True)
    
    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True)
    emergency_contact_relation = models.CharField(max_length=50, blank=True)
    
    # Employment Information
    employee_id = models.CharField(max_length=50, unique=True)
    department = models.CharField(max_length=100)
    specialization = models.CharField(max_length=200)
    qualification = models.TextField()
    joining_date = models.DateField()
    shift = models.CharField(max_length=50, blank=True)  # Morning/Night/On-call
    employment_type = models.CharField(max_length=50, blank=True)  # Full-time/Part-time/Consultant
    years_of_experience = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Medical License & Consultation
    license_number = models.CharField(max_length=100, unique=True)
    consultation_fee = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    available_days = models.JSONField(default=list, blank=True)  # ["Mon", "Tue", "Wed"]
    available_time = models.JSONField(default=dict, blank=True)  # {"start": "09:00", "end": "17:00"}
    
    # Skills & Department
    skills = models.JSONField(default=list, blank=True)  # e.g., ["Cardiac Surgery", "Endoscopy"]
    assigned_ward = models.CharField(max_length=100, blank=True)
    supervisor = models.CharField(max_length=100, blank=True)  # Head of Department
    
    # Financial Information
    salary = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    
    # Additional Fields
    blood_group = models.CharField(max_length=5, choices=(
        ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-')
    ), blank=True, null=True)
    
    # Documents
    documents = models.JSONField(default=dict, blank=True, help_text="""Store all documents in one JSON field:
    {
        "medical_degree": "file_path_or_url",
        "md_ms_certificate": "file_path_or_url",
        "medical_license": "file_path_or_url",
        "id_proof": "file_path_or_url",
        "address_proof": "file_path_or_url",
        "experience_letter": "file_path_or_url",
        "specialization_certificates": ["file1.pdf", "file2.pdf"],
        "research_papers": ["paper1.pdf", "paper2.pdf"],
        "other_documents": ["file1.jpg", "file2.pdf"]
    }
    """)
    profile_picture = models.CharField(max_length=500000, blank=True, null=True)
    uploaded_documents = models.TextField(blank=True, null=True)
    
    # Licensure Information 
    state_of_licensure  = models.CharField(max_length=100, blank=True, null=True)
    license_expiry_date = models.DateField(null=True, blank=True)
 

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'doctor_profiles'
    
    def __str__(self):
        return f"Doctor {self.doctor_id}: Dr. {self.first_name} {self.last_name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate employee_id if not provided
        if not self.employee_id:
            import uuid
            self.employee_id = f"DOC{str(uuid.uuid4())[:8].upper()}"
        
        # Auto-generate license_number if not provided
        if not self.license_number:
            import uuid
            self.license_number = f"LIC{str(uuid.uuid4())[:8].upper()}"
        
        super().save(*args, **kwargs)

class AdminProfile(models.Model):
    admin_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=50, unique=True)
    role = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'admin_profiles'
    
    def __str__(self):
        return f"Admin {self.admin_id}: {self.first_name} {self.last_name}"
    
class OTPVerification(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    
    def is_expired(self):
        """Check if OTP has expired"""
        return timezone.now() > self.expires_at
    
    def save(self, *args, **kwargs):
        """Auto-set expires_at if not provided"""
        if not self.expires_at:
            # Set expiry to 5 minutes from now
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)
    
    @classmethod
    def generate_otp(cls, email):
        """Generate and save a new OTP for email"""
        # Delete any existing unverified OTPs for this email
        cls.objects.filter(email=email, is_verified=False).delete()
        
        # Generate 6-digit OTP
        otp_code = ''.join(random.choices(string.digits, k=6))
        
        # Create and return new OTP
        otp_obj = cls.objects.create(
            email=email,
            otp=otp_code,
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        return otp_obj
    
    @classmethod
    def verify_otp(cls, email, otp_code):
        """Verify OTP and return (is_valid, message)"""
        try:
            otp_obj = cls.objects.get(
                email=email,
                otp=otp_code,
                is_verified=False
            )
        except cls.DoesNotExist:
            return False, "Invalid OTP"
        
        # Check if expired
        if otp_obj.is_expired():
            otp_obj.delete()
            return False, "OTP has expired. Please request a new one"
        
        # Mark as verified
        otp_obj.is_verified = True
        otp_obj.save()
        return True, "OTP verified successfully"
    
    class Meta:
        ordering = ['-created_at']
        # 🔴 Add these for MongoDB/Djongo compatibility
        indexes = [
            models.Index(fields=['email', 'is_verified']),
            models.Index(fields=['expires_at']),
        ]