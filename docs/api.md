# Habla Hermano API Reference

> REST API documentation for Habla Hermano conversational language learning

---

## Overview

Habla Hermano provides an HTMX-driven API that returns HTML partials for seamless UI updates. The primary endpoint processes chat messages through a LangGraph agent and returns rendered HTML including the AI response, scaffolding assistance (for A0-A1 learners), and grammar feedback.

**Base URL**: `http://localhost:8000`

**Content Type**: All POST requests use `application/x-www-form-urlencoded` (form data), except `/api/speak` which accepts `application/json`. Voice endpoints (`/ws/transcribe`, `/ws/speak`) use WebSocket protocol with binary audio frames.

**Response Format**: HTML partials designed for HTMX integration. Voice endpoints return audio streams or JSON transcript data.

---

## Authentication

The API uses two cookie-based identity mechanisms:

- **`sb-access-token`**: User's Supabase JWT. Required for all data-persisting operations (progress, vocabulary, review). Used via `get_supabase_for_user()` to create a user-authenticated Supabase client that respects Row Level Security (RLS).
- **`session_id`**: Anonymous session cookie. Used only for LangGraph chat thread persistence (`thread_id`). Not used for any data operations.

**Endpoint authentication levels**:

| Category | Authentication | Guest behavior |
|----------|---------------|----------------|
| Chat (`/`, `/chat`, `/new`) | Optional (`OptionalUserDep`) | Full chat, grammar feedback, pronunciation tips. No vocabulary tracking or progress. |
| Progress (`/progress/*`) | Required for data (`OptionalUserDep`) | Returns empty/zero stats with `is_guest: True` |
| Review (`/review/*`) | Required (`CurrentUserDep`) | Returns 401 Unauthorized |
| Lessons (`/lessons/*`) | Optional | Full access to browse and play lessons |
| Lesson Chat (`/chat/lesson/*`) | Optional (`OptionalUserDep`) | Full lesson chat access. Score persistence requires authentication. |
| Voice (`/ws/transcribe`, `/ws/speak`) | Required (`sb-access-token` JWT cookie) | WebSocket rejected with close code `4001` |
| Voice (`/api/speak`) | Optional (`OptionalUserDep`) + CSRF header | Full access when voice configured |
| Auth (`/auth/*`) | None | Public endpoints |

### CSRF Protection

All state-changing requests (POST, PUT, DELETE, PATCH) must include a CSRF header. The server validates that the request originated from JavaScript running on the same origin, not from a cross-site form submission.

**Required header** (one of the following):

| Header | Value | When to use |
|--------|-------|-------------|
| `HX-Request` | `true` | HTMX sends this automatically on every request |
| `X-Requested-With` | `XMLHttpRequest` | JavaScript `fetch()` or `XMLHttpRequest` calls |

**Failure response**: `403 {"detail": "CSRF validation failed"}`

**Exempt paths**: `/health`, `/static/`, and safe HTTP methods (`GET`, `OPTIONS`).

Since the HTMX library automatically sends the `HX-Request: true` header, all HTMX-driven form submissions pass CSRF validation without changes. For custom JavaScript (such as `stream.js` or `voice.js`), include the `X-Requested-With` header in `fetch()` calls:

```javascript
fetch('/api/speak', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
  },
  body: JSON.stringify({ text: 'Hola amigo' })
});
```

---

### GET /auth/login

Render the login page for existing users.

**Response**: Full HTML page with login form.

**Example**:
```bash
curl http://localhost:8000/auth/login
```

---

### POST /auth/login

Authenticate user with email and password.

**Content-Type**: `application/x-www-form-urlencoded`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | string | Yes | User's email address |
| `password` | string | Yes | User's password |

**Response**:
- Success: Sets `sb-access-token` cookie (7-day expiry), redirects to `/`
- Error: Returns error message HTML partial

**Example**:
```bash
curl -X POST http://localhost:8000/auth/login \
  -d "email=user@example.com" \
  -d "password=secretpassword"
```

---

### GET /auth/signup

Render the signup page for new users.

**Response**: Full HTML page with signup form.

---

### POST /auth/signup

Create a new user account.

**Content-Type**: `application/x-www-form-urlencoded`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | string | Yes | User's email address |
| `password` | string | Yes | Password (minimum 8 characters) |

**Response**:
- Success: Creates user, sets JWT cookie, redirects to `/`
- Error: Returns error message HTML partial

---

### POST /auth/logout

Clear session and logout user.

**Response**: Clears `sb-access-token` cookie, redirects to `/auth/login`

---

## Chat Endpoints

### GET /

Render the main chat interface. Supports both authenticated and guest users.

**Response**: Full HTML page with chat UI, level/language selectors, and theme toggle.

**Authentication**: Optional (`OptionalUserDep`). Authenticated users see review stats and warmup prompts; guests see the chat interface without review features.

**Example**:
```bash
curl http://localhost:8000/
```

---

### POST /chat

Send a message and receive an AI response with optional scaffolding and grammar feedback as a complete HTML partial. This is the non-streaming fallback endpoint. The primary chat interface uses `POST /chat/stream` instead (see below). Supports both authenticated and guest users.

**Authentication**: Optional (`OptionalUserDep`). Thread ID is derived from user ID for authenticated users (`user:{user_id}`) or from `session_id` cookie for guests. Vocabulary tracking only occurs for authenticated users with a valid `sb-access-token`.

#### Request

**Content-Type**: `application/x-www-form-urlencoded`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `message` | string | Yes | - | User's message in the target language |
| `level` | string | No | `A1` | CEFR proficiency level: `A0`, `A1`, `A2`, `B1` |
| `language` | string | No | `es` | Target language code: `es` (Spanish), `de` (German), `fr` (French) |

**Example Request**:
```bash
curl -X POST http://localhost:8000/chat \
  -d "message=Hola, me llamo Ana" \
  -d "level=A0" \
  -d "language=es"
```

#### Response

Returns an HTML partial (`partials/message_pair.html`) containing:
- AI response bubble
- Scaffolding section (when `scaffolding.enabled` is `true`)
- Grammar feedback section (when corrections exist)

**Response Context Variables**:

| Variable | Type | Description |
|----------|------|-------------|
| `user_message` | string | Echo of the user's submitted message |
| `ai_response` | string | Generated AI response text |
| `scaffolding` | object | Scaffolding configuration (see below) |
| `grammar_feedback` | array | List of grammar corrections |
| `new_vocabulary` | array | List of vocabulary items introduced |

---

### POST /chat/stream

Stream a chat response as server-sent events. Identical request parameters to POST /chat. Added in Phase 15 (SSE Streaming). Tokens are streamed as they are generated by the `respond` node, followed by server-rendered feedback HTML partials.

**Authentication**: Optional (`OptionalUserDep`). Thread ID is derived from user ID for authenticated users (`user:{user_id}`) or from `session_id` cookie for guests. Sets `session_id` cookie for first-time anonymous users.

**Rate Limiting**: 20 calls per 60 seconds (same as POST /chat).

#### Request

**Content-Type**: `application/x-www-form-urlencoded`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `message` | string | Yes | - | User's message in the target language |
| `level` | string | No | `A1` | CEFR proficiency level: `A0`, `A1`, `A2`, `B1` |
| `language` | string | No | `es` | Target language code: `es` (Spanish), `de` (German), `fr` (French) |

**Example Request**:
```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -d "message=Hola, me llamo Ana" \
  -d "level=A0" \
  -d "language=es"
```

#### Response

**Content-Type**: `text/event-stream` (`EventSourceResponse`)

The response is a stream of server-sent events (SSE). Each event has an `event` field indicating the type and a `data` field containing a JSON payload.

#### SSE Event Protocol

| Event | Payload | Description |
|-------|---------|-------------|
| `token` | `{"content": "Hola"}` | AI response token from the `respond` node, streamed incrementally |
| `response_complete` | `{"content": "full response text"}` | Emitted after the LLM finishes generating, contains the full response |
| `scaffolding` | `{"html": "<div>...</div>"}` | Rendered scaffolding HTML (A0-A1 levels only) |
| `grammar` | `{"html": "<div>...</div>"}` | Grammar feedback rendered as HTML |
| `pronunciation` | `{"html": "<div>...</div>"}` | Pronunciation tips rendered as HTML |
| `error` | `{"message": "..."}` | Validation or runtime error |
| `done` | `{}` | Stream complete, no more events will follow |

