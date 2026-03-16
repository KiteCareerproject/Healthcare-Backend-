from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    QuestionCategory, 
    Question, 
    QuestionnaireAssignment, 
    AssignedQuestion
)
from patients.models import PatientMedicalRecord, PatientProfile
from accounts.models import NurseProfile

@admin.register(QuestionCategory)
class QuestionCategoryAdmin(admin.ModelAdmin):
    list_display = ['category_id', 'name', 'created_at']
    list_display_links = ['category_id', 'name']
    search_fields = ['name', 'description']
    readonly_fields = ['category_id', 'created_at']
    fieldsets = (
        ('Category Information', {
            'fields': ('category_id', 'name', 'description', 'created_at')
        }),
    )

class AssignedQuestionInline(admin.TabularInline):
    """Inline for assigned questions in assignment admin"""
    model = AssignedQuestion
    extra = 1
    fields = ['question', 'order', 'is_mandatory', 'conditional_on_question', 'conditional_answer']
    autocomplete_fields = ['question', 'conditional_on_question']

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['question_id', 'text_preview', 'question_type', 'category', 'is_active', 'default_frequency', 'created_at']
    list_display_links = ['question_id', 'text_preview']
    list_filter = ['question_type', 'is_active', 'default_frequency', 'category', 'created_at']
    search_fields = ['text', 'help_text']
    readonly_fields = ['question_id', 'created_at', 'updated_at']
    autocomplete_fields = ['category']
    fieldsets = (
        ('Basic Information', {
            'fields': ('question_id', 'text', 'question_type', 'category', 'is_active', 'created_at', 'updated_at')
        }),
        ('Question Options', {
            'fields': ('options', 'scale_min', 'scale_max'),
            'classes': ('collapse',),
            'description': 'For MULTIPLE_CHOICE: provide options list. For SCALE: set min/max values.'
        }),
        ('Additional Settings', {
            'fields': ('default_frequency', 'help_text'),
            'classes': ('collapse',),
        }),
    )
    
    def text_preview(self, obj):
        return obj.text[:75] + '...' if len(obj.text) > 75 else obj.text
    text_preview.short_description = 'Question Text'

