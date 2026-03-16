# notifications/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from .models import Notification, NotificationDelivery, NotificationPreference
from accounts.models import User
import logging

logger = logging.getLogger(__name__)

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        
        if self.user.is_anonymous:
            logger.warning("Anonymous user tried to connect to notification websocket")
            await self.close()
        else:
            self.room_group_name = f'notifications_{self.user.user_id}'
            
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            # Send connection confirmation
            await self.send(json.dumps({
                'type': 'connection_established',
                'message': 'Connected to notification server',
                'user_id': self.user.user_id,
                'timestamp': str(timezone.now())
            }))
            
            # Send unread count
            await self.send_unread_count()
            
            # Send user preferences
            await self.send_user_preferences()
            
            logger.info(f"WebSocket connected for user {self.user.user_id}")
    
    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            logger.info(f"WebSocket disconnected for user {self.user.user_id if hasattr(self, 'user') else 'unknown'}")
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'mark_read':
                await self.handle_mark_read(data)
            elif message_type == 'mark_all_read':
                await self.handle_mark_all_read()
            elif message_type == 'get_notifications':
                await self.send_paginated_notifications(data)
            elif message_type == 'delete_notification':
                await self.handle_delete_notification(data)
            elif message_type == 'update_preferences':
                await self.handle_update_preferences(data)
            elif message_type == 'confirm_delivery':
                await self.handle_delivery_confirmation(data)
            elif message_type == 'ping':
                await self.send(json.dumps({'type': 'pong', 'timestamp': str(timezone.now())}))
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error in receive: {str(e)}")
    
    async def send_notification(self, event):
        """Send notification to client"""
        notification = event['notification']
        
        # Send to WebSocket
        await self.send(json.dumps({
            'type': 'new_notification',
            'notification': notification,
            'timestamp': str(timezone.now())
        }))
        
        # Update delivery status
        await self.update_delivery_status(notification['id'], 'DELIVERED')
    
    async def notification_update(self, event):
        """Send notification update to client"""
        await self.send(json.dumps({
            'type': 'notification_update',
            'update_type': event['update_type'],
            'notification': event['notification'],
            'timestamp': str(timezone.now())
        }))
    
    async def handle_mark_read(self, data):
        notification_id = data.get('notification_id')
        if notification_id:
            success = await self.mark_notification_read(notification_id)
            if success:
                await self.send(json.dumps({
                    'type': 'mark_read_success',
                    'notification_id': notification_id
                }))
                await self.send_unread_count()
    
    async def handle_mark_all_read(self):
        count = await self.mark_all_notifications_read()
        await self.send(json.dumps({
            'type': 'mark_all_read_success',
            'count': count
        }))
        await self.send_unread_count()
    
    async def handle_delete_notification(self, data):
        notification_id = data.get('notification_id')
        if notification_id:
            success = await self.delete_notification(notification_id)
            if success:
                await self.send(json.dumps({
                    'type': 'delete_success',
                    'notification_id': notification_id
                }))
    
    async def handle_update_preferences(self, data):
        preferences = data.get('preferences', {})
        success = await self.update_user_preferences(preferences)
        if success:
            await self.send(json.dumps({
                'type': 'preferences_updated',
                'preferences': preferences
            }))
    
    async def handle_delivery_confirmation(self, data):
        notification_id = data.get('notification_id')
        if notification_id:
            await self.confirm_delivery(notification_id)
    
    async def send_unread_count(self):
        count = await self.get_unread_count()
        await self.send(json.dumps({
            'type': 'unread_count',
            'count': count
        }))
    
    async def send_user_preferences(self):
        preferences = await self.get_user_preferences()
        await self.send(json.dumps({
            'type': 'user_preferences',
            'preferences': preferences
        }))
    
    async def send_paginated_notifications(self, data):
        page = data.get('page', 1)
        page_size = data.get('page_size', 20)
        filter_type = data.get('filter', 'all')  # all, unread, read
        
        result = await self.get_paginated_notifications(page, page_size, filter_type)
        await self.send(json.dumps({
            'type': 'notification_list',
            'data': result['notifications'],
            'pagination': result['pagination']
        }))
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        try:
            notification = Notification.objects.get(
                notification_id=notification_id,
                recipient=self.user
            )
            if not notification.is_read:
                notification.is_read = True
                notification.read_at = timezone.now()
                notification.save()
                
                # Create delivery record
                NotificationDelivery.objects.create(
                    notification=notification,
                    delivery_method='WEBSOCKET',
                    status='DELIVERED',
                    delivered_at=timezone.now(),
                    confirmed_at=timezone.now()
                )
                
                return True
        except Notification.DoesNotExist:
            pass
        return False
    
    @database_sync_to_async
    def mark_all_notifications_read(self):
        count = Notification.objects.filter(
            recipient=self.user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
        return count
    
    @database_sync_to_async
    def delete_notification(self, notification_id):
        try:
            notification = Notification.objects.get(
                notification_id=notification_id,
                recipient=self.user
            )
            notification.delete()
            return True
        except Notification.DoesNotExist:
            return False
    
    @database_sync_to_async
    def get_unread_count(self):
        return Notification.objects.filter(
            recipient=self.user,
            is_read=False
        ).count()
    
    @database_sync_to_async
    def get_user_preferences(self):
        try:
            prefs = NotificationPreference.objects.get(user=self.user)
            return {
                'enable_websocket': prefs.enable_websocket,
                'enable_push': prefs.enable_push,
                'enable_email': prefs.enable_email,
                'enable_sms': prefs.enable_sms,
                'notification_types': prefs.notification_types,
                'priority_threshold': prefs.priority_threshold,
                'quiet_hours_enabled': prefs.quiet_hours_enabled,
                'quiet_hours_start': str(prefs.quiet_hours_start) if prefs.quiet_hours_start else None,
                'quiet_hours_end': str(prefs.quiet_hours_end) if prefs.quiet_hours_end else None,
                'sound_enabled': prefs.sound_enabled,
            }
        except NotificationPreference.DoesNotExist:
            return {
                'enable_websocket': True,
                'enable_push': False,
                'enable_email': True,
                'enable_sms': False,
                'notification_types': [],
                'priority_threshold': 'LOW',
                'quiet_hours_enabled': False,
                'sound_enabled': True,
            }
    
    @database_sync_to_async
    def update_user_preferences(self, preferences):
        try:
            prefs, created = NotificationPreference.objects.get_or_create(user=self.user)
            
            for key, value in preferences.items():
                if hasattr(prefs, key):
                    setattr(prefs, key, value)
            
            prefs.updated_at = timezone.now()
            prefs.save()
            return True
        except Exception as e:
            logger.error(f"Error updating preferences: {e}")
            return False
    
    @database_sync_to_async
    def update_delivery_status(self, notification_id, status):
        try:
            delivery = NotificationDelivery.objects.filter(
                notification_id=notification_id,
                delivery_method='WEBSOCKET'
            ).first()
            
            if delivery:
                delivery.status = status
                if status == 'DELIVERED':
                    delivery.delivered_at = timezone.now()
                delivery.save()
        except Exception as e:
            logger.error(f"Error updating delivery status: {e}")
    
    @database_sync_to_async
    def confirm_delivery(self, notification_id):
        try:
            delivery = NotificationDelivery.objects.filter(
                notification_id=notification_id,
                delivery_method='WEBSOCKET'
            ).first()
            
            if delivery:
                delivery.confirmed_at = timezone.now()
                delivery.status = 'CONFIRMED'
                delivery.save()
        except Exception as e:
            logger.error(f"Error confirming delivery: {e}")
    
    @database_sync_to_async
    def get_paginated_notifications(self, page, page_size, filter_type):
        queryset = Notification.objects.filter(recipient=self.user)
        
        if filter_type == 'unread':
            queryset = queryset.filter(is_read=False)
        elif filter_type == 'read':
            queryset = queryset.filter(is_read=True)
        
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        
        notifications = list(queryset[start:end])
        
        return {
            'notifications': [
                {
                    'id': n.notification_id,
                    'type': n.notification_type,
                    'priority': n.priority,
                    'title': n.title,
                    'message': n.message,
                    'is_read': n.is_read,
                    'created_at': str(n.created_at),
                    'action_url': n.action_url,
                    'image_url': n.image_url,
                    'metadata': n.metadata
                }
                for n in notifications
            ],
            'pagination': {
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size if total > 0 else 0
            }
        }