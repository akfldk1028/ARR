from django.db import models
from django.contrib.auth.models import User
from core.models import BaseModel, Organization
from agents.models import Agent
from django.utils import timezone
from datetime import timedelta


class ServiceRegistration(BaseModel):
    """Service registry for microservices and external integrations"""

    SERVICE_TYPES = [
        ('agent', 'AI Agent Service'),
        ('api', 'REST API Service'),
        ('webhook', 'Webhook Service'),
        ('database', 'Database Service'),
        ('cache', 'Cache Service'),
        ('queue', 'Message Queue Service'),
        ('storage', 'Storage Service'),
        ('external', 'External Service'),
    ]

    STATUS_CHOICES = [
        ('healthy', 'Healthy'),
        ('unhealthy', 'Unhealthy'),
        ('degraded', 'Degraded'),
        ('unknown', 'Unknown'),
        ('maintenance', 'Maintenance'),
    ]

    name = models.CharField(max_length=255)
    service_id = models.CharField(max_length=100, unique=True)  # Unique service identifier
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPES)
    description = models.TextField(blank=True)

    # Relationships
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='services')
    registered_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='registered_services')
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True, related_name='services')

    # Service details
    version = models.CharField(max_length=50, default='1.0.0')
    base_url = models.URLField(blank=True)  # Primary service endpoint
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown')

    # Discovery and networking
    host = models.CharField(max_length=255, blank=True)
    port = models.IntegerField(null=True, blank=True)
    scheme = models.CharField(max_length=10, default='https')  # http/https
    path_prefix = models.CharField(max_length=255, default='/', blank=True)

    # Health check configuration
    health_check_url = models.CharField(max_length=500, blank=True)  # Relative to base_url
    health_check_interval = models.IntegerField(default=30)  # seconds
    health_check_timeout = models.IntegerField(default=10)  # seconds
    health_check_retries = models.IntegerField(default=3)

    # Service metadata
    tags = models.JSONField(default=list, blank=True)  # Service tags for filtering/grouping
    metadata = models.JSONField(default=dict, blank=True)  # Additional service metadata
    dependencies = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='dependents')

    # Configuration
    config = models.JSONField(default=dict, blank=True)  # Service-specific configuration
    environment = models.CharField(max_length=50, default='production')  # dev/staging/production

    # Status tracking
    last_health_check = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['service_type', 'status']),
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['environment', 'status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.service_type}) - {self.status}"

    @property
    def full_url(self):
        """Construct full service URL"""
        if self.base_url:
            return self.base_url
        if self.host and self.port:
            path = self.path_prefix.strip('/') or ''
            return f"{self.scheme}://{self.host}:{self.port}/{path}".rstrip('/')
        return None

    @property
    def full_health_check_url(self):
        """Construct full health check URL"""
        base = self.full_url
        if base and self.health_check_url:
            return f"{base.rstrip('/')}/{self.health_check_url.lstrip('/')}"
        return None

    def is_healthy(self):
        """Check if service is considered healthy based on recent health checks"""
        if not self.last_health_check:
            return False

        # Service is healthy if last check was successful and within expected interval
        max_age = timezone.now() - timedelta(seconds=self.health_check_interval * 2)
        return (self.status == 'healthy' and
                self.last_health_check > max_age)


class HealthCheck(BaseModel):
    """Health check results for registered services"""

    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failure', 'Failure'),
        ('timeout', 'Timeout'),
        ('error', 'Error'),
    ]

    service = models.ForeignKey(ServiceRegistration, on_delete=models.CASCADE, related_name='health_checks')

    # Check details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    response_time = models.FloatField(null=True, blank=True)  # Response time in seconds
    status_code = models.IntegerField(null=True, blank=True)  # HTTP status code

    # Check results
    response_body = models.TextField(blank=True)
    error_message = models.TextField(blank=True)

    # Metadata
    checked_from = models.CharField(max_length=255, blank=True)  # IP or hostname of checker
    user_agent = models.CharField(max_length=255, blank=True)

    # Additional data
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['service', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"HealthCheck for {self.service.name} - {self.status} at {self.created_at}"

    @property
    def is_successful(self):
        """Check if this health check was successful"""
        return self.status == 'success'


class ServiceEndpoint(BaseModel):
    """Individual endpoints exposed by a service"""

    METHOD_CHOICES = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
        ('OPTIONS', 'OPTIONS'),
        ('HEAD', 'HEAD'),
    ]

    service = models.ForeignKey(ServiceRegistration, on_delete=models.CASCADE, related_name='endpoints')

    # Endpoint details
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default='GET')
    name = models.CharField(max_length=255, blank=True)  # Human-readable endpoint name
    description = models.TextField(blank=True)

    # API specification
    input_schema = models.JSONField(default=dict, blank=True)  # Request schema
    output_schema = models.JSONField(default=dict, blank=True)  # Response schema

    # Endpoint metadata
    tags = models.JSONField(default=list, blank=True)
    is_public = models.BooleanField(default=False)
    requires_auth = models.BooleanField(default=True)
    rate_limit = models.IntegerField(null=True, blank=True)  # Requests per minute

    # Configuration
    timeout = models.IntegerField(default=30)  # Timeout in seconds
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['service', 'path', 'method']
        ordering = ['path', 'method']

    def __str__(self):
        name = self.name or f"{self.method} {self.path}"
        return f"{self.service.name}: {name}"

    @property
    def full_url(self):
        """Construct full endpoint URL"""
        base_url = self.service.full_url
        if base_url:
            return f"{base_url.rstrip('/')}/{self.path.lstrip('/')}"
        return None


class ServiceDependency(BaseModel):
    """Track dependencies between services"""

    DEPENDENCY_TYPES = [
        ('required', 'Required'),
        ('optional', 'Optional'),
        ('weak', 'Weak Dependency'),
    ]

    service = models.ForeignKey(ServiceRegistration, on_delete=models.CASCADE, related_name='service_dependencies')
    depends_on = models.ForeignKey(ServiceRegistration, on_delete=models.CASCADE, related_name='dependent_services')

    dependency_type = models.CharField(max_length=20, choices=DEPENDENCY_TYPES, default='required')
    description = models.TextField(blank=True)

    # Configuration
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['service', 'depends_on']
        ordering = ['dependency_type', 'created_at']

    def __str__(self):
        return f"{self.service.name} depends on {self.depends_on.name} ({self.dependency_type})"
