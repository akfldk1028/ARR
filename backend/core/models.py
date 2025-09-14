from django.db import models
from django.contrib.auth.models import User
import uuid


class BaseModel(models.Model):
    """Base model with common fields"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(BaseModel):
    """Organization/Tenant model for multi-tenancy"""

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # Settings
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class OrganizationMember(BaseModel):
    """User membership in organizations"""

    ROLES = [
        ('owner', 'Owner'),
        ('admin', 'Administrator'),
        ('member', 'Member'),
        ('viewer', 'Viewer'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organization_memberships')
    role = models.CharField(max_length=20, choices=ROLES, default='member')
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['organization', 'user']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} in {self.organization.name} ({self.role})"


class Tag(BaseModel):
    """Generic tagging system"""

    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default='#0066cc')  # Hex color
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='tags', null=True, blank=True)

    class Meta:
        unique_together = ['name', 'organization']
        ordering = ['name']

    def __str__(self):
        return self.name
