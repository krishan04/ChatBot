from django.contrib import admin
from .models import SharedKnowledge, SharedChunk


class SharedChunkInline(admin.TabularInline):
    model = SharedChunk
    extra = 0
    readonly_fields = ["id", "chunk_index", "content", "created_at"]
    can_delete = True


@admin.register(SharedKnowledge)
class SharedKnowledgeAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "is_active", "chunk_count", "updated_at"]
    list_filter = ["category", "is_active"]
    search_fields = ["title"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [SharedChunkInline]

    def chunk_count(self, obj):
        return obj.chunks.count()
    chunk_count.short_description = "Chunks"


@admin.register(SharedChunk)
class SharedChunkAdmin(admin.ModelAdmin):
    list_display = ["id", "knowledge", "chunk_index", "content_preview", "created_at"]
    list_filter = ["knowledge"]
    readonly_fields = ["id", "embedding", "created_at"]

    def content_preview(self, obj):
        return obj.content[:80]
    content_preview.short_description = "Content"
