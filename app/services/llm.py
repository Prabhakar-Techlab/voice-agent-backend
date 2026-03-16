"""LLM response via Groq (llama-3.3-70b) — runs on top of any STT provider."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a helpful voice assistant. The user is speaking to you. "
    "Respond concisely and naturally, as if in a real conversation. "
    "Keep replies brief — 1 to 3 sentences at most."
)


async def get_llm_response(history: list[dict[str, Any]]) -> str:
    """Send full conversation history to Groq LLaMA and return the assistant reply.

    history is a list of {"role": "user"|"assistant", "content": str} dicts.
    """
    settings = get_settings()
    if not settings.groq_api_key:
        logger.warning("[llm] GROQ_API_KEY not set — skipping LLM call")
        return ""

    logger.info("[llm] Sending %d message(s) to LLM", len(history))
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "system", "content": _SYSTEM_PROMPT}, *history],
                "max_tokens": 200,
                "temperature": 0.7,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        reply = resp.json()["choices"][0]["message"]["content"].strip()
        logger.info("[llm] Reply: %s", reply[:120])
        return reply
