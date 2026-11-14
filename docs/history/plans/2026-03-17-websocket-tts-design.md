# WebSocket TTS Design

**Date**: 2026-03-17
**Status**: Approved
**Goal**: Replace REST TTS (`POST /api/speak`) with WebSocket TTS (`/ws/speak`) for lower latency and better iOS reliability

## Motivation

- **Latency**: REST requires full audio download before playback. WebSocket streams chunks as generated, enabling faster time-to-first-byte even with accumulate-then-play.
- **iOS reliability**: WebSocket connections reuse the same auth and connection patterns already proven by STT on iOS Safari.

## Approach

Per-utterance WebSocket connection (Approach A). Open a new WebSocket for each TTS request, stream audio, close when done. No persistent connection management needed.

## Server Changes

**File**: `src/api/routes/voice.py`

Single change: update the existing `/ws/speak` endpoint's Deepgram URL from `encoding=linear16&sample_rate=24000` to `encoding=mp3`. This makes the streamed binary chunks playable by the `<audio>` element without client-side PCM conversion.

No other server changes. The endpoint already handles:
- Authentication (JWT/session/query-token via `_authenticate_websocket()`)
- Voice validation against `ALLOWED_VOICES`
- Rate limiting (`WebSocketMessageRateLimiter`)
- Text input as JSON, binary audio output, metadata delimiter

## Client Changes

**File**: `src/static/js/modules/voice-tts.js`

Replace `doFetch()` REST logic with WebSocket flow. State machine unchanged (`idle -> loading -> playing -> idle`).

### New WebSocket Flow

1. Build URL: `wss://{host}/ws/speak?voice={voice}&token={wsToken}`
2. Open WebSocket
3. On open: send `{"text": "chunk1"}` (first text chunk from `chunkTextForTTS()`)
4. Accumulate incoming binary messages into an array
5. On JSON message with `"type": "metadata"`: current chunk complete, send next chunk or finalize
6. After all chunks done: concatenate binary into single `Blob("audio/mpeg")`, play via `<audio>` element blob URL
7. On error/unexpected close: cleanup, transition to ERROR state

### Cancellation

On AbortSignal abort: send `{"type": "close"}`, close WebSocket, cleanup resources.

### REST Fallback

If WebSocket connection fails (e.g., proxy blocks WS upgrades), fall back to existing `POST /api/speak` REST flow. Keeps the feature resilient.

### iOS Compatibility

Preserved unchanged:
- Same `<audio id="tts-player">` playback path (`load()` -> `play()`)
- Same iOS speaker routing workaround (getUserMedia before playback)
- Same silent MP3 pre-initialization
- Auth token from `data-ws-token` attribute (same pattern as STT)

**File**: `src/static/js/modules/voice-constants.js`

Add `WS_SPEAK_PATH` constant for the WebSocket endpoint path.

## Files Unchanged

- `voice.js` — orchestrator calls `audioElementTTS()` with same signature
- `voice-stt.js` — unrelated
- `chat.html` — `<audio>` element and `data-ws-token` already present
- Server auth — reuses existing `_authenticate_websocket()`

## Testing

- **Unit tests (Vitest)**: Mock WebSocket, verify chunk sequencing, metadata handling, blob creation, REST fallback on connection failure
- **Manual**: Desktop Chrome + iOS Safari
- **Verify**: Cancellation mid-stream, network interruption, rate limiting behavior

## Risk Assessment

| Area | Risk | Rationale |
|------|------|-----------|
| Server encoding change | Low | Single query param (`encoding=mp3`) |
| Client transport swap | Low | Same state machine, same playback path |
| iOS Safari WebSocket | Medium | Already proven via STT, but TTS audio routing needs manual testing |
