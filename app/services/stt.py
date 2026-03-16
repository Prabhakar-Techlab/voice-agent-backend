"""Multi-provider STT: Sarvam/Groq/AssemblyAI (batch REST) + Deepgram (real-time WebSocket)."""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import wave
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
from websockets.asyncio.client import connect as ws_connect

from app.config import get_settings

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 16000
_SAMPLE_WIDTH = 2
_CHANNELS = 1
_BYTES_PER_SECOND = _SAMPLE_RATE * _SAMPLE_WIDTH * _CHANNELS

# Put FLUSH in the queue to trigger immediate transcription on silence
FLUSH = b""

SUPPORTED_PROVIDERS = ["sarvam", "groq", "deepgram", "assemblyai"]


@dataclass
class STTResult:
    text: str
    is_final: bool
    speaker_label: str = "speaker_0"
    start_time: float | None = None
    end_time: float | None = None
    error: str | None = None


def _pcm_to_wav(pcm_data: bytes, sample_rate: int = _SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(_CHANNELS)
        wf.setsampwidth(_SAMPLE_WIDTH)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


async def _call_groq(
    client: httpx.AsyncClient, pcm: bytes, api_key: str, language_code: str, sample_rate: int
) -> str:
    wav = _pcm_to_wav(pcm, sample_rate)
    logger.info("[groq] Sending %.1f KB, %.1fs", len(wav) / 1024, len(pcm) / _BYTES_PER_SECOND)
    resp = await client.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"file": ("audio.wav", wav, "audio/wav")},
        data={"model": "whisper-large-v3-turbo", "response_format": "json", "language": language_code.split("-")[0]},
        timeout=60.0,
    )
    resp.raise_for_status()
    return (resp.json().get("text") or "").strip()



async def _call_assemblyai(
    client: httpx.AsyncClient, pcm: bytes, api_key: str, language_code: str, sample_rate: int
) -> str:
    import asyncio as _asyncio
    wav = _pcm_to_wav(pcm, sample_rate)
    logger.info("[assemblyai] Sending %.1f KB, %.1fs", len(wav) / 1024, len(pcm) / _BYTES_PER_SECOND)
    headers = {"authorization": api_key}

    # Step 1: upload
    up = await client.post("https://api.assemblyai.com/v2/upload", headers=headers, content=wav, timeout=60.0)
    up.raise_for_status()
    upload_url = up.json()["upload_url"]

    # Step 2: submit transcript job
    lang = language_code.split("-")[0]
    sub = await client.post(
        "https://api.assemblyai.com/v2/transcript",
        headers={**headers, "content-type": "application/json"},
        json={"audio_url": upload_url, "language_code": lang},
        timeout=30.0,
    )
    sub.raise_for_status()
    tid = sub.json()["id"]

    # Step 3: poll until done
    for _ in range(60):
        await _asyncio.sleep(1)
        poll = await client.get(f"https://api.assemblyai.com/v2/transcript/{tid}", headers=headers, timeout=15.0)
        poll.raise_for_status()
        data = poll.json()
        if data["status"] == "completed":
            return (data.get("text") or "").strip()
        if data["status"] == "error":
            logger.error("[assemblyai] transcript error: %s", data.get("error"))
            return ""
    logger.error("[assemblyai] timed out waiting for transcript")
    return ""


_PROVIDER_MAP = {
    "groq":       (_call_groq,       "groq_api_key"),
    "assemblyai": (_call_assemblyai, "assemblyai_api_key"),
}

# ── Deepgram real-time WebSocket streaming ──────────────────────────────────