@admin.register(QuestionnaireAssignment)
class QuestionnaireAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        'assignment_id', 
        'patient_info', 
        'frequency', 
        'start_date', 
        'end_date', 
        'status_colored', 
        'assigned_by_name', 
        'created_at'
    ]
    list_display_links = ['assignment_id', 'patient_info']
    list_filter = ['status', 'frequency', 'start_date', 'end_date', 'created_at']
    search_fields = [
        'patient__patient_id', 
        'patient__patient__first_name',  # Search through to PatientProfile
        'patient__patient__last_name'
    ]
    readonly_fields = ['assignment_id', 'created_at', 'updated_at', 'patient_details']
    autocomplete_fields = ['patient', 'assigned_by']
    inlines = [AssignedQuestionInline]
    
    fieldsets = (
        ('Assignment Information', {
            'fields': ('assignment_id', 'patient', 'frequency', 'status', 'created_at', 'updated_at')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date'),
        }),
        ('Assignment Details', {
            'fields': ('assigned_by', 'patient_details'),
        }),
    )
    
    def patient_info(self, obj):
        """
        FIXED: Safely get patient information from PatientMedicalRecord
        PatientMedicalRecord has a ForeignKey to PatientProfile
        """
        if obj.patient:
            try:
                # obj.patient is a PatientMedicalRecord
                # Access the related PatientProfile through the 'patient' field
                if hasattr(obj.patient, 'patient') and obj.patient.patient:
                    patient_profile = obj.patient.patient
                    # FIXED: Use correct admin URL pattern
                    url = reverse('admin:patients_patientprofile_change', args=[patient_profile.pk])
                    return format_html(
                        '<a href="{}">{} {} (MRN: {})</a>',
                        url,
                        patient_profile.first_name,
                        patient_profile.last_name,
                        obj.patient.patient_id
                    )
                # Fallback to just showing the medical record ID
                else:
                    return f"Patient MRN: {obj.patient.patient_id}"
            except Exception as e:
                # If anything goes wrong, show the ID and log the error
                return f"Patient ID: {obj.patient_id}"
        return '-'
    patient_info.short_description = 'Patient'
    
    def patient_details(self, obj):
        """Display detailed patient information without links"""
        if obj.patient:
            try:
                if hasattr(obj.patient, 'patient') and obj.patient.patient:
                    patient_profile = obj.patient.patient
                    medical_record = obj.patient
                    
                    # Get additional info if available
                    cancer_type = medical_record.cancer_type.name if medical_record.cancer_type else 'N/A'
                    
                    return format_html(
                        '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
                        '<strong>Patient Name:</strong> {} {}<br>'
                        '<strong>Medical Record #:</strong> {}<br>'
                        '<strong>Cancer Type:</strong> {}<br>'
                        '<strong>Cancer Stage:</strong> {}<br>'
                        '<strong>Diagnosis Date:</strong> {}<br>'
                        '<strong>Hospital:</strong> {}<br>'
                        '</div>',
                        patient_profile.first_name,
                        patient_profile.last_name,
                        medical_record.patient_id,
                        cancer_type,
                        medical_record.cancer_stage or 'N/A',
                        medical_record.diagnosis_date.strftime('%Y-%m-%d') if medical_record.diagnosis_date else 'N/A',
                        medical_record.hospital_name or 'N/A'
                    )
            except Exception as e:
                return f"Error loading patient details: {str(e)}"
        return '-'
    patient_details.short_description = 'Patient Details'
    
    def status_colored(self, obj):
        """Display status with color coding"""
        colors = {
            'ACTIVE': '#28a745',
            'PAUSED': '#ffc107',
            'COMPLETED': '#17a2b8',
            'EXPIRED': '#dc3545',
            'DRAFT': '#6c757d'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status
        )
    status_colored.short_description = 'Status'
    status_colored.admin_order_field = 'status'
    
    def assigned_by_name(self, obj):
        """Get assigner information safely"""
        if obj.assigned_by:
            try:
                # Handle different user types
                if hasattr(obj.assigned_by, 'first_name'):
                    return f"{obj.assigned_by.first_name} {obj.assigned_by.last_name}"
                elif hasattr(obj.assigned_by, 'user'):
                    return f"{obj.assigned_by.user.first_name} {obj.assigned_by.user.last_name}"
                else:
                    return str(obj.assigned_by)
            except AttributeError:
                return f"User ID: {obj.assigned_by_id}"
        return '-'
    assigned_by_name.short_description = 'Assigned By'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related(
            'patient',
            'patient__patient',  # This joins to PatientProfile
            'assigned_by'
        )
    
    actions = ['activate_assignments', 'pause_assignments', 'complete_assignments', 'extend_assignments']
    
    def activate_assignments(self, request, queryset):
        updated = queryset.update(status='ACTIVE')
        self.message_user(request, f"{updated} assignments activated successfully.")
    activate_assignments.short_description = "Activate selected assignments"
    
    def pause_assignments(self, request, queryset):
        updated = queryset.update(status='PAUSED')
        self.message_user(request, f"{updated} assignments paused successfully.")
    pause_assignments.short_description = "Pause selected assignments"
    
    def complete_assignments(self, request, queryset):
        updated = queryset.update(status='COMPLETED')
        self.message_user(request, f"{updated} assignments marked as completed.")
    complete_assignments.short_description = "Complete selected assignments"
    
    def extend_assignments(self, request, queryset):
        """Extend end date for assignments"""
        days = request.POST.get('extend_days', 30)
        try:
            from datetime import timedelta
            days = int(days)
            count = 0
            for assignment in queryset:
                if assignment.end_date:
                    assignment.end_date += timedelta(days=days)
                    assignment.save()
                    count += 1
            self.message_user(request, f"{count} assignments extended by {days} days.")
        except (ValueError, TypeError):
            self.message_user(request, "Invalid number of days. Please enter a number.", level='ERROR')
    extend_assignments.short_description = "Extend end date"

