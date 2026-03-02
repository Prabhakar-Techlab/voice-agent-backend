"""Pydantic shapes for Session and Utterance (MongoDB documents)."""
from datetime import datetime

from pydantic import BaseModel, Field


class SessionIn(BaseModel):
    """Optional metadata when creating a session."""
    metadata: dict | None = None


class SessionOut(BaseModel):
    """Session as returned from DB (with _id as id)."""
    id: str
    started_at: datetime
    ended_at: datetime | None = None
    metadata: dict | None = None


class UtteranceIn(BaseModel):
    """Payload for appending an utterance."""
    session_id: str
    speaker_label: str  # e.g. speaker_0, speaker_1
    text: str
    start_time: float | None = None  # seconds
    end_time: float | None = None
    is_final: bool = True


class UtteranceOut(BaseModel):
    """Utterance as stored/returned."""
    id: str
    session_id: str
    speaker_label: str
    text: str
    start_time: float | None = None
    end_time: float | None = None
    is_final: bool = True
