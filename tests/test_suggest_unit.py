"""Unit tests for POST /api/v1/suggest_response.

Mocks app.services.suggest.get_suggestion so only the route layer
(request parsing, response shaping, error mapping) is exercised.
No network or DB required.
"""
import anthropic
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_suggest(return_value="Here is a suggestion.", side_effect=None):
    """Patch get_suggestion in the route module."""
    mock = AsyncMock(return_value=return_value, side_effect=side_effect)
    return patch("app.routes.suggest.get_suggestion", mock)


def _make_anthropic_error(cls):
    """Construct an anthropic API error with a minimal mock response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.headers = {}
    return cls("error", response=mock_resp, body=None)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

def test_minimal_request_returns_200(client: TestClient):
    """Minimal body (no final_context) → 200 with suggestion."""
    with _patch_suggest() as mock:
        r = client.post("/api/v1/suggest_response", json={"text": "What should I say?"})

    assert r.status_code == 200
    assert r.json() == {"suggestion": "Here is a suggestion."}
    mock.assert_awaited_once_with("What should I say?", None)


def test_full_context_passes_all_fields(client: TestClient):
    """All final_context fields are forwarded to the service."""
    payload = {
        "text": "How to handle price objection?",
        "final_context": {
            "client_name": "Acme Corp",
            "sales_agent_name": "John Smith",
            "prompt_text": "Enterprise HR SaaS sales call",
        },
    }
    with _patch_suggest() as mock:
        r = client.post("/api/v1/suggest_response", json=payload)

    assert r.status_code == 200
    _, ctx = mock.call_args[0]
    assert ctx.client_name == "Acme Corp"
    assert ctx.sales_agent_name == "John Smith"
    assert ctx.prompt_text == "Enterprise HR SaaS sales call"


def test_partial_context_only_client_name(client: TestClient):
    """Partial final_context (only client_name) is accepted; other fields are None."""
    payload = {"text": "Some question", "final_context": {"client_name": "Only Name"}}
    with _patch_suggest() as mock:
        r = client.post("/api/v1/suggest_response", json=payload)

    assert r.status_code == 200
    _, ctx = mock.call_args[0]
    assert ctx.client_name == "Only Name"
    assert ctx.sales_agent_name is None
    assert ctx.prompt_text is None


def test_explicit_null_final_context(client: TestClient):
    """Explicitly passing final_context: null is treated as no context."""
    with _patch_suggest() as mock:
        r = client.post("/api/v1/suggest_response", json={"text": "hi", "final_context": None})

    assert r.status_code == 200
    mock.assert_awaited_once_with("hi", None)


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

def test_empty_text_returns_422(client: TestClient):
    r = client.post("/api/v1/suggest_response", json={"text": ""})
    assert r.status_code == 422
    errors = r.json()["detail"]
    assert any(e["type"] == "string_too_short" and "text" in e["loc"] for e in errors)


def test_missing_text_returns_422(client: TestClient):
    r = client.post("/api/v1/suggest_response", json={})
    assert r.status_code == 422
    errors = r.json()["detail"]
    assert any("text" in e["loc"] for e in errors)


def test_non_string_text_returns_422(client: TestClient):
    r = client.post("/api/v1/suggest_response", json={"text": 123})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Error-mapping tests
# ---------------------------------------------------------------------------

def test_authentication_error_maps_to_500(client: TestClient):
    err = _make_anthropic_error(anthropic.AuthenticationError)
    with _patch_suggest(side_effect=err):
        r = client.post("/api/v1/suggest_response", json={"text": "test"})

    assert r.status_code == 500
    assert "authentication" in r.json()["detail"].lower()


def test_rate_limit_error_maps_to_429(client: TestClient):
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {}
    err = anthropic.RateLimitError("rate limit", response=mock_resp, body=None)
    with _patch_suggest(side_effect=err):
        r = client.post("/api/v1/suggest_response", json={"text": "test"})

    assert r.status_code == 429
    assert "rate limit" in r.json()["detail"].lower()


def test_api_status_error_maps_to_502(client: TestClient):
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.headers = {}
    err = anthropic.APIStatusError("upstream", response=mock_resp, body=None)
    with _patch_suggest(side_effect=err):
        r = client.post("/api/v1/suggest_response", json={"text": "test"})

    assert r.status_code == 502


def test_unexpected_error_maps_to_500(client: TestClient):
    with _patch_suggest(side_effect=RuntimeError("boom")):
        r = client.post("/api/v1/suggest_response", json={"text": "test"})

    assert r.status_code == 500
    assert r.json()["detail"] == "Internal server error"
