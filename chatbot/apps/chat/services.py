"""
Chat service — orchestrates one full turn:

  1. Save user message to DB
  2. Retrieve memories (dual namespace)
  3. Build prompt (tone + memories + rolling window)
  4. Call LLM via LangChain
  5. Save assistant response to DB
  6. Optionally refresh tone profile every N turns
  7. Return response dict

No Celery — everything is synchronous as agreed.
At <1K users and <512MB RAM on Render free tier this is fine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings

from .models import Message, Conversation
from apps.memory.services import retrieve_memories

if TYPE_CHECKING:
    from apps.accounts.models import User


SYSTEM_PROMPT_TEMPLATE = """\
You are a helpful, personalized AI assistant.

{tone_section}

{memory_section}

Instructions:
- Use the memory context above to give personalized, relevant responses.
- If the user's message relates to something in their memory, acknowledge it naturally.
- Do not explicitly say "I remember that..." — just incorporate it naturally.
- If memory context is empty, respond helpfully without referencing memory.
- Be concise unless the user's tone profile suggests they prefer detail.
"""


def build_system_prompt(user: "User", memory_context: str) -> str:
    tone_section = f"User preferences:\n{user.tone_prompt_fragment}"
    memory_section = memory_context if memory_context else "No relevant memory context for this query."
    return SYSTEM_PROMPT_TEMPLATE.format(
        tone_section=tone_section,
        memory_section=memory_section,
    )


def get_rolling_window(conversation: Conversation) -> list[dict]:
    """
    Return the last CONVERSATION_WINDOW messages as LangChain-style
    [{"role": "user"|"assistant", "content": "..."}] dicts.

    If a summary exists (older turns were compressed), prepend it
    as a system message so the LLM has the full context arc.
    """
    window_size = settings.CONVERSATION_WINDOW
    recent = list(
        conversation.messages
        .order_by("-created_at")[:window_size]
    )
    recent.reverse()  # chronological order

    messages = []

    # Prepend compressed summary if it exists
    if conversation.summary:
        messages.append({
            "role": "system",
            "content": f"Summary of earlier conversation:\n{conversation.summary}",
        })

    for msg in recent:
        messages.append({"role": msg.role, "content": msg.content})

    return messages


def call_llm(system_prompt: str, history: list[dict], user_content: str) -> tuple[str, int]:
    """
    Call the LLM via LangChain ChatOpenAI.
    Returns (response_text, total_tokens_used).
    """
    from langchain_openai import ChatOpenAI
    from langchain.schema import SystemMessage, HumanMessage, AIMessage

    llm = ChatOpenAI(
        model=settings.CHAT_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.7,
        max_tokens=1000,
    )

    # Build LangChain message list
    lc_messages = [SystemMessage(content=system_prompt)]

    for msg in history:
        if msg["role"] == "system":
            lc_messages.append(SystemMessage(content=msg["content"]))
        elif msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))

    lc_messages.append(HumanMessage(content=user_content))

    response = llm.invoke(lc_messages)
    token_count = response.response_metadata.get("token_usage", {}).get("total_tokens", 0)
    return response.content, token_count


def maybe_refresh_tone(user: "User", conversation: Conversation) -> None:
    """
    Every TONE_UPDATE_EVERY_N_TURNS turns, run a lightweight LLM call
    to infer updated tone signals from recent messages.
    Updates user.tone_profile in-place.
    """
    turn_count = conversation.messages.filter(role=Message.ROLE_USER).count()
    if turn_count == 0 or turn_count % settings.TONE_UPDATE_EVERY_N_TURNS != 0:
        return

    from langchain_openai import ChatOpenAI
    from langchain.schema import HumanMessage
    import json

    recent_text = "\n".join(
        f"{m.role}: {m.content}"
        for m in conversation.messages.order_by("-created_at")[:settings.TONE_UPDATE_EVERY_N_TURNS]
    )

    prompt = f"""Analyse this conversation excerpt and infer the user's communication preferences.
Return ONLY a valid JSON object with these exact keys:
{{
  "formality": "casual" | "neutral" | "formal",
  "verbosity": "concise" | "medium" | "detailed",
  "uses_emoji": true | false,
  "preferred_length": "short" | "medium" | "long",
  "interests": ["topic1", "topic2"]
}}

Conversation:
{recent_text}

JSON only, no explanation:"""

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.OPENAI_API_KEY,
        temperature=0,
    )
    try:
        result = llm.invoke([HumanMessage(content=prompt)])
        raw = result.content.strip().lstrip("```json").rstrip("```").strip()
        inferred = json.loads(raw)

        # Merge — preserve existing interests, deduplicate
        existing = user.tone_profile.copy()
        inferred_interests = inferred.pop("interests", [])
        existing_interests = existing.get("interests", [])
        merged_interests = list(dict.fromkeys(existing_interests + inferred_interests))[:10]

        existing.update(inferred)
        existing["interests"] = merged_interests
        existing["sample_turns"] = existing.get("sample_turns", 0) + settings.TONE_UPDATE_EVERY_N_TURNS

        user.tone_profile = existing
        user.save(update_fields=["tone_profile"])
    except (json.JSONDecodeError, Exception):
        # Tone refresh is best-effort — never break the chat turn
        pass


def run_chat_turn(user: "User", conversation: Conversation, user_content: str) -> dict:
    """
    Full chat turn pipeline. Returns a dict with the assistant reply
    and metadata ready to send back to the client.
    """
    # 1. Save user message
    user_msg = Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_USER,
        content=user_content,
    )

    # 2. Retrieve relevant memories (dual namespace)
    memory_context = retrieve_memories(user=user, query=user_content)

    # 3. Build system prompt
    system_prompt = build_system_prompt(user=user, memory_context=memory_context)

    # 4. Get rolling conversation window
    history = get_rolling_window(conversation)

    # 5. Call LLM
    reply_text, token_count = call_llm(
        system_prompt=system_prompt,
        history=history,
        user_content=user_content,
    )

    # 6. Save assistant response
    assistant_msg = Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_ASSISTANT,
        content=reply_text,
        token_count=token_count,
    )

    # 7. Optionally refresh tone profile (every N turns, synchronous)
    maybe_refresh_tone(user=user, conversation=conversation)

    # 8. Auto-set conversation title from first user message
    if not conversation.title and conversation.messages.count() <= 2:
        conversation.title = user_content[:80]
        conversation.save(update_fields=["title"])

    return {
        "message_id": str(assistant_msg.id),
        "reply": reply_text,
        "conversation_id": str(conversation.id),
        "token_count": token_count,
    }