from django.contrib import admin
from django.utils import timezone
from django.urls import reverse
from django.utils.html import format_html
from .models import PatientAssignment, DashboardPreference, AnalyticsReport
from accounts.models import User, NurseProfile, DoctorProfile, AdminProfile
from patients.models import PatientMedicalRecord

@admin.register(PatientAssignment)
class PatientAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        'assignment_id',
        'patient_info',
        'nurse_info',
        'doctor_info',
        'assigned_date',
        'is_active',
        'assigned_by_info',
        'view_patient_link'
    ]
    list_display_links = ['assignment_id', 'patient_info']
    list_filter = [
        'is_active',
        'assigned_date',
        'nurse__department',
        'doctor__specialization'
    ]
    search_fields = [
        'patient__first_name',
        'patient__last_name',
        'patient__patient_id',
        'nurse__first_name',
        'nurse__last_name',
        'doctor__first_name',
        'doctor__last_name'
    ]
    readonly_fields = [
        'assignment_id',
        'assigned_date',
        'assignment_details'
    ]
    autocomplete_fields = ['nurse', 'doctor', 'patient', 'assigned_by']
    
    fieldsets = (
        ('Assignment Information', {
            'fields': (
                'assignment_id',
                'assigned_date',
                'is_active',
                'assignment_details'
            )
        }),
        ('Healthcare Team', {
            'fields': (
                'nurse',
                'doctor',
                'assigned_by'
            ),
            'description': 'Select the nurse and doctor assigned to this patient'
        }),
        ('Patient', {
            'fields': ('patient',),
        }),
    )
    
    def patient_info(self, obj):
        if obj.patient:
            return f"{obj.patient.first_name} {obj.patient.last_name} (ID: {obj.patient.patient_id})"
        return '-'
    patient_info.short_description = 'Patient'
    patient_info.admin_order_field = 'patient__first_name'
    
    def nurse_info(self, obj):
        if obj.nurse:
            return f"{obj.nurse.first_name} {obj.nurse.last_name}"
        return '-'
    nurse_info.short_description = 'Nurse'
    nurse_info.admin_order_field = 'nurse__first_name'
    
    def doctor_info(self, obj):
        if obj.doctor:
            return f"Dr. {obj.doctor.first_name} {obj.doctor.last_name}"
        return '-'
    doctor_info.short_description = 'Doctor'
    doctor_info.admin_order_field = 'doctor__first_name'
    
    def assigned_by_info(self, obj):
        if obj.assigned_by:
            return f"{obj.assigned_by.first_name} {obj.assigned_by.last_name}"
        return '-'
    assigned_by_info.short_description = 'Assigned By'
    
    def assignment_details(self, obj):
        return format_html(
            '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
            '<strong>Assignment ID:</strong> {}<br>'
            '<strong>Assigned Date:</strong> {}<br>'
            '<strong>Status:</strong> {}<br>'
            '<strong>Duration:</strong> {} days'
            '</div>',
            obj.assignment_id,
            obj.assigned_date.strftime('%Y-%m-%d'),
            'Active' if obj.is_active else 'Inactive',
            (timezone.now().date() - obj.assigned_date).days
        )
    assignment_details.short_description = 'Assignment Details'
    
    def view_patient_link(self, obj):
        if obj.patient:
            url = reverse('admin:patients_patientmedicalrecord_change', args=[obj.patient.medical_record_id])
            return format_html('<a href="{}">View Patient</a>', url)
        return '-'
    view_patient_link.short_description = 'Patient Link'
    
    actions = ['activate_assignments', 'deactivate_assignments']
    
    def activate_assignments(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} assignments activated.")
    activate_assignments.short_description = "Activate selected assignments"
    
    def deactivate_assignments(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} assignments deactivated.")
    deactivate_assignments.short_description = "Deactivate selected assignments"

