from django.db import models
from django.contrib.auth.models import User
from core.models import BaseModel, Organization
from agents.models import Agent
from conversations.models import Room, Conversation
from tasks.models import Task, Job, ExecutionRequest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import json


class UsageMetric(BaseModel):
    """Track usage metrics for billing purposes"""

    METRIC_TYPES = [
        ('agent_message', 'Agent Message'),
        ('user_message', 'User Message'),
        ('conversation_minute', 'Conversation Minute'),
        ('task_execution', 'Task Execution'),
        ('job_execution', 'Job Execution'),
        ('api_call', 'API Call'),
        ('storage_gb', 'Storage GB'),
        ('bandwidth_gb', 'Bandwidth GB'),
        ('compute_hour', 'Compute Hour'),
        ('model_token', 'Model Token'),
        ('file_upload', 'File Upload'),
        ('file_download', 'File Download'),
        ('webhook_call', 'Webhook Call'),
        ('mcp_request', 'MCP Request'),
        ('custom', 'Custom Metric'),
    ]

    AGGREGATION_TYPES = [
        ('count', 'Count'),
        ('sum', 'Sum'),
        ('duration', 'Duration'),
        ('size', 'Size'),
        ('rate', 'Rate'),
    ]

    metric_type = models.CharField(max_length=30, choices=METRIC_TYPES)
    aggregation_type = models.CharField(max_length=20, choices=AGGREGATION_TYPES, default='count')

    # Relationships
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='usage_metrics')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='usage_metrics')
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True, related_name='usage_metrics')

    # Related resources (optional)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, null=True, blank=True, related_name='usage_metrics')
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, null=True, blank=True, related_name='usage_metrics')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True, related_name='usage_metrics')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, null=True, blank=True, related_name='usage_metrics')
    execution_request = models.ForeignKey(ExecutionRequest, on_delete=models.CASCADE, null=True, blank=True, related_name='usage_metrics')

    # Metric data
    quantity = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal('0'))
    unit = models.CharField(max_length=50, default='count')  # e.g., 'messages', 'minutes', 'tokens', 'GB'

    # Timing
    recorded_at = models.DateTimeField(default=timezone.now)
    period_start = models.DateTimeField(null=True, blank=True)  # For time-based metrics
    period_end = models.DateTimeField(null=True, blank=True)

    # Additional context
    resource_id = models.CharField(max_length=255, blank=True)  # Generic resource identifier
    resource_type = models.CharField(max_length=50, blank=True)  # Type of resource
    metadata = models.JSONField(default=dict, blank=True)  # Additional metric metadata

    # Cost-related fields
    unit_price = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    total_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)

    # Processing status
    is_billable = models.BooleanField(default=True)
    is_processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['organization', 'metric_type', '-recorded_at']),
            models.Index(fields=['user', 'metric_type', '-recorded_at']),
            models.Index(fields=['agent', 'metric_type', '-recorded_at']),
            models.Index(fields=['is_billable', 'is_processed']),
            models.Index(fields=['period_start', 'period_end']),
        ]

    def __str__(self):
        user_info = f" ({self.user.username})" if self.user else ""
        return f"{self.get_metric_type_display()}: {self.quantity} {self.unit}{user_info}"

    def calculate_cost(self, pricing_rules=None):
        """Calculate cost based on quantity and unit price"""
        if self.unit_price and self.quantity:
            return self.quantity * self.unit_price
        return Decimal('0')


class BillingPeriod(BaseModel):
    """Define billing periods for organizations"""

    PERIOD_TYPES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('pending', 'Pending'),
        ('cancelled', 'Cancelled'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='billing_periods')

    period_type = models.CharField(max_length=20, choices=PERIOD_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Period dates
    start_date = models.DateField()
    end_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)

    # Financial summary
    total_usage = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal('0'))
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    final_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))

    # Processing status
    is_processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)

    # Invoice details
    invoice_number = models.CharField(max_length=100, unique=True, blank=True)
    invoice_generated_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    # Configuration
    config = models.JSONField(default=dict, blank=True)  # Period-specific configuration
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['organization', 'start_date', 'end_date']
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.organization.name} - {self.start_date} to {self.end_date} ({self.status})"

    @property
    def is_current(self):
        """Check if this is the current active period"""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date and self.status == 'active'

    def calculate_totals(self):
        """Calculate period totals from usage metrics"""
        usage_metrics = UsageMetric.objects.filter(
            organization=self.organization,
            recorded_at__gte=self.start_date,
            recorded_at__lt=self.end_date + timedelta(days=1),
            is_billable=True
        )

        self.total_cost = sum(
            metric.total_cost or Decimal('0') for metric in usage_metrics
        )

        self.final_amount = self.total_cost + self.tax_amount - self.discount_amount


