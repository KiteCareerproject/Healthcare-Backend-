# chat/models.py

from djongo import models
from django.utils import timezone

# Chat Room
class ChatRoom(models.Model):
    _id = models.ObjectIdField(primary_key=True)
    room_id = models.IntegerField(unique=True, editable=False, null=True, blank=True)
    
    ROOM_TYPES = (
        ('individual', 'Individual'),
        ('group', 'Group'),
    )
    
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='individual')
    name = models.CharField(max_length=255, blank=True, null=True)
    created_by_id = models.IntegerField()  # Store integer user_id directly
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'chat_rooms'
        ordering = ['-updated_at']
    
    def save(self, *args, **kwargs):
        if not self.room_id:
            last_room = ChatRoom.objects.all().order_by('-room_id').first()
            self.room_id = (last_room.room_id + 1) if last_room and last_room.room_id else 1
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Chat Room {self.room_id}"

# Participants - Separate table for participants
class ChatRoomParticipant(models.Model):
    room_id = models.ObjectIdField(primary_key=True)
    participant_id = models.IntegerField(unique=True, editable=False, null=True, blank=True)
    chat_room_id = models.IntegerField()  # Store room_id
    user_id = models.IntegerField()  # Store user_id
    joined_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'chat_room_participants'
        unique_together = ['chat_room_id', 'user_id']
    
    def save(self, *args, **kwargs):
        if not self.participant_id:
            last = ChatRoomParticipant.objects.all().order_by('-participant_id').first()
            self.participant_id = (last.participant_id + 1) if last and last.participant_id else 1
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Room {self.chat_room_id} - User {self.user_id}"

# Message
class Message(models.Model):
    _id = models.ObjectIdField(primary_key=True)
    message_id = models.IntegerField(unique=True, editable=False, null=True, blank=True)
    
    MESSAGE_TYPES = (
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('audio', 'Audio'),
        ('video', 'Video'),
    )
    
    STATUS_CHOICES = (
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
    )
    
    chat_room_id = models.IntegerField()  # Store room_id
    sender_id = models.IntegerField()  # Store user_id
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='chat_files/', blank=True, null=True)
    image = models.ImageField(upload_to='chat_images/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    is_deleted = models.BooleanField(default=False)
    replied_to_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'messages'
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.message_id:
            last_msg = Message.objects.all().order_by('-message_id').first()
            self.message_id = (last_msg.message_id + 1) if last_msg and last_msg.message_id else 1
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Message {self.message_id}"

# Message Read Receipt
class MessageReadReceipt(models.Model):
    _id = models.ObjectIdField(primary_key=True)
    receipt_id = models.IntegerField(unique=True, editable=False, null=True, blank=True)
    message_id = models.IntegerField()  # Store message_id
    user_id = models.IntegerField()  # Store user_id
    read_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'message_read_receipts'
        unique_together = ['message_id', 'user_id']
    
    def save(self, *args, **kwargs):
        if not self.receipt_id:
            last = MessageReadReceipt.objects.all().order_by('-receipt_id').first()
            self.receipt_id = (last.receipt_id + 1) if last and last.receipt_id else 1
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Receipt {self.receipt_id}"

# User Status
class UserStatus(models.Model):
    _id = models.ObjectIdField(primary_key=True)
    status_id = models.IntegerField(unique=True, editable=False, null=True, blank=True)
    user_id = models.IntegerField(unique=True)  # Store user_id
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(default=timezone.now)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'user_status'
    
    def save(self, *args, **kwargs):
        if not self.status_id:
            last = UserStatus.objects.all().order_by('-status_id').first()
            self.status_id = (last.status_id + 1) if last and last.status_id else 1
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Status {self.status_id}"

# Blocked Users
class BlockedUser(models.Model):
    _id = models.ObjectIdField(primary_key=True)
    block_id = models.IntegerField(unique=True, editable=False, null=True, blank=True)
    user_id = models.IntegerField()  # Store user_id
    blocked_user_id = models.IntegerField()  # Store blocked user_id
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'blocked_users'
        unique_together = ['user_id', 'blocked_user_id']
    
    def save(self, *args, **kwargs):
        if not self.block_id:
            last = BlockedUser.objects.all().order_by('-block_id').first()
            self.block_id = (last.block_id + 1) if last and last.block_id else 1
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Block {self.block_id}"

# Chat Notification
class ChatNotification(models.Model):
    _id = models.ObjectIdField(primary_key=True)
    notification_id = models.IntegerField(unique=True, editable=False, null=True, blank=True)
    
    NOTIFICATION_TYPES = (
        ('message', 'New Message'),
        ('mention', 'Mention'),
        ('reaction', 'Reaction'),
    )
    
    recipient_id = models.IntegerField()  # Store user_id
    sender_id = models.IntegerField(null=True, blank=True)  # Store user_id
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    message_obj_id = models.IntegerField(null=True, blank=True)  # Store message_id
    chat_room_id = models.IntegerField(null=True, blank=True)  # Store room_id
    title = models.CharField(max_length=255)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.DjongoManager()
    
    class Meta:
        db_table = 'chat_notifications'
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.notification_id:
            last = ChatNotification.objects.all().order_by('-notification_id').first()
            self.notification_id = (last.notification_id + 1) if last and last.notification_id else 1
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Notification {self.notification_id}"