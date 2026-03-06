from django.contrib import admin
from django.utils import timezone
from .models import Notification, ReminderSchedule, NotificationLog
from accounts.models import User
from patients.models import PatientMedicalRecord

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'notification_id', 
        'recipient_info', 
        'notification_type', 
        'priority', 
        'title_preview', 
        'is_read', 
        'is_sent',
        'created_at'
    ]
    list_display_links = ['notification_id', 'title_preview']
    list_filter = [
        'notification_type', 
        'priority', 
        'is_read', 
        'is_sent', 
        'created_at',
        'sent_at'
    ]
    search_fields = [
        'title', 
        'message', 
        'recipient__username', 
        'recipient__email'
    ]
    readonly_fields = [
        'notification_id', 
        'created_at', 
        'sent_at', 
        'read_at'
    ]
    autocomplete_fields = ['recipient', 'related_patient', 'related_alert']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'notification_id', 
                'recipient', 
                'notification_type', 
                'priority',
                'created_at'
            )
        }),
        ('Content', {
            'fields': ('title', 'message'),
            'classes': ('wide',)
        }),
        ('Related Data', {
            'fields': ('related_patient', 'related_alert'),
            'classes': ('collapse',),
            'description': 'Link this notification to a patient or alert'
        }),
        ('Delivery Status', {
            'fields': ('is_sent', 'sent_at', 'is_read', 'read_at'),
            'classes': ('collapse',),
        }),
    )
    
    def recipient_info(self, obj):
        if obj.recipient:
            return f"{obj.recipient.username} ({obj.recipient.user_type})"
        return '-'
    recipient_info.short_description = 'Recipient'
    recipient_info.admin_order_field = 'recipient__username'
    
    def title_preview(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_preview.short_description = 'Title'
    
    actions = ['mark_as_sent', 'mark_as_read', 'resend_notifications']
    
    def mark_as_sent(self, request, queryset):
        queryset.update(is_sent=True, sent_at=timezone.now())
        self.message_user(request, f"{queryset.count()} notifications marked as sent.")
    mark_as_sent.short_description = "Mark selected as sent"
    
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True, read_at=timezone.now())
        self.message_user(request, f"{queryset.count()} notifications marked as read.")
    mark_as_read.short_description = "Mark selected as read"
    
    def resend_notifications(self, request, queryset):
        for notification in queryset:
            notification.is_sent = False
            notification.sent_at = None
            notification.save()
        self.message_user(request, f"{queryset.count()} notifications queued for resend.")
    resend_notifications.short_description = "Queue for resend"

class ReminderScheduleInline(admin.TabularInline):
    """Inline for reminder schedules in patient admin"""
    model = ReminderSchedule
    extra = 0
    fields = [
        'schedule_id', 
        'reminder_type', 
        'medication', 
        'time', 
        'days_of_week', 
        'is_active'
    ]
    readonly_fields = ['schedule_id']
    autocomplete_fields = ['medication']
    can_delete = True

@admin.register(ReminderSchedule)
class ReminderScheduleAdmin(admin.ModelAdmin):
    list_display = [
        'schedule_id',
        'patient_info',
        'reminder_type',
        'medication_name',
        'time',
        'days_display',
        'is_recurring',
        'is_active',
        'start_date',
        'end_date'
    ]
    list_display_links = ['schedule_id', 'patient_info']
    list_filter = [
        'reminder_type', 
        'is_recurring', 
        'is_active', 
        'days_of_week',
        'start_date',
        'end_date'
    ]
    search_fields = [
        'patient__first_name', 
        'patient__last_name', 
        'patient__patient_id'
    ]
    readonly_fields = [
        'schedule_id', 
        'created_at', 
        'updated_at', 
        'last_triggered'
    ]
    autocomplete_fields = ['patient', 'medication']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'schedule_id', 
                'patient', 
                'reminder_type',
                'medication',
                'created_at',
                'updated_at'
            )
        }),
        ('Schedule Settings', {
            'fields': ('time', 'days_of_week', 'is_recurring'),
            'description': 'Set the time and days for reminders'
        }),
        ('Validity Period', {
            'fields': ('start_date', 'end_date', 'is_active'),
        }),
        ('Status', {
            'fields': ('last_triggered',),
            'classes': ('collapse',),
        }),
    )
    
    def patient_info(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name} (ID: {obj.patient.patient_id})"
    patient_info.short_description = 'Patient'
    
    def medication_name(self, obj):
        if obj.medication:
            return obj.medication.medication_name
        return '-'
    medication_name.short_description = 'Medication'
    
    def days_display(self, obj):
        days = obj.days_of_week
        if not days:
            return 'Every day'
        day_map = {
            0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu',
            4: 'Fri', 5: 'Sat', 6: 'Sun'
        }
        return ', '.join([day_map.get(d, str(d)) for d in days])
    days_display.short_description = 'Days'
    
    actions = ['activate_schedules', 'deactivate_schedules']
    
    def activate_schedules(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} schedules activated.")
    activate_schedules.short_description = "Activate selected schedules"
    
    def deactivate_schedules(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} schedules deactivated.")
    deactivate_schedules.short_description = "Deactivate selected schedules"

@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = [
        'log_id',
        'notification_info',
        'delivery_method',
        'status',
        'retry_count',
        'sent_at',
        'delivered_at'
    ]
    list_display_links = ['log_id', 'notification_info']
    list_filter = [
        'delivery_method', 
        'status', 
        'sent_at', 
        'delivered_at',
        'retry_count'
    ]
    search_fields = [
        'notification__title', 
        'notification__message',
        'error_message'
    ]
    readonly_fields = [
        'log_id', 
        'notification', 
        'delivery_method', 
        'status',
        'error_message', 
        'retry_count', 
        'sent_at', 
        'delivered_at'
    ]
    
    fieldsets = (
        ('Log Information', {
            'fields': ('log_id', 'notification', 'delivery_method')
        }),
        ('Delivery Status', {
            'fields': ('status', 'retry_count', 'sent_at', 'delivered_at'),
        }),
        ('Error Details', {
            'fields': ('error_message',),
            'classes': ('collapse',),
            'description': 'Error message if delivery failed'
        }),
    )
    
    def notification_info(self, obj):
        return f"#{obj.notification.notification_id}: {obj.notification.title[:30]}"
    notification_info.short_description = 'Notification'
    
    def has_add_permission(self, request):
        """Prevent manual addition of logs"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of logs"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion of logs"""
        return True

# Custom filters
class NotificationPriorityFilter(admin.SimpleListFilter):
    title = 'priority level'
    parameter_name = 'priority'
    
    def lookups(self, request, model_admin):
        return Notification.PRIORITY_LEVELS
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(priority=self.value())
        return queryset

class ReminderTypeFilter(admin.SimpleListFilter):
    title = 'reminder type'
    parameter_name = 'reminder_type'
    
    def lookups(self, request, model_admin):
        return ReminderSchedule.REMINDER_TYPES
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(reminder_type=self.value())
        return queryset

# Register custom filters
NotificationAdmin.list_filter.append(NotificationPriorityFilter)
ReminderScheduleAdmin.list_filter.append(ReminderTypeFilter)

# You can also create a custom admin site if needed
class NotificationsAdminSite(admin.AdminSite):
    site_header = 'Notifications Administration'
    site_title = 'Notifications Admin'
    index_title = 'Notifications Management'

# Uncomment if you want separate admin site
# notifications_admin = NotificationsAdminSite(name='notifications_admin')