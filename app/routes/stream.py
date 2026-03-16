"""WebSocket endpoint for real-time audio streaming and STT."""
import asyncio
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.services import conversation
from app.services.llm import get_llm_response
from app.services.stt import FLUSH, STTResult, stream_stt

logger = logging.getLogger(__name__)
router = APIRouter()

SAMPLE_RATE = 16000


@router.websocket("/stream")
async def ws_stream(
    websocket: WebSocket,
    provider: str = Query(default="sarvam"),
    language: str = Query(default="en-IN"),
    llm: bool = Query(default=False),
):
    await websocket.accept()
    session_id = await conversation.create_session()

    # Queue items: bytes (audio) | b"" (flush/silence) | None (end)
    audio_queue: asyncio.Queue = asyncio.Queue()
    end_signal_sent = False
    conversation_history: list[dict] = []

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

        llm_reply = ""
        if llm:
            try:
                conversation_history.append({"role": "user", "content": result.text})
                llm_reply = await get_llm_response(conversation_history)
                if llm_reply:
                    conversation_history.append({"role": "assistant", "content": llm_reply})
            except Exception as exc:
                logger.exception("[llm] failed: %s", exc)
                if conversation_history and conversation_history[-1]["role"] == "user":
                    conversation_history.pop()

        try:
            await websocket.send_text(json.dumps({
                "text": result.text,
                "speaker": result.speaker_label,
                "is_final": True,
                "start_time": result.start_time,
                "end_time": result.end_time,
                "llm_reply": llm_reply,
            }))
        except Exception:
            pass
        try:
            await conversation.append_utterance(
                session_id=session_id,
                speaker_label=result.speaker_label,
                text=result.text,
                start_time=result.start_time,
                end_time=result.end_time,
                is_final=True,
            )
        except Exception as e:
            logger.exception("MongoDB append_utterance failed: %s", e)

    async def consume_stt() -> None:
        async for result in stream_stt(
            audio_queue,
            sample_rate=SAMPLE_RATE,
            language_code=language,
            provider=provider,
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
                        payload = json.loads(msg["text"])
                        if payload.get("type") == "end":
                            await audio_queue.put(None)
                            end_signal_sent = True
                            break
                        elif payload.get("type") == "flush":
                            await audio_queue.put(FLUSH)
                    except (json.JSONDecodeError, TypeError):
                        pass
    except WebSocketDisconnect:
        pass
    finally:
        if not end_signal_sent:
            await audio_queue.put(None)
        try:
            await asyncio.wait_for(consume_task, timeout=15.0)
        except asyncio.TimeoutError:
            consume_task.cancel()
            try:
                await consume_task
            except asyncio.CancelledError:
                pass
        except asyncio.CancelledError:
            pass
        await conversation.end_session(session_id)
