# Phase 17: Voice Conversation with Deepgram STT/TTS

> Speak to Hermano and hear him reply — adding the missing sensory channel to conversational language learning

---

## Overview

Phase 17 adds voice input (Speech-to-Text) and voice output (Text-to-Speech) to Habla Hermano using Deepgram's Nova-3 and Aura-2 APIs. Currently, all interaction is text-based: users type messages, Hermano replies in text (streamed via SSE). This phase adds an optional voice layer — users can speak into their microphone and hear Hermano's responses spoken aloud — while preserving the existing text chat as the foundation.

**Business Value**: Language learning requires speaking and listening. Text-based pronunciation tips (Phase 11) can explain *how* to say something, but learners need to hear native-quality pronunciation and practice producing sounds themselves. Voice input also lowers the barrier for mobile users, where typing in a foreign language with special characters (ñ, ü, é) is friction-heavy.

**Core Principle**: Voice is additive, not replacing. The text chat, SSE streaming, scaffolding, grammar feedback, and pronunciation tips all continue working exactly as they do today. Voice layers on top as a progressive enhancement — tap a mic button to speak, tap a speaker icon to listen.

---

## Design Decisions

### Deepgram Over Alternatives

The core decision is to use **Deepgram** for both STT and TTS rather than alternatives (Google Cloud Speech, AWS Transcribe, OpenAI Whisper, ElevenLabs, Azure Cognitive Services).

#### Why Deepgram

1. **Unified STT + TTS provider**: One SDK, one API key, one billing relationship, one set of docs. Mixing providers (e.g., Whisper for STT + ElevenLabs for TTS) doubles integration complexity and operational surface area.

2. **Nova-3 multilingual codeswitching**: Deepgram's Nova-3 model natively handles speech that mixes languages in a single utterance — exactly what language learners produce. An A1 student saying "I want to go to the... uh... mercado" gets transcribed correctly without pre-selecting a single language. No other STT service handles this as a first-class feature.

3. **Aura-2 multilingual voices**: 17 Spanish voices (with regional accents: Mexican, Colombian, Peninsular, Argentine), 7 German voices, 2 French voices. Regional accent selection matters for language learning — a student learning Latin American Spanish shouldn't hear Peninsular pronunciation.

4. **WebSocket streaming for STT**: Real-time transcription with ~250ms latency. Students see their words appear as they speak, providing immediate feedback that they're being understood.

5. **Simple REST streaming for TTS**: MP3 audio streamed via HTTP response — no WebSocket complexity needed for the output direction. Browser `<audio>` element handles playback natively.

6. **Cost-effective**: ~$0.11 per 10-minute voice session (see Cost Analysis below). Competitive with or cheaper than alternatives at this scale.

#### Rejected: OpenAI Whisper (Self-Hosted)

- **Pros**: Free (no per-minute cost), highest accuracy for batch transcription
- **Cons**: No real-time streaming (batch-only), requires GPU infrastructure, no TTS (need a second provider), no codeswitching support, significant DevOps overhead
- **Why rejected**: The real-time streaming requirement and operational complexity rule this out. Self-hosting a Whisper model for a learning project adds infrastructure burden without proportional benefit.

#### Rejected: Google Cloud Speech-to-Text + Google Cloud TTS

- **Pros**: Mature, excellent language support, streaming STT available
- **Cons**: Complex GCP setup, separate SDKs for STT and TTS, TTS voices sound notably robotic compared to Deepgram Aura-2, no native codeswitching (must pre-select language), pricing is higher for comparable quality
- **Why rejected**: The codeswitching limitation is a deal-breaker for language learning. Google requires specifying a single language per stream — a student mixing English and Spanish would get poor results.

#### Rejected: ElevenLabs (TTS) + Deepgram (STT)

