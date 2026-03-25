"""
Management command: ingest_knowledge

Usage:
    python manage.py ingest_knowledge --file path/to/doc.txt --title "Product FAQ" --category faq
    python manage.py ingest_knowledge --file path/to/guide.txt --title "Onboarding Guide" --category guide

Splits the document into ~400-token chunks, embeds each one,
and saves them to the knowledge_chunk table.

Run this whenever you add or update shared knowledge content.
"""

import os
from django.core.management.base import BaseCommand, CommandError
from apps.knowledge.models import SharedKnowledge, SharedChunk
from apps.memory.services import get_embedding


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """
    Split text into overlapping word-level chunks.
    chunk_size and overlap are in approximate tokens (words).
    """
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


class Command(BaseCommand):
    help = "Ingest a text file into the shared knowledge base with embeddings"

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to text file")
        parser.add_argument("--title", required=True, help="Document title")
        parser.add_argument(
            "--category",
            choices=["faq", "guide", "policy", "other"],
            default="other",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete existing chunks for this title before ingesting",
        )

    def handle(self, *args, **options):
        filepath = options["file"]
        if not os.path.exists(filepath):
            raise CommandError(f"File not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read().strip()

        if options["replace"]:
            deleted, _ = SharedKnowledge.objects.filter(title=options["title"]).delete()
            if deleted:
                self.stdout.write(f"Deleted existing document: {options['title']}")

        doc = SharedKnowledge.objects.create(
            title=options["title"],
            category=options["category"],
        )

        chunks = chunk_text(text)
        self.stdout.write(f"Ingesting {len(chunks)} chunks for '{options['title']}'...")

        for i, chunk_text_content in enumerate(chunks):
            embedding = get_embedding(chunk_text_content)
            SharedChunk.objects.create(
                knowledge=doc,
                content=chunk_text_content,
                chunk_index=i,
                embedding=embedding,
            )
            if (i + 1) % 10 == 0:
                self.stdout.write(f"  {i + 1}/{len(chunks)} chunks embedded")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Ingested {len(chunks)} chunks for '{options['title']}' (id: {doc.id})"
            )
        )