**Note**: Validation errors are returned as `error` + `done` SSE events rather than HTTP error status codes. The HTTP response will always be 200 with `text/event-stream` content type.

**Client**: The frontend uses `stream.js` (fetch + ReadableStream) to intercept the chat form, POST to this endpoint, and parse SSE events. Tokens are appended to a streaming bubble in real time. HTMX is **not** used for chat form submission.

**Example SSE Stream**:
```
event: token
data: {"content": "¡"}

event: token
data: {"content": "Hola"}

event: token
data: {"content": "!"}

event: response_complete
data: {"content": "¡Hola! Great job saying hello! Now, can you tell me your name?"}

event: scaffolding
data: {"html": "<div class=\"scaffold-section\">...</div>"}

event: grammar
data: {"html": "<div class=\"grammar-feedback\">...</div>"}

event: pronunciation
data: {"html": "<div class=\"pronunciation-tips\">...</div>"}

event: done
data: {}
```

**Example Error Stream**:
```
event: error
data: {"message": "Message is required"}

event: done
data: {}
```

#### JavaScript Integration

```javascript
const form = document.getElementById('chat-form');
const formData = new FormData(form);
const params = new URLSearchParams(formData);

// EventSource only supports GET; for POST use fetch with ReadableStream:
const response = await fetch('/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: params
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const chunk = decoder.decode(value);
  // Parse SSE events from chunk
}
```

---

## Data Structures

### ScaffoldingConfig

Scaffolding provides learning assistance for A0-A1 level learners. When enabled, the response includes a collapsible help section with contextual hints, a word bank, and optional sentence starters.

**Activation**: Automatically enabled for `A0` and `A1` levels via LangGraph conditional routing.

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | Whether scaffolding is active for this response. `true` for A0-A1 levels, `false` otherwise. |
| `word_bank` | array[string] | Relevant vocabulary for forming a response. Format varies by level (see below). |
| `hint_text` | string | English guidance explaining how to respond to the AI's message. |
| `sentence_starter` | string or null | Optional partial sentence to help the learner begin their response. |
| `auto_expand` | boolean | If `true`, scaffolding section displays expanded by default. If `false`, collapsed. |

**Word Bank Format by Level**:

| Level | Format | Example |
|-------|--------|---------|
| A0 | Word with English translation in parentheses | `["hola (hello)", "me llamo (my name is)", "buenos dias (good morning)"]` |
| A1 | Word only (assumes basic vocabulary recognition) | `["hola", "me llamo", "buenos dias"]` |

**Auto-Expand Behavior**:

| Level | `auto_expand` Value | UI Behavior |
|-------|---------------------|-------------|
| A0 | `true` | Scaffolding section is expanded by default to maximize visibility |
| A1 | `false` | Scaffolding section is collapsed by default (click to expand) |

**Example ScaffoldingConfig (A0 level)**:
```json
{
  "enabled": true,
  "word_bank": ["hola (hello)", "me llamo (my name is)", "mucho gusto (nice to meet you)"],
  "hint_text": "Try introducing yourself! Say hello and tell them your name.",
  "sentence_starter": "Hola, me llamo",
  "auto_expand": true
}
```

**Example ScaffoldingConfig (A1 level)**:
```json
{
  "enabled": true,
  "word_bank": ["estoy", "bien", "cansado", "trabajo"],
  "hint_text": "Tell them how you're feeling and why.",
  "sentence_starter": null,
  "auto_expand": false
}
```

**Example ScaffoldingConfig (A2/B1 level - disabled)**:
```json
{
  "enabled": false,
  "word_bank": [],
  "hint_text": "",
  "sentence_starter": null,
  "auto_expand": false
}
```

---

### GrammarFeedback

Grammar corrections are generated by the `analyze` node for the user's last message. Corrections are filtered by level appropriateness.

| Field | Type | Description |
|-------|------|-------------|
| `original` | string | The incorrect phrase from the user's message |
| `correction` | string | The corrected version of the phrase |
| `explanation` | string | Brief, friendly explanation of the error |
| `severity` | string | Error significance: `minor`, `moderate`, or `significant` |

**Severity Levels**:

| Severity | Description | Example |
|----------|-------------|---------|
| `minor` | Small issues that don't impede understanding | Missing accent marks |
| `moderate` | Noticeable errors that may cause confusion | Gender agreement issues |
| `significant` | Errors that change meaning or are grammatically incorrect | Ser vs estar confusion |

**Example GrammarFeedback**:
```json
{
  "original": "Yo soy cansado",
  "correction": "Yo estoy cansado",
  "explanation": "For temporary states like being tired, use 'estar' instead of 'ser'.",
  "severity": "significant"
}
```

---

### VocabWord

Vocabulary items extracted from the conversation to highlight for learning.

| Field | Type | Description |
|-------|------|-------------|
| `word` | string | The word in the target language |
| `translation` | string | English translation |
| `part_of_speech` | string | Grammatical category: `noun`, `verb`, `adjective`, `adverb`, etc. |

**Example VocabWord**:
```json
{
  "word": "cansado",
  "translation": "tired",
  "part_of_speech": "adjective"
}
```

---

## Level-Specific Behavior

The `/chat` endpoint adapts its response based on the learner's CEFR level:

| Level | Scaffolding | AI Language Mix | Grammar Feedback |
|-------|-------------|-----------------|------------------|
| **A0** | Enabled (auto-expanded), translations in word bank | 80% English, 20% Spanish | Basic errors only |
| **A1** | Enabled (collapsed), words only in word bank | 50% English, 50% Spanish | Common errors |
| **A2** | Disabled | 80% Spanish, 20% English | Intermediate errors |
| **B1** | Disabled | 95%+ Spanish | All appropriate errors |

---

## HTML Template Integration

### Response Template Structure

When scaffolding is enabled, the `partials/message_pair.html` template includes the `partials/scaffold.html` partial:

```html
<!-- AI Response -->
<div class="message-enter flex justify-start mb-6">
    <div class="bg-ai rounded-2xl rounded-bl-sm px-4 py-3 max-w-[80%] shadow-sm">
        <div class="text-ai-text leading-relaxed">
            {{ ai_response | safe }}
        </div>
    </div>
</div>

<!-- Scaffolding Help (collapsible) - for A0-A1 learners -->
{% if scaffolding and scaffolding.enabled %}
{% include "partials/scaffold.html" %}
{% endif %}

<!-- Grammar Feedback (collapsible) -->
{% if grammar_feedback %}
{% include "partials/grammar_feedback.html" %}
{% endif %}
```

### Scaffold Partial Features

The scaffold partial (`partials/scaffold.html`) renders:

1. **Toggle Button**: "Need help responding?" with expand/collapse functionality
2. **Hint Section**: Contextual guidance in English
3. **Word Bank**: Clickable vocabulary chips that insert text into the input field
4. **Sentence Starter**: Optional clickable prompt to pre-fill the input

**JavaScript Integration**: Word bank chips trigger `insertWord(word)` and sentence starters trigger `insertStarter(text)` to populate the chat input field.

---

## Chat Form Integration (stream.js)

The chat form uses `stream.js` (fetch + ReadableStream) instead of HTMX for form submission. The script intercepts the form submit event, sends a `POST /chat/stream` request, and parses SSE events to render tokens in real time. Other pages (lessons, progress, review, learn) continue to use HTMX for partial updates.

```html
<!-- Chat form — submitted via stream.js, NOT HTMX -->
<form id="chat-form">
    <input type="hidden" name="level" value="A0">
    <input type="hidden" name="language" value="es">
    <input type="text" name="message" id="message-input" placeholder="Type your message...">
    <button type="submit">Send</button>
</form>
```

---

## Error Handling

### Common Error Responses

| Status | Cause | Response |
|--------|-------|----------|
| 400 | Missing required `message` parameter | Validation error |
| 403 | Missing CSRF header on state-changing request | `{"detail": "CSRF validation failed"}` |
| 422 | Invalid form data | Unprocessable Entity |
| 500 | LangGraph or LLM error | Internal Server Error |

### Validation

The `level` parameter is validated to accept only: `A0`, `A1`, `A2`, `B1`.

The `language` parameter is validated to accept only: `es`, `de`, `fr`.

---

## Example Workflow

### A0 Beginner Conversation

**Request**:
```bash
curl -X POST http://localhost:8000/chat \
  -d "message=hola" \
  -d "level=A0" \
  -d "language=es"
```

