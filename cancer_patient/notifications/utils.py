# notifications/utils.py
import json
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
from .models import Notification, NotificationDelivery, NotificationPreference
import logging

logger = logging.getLogger(__name__)

def send_realtime_notification(notification_id):
    """
    Send notification via WebSocket and store delivery record
    """
    try:
        from .models import Notification
        
        notification = Notification.objects.select_related(
            'recipient', 'related_patient'
        ).get(notification_id=notification_id)
        
        # Check if user wants WebSocket notifications
        try:
            prefs = NotificationPreference.objects.get(user=notification.recipient)
            if not prefs.enable_websocket:
                logger.info(f"User {notification.recipient.user_id} has WebSocket disabled")
                return False
        except NotificationPreference.DoesNotExist:
            pass  # Default to enabled
        
        channel_layer = get_channel_layer()
        room_group_name = f'notifications_{notification.recipient.user_id}'
        
        # Prepare notification data
        notification_data = {
            'id': notification.notification_id,
            'type': notification.notification_type,
            'priority': notification.priority,
            'title': notification.title,
            'message': notification.message,
            'created_at': str(notification.created_at),
            'is_read': notification.is_read,
            'action_url': notification.action_url,
            'image_url': notification.image_url,
            'metadata': notification.metadata
        }
        
        if notification.related_patient:
            notification_data['patient_id'] = notification.related_patient.patient_id
            notification_data['patient_name'] = str(notification.related_patient.patient)
        
        # Create delivery record
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            delivery_method='WEBSOCKET',
            channel_name=room_group_name,
            status='SENT',
            sent_at=timezone.now()
        )
        
        # Send to WebSocket group
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'send_notification',
                'notification': notification_data,
                'delivery_id': delivery.delivery_id
            }
        )
        
        # Update notification
        notification.delivered_via_websocket = True
        notification.websocket_delivered_at = timezone.now()
        notification.is_sent = True
        notification.sent_at = timezone.now()
        notification.save()
        
        logger.info(f"Realtime notification {notification_id} sent to user {notification.recipient.user_id}")
        return True
        
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
        return False
    except Exception as e:
        logger.error(f"Failed to send realtime notification {notification_id}: {str(e)}")
        return False

def send_bulk_realtime_notifications(notification_ids):
    """
    Send multiple notifications via WebSocket
    """
    success_count = 0
    for notification_id in notification_ids:
        if send_realtime_notification(notification_id):
            success_count += 1
    
    return success_count

def create_and_send_notification(**kwargs):
    """
    Create notification and send via WebSocket
    """
    try:
        # Create notification
        notification = Notification.objects.create(**kwargs)
        
        # Send via WebSocket
        send_realtime_notification(notification.notification_id)
        
        return notification
    except Exception as e:
        logger.error(f"Failed to create and send notification: {e}")
        return None