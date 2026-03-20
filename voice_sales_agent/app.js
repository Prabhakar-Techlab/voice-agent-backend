/* ============================================================
   PRODUCT DATA  (extracted from reference files)
   ============================================================ */
const PRODUCTS = {
  'phone-4a': {
    name: 'Nothing Phone (4a)',
    price: '₹28,999',
    badge: 'FEATURED',
    variant: '8GB RAM · 256GB · Black / White / Pink / Blue',
    highlights: ['6.78" AMOLED 120Hz', '4500 nits', '50MP + 70x Zoom', '5,400mAh', '50W Fast Charge', 'Glyph Interface', 'IP64', 'SD 7s Gen 4'],
  },
  'phone-3a': {
    name: 'Nothing Phone (3a)',
    price: '₹26,999',
    badge: 'BEST SELLER',
    variant: '8GB/12GB RAM · 128GB/256GB · White / Black / Blue',
    highlights: ['6.77" AMOLED 120Hz', '50MP + 50MP Tele', '2-Day Battery', 'SD 7s Gen 3', '6yr Updates', 'IP64', 'Glyph Interface'],
  },
  'phone-3a-pro': {
    name: 'Nothing Phone (3a) Pro',
    price: '₹32,999',
    badge: 'PRO',
    variant: '12GB RAM · 256GB · Grey / Black',
    highlights: ['6.77" AMOLED 120Hz', '50MP Periscope 3x/60x', '20GB RAM Boost', 'Vapor Chamber', '5,000mAh', '50W Fast Charge', 'IP64'],
  },
  'phone-3': {
    name: 'Nothing Phone (3)',
    price: '₹52,999',
    badge: 'FLAGSHIP',
    variant: '12GB/16GB RAM · 256GB/512GB · White / Black',
    highlights: ['6.67" AMOLED 120Hz', '4500 nits', 'Quad 50MP Cameras', 'SD 8s Gen 4', '5,500mAh', '65W + 15W Wireless', 'IP68'],
  }
};

/* ============================================================
   QUICK SCENARIO PROMPTS
   ============================================================ */
const SCENARIOS = {
  price:      'The customer says the price is too high and is asking for a discount or a better deal.',
  brand:      'The customer has never heard of the Nothing brand and is skeptical about its reliability and after-sales service.',
  camera:     'The customer is asking about the camera quality, zoom capability, low light performance, and video recording.',
  battery:    'The customer is worried about battery life and wants to know how long it will last with heavy usage.',
  comparison: 'The customer wants to compare this Nothing phone with Samsung Galaxy and is leaning towards Samsung.',
  gaming:     'The customer plays BGMI, Call of Duty Mobile, and wants to know if this phone handles gaming smoothly.',
  warranty:   'The customer is asking about warranty coverage, service centers, and what happens if something goes wrong.',
  storage:    'The customer is asking if 256GB storage is enough and whether they can expand it with a memory card.',
};

/* ============================================================
   STT PROVIDER LABELS
   ============================================================ */
const PROVIDER_LABELS = {
  deepgram:   'Deepgram',
  assemblyai: 'AssemblyAI',
  sarvam:     'Sarvam AI',
  webspeech:  'Browser',
};

/* ============================================================
   STATE
   ============================================================ */
let selectedModel    = 'phone-4a';
let currentProvider  = 'deepgram';
let currentLanguage  = 'en-IN';
let isRecording      = false;
let mediaRecorder    = null;
let audioChunks      = [];
let micStream        = null;
let recognition      = null;          // Web Speech API instance
let wsTranscript     = '';            // live Web Speech interim text
let lastTranscript   = '';
let conversationHistory = [];
let exchangeCount    = 0;
let spaceHeld        = false;
let audioContext     = null;
let silenceTimer     = null;
let wsSilenceTimer   = null;
const SILENCE_THRESHOLD = 0.012;   // RMS level below this = silence
const SILENCE_DURATION  = 3000;    // auto-stop after 3 s of silence

/* ============================================================
   DOM REFS
   ============================================================ */
const micBtn          = document.getElementById('micBtn');
const micHint         = document.getElementById('micHint');
const micRings        = document.getElementById('micRings');
const micIcon         = micBtn.querySelector('.mic-icon');
const stopIcon        = micBtn.querySelector('.stop-icon');

