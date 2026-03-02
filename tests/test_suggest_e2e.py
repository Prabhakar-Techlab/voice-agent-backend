"""E2E / regression tests for POST /api/v1/suggest_response.

Mocks anthropic.AsyncAnthropic at the SDK level so the full stack
(route → service → prompt builder → mocked Claude) is exercised.
No real network calls are made.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Mock factory
# ---------------------------------------------------------------------------

def _make_mock_anthropic(suggestion_text: str = "Mocked suggestion."):
    """Return a mock AsyncAnthropic instance that yields suggestion_text."""
    block = MagicMock()
    block.type = "text"
    block.text = suggestion_text

    message = MagicMock()
    message.content = [block]

    stream_ctx = AsyncMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=stream_ctx)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)
    stream_ctx.get_final_message = AsyncMock(return_value=message)

    messages_obj = MagicMock()
    messages_obj.stream = MagicMock(return_value=stream_ctx)

    sdk_client = MagicMock()
    sdk_client.messages = messages_obj

    anthropic_instance = AsyncMock()
    anthropic_instance.__aenter__ = AsyncMock(return_value=sdk_client)
    anthropic_instance.__aexit__ = AsyncMock(return_value=False)

    return anthropic_instance, messages_obj


# ---------------------------------------------------------------------------
# Regression: mirrors the curl test cases validated manually
# ---------------------------------------------------------------------------

def test_e2e_minimal_request(client: TestClient):
    """Curl test 1 — no final_context: 200 + suggestion returned."""
    anthropic_instance, _ = _make_mock_anthropic("General sales advice.")
    with patch("app.services.suggest.anthropic.AsyncAnthropic", return_value=anthropic_instance):
        r = client.post(
            "/api/v1/suggest_response",
            json={"text": "How should I respond when the client says the price is too high?"},
        )

    assert r.status_code == 200
    assert r.json() == {"suggestion": "General sales advice."}


def test_e2e_full_context_response(client: TestClient):
    """Curl test 2 — all final_context fields: 200 + tailored suggestion."""
    anthropic_instance, messages_obj = _make_mock_anthropic("Tailored HR SaaS advice.")
    with patch("app.services.suggest.anthropic.AsyncAnthropic", return_value=anthropic_instance):
        r = client.post(
            "/api/v1/suggest_response",
            json={
                "text": "How should I respond when the client says the price is too high?",
                "final_context": {
                    "client_name": "Acme Corp",
                    "sales_agent_name": "John Smith",
                    "prompt_text": "B2B SaaS sales call. Product is an enterprise HR platform.",
                },
            },
        )

    assert r.status_code == 200
    assert r.json() == {"suggestion": "Tailored HR SaaS advice."}

    # Verify the system prompt was enriched with all context fields
    _, kwargs = messages_obj.stream.call_args
    system_prompt = kwargs["system"]
    assert "Acme Corp" in system_prompt
    assert "John Smith" in system_prompt
    assert "enterprise HR platform" in system_prompt


def test_e2e_partial_context_only_client_name(client: TestClient):
    """Curl test 3 — only client_name in context: 200, prompt contains client_name."""
    anthropic_instance, messages_obj = _make_mock_anthropic("Context-aware advice.")
    with patch("app.services.suggest.anthropic.AsyncAnthropic", return_value=anthropic_instance):
        r = client.post(
            "/api/v1/suggest_response",
            json={"text": "some question", "final_context": {"client_name": "Only Name"}},
        )

    assert r.status_code == 200
    _, kwargs = messages_obj.stream.call_args
    system_prompt = kwargs["system"]
    assert "Only Name" in system_prompt
    assert "sales agent" not in system_prompt.lower() or "None" not in system_prompt


def test_e2e_empty_text_returns_422(client: TestClient):
    """Curl test 4 — empty string: FastAPI rejects before reaching the service."""
    r = client.post("/api/v1/suggest_response", json={"text": ""})
    assert r.status_code == 422
    errors = r.json()["detail"]
    assert any(e["type"] == "string_too_short" for e in errors)


def test_e2e_no_final_context_uses_base_prompt(client: TestClient):
    """When final_context is omitted, base system prompt is used unchanged."""
    anthropic_instance, messages_obj = _make_mock_anthropic("Base advice.")
    with patch("app.services.suggest.anthropic.AsyncAnthropic", return_value=anthropic_instance):
        r = client.post(
            "/api/v1/suggest_response",
            json={"text": "Give me advice"},
        )

    assert r.status_code == 200
    _, kwargs = messages_obj.stream.call_args
    system_prompt = kwargs["system"]
    # Base prompt has no context section
    assert "Conversation context:" not in system_prompt
    assert "concise, actionable suggestions" in system_prompt


def test_e2e_correct_model_used(client: TestClient):
    """Regression: ensure the expected Claude model is specified in the API call."""
    anthropic_instance, messages_obj = _make_mock_anthropic()
    with patch("app.services.suggest.anthropic.AsyncAnthropic", return_value=anthropic_instance):
        client.post("/api/v1/suggest_response", json={"text": "test"})

    _, kwargs = messages_obj.stream.call_args
    assert kwargs["model"] == "claude-opus-4-6"


def test_e2e_multi_block_content_joined(client: TestClient):
    """Regression: multiple text blocks in Claude response are joined with newlines."""
    block1 = MagicMock()
    block1.type = "text"
    block1.text = "First part."

    block2 = MagicMock()
    block2.type = "thinking"  # non-text block should be ignored
    block2.text = "internal thought"

    block3 = MagicMock()
    block3.type = "text"
    block3.text = "Second part."

    message = MagicMock()
    message.content = [block1, block2, block3]

    stream_ctx = AsyncMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=stream_ctx)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)
    stream_ctx.get_final_message = AsyncMock(return_value=message)

    messages_obj = MagicMock()
    messages_obj.stream = MagicMock(return_value=stream_ctx)

    sdk_client = MagicMock()
    sdk_client.messages = messages_obj

    anthropic_instance = AsyncMock()
    anthropic_instance.__aenter__ = AsyncMock(return_value=sdk_client)
    anthropic_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.suggest.anthropic.AsyncAnthropic", return_value=anthropic_instance):
        r = client.post("/api/v1/suggest_response", json={"text": "test"})

    assert r.status_code == 200
    assert r.json()["suggestion"] == "First part.\nSecond part."
