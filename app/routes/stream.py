"""WebSocket endpoint for real-time audio streaming and STT."""
import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services import conversation
from app.services.stt import STTResult, stream_stt

logger = logging.getLogger(__name__)
router = APIRouter()

SAMPLE_RATE = 16000
LANGUAGE_CODE = "en-US"


async def _chunk_iterator(audio_queue: asyncio.Queue[bytes | None]) -> AsyncIterator[bytes]:
    while True:
        chunk = await audio_queue.get()
        if chunk is None:
            break
        yield chunk


@router.websocket("/stream")
async def ws_stream(websocket: WebSocket):
    await websocket.accept()
    session_id = await conversation.create_session()

    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    end_signal_sent = False

    async def on_stt_result(result: STTResult) -> None:
        if result.error:
            logger.error("STT error session=%s: %s", session_id, result.error)
            try:
                await websocket.send_text(json.dumps({"type": "error", "message": result.error}))
            except Exception:
                pass
            return
        if not result.text:
            return
        logger.info("Transcription session=%s: %s", session_id, result.text[:120])
        try:
            await websocket.send_text(json.dumps({"text": result.text, "is_final": True}))
        except Exception:
            pass
        try:
            await conversation.append_utterance(
                session_id=session_id,
                speaker_label="speaker_0",
                text=result.text,
                is_final=True,
            )
        except Exception as e:
            logger.exception("MongoDB append_utterance failed: %s", e)

    async def consume_stt() -> None:
        async for result in stream_stt(
            _chunk_iterator(audio_queue),
            sample_rate=SAMPLE_RATE,
            language_code=LANGUAGE_CODE,
        ):
            await on_stt_result(result)

    consume_task = asyncio.create_task(consume_stt())

    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("type") == "websocket.receive":
                if "bytes" in msg:
                    await audio_queue.put(msg["bytes"])
                elif "text" in msg:
                    try:
                        if json.loads(msg["text"]).get("type") == "end":
                            await audio_queue.put(None)
                            end_signal_sent = True
                            break
                    except (json.JSONDecodeError, TypeError):
                        pass
    except WebSocketDisconnect:
        pass
    finally:
        if not end_signal_sent:
            await audio_queue.put(None)
        try:
            await asyncio.wait_for(consume_task, timeout=10.0)
        except asyncio.TimeoutError:
            consume_task.cancel()
            try:
                await consume_task
            except asyncio.CancelledError:
                pass
        except asyncio.CancelledError:
            pass
        await conversation.end_session(session_id)
