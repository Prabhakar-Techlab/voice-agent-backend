"""Health and readiness endpoints."""
import pytest
from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready_returns_200_or_503(client: TestClient):
    r = client.get("/ready")
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.json() == {"status": "ready"}
    else:
        assert r.json()["status"] == "not ready"
