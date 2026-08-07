from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from django.utils import timezone
from .models import (
    ChatRoom, ChatRoomParticipant, Message, MessageReadReceipt,
    UserStatus, BlockedUser, ChatNotification
)
from .serializers import *
from .mongo_helper import mongo
from django.contrib.auth import get_user_model
from bson import ObjectId
import json
from django.http import JsonResponse
from datetime import datetime, date

User = get_user_model()

def get_user_id(request):
    """Get user ID from request"""
    if hasattr(request.user, 'id'):
        return request.user.id
    return request.user.pk

# ==================== CHAT ROOM VIEWS ====================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def chat_room_list_create(request):
    """List all chat rooms or create new"""
    
    if request.method == 'GET':
        user_id = get_user_id(request)
        
        # Step 1: Get all rooms where user is participant
        participants_collection = mongo.get_collection('chat_room_participants')
        participants = list(participants_collection.find({'user_id': user_id}))
        
        if not participants:
            return Response([])
        
        # Step 2: Get room IDs
        room_ids = [p['chat_room_id'] for p in participants]
        
        # Step 3: Get room details
        rooms_collection = mongo.get_collection('chat_rooms')
        rooms_data = list(rooms_collection.find({
            'room_id': {'$in': room_ids},
            'is_active': True
        }).sort('updated_at', -1))
        
        # Step 4: Convert to Django model instances
        rooms = []
        for data in rooms_data:
            room = ChatRoom()
            room._id = data['_id']
            room.room_id = data['room_id']
            room.room_type = data['room_type']
            room.name = data.get('name')
            room.created_by_id = data['created_by_id']
            room.created_at = data['created_at']
            room.updated_at = data['updated_at']
            room.is_active = data['is_active']
            rooms.append(room)
        
        serializer = ChatRoomListSerializer(rooms, many=True, context={'request': request})
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = ChatRoomCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            room = serializer.save()
            return Response(ChatRoomListSerializer(room, context={'request': request}).data, 
                          status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def chat_room_detail(request, room_id):
    """Get, update or delete a chat room"""
    
    # Direct MongoDB query - இதுதான் முக்கியமான மாற்றம்
    rooms_collection = mongo.get_collection('chat_rooms')
    room_data = rooms_collection.find_one({
        'room_id': int(room_id), 
        'is_active': True
    })
    
    if not room_data:
        return Response({'error': 'Chat room not found'}, 
                        status=status.HTTP_404_NOT_FOUND)
    
    # Check if user is participant
    user_id = get_user_id(request)
    participants_collection = mongo.get_collection('chat_room_participants')
    is_participant = participants_collection.find_one({
        'chat_room_id': int(room_id),
        'user_id': user_id
    })
    
    if not is_participant:
        return Response({'error': 'You are not a participant'}, 
                        status=status.HTTP_403_FORBIDDEN)
    
    # Create ChatRoom instance
    room = ChatRoom()
    room._id = room_data['_id']
    room.room_id = room_data['room_id']
    room.room_type = room_data['room_type']
    room.name = room_data.get('name')
    room.created_by_id = room_data['created_by_id']
    room.created_at = room_data['created_at']
    room.updated_at = room_data['updated_at']
    room.is_active = room_data['is_active']
    
    if request.method == 'GET':
        serializer = ChatRoomDetailSerializer(room, context={'request': request})
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        # Update only allowed fields
        update_data = {}
        if 'name' in request.data and room.room_type != 'individual':
            update_data['name'] = request.data['name']
        if 'is_active' in request.data:
            update_data['is_active'] = request.data['is_active']
            update_data['updated_at'] = timezone.now()
        
        if update_data:
            rooms_collection.update_one(
                {'room_id': int(room_id)},
                {'$set': update_data}
            )
            # Refresh room data
            updated_room = rooms_collection.find_one({'room_id': int(room_id)})
            room.name = updated_room.get('name')
            room.is_active = updated_room['is_active']
        
        serializer = ChatRoomDetailSerializer(room, context={'request': request})
        return Response(serializer.data)
    
    elif request.method == 'DELETE':
        rooms_collection.update_one(
            {'room_id': int(room_id)},
            {'$set': {'is_active': False, 'updated_at': timezone.now()}}
        )
        return Response({'message': 'Room deleted'}, status=status.HTTP_200_OK)




def convert_objectid_to_str(obj):
    """Recursively convert ObjectId to string in dict/list"""
    if isinstance(obj, dict):
        return {key: convert_objectid_to_str(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectid_to_str(item) for item in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return obj

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_participant(request, room_id):
    """Add participant to room"""
    
    rooms_collection = mongo.get_collection('chat_rooms')
    room_data = rooms_collection.find_one({'room_id': int(room_id), 'is_active': True})
    
    if not room_data:
        return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Get user_ids - handle both single integer and list
    user_ids = request.data.get('user_ids', [])
    
    # Convert single integer to list
    if isinstance(user_ids, int):
        user_ids = [user_ids]
    
    # If it's a string representation, try to parse
    if isinstance(user_ids, str):
        try:
            import json
            user_ids = json.loads(user_ids)
        except:
            user_ids = [int(user_ids)] if user_ids.isdigit() else []
    
    # Ensure it's a list
    if not isinstance(user_ids, list):
        user_ids = [user_ids]
    
    # Remove duplicates and None values
    user_ids = list(set(filter(None, user_ids)))
    
    if not user_ids:
        return Response(
            {'error': 'user_ids required (single integer or array of integers)'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate that all user_ids are integers
    try:
        user_ids = [int(uid) for uid in user_ids]
    except (ValueError, TypeError):
        return Response(
            {'error': 'user_ids must be integers'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    participants_collection = mongo.get_collection('chat_room_participants')
    users_collection = mongo.get_collection('users')
    created = []
    already_existing = []
    not_found = []
    
    for user_id in user_ids:
        # Check if user exists
        user = users_collection.find_one({'user_id': user_id})
        
        if not user:
            not_found.append(user_id)
            continue
        
        # Check if already participant
        existing = participants_collection.find_one({
            'chat_room_id': int(room_id),
            'user_id': user_id
        })
        
        if existing:
            already_existing.append(user_id)
            continue
        
        # Get max participant_id
        last = participants_collection.find_one(sort=[('participant_id', -1)])
        new_id = (last['participant_id'] + 1) if last else 1
        
        participant = {
            'participant_id': new_id,
            'chat_room_id': int(room_id),
            'user_id': user_id,
            'role': 'member',
            'joined_at': timezone.now(),
            'last_read_at': timezone.now()
        }
        
        result = participants_collection.insert_one(participant)
        participant['_id'] = str(result.inserted_id)  # Convert ObjectId to string
        participant['user_details'] = {
            'id': user.get('user_id'),
            'username': user.get('username'),
            'full_name': user.get('full_name', user.get('username')),
            'email': user.get('email')
        }
        created.append(participant)
    
    # Prepare response based on results
    if created:
        response_data = {
            'message': f'Successfully added {len(created)} participant(s)',
            'participants': created,
        }
        
        if already_existing:
            response_data['already_participants'] = already_existing
            response_data['message'] += f", {len(already_existing)} user(s) already in room"
        
        if not_found:
            response_data['not_found'] = not_found
            response_data['message'] += f", {len(not_found)} user(s) not found"
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    elif already_existing and not not_found:
        return Response({
            'message': f'All {len(already_existing)} user(s) are already participants',
            'already_participants': already_existing
        }, status=status.HTTP_200_OK)
    
    else:
        return Response({
            'error': 'No participants were added',
            'details': {
                'not_found': not_found,
                'already_participants': already_existing
            }
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def remove_participant(request, room_id):
    """Remove participant from room"""
    
    user_id = request.data.get('user_id')
    if not user_id:
        return Response({'error': 'user_id required'}, status=status.HTTP_400_BAD_REQUEST)
    
    participants_collection = mongo.get_collection('chat_room_participants')
    result = participants_collection.delete_one({
        'chat_room_id': int(room_id),
        'user_id': user_id
    })
    
    if result.deleted_count == 0:
        return Response({'error': 'Participant not found'}, status=status.HTTP_404_NOT_FOUND)
    
    return Response({'message': 'Participant removed'}, status=status.HTTP_200_OK)


from bson import ObjectId
from datetime import datetime, date

def convert_mongo_doc(doc):
    """Recursively convert MongoDB document to JSON-serializable format"""
    if isinstance(doc, dict):
        return {key: convert_mongo_doc(value) for key, value in doc.items()}
    elif isinstance(doc, list):
        return [convert_mongo_doc(item) for item in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    elif isinstance(doc, datetime):
        return doc.isoformat()
    elif isinstance(doc, date):
        return doc.isoformat()
    else:
        return doc

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def room_participants(request, room_id):
    """Get all participants"""
    
    participants_collection = mongo.get_collection('chat_room_participants')
    participants = list(participants_collection.find({'chat_room_id': int(room_id)}))
    
    # Convert all MongoDB documents to JSON-serializable format
    serialized_participants = [convert_mongo_doc(participant) for participant in participants]
    
    return Response(serialized_participants)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def room_messages(request, room_id):
    """Get messages"""
    
    limit = int(request.query_params.get('limit', 50))
    offset = int(request.query_params.get('offset', 0))
    
    messages_collection = mongo.get_collection('messages')
    messages = list(messages_collection.find({
        'chat_room_id': int(room_id),
        'is_deleted': False
    }).sort('created_at', -1).skip(offset).limit(limit))
    
    # Convert ObjectId to string for JSON
    for msg in messages:
        msg['_id'] = str(msg['_id'])
    
    return Response(messages)


# ==================== PARTICIPANT VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_rooms(request):
    """Get all rooms where current user is a participant"""
    
    user_id = request.user.id
    participants = ChatRoomParticipant.objects.filter(user_id=user_id)
    serializer = ChatRoomParticipantSerializer(participants, many=True)
    return Response(serializer.data)


# ==================== MESSAGE VIEWS ====================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def message_list_create(request):
    """List messages or create new message"""
    
    user_id = request.user.pk
    
    if request.method == 'GET':
        # Convert to list to avoid subquery issues with djongo
        user_rooms = list(ChatRoomParticipant.objects.filter(
            user_id=user_id
        ).values_list('chat_room_id', flat=True))
        
        # If user has no rooms, return empty response
        if not user_rooms:
            return Response([])
        
        # Now query messages with the list of room IDs
        messages = Message.objects.filter(
            chat_room_id__in=user_rooms,
            is_deleted=False
        ).order_by('-created_at')
        
        room_id = request.query_params.get('room_id')
        if room_id:
            messages = messages.filter(chat_room_id=room_id)
        
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        
        # Convert to list to avoid lazy evaluation issues
        messages_list = list(messages[offset:offset+limit])
        
        serializer = MessageSerializer(messages_list, many=True, context={'request': request})
        return Response(serializer.data)
    
    if request.method == 'POST':
        serializer = MessageCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            
            # Check if receiver needs to be added
            chat_room_id = serializer.validated_data['chat_room_id']
            
            # Get current participants
            participants = ChatRoomParticipant.objects.filter(chat_room_id=chat_room_id)
            participant_ids = list(participants.values_list('user_id', flat=True))
            
            # If only sender is in the room, add default receiver
            if len(participant_ids) == 1 and participant_ids[0] == user_id:
                # Add a default receiver (user 80)
                ChatRoomParticipant.objects.create(
                    chat_room_id=chat_room_id,
                    user_id=80
                )
                print(f"Auto-added user 80 to chat room {chat_room_id}")
            
            message = serializer.save()
            
            # Get all participants (including newly added)
            all_participants = ChatRoomParticipant.objects.filter(
                chat_room_id=message.chat_room_id
            )
            
            # Get receiver details
            receivers = all_participants.exclude(user_id=user_id)
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            receiver_details = []
            for receiver in receivers:
                try:
                    user = User.objects.get(pk=receiver.user_id)
                    receiver_details.append({
                        'id': user.pk,
                        'username': user.username,
                        'full_name': getattr(user, 'full_name', user.username),
                        'email': user.email
                    })
                except:
                    receiver_details.append({
                        'id': receiver.user_id,
                        'username': 'Unknown',
                        'full_name': 'Unknown User',
                        'email': ''
                    })
            
            # Get sender details
            try:
                sender = User.objects.get(pk=user_id)
                sender_details = {
                    'id': sender.pk,
                    'username': sender.username,
                    'full_name': getattr(sender, 'full_name', sender.username),
                    'email': sender.email
                }
            except:
                sender_details = {
                    'id': user_id,
                    'username': 'Unknown',
                    'full_name': 'Unknown User',
                    'email': ''
                }
            
            # Create notifications
            notifications = []
            for receiver in receivers:
                notifications.append(
                    ChatNotification(
                        recipient_id=str(receiver.user_id),
                        sender_id=str(user_id),
                        notification_type='message',
                        message_obj_id=str(message.message_id),
                        chat_room_id=str(message.chat_room_id),
                        title='New Message',
                        content=message.content[:100] if message.content else 'New message'
                    )
                )
            
            if notifications:
                try:
                    ChatNotification.objects.bulk_create(notifications)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to create notifications: {str(e)}")
            
            # Prepare response
            response_data = MessageSerializer(message, context={'request': request}).data
            response_data['sender_details'] = sender_details
            response_data['receiver_details'] = receiver_details
            response_data['receiver_count'] = len(receiver_details)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def message_detail(request, message_id):
    """Retrieve, update or delete a message"""
    
    # Use direct MongoDB access to avoid djongo recursion issues
    # from .mongo import mongo
    from bson import ObjectId
    
    messages_collection = mongo.get_collection('messages')
    participants_collection = mongo.get_collection('chat_room_participants')
    users_collection = mongo.get_collection('users')
    
    # Find the message
    message = messages_collection.find_one({
        'message_id': int(message_id) if str(message_id).isdigit() else message_id,
        'is_deleted': False
    })
    
    if not message:
        return Response({'error': 'Message not found'}, 
                        status=status.HTTP_404_NOT_FOUND)
    
    # Check if user is a participant in the chat room
    participant = participants_collection.find_one({
        'chat_room_id': message['chat_room_id'],
        'user_id': request.user.pk
    })
    
    if not participant:
        return Response({'error': 'You are not a participant in this chat'}, 
                        status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        # Get sender details
        sender = users_collection.find_one({'user_id': message['sender_id']})
        
        # Prepare response
        response_data = {
            '_id': str(message['_id']),
            'message_id': message['message_id'],
            'chat_room_id': message['chat_room_id'],
            'sender_id': message['sender_id'],
            'sender_details': {
                'id': sender['user_id'] if sender else message['sender_id'],
                'username': sender.get('username', 'Unknown') if sender else 'Unknown',
                'full_name': sender.get('full_name', sender.get('username', 'Unknown')) if sender else 'Unknown',
                'email': sender.get('email', '') if sender else ''
            } if sender else None,
            'message_type': message.get('message_type', 'text'),
            'content': message.get('content', ''),
            'file': message.get('file'),
            'image': message.get('image'),
            'status': message.get('status', 'sent'),
            'is_deleted': message.get('is_deleted', False),
            'replied_to_id': message.get('replied_to_id'),
            'created_at': message.get('created_at'),
            'updated_at': message.get('updated_at')
        }
        
        # Add replied_to_message if exists
        if message.get('replied_to_id'):
            replied_msg = messages_collection.find_one({
                'message_id': message['replied_to_id'],
                'is_deleted': False
            })
            if replied_msg:
                response_data['replied_to_message'] = {
                    'message_id': replied_msg['message_id'],
                    'content': replied_msg.get('content', ''),
                    'sender_id': replied_msg['sender_id']
                }
        
        return Response(response_data)
    
    elif request.method == 'PUT':
        # Check if user owns the message
        if message['sender_id'] != request.user.pk:
            return Response({'error': 'You can only edit your own messages'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        # Update message
        update_data = {}
        
        if 'content' in request.data:
            update_data['content'] = request.data['content']
        if 'message_type' in request.data:
            update_data['message_type'] = request.data['message_type']
        if 'file' in request.data:
            update_data['file'] = request.data['file']
        if 'image' in request.data:
            update_data['image'] = request.data['image']
        
        if update_data:
            from django.utils import timezone
            update_data['updated_at'] = timezone.now()
            
            messages_collection.update_one(
                {'message_id': message['message_id']},
                {'$set': update_data}
            )
            
            # Get updated message
            updated_message = messages_collection.find_one({
                'message_id': message['message_id']
            })
            
            # Prepare response
            sender = users_collection.find_one({'user_id': updated_message['sender_id']})
            
            response_data = {
                '_id': str(updated_message['_id']),
                'message_id': updated_message['message_id'],
                'chat_room_id': updated_message['chat_room_id'],
                'sender_id': updated_message['sender_id'],
                'sender_details': {
                    'id': sender['user_id'] if sender else updated_message['sender_id'],
                    'username': sender.get('username', 'Unknown') if sender else 'Unknown',
                    'full_name': sender.get('full_name', sender.get('username', 'Unknown')) if sender else 'Unknown',
                    'email': sender.get('email', '') if sender else ''
                } if sender else None,
                'message_type': updated_message.get('message_type', 'text'),
                'content': updated_message.get('content', ''),
                'file': updated_message.get('file'),
                'image': updated_message.get('image'),
                'status': updated_message.get('status', 'sent'),
                'is_deleted': updated_message.get('is_deleted', False),
                'replied_to_id': updated_message.get('replied_to_id'),
                'created_at': updated_message.get('created_at'),
                'updated_at': updated_message.get('updated_at')
            }
            
            return Response(response_data)
        
        return Response({'message': 'No updates provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        # Check if user owns the message
        if message['sender_id'] != request.user.pk:
            return Response({'error': 'You can only delete your own messages'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        # Soft delete the message
        messages_collection.update_one(
            {'message_id': message['message_id']},
            {'$set': {'is_deleted': True, 'deleted_at': timezone.now()}}
        )
        
        return Response({'message': 'Message deleted successfully'}, 
                        status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_message_read(request, message_id):
    """Mark a message as read by current user"""
    
    # from .mongo import mongo
    from django.utils import timezone
    
    messages_collection = mongo.get_collection('messages')
    participants_collection = mongo.get_collection('chat_room_participants')
    read_receipts_collection = mongo.get_collection('message_read_receipts')
    
    # Convert message_id to int if needed
    try:
        msg_id = int(message_id)
    except (ValueError, TypeError):
        msg_id = message_id
    
    # Find the message
    message = messages_collection.find_one({
        'message_id': msg_id,
        'is_deleted': False
    })
    
    if not message:
        return Response({'error': 'Message not found'}, 
                        status=status.HTTP_404_NOT_FOUND)
    
    user_id = request.user.pk
    
    # Check if user is a participant in the chat room
    participant = participants_collection.find_one({
        'chat_room_id': message['chat_room_id'],
        'user_id': user_id
    })
    
    if not participant:
        return Response({'error': 'You are not a participant in this chat'}, 
                        status=status.HTTP_403_FORBIDDEN)
    
    # Check if receipt already exists
    existing_receipt = read_receipts_collection.find_one({
        'message_id': msg_id,
        'user_id': user_id
    })
    
    if not existing_receipt:
        # Create new read receipt
        # Get max receipt_id
        last_receipt = read_receipts_collection.find_one(sort=[('receipt_id', -1)])
        new_id = (last_receipt['receipt_id'] + 1) if last_receipt else 1
        
        receipt = {
            'receipt_id': new_id,
            'message_id': msg_id,
            'user_id': user_id,
            'read_at': timezone.now()
        }
        
        read_receipts_collection.insert_one(receipt)
        
        # Get total participants count
        total_participants = participants_collection.count_documents({
            'chat_room_id': message['chat_room_id']
        })
        
        # Get read count
        read_count = read_receipts_collection.count_documents({
            'message_id': msg_id
        })
        
        # Update message status if all participants have read it
        if read_count == total_participants:
            messages_collection.update_one(
                {'message_id': msg_id},
                {'$set': {'status': 'read', 'updated_at': timezone.now()}}
            )
    
    return Response({'status': 'marked as read', 'message_id': msg_id})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def message_read_receipts(request, message_id):
    """Get read receipts for a message"""
    
    try:
        message = Message.objects.get(message_id=message_id)
    except Message.DoesNotExist:
        return Response({'error': 'Message not found'}, 
                        status=status.HTTP_404_NOT_FOUND)
    
    receipts = MessageReadReceipt.objects.filter(message_id=message.message_id)
    serializer = MessageReadReceiptSerializer(receipts, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_messages_count(request):
    """Get count of unread messages for current user"""
    
    # from .mongo import mongo
    
    # Use pk instead of id
    user_id = request.user.pk
    
    # Get collections
    participants_collection = mongo.get_collection('chat_room_participants')
    messages_collection = mongo.get_collection('messages')
    read_receipts_collection = mongo.get_collection('message_read_receipts')
    
    # Get all rooms where user is a participant
    user_rooms = list(participants_collection.find(
        {'user_id': user_id},
        {'chat_room_id': 1}
    ))
    
    room_ids = [room['chat_room_id'] for room in user_rooms]
    
    if not room_ids:
        return Response({'unread_count': 0})
    
    # Get all messages in those rooms (not deleted)
    messages = list(messages_collection.find({
        'chat_room_id': {'$in': room_ids},
        'is_deleted': False
    }))
    
    # Get all read receipts for this user
    read_receipts = set()
    receipts = read_receipts_collection.find({
        'user_id': user_id
    })
    
    for receipt in receipts:
        read_receipts.add(receipt['message_id'])
    
    # Count unread messages
    unread_count = 0
    for message in messages:
        if message['message_id'] not in read_receipts:
            unread_count += 1
    
    return Response({'unread_count': unread_count})


# ==================== USER STATUS VIEWS ====================

@api_view(['GET', 'POST', 'PUT'])
@permission_classes([IsAuthenticated])
def user_status(request):
    """Get or update current user's status"""
    
    # from .mongo import mongo
    from django.utils import timezone
    
    # Use pk instead of id
    user_id = request.user.pk
    
    # Get collection
    user_status_collection = mongo.get_collection('user_status')
    
    if request.method == 'GET':
        # Get user status from MongoDB
        status_obj = user_status_collection.find_one({'user_id': user_id})
        
        if status_obj:
            # Convert ObjectId to string for response
            if '_id' in status_obj:
                status_obj['_id'] = str(status_obj['_id'])
            
            return Response({
                'user_id': status_obj.get('user_id'),
                'is_online': status_obj.get('is_online', False),
                'last_seen': status_obj.get('last_seen'),
                'status_message': status_obj.get('status_message', ''),
                'updated_at': status_obj.get('updated_at')
            })
        else:
            return Response({'is_online': False, 'last_seen': None})
    
    elif request.method == 'POST':
        # Create new status
        data = request.data
        
        # Check if status already exists
        existing = user_status_collection.find_one({'user_id': user_id})
        
        if existing:
            return Response({'error': 'Status already exists. Use PUT to update.'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Get max status_id
        last_status = user_status_collection.find_one(sort=[('status_id', -1)])
        new_id = (last_status['status_id'] + 1) if last_status else 1
        
        status_data = {
            'status_id': new_id,
            'user_id': user_id,
            'is_online': data.get('is_online', False),
            'last_seen': data.get('last_seen', timezone.now()),
            'status_message': data.get('status_message', ''),
            'updated_at': timezone.now()
        }
        
        result = user_status_collection.insert_one(status_data)
        
        return Response({
            'user_id': user_id,
            'is_online': status_data['is_online'],
            'last_seen': status_data['last_seen'],
            'status_message': status_data['status_message'],
            'updated_at': status_data['updated_at']
        }, status=status.HTTP_201_CREATED)
    
    elif request.method == 'PUT':
        # Update existing status
        data = request.data
        
        # Check if status exists
        existing = user_status_collection.find_one({'user_id': user_id})
        
        if not existing:
            return Response({'error': 'Status not found'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
        # Prepare update data
        update_data = {}
        if 'is_online' in data:
            update_data['is_online'] = data['is_online']
        if 'status_message' in data:
            update_data['status_message'] = data['status_message']
        if 'last_seen' in data:
            update_data['last_seen'] = data['last_seen']
        
        if update_data:
            update_data['updated_at'] = timezone.now()
            
            # Update in MongoDB
            user_status_collection.update_one(
                {'user_id': user_id},
                {'$set': update_data}
            )
            
            # Get updated status
            updated_status = user_status_collection.find_one({'user_id': user_id})
            
            return Response({
                'user_id': user_id,
                'is_online': updated_status.get('is_online', False),
                'last_seen': updated_status.get('last_seen'),
                'status_message': updated_status.get('status_message', ''),
                'updated_at': updated_status.get('updated_at')
            })
        
        return Response({
            'user_id': user_id,
            'is_online': existing.get('is_online', False),
            'last_seen': existing.get('last_seen'),
            'status_message': existing.get('status_message', ''),
            'updated_at': existing.get('updated_at')
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_online(request):
    """Set current user as online"""
    
    # from .mongo import mongo
    from django.utils import timezone
    
    # Use pk instead of id
    user_id = request.user.pk
    
    # Get collection
    user_status_collection = mongo.get_collection('user_status')
    
    # Check if status exists
    existing = user_status_collection.find_one({'user_id': user_id})
    
    if existing:
        # Update existing
        user_status_collection.update_one(
            {'user_id': user_id},
            {'$set': {
                'is_online': True,
                'last_seen': timezone.now(),
                'updated_at': timezone.now()
            }}
        )
    else:
        # Create new
        last_status = user_status_collection.find_one(sort=[('status_id', -1)])
        new_id = (last_status['status_id'] + 1) if last_status else 1
        
        user_status_collection.insert_one({
            'status_id': new_id,
            'user_id': user_id,
            'is_online': True,
            'last_seen': timezone.now(),
            'status_message': '',
            'updated_at': timezone.now()
        })
    
    return Response({'status': 'online', 'user_id': user_id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_offline(request):
    """Set current user as offline"""
    
    # from .mongo import mongo
    from django.utils import timezone
    
    # Use pk instead of id
    user_id = request.user.pk
    
    # Get collection
    user_status_collection = mongo.get_collection('user_status')
    
    # Update or create status
    existing = user_status_collection.find_one({'user_id': user_id})
    
    if existing:
        user_status_collection.update_one(
            {'user_id': user_id},
            {'$set': {
                'is_online': False,
                'last_seen': timezone.now(),
                'updated_at': timezone.now()
            }}
        )
    else:
        # Create status if not exists
        last_status = user_status_collection.find_one(sort=[('status_id', -1)])
        new_id = (last_status['status_id'] + 1) if last_status else 1
        
        user_status_collection.insert_one({
            'status_id': new_id,
            'user_id': user_id,
            'is_online': False,
            'last_seen': timezone.now(),
            'status_message': '',
            'updated_at': timezone.now()
        })
    
    return Response({'status': 'offline', 'user_id': user_id})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_status(request, user_id):
    """Get status of a specific user"""
    
    try:
        status_obj = UserStatus.objects.get(user_id=user_id)
        serializer = UserStatusSerializer(status_obj)
        return Response(serializer.data)
    except UserStatus.DoesNotExist:
        return Response({'user_id': user_id, 'is_online': False, 'last_seen': None})


# ==================== BLOCKED USER VIEWS ====================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def blocked_users(request):
    """List blocked users or block a user"""
    
    if request.method == 'GET':
        blocked = BlockedUser.objects.filter(user_id=request.user.id)
        serializer = BlockedUserSerializer(blocked, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = BlockUserSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            blocked = BlockedUser.objects.create(
                user_id=request.user.id,
                blocked_user_id=serializer.validated_data['blocked_user_id']
            )
            return Response(BlockedUserSerializer(blocked).data, 
                          status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def unblock_user(request, blocked_user_id):
    """Unblock a user"""
    
    blocked = BlockedUser.objects.filter(
        user_id=request.user.id,
        blocked_user_id=blocked_user_id
    ).first()
    
    if not blocked:
        return Response({'error': 'User not found in blocked list'}, 
                        status=status.HTTP_404_NOT_FOUND)
    
    blocked.delete()
    return Response({'message': 'User unblocked successfully'}, 
                    status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_blocked(request):
    """Check if a user is blocked by current user"""
    
    user_id = request.query_params.get('user_id')
    if not user_id:
        return Response({'error': 'user_id is required'}, 
                        status=status.HTTP_400_BAD_REQUEST)
    
    is_blocked = BlockedUser.objects.filter(
        user_id=request.user.id,
        blocked_user_id=user_id
    ).exists()
    
    return Response({'is_blocked': is_blocked})


# ==================== NOTIFICATION VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notifications(request):
    """Get all notifications for current user"""
    
    # from .mongo import mongo
    
    # Use pk instead of id
    user_id = request.user.pk
    
    # Get parameters
    limit = int(request.query_params.get('limit', 50))
    offset = int(request.query_params.get('offset', 0))
    is_read = request.query_params.get('is_read')
    
    # Get collection
    notifications_collection = mongo.get_collection('chat_notifications')
    users_collection = mongo.get_collection('users')
    
    # Build query
    query = {'recipient_id': user_id}
    
    if is_read is not None:
        query['is_read'] = is_read.lower() == 'true'
    
    # Get notifications with pagination
    notifications_cursor = notifications_collection.find(query).sort('created_at', -1).skip(offset).limit(limit)
    
    notifications_list = []
    for notification in notifications_cursor:
        # Convert ObjectId to string
        if '_id' in notification:
            notification['_id'] = str(notification['_id'])
        
        # Get sender details if available
        if 'sender_id' in notification and notification['sender_id']:
            sender = users_collection.find_one({'user_id': notification['sender_id']})
            if sender:
                notification['sender_details'] = {
                    'id': sender.get('user_id'),
                    'username': sender.get('username', 'Unknown'),
                    'full_name': sender.get('full_name', sender.get('username', 'Unknown')),
                    'email': sender.get('email', '')
                }
        
        notifications_list.append(notification)
    
    # Get total count
    total_count = notifications_collection.count_documents(query)
    
    return Response({
        'count': len(notifications_list),
        'total': total_count,
        'results': notifications_list
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """Mark a specific notification as read"""
    
    # from .mongo import mongo
    
    # Use pk instead of id
    user_id = request.user.pk
    
    # Get collection
    notifications_collection = mongo.get_collection('chat_notifications')
    
    # Update the notification
    result = notifications_collection.update_one(
        {
            'notification_id': int(notification_id),
            'recipient_id': user_id
        },
        {'$set': {'is_read': True}}
    )
    
    if result.matched_count == 0:
        return Response({'error': 'Notification not found'}, 
                        status=status.HTTP_404_NOT_FOUND)
    
    return Response({'status': 'marked as read'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """Mark all notifications as read for current user"""
    
    # from .mongo import mongo
    
    # Use pk instead of id
    user_id = request.user.pk
    
    # Get collection
    notifications_collection = mongo.get_collection('chat_notifications')
    
    # Update all unread notifications
    result = notifications_collection.update_many(
        {
            'recipient_id': user_id,
            'is_read': False
        },
        {'$set': {'is_read': True}}
    )
    
    return Response({
        'status': 'all notifications marked as read',
        'updated_count': result.modified_count
    })

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    """Delete a notification"""
    
    try:
        notification = ChatNotification.objects.get(
            notification_id=notification_id,
            recipient_id=request.user.id
        )
    except ChatNotification.DoesNotExist:
        return Response({'error': 'Notification not found'}, 
                        status=status.HTTP_404_NOT_FOUND)
    
    notification.delete()
    return Response({'message': 'Notification deleted successfully'}, 
                    status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_notifications_count(request):
    """Get count of unread notifications for current user"""
    
    count = ChatNotification.objects.filter(
        recipient_id=request.user.id,
        is_read=False
    ).count()
    
    return Response({'unread_count': count})


# ==================== DIRECT MESSAGE VIEWS ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_or_get_direct_chat(request):
    """Create or get existing direct chat with another user"""
    
    # from .mongo import mongo
    
    # Use pk instead of id
    user_id = request.user.pk
    
    # Validate input
    serializer = DirectMessageCreateSerializer(data=request.data, context={'request': request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    other_user_id = serializer.validated_data['user_id']
    
    # Get collections
    chat_rooms_collection = mongo.get_collection('chat_rooms')
    participants_collection = mongo.get_collection('chat_room_participants')
    users_collection = mongo.get_collection('users')
    
    # Check if other user exists
    other_user = users_collection.find_one({'user_id': other_user_id})
    if not other_user:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Find existing direct chat
    user_rooms = list(participants_collection.find(
        {'user_id': user_id},
        {'chat_room_id': 1}
    ))
    user_room_ids = [room['chat_room_id'] for room in user_rooms]
    
    other_user_rooms = list(participants_collection.find(
        {'user_id': other_user_id},
        {'chat_room_id': 1}
    ))
    other_user_room_ids = [room['chat_room_id'] for room in other_user_rooms]
    
    common_rooms = set(user_room_ids) & set(other_user_room_ids)
    
    existing_room = None
    for room_id in common_rooms:
        room = chat_rooms_collection.find_one({
            'room_id': room_id,
            'room_type': 'individual',
            'is_active': True
        })
        if room:
            existing_room = room
            break
    
    if existing_room:
        # Prepare room response with participants
        participants = list(participants_collection.find({'chat_room_id': existing_room['room_id']}))
        
        participant_details = []
        for participant in participants:
            user = users_collection.find_one({'user_id': participant['user_id']})
            participant_details.append({
                'user_id': participant['user_id'],
                'user_details': {
                    'id': user['user_id'] if user else participant['user_id'],
                    'username': user.get('username', 'Unknown') if user else 'Unknown',
                    'full_name': user.get('full_name', user.get('username', 'Unknown')) if user else 'Unknown',
                    'email': user.get('email', '') if user else ''
                } if user else None,
                'role': participant.get('role', 'member'),
                'joined_at': participant.get('joined_at')
            })
        
        # Get creator details
        creator = users_collection.find_one({'user_id': existing_room['created_by_id']})
        
        response_data = {
            '_id': str(existing_room['_id']),
            'room_id': existing_room['room_id'],
            'room_type': existing_room.get('room_type', 'individual'),
            'name': existing_room.get('name'),
            'created_by_id': existing_room['created_by_id'],
            'created_by_details': {
                'id': creator['user_id'] if creator else existing_room['created_by_id'],
                'username': creator.get('username', 'Unknown') if creator else 'Unknown',
                'full_name': creator.get('full_name', creator.get('username', 'Unknown')) if creator else 'Unknown',
                'email': creator.get('email', '') if creator else ''
            } if creator else None,
            'created_at': existing_room.get('created_at'),
            'updated_at': existing_room.get('updated_at'),
            'is_active': existing_room.get('is_active', True),
            'participants': participant_details,
            'participants_count': len(participant_details)
        }
        
        return Response(response_data)
    
    # Create new direct chat
    # Get next room_id
    last_room = chat_rooms_collection.find_one(sort=[('room_id', -1)])
    new_room_id = (last_room['room_id'] + 1) if last_room else 1
    
    from django.utils import timezone
    new_room = {
        'room_id': new_room_id,
        'room_type': 'individual',
        'name': None,
        'created_by_id': user_id,
        'created_at': timezone.now(),
        'updated_at': timezone.now(),
        'is_active': True
    }
    
    result = chat_rooms_collection.insert_one(new_room)
    new_room['_id'] = str(result.inserted_id)
    
    # Add participants
    participants_collection = mongo.get_collection('chat_room_participants')
    
    # Get next participant_id for both participants
    last_participant = participants_collection.find_one(sort=[('participant_id', -1)])
    next_participant_id = (last_participant['participant_id'] + 1) if last_participant else 1
    
    # Add user 1
    participant1 = {
        'participant_id': next_participant_id,
        'chat_room_id': new_room_id,
        'user_id': user_id,
        'role': 'member',
        'joined_at': timezone.now(),
        'last_read_at': timezone.now()
    }
    participants_collection.insert_one(participant1)
    
    # Add user 2
    participant2 = {
        'participant_id': next_participant_id + 1,
        'chat_room_id': new_room_id,
        'user_id': other_user_id,
        'role': 'member',
        'joined_at': timezone.now(),
        'last_read_at': timezone.now()
    }
    participants_collection.insert_one(participant2)
    
    # Prepare response
    participants = [participant1, participant2]
    participant_details = []
    for participant in participants:
        user = users_collection.find_one({'user_id': participant['user_id']})
        participant_details.append({
            'user_id': participant['user_id'],
            'user_details': {
                'id': user['user_id'] if user else participant['user_id'],
                'username': user.get('username', 'Unknown') if user else 'Unknown',
                'full_name': user.get('full_name', user.get('username', 'Unknown')) if user else 'Unknown',
                'email': user.get('email', '') if user else ''
            } if user else None,
            'role': participant.get('role', 'member'),
            'joined_at': participant.get('joined_at')
        })
    
    # Get creator details
    creator = users_collection.find_one({'user_id': user_id})
    
    response_data = {
        '_id': str(new_room['_id']),
        'room_id': new_room['room_id'],
        'room_type': new_room['room_type'],
        'name': new_room.get('name'),
        'created_by_id': new_room['created_by_id'],
        'created_by_details': {
            'id': creator['user_id'] if creator else user_id,
            'username': creator.get('username', 'Unknown') if creator else 'Unknown',
            'full_name': creator.get('full_name', creator.get('username', 'Unknown')) if creator else 'Unknown',
            'email': creator.get('email', '') if creator else ''
        } if creator else None,
        'created_at': new_room['created_at'],
        'updated_at': new_room['updated_at'],
        'is_active': new_room['is_active'],
        'participants': participant_details,
        'participants_count': len(participant_details)
    }
    
    return Response(response_data, status=status.HTTP_201_CREATED)


# ==================== SEARCH VIEWS ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search_messages(request):
    """Search messages by content"""
    
    serializer = MessageSearchSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    query = data['query']
    
    # Get rooms where user is participant
    user_rooms = ChatRoomParticipant.objects.filter(
        user_id=request.user.id
    ).values_list('chat_room_id', flat=True)
    
    messages = Message.objects.filter(
        chat_room_id__in=user_rooms,
        is_deleted=False,
        content__icontains=query
    )
    
    if data.get('chat_room_id'):
        messages = messages.filter(chat_room_id=data['chat_room_id'])
    
    if data.get('sender_id'):
        messages = messages.filter(sender_id=data['sender_id'])
    
    if data.get('start_date'):
        messages = messages.filter(created_at__gte=data['start_date'])
    
    if data.get('end_date'):
        messages = messages.filter(created_at__lte=data['end_date'])
    
    limit = int(request.query_params.get('limit', 50))
    offset = int(request.query_params.get('offset', 0))
    messages = messages.order_by('-created_at')[offset:offset+limit]
    
    result_serializer = MessageSerializer(messages, many=True, context={'request': request})
    return Response(result_serializer.data)