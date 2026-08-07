from django.urls import path
from . import views

urlpatterns = [
    # Chat Room URLs
    path('rooms/', views.chat_room_list_create, name='chat-room-list-create'),
    path('rooms/<int:room_id>/', views.chat_room_detail, name='chat-room-detail'),
    path('rooms/<int:room_id>/add-participant/', views.add_participant, name='add-participant'),
    path('rooms/<int:room_id>/remove-participant/', views.remove_participant, name='remove-participant'),
    path('rooms/<int:room_id>/participants/', views.room_participants, name='room-participants'),
    path('rooms/<int:room_id>/messages/', views.room_messages, name='room-messages'),
    
    # Message URLs
    path('messages/', views.message_list_create, name='message-list-create'),
    path('messages/<int:message_id>/', views.message_detail, name='message-detail'),
    path('messages/<int:message_id>/mark-read/', views.mark_message_read, name='mark-message-read'),
    path('messages/<int:message_id>/read-receipts/', views.message_read_receipts, name='message-read-receipts'),
    path('messages/unread/count/', views.unread_messages_count, name='unread-messages-count'),
    
    # Participant URLs
    path('my-rooms/', views.user_rooms, name='user-rooms'),
    
    # User Status URLs
    path('status/', views.user_status, name='user-status'),
    path('status/set-online/', views.set_online, name='set-online'),
    path('status/set-offline/', views.set_offline, name='set-offline'),
    path('status/<int:user_id>/', views.get_user_status, name='get-user-status'),
    
    # Blocked User URLs
    path('blocked/', views.blocked_users, name='blocked-users'),
    path('blocked/<int:blocked_user_id>/', views.unblock_user, name='unblock-user'),
    path('blocked/check/', views.check_blocked, name='check-blocked'),
    
    # Notification URLs
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:notification_id>/mark-read/', views.mark_notification_read, name='mark-notification-read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark-all-notifications-read'),
    path('notifications/<int:notification_id>/delete/', views.delete_notification, name='delete-notification'),
    path('notifications/unread/count/', views.unread_notifications_count, name='unread-notifications-count'),
    
    # Direct Message URLs
    path('direct-message/', views.create_or_get_direct_chat, name='direct-message'),
    
    # Search URLs
    path('search/messages/', views.search_messages, name='search-messages'),
]