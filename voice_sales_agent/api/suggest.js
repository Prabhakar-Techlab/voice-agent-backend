const Groq = require('groq-sdk');

/* ============================================================
   PRODUCT KNOWLEDGE BASE
   ============================================================ */
const PRODUCT_KNOWLEDGE = `
NOTHING PHONE LINEUP — FULL SPECS & SALES DATA

1. NOTHING PHONE (4a) — ₹28,999 [FEATURED / BEST VALUE]
   Display: 6.78" AMOLED, 120Hz adaptive, 4500 nits peak, 440 PPI, Gorilla Glass 7i, 1.07B colors (10-bit)
   Processor: Snapdragon 7s Gen 4 (4nm), 8-core 2.7GHz, Adreno 810 GPU
   Memory: 8GB RAM (12GB variant available), 256GB UFS 3.1 (no microSD)
   Camera: 50MP main f/1.88 OIS | 3.5x periscope telephoto | 120° ultrawide f/2.2 | 32MP front 89° FOV
           Up to 70x Ultra Zoom | TrueLens Engine 4 AI photography | 4K@30fps/60fps video | OIS stabilized
   Battery: 5,400mAh (India), 50W wired fast charge (0-50% in 20min, full in ~55min), 7.5W reverse wireless
   Build: IP64 (splash/dust resistant), 205g, 163.9×77.5×8.5mm, Black/White/Pink/Blue
   Software: Nothing OS with Essential AI, 3 years Android updates, 6 years security updates
   Unique: Glyph Interface (patented LED system on back — notifications, calls, music, timer, customizable per contact)
   Box includes: Phone, 50W charger, USB-C cable, SIM tool, guide, warranty card

2. NOTHING PHONE (3a) — ₹26,999 [BEST SELLER / MOST POPULAR]
   Display: 6.77" AMOLED, 120Hz adaptive
   Processor: Snapdragon 7s Gen 3 (4nm)
   Memory: 8GB/12GB RAM, 128GB/256GB storage
   Camera: 50MP main f/1.88 OIS/EIS | 50MP tele 2x optical zoom | 8MP 120° ultrawide | 12MP front
   Battery: 5,000mAh, 2-day battery life, fast charging
   Build: IP64, White/Black/Blue
   Software: Nothing OS with AI, 6 years security updates (until 2030)
   Unique: Glyph Interface, best price-to-performance in lineup, 6yr updates (most brands give 2-3yr)

3. NOTHING PHONE (3a) PRO — ₹32,999 [PRO CAMERA / POWER USER]
   Display: 6.77" AMOLED, 120Hz, 3000 nits
   Processor: Snapdragon 7s Gen 3 (4nm)
   Memory: 12GB RAM expandable to 20GB via RAM Boost, 256GB storage
   Camera: 50MP main f/1.88 OIS/EIS | 50MP PERISCOPE tele 3x optical 60x digital | 8MP ultrawide | 12MP front
   Battery: 5,000mAh, 50W wired, 7.5W reverse wireless, IP64, 211g
   Build: Vapor chamber cooling system (better sustained gaming performance), IP64
   Software: Nothing OS 3.1 (Android 15), 3 Android updates + 6yr security updates
   Unique: Periscope telephoto (usually found in ₹60K+ phones), 20GB RAM expansion, vapor chamber

4. NOTHING PHONE (3) — ₹52,999 [FLAGSHIP]
   Display: 6.67" AMOLED, 120Hz, 4500 nits
   Processor: Snapdragon 8s Gen 4 (4nm) — FLAGSHIP class chipset
   Memory: 12GB/16GB RAM, 256GB/512GB storage
   Camera: QUAD 50MP system — main f/1.68 OIS/EIS | 50MP periscope 3x optical 60x digital | 50MP ultrawide | 50MP front
   Battery: 5,500mAh, 65W wired, 15W wireless charging (Qi compatible), reverse wireless, IP68
   Build: IP68 (fully waterproof 1.5m/30min), 218g, White/Black
   Software: Nothing OS with AI
   Unique: Only Nothing phone with IP68 + wireless charging. Flagship Snapdragon 8s Gen 4.

COMPETITOR COMPARISONS:
- Samsung Galaxy A55 (₹39,999) vs Phone 4a (₹28,999): Save ₹11,000. Nothing: 4.5x brighter display (4500 vs 1000 nits), 70x zoom vs basic, larger battery (5400 vs 5000mAh), 2x faster charging (50W vs 25W), unique Glyph Interface
- OnePlus Nord 4 (~₹30,000) vs Phone 4a: Better zoom (70x), brighter display, Glyph, similar price
- Samsung Galaxy S24 (₹74,999) vs Phone 3 (₹52,999): Save ₹22,000 with comparable flagship specs
- iPhone 15 (₹79,900) vs Phone 3 (₹52,999): Save ₹27,000. Nothing: better zoom (60x vs 2x), larger battery, 3x faster charging (65W vs 20W)
- Redmi Note 13 Pro+ (~₹27,999) vs Phone 3a (₹26,999): Nothing: cleaner OS, better build, 6yr updates vs 2yr
- Realme GT 6T (~₹33,000) vs Phone 3a Pro (₹32,999): Nothing: periscope camera, cleaner OS, Glyph

BRAND INFO:
- Nothing founded by Carl Pei (OnePlus co-founder)
- Backed by Tony Fadell (designed the iPod at Apple) and major investors
- Multiple international design awards
- Millions of phones sold globally
- Glyph Interface is patented technology
- Authorized service centers in all major Indian cities including Noida Sector 18
- Doorstep pickup & delivery service available
- 1-year manufacturer warranty on all models

COMMON SALES SITUATIONS:
- Price objection: Bank discounts ₹1-2K (HDFC, ICICI, SBI). Exchange value ₹2-5K. No-cost EMI from ₹1,200/month.
- Storage: 256GB = ~50,000 photos / 200 hours HD video. Google Photos backup available.
- Gaming: Snapdragon handles BGMI, Genshin Impact, CoD Mobile at high settings. 120Hz display advantage.
- Service: Noida Sector 18 authorized center. Doorstep service. 1yr warranty. Vijay Sales additional support.
- Warranty extension: Up to 2 years total through extended warranty plans.
`;