- **Pros**: ElevenLabs has arguably the most natural-sounding voices
- **Cons**: Two providers to manage, ElevenLabs pricing is 2-3x Deepgram TTS, limited multilingual voice selection, adds a second SDK and API key
- **Why rejected**: The quality difference doesn't justify the integration complexity and cost for this use case. Deepgram Aura-2 voices are natural enough for language tutoring.

### Server-Side Proxy Architecture

All Deepgram API calls are proxied through the FastAPI server. The browser never communicates directly with Deepgram.

**Rationale**:
- **API key security**: The Deepgram API key stays server-side, never exposed to the browser. Deepgram offers temporary tokens, but they're limited to 250/day and add complexity.
- **Consistent with existing patterns**: The SSE streaming endpoint (Phase 15) already proxies LLM calls through FastAPI. Voice follows the same pattern.
- **Request enrichment**: The server can inject context (user's language, level, session info) before forwarding to Deepgram.
- **Rate limiting and cost control**: Server-side proxy enables per-user rate limiting to prevent abuse.

**Trade-off**: Adds one network hop (browser → FastAPI → Deepgram). For STT, this adds ~50ms latency on top of Deepgram's ~250ms. For TTS, it's negligible since we're streaming audio chunks.

### WebSocket for STT, REST for TTS

**STT uses WebSocket**: Audio flows continuously from the browser microphone. A persistent WebSocket connection (browser → FastAPI → Deepgram) carries binary audio chunks in real-time and returns transcript events as JSON. This is the only viable pattern for live microphone transcription — HTTP request-response cannot handle a continuous audio stream.

**TTS uses REST with streaming response**: When the user taps "play" on a Hermano response, the browser makes a POST request to a FastAPI endpoint. FastAPI streams the audio response from Deepgram's REST API back to the browser as `audio/mpeg`. The browser plays it using the native `<audio>` element or `Audio()` constructor.

**Why not WebSocket for TTS?** Deepgram's WebSocket TTS only supports raw PCM formats (`linear16`, `mulaw`, `alaw`). The browser can't play raw PCM natively — it requires encoding to a playable format first (adding a WAV header or using AudioWorklet). The REST API supports MP3 directly, which every browser plays natively. Simpler is better.

### STT Transcription as Form Input (Not Direct Chat Submission)

When the user speaks, the transcribed text populates the chat input field — it does **not** auto-submit the message to the chat endpoint. The user sees their transcribed words, can edit them if needed, and then submits manually (tap send or press Enter).

**Rationale**:
- **User control**: Speech recognition isn't perfect. Users need to review and correct before sending, especially at lower levels where they may be unsure of what they said.
- **Consistency**: The chat submission flow remains identical regardless of input method (typed or spoken). The same form data goes to the same `/chat/stream` endpoint.
- **No LangGraph changes needed**: The chat pipeline processes text input. Voice is just an alternative way to produce that text. No agent, node, or prompt modifications required.
- **Simpler architecture**: Decoupling STT from chat submission means the voice system is purely a UI concern with a server-side transcription proxy. It doesn't touch the AI pipeline at all.

### TTS Triggered Post-Stream (Not During Streaming)

TTS is triggered **after** the SSE stream completes and Hermano's full response is assembled — not token-by-token during streaming.

**Rationale**:
- **Natural speech quality**: Synthesizing a complete sentence produces natural prosody, intonation, and pacing. Synthesizing token-by-token would produce choppy, robotic speech with incorrect sentence-level intonation.
- **Simpler implementation**: One TTS request per response, not hundreds of micro-requests per token stream.
- **User-initiated playback**: The user taps a speaker icon to hear the response. This avoids unexpected audio (important on mobile, in public spaces, etc.) and gives the user control over when voice is used.
- **Aligns with learning**: Students benefit from re-listening. A play button lets them replay Hermano's response multiple times to practice listening comprehension.

**Future consideration**: Auto-play TTS (optional setting where Hermano's responses are automatically spoken) could be added later as a user preference. The architecture supports this — it's just a UI toggle that triggers playback after `done` SSE event.

---

## Voice Selection Strategy

### Per-Language Default Voices

| Language | Default Voice | Model ID | Accent | Gender |
|----------|--------------|----------|--------|--------|
| Spanish | Celeste | `aura-2-celeste-es` | Colombian | Female |
| German | Elara | `aura-2-elara-de` | Standard | Female |
| French | Agathe | `aura-2-agathe-fr` | Standard | Female |

**Why these defaults**: Celeste (Colombian) was chosen over Peninsular Spanish voices because Latin American Spanish is more commonly studied worldwide. Elara and Agathe are the most natural-sounding voices in their respective language catalogs based on Deepgram's benchmarks.

### Alternative Voices (Future: User Preference)

| Language | Alternatives | Notes |
|----------|-------------|-------|
| Spanish | Estrella (Mexican), Nestor (male), + 14 more | Rich selection with regional accents |
| German | Julius (male), Aurelia, Lara, + 4 more | Moderate selection |
| French | Hector (male) | Only 2 voices total — limited |

Voice selection could become a user preference in a future phase. The architecture supports it — voice ID is a parameter on the TTS endpoint.

---

## Client Architecture

### UI Components

#### Microphone Button

A circular microphone button sits to the left of the chat input field (or below it on very narrow screens). Three visual states:

```
[🎤]  → Idle (gray, ready to record)
[🎤]  → Recording (red pulse animation, live transcript appears in input)
[⏹]  → Stop (tap again to stop recording)
```

**Microphone permissions**: On first tap, the browser requests microphone access via `navigator.mediaDevices.getUserMedia()`. If denied, the button shows a tooltip explaining that mic permission is needed. The app never auto-requests permission on page load — only on explicit user action.

#### Speaker Button on Hermano Responses

Each Hermano response bubble gets a small speaker icon:

```
┌──────────────────────────────────┐
│ ¡Muy bien! Me alegra oírte.     │
│ ¿Qué hiciste hoy?              │
│                          [🔊]   │
└──────────────────────────────────┘
```

Three states:
```
[🔊]  → Ready to play
[⏸]   → Playing (tap to pause)
[🔊]  → Finished (ready to replay)
```

#### Live Transcription Display

While recording, interim transcripts appear in the chat input field with a subtle visual distinction (lighter text or italics) to indicate they're not final. When speech ends, the final transcript replaces the interim text in normal style.

```
Input field while recording:
┌─────────────────────────────────────────┐
│ Yo fui al mercado ayer...              │ ← interim (light gray)
└─────────────────────────────────────────┘

After speech final:
┌─────────────────────────────────────────┐
│ Yo fui al mercado ayer                  │ ← final (normal text)
└─────────────────────────────────────────┘
```

### voice.js Module

A new ES module handles all client-side voice logic. It follows the same pattern as `stream.js` — imperative JavaScript that layers on top of the HTMX-driven page.

```javascript
// src/static/js/voice.js

export class VoiceManager {
    constructor(chatInput, micButton) {
        this.chatInput = chatInput;
        this.micButton = micButton;
        this.mediaRecorder = null;
        this.ws = null;
        this.isRecording = false;
    }

    async startRecording(language) {
        // 1. Request microphone permission
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        // 2. Detect supported mime type
        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : 'audio/mp4';

        // 3. Create MediaRecorder
        this.mediaRecorder = new MediaRecorder(stream, { mimeType });

        // 4. Open WebSocket to FastAPI transcription proxy
        const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(
            `${wsProtocol}//${location.host}/ws/transcribe?language=${language}`
        );

        // 5. Handle transcription results
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.is_final) {
                this.chatInput.value = data.transcript;
                this.chatInput.classList.remove('voice-interim');
            } else {
                this.chatInput.value = data.transcript;
                this.chatInput.classList.add('voice-interim');
            }
        };

        // 6. Stream audio chunks to server
        this.ws.onopen = () => {
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0 && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(event.data);
                }
            };
            this.mediaRecorder.start(250); // 250ms chunks
            this.isRecording = true;
            this.updateUI();
        };
    }

    stopRecording() {
        if (this.mediaRecorder?.state === 'recording') {
            this.mediaRecorder.stop();
        }
        this.mediaRecorder?.stream.getTracks().forEach(t => t.stop());
        this.ws?.close();
        this.isRecording = false;
        this.updateUI();
    }

    async playResponse(text, language) {
        // Map language to default voice
        const voices = {
            es: 'aura-2-celeste-es',
            de: 'aura-2-elara-de',
            fr: 'aura-2-agathe-fr',
        };

        const response = await fetch('/api/speak', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: text,
                voice: voices[language] || voices.es,
            }),
        });

        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);

        audio.onended = () => URL.revokeObjectURL(audioUrl);
        await audio.play();
        return audio; // caller can pause/stop
    }

    updateUI() { /* toggle mic button state */ }
}
```

**Responsibilities**:
- Manage microphone permissions and `MediaRecorder` lifecycle
- Open/close WebSocket connections to the transcription proxy
- Stream audio chunks to the server in real-time
- Display interim and final transcripts in the chat input
- Handle TTS playback for Hermano responses
- Clean up audio streams, WebSocket connections, and object URLs

---

## Server Architecture

### WebSocket Transcription Proxy (`/ws/transcribe`)

A new WebSocket endpoint in FastAPI acts as a proxy between the browser and Deepgram's STT WebSocket API.

```python
# src/api/routes/voice.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from deepgram import AsyncDeepgramClient

