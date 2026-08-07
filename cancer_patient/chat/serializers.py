from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import (
    ChatRoom, ChatRoomParticipant, Message, MessageReadReceipt,
    UserStatus, BlockedUser, ChatNotification
)
from .mongo_helper import mongo
User = get_user_model()


# ==================== CHAT ROOM SERIALIZERS ====================

class ChatRoomListSerializer(serializers.ModelSerializer):
    """Serializer for listing chat rooms with basic info"""
    
    participant_count = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    last_message_time = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatRoom
        fields = [
            '_id', 'room_id', 'room_type', 'name', 'created_by_id',
            'created_at', 'updated_at', 'is_active', 'participant_count',
            'last_message_preview', 'last_message_time', 'unread_count'
        ]
        read_only_fields = ['room_id', 'created_at', 'updated_at']
    
    def get_participant_count(self, obj):
        try:
            return ChatRoomParticipant.objects.filter(chat_room_id=obj.room_id).count()
        except Exception:
            return 0
    
    def get_last_message_preview(self, obj):
        try:
            # Use exclude instead of is_deleted=False to avoid boolean filter issues
            last_msg = Message.objects.filter(
                chat_room_id=obj.room_id
            ).exclude(is_deleted=True).order_by('-created_at').first()
            
            if last_msg:
                return {
                    'message_id': last_msg.message_id,
                    'content': last_msg.content[:50] + '...' if last_msg.content and len(last_msg.content) > 50 else last_msg.content,
                    'sender_id': last_msg.sender_id,
                    'message_type': last_msg.message_type,
                    'created_at': last_msg.created_at
                }
        except Exception:
            pass
        return None
    
    def get_last_message_time(self, obj):
        try:
            last_msg = Message.objects.filter(
                chat_room_id=obj.room_id
            ).exclude(is_deleted=True).order_by('-created_at').first()
            return last_msg.created_at if last_msg else None
        except Exception:
            return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        
        try:
            user_id = request.user.pk
            # Use exclude instead of is_deleted=False
            messages = Message.objects.filter(
                chat_room_id=obj.room_id
            ).exclude(is_deleted=True)
            
            unread_count = 0
            for message in messages:
                if not MessageReadReceipt.objects.filter(
                    message_id=message.message_id,
                    user_id=user_id
                ).exists():
                    unread_count += 1
            return unread_count
        except Exception:
            return 0


class ChatRoomDetailSerializer(serializers.Serializer):
    """Serializer for detailed chat room information that works with MongoDB documents"""
    
    _id = serializers.CharField()
    room_id = serializers.IntegerField()
    room_type = serializers.CharField()
    name = serializers.CharField(required=False, allow_blank=True)
    created_by_id = serializers.IntegerField()
    created_by_details = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    is_active = serializers.BooleanField()
    participants = serializers.SerializerMethodField()
    participants_count = serializers.SerializerMethodField()
    recent_messages = serializers.SerializerMethodField()
    
    def get_participants(self, obj):
        """Get participants using direct MongoDB query"""
        participants_collection = mongo.get_collection('chat_room_participants')
        participants = list(participants_collection.find({
            'chat_room_id': obj['room_id'] if isinstance(obj, dict) else obj.room_id
        }))
        return ChatRoomParticipantSerializer(participants, many=True, context=self.context).data
    
    def get_participants_count(self, obj):
        """Get participants count using direct MongoDB query"""
        participants_collection = mongo.get_collection('chat_room_participants')
        room_id = obj['room_id'] if isinstance(obj, dict) else obj.room_id
        return participants_collection.count_documents({'chat_room_id': room_id})
    
    def get_created_by_details(self, obj):
        """Get creator details using direct MongoDB query"""
        try:
            created_by_id = obj['created_by_id'] if isinstance(obj, dict) else obj.created_by_id
            users_collection = mongo.get_collection('users')
            user = users_collection.find_one({'_id': created_by_id})
            
            if user:
                return {
                    'id': user['_id'],
                    'username': user.get('username'),
                    'full_name': user.get('full_name', ''),
                    'email': user.get('email')
                }
        except Exception as e:
            print(f"Error getting creator details: {e}")
        
        return None
    
    def get_recent_messages(self, obj):
        """Get recent messages using direct MongoDB query"""
        try:
            messages_collection = mongo.get_collection('messages')
            room_id = obj['room_id'] if isinstance(obj, dict) else obj.room_id
            
            messages = list(messages_collection.find({
                'chat_room_id': room_id,
                'is_deleted': False
            }).sort('created_at', -1).limit(50))
            
            return MessageSerializer(messages, many=True, context=self.context).data
        except Exception as e:
            print(f"Error getting recent messages: {e}")
            return []
    
    def to_representation(self, instance):
        """Convert MongoDB dict to representation"""
        if isinstance(instance, dict):
            return {
                '_id': str(instance.get('_id')),
                'room_id': instance.get('room_id'),
                'room_type': instance.get('room_type'),
                'name': instance.get('name', ''),
                'created_by_id': instance.get('created_by_id'),
                'created_by_details': self.get_created_by_details(instance),
                'created_at': instance.get('created_at'),
                'updated_at': instance.get('updated_at'),
                'is_active': instance.get('is_active', True),
                'participants': self.get_participants(instance),
                'participants_count': self.get_participants_count(instance),
                'recent_messages': self.get_recent_messages(instance),
            }
        # Handle Django model instance (if any)
        return super().to_representation(instance)


class ChatRoomCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new chat rooms"""
    
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True
    )
    
    class Meta:
        model = ChatRoom
        fields = ['room_type', 'name', 'participant_ids']
    
    def validate(self, data):
        if data.get('room_type') == 'group' and not data.get('name'):
            raise serializers.ValidationError({
                'name': 'Group chat must have a name'
            })
        return data
    
    def validate_participant_ids(self, value):
        if value:
            existing_users = User.objects.filter(pk__in=value)
            if len(existing_users) != len(value):
                raise serializers.ValidationError("One or more users do not exist")
        return value
    
    def create(self, validated_data):
        participant_ids = validated_data.pop('participant_ids', [])
        request = self.context.get('request')
        
        # Get user ID safely
        user_id = request.user.pk if hasattr(request.user, 'pk') else request.user.id
        
        # Create room
        room = ChatRoom.objects.create(
            **validated_data,
            created_by_id=user_id
        )
        
        # Add creator as participant
        ChatRoomParticipant.objects.create(
            chat_room_id=room.room_id,
            user_id=user_id
        )
        
        # Add other participants
        for user_id in participant_ids:
            ChatRoomParticipant.objects.create(
                chat_room_id=room.room_id,
                user_id=user_id
            )
        
        return room


class ChatRoomUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating chat rooms"""
    
    class Meta:
        model = ChatRoom
        fields = ['name', 'is_active']
    
    def validate(self, data):
        if self.instance.room_type == 'individual' and 'name' in data:
            raise serializers.ValidationError({
                'name': 'Individual chats cannot be renamed'
            })
        return data


# ==================== PARTICIPANT SERIALIZERS ====================

class ChatRoomParticipantSerializer(serializers.Serializer):
    """Serializer for chat room participants that works with MongoDB documents"""
    
    _id = serializers.CharField()
    chat_room_id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    user_details = serializers.SerializerMethodField()
    role = serializers.CharField()
    joined_at = serializers.DateTimeField()
    last_read_at = serializers.DateTimeField()
    
    def get_user_details(self, obj):
        """Handle both Django model and MongoDB dict"""
        try:
            # Get user_id from dict or model instance
            if isinstance(obj, dict):
                user_id = obj.get('user_id')
            else:
                user_id = obj.user_id
            
            if not user_id:
                return None
            
            # Use direct MongoDB query for user details
            users_collection = mongo.get_collection('users')
            user = users_collection.find_one({'_id': user_id})
            
            if user:
                return {
                    'id': user['_id'],
                    'username': user.get('username'),
                    'full_name': user.get('full_name', ''),
                    'email': user.get('email'),
                    'profile_pic': user.get('profile_pic')
                }
        except Exception as e:
            print(f"Error getting user details: {e}")
        
        return None
    
    def to_representation(self, instance):
        """Convert MongoDB dict to representation"""
        if isinstance(instance, dict):
            return {
                '_id': str(instance.get('_id')),
                'chat_room_id': instance.get('chat_room_id'),
                'user_id': instance.get('user_id'),
                'user_details': self.get_user_details(instance),
                'role': instance.get('role', 'member'),
                'joined_at': instance.get('joined_at'),
                'last_read_at': instance.get('last_read_at'),
            }
        # Handle Django model instance
        return super().to_representation(instance)


