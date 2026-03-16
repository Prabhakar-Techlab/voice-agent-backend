import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
from app.routes import history


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
app.include_router(history.router, tags=["history"])

_static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(_static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/", include_in_schema=False)
async def serve_ui():
    return FileResponse(os.path.join(_static_dir, "index.html"))


@app.get("/history", include_in_schema=False)
async def serve_history():
    return FileResponse(os.path.join(_static_dir, "history.html"))