@admin.register(DashboardPreference)
class DashboardPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'preference_id',
        'user_info',
        'dashboard_type',
        'refresh_interval',
        'widget_count',
        'last_updated',
        'created_at'
    ]
    list_display_links = ['preference_id', 'user_info']
    list_filter = [
        'dashboard_type',
        'refresh_interval',
        'created_at',
        'updated_at'
    ]
    search_fields = [
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name'
    ]
    readonly_fields = [
        'preference_id',
        'created_at',
        'updated_at',
        'preview_config'
    ]
    autocomplete_fields = ['user']
    
    fieldsets = (
        ('Preference Information', {
            'fields': (
                'preference_id',
                'user',
                'dashboard_type',
                'refresh_interval',
                'created_at',
                'updated_at'
            )
        }),
        ('Dashboard Configuration', {
            'fields': (
                'layout_config',
                'widget_visibility',
            ),
            'classes': ('wide',),
            'description': 'JSON configurations for dashboard layout and widgets'
        }),
        ('Preview', {
            'fields': ('preview_config',),
            'classes': ('collapse',),
        }),
    )
    
    def user_info(self, obj):
        if obj.user:
            return f"{obj.user.username} ({obj.user.user_type})"
        return '-'
    user_info.short_description = 'User'
    user_info.admin_order_field = 'user__username'
    
    def widget_count(self, obj):
        if obj.widget_visibility:
            return len(obj.widget_visibility)
        return 0
    widget_count.short_description = 'Widgets'
    
    def last_updated(self, obj):
        return obj.updated_at.strftime('%Y-%m-%d %H:%M')
    last_updated.short_description = 'Last Updated'
    
    def preview_config(self, obj):
        import json
        layout = json.dumps(obj.layout_config, indent=2) if obj.layout_config else '{}'
        widgets = json.dumps(obj.widget_visibility, indent=2) if obj.widget_visibility else '{}'
        
        return format_html(
            '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
            '<h4>Layout Configuration:</h4>'
            '<pre style="background: #e9ecef; padding: 10px;">{}</pre>'
            '<h4>Widget Visibility:</h4>'
            '<pre style="background: #e9ecef; padding: 10px;">{}</pre>'
            '</div>',
            layout, widgets
        )
    preview_config.short_description = 'Configuration Preview'
    
    actions = ['reset_to_default', 'set_refresh_interval']
    
    def reset_to_default(self, request, queryset):
        for pref in queryset:
            pref.layout_config = {}
            pref.widget_visibility = {}
            pref.save()
        self.message_user(request, f"{queryset.count()} preferences reset to default.")
    reset_to_default.short_description = "Reset to default configuration"
    
    def set_refresh_interval(self, request, queryset):
        interval = request.POST.get('refresh_interval', 300)
        queryset.update(refresh_interval=int(interval))
        self.message_user(request, f"{queryset.count()} preferences updated with refresh interval {interval}s.")
    set_refresh_interval.short_description = "Set refresh interval"

