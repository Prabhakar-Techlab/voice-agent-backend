import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure app loggers always write to stderr (visible in uvicorn terminal)
_app_log = logging.getLogger("app")
_app_log.setLevel(logging.INFO)
if not _app_log.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setLevel(logging.INFO)
    _handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
    )
    _app_log.addHandler(_handler)
_app_log.propagate = False

from app.config import get_settings
from app.db import close_db, init_db
from app.routes import health, stream, suggest


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="Real-time STT Backend",
    description="WebSocket streaming Speech-to-Text with speaker diarization; logs to MongoDB.",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(stream.router, prefix="/ws", tags=["stream"])
app.include_router(suggest.router, tags=["suggest"])