const recDot          = document.getElementById('recDot');
const recText         = document.getElementById('recText');

const transcriptBox   = document.getElementById('transcriptBox');
const transcriptText  = document.getElementById('transcriptText');

const historyList     = document.getElementById('historyList');
const historyCount    = document.getElementById('historyCount');

const modelRefName    = document.getElementById('modelRefName');
const modelRefVariant = document.getElementById('modelRefVariant');
const modelRefPrice   = document.getElementById('modelRefPrice');
const highlightsRow   = document.getElementById('highlightsRow');

const aiIdle          = document.getElementById('aiIdle');
const aiProcessing    = document.getElementById('aiProcessing');
const aiResults       = document.getElementById('aiResults');
const aiError         = document.getElementById('aiError');

const procTranscript  = document.getElementById('procTranscript');
const keyPoint        = document.getElementById('keyPoint');
const supportingFact  = document.getElementById('supportingFact');
const closingLine     = document.getElementById('closingLine');

const listenAgainBtn  = document.getElementById('listenAgainBtn');
const copyResponseBtn = document.getElementById('copyResponseBtn');
const convoThread     = document.getElementById('convoThread');
const convoList       = document.getElementById('convoList');
const convoCount      = document.getElementById('convoCount');
const newSessionBtn   = document.getElementById('newSessionBtn');
const retryBtn        = document.getElementById('retryBtn');
const errorMsg        = document.getElementById('errorMsg');
const browserWarn     = document.getElementById('browserWarn');
const connDot         = document.querySelector('.conn-dot');
const connLabel       = document.querySelector('.conn-label');

/* ============================================================
   UI STATE
   ============================================================ */
function setAIState(state) {
  [aiIdle, aiProcessing, aiResults, aiError].forEach(el => el.classList.add('hidden'));
  const map = { idle: aiIdle, processing: aiProcessing, results: aiResults, error: aiError };
  if (map[state]) map[state].classList.remove('hidden');
}

function setRecStatus(state, label) {
  recDot.className = 'rec-dot ' + state;
  const labels = {
    idle:       'Ready to listen',
    recording:  `Listening via ${PROVIDER_LABELS[currentProvider]}...`,
    processing: 'Transcribing...',
    success:    'Response ready',
  };
  recText.textContent = label || labels[state] || state;
}

function setConnStatus(state, label) {
  connDot.className = 'conn-dot' + (state !== 'ok' ? ' ' + state : '');
  connLabel.textContent = label || (state === 'ok' ? 'Ready' : state);
}

function setRecordingUI(on) {
  micBtn.classList.toggle('recording', on);
  micRings.classList.toggle('recording', on);
  micIcon.classList.toggle('hidden', on);
  stopIcon.classList.toggle('hidden', !on);
  micHint.textContent = on ? 'Click to stop · Auto-stops after 5 s of silence' : 'Click to listen to customer';
}

/* ============================================================
   MODEL SELECTION
   ============================================================ */
function selectModel(modelId) {
  selectedModel = modelId;
  const data = PRODUCTS[modelId];

  document.querySelectorAll('.model-card').forEach(t =>
    t.classList.toggle('active', t.dataset.model === modelId)
  );

  modelRefName.textContent    = data.name;
  modelRefVariant.textContent = data.variant;
  modelRefPrice.textContent   = data.price;

  highlightsRow.innerHTML = data.highlights
    .map(h => `<span class="highlight-chip">${h}</span>`)
    .join('');

  setAIState('idle');
  setRecStatus('idle');
}

document.querySelectorAll('.model-card').forEach(tab =>
  tab.addEventListener('click', () => selectModel(tab.dataset.model))
);

/* ============================================================
   STT PROVIDER SELECTION
   ============================================================ */
function selectProvider(provider) {
  currentProvider = provider;

  document.querySelectorAll('.stt-tab').forEach(t =>
    t.classList.toggle('active', t.dataset.provider === provider)
  );

  // Show browser warning if Web Speech not supported and browser selected
  if (provider === 'webspeech') {
    const supported = !!(window.SpeechRecognition || window.webkitSpeechRecognition);
    browserWarn.classList.toggle('hidden', supported);
  } else {
    browserWarn.classList.add('hidden');
  }
}

