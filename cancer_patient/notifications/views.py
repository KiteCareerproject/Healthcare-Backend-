# from rest_framework import status
# from rest_framework.decorators import api_view, permission_classes
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response
# from django.utils import timezone
# from .models import Notification, ReminderSchedule, NotificationLog
# from accounts.models import User, PatientProfile
# from patients.models import PatientMedicalRecord
# from accounts.utils import handle_errors, APIError
# from .serializers import (
#     NotificationSerializer, ReminderScheduleSerializer,
#     NotificationLogSerializer, CreateNotificationSerializer
# )
# import logging

# logger = logging.getLogger(__name__)

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def get_my_notifications(request):
#     """Get notifications for the current user"""
    
#     # Get all notifications for the user
#     notifications = Notification.objects.filter(recipient=request.user)
    
#     # Apply filters
#     is_read = request.query_params.get('is_read')
#     if is_read is not None:
#         is_read_bool = is_read.lower() == 'true'
#         # FIX: Don't use .filter() with NOT condition
#         all_notifications = list(notifications)
#         filtered_notifications = [n for n in all_notifications if n.is_read == is_read_bool]
#         # Convert back to queryset? Better to handle differently
#         notifications = notifications.filter(is_read=is_read_bool)  # This might still fail
    
#     # Pagination
#     page = int(request.query_params.get('page', 1))
#     page_size = int(request.query_params.get('page_size', 20))
#     start = (page - 1) * page_size
#     end = start + page_size
    
#     # FIX: Get counts manually to avoid Djongo translation errors
#     try:
#         # Get all notifications as list
#         all_notifications = list(notifications)
#         total_count = len(all_notifications)
        
#         # Count unread manually
#         unread_count = len([n for n in all_notifications if not n.is_read])
        
#         # Paginate manually
#         paginated_notifications = all_notifications[start:end]
        
#     except Exception as e:
#         print(f"Error processing notifications: {e}")
#         total_count = 0
#         unread_count = 0
#         paginated_notifications = []
    
#     serializer = NotificationSerializer(paginated_notifications, many=True)
    
#     return Response({
#         'success': True,
#         'data': serializer.data,
#         'unread_count': unread_count,
#         'pagination': {
#             'total': total_count,
#             'page': page,
#             'page_size': page_size,
#             'total_pages': (total_count + page_size - 1) // page_size if total_count > 0 else 0
#         }
#     })

# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def mark_as_read(request, notification_id):
#     """Mark notification as read"""
#     user = request.user
    
#     try:
#         notification = Notification.objects.get(notification_id=notification_id, recipient=user)
#     except Notification.DoesNotExist:
#         raise APIError("Notification not found", status_code=status.HTTP_404_NOT_FOUND)
    
#     notification.is_read = True
#     notification.read_at = timezone.now()
#     notification.save()
    
#     return Response({
#         'success': True,
#         'message': 'Notification marked as read'
#     })

# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def mark_all_read(request):
#     """Mark all notifications as read for the current user"""
    
#     count = 0
    
#     # FIX: Don't use iterator() - get all IDs first
#     try:
#         # Get only the IDs of unread notifications
#         notification_ids = list(Notification.objects.filter(
#             recipient=request.user,
#             is_read=False
#         ).values_list('id', flat=True))
        
#         # Update each notification by ID
#         for notification_id in notification_ids:
#             try:
#                 # Get and update individually
#                 notification = Notification.objects.get(id=notification_id)
#                 notification.is_read = True
#                 notification.read_at = timezone.now()
#                 notification.save()
#                 count += 1
#             except Notification.DoesNotExist:
#                 continue
#             except Exception as e:
#                 logger.error(f"Error updating notification {notification_id}: {e}")
                
#     except Exception as e:
#         logger.error(f"Error getting notification IDs: {e}")
        
#         # Fallback: Try a different approach
#         try:
#             # Get all notifications and filter in Python
#             all_notifications = list(Notification.objects.filter(recipient=request.user))
#             unread_notifications = [n for n in all_notifications if not n.is_read]
            
#             for notification in unread_notifications:
#                 try:
#                     notification.is_read = True
#                     notification.read_at = timezone.now()
#                     notification.save()
#                     count += 1
#                 except Exception as e2:
#                     logger.error(f"Error saving notification: {e2}")
#         except Exception as e2:
#             logger.error(f"Fallback also failed: {e2}")
    
