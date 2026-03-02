"""Conversation log: create session, append utterances, end session."""
from datetime import datetime
from typing import Any

from bson import ObjectId

from app.db import get_sessions_collection, get_utterances_collection


async def create_session(metadata: dict | None = None) -> str:
    """Create a new session document. Returns session_id (MongoDB ObjectId as string)."""
    coll = get_sessions_collection()
    now = datetime.utcnow()
    doc: dict[str, Any] = {
        "started_at": now,
        "ended_at": None,
        "metadata": metadata or {},
    }
    result = await coll.insert_one(doc)
    return str(result.inserted_id)


async def append_utterance(
    session_id: str,
    speaker_label: str,
    text: str,
    start_time: float | None = None,
    end_time: float | None = None,
    is_final: bool = True,
) -> str:
    """Append an utterance to a session. Returns utterance id."""
    coll = get_utterances_collection()
    doc: dict[str, Any] = {
        "session_id": session_id,
        "speaker_label": speaker_label,
        "text": text,
        "start_time": start_time,
        "end_time": end_time,
        "is_final": is_final,
    }
    result = await coll.insert_one(doc)
    return str(result.inserted_id)


async def end_session(session_id: str) -> None:
    """Set ended_at on the session."""
    coll = get_sessions_collection()
    await coll.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"ended_at": datetime.utcnow()}},
    )
