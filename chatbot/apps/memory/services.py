"""
Memory service layer.

Two responsibilities:
  1. embed_and_save_memory  — take user text, embed it, write to DB
  2. retrieve_memories      — given a query, return ranked context string
                              from both private + shared namespaces
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from pgvector.django import CosineDistance

from .models import PrivateMemory
from apps.knowledge.models import SharedChunk

if TYPE_CHECKING:
    from apps.accounts.models import User


def get_embedding(text: str) -> list[float]:
    """
    Call OpenAI embeddings API and return a 1536-dim float list.
    Uses text-embedding-3-small — cheap, fast, good enough for memory retrieval.
    """
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=text.strip(),
    )
    return response.data[0].embedding


def embed_and_save_memory(
    user: "User",
    content: str,
    kind: str = PrivateMemory.KIND_FACT,
    source_message_id=None,
) -> PrivateMemory:
    """
    Embed the given text and persist it as a PrivateMemory row.
    Called when user explicitly clicks 'Save to memory' in the UI.
    """
    embedding = get_embedding(content)
    memory = PrivateMemory.objects.create(
        user=user,
        content=content,
        kind=kind,
        embedding=embedding,
        source_message_id=source_message_id,
    )
    return memory


def retrieve_memories(user: "User", query: str) -> str:
    """
    Dual-namespace retrieval:
      1. Embed the query
      2. Search private memories   (top-K, cosine similarity, user-scoped)
      3. Search shared KB chunks   (top-K, cosine similarity, all users)
      4. Merge — private memories get a 1.3× relevance boost
      5. Return top MEMORY_TOP_K results as a formatted string

    Returns an empty string if no relevant memories are found.
    """
    top_k = settings.MEMORY_TOP_K
    query_embedding = get_embedding(query)

    # ── Private memories ──────────────────────────────────────────────────────
    private_results = (
        PrivateMemory.objects
        .filter(user=user)
        .annotate(distance=CosineDistance("embedding", query_embedding))
        .order_by("distance")
        .values("content", "kind", "distance")[:top_k]
    )

    # ── Shared knowledge chunks ───────────────────────────────────────────────
    shared_results = (
        SharedChunk.objects
        .filter(knowledge__is_active=True)
        .annotate(distance=CosineDistance("embedding", query_embedding))
        .order_by("distance")
        .values("content", "knowledge__title", "distance")[:top_k]
    )

    # ── Merge and re-rank ─────────────────────────────────────────────────────
    # Lower distance = more similar. Apply boost to private by reducing distance.
    PRIVATE_BOOST = 0.7   # multiply distance by 0.7 → effectively ranks higher
    RELEVANCE_THRESHOLD = 0.5  # discard anything with distance > 0.5 (not relevant)

    candidates = []

    for row in private_results:
        boosted = row["distance"] * PRIVATE_BOOST
        if boosted < RELEVANCE_THRESHOLD:
            candidates.append({
                "text": f"[{row['kind'].capitalize()}] {row['content']}",
                "score": boosted,
                "source": "private",
            })

    for row in shared_results:
        if row["distance"] < RELEVANCE_THRESHOLD:
            candidates.append({
                "text": f"[Knowledge: {row['knowledge__title']}] {row['content']}",
                "score": row["distance"],
                "source": "shared",
            })

    # Sort by score ascending (lower = better), keep top_k
    candidates.sort(key=lambda x: x["score"])
    top = candidates[:top_k]

    if not top:
        return ""

    lines = ["Relevant context from memory:"]
    for item in top:
        lines.append(f"  • {item['text']}")
    return "\n".join(lines)