**Response includes**:
- AI response: "Great job! You said 'hola' - that means 'hello'! Now let's learn your name..."
- Scaffolding (expanded by default):
  - Hint: "Try saying your name! Use 'Me llamo' followed by your name."
  - Word bank: `["me llamo (my name is)", "mucho gusto (nice to meet you)"]`
  - Sentence starter: "Me llamo"

### A1 Beginner Conversation

**Request**:
```bash
curl -X POST http://localhost:8000/chat \
  -d "message=Estoy cansado" \
  -d "level=A1" \
  -d "language=es"
```

**Response includes**:
- AI response: "Ah, estas cansado? Yo tambien estoy cansado..."
- Scaffolding (collapsed by default):
  - Hint: "Tell them why you're tired."
  - Word bank: `["trabajo", "mucho", "hoy", "ayer"]`
  - Sentence starter: null

### A2/B1 Conversation

**Request**:
```bash
curl -X POST http://localhost:8000/chat \
  -d "message=Ayer fui al cine con mis amigos" \
  -d "level=A2" \
  -d "language=es"
```

**Response includes**:
- AI response: "Que pelicula vieron? Me encanta ir al cine..."
- Scaffolding: `{ "enabled": false, ... }`
- Grammar feedback (if applicable)

---

## Voice Endpoints (Phase 17)

Phase 17 introduces voice conversation capabilities powered by Deepgram. The server acts as a proxy between the browser and Deepgram's real-time APIs, handling authentication, rate limiting, and audio format negotiation. Voice features are optional and require `DEEPGRAM_API_KEY` to be configured. When not configured, the voice UI is hidden and endpoints return appropriate errors.

**Deepgram Models**:
- **STT**: Nova-3 (real-time speech recognition with smart formatting and punctuation)
- **TTS**: Aura-2 (low-latency text-to-speech with natural voices)

**Authentication**: WebSocket endpoints (`/ws/transcribe`, `/ws/speak`) require a valid `sb-access-token` JWT cookie or a `session_id` guest cookie. If neither is present or valid, the WebSocket connection is rejected before acceptance with close code `4001` (authentication required). The REST endpoint (`/api/speak`) uses `OptionalUserDep` and requires a CSRF header for the POST request.

**Privacy**: All Deepgram API calls (STT and TTS) are sent with `mip_opt_out=true`, which prevents user audio and text data from being used in Deepgram's Model Improvement Program.

**Rate Limiting**: Voice endpoints are rate-limited to prevent API budget abuse:

| Endpoint | Type | Limit | Scope |
|----------|------|-------|-------|
| `POST /api/speak` | REST | 10 calls per 60 seconds | Function-level (all callers share the limit) |
| `GET /ws/speak` | WebSocket | 30 text messages per 60 seconds | Per-connection (each WebSocket gets its own counter) |
| `GET /ws/transcribe` | WebSocket | Not rate-limited per-message | Per-connection (AudioWorklet fires at ~375 frames/sec; the authenticated connection itself is the throttle) |

When the REST rate limit is exceeded, the server returns HTTP `429 Too Many Requests`. When the WebSocket TTS message rate limit is exceeded, the server sends a JSON error frame instead of closing the connection:

```json
{"error": "Rate limit exceeded", "code": "RATE_LIMITED"}
```

### Available Voices

Voice IDs follow Deepgram's Aura-2 naming convention: `aura-2-{name}-{lang}`.

| Language | Voice ID | Default |
|----------|----------|---------|
| Spanish (`es`) | `aura-2-celeste-es` | |
| Spanish (`es`) | `aura-2-estrella-es` | |
| Spanish (`es`) | `aura-2-nestor-es` | Yes |
| German (`de`) | `aura-2-elara-de` | |
| German (`de`) | `aura-2-julius-de` | Yes |
| French (`fr`) | `aura-2-agathe-fr` | |
| French (`fr`) | `aura-2-hector-fr` | Yes |

Default voices are masculine to match the Hermano ("big brother") tutor persona.

### STT Language Options

| Code | Description |
|------|-------------|
| `es` | Spanish |
| `de` | German |
| `fr` | French |
| `multi` | Code-switching mode (default) -- allows mixing target language with English |

---

### WebSocket /ws/transcribe

Real-time speech-to-text proxy using Deepgram Nova-3. The browser captures microphone audio via an AudioWorklet, sends raw PCM frames over a WebSocket, and the server relays them to Deepgram's streaming STT API. Transcript results are forwarded back to the browser as JSON messages.

**Protocol**: WebSocket

**Authentication**: Required. The `sb-access-token` JWT cookie or `session_id` guest cookie must be present. Connection is rejected with close code `4001` if authentication fails. Authentication is validated **before** the WebSocket handshake is accepted.

| Query Parameter | Type | Default | Description |
|----------------|------|---------|-------------|
| `language` | string | `multi` | STT language code: `es`, `de`, `fr`, or `multi` (code-switching) |

#### Connection Lifecycle

```
Browser                        Server                       Deepgram
  |                              |                              |
  |--- WebSocket upgrade ------->|                              |
  |                              |-- validate JWT/session ----  |
  |                              |   (reject 4001 if invalid)   |
  |                              |                              |
  |<-- WebSocket accepted -------|                              |
  |                              |--- open STT WebSocket ------>|
  |                              |   (Nova-3, language, PCM)    |
  |                              |                              |
  |--- binary audio chunk ------>|--- forward audio ----------->|
  |--- binary audio chunk ------>|--- forward audio ----------->|
  |                              |                              |
  |                              |<-- transcript result --------|
  |<-- JSON transcript ---------|                              |
  |                              |                              |
  |--- disconnect -------------->|--- send finalize ----------->|
  |                              |--- close Deepgram WS ------->|
```

#### Client to Server

Binary audio frames: linear16 PCM, 16kHz sample rate, mono channel. The browser's AudioWorklet (`pcm-processor.js`) captures microphone input at the native sample rate and resamples to 16kHz before sending.

#### Server to Client

JSON transcript messages with three fields:

```json
{
  "transcript": "Hola, me llamo Ana",
  "is_final": true,
  "speech_final": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `transcript` | string | Recognized text from the audio |
| `is_final` | boolean | `true` if Deepgram considers this a final (non-interim) result |
| `speech_final` | boolean | `true` if Deepgram detected end of utterance (endpointing) |

Interim results (`is_final: false`) are sent as the user speaks, allowing the UI to display live transcription. Final results replace the interim text. The `speech_final` flag indicates a natural pause where the user has stopped speaking (configured at 300ms endpointing with 1000ms utterance end).

#### Deepgram STT Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| `model` | `nova-3` | Latest Deepgram speech recognition model |
| `smart_format` | `true` | Automatic formatting (capitalization, numerals) |
| `punctuate` | `true` | Add punctuation to transcripts |
| `interim_results` | `true` | Send partial results during speech |
| `endpointing` | `300` | Silence duration (ms) to trigger end of speech |
| `utterance_end_ms` | `1000` | Maximum silence before utterance is finalized |
| `vad_events` | `true` | Voice activity detection events |
| `encoding` | `linear16` | Raw PCM audio encoding |
| `sample_rate` | `16000` | 16kHz sample rate |

#### Close Codes

| Code | Reason | Description |
|------|--------|-------------|
| `1000` | Normal closure | Client disconnected normally |
| `1008` | Policy violation | Invalid `language` parameter or authentication failure |
| `1011` | Internal error | Voice features not configured (`DEEPGRAM_API_KEY` missing) or server error |
| `4001` | Authentication required | Missing or invalid JWT/session cookie |

#### JavaScript Integration

```javascript
// Open STT WebSocket with language parameter
const ws = new WebSocket(`ws://localhost:8000/ws/transcribe?language=es`);
// Note: cookies (sb-access-token, session_id) are sent automatically

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.speech_final) {
    // User finished speaking -- use data.transcript as final text
    console.log('Final:', data.transcript);
  } else if (data.is_final) {
    // Intermediate final result
    console.log('Partial final:', data.transcript);
  } else {
    // Interim result -- update live transcription display
    console.log('Interim:', data.transcript);
  }
};

// Send audio from AudioWorklet
audioWorkletNode.port.onmessage = (event) => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(event.data);  // ArrayBuffer of linear16 PCM
  }
};