router = APIRouter()

@router.websocket("/ws/transcribe")
async def transcribe_stream(
    websocket: WebSocket,
    language: str = Query(default="es"),
):
    """Proxy browser audio to Deepgram STT and return transcripts.

    Audio flows: Browser mic → WebSocket → FastAPI → Deepgram WebSocket
    Transcripts flow: Deepgram → FastAPI → WebSocket → Browser

    Args:
        websocket: Browser WebSocket connection carrying audio chunks.
        language: BCP-47 language code or "multi" for codeswitching.
    """
    await websocket.accept()

    dg_client = get_deepgram_client()  # from dependency injection

    # Determine STT language setting based on user's level
    # A0-A1: use "multi" for codeswitching tolerance
    # A2-B1: use specific language code for better accuracy
    stt_language = language if language != "multi" else "multi"

    dg_config = {
        "model": "nova-3",
        "language": stt_language,
        "smart_format": True,
        "punctuate": True,
        "interim_results": True,
        "endpointing": 300,       # 300ms silence = speech final
        "utterance_end_ms": 1000, # 1s silence = utterance complete
        "vad_events": True,       # speech start detection
    }

    async with dg_client.listen.asyncwebsocket.v("1", dg_config) as dg_connection:

        async def on_transcript(self, result, **kwargs):
            """Forward Deepgram transcripts to the browser."""
            transcript = result.channel.alternatives[0].transcript
            is_final = result.is_final
            speech_final = result.speech_final

            if transcript:
                await websocket.send_json({
                    "transcript": transcript,
                    "is_final": is_final,
                    "speech_final": speech_final,
                })

        dg_connection.on(
            deepgram.LiveTranscriptionEvents.Transcript,
            on_transcript,
        )

        try:
            while True:
                audio_data = await websocket.receive_bytes()
                await dg_connection.send(audio_data)
        except WebSocketDisconnect:
            pass
