from django.db import models
from django.contrib.auth.models import User
from core.models import BaseModel, Organization
from agents.models import Agent
from django.utils import timezone
from datetime import timedelta
import json


class MCPConnector(BaseModel):
    """MCP (Model Context Protocol) connector for external integrations"""

    CONNECTOR_TYPES = [
        ('api', 'REST API Connector'),
        ('database', 'Database Connector'),
        ('file', 'File System Connector'),
        ('webhook', 'Webhook Connector'),
        ('queue', 'Message Queue Connector'),
        ('websocket', 'WebSocket Connector'),
        ('grpc', 'gRPC Connector'),
        ('custom', 'Custom Connector'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
        ('maintenance', 'Maintenance'),
        ('testing', 'Testing'),
    ]

    PROTOCOL_VERSIONS = [
        ('1.0', 'MCP 1.0'),
        ('1.1', 'MCP 1.1'),
        ('2.0', 'MCP 2.0'),
    ]

    name = models.CharField(max_length=255)
    connector_id = models.CharField(max_length=100, unique=True)
    connector_type = models.CharField(max_length=20, choices=CONNECTOR_TYPES)
    description = models.TextField(blank=True)

    # Relationships
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='mcp_connectors')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_connectors')
    agents = models.ManyToManyField(Agent, through='MCPAgentConnection', related_name='mcp_connectors')

    # Protocol details
    protocol_version = models.CharField(max_length=10, choices=PROTOCOL_VERSIONS, default='1.0')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')

    # Connection configuration
    endpoint_url = models.URLField(blank=True)
    authentication_type = models.CharField(
        max_length=20,
        choices=[
            ('none', 'None'),
            ('api_key', 'API Key'),
            ('bearer_token', 'Bearer Token'),
            ('basic_auth', 'Basic Auth'),
            ('oauth2', 'OAuth 2.0'),
            ('custom', 'Custom'),
        ],
        default='none'
    )
    auth_config = models.JSONField(default=dict, blank=True)  # Authentication configuration

    # Connection settings
    timeout_seconds = models.IntegerField(default=30)
    max_retries = models.IntegerField(default=3)
    retry_delay_seconds = models.IntegerField(default=5)

    # Health monitoring
    health_check_endpoint = models.CharField(max_length=500, blank=True)
    health_check_interval = models.IntegerField(default=300)  # 5 minutes
    last_health_check = models.DateTimeField(null=True, blank=True)

    # Capabilities and features
    supported_operations = models.JSONField(default=list, blank=True)  # List of supported operations
    supported_formats = models.JSONField(default=list, blank=True)  # Supported data formats
    features = models.JSONField(default=dict, blank=True)  # Feature flags and settings

    # Configuration and metadata
    config = models.JSONField(default=dict, blank=True)  # Connector-specific configuration
    metadata = models.JSONField(default=dict, blank=True)  # Additional metadata
    tags = models.JSONField(default=list, blank=True)  # Tags for organization

    # Statistics
    total_requests = models.IntegerField(default=0)
    successful_requests = models.IntegerField(default=0)
    failed_requests = models.IntegerField(default=0)
    last_request_at = models.DateTimeField(null=True, blank=True)

    # Error tracking
    last_error = models.TextField(blank=True)
    error_count = models.IntegerField(default=0)
    last_error_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['connector_type', 'status']),
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['created_by', '-created_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.connector_type}) - {self.status}"

    @property
    def success_rate(self):
        """Calculate success rate percentage"""
        if self.total_requests == 0:
            return 0
        return (self.successful_requests / self.total_requests) * 100

    def is_healthy(self):
        """Check if connector is considered healthy"""
        if self.status != 'active':
            return False

        # Check if recent health check passed
        if self.last_health_check:
            max_age = timezone.now() - timedelta(seconds=self.health_check_interval * 2)
            return self.last_health_check > max_age

        return True


class MCPService(BaseModel):
    """Individual MCP services provided by connectors"""

    SERVICE_TYPES = [
        ('data_query', 'Data Query'),
        ('data_insert', 'Data Insert'),
        ('data_update', 'Data Update'),
        ('data_delete', 'Data Delete'),
        ('file_read', 'File Read'),
        ('file_write', 'File Write'),
        ('notification', 'Notification'),
        ('computation', 'Computation'),
        ('translation', 'Translation'),
        ('validation', 'Validation'),
        ('transformation', 'Transformation'),
    ]

    connector = models.ForeignKey(MCPConnector, on_delete=models.CASCADE, related_name='services')

    name = models.CharField(max_length=255)
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPES)
    description = models.TextField(blank=True)

    # Service specification
    endpoint_path = models.CharField(max_length=500, blank=True)  # Relative to connector endpoint
    http_method = models.CharField(
        max_length=10,
        choices=[
            ('GET', 'GET'),
            ('POST', 'POST'),
            ('PUT', 'PUT'),
            ('PATCH', 'PATCH'),
            ('DELETE', 'DELETE'),
        ],
        default='POST'
    )

    # Schema definitions
    input_schema = models.JSONField(default=dict, blank=True)  # JSON schema for input
    output_schema = models.JSONField(default=dict, blank=True)  # JSON schema for output
    error_schema = models.JSONField(default=dict, blank=True)  # JSON schema for errors

    # Service configuration
    is_enabled = models.BooleanField(default=True)
    requires_auth = models.BooleanField(default=True)
    is_cacheable = models.BooleanField(default=False)
    cache_duration = models.IntegerField(default=300)  # Cache duration in seconds

    # Rate limiting
    rate_limit_per_minute = models.IntegerField(null=True, blank=True)
    rate_limit_per_hour = models.IntegerField(null=True, blank=True)

    # Execution settings
    timeout_seconds = models.IntegerField(default=30)
    max_retries = models.IntegerField(default=3)

    # Documentation
    documentation_url = models.URLField(blank=True)
    examples = models.JSONField(default=list, blank=True)  # Example requests/responses

    # Statistics
    total_calls = models.IntegerField(default=0)
    successful_calls = models.IntegerField(default=0)
    failed_calls = models.IntegerField(default=0)
    average_response_time = models.FloatField(default=0.0)  # In seconds
    last_call_at = models.DateTimeField(null=True, blank=True)

    # Configuration and metadata
    config = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['connector', 'name']
        ordering = ['name']

    def __str__(self):
        return f"{self.connector.name}: {self.name} ({self.service_type})"

    @property
    def success_rate(self):
        """Calculate success rate percentage"""
        if self.total_calls == 0:
            return 0
        return (self.successful_calls / self.total_calls) * 100

    @property
    def full_endpoint_url(self):
        """Construct full endpoint URL"""
        if self.connector.endpoint_url and self.endpoint_path:
            base = self.connector.endpoint_url.rstrip('/')
            path = self.endpoint_path.lstrip('/')
            return f"{base}/{path}"
        return None