// Clean up
ws.close();
```

---

### POST /api/speak

Synthesize speech from text using Deepgram Aura-2 TTS via REST. This endpoint proxies the request to Deepgram's REST TTS API and streams back the audio response as `audio/mpeg`. Use this endpoint for one-shot TTS requests (e.g., clicking a speaker icon on a message). For low-latency conversational TTS, use the WebSocket `/ws/speak` endpoint instead.

**Authentication**: Optional (`OptionalUserDep`).

**CSRF**: Required. Include `HX-Request: true` or `X-Requested-With: XMLHttpRequest` header (see [CSRF Protection](#csrf-protection)).

**Rate Limiting**: 10 calls per 60 seconds. Exceeding the limit returns HTTP `429 Too Many Requests` with body `{"detail": "Rate limit exceeded. Please try again later."}`.

**Content-Type**: `application/json`

#### Request Body

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | Yes | - | Text to synthesize (1-2000 characters) |
| `voice` | string | No | `aura-2-nestor-es` | Deepgram Aura-2 voice model ID (see [Available Voices](#available-voices)) |

#### Response

**Success** (`200`): `audio/mpeg` streaming response with the following headers:
- `Content-Type: audio/mpeg`
- `Cache-Control: no-cache`
- `Content-Disposition: inline`

The audio is streamed in 1024-byte chunks as they arrive from Deepgram, allowing playback to begin before the full response is generated.

#### Error Responses

| Status | Cause | Response Body |
|--------|-------|---------------|
| `400` | Invalid voice ID (not in allowed voices list) | `{"detail": "Invalid voice: <voice_id>"}` |
| `403` | Missing CSRF header | `{"detail": "CSRF validation failed"}` |
| `429` | Rate limit exceeded | `{"detail": "Rate limit exceeded. Please try again later."}` |
| `503` | `DEEPGRAM_API_KEY` not configured | `{"detail": "Voice features not configured"}` |

#### Example

```bash
curl -X POST http://localhost:8000/api/speak \
  -H "Content-Type: application/json" \
  -H "X-Requested-With: XMLHttpRequest" \
  -d '{"text": "Hola, me llamo Ana", "voice": "aura-2-celeste-es"}' \
  --output speech.mp3
```

#### JavaScript Integration

```javascript
const response = await fetch('/api/speak', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
  },
  body: JSON.stringify({
    text: 'Hola, me llamo Ana',
    voice: 'aura-2-nestor-es'
  })
});

if (response.ok) {
  const blob = await response.blob();
  const audio = new Audio(URL.createObjectURL(blob));
  audio.play();
}
```

---

### WebSocket /ws/speak

Stream TTS audio via WebSocket for low-latency playback. The browser sends JSON text messages and the server proxies them to Deepgram's WebSocket TTS API, forwarding binary audio chunks back as they are generated. This achieves lower latency than the REST `/api/speak` endpoint because audio begins streaming before the full synthesis is complete.

**Protocol**: WebSocket

**Authentication**: Required. The `sb-access-token` JWT cookie or `session_id` guest cookie must be present. Connection is rejected with close code `4001` if authentication fails. Authentication is validated **before** the WebSocket handshake is accepted.

**Rate Limiting**: 30 text messages per 60 seconds per connection (sliding window). When exceeded, the server sends a JSON error frame and drops the message without forwarding it to Deepgram. The connection remains open.

| Query Parameter | Type | Default | Description |
|----------------|------|---------|-------------|
| `voice` | string | `aura-2-nestor-es` | Deepgram Aura-2 voice model ID (see [Available Voices](#available-voices)) |

#### Connection Lifecycle

```
Browser                        Server                       Deepgram
  |                              |                              |
  |--- WebSocket upgrade ------->|                              |
  |   ?voice=aura-2-nestor-es   |                              |
  |                              |-- validate JWT/session ----  |
  |                              |   (reject 4001 if invalid)   |
  |                              |-- validate voice parameter   |
  |                              |   (reject 1008 if invalid)   |
  |                              |                              |
  |<-- WebSocket accepted -------|                              |
  |                              |--- open TTS WebSocket ------>|
  |                              |   (Aura-2, linear16, 24kHz)  |
  |                              |                              |
  |--- {"text": "Hola"} ------->|--- Speak + Flush ----------->|
  |                              |                              |
  |                              |<-- binary audio chunks ------|
  |<-- binary audio chunks ------|                              |
  |                              |<-- {"type": "Flushed"} ------|
  |<-- {"type": "Flushed"} -----|                              |
  |                              |                              |
  |--- {"type": "close"} ------>|--- Close ------------------->|
  |                              |--- close Deepgram WS ------->|
```

#### Client to Server

JSON text messages with the following fields:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | Yes | - | Text to synthesize (1-2000 characters; empty or oversized messages are silently dropped) |
| `type` | string | No | - | Set to `"close"` to gracefully end the TTS session |

**Example messages**:
```json
{"text": "Hola amigo, como estas?"}
{"type": "close"}
```

Each text message triggers a Deepgram `Speak` command followed by a `Flush` command, which causes Deepgram to immediately begin synthesizing and streaming audio for that text segment.

#### Server to Client

The server forwards two types of messages from Deepgram:

**Binary frames**: Raw audio data (linear16 PCM, 24kHz sample rate, mono channel). The browser uses an AudioWorklet (`pcm-processor.js`) or an `AudioContext` to decode and play these chunks in real time.

**Text frames**: JSON metadata messages from Deepgram:
```json
{"type": "Flushed"}
```

The `Flushed` message indicates that all audio for the preceding text has been generated and sent. The client can use this signal to know when playback of a particular utterance is complete.

#### Close Codes

| Code | Reason | Description |
|------|--------|-------------|
| `1008` | Policy violation | Invalid `voice` parameter or authentication failure |
| `1011` | Internal error | Voice features not configured (`DEEPGRAM_API_KEY` missing) or server error |
| `4001` | Authentication required | Missing or invalid JWT/session cookie |

#### JavaScript Integration

```javascript
// Open TTS WebSocket with voice parameter
const ws = new WebSocket(`ws://localhost:8000/ws/speak?voice=aura-2-nestor-es`);
// Note: cookies are sent automatically by the browser

ws.binaryType = 'arraybuffer';

ws.onmessage = (event) => {
  if (event.data instanceof ArrayBuffer) {
    // Binary audio chunk -- queue for playback
    playAudioChunk(event.data);  // linear16 PCM, 24kHz, mono
  } else {
    const msg = JSON.parse(event.data);
    if (msg.type === 'Flushed') {
      // All audio for the last text has been sent
      console.log('Audio generation complete');
    }
    if (msg.error) {
      // Rate limit or other error
      console.warn(msg.error, msg.code);
    }
  }
};

// Send text for synthesis
ws.send(JSON.stringify({ text: 'Hola, como estas?' }));

// Gracefully close
ws.send(JSON.stringify({ type: 'close' }));
```

---

## Lesson Endpoints

The lesson system provides structured learning experiences with guided steps, exercises, and progress tracking. Lessons support guest access (no authentication required) and are designed for HTMX-driven partial page updates.

### GET /lessons/

List available lessons with optional filtering by language and level.

**Authentication**: Optional. Guest users can browse and play lessons.

**Query Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `language` | string | No | - | Filter by target language code: `es`, `de`, `fr` |
| `level` | string | No | - | Filter by CEFR level: `A0`, `A1`, `A2`, `B1` |

**Response**: Full HTML page with lesson cards grid.

**Example**:
```bash
# List all lessons
curl http://localhost:8000/lessons/

# Filter by Spanish A1 lessons
curl "http://localhost:8000/lessons/?language=es&level=A1"
```

---

### GET /lessons/{lesson_id}/play

Render the lesson player page for a specific lesson.

**Authentication**: Optional. Guest users can play lessons.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |

**Response**: Full HTML page with lesson player interface including:
- Lesson title and description
- Progress indicator
- Step content area
- Navigation controls

**Example**:
```bash
curl http://localhost:8000/lessons/spanish-greetings-a0/play
```

---

### GET /lessons/{lesson_id}/step/{step_index}

Get a specific lesson step content as an HTML partial.

**Authentication**: Optional.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |
| `step_index` | integer | Zero-based step index |

**Response**: HTML partial (`partials/lesson_step.html`) containing:
- Step instruction text
- Example content (if applicable)
- Exercise component (if step includes exercise)
- Navigation buttons

**HTMX Integration**:
```html
<div hx-get="/lessons/spanish-greetings-a0/step/0"
     hx-trigger="load"
     hx-target="#step-content">
