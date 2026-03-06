# from django.contrib import admin
# from django.contrib.auth.admin import UserAdmin
# from .models import User, PatientProfile, NurseProfile, DoctorProfile, AdminProfile

# @admin.register(User)
# class CustomUserAdmin(UserAdmin):
#     list_display = ('user_id', 'username', 'email', 'user_type', 'is_verified', 'created_at')
#     list_filter = ('user_type', 'is_verified', 'is_active')
#     search_fields = ('username', 'email', 'phone_number')
#     ordering = ('-created_at',)

# @admin.register(PatientProfile)
# class PatientProfileAdmin(admin.ModelAdmin):
#     list_display = ('patient_id', 'first_name', 'last_name', 'aadhar_number', 'phone_number', 'created_at')
#     search_fields = ('first_name', 'last_name', 'aadhar_number', 'user__phone_number')
#     list_filter = ('gender',)
    
#     def phone_number(self, obj):
#         return obj.user.phone_number
#     phone_number.short_description = 'Phone Number'

# @admin.register(NurseProfile)
# class NurseProfileAdmin(admin.ModelAdmin):
#     list_display = ('nurse_id', 'first_name', 'last_name', 'employee_id', 'department', 'joining_date')
#     search_fields = ('first_name', 'last_name', 'employee_id')
#     list_filter = ('department',)

# @admin.register(DoctorProfile)
# class DoctorProfileAdmin(admin.ModelAdmin):
#     list_display = ('doctor_id', 'first_name', 'last_name', 'employee_id', 'specialization', 'department')
#     search_fields = ('first_name', 'last_name', 'employee_id', 'license_number')
#     list_filter = ('specialization', 'department')

# @admin.register(AdminProfile)
# class AdminProfileAdmin(admin.ModelAdmin):
#     list_display = ('admin_id', 'first_name', 'last_name', 'employee_id', 'role')
#     search_fields = ('first_name', 'last_name', 'employee_id')

# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, PatientProfile, NurseProfile, DoctorProfile, AdminProfile

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('user_id', 'username', 'email', 'phone_number', 'user_type', 'is_verified', 'created_at')
    list_filter = ('user_type', 'is_verified', 'is_active')
    search_fields = ('username', 'email', 'phone_number')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone_number')}),
        ('Permissions', {'fields': ('user_type', 'is_verified', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
    )
    readonly_fields = ('user_id', 'created_at', 'updated_at')

@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('patient_id', 'first_name', 'last_name', 'aadhar_number', 'get_phone', 'gender', 'created_at')
    list_display_links = ('patient_id', 'first_name', 'last_name')
    search_fields = ('first_name', 'last_name', 'aadhar_number', 'user__phone_number')
    list_filter = ('gender', 'created_at')
    readonly_fields = ('patient_id', 'created_at', 'updated_at')
    raw_id_fields = ['user']
    
    fieldsets = (
        ('Patient Information', {
            'fields': ('patient_id', 'user', 'first_name', 'last_name')
        }),
        ('Personal Details', {
            'fields': ('aadhar_number', 'date_of_birth', 'gender', 'address')
        }),
        ('Emergency Contact', {
            'fields': ('emergency_contact_name', 'emergency_contact_phone'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_phone(self, obj):
        return obj.user.phone_number
    get_phone.short_description = 'Phone Number'

@admin.register(NurseProfile)
class NurseProfileAdmin(admin.ModelAdmin):
    # Remove 'experience_years' from list_display
    list_display = ('nurse_id', 'first_name', 'last_name', 'qualification', 'department', 'get_phone')
    list_display_links = ('nurse_id', 'first_name', 'last_name')
    search_fields = ('first_name', 'last_name', 'qualification', 'department', 'user__username')
    list_filter = ('department', 'qualification')
    readonly_fields = ('nurse_id', 'created_at', 'updated_at')
    raw_id_fields = ['user']
    
    fieldsets = (
        ('Nurse Information', {
            'fields': ('nurse_id', 'user', 'first_name', 'last_name')
        }),
        ('Professional Details', {
            'fields': ('qualification', 'department')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_phone(self, obj):
        return obj.user.phone_number
    get_phone.short_description = 'Phone Number'

@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    # Remove 'consultation_fee' from list_display
    list_display = ('doctor_id', 'first_name', 'last_name', 'specialization', 'license_number', 'get_phone')
    list_display_links = ('doctor_id', 'first_name', 'last_name')
    search_fields = ('first_name', 'last_name', 'specialization', 'license_number', 'user__username')
    list_filter = ('specialization',)
    readonly_fields = ('doctor_id', 'created_at', 'updated_at')
    raw_id_fields = ['user']
    
    fieldsets = (
        ('Doctor Information', {
            'fields': ('doctor_id', 'user', 'first_name', 'last_name')
        }),
        ('Professional Details', {
            'fields': ('specialization', 'license_number', 'available_days')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_phone(self, obj):
        return obj.user.phone_number
    get_phone.short_description = 'Phone Number'

@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ('admin_id', 'first_name', 'last_name', 'get_username', 'get_email')
    list_display_links = ('admin_id', 'first_name', 'last_name')
    search_fields = ('first_name', 'last_name', 'user__username', 'user__email')
    readonly_fields = ('admin_id', 'created_at', 'updated_at')
    raw_id_fields = ['user']
    
    fieldsets = (
        ('Admin Information', {
            'fields': ('admin_id', 'user', 'first_name', 'last_name')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Username'
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'