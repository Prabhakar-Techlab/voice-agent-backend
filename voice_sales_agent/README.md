# Nothing Phone — AI Voice Sales Agent

A real-time AI assistant for Nothing Phone sales agents. Listen to what the customer says, get instant AI-powered talking points to respond with.

## How it works

1. Sales agent selects the phone model being discussed
2. Click the mic button and let the customer speak
3. App transcribes the speech and sends it to AI
4. AI returns 3 ready-to-speak responses instantly — displayed on screen (not spoken)

## Features

- **4 phone models** — Phone (4a), Phone (3a), Phone (3a) Pro, Phone (3)
- **3 STT providers** — Deepgram, AssemblyAI, Sarvam AI (switchable)
- **Language support** — English, Hindi, Hinglish
- **Live transcript** — See words appear as customer speaks
- **Conversation memory** — Full session history sent to AI for context-aware responses
- **Persistent session** — Conversation survives page refresh, clears on "New" button
- **Dark / Light theme** — Toggle in the header
- **Responsive** — Works on desktop, tablet, and mobile
- **Quick triggers** — 8 preset scenarios (price, camera, battery, brand, etc.)

## Tech Stack

| Layer | Tool |
|---|---|
| Frontend | Vanilla HTML / CSS / JS |
| Speech-to-Text | Deepgram Nova-2, AssemblyAI, Sarvam AI saarika:v2.5 |
| AI responses | Groq — llama-3.3-70b-versatile |
| Hosting | Vercel (serverless functions for API routes) |

## Deploy on Vercel

1. Import this repo on [vercel.com](https://vercel.com)
2. Set **Root Directory** to `voice_sales_agent`
3. Add these environment variables in Vercel project settings:

```
GROQ_API_KEY=
DEEPGRAM_API_KEY=
ASSEMBLYAI_API_KEY=
SARVAM_API_KEY=
```

4. Deploy — no build step needed

## Run Locally

```bash
cd voice_sales_agent
cp .env.example .env        # add your API keys
npm install
node server.js              # opens at http://localhost:3000
```

## API Routes

| Route | Description |
|---|---|
| `POST /api/transcribe` | Transcribes audio via Deepgram / AssemblyAI / Sarvam |
| `POST /api/suggest` | Generates 3 sales talking points via Groq |

API keys are kept server-side and never exposed to the browser.