</div>
```

**Example**:
```bash
curl http://localhost:8000/lessons/spanish-greetings-a0/step/0
```

---

### POST /lessons/{lesson_id}/step/next

Navigate to the next step in the lesson.

**Authentication**: Optional.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |

**Request Body** (form data):

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `current_step` | integer | Yes | Current step index |

**Response**: HTML partial for the next step, or completion partial if at end.

**Response Headers**:
- `HX-Trigger`: `stepChanged` event for progress bar updates

**Example**:
```bash
curl -X POST http://localhost:8000/lessons/spanish-greetings-a0/step/next \
  -d "current_step=0"
```

---

### POST /lessons/{lesson_id}/step/prev

Navigate to the previous step in the lesson.

**Authentication**: Optional.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |

**Request Body** (form data):

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `current_step` | integer | Yes | Current step index |

**Response**: HTML partial for the previous step.

**Response Headers**:
- `HX-Trigger`: `stepChanged` event for progress bar updates

**Example**:
```bash
curl -X POST http://localhost:8000/lessons/spanish-greetings-a0/step/prev \
  -d "current_step=2"
```

---

### GET /lessons/{lesson_id}/exercise/{exercise_id}

Get a specific exercise component as an HTML partial.

**Authentication**: Optional.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |
| `exercise_id` | string | Unique exercise identifier within the lesson |

**Response**: HTML partial (`partials/exercise.html`) containing the exercise UI based on type:
- Multiple choice options
- Fill-in-the-blank input
- Matching pairs interface
- Audio response recorder

**Example**:
```bash
curl http://localhost:8000/lessons/spanish-greetings-a0/exercise/greeting-choice-1
```

---

### POST /lessons/{lesson_id}/exercise/{exercise_id}/submit

Submit an answer for an exercise.

**Authentication**: Optional.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |
| `exercise_id` | string | Unique exercise identifier |

**Request Body** (form data):

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `answer` | string | Yes | User's submitted answer |

**Response**: HTML partial (`partials/exercise_result.html`) containing:
- Correct/incorrect indicator
- Feedback message
- Correct answer (if incorrect)
- Continue button

**Example**:
```bash
curl -X POST http://localhost:8000/lessons/spanish-greetings-a0/exercise/greeting-choice-1/submit \
  -d "answer=hola"
```

**Response Example (correct)**:
```html
<div class="exercise-result correct">
  <span class="icon">✓</span>
  <p class="feedback">Excellent! "Hola" is the standard greeting.</p>
  <button hx-post="/lessons/spanish-greetings-a0/step/next">Continue</button>
</div>
```

**Response Example (incorrect)**:
```html
<div class="exercise-result incorrect">
  <span class="icon">✗</span>
  <p class="feedback">Not quite. The correct answer is "hola".</p>
  <button hx-get="/lessons/spanish-greetings-a0/exercise/greeting-choice-1">Try Again</button>
</div>
```

---

### POST /lessons/{lesson_id}/complete

Mark a lesson as complete. For authenticated users, this records progress in the database.

**Authentication**: Optional. Progress is only persisted for authenticated users.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |

**Response**: HTML partial (`partials/lesson_complete.html`) containing:
- Completion celebration
- Summary statistics (exercises completed, accuracy)
- Recommended next lessons
- Handoff to chat option

**Response Headers**:
- `HX-Trigger`: `lessonComplete` event for UI updates

**Example**:
```bash
curl -X POST http://localhost:8000/lessons/spanish-greetings-a0/complete
```

---

### POST /lessons/{lesson_id}/handoff

Transition from lesson to free chat practice with lesson context.

**Authentication**: Required. The chat requires authentication for conversation persistence.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |

**Response**: Redirects to chat with lesson context pre-loaded.

**Response Headers**:
- `HX-Redirect`: `/` with lesson context query parameters

**Behavior**:
1. Validates user authentication
2. Prepares chat context with lesson vocabulary and topics
3. Sets initial chat prompt based on lesson theme
4. Redirects to main chat interface

**Example**:
```bash
curl -X POST http://localhost:8000/lessons/spanish-greetings-a0/handoff \
  --cookie "sb-access-token=<jwt_token>"
```

**Unauthenticated Response**:
```html
<!-- Returns login prompt partial -->
<div class="auth-prompt">
  <p>Sign in to continue practicing in chat mode.</p>
  <a href="/auth/login" class="btn-primary">Sign In</a>
</div>
```

---

## AI-Enhanced Lesson Endpoints (Phase 9)

Phase 9 introduces AI-enhanced lesson delivery through LangGraph subgraphs. These endpoints provide personalized content from Hermano for each lesson step.

### GET /lessons/{lesson_id}/step/{step_index}/enhanced

Get an AI-enhanced lesson step with Hermano's personalized intro and additional content.

**Authentication**: Optional.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |
| `step_index` | integer | Zero-based step index |

**Query Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `language` | string | No | `es` | Target language code: `es`, `de`, `fr` |
| `level` | string | No | `A0` | CEFR level: `A0`, `A1`, `A2`, `B1` |

**Response**: HTML partial (`partials/lesson_step_enhanced.html`) containing:
- Original step content
- Hermano's personalized intro
- Enhanced explanations and examples
- Cultural tips and memory aids

**Example**:
```bash
curl "http://localhost:8000/lessons/numbers-001/step/1/enhanced?language=es&level=A0"
```

**Response Example**:
```html
<div class="enhanced-step">
  <div class="hermano-intro">
    <p>¡Hola! Let me share a memory trick for numbers - Spanish numbers
    actually sound like their meanings when you say them fast!</p>
  </div>
  <div class="step-content">
    <!-- Original step content -->
  </div>
  <div class="enhanced-content">
    <!-- Additional examples, tips, and cultural context -->
  </div>
</div>
```

---

### POST /lessons/{lesson_id}/exercise/{exercise_id}/submit/enhanced

Submit an exercise answer and receive AI-generated personalized feedback from Hermano.

**Authentication**: Optional.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |
| `exercise_id` | string | Unique exercise identifier |

**Request Body** (form data):

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `answer` | string | Yes | User's submitted answer |
| `language` | string | No | Target language (default: `es`) |
| `level` | string | No | CEFR level (default: `A0`) |

**Response**: HTML partial (`partials/exercise_result_enhanced.html`) containing:
- Correct/incorrect indicator
- Hermano's personalized feedback
- Encouragement or helpful hints
- Cultural context when relevant

**Example**:
```bash
curl -X POST "http://localhost:8000/lessons/numbers-001/exercise/ex-mc-num-001/submit/enhanced" \
  -d "answer=0" \
  -d "language=es" \
  -d "level=A0"
```

**Response Example (correct answer)**:
```html
<div class="exercise-result correct">
  <span class="icon">✓</span>
  <p class="hermano-feedback">
    ¡Excelente! You nailed it! "Uno" is indeed number one.
    Fun fact: in Spanish, we often use "uno" to mean "someone" too,
    like "uno nunca sabe" (one never knows). Keep up the great work!
  </p>
  <button hx-post="/lessons/numbers-001/step/next">Continue</button>
</div>
```

**Response Example (incorrect answer)**:
```html
<div class="exercise-result incorrect">
  <span class="icon">✗</span>
  <p class="hermano-feedback">
    Almost! The correct answer was "uno". Don't worry - this is a common
    mix-up at first. Think of it this way: "uno" sounds like "ooh-no" -
    as in "ooh no, there's only ONE left!" Try the next one!
  </p>
  <button hx-get="/lessons/numbers-001/exercise/ex-mc-num-001">Try Again</button>
