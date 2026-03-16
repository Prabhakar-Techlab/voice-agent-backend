"""History API: list sessions and their utterances."""
from fastapi import APIRouter, HTTPException

from app.db import get_sessions_collection, get_utterances_collection

router = APIRouter()


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.get("/api/history/sessions")
async def list_sessions(limit: int = 50):
    coll = get_sessions_collection()
    docs = await coll.find({}).sort("started_at", -1).limit(limit).to_list(limit)
    return [_serialize(d) for d in docs]


@router.get("/api/history/sessions/{session_id}")
async def get_session(session_id: str):
    from bson import ObjectId
    from bson.errors import InvalidId

    sessions = get_sessions_collection()
    utterances = get_utterances_collection()

    try:
        oid = ObjectId(session_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid session_id")

    session = await sessions.find_one({"_id": oid})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    utts = await utterances.find({"session_id": session_id}).sort("start_time", 1).to_list(None)

    return {
        "session": _serialize(session),
        "utterances": [_serialize(u) for u in utts],
    }
