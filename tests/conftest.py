"""Pytest fixtures: test DB name for isolation."""
import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB_NAME", "stt_conversations_test")


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)