</div>
```

---

## AI Enhancement Data Structures

### EnhancedStepContent

Content returned by the AI-enhanced step endpoint.

| Field | Type | Description |
|-------|------|-------------|
| `hermano_intro` | string | Hermano's personalized introduction to the step |
| `enhanced_content` | string | Full enhanced content with additional examples |
| `step_type` | string | Original step type: `instruction`, `vocabulary`, `example`, `tip`, `practice` |
| `step_content` | string | Original step content |
| `vocabulary` | array[VocabWord] | Vocabulary items with translations |

**Example EnhancedStepContent**:
```json
{
  "hermano_intro": "¡Hola! Numbers are super useful - you'll use these every day for prices, phone numbers, and addresses!",
  "enhanced_content": "INTRO: Let me show you the first ten numbers...\nEXTRA: Notice how uno, dos, tres have a nice rhythm...",
  "step_type": "vocabulary",
  "step_content": "Learn numbers 1-10 in Spanish",
  "vocabulary": [
    {"word": "uno", "translation": "one"},
    {"word": "dos", "translation": "two"}
  ]
}
```

### ExerciseFeedback

AI-generated feedback for exercise submissions.

| Field | Type | Description |
|-------|------|-------------|
| `is_correct` | boolean | Whether the answer was correct |
| `exercise_feedback` | string | Hermano's personalized feedback message |
| `correct_answer` | string | The correct answer (shown when incorrect) |

**Example ExerciseFeedback**:
```json
{
  "is_correct": false,
  "exercise_feedback": "Not quite! The answer is 'tres' for three. Remember: 'tres' sounds like 'trace' - imagine tracing three lines!",
  "correct_answer": "tres"
}
```

---

## Lesson Chat

Conversational lesson delivery where Hermano teaches YAML lesson content through the chat UI. Uses the same SSE streaming infrastructure as freeform chat.

### GET /chat/lesson/{lesson_id}

Render the lesson chat page for a specific lesson.

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `lesson_id` | string | Yes | Lesson identifier (e.g., `es_a1_greetings_01`) |

**Response**: Full HTML page with lesson chat interface. The page includes lesson metadata (title, description, level, language) and auto-starts the lesson conversation. Language and level selectors are hidden via `visibility: hidden` (not `display: none`) to preserve the header flex layout.

**Cookies Set**: `session_id` cookie for guests (7-day expiry) if not already present.

**Errors**:
- `404`: Lesson not found

**Example**:
```bash
curl http://localhost:8000/chat/lesson/es_a1_greetings_01
```

---

### POST /chat/lesson/stream

Stream a lesson chat response as Server-Sent Events.

**Content-Type**: `application/x-www-form-urlencoded`

**CSRF**: Required (`HX-Request: true` or `X-Requested-With: XMLHttpRequest`)

**Rate Limit**: Same as chat endpoint (20 calls/60s)

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `message` | string | Yes | — | User's message (max 2000 chars) |
| `lesson_id` | string | Yes | — | Lesson identifier |

> **Note**: `level` and `language` parameters were removed. These are now derived server-side from lesson metadata, ensuring correct difficulty and language regardless of client input.

**Checkpoint-aware invocation**: The endpoint checks for an existing LangGraph checkpoint before sending inputs. On the first invocation (no checkpoint), the full initialization state is sent (lesson data, lesson phase, step index, etc.). On subsequent turns, only the new user message is sent, preventing the checkpoint state from being overwritten.

**Response**: `text/event-stream` with the following event types:

| Event | Data | When |
|-------|------|------|
| `token` | `{"content": "..."}` | Each token of the AI response |
| `message_complete` | `{"html": "..."}` | Full rendered HTML of the response |
| `lesson_progress` | `{"step": N, "total_steps": N, "progress": N, "phase": "...", "title": "..."}` | After every turn. `progress` is a 0-100 integer computed server-side from `(completed_teaching_steps + completed_exercises) / total_items * 100`. `step` and `total_steps` remain for backwards compatibility. |
| `exercise_result` | `{"is_correct": bool, "exercise_id": "..."}` | After exercise evaluation |
| `lesson_complete` | `{"score": N, "vocab_count": N, "lesson_id": "..."}` | When lesson finishes |
| `error` | `{"message": "..."}` | Validation errors |
| `done` | `{}` | Stream end |

**Lesson Phase Machine**:

The lesson progresses through phases automatically:

```
intro → teaching → exercise_ask → exercise_eval → complete
```

- **intro**: Hermano welcomes the learner and previews the lesson
- **teaching**: Lesson steps delivered in batches of 3 per turn
- **exercise_ask**: Hermano presents the current exercise
- **exercise_eval**: Evaluates the user's answer and provides feedback
- **complete**: Calculates score, emits completion event, persists results

**Thread Isolation**: Each lesson gets its own conversation thread: `lesson:{user_or_session_id}:{lesson_id}`

**Example**:
```bash
curl -X POST http://localhost:8000/chat/lesson/stream \
  -H "X-Requested-With: XMLHttpRequest" \
  -d "message=Start the lesson" \
  -d "lesson_id=es_a1_greetings_01"
```

---

## Lesson Data Structures

### LessonMetadata

Metadata describing a lesson for listing and filtering.

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique lesson identifier (URL-safe slug) |
| `title` | string | Display title of the lesson |
| `description` | string | Brief description of lesson content |
| `language` | string | Target language code: `es`, `de`, `fr` |
| `level` | string | CEFR proficiency level: `A0`, `A1`, `A2`, `B1` |
| `duration_minutes` | integer | Estimated completion time in minutes |
| `step_count` | integer | Total number of steps in the lesson |
| `topics` | array[string] | Learning topics covered (e.g., `["greetings", "introductions"]`) |
| `thumbnail_url` | string | URL to lesson thumbnail image |

**Example LessonMetadata**:
```json
{
  "id": "spanish-greetings-a0",
  "title": "Basic Greetings",
  "description": "Learn to say hello and introduce yourself in Spanish.",
  "language": "es",
  "level": "A0",
  "duration_minutes": 10,
  "step_count": 5,
  "topics": ["greetings", "introductions", "basic phrases"],
  "thumbnail_url": "/static/lessons/thumbnails/greetings.png"
}
```

---

### LessonStep

A single step within a lesson.

| Field | Type | Description |
|-------|------|-------------|
| `index` | integer | Zero-based position in the lesson |
| `type` | string | Step type: `instruction`, `example`, `exercise`, `summary` |
| `content` | string | Main text content (supports Markdown) |
| `audio_url` | string or null | URL to audio pronunciation (if applicable) |
| `exercise` | Exercise or null | Exercise component (if type is `exercise`) |
| `vocabulary` | array[VocabWord] | Vocabulary introduced in this step |

**Example LessonStep (instruction type)**:
```json
{
  "index": 0,
  "type": "instruction",
  "content": "In Spanish, 'hola' is the most common way to say hello. It can be used in both formal and informal situations.",
  "audio_url": "/static/audio/es/hola.mp3",
  "exercise": null,
  "vocabulary": [
    {
      "word": "hola",
      "translation": "hello",
      "part_of_speech": "interjection"
    }
  ]
}
```

**Example LessonStep (exercise type)**:
```json
{
  "index": 2,
  "type": "exercise",
  "content": "Choose the correct greeting for the morning:",
  "audio_url": null,
  "exercise": {
    "id": "morning-greeting-mc",
    "type": "multiple_choice",
    "question": "How do you say 'good morning' in Spanish?",
    "options": ["Buenos dias", "Buenas noches", "Buenas tardes", "Hola"],
    "correct_answer": "Buenos dias",
    "feedback": {
      "correct": "Excellent! 'Buenos dias' is used until around noon.",
      "incorrect": "Not quite. 'Buenos dias' means 'good morning'."
    }
  },
  "vocabulary": []
}
```

---

### Exercise Types

Lessons support multiple exercise types, each with specific data structures.

#### Multiple Choice

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique exercise identifier |
| `type` | string | Always `multiple_choice` |
| `question` | string | Question text |
| `options` | array[string] | Answer choices (2-4 options) |
| `correct_answer` | string | The correct option |
| `feedback` | object | Feedback messages for correct/incorrect |

**Example**:
```json
{
  "id": "greeting-mc-1",
  "type": "multiple_choice",
  "question": "Which greeting is appropriate for the evening?",
  "options": ["Buenos dias", "Buenas tardes", "Buenas noches"],
  "correct_answer": "Buenas noches",
  "feedback": {
    "correct": "Correct! 'Buenas noches' is used in the evening and night.",
    "incorrect": "Remember, 'noches' means 'nights', so 'Buenas noches' is for evening."
  }
}
```

#### Fill in the Blank

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique exercise identifier |
| `type` | string | Always `fill_blank` |
| `sentence` | string | Sentence with `___` placeholder |
| `correct_answer` | string | Expected answer |
| `acceptable_answers` | array[string] | Alternative correct answers |
| `hint` | string | Optional hint text |
| `feedback` | object | Feedback messages |

**Example**:
```json
{
  "id": "intro-fill-1",
  "type": "fill_blank",
  "sentence": "Me ___ Maria.",
  "correct_answer": "llamo",
  "acceptable_answers": ["llamo"],
  "hint": "This verb means 'to call oneself'",
  "feedback": {
    "correct": "Perfect! 'Me llamo' means 'I am called' or 'My name is'.",
    "incorrect": "The answer is 'llamo'. 'Me llamo' literally means 'I call myself'."
  }
}
```

#### Matching

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique exercise identifier |
| `type` | string | Always `matching` |
| `instruction` | string | Exercise instruction |
| `pairs` | array[object] | Array of `{left, right}` pairs to match |
| `feedback` | object | Feedback messages |

**Example**:
```json
{
  "id": "greetings-match-1",
  "type": "matching",
  "instruction": "Match the Spanish greeting with its English meaning:",
  "pairs": [
    {"left": "Hola", "right": "Hello"},
    {"left": "Buenos dias", "right": "Good morning"},
    {"left": "Buenas noches", "right": "Good night"},
    {"left": "Adios", "right": "Goodbye"}
  ],
  "feedback": {
    "correct": "Excellent! You matched all the greetings correctly.",
    "incorrect": "Some matches were incorrect. Review and try again."
  }
}
```

#### Audio Response

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique exercise identifier |
| `type` | string | Always `audio_response` |
| `prompt` | string | What the user should say |
| `expected_phrase` | string | Expected spoken phrase |
| `audio_example_url` | string | URL to example pronunciation |
| `feedback` | object | Feedback messages |

**Example**:
```json
{
  "id": "pronunciation-1",
  "type": "audio_response",
  "prompt": "Say 'Mucho gusto' (Nice to meet you)",
  "expected_phrase": "Mucho gusto",
  "audio_example_url": "/static/audio/es/mucho-gusto.mp3",
  "feedback": {
    "correct": "Great pronunciation! 'Mucho gusto' is perfect for introductions.",
    "incorrect": "Try again. Listen to the example and match the pronunciation."
  }
}
```

---

## Lesson HTMX Integration

### Lesson Player Structure

```html
<div id="lesson-player">
  <!-- Progress bar -->
  <div id="progress-bar"
       hx-get="/lessons/spanish-greetings-a0/progress"
       hx-trigger="stepChanged from:body">
    <div class="progress" style="width: 20%"></div>
  </div>

  <!-- Step content area -->
  <div id="step-content"
       hx-get="/lessons/spanish-greetings-a0/step/0"
       hx-trigger="load">
  </div>

  <!-- Navigation -->
  <div id="lesson-nav">
    <button hx-post="/lessons/spanish-greetings-a0/step/prev"
            hx-target="#step-content"
            hx-include="[name='current_step']">
      Previous
    </button>
    <button hx-post="/lessons/spanish-greetings-a0/step/next"
            hx-target="#step-content"
            hx-include="[name='current_step']">
      Next
    </button>
  </div>
