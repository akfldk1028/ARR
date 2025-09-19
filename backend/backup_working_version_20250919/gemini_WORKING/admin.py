from django.contrib import admin
from .models import ChatSession, ChatMessage


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'title', 'is_active', 'created_at', 'message_count']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'user__username']
    readonly_fields = ['id', 'created_at', 'updated_at']

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Messages'


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'session', 'sender_type', 'message_type', 'content_preview', 'created_at', 'processing_time']
    list_filter = ['sender_type', 'message_type', 'created_at']
    search_fields = ['content', 'session__title', 'session__user__username']
    readonly_fields = ['id', 'created_at', 'processing_time']

    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'