```

**Key design points**:
- **Language parameter on WebSocket URL**: The browser passes the user's selected language as a query parameter. This avoids needing to negotiate language mid-stream.
- **Interim results enabled**: The browser shows live transcription as the user speaks. Interim results update progressively; `speech_final` indicates the definitive transcript for an utterance.
- **Endpointing at 300ms**: Configurable silence duration to detect speech boundaries. 300ms is responsive without cutting off natural pauses.
- **VAD events**: Voice Activity Detection events allow the client to show visual feedback when speech is detected (mic button pulses).

### TTS Endpoint (`POST /api/speak`)

A REST endpoint that proxies text to Deepgram's TTS API and streams audio back.

```python
# src/api/routes/voice.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx

class SpeakRequest(BaseModel):
    text: str
    voice: str = "aura-2-celeste-es"

@router.post("/api/speak")
async def speak(request: SpeakRequest):
    """Synthesize speech from text using Deepgram TTS.

    Returns an audio/mpeg stream for browser playback.
    The browser can play this directly via Audio() or <audio> element.
    """
    dg_api_key = get_deepgram_api_key()  # from config

    async def audio_stream():
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"https://api.deepgram.com/v1/speak?model={request.voice}&encoding=mp3",
                headers={
                    "Authorization": f"Token {dg_api_key}",
                    "Content-Type": "application/json",
                },
                json={"text": request.text},
                timeout=30.0,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(1024):
                    yield chunk

    return StreamingResponse(
        audio_stream(),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Content-Disposition": "inline",
        },
    )