</div>
```

### Exercise Submission

```html
<form hx-post="/lessons/spanish-greetings-a0/exercise/greeting-mc-1/submit"
      hx-target="#exercise-result"
      hx-swap="innerHTML">
  <input type="hidden" name="answer" id="selected-answer">
  <div class="options">
    <button type="button" onclick="selectOption('hola')">Hola</button>
    <button type="button" onclick="selectOption('adios')">Adios</button>
  </div>
  <button type="submit">Check Answer</button>
</form>
<div id="exercise-result"></div>
```

---

## Progress Tracking

The progress tracking system provides a dashboard for viewing learning statistics, vocabulary growth, and session history. All endpoints use `OptionalUserDep` but require authentication to return meaningful data.

**Authentication**: Requires `sb-access-token` cookie for data access. Unauthenticated users see the progress page with empty/zero stats and a sign-up prompt (`is_guest: True`). All database operations use `get_supabase_for_user(sb_access_token)` to create a user-authenticated client that respects RLS policies.

---

### GET /progress/

Render the progress dashboard page.

**Authentication**: Required for data (`OptionalUserDep`). Unauthenticated users see empty stats with `is_guest: True` and a sign-up prompt.

**Response**: Full HTML page with progress dashboard including:
- Statistics summary cards
- Vocabulary list with filtering
- Progress charts
- Review stats (spaced repetition)

**Example**:
```bash
curl http://localhost:8000/progress/
```

---

### GET /progress/stats

Get the statistics summary as an HTML partial.

**Authentication**: Required for data (`OptionalUserDep`). Returns zeroed stats for unauthenticated users.

**Response**: HTML partial (`partials/progress_stats.html`) containing statistics cards.

**HTMX Integration**:
```html
<div hx-get="/progress/stats"
     hx-trigger="load"
     hx-target="#stats-container">
</div>
```

**Example**:
```bash
curl http://localhost:8000/progress/stats
```

---

### GET /progress/vocabulary

Get the vocabulary list as an HTML partial.

**Authentication**: Required for data (`OptionalUserDep`). Returns empty list for unauthenticated users.

**Query Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `language` | string | No | `es` | Filter by target language code: `es`, `de`, `fr` |

**Response**: HTML partial (`partials/vocabulary_list.html`) containing vocabulary table with:
- Word and translation
- Part of speech
- Date learned
- Delete button

**HTMX Integration**:
```html
<div hx-get="/progress/vocabulary?language=es"
     hx-trigger="load, languageChanged from:body"
     hx-target="#vocabulary-container">
</div>
```

**Example**:
```bash
curl "http://localhost:8000/progress/vocabulary?language=es"
```

---

### GET /progress/chart-data

Get chart data for progress visualization.

**Authentication**: Required for data (`OptionalUserDep`). Returns empty arrays for unauthenticated users.

**Query Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `language` | string | No | `es` | Filter by target language code: `es`, `de`, `fr` |
| `days` | integer | No | `30` | Number of days of history to include (max 90) |

**Response**: JSON object containing chart datasets.

**Example**:
```bash
curl "http://localhost:8000/progress/chart-data?language=es&days=30"
```

**Response Example**:
```json
{
  "vocab_growth": [
    {"date": "2025-01-01", "count": 5},
    {"date": "2025-01-02", "count": 8},
    {"date": "2025-01-03", "count": 12}
  ],
  "accuracy_trend": [
    {"date": "2025-01-01", "accuracy": 0.75},
    {"date": "2025-01-02", "accuracy": 0.82},
    {"date": "2025-01-03", "accuracy": 0.88}
  ]
}
```

---

### DELETE /progress/vocabulary/{word_id}

Remove a vocabulary word from the user's learned words.

**Authentication**: Required for data (`OptionalUserDep`). No-ops silently for unauthenticated users. Ownership enforced at database level via RLS.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `word_id` | string | Unique identifier for the vocabulary word |

**Response**: Empty response with 200 status on success, or error message.

**Response Headers**:
- `HX-Trigger`: `vocabularyUpdated` event for UI refresh

**HTMX Integration**:
```html
<button hx-delete="/progress/vocabulary/abc123"
        hx-target="closest tr"
        hx-swap="outerHTML swap:1s"
        hx-confirm="Remove this word from your vocabulary?">
  Remove
