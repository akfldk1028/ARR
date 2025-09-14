from django.db import models
from django.contrib.auth.models import User
from core.models import BaseModel, Organization, Tag


class Agent(BaseModel):
    """AI Agent definitions"""

    AGENT_TYPES = [
        ('gemini', 'Google Gemini'),
        ('gpt', 'OpenAI GPT'),
        ('claude', 'Anthropic Claude'),
        ('custom', 'Custom Agent'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Maintenance'),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField()
    agent_type = models.CharField(max_length=20, choices=AGENT_TYPES)
    description = models.TextField(blank=True)

    # Relationships
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='agents')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    tags = models.ManyToManyField(Tag, blank=True, related_name='agents')

    # Agent configuration
    model_name = models.CharField(max_length=255)  # e.g., "models/gemini-2.0-flash-exp"
    system_prompt = models.TextField(default="You are a helpful AI assistant.")
    capabilities = models.JSONField(default=list)  # ["text", "image", "audio", "video"]

    # Status and limits
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    max_concurrent_sessions = models.IntegerField(default=10)
    rate_limit_per_minute = models.IntegerField(default=60)

    # Configuration
    config = models.JSONField(default=dict, blank=True)  # Store agent-specific settings

    class Meta:
        unique_together = ['organization', 'slug']
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.agent_type})"
