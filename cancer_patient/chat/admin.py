from rest_framework import serializers
from .models import (
    ChatRoom, ChatRoomParticipant, Message, MessageReadReceipt,
    UserStatus, BlockedUser, ChatNotification
)
from django.contrib.auth import get_user_model

User = get_user_model()


class ChatRoomSerializer(serializers.ModelSerializer):
    participant_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatRoom
        fields = ['_id', 'room_id', 'room_type', 'name', 'created_by_id', 
                  'created_at', 'updated_at', 'is_active', 'participant_count', 
                  'last_message']
        read_only_fields = ['room_id', 'created_at', 'updated_at']
    
    def get_participant_count(self, obj):
        return ChatRoomParticipant.objects.filter(chat_room_id=obj.room_id).count()
    
    def get_last_message(self, obj):
        last_msg = Message.objects.filter(chat_room_id=obj.room_id).first()
        if last_msg:
            return {
                'message_id': last_msg.message_id,
                'content': last_msg.content,
                'sender_id': last_msg.sender_id,
                'created_at': last_msg.created_at,
                'message_type': last_msg.message_type
            }
        return None


class ChatRoomParticipantSerializer(serializers.ModelSerializer):
    user_details = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatRoomParticipant
        fields = ['participant_id', 'chat_room_id', 'user_id', 'joined_at', 'user_details']
        read_only_fields = ['participant_id', 'joined_at']
    
    def get_user_details(self, obj):
        try:
            user = User.objects.get(id=obj.user_id)
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
        except User.DoesNotExist:
            return None


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    read_count = serializers.SerializerMethodField()
    total_participants = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = ['_id', 'message_id', 'chat_room_id', 'sender_id', 'sender_name',
                  'message_type', 'content', 'file', 'image', 'status', 
                  'is_deleted', 'replied_to_id', 'created_at', 'updated_at',
                  'read_count', 'total_participants']
        read_only_fields = ['message_id', 'created_at', 'updated_at']
    
    def get_sender_name(self, obj):
        try:
            user = User.objects.get(id=obj.sender_id)
            return user.get_full_name() or user.username
        except User.DoesNotExist:
            return "Unknown User"
    
    def get_read_count(self, obj):
        return MessageReadReceipt.objects.filter(message_id=obj.message_id).count()
    
    def get_total_participants(self, obj):
        return ChatRoomParticipant.objects.filter(chat_room_id=obj.chat_room_id).count()


class MessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['chat_room_id', 'sender_id', 'message_type', 'content', 
                  'file', 'image', 'replied_to_id']
    
    def validate_chat_room_id(self, value):
        if not ChatRoom.objects.filter(room_id=value, is_active=True).exists():
            raise serializers.ValidationError("Chat room does not exist or is inactive")
        return value
    
    def validate_sender_id(self, value):
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User does not exist")
        return value


class MessageReadReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageReadReceipt
        fields = ['receipt_id', 'message_id', 'user_id', 'read_at']
        read_only_fields = ['receipt_id', 'read_at']


class UserStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserStatus
        fields = ['status_id', 'user_id', 'is_online', 'last_seen']
        read_only_fields = ['status_id']


class BlockedUserSerializer(serializers.ModelSerializer):
    blocked_user_details = serializers.SerializerMethodField()
    
    class Meta:
        model = BlockedUser
        fields = ['block_id', 'user_id', 'blocked_user_id', 'created_at', 
                  'blocked_user_details']
        read_only_fields = ['block_id', 'created_at']
    
    def get_blocked_user_details(self, obj):
        try:
            user = User.objects.get(id=obj.blocked_user_id)
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
        except User.DoesNotExist:
            return None


class ChatNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatNotification
        fields = ['notification_id', 'recipient_id', 'sender_id', 
                  'notification_type', 'message_obj_id', 'chat_room_id',
                  'title', 'content', 'is_read', 'created_at']
        read_only_fields = ['notification_id', 'created_at']