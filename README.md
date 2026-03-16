# Real-time STT Backend

FastAPI backend for real-time audio transcription over WebSocket. Supports four STT providers (Sarvam and Deepgram via live WebSocket, Groq and AssemblyAI via batch REST), optional LLM replies via Groq LLaMA, speaker diarization, and conversation logging to MongoDB.

## Quick start

```bash
# Create venv and install
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure secrets
cp .env.example .env
# Edit .env and fill in your API keys

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- UI: http://localhost:8000/
- History: http://localhost:8000/history
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGODB_URI` | Yes | MongoDB connection string (default: `mongodb://localhost:27017`) |
| `MONGODB_DB_NAME` | Yes | Database name (default: `stt_conversations`) |
| `SARVAM_API_KEY` | For Sarvam | Sarvam AI subscription key |
| `DEEPGRAM_API_KEY` | For Deepgram | Deepgram API key |
| `GROQ_API_KEY` | For Groq STT/LLM | Groq API key (used for both Whisper STT and LLaMA LLM) |
| `ASSEMBLYAI_API_KEY` | For AssemblyAI | AssemblyAI API key |
| `ANTHROPIC_API_KEY` | For /suggest | Anthropic API key (smart suggestions route) |

## STT providers

| Provider | Mode | Notes |
|----------|------|-------|
| `sarvam` (default) | Real-time WebSocket | `saaras:v3`, Indian language support |
| `deepgram` | Real-time WebSocket | `nova-2`, speaker diarization |
| `groq` | Batch REST | `whisper-large-v3-turbo` |
| `assemblyai` | Batch REST | Upload → poll pattern |

## WebSocket protocol

**Endpoint:** `ws://localhost:8000/ws/stream`

**Query parameters:**
- `provider` — `sarvam` (default), `deepgram`, `groq`, `assemblyai`
- `language` — BCP-47 language code, e.g. `en-IN`, `hi-IN` (default: `en-IN`)
- `llm` — `true` to enable LLM replies via Groq LLaMA (default: `false`)

**Client → Server:**

| Frame | Description |
|-------|-------------|
| Binary | Raw PCM audio: 16 kHz, 16-bit, mono. Send ~100–500ms chunks (~3200 bytes = 100ms). |
| `{"type":"flush"}` | Force immediate transcription (silence/pause signal). |
| `{"type":"end"}` | Signal end of audio; server flushes remaining buffer and closes session. |

**Server → Client:**

```json
{
  "text": "Hello world",
  "speaker": "speaker_0",
  "is_final": true,
  "start_time": 0.0,
  "end_time": 1.4,
  "llm_reply": "Hi! How can I help?"
}
```

On error:
```json
{"type": "error", "message": "..."}
```

## Data model (MongoDB)

- **sessions**: `_id`, `started_at`, `ended_at`
- **utterances**: `session_id`, `speaker_label`, `text`, `start_time`, `end_time`, `is_final`

Each WebSocket connection creates one session. Utterances are appended in real time as transcripts arrive.

## LLM conversation memory

When `llm=true`, the full conversation history is maintained per session and sent to Groq LLaMA 3.3-70B on each utterance. The assistant reply is returned in `llm_reply`.

## Speaker diarization

Diarization is available with the `deepgram` provider. Speaker labels (`speaker_0`, `speaker_1`, …) are returned in `speaker` and color-coded in the UI.

## Python client example

```python
import asyncio, json, websockets

async def stream():
    uri = "ws://localhost:8000/ws/stream?provider=deepgram&language=en-IN"
    async with websockets.connect(uri) as ws:
        with open("audio.raw", "rb") as f:
            while chunk := f.read(3200):   # 100ms chunks
                await ws.send(chunk)
        await ws.send(json.dumps({"type": "end"}))
        async for msg in ws:
            print(json.loads(msg))

asyncio.run(stream())
```