class MCPAgentConnection(BaseModel):
    """Through model for Agent-MCPConnector relationship"""

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE)
    connector = models.ForeignKey(MCPConnector, on_delete=models.CASCADE)

    # Connection settings
    is_enabled = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)  # Higher values have higher priority

    # Access control
    allowed_services = models.JSONField(default=list, blank=True)  # Service names agent can use
    restricted_services = models.JSONField(default=list, blank=True)  # Service names agent cannot use

    # Configuration overrides
    config_override = models.JSONField(default=dict, blank=True)  # Agent-specific connector config

    # Usage statistics
    requests_made = models.IntegerField(default=0)
    last_request_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['agent', 'connector']
        ordering = ['-priority', 'created_at']

    def __str__(self):
        return f"{self.agent.name} -> {self.connector.name}"


class MCPRequest(BaseModel):
    """Individual MCP service requests and responses"""

    REQUEST_TYPES = [
        ('service_call', 'Service Call'),
        ('health_check', 'Health Check'),
        ('capability_query', 'Capability Query'),
        ('batch_request', 'Batch Request'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
        ('cancelled', 'Cancelled'),
    ]

    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES, default='service_call')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Relationships
    connector = models.ForeignKey(MCPConnector, on_delete=models.CASCADE, related_name='requests')
    service = models.ForeignKey(MCPService, on_delete=models.CASCADE, null=True, blank=True, related_name='requests')
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True, related_name='mcp_requests')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='mcp_requests')

    # Request details
    request_id = models.CharField(max_length=255, unique=True)  # Unique request identifier
    request_data = models.JSONField(default=dict, blank=True)
    request_headers = models.JSONField(default=dict, blank=True)

    # Response details
    response_data = models.JSONField(default=dict, blank=True)
    response_headers = models.JSONField(default=dict, blank=True)
    response_status_code = models.IntegerField(null=True, blank=True)

    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    response_time = models.FloatField(null=True, blank=True)  # In seconds

    # Error handling
    error_message = models.TextField(blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    retry_count = models.IntegerField(default=0)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    trace_id = models.CharField(max_length=255, blank=True)  # For distributed tracing

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['connector', 'status', '-created_at']),
            models.Index(fields=['service', '-created_at']),
            models.Index(fields=['agent', '-created_at']),
            models.Index(fields=['request_id']),
            models.Index(fields=['trace_id']),
        ]

    def __str__(self):
        service_name = self.service.name if self.service else 'N/A'
        return f"MCPRequest: {self.connector.name}/{service_name} - {self.status}"

    @property
    def duration(self):
        """Calculate request duration if completed"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return self.response_time


class MCPWebhook(BaseModel):
    """Webhook endpoints for MCP event notifications"""

    connector = models.ForeignKey(MCPConnector, on_delete=models.CASCADE, related_name='webhooks')

    name = models.CharField(max_length=255)
    endpoint_url = models.URLField()
    secret_key = models.CharField(max_length=255, blank=True)  # For webhook verification

    # Event configuration
    event_types = models.JSONField(default=list, blank=True)  # Events to listen for
    filters = models.JSONField(default=dict, blank=True)  # Additional event filters

    # Status and control
    is_active = models.BooleanField(default=True)
    max_retry_attempts = models.IntegerField(default=3)
    retry_delay_seconds = models.IntegerField(default=60)

    # Statistics
    events_sent = models.IntegerField(default=0)
    events_failed = models.IntegerField(default=0)
    last_event_at = models.DateTimeField(null=True, blank=True)

    # Configuration
    headers = models.JSONField(default=dict, blank=True)  # Custom headers to send
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['connector', 'name']
        ordering = ['name']

    def __str__(self):
        return f"Webhook: {self.connector.name}/{self.name}"