document.querySelectorAll('.stt-tab').forEach(tab =>
  tab.addEventListener('click', () => selectProvider(tab.dataset.provider))
);

/* ============================================================
   LANGUAGE SELECTION
   ============================================================ */
function selectLanguage(lang) {
  currentLanguage = lang;
  document.querySelectorAll('.lang-tab').forEach(t =>
    t.classList.toggle('active', t.dataset.lang === lang)
  );
  // Reset Web Speech instance so it picks up the new language
  recognition = null;
}

document.querySelectorAll('.lang-tab').forEach(tab =>
  tab.addEventListener('click', () => selectLanguage(tab.dataset.lang))
);

/* ============================================================
   WEB SPEECH API (Browser native — live display + fallback)
   ============================================================ */
function setupWebSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return null;

  const rec = new SR();
  rec.continuous     = true;
  rec.interimResults = true;

  // Map language selection to Web Speech lang codes
  const langMap = { 'en-IN': 'en-IN', 'hi-IN': 'hi-IN', 'hinglish': 'hi-IN' };
  rec.lang = langMap[currentLanguage] || 'en-IN';

  rec.onresult = (e) => {
    let interim = '', final = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript;
      e.results[i].isFinal ? (final += t + ' ') : (interim += t);
    }
    if (final) wsTranscript = (wsTranscript + ' ' + final).trim();
    transcriptText.textContent = (wsTranscript + ' ' + interim).trim() || '...';

    // Reset the silence auto-stop timer on each new result
    if (wsSilenceTimer) { clearTimeout(wsSilenceTimer); wsSilenceTimer = null; }
    wsSilenceTimer = setTimeout(() => { if (isRecording) stopRecording(null); }, SILENCE_DURATION);
  };

  rec.onerror = (e) => {
    if (e.error === 'not-allowed') {
      showError('Microphone permission denied. Please allow microphone access in your browser.');
    } else if (e.error !== 'no-speech' && e.error !== 'aborted') {
      console.warn('[WebSpeech error]', e.error);
    }
  };

  rec.onend = () => {
    if (isRecording && currentProvider === 'webspeech') {
      try { rec.start(); } catch (_) {}
    }
  };

  return rec;
}

/* ============================================================
   LIVE DISPLAY  — Web Speech for real-time preview during REST recording
   (display only — actual transcription still done by the selected provider)
   ============================================================ */
let liveRec     = null;
let liveText    = '';

function startLiveDisplay() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return;
  liveText = '';
  try {
    liveRec = new SR();
    liveRec.continuous     = true;
    liveRec.interimResults = true;
    const langMap = { 'en-IN': 'en-IN', 'hi-IN': 'hi-IN', 'hinglish': 'hi-IN' };
    liveRec.lang = langMap[currentLanguage] || 'en-IN';

    liveRec.onresult = (e) => {
      let interim = '', final = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        e.results[i].isFinal ? (final += t + ' ') : (interim += t);
      }
      if (final) liveText = (liveText + ' ' + final).trim();
      transcriptText.textContent = (liveText + ' ' + interim).trim() || 'Listening...';
    };
    liveRec.onend = () => {
      if (isRecording && liveRec) try { liveRec.start(); } catch (_) {}
    };
    liveRec.onerror = (e) => {
      if (e.error !== 'aborted' && e.error !== 'no-speech') {
        transcriptText.textContent = 'Listening... (live preview unavailable)';
      }
    };
    liveRec.start();
  } catch (_) {}
}

function stopLiveDisplay() {
  if (liveRec) { try { liveRec.abort(); } catch (_) {} liveRec = null; }
}

// Stop Web Speech and wait for final result (async)
function stopWebSpeechAndGetTranscript() {
  return new Promise((resolve) => {
    if (!recognition) { resolve(wsTranscript.trim()); return; }

    const timeout = setTimeout(() => resolve(wsTranscript.trim()), 1500);

    recognition.onend = () => {
      clearTimeout(timeout);
      resolve(wsTranscript.trim());
    };

    try { recognition.stop(); } catch (_) { resolve(wsTranscript.trim()); }
  });
}

/* ============================================================
   MEDIA RECORDER (for Deepgram / AssemblyAI / Sarvam)
   ============================================================ */
