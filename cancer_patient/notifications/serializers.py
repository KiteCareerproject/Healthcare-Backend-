# from rest_framework import serializers
# from .models import Notification, ReminderSchedule, NotificationLog

# class NotificationSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Notification
#         fields = '__all__'

# class ReminderScheduleSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = ReminderSchedule
#         fields = '__all__'

# class NotificationLogSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = NotificationLog
#         fields = '__all__'

# class CreateNotificationSerializer(serializers.Serializer):
#     recipient_id = serializers.IntegerField()
#     notification_type = serializers.ChoiceField(choices=Notification.NOTIFICATION_TYPES)
#     priority = serializers.ChoiceField(choices=Notification.PRIORITY_LEVELS, default='MEDIUM')
#     title = serializers.CharField()
#     message = serializers.CharField()
#     related_patient_id = serializers.IntegerField(required=False)
#     related_alert_id = serializers.IntegerField(required=False)

# notifications/serializers.py
from rest_framework import serializers
from .models import Notification, ReminderSchedule, NotificationLog, NotificationPreference

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['notification_id', 'created_at', 'updated_at']

class ReminderScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReminderSchedule
        fields = '__all__'
        read_only_fields = ['schedule_id', 'created_at', 'updated_at']

class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = '__all__'

class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = '__all__'
        read_only_fields = ['preference_id', 'created_at', 'updated_at']

class CreateNotificationSerializer(serializers.Serializer):
    recipient_id = serializers.IntegerField()
    notification_type = serializers.ChoiceField(choices=Notification.NOTIFICATION_TYPES)
    priority = serializers.ChoiceField(choices=Notification.PRIORITY_LEVELS, default='MEDIUM')
    title = serializers.CharField(max_length=200)
    message = serializers.CharField()
    related_patient_id = serializers.IntegerField(required=False, allow_null=True)
    related_alert_id = serializers.IntegerField(required=False, allow_null=True)
    action_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    image_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    metadata = serializers.JSONField(required=False, default=dict)