```

**Key design points**:
- **MP3 format**: Universal browser support. No need for codec negotiation or format detection.
- **Streaming response**: Audio chunks flow through FastAPI to the browser without buffering the entire file in memory. First audio bytes arrive within ~300ms.
- **Voice parameter**: Allows the client to request specific voices. Defaults to Celeste (Spanish). The client selects the voice based on the user's active language.
- **No caching**: Each TTS request is unique (different text). `Cache-Control: no-cache` ensures proxies don't cache responses.

### Deepgram Client Initialization

```python
# src/api/config.py (additions)

class Settings:
    # ... existing settings ...
    DEEPGRAM_API_KEY: str = ""

# src/api/dependencies.py (additions)

from deepgram import AsyncDeepgramClient

_deepgram_client: AsyncDeepgramClient | None = None

def get_deepgram_client() -> AsyncDeepgramClient:
    """Get or create the shared Deepgram async client."""
    global _deepgram_client
    if _deepgram_client is None:
        api_key = get_settings().DEEPGRAM_API_KEY
        if not api_key:
            raise RuntimeError("DEEPGRAM_API_KEY not configured")
        _deepgram_client = AsyncDeepgramClient(api_key=api_key)
    return _deepgram_client
```

---

## Data Flow

### STT Flow (User Speaks)

```
Browser                    FastAPI                     Deepgram
───────                    ───────                     ────────
getUserMedia()
     │
MediaRecorder.start(250ms)
     │
  audio chunk ──WebSocket──► /ws/transcribe
     │                           │
     │                      audio chunk ──WebSocket──► Nova-3 STT
     │                           │                        │
     │                           │              transcript event
     │                           │                        │
     │                      ◄──────────────────────────────
     │                           │
  ◄──WebSocket── {"transcript":  │
     │            "Hola",        │
     │            "is_final":    │
     │            false}         │
     │                           │
  Show interim in input          │
     │                           │
  ... more chunks ...            │
     │                           │
  ◄──WebSocket── {"transcript":  │
     │            "Hola, ¿cómo   │
     │            estás?",       │
     │            "is_final":    │
     │            true}          │
     │                           │
  Show final in input            │
  User taps Send                 │
     │                           │
  POST /chat/stream ────────────►│
  (existing SSE flow)            │