class ParticipantAddSerializer(serializers.Serializer):
    """Serializer for adding participants to a room"""
    
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    
    def validate_user_ids(self, value):
        existing_users = User.objects.filter(pk__in=value)
        if len(existing_users) != len(value):
            invalid_ids = set(value) - set(existing_users.values_list('pk', flat=True))
            raise serializers.ValidationError(f"Users not found: {list(invalid_ids)}")
        
        room_id = self.context.get('room_id')
        existing_participants = ChatRoomParticipant.objects.filter(
            chat_room_id=room_id,
            user_id__in=value
        ).values_list('user_id', flat=True)
        
        if existing_participants:
            raise serializers.ValidationError(
                f"Users already in room: {list(existing_participants)}"
            )
        
        return value


# ==================== MESSAGE SERIALIZERS ====================

class MessageSerializer(serializers.ModelSerializer):
    """Serializer for messages with detailed information"""
    
    sender_details = serializers.SerializerMethodField()
    read_receipts = serializers.SerializerMethodField()
    read_count = serializers.SerializerMethodField()
    total_participants = serializers.SerializerMethodField()
    is_read_by_current_user = serializers.SerializerMethodField()
    replied_to_message = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            '_id', 'message_id', 'chat_room_id', 'sender_id', 'sender_details',
            'message_type', 'content', 'file', 'file_url', 'image', 'image_url',
            'status', 'is_deleted', 'replied_to_id', 'replied_to_message',
            'created_at', 'updated_at', 'read_count', 'total_participants',
            'is_read_by_current_user', 'read_receipts'
        ]
        read_only_fields = ['message_id', 'created_at', 'updated_at']
    
    def get_sender_details(self, obj):
        try:
            user = User.objects.get(pk=obj.sender_id)
            return {
                'id': user.pk,
                'username': user.username,
                'full_name': user.get_full_name(),
                'email': user.email
            }
        except User.DoesNotExist:
            return None
    
    def get_read_receipts(self, obj):
        receipts = MessageReadReceipt.objects.filter(message_id=obj.message_id)
        return MessageReadReceiptSerializer(receipts, many=True).data
    
    def get_read_count(self, obj):
        return MessageReadReceipt.objects.filter(message_id=obj.message_id).count()
    
    def get_total_participants(self, obj):
        return ChatRoomParticipant.objects.filter(chat_room_id=obj.chat_room_id).count()
    
    def get_is_read_by_current_user(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        user_id = request.user.pk if hasattr(request.user, 'pk') else request.user.id
        return MessageReadReceipt.objects.filter(
            message_id=obj.message_id,
            user_id=user_id
        ).exists()
    
    def get_replied_to_message(self, obj):
        if obj.replied_to_id:
            try:
                replied_msg = Message.objects.get(
                    message_id=obj.replied_to_id,
                    is_deleted=False
                )
                return {
                    'message_id': replied_msg.message_id,
                    'content': replied_msg.content[:100] if replied_msg.content else None,
                    'sender_id': replied_msg.sender_id,
                    'message_type': replied_msg.message_type
                }
            except Message.DoesNotExist:
                return None
        return None
    
    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None
    
    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class MessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new messages"""
    
    class Meta:
        model = Message
        fields = [
            'chat_room_id', 'message_type', 'content', 
            'file', 'image', 'replied_to_id'
        ]
    
    def validate_chat_room_id(self, value):
        # CHANGE 1: Remove the .first() and use try-except with get()
        try:
            # Use get() instead of filter().first()
            chat_room = ChatRoom.objects.get(room_id=value, is_active=True)
        except ChatRoom.DoesNotExist:
            raise serializers.ValidationError("Chat room does not exist or is inactive")
        except Exception as e:
            # If get() fails due to djongo, try a different approach
            try:
                # Fallback: filter and then check in Python
                chat_rooms = list(ChatRoom.objects.filter(room_id=value))
                if not chat_rooms:
                    raise serializers.ValidationError("Chat room does not exist")
                
                # Check is_active manually
                active_rooms = [room for room in chat_rooms if room.is_active]
                if not active_rooms:
                    raise serializers.ValidationError("Chat room is inactive")
            except:
                raise serializers.ValidationError("Error validating chat room")
        
        # CHANGE 2: Validate participant using try-except
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            user_id = request.user.pk
            
            try:
                # Use get() instead of filter().exists()
                participant = ChatRoomParticipant.objects.get(
                    chat_room_id=value,
                    user_id=user_id
                )
            except ChatRoomParticipant.DoesNotExist:
                raise serializers.ValidationError("You are not a participant in this chat room")
            except Exception as e:
                # Fallback: filter and check in Python
                try:
                    participants = list(ChatRoomParticipant.objects.filter(
                        chat_room_id=value,
                        user_id=user_id
                    ))
                    if not participants:
                        raise serializers.ValidationError("You are not a participant in this chat room")
                except:
                    raise serializers.ValidationError("Error validating participant")
        
        return value
    
    def validate_replied_to_id(self, value):
        if value:
            # CHANGE 3: Use try-except for message validation
            try:
                message = Message.objects.get(message_id=value, is_deleted=False)
            except Message.DoesNotExist:
                raise serializers.ValidationError("The message you're replying to does not exist")
            except Exception:
                # Fallback
                try:
                    messages = list(Message.objects.filter(message_id=value))
                    if not messages:
                        raise serializers.ValidationError("The message you're replying to does not exist")
                    
                    # Check is_deleted manually
                    active_messages = [msg for msg in messages if not msg.is_deleted]
                    if not active_messages:
                        raise serializers.ValidationError("The message you're replying to does not exist")
                except:
                    raise serializers.ValidationError("Error validating replied message")
        return value
    
    def validate(self, data):
        message_type = data.get('message_type', 'text')
        
        if message_type == 'text' and not data.get('content'):
            raise serializers.ValidationError({
                'content': 'Content is required for text messages'
            })
        
        if message_type == 'image' and not data.get('image'):
            raise serializers.ValidationError({
                'image': 'Image file is required for image messages'
            })
        
        if message_type == 'file' and not data.get('file'):
            raise serializers.ValidationError({
                'file': 'File is required for file messages'
            })
        
        return data
    
    def create(self, validated_data):
        request = self.context.get('request')
        user_id = request.user.pk
        validated_data['sender_id'] = user_id
        return super().create(validated_data)


class MessageUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating messages"""
    
    class Meta:
        model = Message
        fields = ['content']
    
    def validate(self, data):
        if self.instance.message_type != 'text' and 'content' in data:
            raise serializers.ValidationError({
                'content': 'Only text messages can be edited'
            })
        
        request = self.context.get('request')
        if request and self.instance.sender_id != (request.user.pk if hasattr(request.user, 'pk') else request.user.id):
            raise serializers.ValidationError("You can only edit your own messages")
        
        return data


# ==================== READ RECEIPT SERIALIZERS ====================

class MessageReadReceiptSerializer(serializers.ModelSerializer):
    """Serializer for message read receipts"""
    
    user_details = serializers.SerializerMethodField()
    
    class Meta:
        model = MessageReadReceipt
        fields = ['receipt_id', 'message_id', 'user_id', 'user_details', 'read_at']
        read_only_fields = ['receipt_id', 'read_at']
    
    def get_user_details(self, obj):
        try:
            user = User.objects.get(pk=obj.user_id)
            return {
                'id': user.pk,
                'username': user.username,
                'full_name': user.get_full_name()
            }
        except User.DoesNotExist:
            return None


# ==================== USER STATUS SERIALIZERS ====================

class UserStatusSerializer(serializers.ModelSerializer):
    """Serializer for user online status"""
    
    class Meta:
        model = UserStatus
        fields = ['status_id', 'user_id', 'is_online', 'last_seen']
        read_only_fields = ['status_id']
    
    def update(self, instance, validated_data):
        if 'is_online' in validated_data and not validated_data['is_online']:
            validated_data['last_seen'] = timezone.now()
        return super().update(instance, validated_data)


class UserStatusBulkSerializer(serializers.Serializer):
    """Serializer for bulk user status retrieval"""
    
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True
    )
    
    def validate_user_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one user ID is required")
        return value


