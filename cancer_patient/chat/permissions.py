# chat/permissions.py

from rest_framework import permissions

class IsParticipantOfChat(permissions.BasePermission):
    """Check if user is participant in the chat room"""
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'chat_room'):
            return obj.chat_room.participants.filter(id=request.user.id).exists()
        return False

class IsMessageSenderOrAdmin(permissions.BasePermission):
    """Check if user is message sender or admin"""
    
    def has_object_permission(self, request, view, obj):
        if request.user.user_type == 'admin':
            return True
        if hasattr(obj, 'sender'):
            return obj.sender == request.user
        return False

class IsChatRoomParticipant(permissions.BasePermission):
    """Check if user is participant in chat room"""
    
    def has_object_permission(self, request, view, obj):
        return obj.participants.filter(id=request.user.id).exists()