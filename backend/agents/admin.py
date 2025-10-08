from django.contrib import admin
from .models import Agent


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ['slug', 'name', 'agent_type', 'organization', 'created_by', 'status', 'created_at']
    list_filter = ['agent_type', 'status', 'organization']
    search_fields = ['slug', 'name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']

    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'slug', 'name', 'description', 'agent_type')
        }),
        ('Organization', {
            'fields': ('organization', 'created_by')
        }),
        ('Configuration', {
            'fields': ('model_name', 'system_prompt', 'capabilities', 'config'),
            'classes': ('collapse',)
        }),
        ('Limits', {
            'fields': ('rate_limit_per_minute', 'max_concurrent_sessions', 'status'),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
