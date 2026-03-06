from rest_framework import serializers
from .models import Notification, ReminderSchedule, NotificationLog

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'

class ReminderScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReminderSchedule
        fields = '__all__'

class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = '__all__'

class CreateNotificationSerializer(serializers.Serializer):
    recipient_id = serializers.IntegerField()
    notification_type = serializers.ChoiceField(choices=Notification.NOTIFICATION_TYPES)
    priority = serializers.ChoiceField(choices=Notification.PRIORITY_LEVELS, default='MEDIUM')
    title = serializers.CharField()
    message = serializers.CharField()
    related_patient_id = serializers.IntegerField(required=False)
    related_alert_id = serializers.IntegerField(required=False)