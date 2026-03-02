"""WebSocket /ws/stream: connect, send chunks, disconnect."""
from collections.abc import AsyncIterator
from fastapi.testclient import TestClient


async def _mock_stream_stt(audio_chunks: AsyncIterator[bytes], **kwargs):
    async for _ in audio_chunks:
        pass
    return
    yield


def test_websocket_connect_send_disconnect(client: TestClient, monkeypatch):
    """Connect to /ws/stream, send binary chunks, disconnect. Mocks DB and STT so no MongoDB/Google required."""
    from app.routes import stream as stream_module
    from app.services import stt as stt_module
    created = []
    ended = []

    async def mock_create_session(metadata=None):
        created.append("session")
        return "test-session-id"

    async def mock_end_session(session_id):
        ended.append(session_id)

    async def mock_append_utterance(*args, **kwargs):
        pass

    monkeypatch.setattr(stream_module.conversation, "create_session", mock_create_session)
    monkeypatch.setattr(stream_module.conversation, "end_session", mock_end_session)
    monkeypatch.setattr(stream_module.conversation, "append_utterance", mock_append_utterance)
    monkeypatch.setattr(stt_module, "stream_stt", _mock_stream_stt)

    r = client.get("/health")
    assert r.status_code == 200
    with client.websocket_connect("/ws/stream") as websocket:
        chunk = b"\x00" * 3200
        websocket.send_bytes(chunk)
        websocket.send_bytes(chunk)

    assert len(created) == 1
    assert "test-session-id" in ended
