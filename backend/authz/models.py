from django.db import models
from django.contrib.auth.models import User
from core.models import BaseModel, Organization


class Role(BaseModel):
    """Role-based access control roles"""

    name = models.CharField(max_length=100)
    slug = models.SlugField()
    description = models.TextField(blank=True)

    # Scoped to organization
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='roles')

    # System roles (can't be deleted)
    is_system = models.BooleanField(default=False)

    class Meta:
        unique_together = ['organization', 'slug']
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class Permission(BaseModel):
    """Granular permissions for resources"""

    RESOURCE_TYPES = [
        ('agent', 'Agent'),
        ('conversation', 'Conversation'),
        ('room', 'Room'),
        ('task', 'Task'),
        ('billing', 'Billing'),
        ('organization', 'Organization'),
    ]

    ACTION_TYPES = [
        ('create', 'Create'),
        ('read', 'Read'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('execute', 'Execute'),
        ('manage', 'Manage'),
    ]

    name = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES)
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ['resource_type', 'action']
        ordering = ['resource_type', 'action']

    def __str__(self):
        return f"{self.action}_{self.resource_type}"


class RolePermission(BaseModel):
    """Many-to-many relationship between roles and permissions"""

    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    # Optional resource-level constraints
    resource_filter = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['role', 'permission']

    def __str__(self):
        return f"{self.role.name} - {self.permission}"


class UserRole(BaseModel):
    """User role assignments within organizations"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='role_assignments')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_assignments')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='user_roles')

    # Role assignment metadata
    assigned_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_roles')
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'role', 'organization']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.role.name} in {self.organization.name}"


class APIKey(BaseModel):
    """API key management for external integrations"""

    name = models.CharField(max_length=255)
    key_hash = models.CharField(max_length=128, unique=True)
    key_prefix = models.CharField(max_length=16)  # First 8 chars for identification

    # Ownership
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='api_keys')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_api_keys')

    # Access control
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used = models.DateTimeField(null=True, blank=True)

    # Permissions and limits
    permissions = models.ManyToManyField(Permission, blank=True, related_name='api_keys')
    rate_limit = models.IntegerField(default=1000)  # requests per hour

    # IP restrictions
    allowed_ips = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.key_prefix}...)"