# ==================== BLOCKED USER SERIALIZERS ====================

class BlockedUserSerializer(serializers.ModelSerializer):
    """Serializer for blocked users"""
    
    blocked_user_details = serializers.SerializerMethodField()
    
    class Meta:
        model = BlockedUser
        fields = ['block_id', 'user_id', 'blocked_user_id', 'blocked_user_details', 'created_at']
        read_only_fields = ['block_id', 'created_at']
    
    def get_blocked_user_details(self, obj):
        try:
            user = User.objects.get(pk=obj.blocked_user_id)
            return {
                'id': user.pk,
                'username': user.username,
                'full_name': user.get_full_name(),
                'email': user.email
            }
        except User.DoesNotExist:
            return None


class BlockUserSerializer(serializers.Serializer):
    """Serializer for blocking a user"""
    
    blocked_user_id = serializers.IntegerField(required=True)
    
    def validate_blocked_user_id(self, value):
        if not User.objects.filter(pk=value).exists():
            raise serializers.ValidationError("User does not exist")
        
        request = self.context.get('request')
        user_id = request.user.pk if hasattr(request.user, 'pk') else request.user.id
        if request and user_id == value:
            raise serializers.ValidationError("You cannot block yourself")
        
        if BlockedUser.objects.filter(
            user_id=user_id,
            blocked_user_id=value
        ).exists():
            raise serializers.ValidationError("User is already blocked")
        
        return value