@admin.register(AssignedQuestion)
class AssignedQuestionAdmin(admin.ModelAdmin):
    list_display = ['assigned_question_id', 'assignment_info', 'question_preview', 'order', 'is_mandatory', 'created_at']
    list_display_links = ['assigned_question_id', 'question_preview']
    list_filter = ['is_mandatory', 'created_at']
    search_fields = ['question__text', 'questionnaire_assignment__assignment_id']
    readonly_fields = ['assigned_question_id', 'created_at']
    autocomplete_fields = ['questionnaire_assignment', 'question', 'conditional_on_question']
    
    fieldsets = (
        ('Assigned Question Information', {
            'fields': ('assigned_question_id', 'questionnaire_assignment', 'question', 'order', 'is_mandatory', 'created_at')
        }),
        ('Conditional Logic', {
            'fields': ('conditional_on_question', 'conditional_answer'),
            'classes': ('collapse',),
            'description': 'Set conditions for when this question should appear'
        }),
    )
    
    def assignment_info(self, obj):
        """Get assignment information with link"""
        if obj.questionnaire_assignment:
            url = reverse('admin:questionnaires_questionnaireassignment_change', 
                         args=[obj.questionnaire_assignment.pk])
            return format_html(
                '<a href="{}">Assignment #{}</a>',
                url,
                obj.questionnaire_assignment.assignment_id
            )
        return '-'
    assignment_info.short_description = 'Assignment'
    
    def question_preview(self, obj):
        """Preview question text"""
        if obj.question:
            return obj.question.text[:50] + '...' if len(obj.question.text) > 50 else obj.question.text
        return '-'
    question_preview.short_description = 'Question'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related(
            'questionnaire_assignment',
            'question',
            'conditional_on_question'
        )

# Custom filters for QuestionAdmin
class QuestionTypeListFilter(admin.SimpleListFilter):
    title = 'question type'
    parameter_name = 'question_type'
    
    def lookups(self, request, model_admin):
        return Question.QUESTION_TYPES
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(question_type=self.value())
        return queryset

# Custom filter for assignment status with date awareness
class AssignmentStatusDateFilter(admin.SimpleListFilter):
    title = 'current status'
    parameter_name = 'current_status'
    
    def lookups(self, request, model_admin):
        return [
            ('active', ' Active'),
            ('paused', ' Paused'),
            ('completed', ' Completed'),
            ('expired', ' Expired'),
            ('upcoming', ' Upcoming'),
        ]
    
    def queryset(self, request, queryset):
        from django.utils import timezone
        today = timezone.now().date()
        
        if self.value() == 'active':
            return queryset.filter(
                status='ACTIVE',
                start_date__lte=today,
                end_date__gte=today
            )
        elif self.value() == 'paused':
            return queryset.filter(status='PAUSED')
        elif self.value() == 'completed':
            return queryset.filter(status='COMPLETED')
        elif self.value() == 'expired':
            return queryset.filter(
                status='ACTIVE',
                end_date__lt=today
            )
        elif self.value() == 'upcoming':
            return queryset.filter(
                status='ACTIVE',
                start_date__gt=today
            )
        return queryset

# Add the custom filter to the admin class
QuestionnaireAssignmentAdmin.list_filter.append(AssignmentStatusDateFilter)

# Register models with custom admin sites if needed
class QuestionnairesAdminSite(admin.AdminSite):
    site_header = 'Questionnaires Administration'
    site_title = 'Questionnaires Admin'
    index_title = 'Questionnaires Management'