async function getMicStream() {
  if (micStream && micStream.active) return micStream;
  micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  return micStream;
}

function startMediaRecorder(stream) {
  audioChunks = [];

  // Pick best audio-only format (avoid video/webm which Chrome uses by default)
  const preferred = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ];
  const mimeType = preferred.find(t => MediaRecorder.isTypeSupported(t)) || '';

  console.log('[MediaRecorder] using mimeType:', mimeType || '(browser default)');

  mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
  mediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) audioChunks.push(e.data);
  };
  // No timeslice — collect all data at once when stopped (produces valid complete file)
  mediaRecorder.start();
}

/* ============================================================
   SILENCE DETECTION  (AudioContext RMS-based)
   ============================================================ */
function startSilenceDetection(stream) {
  try {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source  = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);

    const data = new Uint8Array(analyser.frequencyBinCount);

    function tick() {
      if (!isRecording) return;
      analyser.getByteTimeDomainData(data);

      let sum = 0;
      for (let i = 0; i < data.length; i++) {
        const v = (data[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / data.length);

      if (rms < SILENCE_THRESHOLD) {
        if (!silenceTimer) {
          silenceTimer = setTimeout(() => {
            if (isRecording) stopRecording(null);
          }, SILENCE_DURATION);
        }
      } else {
        // Voice detected — reset silence countdown
        if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
      }

      requestAnimationFrame(tick);
    }
    tick();
  } catch (err) {
    console.warn('[SilenceDetection] not available:', err.message);
  }
}

function stopSilenceDetection() {
  if (silenceTimer)   { clearTimeout(silenceTimer);   silenceTimer   = null; }
  if (wsSilenceTimer) { clearTimeout(wsSilenceTimer); wsSilenceTimer = null; }
  if (audioContext)   { audioContext.close().catch(() => {}); audioContext = null; }
}

function stopMediaRecorder() {
  return new Promise((resolve) => {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') {
      resolve(null);
      return;
    }
    mediaRecorder.onstop = () => {
      const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
      resolve(blob);
    };
    mediaRecorder.stop();
  });
}

async function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result.split(',')[1]);
    reader.onerror   = reject;
    reader.readAsDataURL(blob);
  });
}

/* ============================================================
   START RECORDING
   ============================================================ */
async function startRecording(e) {
  if (e) e.preventDefault();
  if (isRecording || micBtn.disabled) return;

  isRecording   = true;
  wsTranscript  = '';

  setAIState('idle');
  setRecStatus('recording');
  setRecordingUI(true);
  transcriptBox.classList.remove('hidden');
  transcriptText.textContent = '...';

  if (currentProvider === 'webspeech') {
    // Pure Web Speech mode
    if (!recognition) recognition = setupWebSpeech();
    if (!recognition) {
      browserWarn.classList.remove('hidden');
      stopAllRecording();
      return;
    }
    try { recognition.start(); } catch (_) {}

    // Auto-stop after 5 s of no new results
    wsSilenceTimer = setTimeout(() => {
      if (isRecording) stopRecording(null);
    }, SILENCE_DURATION);

  } else {
    // MediaRecorder mode (Deepgram / AssemblyAI / Sarvam)
    transcriptText.textContent = 'Listening...';
    try {
      // Start live display FIRST so Web Speech gets mic access before MediaRecorder
      startLiveDisplay();
      await new Promise(r => setTimeout(r, 400));

      const stream = await getMicStream();
      startMediaRecorder(stream);
      startSilenceDetection(stream);
    } catch (err) {
      console.error('[Mic error]', err);
      showError('Microphone access denied. Please allow microphone permission and try again.');
      stopAllRecording();
    }
  }
}

/* ============================================================
   STOP RECORDING
   ============================================================ */
