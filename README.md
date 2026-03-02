# Real-time STT Backend

FastAPI backend that accepts real-time audio over WebSocket, runs Google Cloud Speech-to-Text with speaker diarization, and logs conversations (sessions and utterances) to MongoDB.

## Run

```bash
# Create venv and install
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Set env (copy .env.example to .env and fill)
cp .env.example .env

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API docs: http://localhost:8000/docs  
- Health: http://localhost:8000/health  
- Ready (includes MongoDB check): http://localhost:8000/ready  

## Environment variables

| Variable | Description |
|----------|-------------|
| `MONGODB_URI` | MongoDB connection string (default: `mongodb://localhost:27017`) |
| `MONGODB_DB_NAME` | Database name (default: `stt_conversations`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Google service account JSON (optional if using default credentials) |
| `GOOGLE_CLOUD_PROJECT_ID` | GCP project ID (optional) |
| `DIARIZATION_SPEAKER_COUNT` | Optional; min/max speakers for diarization (default: auto) |

## WebSocket: required audio format and usage

**Endpoint:** `ws://<host>/ws/stream` (e.g. `ws://localhost:8000/ws/stream`).

**Client → Server**

- Send **binary** WebSocket frames only.
- Audio format: **16 kHz, 16-bit PCM, mono**.
- Chunk size: send every **100–500 ms** of audio (e.g. 3 200 bytes ≈ 100 ms at 16 kHz 16-bit mono). Avoid sending one huge buffer per second.

**Server → Client (optional)**

- Server may send JSON text frames:  
  `{"text": "...", "speaker": "speaker_0", "is_final": true, "start_time": 0.0, "end_time": 1.2}`.

**Lifecycle**

- One connection = one session. On connect a session is created in MongoDB; on disconnect the session is closed (`ended_at` set) and utterances are already stored.

## Example (Python client)

```python
import asyncio
import websockets

async def send_audio():
    uri = "ws://localhost:8000/ws/stream"
    async with websockets.connect(uri) as ws:
        # Send 100 ms of silence (3200 bytes) as placeholder
        chunk = b"\x00" * 3200
        for _ in range(10):
            await ws.send(chunk)
            msg = await ws.recv()
            print(msg)

asyncio.run(send_audio())
```

## Data model (MongoDB)

- **sessions**: `_id`, `started_at`, `ended_at`, `metadata`
- **utterances**: `session_id`, `speaker_label`, `text`, `start_time`, `end_time`, `is_final`
# audio_stream_backend