</button>
```

**Example**:
```bash
curl -X DELETE http://localhost:8000/progress/vocabulary/abc123
```

---

## Progress Data Structures

### DashboardStats

Statistics summary for the progress dashboard.

| Field | Type | Description |
|-------|------|-------------|
| `total_words` | integer | Total vocabulary words learned across all languages |
| `total_sessions` | integer | Total number of chat and lesson sessions |
| `lessons_completed` | integer | Number of lessons marked as complete |
| `current_streak` | integer | Current consecutive days of activity |
| `accuracy_rate` | float | Overall exercise accuracy (0.0 to 1.0) |
| `words_learned_today` | integer | Vocabulary words added today |
| `messages_today` | integer | Chat messages sent today |

**Example DashboardStats**:
```json
{
  "total_words": 127,
  "total_sessions": 45,
  "lessons_completed": 8,
  "current_streak": 5,
  "accuracy_rate": 0.84,
  "words_learned_today": 3,
  "messages_today": 12
}
```

---

### ChartData

Time-series data for progress visualization charts.

| Field | Type | Description |
|-------|------|-------------|
| `vocab_growth` | array[VocabGrowthPoint] | Daily vocabulary count over time |
| `accuracy_trend` | array[AccuracyTrendPoint] | Daily accuracy rate over time |

#### VocabGrowthPoint

| Field | Type | Description |
|-------|------|-------------|
| `date` | string | Date in ISO format (YYYY-MM-DD) |
| `count` | integer | Cumulative vocabulary count on this date |

#### AccuracyTrendPoint

| Field | Type | Description |
|-------|------|-------------|
| `date` | string | Date in ISO format (YYYY-MM-DD) |
| `accuracy` | float | Accuracy rate for exercises on this date (0.0 to 1.0) |

**Example ChartData**:
```json
{
  "vocab_growth": [
    {"date": "2025-01-25", "count": 115},
    {"date": "2025-01-26", "count": 120},
    {"date": "2025-01-27", "count": 124},
    {"date": "2025-01-28", "count": 127}
  ],
  "accuracy_trend": [
    {"date": "2025-01-25", "accuracy": 0.80},
    {"date": "2025-01-26", "accuracy": 0.85},
    {"date": "2025-01-27", "accuracy": 0.82},
    {"date": "2025-01-28", "accuracy": 0.88}
  ]
}
```

---

## Progress HTMX Integration

### Dashboard Page Structure

```html
<div id="progress-dashboard">
  <!-- Statistics Cards -->
  <div id="stats-container"
       hx-get="/progress/stats"
       hx-trigger="load">
  </div>

  <!-- Language Filter -->
  <select name="language"
          hx-get="/progress/vocabulary"
          hx-target="#vocabulary-container"
          hx-trigger="change"
          hx-vals='{"language": this.value}'>
    <option value="es">Spanish</option>
    <option value="de">German</option>
    <option value="fr">French</option>
  </select>

  <!-- Vocabulary Table -->
  <div id="vocabulary-container"
       hx-get="/progress/vocabulary?language=es"
       hx-trigger="load, vocabularyUpdated from:body">
  </div>

  <!-- Progress Chart -->
  <canvas id="progress-chart"></canvas>
  <script>
    // Fetch chart data and render with Chart.js
    fetch('/progress/chart-data?language=es&days=30')
      .then(res => res.json())
      .then(data => renderChart(data));
  </script>
</div>
```

### Vocabulary Item Actions

```html
<tr id="vocab-{{ word.id }}">
  <td>{{ word.word }}</td>
  <td>{{ word.translation }}</td>
  <td>{{ word.part_of_speech }}</td>
  <td>{{ word.learned_date }}</td>
  <td>
    <button hx-delete="/progress/vocabulary/{{ word.id }}"
            hx-target="#vocab-{{ word.id }}"
            hx-swap="outerHTML swap:0.5s"
            hx-confirm="Remove '{{ word.word }}' from your vocabulary?">
      Remove
    </button>
  </td>
</tr>
```

---

## Review Endpoints (Spaced Repetition)

The review system implements SM-2 spaced repetition for vocabulary reinforcement. All review endpoints require authentication (`CurrentUserDep`) and return 401 for unauthenticated users. Review session state is stored in a `review_session` cookie.

**Authentication**: Required (`CurrentUserDep`). All endpoints use `get_supabase_for_user(sb_access_token)` for database operations.

---

### GET /review/stats

Get review statistics for progress page and review prompts.

**Authentication**: Required.

**Query Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `language` | string | No | `es` | Target language code: `es`, `de`, `fr` |

**Response**: JSON object with review statistics.

**Example**:
```bash
curl http://localhost:8000/review/stats?language=es \
  --cookie "sb-access-token=<jwt_token>"
```

**Response Example**:
```json
{
  "due_count": 5,
  "next_review_in": "2 hours",
  "total_in_rotation": 42
}
```

---

### POST /review/start

Initialize a review session and return the first question.

**Authentication**: Required.

**Query Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `count` | integer or `"all"` | No | `10` | Number of words to review |
| `language` | string | No | `es` | Target language code |

**Response**: HTML partial (`partials/review_question.html`) with the first review question. Sets a `review_session` cookie with session state.

**Example**:
```bash
curl -X POST "http://localhost:8000/review/start?count=10&language=es" \
  --cookie "sb-access-token=<jwt_token>"
```

---

### POST /review/answer

Submit an answer for the current review question.

**Authentication**: Required.

**Request Body** (form data):

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `word_id` | integer | Yes | Vocabulary ID being answered |
| `user_answer` | string | Yes | User's submitted answer |

**Response**: HTML partial with feedback and the next question (`partials/review_feedback_question.html`), or session summary (`partials/review_summary.html`) if the session is complete. Updates SM-2 scheduling for the answered word.

**Example**:
```bash
curl -X POST http://localhost:8000/review/answer \
  -d "word_id=42" \
  -d "user_answer=cansado" \
  --cookie "sb-access-token=<jwt_token>" \
  --cookie "review_session=<session_state>"
```

---

### POST /review/end

End the current review session early and show a summary.

**Authentication**: Not required (reads session cookie only).

**Response**: HTML partial (`partials/review_summary.html`) with progress so far. Clears the `review_session` cookie.

---

### DELETE /review/warmup-prompt

Dismiss the review warmup prompt for the current browser session.

**Authentication**: Not required (manages UI preference cookie only).

**Response**: Empty response. Sets a `warmup_dismissed` session cookie to suppress the prompt.

---

## Learning Path Endpoints (Phase 14)

Phase 14 introduces structured learning paths with adaptive daily recommendations. These endpoints provide an overview of the learning path and personalized suggestions for what to learn next.

### GET /learn/

Render the learning path overview page showing structured progression from A0 to B1.

**Authentication**: Optional (`OptionalUserDep`). Authenticated users see their completion progress and adaptive recommendations. Guests see the path structure without progress data.

**Query Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `language` | string | No | `es` | Target language code: `es`, `de`, `fr` |

**Response**: Full HTML page (`learn.html`) containing:
- Path timeline with units and lessons
- Completion percentage and progress bar
- Current unit highlight
- Lazy-loaded recommendation card (via HTMX)
- Links to lesson player for each lesson

**Example**:
```bash
# View Spanish learning path
curl http://localhost:8000/learn/

# View German learning path
curl "http://localhost:8000/learn/?language=de"
```

---

### GET /learn/recommendation

Get the adaptive daily recommendation as an HTMX partial. Designed for lazy loading — the learn page renders first, then this card fills in asynchronously.

**Authentication**: Optional. Returns empty recommendation for guests.

**Query Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `language` | string | No | `es` | Target language code: `es`, `de`, `fr` |

**Response**: HTML partial (`partials/learn_recommendation.html`) containing:
- Next lesson suggestion with link
- Review due count (links to review mode)
- Weak category warnings (accuracy < 70%)
- Level readiness indicator
- Human-readable suggestion text

**HTMX Integration**:
```html
<div hx-get="/learn/recommendation?language=es"
     hx-trigger="load"
     hx-target="#recommendation-card">
</div>
```

**Example**:
```bash
curl "http://localhost:8000/learn/recommendation?language=es" \
  --cookie "sb-access-token=<jwt_token>"
```

---

### Learning Path Data Structures

#### DailyRecommendation

Personalized daily learning recommendation combining multiple signals.

| Field | Type | Description |
|-------|------|-------------|
| `next_lesson` | Lesson or null | The next uncompleted lesson in the path |
| `review_due_count` | integer | Words due for spaced repetition review |
| `weak_categories` | array[CategoryStrength] | Categories with accuracy below 70% |
| `level_readiness` | LevelReadiness or null | Current level completion summary |
| `suggestion_text` | string | Human-readable recommendation sentence |

#### CategoryStrength

| Field | Type | Description |
|-------|------|-------------|
| `category` | string | Category name (e.g., "greetings") |
| `total_words` | integer | Total vocabulary words in this category |
| `words_seen` | integer | Words the user has encountered |
| `accuracy` | float | Ratio of correct answers to total attempts (0.0-1.0) |
| `is_weak` | boolean | True when accuracy < 0.7 and user has seen words |

#### LevelReadiness

| Field | Type | Description |
|-------|------|-------------|
| `current_level` | string | CEFR level (e.g., "A1") |
| `completed_in_level` | integer | Lessons completed at this level |
| `total_in_level` | integer | Total lessons at this level |
| `readiness_pct` | float | Completion percentage (0-100) |
| `is_ready` | boolean | True when all lessons at the level are complete |
| `next_level` | string or null | Next CEFR level, or null at highest |

---

## Related Documentation

- [Product Specification](./product.md) - Vision, pedagogy, and feature details
- [Technical Architecture](./architecture.md) - LangGraph design and implementation phases
- [E2E Test Results](./playwright-e2e.md) - Playwright testing documentation
