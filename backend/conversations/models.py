from django.db import models
from django.contrib.auth.models import User
from core.models import BaseModel, Organization
from agents.models import Agent


class Room(BaseModel):
    """Chat room for multi-user conversations"""

    ROOM_TYPES = [
        ('private', 'Private Chat'),
        ('group', 'Group Chat'),
        ('agent', 'AI Agent Room'),
        ('multi_agent', 'Multi-Agent Room'),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField()
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='private')
    description = models.TextField(blank=True)

    # Relationships
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='rooms')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rooms')
    participants = models.ManyToManyField(User, through='RoomParticipant', related_name='rooms')
    agents = models.ManyToManyField(Agent, through='RoomAgent', related_name='assigned_rooms')

    # Room settings
    max_participants = models.IntegerField(default=10)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=False)

    # Configuration
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['organization', 'slug']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.room_type})"


class RoomParticipant(BaseModel):
    """Users participating in rooms"""

    ROLES = [
        ('owner', 'Owner'),
        ('admin', 'Administrator'),
        ('member', 'Member'),
        ('observer', 'Observer'),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLES, default='member')

    # Status
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(auto_now=True)

    # Permissions
    can_invite = models.BooleanField(default=False)
    can_manage_agents = models.BooleanField(default=False)

    class Meta:
        unique_together = ['room', 'user']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} in {self.room.name} ({self.role})"


class RoomAgent(BaseModel):
    """AI Agents assigned to rooms"""

    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE)

    # Agent configuration in this room
    is_active = models.BooleanField(default=True)
    auto_respond = models.BooleanField(default=True)
    trigger_keywords = models.JSONField(default=list, blank=True)

    # Settings
    max_messages_per_session = models.IntegerField(default=100)
    cooldown_seconds = models.IntegerField(default=0)

    added_by = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['room', 'agent']
        ordering = ['created_at']

    def __str__(self):
        return f"{self.agent.name} in {self.room.name}"


class Conversation(BaseModel):
    """Individual conversation sessions"""

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='conversations')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    # Session details
    title = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    # Timestamps
    last_activity = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-last_activity']

    def __str__(self):
        return f"Conversation {self.id.hex[:8]} in {self.room.name}"


class Message(BaseModel):
    """Chat messages in conversations"""

    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('file', 'File'),
        ('system', 'System'),
    ]

    SENDER_TYPES = [
        ('user', 'User'),
        ('agent', 'AI Agent'),
        ('system', 'System'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')

    # Message content
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()

    # Sender information
    sender_type = models.CharField(max_length=20, choices=SENDER_TYPES)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True)

    # Message metadata
    metadata = models.JSONField(default=dict, blank=True)
    processing_time = models.FloatField(null=True, blank=True)

    # Threading support
    reply_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        sender = self.user.username if self.user else (self.agent.name if self.agent else 'System')
        return f"{sender}: {self.content[:50]}..."
