"""Google Cloud Speech-to-Text streaming: transcription with punctuation."""
from __future__ import annotations

import asyncio
import logging
import os
import queue
import threading
from collections.abc import AsyncIterator
from dataclasses import dataclass

from google.cloud import speech_v1p1beta1 as speech
from google.cloud.speech_v1p1beta1.services.speech.client import SpeechClient as _GapicSpeechClient

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class STTResult:
    text: str
    is_final: bool
    error: str | None = None


def _run_streaming_recognize(
    audio_queue: queue.Queue[bytes | None],
    result_queue: queue.Queue[STTResult | None],
    sample_rate: int,
    language_code: str,
) -> None:
    settings = get_settings()
    if settings.google_application_credentials:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials

    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=sample_rate,
        language_code=language_code,
        enable_automatic_punctuation=True,
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=False,
    )

    request_queue: queue.Queue[speech.StreamingRecognizeRequest | None] = queue.Queue()

    def produce_requests() -> None:
        request_queue.put(speech.StreamingRecognizeRequest(streaming_config=streaming_config))
        while True:
            chunk = audio_queue.get()
            if chunk is None:
                request_queue.put(None)
                break
            request_queue.put(speech.StreamingRecognizeRequest(audio_content=chunk))

    class RequestIterator:
        def __iter__(self) -> "RequestIterator":
            return self

        def __next__(self) -> speech.StreamingRecognizeRequest:
            req = request_queue.get()
            if req is None:
                raise StopIteration
            return req

    producer = threading.Thread(target=produce_requests, daemon=True)
    producer.start()

    try:
        responses = _GapicSpeechClient.streaming_recognize(client, requests=RequestIterator())
        for response in responses:
            if not response.results:
                continue
            for result in response.results:
                if not result.alternatives:
                    continue
                transcript = (result.alternatives[0].transcript or "").strip()
                if not transcript:
                    continue
                result_queue.put(STTResult(text=transcript, is_final=True))
    except Exception as e:
        logger.exception("Google STT streaming failed: %s", e)
        result_queue.put(STTResult(text="", is_final=True, error="Speech recognition failed."))
    finally:
        result_queue.put(None)
        audio_queue.put(None)
        producer.join(timeout=2.0)


async def stream_stt(
    audio_chunks: AsyncIterator[bytes],
    *,
    sample_rate: int = 16000,
    language_code: str = "en-US",
) -> AsyncIterator[STTResult]:
    audio_queue: queue.Queue[bytes | None] = queue.Queue()
    result_queue: queue.Queue[STTResult | None] = queue.Queue()
    loop = asyncio.get_event_loop()

    def put_audio(chunk: bytes | None) -> None:
        audio_queue.put(chunk)

    def run_thread() -> None:
        _run_streaming_recognize(
            audio_queue, result_queue,
            sample_rate=sample_rate,
            language_code=language_code,
        )

    thread = threading.Thread(target=run_thread, daemon=True)
    thread.start()

    async def feed_audio() -> None:
        async for chunk in audio_chunks:
            await loop.run_in_executor(None, lambda c=chunk: put_audio(c))
        await loop.run_in_executor(None, lambda: put_audio(None))

    feed_task = asyncio.create_task(feed_audio())

    try:
        while True:
            result = await loop.run_in_executor(None, result_queue.get)
            if result is None:
                break
            yield result
    finally:
        feed_task.cancel()
        try:
            await feed_task
        except asyncio.CancelledError:
            pass
        thread.join(timeout=5.0)
