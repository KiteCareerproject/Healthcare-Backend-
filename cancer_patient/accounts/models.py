from django.contrib.auth.models import AbstractUser
from djongo import models
from django.utils import timezone
import jwt
from django.conf import settings
import logging

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
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
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
    patient_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=(
        ('MALE', 'Male'), ('FEMALE', 'Female'), ('OTHER', 'Other')
    ))
    address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True)
    emergency_contact_relation = models.CharField(max_length=50, blank=True)
    aadhar_number = models.CharField(max_length=12, unique=True)
    profile_picture = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'patient_profiles'
    
    def __str__(self):
        return f"Patient {self.patient_id}: {self.first_name} {self.last_name}"

class NurseProfile(models.Model):
    nurse_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='nurse_profile')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=50, unique=True)
    department = models.CharField(max_length=100)
    qualification = models.TextField(blank=True)
    joining_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'nurse_profiles'
    
    def __str__(self):
        return f"Nurse {self.nurse_id}: {self.first_name} {self.last_name}"

class DoctorProfile(models.Model):
    doctor_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=50, unique=True)
    department = models.CharField(max_length=100)
    specialization = models.CharField(max_length=200)
    qualification = models.TextField()
    joining_date = models.DateField()
    license_number = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'doctor_profiles'
    
    def __str__(self):
        return f"Doctor {self.doctor_id}: Dr. {self.first_name} {self.last_name}"

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