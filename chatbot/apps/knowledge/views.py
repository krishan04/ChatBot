from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from .models import SharedKnowledge


class SharedKnowledgeSerializer(serializers.ModelSerializer):
    chunk_count = serializers.SerializerMethodField()

    class Meta:
        model = SharedKnowledge
        fields = ["id", "title", "category", "chunk_count", "updated_at"]

    def get_chunk_count(self, obj):
        return obj.chunks.count()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def knowledge_list(request):
    """List active shared knowledge documents (read-only for users)."""
    qs = SharedKnowledge.objects.filter(is_active=True)
    return Response(SharedKnowledgeSerializer(qs, many=True).data)