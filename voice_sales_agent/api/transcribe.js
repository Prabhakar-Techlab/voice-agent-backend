/* ============================================================
   UNIFIED TRANSCRIPTION ENDPOINT
   Supports: Deepgram | AssemblyAI | Sarvam AI
   ============================================================ */

module.exports.config = {
  api: { bodyParser: { sizeLimit: '10mb' } },
};

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST')   return res.status(405).json({ error: 'Method not allowed' });

  const { provider, audio, mimeType, language } = req.body || {};

  if (!provider) return res.status(400).json({ error: 'provider is required' });
  if (!audio)    return res.status(400).json({ error: 'audio (base64) is required' });

  const audioBuffer = Buffer.from(audio, 'base64');

  // Reject obviously empty recordings (< 2 KB = no real audio content)
  if (audioBuffer.length < 2000) {
    return res.status(400).json({ error: 'Audio too short — speak for at least 1–2 seconds and make sure your microphone is working.' });
  }

  // Resolve language: hinglish → use hi for Deepgram/Sarvam, en for AssemblyAI
  const lang = language || 'en-IN';

  try {
    switch (provider) {
      case 'deepgram':   return await transcribeDeepgram(audioBuffer, mimeType, lang, res);
      case 'assemblyai': return await transcribeAssemblyAI(audioBuffer, lang, res);
      case 'sarvam':     return await transcribeSarvam(audioBuffer, mimeType, lang, res);
      default:           return res.status(400).json({ error: `Unknown provider: ${provider}` });
    }
  } catch (err) {
    console.error(`[Transcribe:${provider}]`, err?.message || err);
    return res.status(500).json({ error: err.message || 'Transcription failed' });
  }
};

/* ============================================================
   DEEPGRAM  (~1-2 seconds)
   ============================================================ */
async function transcribeDeepgram(buffer, mimeType, lang, res) {
  const apiKey = process.env.DEEPGRAM_API_KEY;
  if (!apiKey) return res.status(500).json({ error: 'DEEPGRAM_API_KEY not set.' });

  // Strip codec params — Deepgram only wants the base MIME type
  const cleanMime = (mimeType || 'audio/webm').split(';')[0].trim();

  // nova-2 accepts 'en', 'hi' — not regional variants like en-IN / hi-IN
  const dgLang = lang === 'hi-IN' ? 'hi' : 'en';

  const params = new URLSearchParams({ model: 'nova-2', smart_format: 'true', punctuate: 'true' });

  if (lang === 'hinglish') {
    // Let Deepgram auto-detect between English and Hindi for code-switched speech
    params.set('detect_language', 'true');
  } else {
    params.set('language', dgLang);
  }

  console.log(`[Deepgram] lang=${dgLang} mimeType=${cleanMime} bufferSize=${buffer.length}`);

  let response;
  try {
    response = await fetch(`https://api.deepgram.com/v1/listen?${params}`, {
    method:  'POST',
    headers: {
      'Authorization': `Token ${apiKey}`,
      'Content-Type':  cleanMime,
    },
    body: buffer,
  });
  } catch (netErr) {
    throw new Error(`Deepgram network error: ${netErr.message}. Check your internet connection.`);
  }

  const data = await response.json();

  if (!response.ok) {
    throw new Error(`Deepgram ${response.status}: ${data?.err_msg || data?.error || response.statusText}`);
  }

  const transcript = data?.results?.channels?.[0]?.alternatives?.[0]?.transcript || '';
  console.log(`[Deepgram] transcript="${transcript}" duration=${data?.metadata?.duration}s`);

  return res.status(200).json({ transcript, provider: 'deepgram' });
}

/* ============================================================
   ASSEMBLYAI  (~4-8 seconds)
   ============================================================ */
