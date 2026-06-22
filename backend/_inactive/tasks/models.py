from django.db import models
from django.contrib.auth.models import User
from core.models import BaseModel, Organization
from agents.models import Agent
import json


class Task(BaseModel):
    """Individual task definition for job and workflow management"""

    TASK_TYPES = [
        ('sync', 'Synchronous'),
        ('async', 'Asynchronous'),
        ('scheduled', 'Scheduled'),
        ('webhook', 'Webhook Triggered'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('deprecated', 'Deprecated'),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField()
    task_type = models.CharField(max_length=20, choices=TASK_TYPES, default='async')
    description = models.TextField(blank=True)

    # Relationships
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='tasks')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tasks')
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True, related_name='tasks')

    # Task configuration
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Scheduling and timing
    timeout_seconds = models.IntegerField(default=3600)  # 1 hour default
    max_retries = models.IntegerField(default=3)
    retry_delay_seconds = models.IntegerField(default=60)

    # Configuration and input schema
    input_schema = models.JSONField(default=dict, blank=True)  # JSON schema for task inputs
    config = models.JSONField(default=dict, blank=True)  # Task-specific configuration

    # Dependencies
    depends_on = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='dependents')

    class Meta:
        unique_together = ['organization', 'slug']
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.task_type})"


class Job(BaseModel):
    """Job represents a collection of tasks or a workflow"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('retrying', 'Retrying'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Relationships
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='jobs')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_jobs')
    tasks = models.ManyToManyField(Task, through='JobTask', related_name='jobs')

    # Job control
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')

    # Timing
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Progress tracking
    total_tasks = models.IntegerField(default=0)
    completed_tasks = models.IntegerField(default=0)
    failed_tasks = models.IntegerField(default=0)

    # Configuration
    config = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    # Error handling
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.status}"

    @property
    def progress_percentage(self):
        if self.total_tasks == 0:
            return 0
        return (self.completed_tasks / self.total_tasks) * 100


class JobTask(BaseModel):
    """Through model for Job-Task relationship with execution order"""

    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)

    # Execution control
    order = models.IntegerField(default=0)  # Execution order within the job
    is_required = models.BooleanField(default=True)  # Whether job fails if this task fails

    # Status and configuration
    status = models.CharField(max_length=20, choices=Job.STATUS_CHOICES, default='pending')
    config_override = models.JSONField(default=dict, blank=True)  # Task-specific overrides for this job

    class Meta:
        unique_together = ['job', 'task']
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.job.name} -> {self.task.name} (#{self.order})"


class ExecutionRequest(BaseModel):
    """Request to execute a task or job with specific parameters"""

    REQUEST_TYPES = [
        ('task', 'Single Task'),
        ('job', 'Job/Workflow'),
        ('batch', 'Batch Request'),
    ]

    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('timeout', 'Timeout'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES)

    # Relationships
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='execution_requests')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='execution_requests')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True, related_name='execution_requests')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, null=True, blank=True, related_name='execution_requests')

    # Execution parameters
    input_data = models.JSONField(default=dict, blank=True)  # Input parameters for the task/job
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')

    # Status and timing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    queued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Results and error handling
    output_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)

    # Retry mechanism
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    retry_policy = models.JSONField(default=dict, blank=True)  # Custom retry configuration

    # Execution metadata
    execution_time = models.FloatField(null=True, blank=True)  # Execution time in seconds
    worker_id = models.CharField(max_length=255, blank=True)  # ID of worker that processed this

    # Configuration
    config = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['requested_by', 'status']),
        ]

    def __str__(self):
        target = self.task.name if self.task else (self.job.name if self.job else 'Unknown')
        return f"ExecutionRequest: {target} - {self.status}"

    @property
    def duration(self):
        """Calculate execution duration if completed"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