```

### TTS Flow (Hermano Speaks)

```
Browser                    FastAPI                     Deepgram
───────                    ───────                     ────────
SSE stream completes
(Hermano's text ready)
     │
User taps 🔊
     │
POST /api/speak ──────────► /api/speak
  {text, voice}                  │
     │                    POST ─────────────────────► Aura-2 TTS
     │                           │                        │
     │                           │              audio chunks (mp3)
     │                           │                        │
     │                    ◄──────────────────────────────
     │                           │
  ◄── audio/mpeg stream ────────│
     │
  new Audio(blob).play()
```

---

## Dependencies

### New External Libraries

| Package | Version | Purpose |
|---------|---------|---------|
| `deepgram-sdk` | >= 3.0 | Deepgram Python SDK for STT WebSocket and TTS REST calls |
| `httpx` | >= 0.25 | Async HTTP client for streaming TTS proxy (already a transitive dependency) |

**No new frontend dependencies.** The implementation uses:
- `navigator.mediaDevices.getUserMedia()` (native browser API)
- `MediaRecorder` (native browser API)
- `WebSocket` (native browser API)
- `Audio()` (native browser API)

### New Internal Modules

| Module | Purpose |
|--------|---------|
| `src/api/routes/voice.py` | WebSocket `/ws/transcribe` endpoint + REST `POST /api/speak` endpoint |
| `src/static/js/voice.js` | Client-side `VoiceManager` class — mic capture, WebSocket streaming, TTS playback |

### Modified Internal Modules

| Module | Change |
|--------|--------|
| `src/api/main.py` | Register voice router |
| `src/api/config.py` | Add `DEEPGRAM_API_KEY` setting |
| `src/api/dependencies.py` | Add `get_deepgram_client()` |
| `src/templates/chat.html` | Add mic button, speaker icons, load `voice.js` |
| `src/templates/partials/message_pair.html` | Add speaker icon to Hermano response bubbles |

### Unchanged Modules

The following are explicitly **not modified**:
- `src/agent/` — No changes to LangGraph graph, nodes, prompts, or state
- `src/api/routes/chat.py` — The `/chat` and `/chat/stream` endpoints are unchanged
- `src/api/streaming.py` — SSE streaming logic is unchanged
- `src/services/` — No changes to progress, review, or path services
- `src/db/` — No new database tables or schema changes

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPGRAM_API_KEY` | Yes (for voice) | `""` | Deepgram API key for STT and TTS |

**Graceful degradation**: If `DEEPGRAM_API_KEY` is empty, voice features are disabled. The mic button and speaker icons don't render. The app functions identically to the current text-only experience. This is enforced in the Jinja2 template:

```html
{% if config.DEEPGRAM_API_KEY %}
  <button id="mic-btn" class="voice-mic-btn" aria-label="Record voice message">🎤</button>
{% endif %}
```

### Deepgram STT Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `model` | `nova-3` | Best accuracy, multilingual codeswitching |
| `language` | `multi` (A0-A1) or specific BCP-47 (A2-B1) | Codeswitching tolerance for beginners, precision for advanced |
| `smart_format` | `true` | Auto-capitalizes, adds punctuation |
| `punctuate` | `true` | Adds periods, question marks |
| `interim_results` | `true` | Live transcription display |
| `endpointing` | `300` | 300ms silence = speech boundary |
| `utterance_end_ms` | `1000` | 1s silence = utterance complete |
| `vad_events` | `true` | Visual feedback for speech detection |

### Deepgram TTS Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `model` | Per-language default (see voice table) | Language-appropriate voice |
| `encoding` | `mp3` | Universal browser support |

---

## Cost Analysis

### Per-Session Estimate

Assuming a 10-minute voice conversation session:
- ~5 minutes of student speech (STT)
- ~2,000 characters of Hermano TTS responses

| Service | Calculation | Cost |
|---------|------------|------|
| STT (Nova-3 multilingual) | 5 min × $0.0092/min | $0.046 |
| TTS (Aura-2) | 2,000 chars × $0.030/1K chars | $0.060 |
| **Total per session** | | **$0.106** |

### Cost Controls

1. **Server-side proxy**: All requests go through FastAPI, enabling per-user rate limiting
2. **No auto-play TTS**: Users explicitly tap to hear responses, preventing unnecessary TTS calls
3. **Session-level limits**: Consider capping TTS requests per session (e.g., 50 playbacks) to prevent abuse
4. **Deepgram billing is per-second**: STT is billed by actual audio seconds, not rounded up to minutes

### Free Tier

Deepgram offers $200 in free credit for new accounts (no expiration, no credit card required). This covers approximately:
- ~1,800 voice sessions at $0.11 each
- Sufficient for development, testing, and early users

---

## Browser Compatibility

### Required APIs

| API | Chrome | Firefox | Safari | Edge |
|-----|--------|---------|--------|------|
| `getUserMedia()` | 53+ | 36+ | 11+ | 12+ |
| `MediaRecorder` | 47+ | 25+ | 14.1+ | 79+ |
| `WebSocket` | 16+ | 11+ | 7+ | 12+ |
| `Audio()` | 4+ | 3.5+ | 4+ | 12+ |

All required APIs are supported in every modern browser. The main concern is **Safari's MediaRecorder**, which was added in Safari 14.1 (April 2021). It produces `audio/mp4` instead of `audio/webm`, but Deepgram handles both container formats automatically.

### Mobile Considerations

- **iOS Safari**: `getUserMedia` requires HTTPS. Development on `localhost` works, but deployed environments must use HTTPS (already the case for Render deployments).
- **Android Chrome**: Full support. `audio/webm;codecs=opus` is the default.
- **Microphone on mobile**: The browser shows a system-level permission dialog. Once granted, it persists for the session.
- **Audio playback on mobile**: iOS requires a user gesture to play audio. The "tap speaker icon" pattern satisfies this requirement.

---

## Error Handling

### STT Errors

| Error | Detection | User Experience |
|-------|-----------|-----------------|
| Microphone permission denied | `getUserMedia` rejection | Tooltip: "Microphone access needed for voice input" |
| WebSocket connection failed | `ws.onerror` / `ws.onclose` | Mic button shows error state, falls back to text input |
| Deepgram API error | Error event from Deepgram | Mic button resets, toast: "Voice input temporarily unavailable" |
| No speech detected | `utterance_end_ms` timeout with empty transcript | Mic button resets automatically |
| Network interruption | WebSocket close during recording | Stop recording, preserve any partial transcript in input |

### TTS Errors

| Error | Detection | User Experience |
|-------|-----------|-----------------|
| Deepgram API error | HTTP 4xx/5xx from `/api/speak` | Speaker icon shows error state, toast: "Couldn't play audio" |
| Empty text | Client-side check before request | Speaker icon not shown for empty responses |
| Audio playback failed | `audio.onerror` | Speaker icon resets to ready state |
| Network timeout | `httpx` timeout (30s) | Same as API error |

### Deepgram Service Unavailable

If Deepgram is down or the API key is invalid, voice features degrade gracefully:
- STT: Mic button disabled with tooltip "Voice input unavailable"
- TTS: Speaker icons hidden
- Text chat continues working normally — zero impact on core functionality

---

## Security Considerations

### API Key Protection

- `DEEPGRAM_API_KEY` is stored server-side only (environment variable)
- Never transmitted to the browser in any response
- All Deepgram API calls originate from the server
- The WebSocket endpoint and TTS endpoint are the only code that reads the key

### Audio Data Privacy

- Audio from the microphone is streamed directly to Deepgram for transcription — it is **not stored** on the FastAPI server
- Deepgram processes audio in real-time and does not retain audio data after transcription (per their data processing terms)
- TTS requests contain only the text to synthesize — no user-identifying information
- No audio recordings are saved to disk or database

### Rate Limiting

- WebSocket connections should be limited per user (e.g., 1 concurrent transcription session)
- TTS endpoint should be rate-limited (e.g., 30 requests per minute per user)
- Implementation via FastAPI middleware or per-route dependency

### Input Validation

- `language` query parameter on `/ws/transcribe` is validated against allowed values (`es`, `de`, `fr`, `multi`)
- `voice` parameter on `/api/speak` is validated against a whitelist of allowed Deepgram voice IDs
- `text` parameter on `/api/speak` is length-limited (e.g., max 2,000 characters per Deepgram's recommendation)

---

## Testing Strategy

### Unit Tests

**`tests/api/routes/test_voice.py`**:
- WebSocket transcription proxy connects and accepts audio
- WebSocket sends transcript JSON with correct schema (`transcript`, `is_final`, `speech_final`)
- WebSocket closes cleanly on client disconnect
- TTS endpoint returns `audio/mpeg` content type
- TTS endpoint validates voice parameter against whitelist
- TTS endpoint validates text length limit
- TTS endpoint returns 400 for empty text
- Missing `DEEPGRAM_API_KEY` returns appropriate error
- Invalid language parameter returns 422

**`tests/api/test_config.py`** (additions):
- `DEEPGRAM_API_KEY` setting loads from environment
- Empty `DEEPGRAM_API_KEY` results in voice features disabled

### Integration Tests

- Full STT flow: send audio bytes over WebSocket, receive transcript
- Full TTS flow: POST text, receive playable audio bytes
- Verify voice endpoints respect authentication (if auth required)
- Verify rate limiting on TTS endpoint

### Mock Strategy

Deepgram API calls are mocked in tests using:
- `unittest.mock.patch` on `AsyncDeepgramClient` for STT tests
- `respx` or `httpx` mocking for TTS REST proxy tests
- No real Deepgram API calls in CI (uses `$200 free credit` for manual testing only)

### Manual Testing

- Record and transcribe in each language (es, de, fr)
- Verify codeswitching: speak mixed English + target language
- Verify TTS playback in each language with default voice
- Test on mobile (iOS Safari, Android Chrome)
- Test microphone permission flow (grant, deny, revoke)
- Test with background noise and poor microphone
- Test rapid start/stop recording
- Test TTS while another audio is playing
- Verify graceful degradation when Deepgram API key is missing

---

## Success Criteria

### Functional

- [ ] User can tap mic button and speak — transcribed text appears in chat input
- [ ] User can edit transcribed text before sending
- [ ] User can tap speaker icon on any Hermano response to hear it spoken
- [ ] STT works for all three languages (es, de, fr)
- [ ] TTS plays correct language voice for each language
- [ ] Existing text chat continues working unchanged
- [ ] Voice features hidden when `DEEPGRAM_API_KEY` not configured

### Performance

- [ ] First interim transcript appears within 500ms of speaking
- [ ] Final transcript available within 300ms of stopping speech
- [ ] TTS audio playback begins within 1 second of tapping speaker icon
- [ ] No perceptible UI jank during recording or playback

### Technical

- [ ] WebSocket connections close cleanly (no leaked connections)
- [ ] MediaRecorder streams and tracks properly released after recording
- [ ] Audio object URLs revoked after playback (no memory leaks)
- [ ] Deepgram API key never appears in browser-accessible responses
- [ ] All existing tests pass unchanged
- [ ] New voice tests achieve 80%+ coverage of voice module

### Mobile

- [ ] Mic button and speaker icons are touch-friendly (48px+ targets)
- [ ] Recording works on iOS Safari and Android Chrome
- [ ] TTS playback works on iOS (respects user gesture requirement)
- [ ] Voice UI doesn't interfere with virtual keyboard or safe areas

---

## Future Enhancements (Not in Phase 17)

| Enhancement | Description | Complexity |
|-------------|-------------|------------|
| **Auto-play TTS** | User preference to auto-play Hermano responses | Low — UI toggle + auto-trigger after `done` SSE event |
| **Voice selection** | Let users choose from available voices per language | Low — dropdown in settings, voice ID passed to TTS |
| **Pronunciation scoring** | Compare user speech to expected pronunciation | High — requires phoneme-level analysis, possibly a different service |
| **Voice in lessons** | "Repeat after me" exercises using STT comparison | Medium — lesson subgraph changes + UI |
| **Continuous conversation** | Full voice-only mode (no typing, auto-send after speech) | Medium — auto-submit on `utterance_end_ms`, auto-play TTS |
| **Voice speed control** | Slow down TTS for beginners | Low — depends on Deepgram adding speed parameter |
