from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db import get_db

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready():
    try:
        await get_db().command("ping")
        return {"status": "ready"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "detail": "MongoDB unavailable"},
        )