#     return Response({
#         'success': True,
#         'message': f'{count} notifications marked as read',
#         'count': count
#     })

# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def create_notification(request):
#     """Create a new notification (for staff)"""
#     user = request.user
    
#     if user.user_type not in ['NURSE', 'DOCTOR', 'ADMIN']:
#         raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
#     serializer = CreateNotificationSerializer(data=request.data)
#     if not serializer.is_valid():
#         raise APIError("Validation error", errors=serializer.errors)
    
#     data = serializer.validated_data
    
#     try:
#         recipient = User.objects.get(user_id=data['recipient_id'])
#     except User.DoesNotExist:
#         raise APIError("Recipient not found", status_code=status.HTTP_404_NOT_FOUND)
    
#     notification_data = {
#         'recipient': recipient,
#         'notification_type': data['notification_type'],
#         'priority': data.get('priority', 'MEDIUM'),
#         'title': data['title'],
#         'message': data['message']
#     }
    
#     if data.get('related_patient_id'):
#         try:
#             patient = PatientMedicalRecord.objects.get(medical_record_id=data['related_patient_id'])
#             notification_data['related_patient'] = patient
#         except PatientMedicalRecord.DoesNotExist:
#             pass
    
#     notification = Notification.objects.create(**notification_data)
    
#     logger.info(f"Notification created for user {data['recipient_id']}")
    
#     response_serializer = NotificationSerializer(notification)
#     return Response({
#         'success': True,
#         'message': 'Notification created successfully',
#         'data': response_serializer.data
#     }, status=status.HTTP_201_CREATED)

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# @handle_errors
# def get_reminder_schedules(request):
#     """Get reminder schedules for current patient"""
#     user = request.user
    
#     if user.user_type != 'PATIENT':
#         raise APIError("Only patients can access reminder schedules", 
#                       status_code=status.HTTP_403_FORBIDDEN)
    
#     try:
#         patient = PatientProfile.objects.get(user=user)
#         medical_record = PatientMedicalRecord.objects.get(patient=patient)
#     except (PatientProfile.DoesNotExist, PatientMedicalRecord.DoesNotExist):
#         raise APIError("Patient profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
#     schedules = ReminderSchedule.objects.filter(patient=medical_record, is_active=True)
#     serializer = ReminderScheduleSerializer(schedules, many=True)
    
#     return Response({
#         'success': True,
#         'data': serializer.data
#     })

