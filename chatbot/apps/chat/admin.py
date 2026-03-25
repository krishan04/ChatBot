from django.contrib import admin
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ["id", "role", "content", "token_count", "created_at"]
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "title", "message_count", "last_active_at"]
    list_filter = ["created_at"]
    search_fields = ["user__email", "title"]
    readonly_fields = ["id", "created_at", "last_active_at"]
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "conversation", "role", "content_preview", "token_count", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["content", "conversation__user__email"]
    readonly_fields = ["id", "created_at"]

    def content_preview(self, obj):
        return obj.content[:80]
    content_preview.short_description = "Content"
