from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from core.models import BaseModel, Organization
from agents.models import Agent
from conversations.models import Room, Conversation
import json


class EventLog(BaseModel):
    """System-wide event logging for all activities"""

    EVENT_TYPES = [
        # User events
        ('user.login', 'User Login'),
        ('user.logout', 'User Logout'),
        ('user.register', 'User Registration'),
        ('user.profile_update', 'Profile Update'),

        # Agent events
        ('agent.created', 'Agent Created'),
        ('agent.updated', 'Agent Updated'),
        ('agent.activated', 'Agent Activated'),
        ('agent.deactivated', 'Agent Deactivated'),
        ('agent.message_sent', 'Agent Message Sent'),
        ('agent.message_received', 'Agent Message Received'),

        # Conversation events
        ('conversation.started', 'Conversation Started'),
        ('conversation.ended', 'Conversation Ended'),
        ('message.sent', 'Message Sent'),
        ('message.received', 'Message Received'),
        ('room.created', 'Room Created'),
        ('room.joined', 'Room Joined'),
        ('room.left', 'Room Left'),

        # Task events
        ('task.created', 'Task Created'),
        ('task.started', 'Task Started'),
        ('task.completed', 'Task Completed'),
        ('task.failed', 'Task Failed'),
        ('job.queued', 'Job Queued'),
        ('job.started', 'Job Started'),
        ('job.completed', 'Job Completed'),
        ('job.failed', 'Job Failed'),

        # System events
        ('system.startup', 'System Startup'),
        ('system.shutdown', 'System Shutdown'),
        ('service.registered', 'Service Registered'),
        ('service.health_check', 'Service Health Check'),
        ('error.occurred', 'Error Occurred'),
        ('warning.issued', 'Warning Issued'),

        # Security events
        ('auth.failed', 'Authentication Failed'),
        ('auth.success', 'Authentication Success'),
        ('permission.denied', 'Permission Denied'),
        ('api.rate_limit', 'API Rate Limit Hit'),

        # Business events
        ('billing.usage_recorded', 'Usage Recorded'),
        ('billing.invoice_generated', 'Invoice Generated'),
        ('organization.created', 'Organization Created'),
        ('organization.updated', 'Organization Updated'),
    ]

    SEVERITY_LEVELS = [
        ('debug', 'Debug'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]

    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='info')

    # Relationships
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='events', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='events')
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True, related_name='events')

    # Generic foreign key to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=36, blank=True)  # UUID string
    content_object = GenericForeignKey('content_type', 'object_id')

    # Event details
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Event data and context
    event_data = models.JSONField(default=dict, blank=True)  # Structured event data
    context = models.JSONField(default=dict, blank=True)  # Additional context information

    # Request/session information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    session_id = models.CharField(max_length=255, blank=True)
    request_id = models.CharField(max_length=255, blank=True)  # Unique request identifier

    # Error information (for error events)
    error_code = models.CharField(max_length=50, blank=True)
    stack_trace = models.TextField(blank=True)

    # Processing information
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', '-created_at']),
            models.Index(fields=['organization', 'event_type', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['severity', '-created_at']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        user_info = f" by {self.user.username}" if self.user else ""
        return f"{self.get_event_type_display()}{user_info} at {self.created_at}"

    def get_related_object_name(self):
        """Get a string representation of the related object"""
        if self.content_object:
            return str(self.content_object)
        return None


class AuditTrail(BaseModel):
    """Detailed audit trail for sensitive operations and compliance"""

    ACTION_TYPES = [
        ('create', 'Create'),
        ('read', 'Read'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('access', 'Access'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('publish', 'Publish'),
        ('archive', 'Archive'),
    ]

    # Who, what, when, where
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit_actions')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='audit_trails')

    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    resource_name = models.CharField(max_length=255)  # What was acted upon
    resource_id = models.CharField(max_length=36, blank=True)  # ID of the resource

    # Generic foreign key to the actual object
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=36, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    # Details
    description = models.TextField()

    # Before/after data for updates
    old_values = models.JSONField(default=dict, blank=True)  # Values before change
    new_values = models.JSONField(default=dict, blank=True)  # Values after change

    # Request context
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=500, blank=True)
    session_id = models.CharField(max_length=255, blank=True)
    request_id = models.CharField(max_length=255, blank=True)

    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)

    # Risk assessment
    risk_level = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        default='low'
    )

    # Compliance tags
    compliance_tags = models.JSONField(default=list, blank=True)  # e.g., ['GDPR', 'SOX', 'HIPAA']

    # Review status
    requires_review = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_audits')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['organization', 'action', '-created_at']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['risk_level', '-created_at']),
            models.Index(fields=['requires_review', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} {self.action} {self.resource_name} at {self.created_at}"

    @property
    def changes_summary(self):
        """Generate a summary of changes made"""
        if not self.old_values and not self.new_values:
            return None

        changes = []
        all_fields = set(self.old_values.keys()) | set(self.new_values.keys())

        for field in all_fields:
            old_val = self.old_values.get(field, '<not set>')
            new_val = self.new_values.get(field, '<removed>')
            if old_val != new_val:
                changes.append(f"{field}: {old_val} → {new_val}")

        return changes


class EventStream(BaseModel):
    """Real-time event streaming configuration and subscriptions"""

    STREAM_TYPES = [
        ('websocket', 'WebSocket'),
        ('sse', 'Server-Sent Events'),
        ('webhook', 'Webhook'),
        ('queue', 'Message Queue'),
    ]

    name = models.CharField(max_length=255)
    stream_type = models.CharField(max_length=20, choices=STREAM_TYPES)
    description = models.TextField(blank=True)

    # Relationships
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='event_streams')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_streams')

    # Stream configuration
    endpoint_url = models.URLField(blank=True)  # For webhooks
    event_types = models.JSONField(default=list, blank=True)  # Event types to stream
    filters = models.JSONField(default=dict, blank=True)  # Additional filters

    # Status and control
    is_active = models.BooleanField(default=True)
    max_retry_attempts = models.IntegerField(default=3)
    retry_delay_seconds = models.IntegerField(default=60)

    # Statistics
    events_sent = models.IntegerField(default=0)
    events_failed = models.IntegerField(default=0)
    last_event_at = models.DateTimeField(null=True, blank=True)

    # Configuration
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.stream_type})"


class EventSubscription(BaseModel):
    """User/agent subscriptions to specific events"""

    subscriber_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='event_subscriptions')
    subscriber_agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True, related_name='event_subscriptions')

    # Subscription details
    event_types = models.JSONField(default=list, blank=True)  # Event types to subscribe to
    filters = models.JSONField(default=dict, blank=True)  # Additional filters

    # Delivery configuration
    delivery_method = models.CharField(
        max_length=20,
        choices=[
            ('email', 'Email'),
            ('in_app', 'In-App Notification'),
            ('webhook', 'Webhook'),
            ('agent_trigger', 'Agent Trigger'),
        ],
        default='in_app'
    )

    delivery_config = models.JSONField(default=dict, blank=True)  # Method-specific config

    # Status
    is_active = models.BooleanField(default=True)

    # Statistics
    events_received = models.IntegerField(default=0)
    last_notification_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        subscriber = self.subscriber_user.username if self.subscriber_user else (
            self.subscriber_agent.name if self.subscriber_agent else 'Unknown'
        )
        return f"Subscription by {subscriber} via {self.delivery_method}"