async def _stream_deepgram_realtime(
    audio_queue: asyncio.Queue,
    *,
    api_key: str,
    language_code: str,
    sample_rate: int,
) -> AsyncIterator[STTResult]:
    """
    Streams raw PCM audio to Deepgram's real-time WebSocket API.
    Yields STTResult as Deepgram emits final transcripts (~100-300ms latency).
    """
    lang = language_code.split("-")[0]
    url = (
        f"wss://api.deepgram.com/v1/listen"
        f"?encoding=linear16&sample_rate={sample_rate}"
        f"&language={lang}&model=nova-2&punctuate=true"
        f"&interim_results=true&diarize=true"
    )
    logger.info("[deepgram-ws] Connecting, language=%s sample_rate=%d diarize=true", lang, sample_rate)

    result_q: asyncio.Queue = asyncio.Queue()

    async def _run() -> None:
        try:
            async with ws_connect(
                url,
                additional_headers={"Authorization": f"Token {api_key}"},
                ping_interval=10,
            ) as dg_ws:

                async def _sender() -> None:
                    try:
                        while True:
                            item = await audio_queue.get()
                            if item is None:
                                try:
                                    await dg_ws.send(json.dumps({"type": "CloseStream"}))
                                except Exception:
                                    pass
                                break
                            if item == FLUSH:
                                try:
                                    await dg_ws.send(json.dumps({"type": "Finalize"}))
                                except Exception:
                                    pass
                                continue
                            if item:
                                await dg_ws.send(bytes(item))
                    except Exception as exc:
                        logger.exception("[deepgram-ws] sender error: %s", exc)

                async def _receiver() -> None:
                    try:
                        async for msg in dg_ws:
                            data = json.loads(msg)
                            if data.get("type") == "Results":
                                alts = data.get("channel", {}).get("alternatives", [{}])
                                transcript = (alts[0].get("transcript") or "").strip()
                                if transcript and data.get("is_final"):
                                    # Determine dominant speaker from word-level diarization
                                    words = alts[0].get("words", [])
                                    if words:
                                        counts: dict[int, int] = {}
                                        for w in words:
                                            spk = w.get("speaker", 0)
                                            counts[spk] = counts.get(spk, 0) + 1
                                        dominant = max(counts, key=lambda k: counts[k])
                                        speaker_label = f"speaker_{dominant}"
                                    else:
                                        speaker_label = "speaker_0"
                                    await result_q.put(STTResult(
                                        text=transcript,
                                        is_final=True,
                                        speaker_label=speaker_label,
                                    ))
                            elif data.get("type") == "Metadata":
                                logger.info("[deepgram-ws] connected, request_id=%s", data.get("request_id"))
                    except Exception as exc:
                        logger.exception("[deepgram-ws] receiver error: %s", exc)

                await asyncio.gather(_sender(), _receiver())

        except Exception as exc:
            logger.exception("[deepgram-ws] connection error: %s", exc)
            await result_q.put(STTResult(text="", is_final=True, error=f"Deepgram WS error: {exc}"))
        finally:
            await result_q.put(None)

    run_task = asyncio.create_task(_run())
    try:
        while True:
            item = await result_q.get()
            if item is None:
                break
            yield item
    finally:
        run_task.cancel()
        try:
            await run_task
        except asyncio.CancelledError:
            pass


# ── Sarvam real-time WebSocket streaming ─────────────────────────────────────

async def _stream_sarvam_realtime(
    audio_queue: asyncio.Queue,
    *,
    api_key: str,
    language_code: str,
    sample_rate: int,
) -> AsyncIterator[STTResult]:
    """
    Streams audio to Sarvam's real-time WebSocket API (saaras:v3).
    Each chunk is encoded as a WAV and sent as JSON+base64; flush signals as JSON.
    """
    url = (
        f"wss://api.sarvam.ai/speech-to-text/ws"
        f"?language-code={language_code}&model=saaras:v3&mode=transcribe"
        f"&sample_rate={sample_rate}"
    )
    logger.info("[sarvam-ws] Connecting, language=%s sample_rate=%d", language_code, sample_rate)

    result_q: asyncio.Queue = asyncio.Queue()

    async def _run() -> None:
        try:
            async with ws_connect(
                url,
                additional_headers={"Api-Subscription-Key": api_key},
                ping_interval=10,
            ) as sv_ws:

                async def _sender() -> None:
                    try:
                        while True:
                            item = await audio_queue.get()
                            if item is None:
                                break
                            if item == FLUSH:
                                try:
                                    await sv_ws.send(json.dumps({"type": "flush"}))
                                except Exception:
                                    pass
                                continue
                            if item:
                                # Spec requires JSON + base64 WAV
                                wav = _pcm_to_wav(bytes(item), sample_rate)
                                await sv_ws.send(json.dumps({
                                    "audio": {
                                        "data": base64.b64encode(wav).decode(),
                                        "sample_rate": str(sample_rate),
                                        "encoding": "audio/wav",
                                    }
                                }))
                    except Exception as exc:
                        logger.exception("[sarvam-ws] sender error: %s", exc)

                async def _receiver() -> None:
                    try:
                        async for msg in sv_ws:
                            if isinstance(msg, bytes):
                                continue
                            data = json.loads(msg)
                            logger.debug("[sarvam-ws] raw message: %s", str(data)[:200])
                            if data.get("type") == "data":
                                transcript = (data.get("data", {}).get("transcript") or "").strip()
                                if transcript:
                                    await result_q.put(STTResult(
                                        text=transcript,
                                        is_final=True,
                                        speaker_label="speaker_0",
                                    ))
                            elif data.get("type") == "error":
                                raw = data.get("data") or data
                                err = (raw.get("error") or raw.get("message") or str(raw))
                                logger.error("[sarvam-ws] server error: %s | full: %s", err, data)
                                await result_q.put(STTResult(text="", is_final=True, error=f"Sarvam WS: {err}"))
                    except Exception as exc:
                        logger.exception("[sarvam-ws] receiver error: %s", exc)

                await asyncio.gather(_sender(), _receiver())

        except Exception as exc:
            logger.exception("[sarvam-ws] connection error: %s", exc)
            await result_q.put(STTResult(text="", is_final=True, error=f"Sarvam WS error: {exc}"))
        finally:
            await result_q.put(None)

    run_task = asyncio.create_task(_run())
    try:
        while True:
            item = await result_q.get()
            if item is None:
                break
            yield item
    finally:
        run_task.cancel()
        try:
            await run_task
        except asyncio.CancelledError:
            pass


