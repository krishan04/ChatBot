from rest_framework import serializers
from .models import PrivateMemory


class PrivateMemorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PrivateMemory
        fields = ["id", "content", "kind", "pinned", "source_message", "created_at"]
        read_only_fields = ["id", "created_at"]