/* ============================================================
   HANDLER
   ============================================================ */
module.exports = async function handler(req, res) {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { transcript, model, modelName, modelPrice, history } = req.body || {};

  if (!transcript || typeof transcript !== 'string' || transcript.trim().length < 2) {
    return res.status(400).json({ error: 'transcript is required' });
  }

  if (!process.env.GROQ_API_KEY) {
    return res.status(500).json({ error: 'GROQ_API_KEY environment variable is not set.' });
  }

  const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

  const currentModel = modelName || 'Nothing Phone';
  const currentPrice = modelPrice || '';

  const systemPrompt = `${PRODUCT_KNOWLEDGE}

You are an AI sales assistant helping a salesperson at a retail store sell Nothing phones in real time.

The salesperson is currently discussing: ${currentModel} (${currentPrice}).

A customer just said something. Your job is to give the salesperson 3 short, confident talking points to respond with.

RULES:
- Be conversational and natural — the salesperson will speak these words to a real customer
- Be specific: use actual specs, actual prices, actual comparisons when relevant
- Be persuasive but honest
- Keep each point concise (2-4 sentences max)
- Reference the selected model (${currentModel}) specifically
- If the customer is comparing with another brand, acknowledge that brand by name and give concrete advantages

Respond ONLY with a valid JSON object in this exact format:
{
  "keyPoint": "The main, most persuasive response to what the customer said. Start speaking this immediately.",
  "supportingFact": "A specific fact, number, or comparison that backs up the key point.",
  "closingLine": "A single sentence to move the customer toward a decision or next step."
}`;

  // Build multi-turn history so Groq remembers the full conversation
  const pastMessages = [];
  if (Array.isArray(history)) {
    // Keep last 10 turns to stay within token limits
    const recent = history.slice(-10);
    for (const entry of recent) {
      pastMessages.push({ role: 'user', content: `Customer said: "${entry.transcript}"` });
      if (entry.aiResult) {
        pastMessages.push({ role: 'assistant', content: JSON.stringify(entry.aiResult) });
      }
    }
  }

  try {
    const completion = await groq.chat.completions.create({
      model: 'llama-3.3-70b-versatile',
      messages: [
        { role: 'system', content: systemPrompt },
        ...pastMessages,
        { role: 'user',   content: `Customer said: "${transcript.trim()}"` },
      ],
      response_format: { type: 'json_object' },
      temperature: 0.65,
      max_tokens: 600,
    });

    const raw = completion.choices[0]?.message?.content;
    if (!raw) throw new Error('Empty response from Groq');

    const parsed = JSON.parse(raw);

    // Validate structure
    const result = {
      keyPoint:       String(parsed.keyPoint      || '').trim() || 'Please repeat the question.',
      supportingFact: String(parsed.supportingFact || '').trim() || '',
      closingLine:    String(parsed.closingLine    || '').trim() || '',
    };

    return res.status(200).json(result);

  } catch (err) {
    console.error('[Groq Error]', err?.message || err);

    if (err?.status === 401) {
      return res.status(500).json({ error: 'Invalid GROQ_API_KEY. Check your Vercel environment variables.' });
    }
    if (err?.status === 429) {
      return res.status(429).json({ error: 'Groq rate limit reached. Please wait a moment and try again.' });
    }

    return res.status(500).json({ error: 'AI service error. Please try again.' });
  }
};
