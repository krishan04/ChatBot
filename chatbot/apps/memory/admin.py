from django.contrib import admin
from .models import PrivateMemory, ConversationSummaryEmbedding


@admin.register(PrivateMemory)
class PrivateMemoryAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "kind", "pinned", "content_preview", "created_at"]
    list_filter = ["kind", "pinned", "created_at"]
    search_fields = ["user__email", "content"]
    readonly_fields = ["id", "embedding", "created_at", "updated_at"]

    def content_preview(self, obj):
        return obj.content[:80]
    content_preview.short_description = "Content"


@admin.register(ConversationSummaryEmbedding)
class ConversationSummaryEmbeddingAdmin(admin.ModelAdmin):
    list_display = ["id", "conversation", "created_at"]
    readonly_fields = ["id", "embedding", "created_at"]
