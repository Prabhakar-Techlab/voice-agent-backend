"""Suggestion service — uses Claude API to answer questions/statements."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import anthropic

from app.config import get_settings

if TYPE_CHECKING:
    from app.routes.suggest import FinalContext

logger = logging.getLogger(__name__)

_BASE_SYSTEM_PROMPT = (
    "You are a helpful assistant that provides concise, actionable suggestions. "
    "When given a question or statement, respond with the best possible suggestion or answer. "
    "Be clear, direct, and practical."
)

_MODEL = "claude-opus-4-6"


def _build_system_prompt(final_context: FinalContext | None) -> str:
    if not final_context:
        return _BASE_SYSTEM_PROMPT

    parts = [_BASE_SYSTEM_PROMPT, "\n\nConversation context:"]
    if final_context.client_name:
        parts.append(f"- Client name: {final_context.client_name}")
    if final_context.sales_agent_name:
        parts.append(f"- Sales agent name: {final_context.sales_agent_name}")
    if final_context.prompt_text:
        parts.append(f"- Additional context: {final_context.prompt_text}")
    return "\n".join(parts)


async def get_suggestion(text: str, final_context: FinalContext | None = None) -> str:
    """Call Claude and return the best suggestion for *text*."""
    settings = get_settings()

    client_kwargs: dict = {}
    if settings.anthropic_api_key:
        client_kwargs["api_key"] = settings.anthropic_api_key
    # If no key in config, anthropic SDK falls back to ANTHROPIC_API_KEY env var.

    system_prompt = _build_system_prompt(final_context)

    async with anthropic.AsyncAnthropic(**client_kwargs) as client:
        stream = client.messages.stream(
            model=_MODEL,
            max_tokens=1024,
            thinking={"type": "adaptive"},
            system=system_prompt,
            messages=[{"role": "user", "content": text}],
        )
        async with stream as s:
            message = await s.get_final_message()

    text_blocks = [b.text for b in message.content if b.type == "text"]
    return "\n".join(text_blocks)