# ==================== NOTIFICATION SERIALIZERS ====================

class ChatNotificationSerializer(serializers.ModelSerializer):
    """Serializer for chat notifications"""
    
    sender_details = serializers.SerializerMethodField()
    chat_room_details = serializers.SerializerMethodField()
    message_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatNotification
        fields = [
            'notification_id', 'recipient_id', 'sender_id', 'sender_details',
            'notification_type', 'message_obj_id', 'chat_room_id', 'chat_room_details',
            'title', 'content', 'is_read', 'created_at', 'message_preview'
        ]
        read_only_fields = ['notification_id', 'created_at']
    
    def get_sender_details(self, obj):
        if obj.sender_id:
            try:
                user = User.objects.get(pk=obj.sender_id)
                return {
                    'id': user.pk,
                    'username': user.username,
                    'full_name': user.get_full_name()
                }
            except User.DoesNotExist:
                pass
        return None
    
    def get_chat_room_details(self, obj):
        if obj.chat_room_id:
            try:
                room = ChatRoom.objects.get(room_id=obj.chat_room_id)
                return {
                    'room_id': room.room_id,
                    'room_type': room.room_type,
                    'name': room.name
                }
            except ChatRoom.DoesNotExist:
                pass
        return None
    
    def get_message_preview(self, obj):
        if obj.message_obj_id:
            try:
                message = Message.objects.get(
                    message_id=obj.message_obj_id,
                    is_deleted=False
                )
                return {
                    'content': message.content[:100] if message.content else None,
                    'message_type': message.message_type
                }
            except Message.DoesNotExist:
                pass
        return None


class NotificationMarkReadSerializer(serializers.Serializer):
    """Serializer for marking notifications as read"""
    
    notification_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    mark_all = serializers.BooleanField(
        required=False,
        default=False
    )
    
    def validate(self, data):
        if not data.get('mark_all') and not data.get('notification_ids'):
            raise serializers.ValidationError(
                "Either provide notification_ids or set mark_all=True"
            )
        return data


# ==================== DIRECT MESSAGE SERIALIZERS ====================

class DirectMessageCreateSerializer(serializers.Serializer):
    """Serializer for creating direct messages"""
    
    user_id = serializers.IntegerField(required=True)
    
    def validate_user_id(self, value):
        if not User.objects.filter(pk=value).exists():
            raise serializers.ValidationError("User does not exist")
        
        request = self.context.get('request')
        user_pk = request.user.pk if hasattr(request.user, 'pk') else request.user.id
        if request and user_pk == value:
            raise serializers.ValidationError("You cannot send a message to yourself")
        
        return value


# ==================== SEARCH SERIALIZERS ====================

class MessageSearchSerializer(serializers.Serializer):
    """Serializer for searching messages"""
    
    query = serializers.CharField(required=True)
    chat_room_id = serializers.IntegerField(required=False)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    sender_id = serializers.IntegerField(required=False)
    
    def validate(self, data):
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError(
                    "Start date must be before end date"
                )
        return data


# ==================== EXPORT SERIALIZERS ====================

class ChatExportSerializer(serializers.Serializer):
    """Serializer for exporting chat data"""
    
    chat_room_id = serializers.IntegerField(required=True)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    include_participants = serializers.BooleanField(default=True)
    include_messages = serializers.BooleanField(default=True)
    format = serializers.ChoiceField(
        choices=['json', 'csv', 'txt'],
        default='json'
    )
    
    def validate_chat_room_id(self, value):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            user_id = request.user.pk if hasattr(request.user, 'pk') else request.user.id
            if not ChatRoomParticipant.objects.filter(
                chat_room_id=value,
                user_id=user_id
            ).exists():
                raise serializers.ValidationError(
                    "You don't have access to this chat room"
                )
        return value