async function stopRecording(e) {
  if (e) e.preventDefault();
  if (!isRecording) return;

  isRecording = false;
  stopSilenceDetection();
  stopLiveDisplay();
  setRecordingUI(false);
  setRecStatus('processing');

  if (currentProvider === 'webspeech') {
    // Wait for Web Speech to flush final result before reading
    const transcript = await stopWebSpeechAndGetTranscript();
    recognition = null; // reset for next session

    if (!transcript || transcript.length < 2) {
      showError('No speech detected. Make sure your microphone is allowed and speak clearly.');
      return;
    }
    lastTranscript = transcript;
    transcriptText.textContent = lastTranscript;
    fetchSuggestion(lastTranscript);
    return;
  }

  // Stop MediaRecorder and get blob
  const blob = await stopMediaRecorder();

  if (!blob || blob.size < 2000) {
    showError('No audio captured — your microphone may be muted or too quiet. Check your mic settings and try again.');
    return;
  }

  try {
    const base64Audio = await blobToBase64(blob);
    console.log('[Audio] blob size:', blob.size, 'type:', blob.type);
    const transcript  = await transcribeAudio(base64Audio, blob.type);

    if (!transcript || transcript.trim().length < 2) {
      showError(`No speech detected by ${PROVIDER_LABELS[currentProvider]}. Try speaking louder, or switch to "Browser" voice engine as a fallback.`);
      return;
    }

    lastTranscript = transcript.trim();
    transcriptText.textContent = lastTranscript;
    fetchSuggestion(lastTranscript);

  } catch (err) {
    console.error('[Transcription error]', err);
    showError(err.message || 'Transcription failed. Please check your API key and try again.');
  }
}

function stopAllRecording() {
  isRecording = false;
  stopSilenceDetection();
  stopLiveDisplay();
  setRecordingUI(false);
  setRecStatus('idle');
  if (recognition) { try { recognition.abort(); } catch (_) {} }
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    try { mediaRecorder.stop(); } catch (_) {}
  }
}

function resetToIdle() {
  setAIState('idle');
  setRecStatus('idle');
  transcriptBox.classList.add('hidden');
  transcriptText.textContent = '';
  wsTranscript = '';
}

/* ============================================================
   TRANSCRIBE AUDIO  →  /api/transcribe
   ============================================================ */