async def stream_stt(
    audio_queue: asyncio.Queue,
    *,
    sample_rate: int = _SAMPLE_RATE,
    language_code: str = "en-IN",
    provider: str = "sarvam",
) -> AsyncIterator[STTResult]:
    """
    Reads from audio_queue:
      bytes → stream (sarvam/deepgram WS) or accumulate (batch REST)
      b""   → flush: force transcription (all providers)
      None  → end: flush remaining buffer then stop
    """
    settings = get_settings()

    # ── Sarvam: real-time WebSocket path ────────────────────────────────────
    if provider == "sarvam":
        api_key = settings.sarvam_api_key
        if not api_key:
            yield STTResult(text="", is_final=True, error="SARVAM_API_KEY is not set in .env")
            return
        async for result in _stream_sarvam_realtime(
            audio_queue,
            api_key=api_key,
            language_code=language_code,
            sample_rate=sample_rate,
        ):
            yield result
        return

    # ── Deepgram: real-time WebSocket path ──────────────────────────────────
    if provider == "deepgram":
        api_key = settings.deepgram_api_key
        if not api_key:
            yield STTResult(text="", is_final=True, error="DEEPGRAM_API_KEY is not set in .env")
            return
        async for result in _stream_deepgram_realtime(
            audio_queue,
            api_key=api_key,
            language_code=language_code,
            sample_rate=sample_rate,
        ):
            yield result
        return

    # ── All other providers: batch REST path ────────────────────────────────
    if provider not in _PROVIDER_MAP:
        yield STTResult(text="", is_final=True, error=f"Unknown provider '{provider}'. Use: {SUPPORTED_PROVIDERS}")
        return

    call_fn, key_attr = _PROVIDER_MAP[provider]
    api_key = getattr(settings, key_attr, None)
    if not api_key:
        yield STTResult(text="", is_final=True, error=f"{key_attr.upper()} is not set in .env")
        return

    buffer = bytearray()
    start_time = 0.0

    async with httpx.AsyncClient() as client:
        while True:
            item = await audio_queue.get()

            if item is None:
                if buffer:
                    pcm = bytes(buffer)
                    duration = len(pcm) / _BYTES_PER_SECOND
                    try:
                        text = await call_fn(client, pcm, api_key, language_code, sample_rate)
                        if text:
                            yield STTResult(text=text, is_final=True, speaker_label="speaker_0",
                                            start_time=start_time, end_time=start_time + duration)
                    except httpx.HTTPStatusError as exc:
                        logger.error("[%s] %s: %s", provider, exc.response.status_code, exc.response.text)
                    except Exception as exc:
                        logger.exception("[%s] failed: %s", provider, exc)
                break

            if item == FLUSH:
                if buffer:
                    pcm = bytes(buffer)
                    duration = len(pcm) / _BYTES_PER_SECOND
                    try:
                        text = await call_fn(client, pcm, api_key, language_code, sample_rate)
                        if text:
                            yield STTResult(text=text, is_final=True, speaker_label="speaker_0",
                                            start_time=start_time, end_time=start_time + duration)
                        start_time += duration
                    except httpx.HTTPStatusError as exc:
                        logger.error("[%s] %s: %s", provider, exc.response.status_code, exc.response.text)
                    except Exception as exc:
                        logger.exception("[%s] failed: %s", provider, exc)
                    buffer = bytearray()
                continue

            buffer.extend(item)
