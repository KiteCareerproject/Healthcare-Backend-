from django.contrib import admin
from .models import (
    QuestionCategory, 
    Question, 
    QuestionnaireAssignment, 
    AssignedQuestion
)
from patients.models import PatientMedicalRecord
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
    list_display = ['assignment_id', 'patient_info', 'frequency', 'start_date', 'end_date', 'status', 'assigned_by_name', 'created_at']
    list_display_links = ['assignment_id', 'patient_info']
    list_filter = ['status', 'frequency', 'start_date', 'end_date', 'created_at']
    search_fields = ['patient__patient_id', 'patient__first_name', 'patient__last_name']
    readonly_fields = ['assignment_id', 'created_at', 'updated_at']
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
            'fields': ('assigned_by',),
        }),
    )
    
    def patient_info(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name} (ID: {obj.patient.patient_id})"
    patient_info.short_description = 'Patient'
    
    def assigned_by_name(self, obj):
        if obj.assigned_by:
            return f"{obj.assigned_by.first_name} {obj.assigned_by.last_name}"
        return '-'
    assigned_by_name.short_description = 'Assigned By'
    
    actions = ['activate_assignments', 'pause_assignments', 'complete_assignments']
    
    def activate_assignments(self, request, queryset):
        queryset.update(status='ACTIVE')
        self.message_user(request, f"{queryset.count()} assignments activated successfully.")
    activate_assignments.short_description = "Activate selected assignments"
    
    def pause_assignments(self, request, queryset):
        queryset.update(status='PAUSED')
        self.message_user(request, f"{queryset.count()} assignments paused successfully.")
    pause_assignments.short_description = "Pause selected assignments"
    
    def complete_assignments(self, request, queryset):
        queryset.update(status='COMPLETED')
        self.message_user(request, f"{queryset.count()} assignments marked as completed.")
    complete_assignments.short_description = "Complete selected assignments"

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
        return f"Assignment #{obj.questionnaire_assignment.assignment_id}"
    assignment_info.short_description = 'Assignment'
    
    def question_preview(self, obj):
        return obj.question.text[:50] + '...' if len(obj.question.text) > 50 else obj.question.text
    question_preview.short_description = 'Question'

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

# Register models with custom admin sites if needed
class QuestionnairesAdminSite(admin.AdminSite):
    site_header = 'Questionnaires Administration'
    site_title = 'Questionnaires Admin'
    index_title = 'Questionnaires Management'

# You can uncomment this if you want a separate admin site for questionnaires
# questionnaires_admin = QuestionnairesAdminSite(name='questionnaires_admin')

# If you want to register with the main admin site, just use the @admin.register decorators above