# notifications/views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from .models import Notification, ReminderSchedule, NotificationLog, NotificationDelivery, NotificationPreference
from accounts.models import User, PatientProfile
from patients.models import PatientMedicalRecord
from accounts.utils import handle_errors, APIError
from .serializers import (
    NotificationSerializer, ReminderScheduleSerializer,
    NotificationLogSerializer, CreateNotificationSerializer, 
    NotificationPreferenceSerializer
)
from .utils import send_realtime_notification
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_my_notifications(request):
    """Get notifications for the current user"""
    user = request.user
    
    # Apply filters
    is_read = request.query_params.get('is_read')
    notification_type = request.query_params.get('type')
    priority = request.query_params.get('priority')
    
    # Build queryset
    notifications = Notification.objects.filter(recipient=user)
    
    if is_read is not None:
        is_read_bool = is_read.lower() == 'true'
        notifications = notifications.filter(is_read=is_read_bool)
    
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    if priority:
        notifications = notifications.filter(priority=priority)
    
    # Pagination
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    start = (page - 1) * page_size
    end = start + page_size
    
    # Get counts
    total_count = notifications.count()
    unread_count = notifications.filter(is_read=False).count()
    
    # Paginate
    paginated_notifications = notifications[start:end]
    
    serializer = NotificationSerializer(paginated_notifications, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data,
        'unread_count': unread_count,
        'pagination': {
            'total': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size if total_count > 0 else 0
        }
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def mark_as_read(request, notification_id):
    """Mark notification as read"""
    user = request.user
    
    try:
        notification = Notification.objects.get(notification_id=notification_id, recipient=user)
    except Notification.DoesNotExist:
        raise APIError("Notification not found", status_code=status.HTTP_404_NOT_FOUND)
    
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save()
    
    # Create delivery confirmation
    NotificationDelivery.objects.create(
        notification=notification,
        delivery_method='IN_APP',
        status='DELIVERED',
        delivered_at=timezone.now(),
        confirmed_at=timezone.now()
    )
    
    return Response({
        'success': True,
        'message': 'Notification marked as read'
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def mark_all_read(request):
    """Mark all notifications as read for the current user"""
    
    with transaction.atomic():
        notifications = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        )
        
        count = notifications.count()
        
        notifications.update(
            is_read=True,
            read_at=timezone.now()
        )
    
    return Response({
        'success': True,
        'message': f'{count} notifications marked as read',
        'count': count
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@handle_errors
def create_notification(request):
    """Create a new notification with WebSocket delivery"""
    user = request.user
    
    if user.user_type not in ['NURSE', 'DOCTOR', 'ADMIN']:
        raise APIError("Permission denied", status_code=status.HTTP_403_FORBIDDEN)
    
    serializer = CreateNotificationSerializer(data=request.data)
    if not serializer.is_valid():
        raise APIError("Validation error", errors=serializer.errors)
    
    data = serializer.validated_data
    
    try:
        recipient = User.objects.get(user_id=data['recipient_id'])
    except User.DoesNotExist:
        raise APIError("Recipient not found", status_code=status.HTTP_404_NOT_FOUND)
    
    notification_data = {
        'recipient': recipient,
        'notification_type': data['notification_type'],
        'priority': data.get('priority', 'MEDIUM'),
        'title': data['title'],
        'message': data['message'],
        'metadata': data.get('metadata', {}),
        'action_url': data.get('action_url'),
        'image_url': data.get('image_url'),
    }
    
    if data.get('related_patient_id'):
        try:
            patient = PatientMedicalRecord.objects.get(medical_record_id=data['related_patient_id'])
            notification_data['related_patient'] = patient
        except PatientMedicalRecord.DoesNotExist:
            pass
    
    if data.get('related_alert_id'):
        try:
            from monitoring.models import Alert
            alert = Alert.objects.get(alert_id=data['related_alert_id'])
            notification_data['related_alert'] = alert
        except:
            pass
    
    # Create notification
    notification = Notification.objects.create(**notification_data)
    
    # Send via WebSocket
    send_realtime_notification(notification.notification_id)
    
    logger.info(f"Notification created for user {data['recipient_id']}")
    
    response_serializer = NotificationSerializer(notification)
    return Response({
        'success': True,
        'message': 'Notification created and sent successfully',
        'data': response_serializer.data
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@handle_errors
def get_reminder_schedules(request):
    """Get reminder schedules for current patient"""
    user = request.user
    
    if user.user_type != 'PATIENT':
        raise APIError("Only patients can access reminder schedules", 
                      status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        patient = PatientProfile.objects.get(user=user)
        medical_record = PatientMedicalRecord.objects.get(patient=patient)
    except (PatientProfile.DoesNotExist, PatientMedicalRecord.DoesNotExist):
        raise APIError("Patient profile not found", status_code=status.HTTP_404_NOT_FOUND)
    
    schedules = ReminderSchedule.objects.filter(patient=medical_record, is_active=True)
    serializer = ReminderScheduleSerializer(schedules, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data
    })

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
@handle_errors
def notification_preferences(request):
    """Get or update notification preferences"""
    user = request.user
    
    if request.method == 'GET':
        try:
            prefs = NotificationPreference.objects.get(user=user)
            serializer = NotificationPreferenceSerializer(prefs)
        except NotificationPreference.DoesNotExist:
            serializer = NotificationPreferenceSerializer()
        
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    elif request.method == 'PUT':
        prefs, created = NotificationPreference.objects.get_or_create(user=user)
        serializer = NotificationPreferenceSerializer(prefs, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'data': serializer.data
            })
        
        raise APIError("Validation error", errors=serializer.errors)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@handle_errors
def delete_notification(request, notification_id):
    """Delete a notification"""
    user = request.user
    
    try:
        notification = Notification.objects.get(notification_id=notification_id, recipient=user)
        notification.delete()
        
        return Response({
            'success': True,
            'message': 'Notification deleted successfully'
        })
    except Notification.DoesNotExist:
        raise APIError("Notification not found", status_code=status.HTTP_404_NOT_FOUND)