class CostCalculation(BaseModel):
    """Cost calculation rules and pricing for different usage types"""

    CALCULATION_TYPES = [
        ('fixed', 'Fixed Price'),
        ('tiered', 'Tiered Pricing'),
        ('volume', 'Volume Discount'),
        ('usage_based', 'Usage Based'),
        ('subscription', 'Subscription'),
        ('pay_as_you_go', 'Pay As You Go'),
    ]

    name = models.CharField(max_length=255)
    calculation_type = models.CharField(max_length=20, choices=CALCULATION_TYPES)
    description = models.TextField(blank=True)

    # Relationships
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='cost_calculations')

    # Pricing rules
    metric_type = models.CharField(max_length=30, choices=UsageMetric.METRIC_TYPES, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal('0'))
    minimum_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    maximum_charge = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Tiered pricing configuration
    pricing_tiers = models.JSONField(default=list, blank=True)  # [{"min": 0, "max": 100, "price": 0.10}, ...]

    # Validity period
    effective_from = models.DateField(default=timezone.now)
    effective_until = models.DateField(null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)

    # Configuration
    config = models.JSONField(default=dict, blank=True)  # Additional pricing configuration

    class Meta:
        ordering = ['-effective_from']
        indexes = [
            models.Index(fields=['organization', 'metric_type', 'is_active']),
            models.Index(fields=['effective_from', 'effective_until']),
        ]

    def __str__(self):
        org_info = f" for {self.organization.name}" if self.organization else ""
        return f"{self.name} ({self.calculation_type}){org_info}"

    def calculate_cost(self, quantity, metadata=None):
        """Calculate cost for given quantity using this pricing rule"""
        if not self.is_active:
            return Decimal('0')

        quantity = Decimal(str(quantity))

        if self.calculation_type == 'fixed':
            return self.unit_price

        elif self.calculation_type == 'usage_based':
            cost = quantity * self.unit_price
            if self.minimum_charge and cost < self.minimum_charge:
                cost = self.minimum_charge
            if self.maximum_charge and cost > self.maximum_charge:
                cost = self.maximum_charge
            return cost

        elif self.calculation_type == 'tiered':
            return self._calculate_tiered_cost(quantity)

        elif self.calculation_type == 'volume':
            return self._calculate_volume_cost(quantity)

        # Default to usage-based
        return quantity * self.unit_price

    def _calculate_tiered_cost(self, quantity):
        """Calculate cost using tiered pricing"""
        total_cost = Decimal('0')
        remaining_quantity = quantity

        for tier in self.pricing_tiers:
            tier_min = Decimal(str(tier.get('min', 0)))
            tier_max = Decimal(str(tier.get('max', 0))) if tier.get('max') else None
            tier_price = Decimal(str(tier.get('price', 0)))

            if remaining_quantity <= 0:
                break

            if tier_max:
                tier_quantity = min(remaining_quantity, tier_max - tier_min)
            else:
                tier_quantity = remaining_quantity

            tier_cost = tier_quantity * tier_price
            total_cost += tier_cost
            remaining_quantity -= tier_quantity

        return total_cost

    def _calculate_volume_cost(self, quantity):
        """Calculate cost using volume discounts"""
        # Find applicable tier
        applicable_tier = None
        for tier in self.pricing_tiers:
            tier_min = Decimal(str(tier.get('min', 0)))
            if quantity >= tier_min:
                applicable_tier = tier
            else:
                break

        if applicable_tier:
            price = Decimal(str(applicable_tier.get('price', self.unit_price)))
            return quantity * price

        return quantity * self.unit_price


class BillingAlert(BaseModel):
    """Billing alerts and notifications for usage thresholds"""

    ALERT_TYPES = [
        ('usage_threshold', 'Usage Threshold'),
        ('cost_threshold', 'Cost Threshold'),
        ('quota_exceeded', 'Quota Exceeded'),
        ('payment_due', 'Payment Due'),
        ('payment_failed', 'Payment Failed'),
        ('invoice_generated', 'Invoice Generated'),
    ]

    ALERT_LEVELS = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='billing_alerts')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='billing_alerts')

    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    alert_level = models.CharField(max_length=20, choices=ALERT_LEVELS, default='info')

    # Alert configuration
    metric_type = models.CharField(max_length=30, choices=UsageMetric.METRIC_TYPES, blank=True)
    threshold_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    current_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)

    # Alert details
    title = models.CharField(max_length=255)
    message = models.TextField()

    # Status
    is_active = models.BooleanField(default=True)
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='acknowledged_alerts')
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    # Related objects
    billing_period = models.ForeignKey(BillingPeriod, on_delete=models.CASCADE, null=True, blank=True, related_name='alerts')

    # Configuration
    config = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'alert_type', '-created_at']),
            models.Index(fields=['is_active', 'is_acknowledged']),
            models.Index(fields=['alert_level', '-created_at']),
        ]

    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.title} ({self.alert_level})"


class BillingConfig(BaseModel):
    """Billing configuration for organizations"""

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='billing_config')

    # Billing settings
    currency = models.CharField(max_length=3, default='USD')  # ISO currency code
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0'))  # e.g., 0.0825 for 8.25%

    # Payment settings
    payment_terms_days = models.IntegerField(default=30)  # Net payment terms
    grace_period_days = models.IntegerField(default=7)  # Grace period before service suspension

    # Thresholds and limits
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    usage_alert_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('80'))  # 80%
    cost_alert_threshold = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Invoice settings
    invoice_prefix = models.CharField(max_length=10, default='INV')
    next_invoice_number = models.IntegerField(default=1)

    # Notification settings
    billing_email = models.EmailField(blank=True)
    send_usage_alerts = models.BooleanField(default=True)
    send_invoice_notifications = models.BooleanField(default=True)
    send_payment_reminders = models.BooleanField(default=True)

    # Auto-billing settings
    auto_suspend_on_overdue = models.BooleanField(default=False)
    auto_resume_on_payment = models.BooleanField(default=True)

    # Configuration
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Billing Configuration'
        verbose_name_plural = 'Billing Configurations'

    def __str__(self):
        return f"Billing Config for {self.organization.name}"

    def generate_next_invoice_number(self):
        """Generate and increment invoice number"""
        invoice_number = f"{self.invoice_prefix}-{self.next_invoice_number:06d}"
        self.next_invoice_number += 1
        self.save(update_fields=['next_invoice_number'])
        return invoice_number
