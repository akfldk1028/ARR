from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class ChatSession(models.Model):
    """Simple chat session tracking"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    # Session details
    title = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        user_name = self.user.username if self.user else 'Anonymous'
        return f"Session {self.id.hex[:8]} - {user_name}"


class ChatMessage(models.Model):
    """Chat messages in sessions"""

    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('audio', 'Audio'),
        ('system', 'System'),
    ]

    SENDER_TYPES = [
        ('user', 'User'),
        ('assistant', 'AI Assistant'),
        ('system', 'System'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')

    # Message content
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()
    sender_type = models.CharField(max_length=20, choices=SENDER_TYPES)

    # Message metadata
    metadata = models.JSONField(default=dict, blank=True)  # Response times, model info, etc.
    processing_time = models.FloatField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender_type}: {self.content[:50]}..."
