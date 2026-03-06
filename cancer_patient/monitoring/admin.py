from django.contrib import admin
from .models import DailyResponse, QuestionResponse, Alert, AlertEscalation, PatientNote

class QuestionResponseInline(admin.TabularInline):
    model = QuestionResponse
    extra = 0
    fields = ('question_response_id', 'question', 'yes_no_response', 'scale_response', 'text_response')
    readonly_fields = ('question_response_id',)

@admin.register(DailyResponse)
class DailyResponseAdmin(admin.ModelAdmin):
    list_display = ('response_id', 'patient_info', 'response_date', 'is_completed', 'completed_at')
    list_filter = ('is_completed', 'response_date')
    search_fields = ('patient__patient__first_name', 'patient__patient__last_name')
    inlines = [QuestionResponseInline]
    readonly_fields = ('response_id', 'created_at')
    
    def patient_info(self, obj):
        return f"{obj.patient.patient.first_name} {obj.patient.patient.last_name} (P-{obj.patient.patient_id})"
    patient_info.short_description = 'Patient'

@admin.register(QuestionResponse)
class QuestionResponseAdmin(admin.ModelAdmin):
    list_display = ('question_response_id', 'daily_response', 'question', 'response_summary', 'responded_at')
    list_filter = ('question__question_type',)
    search_fields = ('daily_response__patient__patient__first_name',)
    
    def response_summary(self, obj):
        if obj.yes_no_response is not None:
            return "Yes" if obj.yes_no_response else "No"
        elif obj.scale_response:
            return f"Scale: {obj.scale_response}"
        elif obj.multiple_choice_response:
            return obj.multiple_choice_response
        elif obj.text_response:
            return obj.text_response[:50] + "..."
        return "-"
    response_summary.short_description = 'Response'

class AlertEscalationInline(admin.TabularInline):
    model = AlertEscalation
    extra = 0
    fields = ('escalation_id', 'escalated_by', 'escalated_to', 'reason', 'created_at')
    readonly_fields = ('escalation_id', 'created_at')

class PatientNoteInline(admin.TabularInline):
    model = PatientNote
    extra = 0
    fields = ('note_id', 'author_nurse', 'author_doctor', 'note', 'created_at')
    readonly_fields = ('note_id', 'created_at')

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('alert_id', 'patient_info', 'title', 'alert_level', 'status', 'assigned_to_nurse', 'created_at')
    list_filter = ('alert_level', 'status', 'created_at')
    search_fields = ('patient__patient__first_name', 'patient__patient__last_name', 'title')
    inlines = [AlertEscalationInline, PatientNoteInline]
    readonly_fields = ('alert_id', 'created_at')
    
    def patient_info(self, obj):
        return f"{obj.patient.patient.first_name} {obj.patient.patient.last_name} (P-{obj.patient.patient_id})"
    patient_info.short_description = 'Patient'

@admin.register(AlertEscalation)
class AlertEscalationAdmin(admin.ModelAdmin):
    list_display = ('escalation_id', 'alert', 'escalated_by', 'escalated_to', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('alert__title',)

@admin.register(PatientNote)
class PatientNoteAdmin(admin.ModelAdmin):
    list_display = ('note_id', 'patient_info', 'author_name', 'alert', 'is_private', 'created_at')
    list_filter = ('is_private', 'created_at')
    search_fields = ('patient__patient__first_name', 'note')
    
    def patient_info(self, obj):
        return f"{obj.patient.patient.first_name} {obj.patient.patient.last_name} (P-{obj.patient.patient_id})"
    patient_info.short_description = 'Patient'
    
    def author_name(self, obj):
        if obj.author_nurse:
            return f"Nurse: {obj.author_nurse.first_name} {obj.author_nurse.last_name}"
        elif obj.author_doctor:
            return f"Dr. {obj.author_doctor.first_name} {obj.author_doctor.last_name}"
        return "-"
    author_name.short_description = 'Author'