async function transcribeAudio(base64Audio, mimeType) {
  setConnStatus('loading', 'Transcribing...');

  const res = await fetch('/api/transcribe', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      provider:  currentProvider,
      audio:     base64Audio,
      mimeType:  mimeType || 'audio/webm',
      language:  currentLanguage,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Transcription error ${res.status}`);
  }

  const data = await res.json();
  return data.transcript || '';
}

/* ============================================================
   GET AI SUGGESTION  →  /api/suggest
   ============================================================ */
async function fetchSuggestion(transcript) {
  setAIState('processing');
  setConnStatus('loading', 'Thinking...');
  procTranscript.textContent = `"${transcript.slice(0, 100)}${transcript.length > 100 ? '...' : ''}"`;

  try {
    const res = await fetch('/api/suggest', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        transcript,
        model:      selectedModel,
        modelName:  PRODUCTS[selectedModel].name,
        modelPrice: PRODUCTS[selectedModel].price,
        history:    conversationHistory,   // full conversation so far
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `AI error ${res.status}`);
    }

    const data = await res.json();

    keyPoint.textContent       = data.keyPoint       || '—';
    supportingFact.textContent = data.supportingFact || '—';
    closingLine.textContent    = data.closingLine    || '—';

    setAIState('results');
    setRecStatus('success');
    setConnStatus('ok', 'Ready');
    addToHistory(transcript, { aiResult: { keyPoint: data.keyPoint, supportingFact: data.supportingFact, closingLine: data.closingLine } });

    // Persist last AI result so it survives a page refresh
    localStorage.setItem('lastResult', JSON.stringify({
      transcript, keyPoint: data.keyPoint, supportingFact: data.supportingFact, closingLine: data.closingLine
    }));

  } catch (err) {
    console.error('[AI error]', err);
    showError(err.message || 'Failed to get AI response. Check your API keys.');
    setConnStatus('error', 'Error');
  }
}

/* ============================================================
   QUICK SCENARIO BUTTONS
   ============================================================ */
document.querySelectorAll('.scenario-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const prompt = SCENARIOS[btn.dataset.scenario];
    if (!prompt) return;

    document.querySelectorAll('.scenario-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    setTimeout(() => btn.classList.remove('active'), 1500);

    lastTranscript = prompt;
    transcriptText.textContent = prompt;
    transcriptBox.classList.remove('hidden');
    fetchSuggestion(prompt);
  });
});

/* ============================================================
   ERROR
   ============================================================ */
function showError(msg) {
  errorMsg.textContent = msg || 'Something went wrong. Please try again.';
  setAIState('error');
  setRecStatus('idle');
  setConnStatus('error', 'Error');
}

retryBtn.addEventListener('click', () => {
  if (lastTranscript) fetchSuggestion(lastTranscript);
  else { setAIState('idle'); setRecStatus('idle'); setConnStatus('ok', 'Ready'); }
});

/* ============================================================
   LISTEN AGAIN
   ============================================================ */
listenAgainBtn.addEventListener('click', resetToIdle);

/* ============================================================
   COPY RESPONSE
   ============================================================ */
copyResponseBtn.addEventListener('click', () => {
  const text = [
    keyPoint.textContent,
    supportingFact.textContent,
    closingLine.textContent,
  ].filter(t => t && t !== '—').join('\n\n');

  navigator.clipboard.writeText(text).then(() => {
    copyResponseBtn.classList.add('copied');
    copyResponseBtn.querySelector('span') && (copyResponseBtn.querySelector('span').textContent = 'Copied!');
    setTimeout(() => {
      copyResponseBtn.classList.remove('copied');
    }, 2000);
  }).catch(() => {});
});

/* ============================================================
   NEW SESSION
   ============================================================ */
newSessionBtn.addEventListener('click', () => {
  if (exchangeCount > 0 && !confirm('Start a new session? This will clear the conversation log.')) return;

  conversationHistory = [];
  exchangeCount       = 0;
  lastTranscript      = '';
  wsTranscript        = '';

  localStorage.removeItem('conversationHistory');
  localStorage.removeItem('exchangeCount');
  localStorage.removeItem('lastResult');

  historyList.innerHTML    = '<div class="history-empty">Start a conversation to see the log here.</div>';
  historyCount.textContent = '0 exchanges';
  clearConvoThread();

  resetToIdle();
  setConnStatus('ok', 'Ready');
});

/* ============================================================
   CONVERSATION HISTORY
   ============================================================ */
function addToHistory(transcript, opts = {}) {
  exchangeCount++;

  const time  = opts.time || new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  const model = opts.model || selectedModel;
  const prov  = opts.provider || currentProvider;

  // ── Left panel session log ──
  const empty = historyList.querySelector('.history-empty');
  if (empty) empty.remove();

  const item = document.createElement('div');
  item.className = 'history-item';
  item.innerHTML = `
    <div class="history-customer">${escapeHTML(transcript.slice(0, 120))}${transcript.length > 120 ? '...' : ''}</div>
    <div class="history-time">${time} &bull; ${PRODUCTS[model]?.name || model} &bull; ${PROVIDER_LABELS[prov] || prov}</div>
  `;
  historyList.insertBefore(item, historyList.firstChild);
  const items = historyList.querySelectorAll('.history-item');
  if (items.length > 10) items[items.length - 1].remove();
  historyCount.textContent = `${exchangeCount} exchange${exchangeCount !== 1 ? 's' : ''}`;

  const entry = { transcript, model, provider: prov, time, aiResult: opts.aiResult || null };
  if (!opts.restoring) {
    conversationHistory.push(entry);
    localStorage.setItem('conversationHistory', JSON.stringify(conversationHistory));
    localStorage.setItem('exchangeCount', exchangeCount);
  }

  // ── Right panel conversation thread ──
  renderConvoItem(entry);
}

function renderConvoItem(entry) {
  const ai = entry.aiResult;

  const div = document.createElement('div');
  div.className = 'convo-item';
  div.innerHTML = `
    <div class="convo-time">${entry.time}</div>
    <div class="convo-bubble-customer"><p>${escapeHTML(entry.transcript)}</p></div>
    ${ai ? `
    <div class="convo-bubble-ai">
      <p>${escapeHTML(ai.keyPoint || '')}</p>
      ${ai.supportingFact ? `<p class="ai-supporting">${escapeHTML(ai.supportingFact)}</p>` : ''}
      ${ai.closingLine    ? `<p class="ai-closing">${escapeHTML(ai.closingLine)}</p>` : ''}
    </div>` : ''}
  `;

  convoList.appendChild(div);   // always append — newest at bottom

  convoThread.classList.remove('hidden');
  const total = convoList.querySelectorAll('.convo-item').length;
  convoCount.textContent = `${total} exchange${total !== 1 ? 's' : ''}`;

  // Scroll suggestions panel to bottom so new exchange is visible
  const panel = document.querySelector('.suggestions-panel');
  if (panel) panel.scrollTop = panel.scrollHeight;
}

function clearConvoThread() {
  convoList.innerHTML = '';
  convoThread.classList.add('hidden');
  convoCount.textContent = '';
}

/* ============================================================
   MIC BUTTON EVENTS  (click-toggle, not hold)
   ============================================================ */
micBtn.addEventListener('click', (e) => {
  if (isRecording) stopRecording(e);
  else             startRecording(e);
});
micBtn.addEventListener('touchend', (e) => {
  e.preventDefault();          // prevent ghost click on mobile
  if (isRecording) stopRecording(e);
  else             startRecording(e);
}, { passive: false });
micBtn.addEventListener('contextmenu', e => e.preventDefault());

/* ============================================================
   KEYBOARD — Spacebar toggles mic
   ============================================================ */
document.addEventListener('keydown', (e) => {
  if (e.code === 'Space' && !e.target.matches('input,textarea,button,select') && !spaceHeld) {
    e.preventDefault();
    spaceHeld = true;
    if (isRecording) stopRecording(null);
    else             startRecording(null);
  }
});
document.addEventListener('keyup', (e) => {
  if (e.code === 'Space') spaceHeld = false;
});

/* ============================================================
   UTILITY
   ============================================================ */
function escapeHTML(str) {
  return str
    .replace(/&/g,  '&amp;')
    .replace(/</g,  '&lt;')
    .replace(/>/g,  '&gt;')
    .replace(/"/g,  '&quot;');
}

/* ============================================================
   THEME TOGGLE  (dark / light)
   ============================================================ */
const themeToggle = document.getElementById('themeToggle');

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
  // Show sun icon in dark mode (click to go light), moon icon in light mode (click to go dark)
  themeToggle.setAttribute('aria-label', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
}

themeToggle.addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  applyTheme(current === 'dark' ? 'light' : 'dark');
});

/* ============================================================
   INIT
   ============================================================ */
(function init() {
  // Apply saved theme (default: dark)
  const savedTheme = localStorage.getItem('theme') || 'dark';
  applyTheme(savedTheme);

  selectModel('phone-4a');
  selectProvider('deepgram');
  setAIState('idle');
  setRecStatus('idle');
  setConnStatus('ok', 'Ready');

  // ── Restore conversation history ──────────────────────────
  try {
    const saved = JSON.parse(localStorage.getItem('conversationHistory') || '[]');
    if (saved.length > 0) {
      conversationHistory = saved;
      exchangeCount = parseInt(localStorage.getItem('exchangeCount') || saved.length, 10);

      // Left panel log — replay newest-first
      saved.slice().reverse().forEach(entry => {
        const empty2 = historyList.querySelector('.history-empty');
        if (empty2) empty2.remove();
        const item = document.createElement('div');
        item.className = 'history-item';
        item.innerHTML = `
          <div class="history-customer">${escapeHTML(entry.transcript.slice(0, 120))}${entry.transcript.length > 120 ? '...' : ''}</div>
          <div class="history-time">${entry.time} &bull; ${PRODUCTS[entry.model]?.name || entry.model} &bull; ${PROVIDER_LABELS[entry.provider] || entry.provider}</div>
        `;
        historyList.insertBefore(item, historyList.firstChild);
      });
      historyCount.textContent = `${exchangeCount} exchange${exchangeCount !== 1 ? 's' : ''}`;

      // Right panel thread — oldest to newest (natural chat order)
      saved.forEach(entry => renderConvoItem(entry));
    }
  } catch (_) {}

  // ── Restore last AI result ────────────────────────────────
  try {
    const last = JSON.parse(localStorage.getItem('lastResult') || 'null');
    if (last) {
      lastTranscript = last.transcript;
      keyPoint.textContent       = last.keyPoint       || '—';
      supportingFact.textContent = last.supportingFact || '—';
      closingLine.textContent    = last.closingLine    || '—';
      transcriptText.textContent = last.transcript;
      transcriptBox.classList.remove('hidden');
      setAIState('results');
      setRecStatus('success');
    }
  } catch (_) {}
})();