@admin.register(AnalyticsReport)
class AnalyticsReportAdmin(admin.ModelAdmin):
    list_display = [
        'report_id',
        'report_type',
        'generated_by_info',
        'date_range',
        'data_summary',
        'file_link',
        'generated_at'
    ]
    list_display_links = ['report_id', 'report_type']
    list_filter = [
        'report_type',
        'generated_at',
        'date_range_start',
        'date_range_end'
    ]
    search_fields = [
        'generated_by__first_name',
        'generated_by__last_name',
        'parameters',
        'data'
    ]
    readonly_fields = [
        'report_id',
        'generated_at',
        'report_preview',
        'parameters_display',
        'data_display'
    ]
    autocomplete_fields = ['generated_by']
    
    fieldsets = (
        ('Report Information', {
            'fields': (
                'report_id',
                'report_type',
                'generated_by',
                'generated_at'
            )
        }),
        ('Date Range', {
            'fields': (
                'date_range_start',
                'date_range_end'
            )
        }),
        ('Parameters', {
            'fields': ('parameters_display',),
            'classes': ('collapse',),
        }),
        ('Report Data', {
            'fields': ('data_display', 'report_preview'),
        }),
        ('File', {
            'fields': ('file',),
            'classes': ('collapse',),
        }),
    )
    
    def generated_by_info(self, obj):
        if obj.generated_by:
            return f"{obj.generated_by.first_name} {obj.generated_by.last_name}"
        return '-'
    generated_by_info.short_description = 'Generated By'
    
    def date_range(self, obj):
        return f"{obj.date_range_start} to {obj.date_range_end}"
    date_range.short_description = 'Date Range'
    
    def data_summary(self, obj):
        if not obj.data:
            return '-'
        
        if obj.report_type == 'COMPLETION_RATE':
            rate = obj.data.get('completion_rate', 0)
            return f"Rate: {rate:.1f}%"
        elif obj.report_type == 'ALERT_SUMMARY':
            total = obj.data.get('total_alerts', 0)
            return f"Total Alerts: {total}"
        return 'Data available'
    data_summary.short_description = 'Summary'
    
    def file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">Download</a>', obj.file)
        return '-'
    file_link.short_description = 'File'
    
    def parameters_display(self, obj):
        import json
        return format_html(
            '<pre style="background: #f8f9fa; padding: 10px;">{}</pre>',
            json.dumps(obj.parameters, indent=2)
        )
    parameters_display.short_description = 'Parameters'
    
    def data_display(self, obj):
        import json
        return format_html(
            '<pre style="background: #f8f9fa; padding: 10px;">{}</pre>',
            json.dumps(obj.data, indent=2)
        )
    data_display.short_description = 'Raw Data'
    
    def report_preview(self, obj):
        if not obj.data:
            return '-'
        
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
        
        if obj.report_type == 'COMPLETION_RATE':
            rate = obj.data.get('completion_rate', 0)
            total = obj.data.get('total_responses', 0)
            completed = obj.data.get('completed_responses', 0)
            
            html += f'''
            <h3>Completion Rate Report</h3>
            <p><strong>Total Responses:</strong> {total}</p>
            <p><strong>Completed:</strong> {completed}</p>
            <p><strong>Completion Rate:</strong> {rate:.1f}%</p>
            <div style="background: #e9ecef; height: 20px; width: 100%; border-radius: 10px;">
                <div style="background: #28a745; height: 20px; width: {rate}%; border-radius: 10px;"></div>
            </div>
            '''
        
        elif obj.report_type == 'ALERT_SUMMARY':
            total = obj.data.get('total_alerts', 0)
            by_level = obj.data.get('by_level', [])
            by_status = obj.data.get('by_status', [])
            
            html += f'<h3>Alert Summary Report</h3>'
            html += f'<p><strong>Total Alerts:</strong> {total}</p>'
            
            if by_level:
                html += '<h4>By Alert Level:</h4><ul>'
                for item in by_level:
                    html += f'<li>{item["alert_level"]}: {item["count"]}</li>'
                html += '</ul>'
            
            if by_status:
                html += '<h4>By Status:</h4><ul>'
                for item in by_status:
                    html += f'<li>{item["status"]}: {item["count"]}</li>'
                html += '</ul>'
        
        html += '</div>'
        return format_html(html)
    report_preview.short_description = 'Report Preview'
    
    def has_add_permission(self, request):
        """Reports are generated through API, not manually"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of reports"""
        return False

# Custom filters
class AssignmentStatusFilter(admin.SimpleListFilter):
    title = 'assignment status'
    parameter_name = 'assignment_status'
    
    def lookups(self, request, model_admin):
        return [
            ('active', 'Active'),
            ('inactive', 'Inactive'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(is_active=True)
        if self.value() == 'inactive':
            return queryset.filter(is_active=False)
        return queryset

class ReportTypeFilter(admin.SimpleListFilter):
    title = 'report type'
    parameter_name = 'report_type'
    
    def lookups(self, request, model_admin):
        return AnalyticsReport.REPORT_TYPES
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(report_type=self.value())
        return queryset

# Register custom filters
PatientAssignmentAdmin.list_filter.append(AssignmentStatusFilter)
AnalyticsReportAdmin.list_filter.append(ReportTypeFilter)

# Inline for assignments in patient admin
class PatientAssignmentInline(admin.TabularInline):
    model = PatientAssignment
    extra = 0
    fields = ['assignment_id', 'nurse', 'doctor', 'assigned_date', 'is_active']
    readonly_fields = ['assignment_id', 'assigned_date']
    can_delete = True
    show_change_link = True

# You can add this inline to your PatientMedicalRecordAdmin in patients app