async function transcribeAssemblyAI(buffer, lang, res) {
  const apiKey = process.env.ASSEMBLYAI_API_KEY;
  if (!apiKey) return res.status(500).json({ error: 'ASSEMBLYAI_API_KEY not set.' });

  const authHeaders = { 'Authorization': apiKey };

  // Step 1: Upload audio as raw bytes
  console.log(`[AssemblyAI] uploading ${buffer.length} bytes...`);
  const uploadRes = await fetch('https://api.assemblyai.com/v2/upload', {
    method:  'POST',
    headers: { ...authHeaders, 'Content-Type': 'application/octet-stream' },
    body:    buffer,
  });

  if (!uploadRes.ok) {
    const e = await uploadRes.json().catch(() => ({}));
    throw new Error(`AssemblyAI upload failed ${uploadRes.status}: ${e?.error || uploadRes.statusText}`);
  }
  const { upload_url } = await uploadRes.json();

  // Step 2: Request transcription (no speech_model — field is deprecated and causes 400)
  const body = { audio_url: upload_url };
  // Only add language_code if not hinglish (let AssemblyAI auto-detect for hinglish)
  if (lang === 'en-IN') body.language_code = 'en';
  if (lang === 'hi-IN') body.language_code = 'hi';

  console.log(`[AssemblyAI] submitting transcription...`);
  const txRes = await fetch('https://api.assemblyai.com/v2/transcript', {
    method:  'POST',
    headers: { ...authHeaders, 'Content-Type': 'application/json' },
    body:    JSON.stringify(body),
  });

  if (!txRes.ok) {
    const e = await txRes.json().catch(() => ({}));
    throw new Error(`AssemblyAI submit failed ${txRes.status}: ${e?.error || txRes.statusText}`);
  }
  const { id } = await txRes.json();

  // Step 3: Poll until complete (max 25 seconds)
  for (let i = 0; i < 25; i++) {
    await sleep(1000);
    const pollRes  = await fetch(`https://api.assemblyai.com/v2/transcript/${id}`, { headers: authHeaders });
    const pollData = await pollRes.json();

    console.log(`[AssemblyAI] poll ${i+1}: status=${pollData.status}`);

    if (pollData.status === 'completed') {
      return res.status(200).json({ transcript: pollData.text || '', provider: 'assemblyai' });
    }
    if (pollData.status === 'error') {
      throw new Error(`AssemblyAI error: ${pollData.error}`);
    }
  }

  throw new Error('AssemblyAI timed out after 25 seconds.');
}

/* ============================================================
   SARVAM AI  (~1-3 seconds, best for Hinglish)
   ============================================================ */
async function transcribeSarvam(buffer, mimeType, lang, res) {
  const apiKey = process.env.SARVAM_API_KEY;
  if (!apiKey) return res.status(500).json({ error: 'SARVAM_API_KEY not set.' });

  // Sarvam language codes
  const sarvamLang = lang === 'en-IN' ? 'en-IN'
                   : lang === 'hi-IN' ? 'hi-IN'
                   : 'hi-IN'; // hinglish → hi-IN (Sarvam handles code-switching)

  const cleanMime = (mimeType || 'audio/webm').split(';')[0].trim();
  const ext       = cleanMime.includes('ogg') ? 'ogg'
                  : cleanMime.includes('mp4') ? 'mp4'
                  : 'webm';

  console.log(`[Sarvam] lang=${sarvamLang} mimeType=${cleanMime} bufferSize=${buffer.length}`);

  const formData = new FormData();
  formData.append('file', new Blob([buffer], { type: cleanMime }), `audio.${ext}`);
  formData.append('language_code', sarvamLang);
  formData.append('model', 'saarika:v2.5');
  formData.append('with_timestamps', 'false');

  const response = await fetch('https://api.sarvam.ai/speech-to-text', {
    method:  'POST',
    headers: { 'api-subscription-key': apiKey },
    body:    formData,
  });

  const rawText = await response.text().catch(() => '');
  let data = {};
  try { data = JSON.parse(rawText); } catch (_) {}

  if (!response.ok) {
    console.error(`[Sarvam] raw error body:`, rawText);
    throw new Error(`Sarvam ${response.status}: ${data?.message || data?.error || rawText || response.statusText}`);
  }

  const transcript = data?.transcript || '';
  console.log(`[Sarvam] transcript="${transcript}"`);

  return res.status(200).json({ transcript, provider: 'sarvam' });
}

/* ============================================================
   UTILITY
   ============================================================ */
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
