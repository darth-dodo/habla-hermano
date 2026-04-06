# Fix WebSocket TTS (encoding=mp3 -> linear16) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the broken WebSocket TTS endpoint by switching from `encoding=mp3` (unsupported on Deepgram WS) to `encoding=linear16&container=none`, and update the client to play raw PCM audio via Web Audio API.

**Architecture:** The server-side `/ws/speak` endpoint proxies text from the browser to Deepgram's WebSocket TTS and forwards binary audio back. Currently broken because `encoding=mp3` isn't supported on Deepgram's WS API (only REST). Fix: change to `linear16` raw PCM on the server, add a lightweight PCM-to-playable-audio converter on the client. The client already accumulates all chunks before playing, so we just need to wrap the raw PCM in a WAV header before creating the blob URL.

**Tech Stack:** Python (FastAPI WebSocket), JavaScript (Web Audio API), Deepgram TTS WebSocket API

---

### Task 1: Fix server-side Deepgram WebSocket URL encoding

**Files:**
- Modify: `src/api/routes/voice.py:480`

**Step 1: Update the Deepgram URL**

In `src/api/routes/voice.py`, line 480, change:
```python
dg_url = f"wss://api.deepgram.com/v1/speak?model={voice}&encoding=mp3&mip_opt_out=true"
```
to:
```python
dg_url = f"wss://api.deepgram.com/v1/speak?model={voice}&encoding=linear16&container=none&sample_rate=24000&mip_opt_out=true"
```

**Step 2: Update the docstring**

In `src/api/routes/voice.py`, update the `speak_stream` docstring (around line 453-454) to reflect the actual protocol:
```
Server -> binary audio chunks (raw linear16 PCM, 24kHz mono)
Server -> {"type": "Flushed", ...} (JSON when audio chunk is complete)
```

**Step 3: Catch InvalidStatus from websockets library**

The `except` clause at line 496 doesn't catch `websockets.InvalidStatus`, which is why the error propagates as an unhandled traceback. Add it to the exception handling in `speak_stream`:

```python
except WebSocketDisconnect:
    logger.debug("WebSocket disconnected during TTS setup")
except Exception as exc:
    # Catch websockets.InvalidStatus (HTTP 400/401/etc from Deepgram),
    # ConnectionError, OSError, RuntimeError, and any other transport errors.
    logger.exception("Error in TTS WebSocket")
    with contextlib.suppress(Exception):
        await websocket.close(code=1011, reason="Internal error")
```

Note: We broaden to `Exception` here because the `websockets` import is lazy (inside the try block), so we can't reference `websockets.InvalidStatus` in the except clause without importing it at module level. Using bare `Exception` is acceptable since we're at the outermost handler of this endpoint and we log + close with 1011.

**Step 4: Update the metadata message type check in _forward_deepgram_to_browser**

The Deepgram WS TTS API sends `Flushed` events (not `metadata`). The current `_forward_deepgram_to_browser` forwards all messages (bytes and text) unchanged, so no server-side change needed for the forwarding logic itself. The client will handle the new message types.

No code change needed for this step — just noting the protocol difference.

**Step 5: Run existing server tests**

Run: `cd /Users/abhishek/stuff/ai-adventures/habla-hermano && python -m pytest tests/api/routes/test_voice.py tests/api/routes/test_voice_integration.py -x -q 2>&1 | tail -20`

Expected: Some tests will fail because `test_deepgram_url_contains_encoding_params` asserts `encoding=mp3`. That's expected — we fix it in Task 2.

---

### Task 2: Update server-side tests for new encoding

**Files:**
- Modify: `tests/api/routes/test_voice_integration.py:1341-1360`

**Step 1: Update the encoding assertion test**

In `tests/api/routes/test_voice_integration.py`, find `test_deepgram_url_contains_encoding_params` (around line 1341). Change:
```python
assert "encoding=mp3" in url
assert "sample_rate" not in url
```
to:
```python
assert "encoding=linear16" in url
assert "container=none" in url
assert "sample_rate=24000" in url
```

Also update the docstring from `"The Deepgram TTS URL includes encoding=mp3."` to `"The Deepgram TTS URL includes linear16 encoding for WebSocket."`.

**Step 2: Run all voice tests**

Run: `cd /Users/abhishek/stuff/ai-adventures/habla-hermano && python -m pytest tests/api/routes/test_voice.py tests/api/routes/test_voice_integration.py -x -q 2>&1 | tail -20`

Expected: All pass.

**Step 3: Commit**

```bash
git add src/api/routes/voice.py tests/api/routes/test_voice_integration.py
git commit -m "fix: use linear16 encoding for Deepgram WebSocket TTS

encoding=mp3 is only supported on Deepgram's REST API, not WebSocket.
The WS endpoint was silently failing with HTTP 400 on every request,
falling back to REST. Switch to linear16 with container=none for raw PCM.

Also broaden exception handling to catch websockets.InvalidStatus."
```

---

### Task 3: Add WAV header utility to client for PCM playback

**Files:**
- Modify: `src/static/js/modules/voice-constants.js`

The browser can't play raw linear16 PCM directly. We need to wrap it in a WAV header. This is a simple 44-byte header prepended to the raw PCM bytes.

**Step 1: Add createWavBlob utility function**

At the end of `src/static/js/modules/voice-constants.js`, add:

```javascript
/**
 * Wrap raw linear16 PCM data in a WAV container for browser playback.
 * Creates a minimal 44-byte WAV header + raw PCM payload.
 *
 * @param {ArrayBuffer[]} pcmBuffers - Array of raw PCM ArrayBuffers (16-bit LE mono)
 * @param {number} sampleRate - Sample rate in Hz (e.g. 24000)
 * @returns {Blob} WAV audio blob playable by <audio> element
 */
export function createWavBlob(pcmBuffers, sampleRate) {
    // Calculate total PCM data length
    var dataLength = 0;
    for (var i = 0; i < pcmBuffers.length; i++) {
        dataLength += pcmBuffers[i].byteLength;
    }

    var numChannels = 1;
    var bitsPerSample = 16;
    var byteRate = sampleRate * numChannels * (bitsPerSample / 8);
    var blockAlign = numChannels * (bitsPerSample / 8);

    // 44-byte WAV header
    var header = new ArrayBuffer(44);
    var view = new DataView(header);

    // RIFF chunk descriptor
    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + dataLength, true); // file size - 8
    writeString(view, 8, 'WAVE');

    // fmt sub-chunk
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);             // sub-chunk size (PCM = 16)
    view.setUint16(20, 1, true);              // audio format (1 = PCM)
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitsPerSample, true);

    // data sub-chunk
    writeString(view, 36, 'data');
    view.setUint32(40, dataLength, true);

    // Combine header + all PCM buffers into one Blob
    var parts = [header];
    for (var j = 0; j < pcmBuffers.length; j++) {
        parts.push(pcmBuffers[j]);
    }
    return new Blob(parts, { type: 'audio/wav' });
}

function writeString(view, offset, str) {
    for (var i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
    }
}
```

**Step 2: Add the TTS_WS_SAMPLE_RATE constant**

At the top of `voice-constants.js`, near the existing `TTS_SAMPLE_RATE` constant (line 14), add:

```javascript
export var TTS_WS_SAMPLE_RATE = 24000; // Deepgram WS TTS linear16 sample rate
```

**Step 3: Commit**

```bash
git add src/static/js/modules/voice-constants.js
git commit -m "feat: add WAV header utility for WebSocket TTS PCM playback"
```

---

### Task 4: Update client WebSocket TTS to use PCM/WAV

**Files:**
- Modify: `src/static/js/modules/voice-tts.js:121-257`

**Step 1: Import the new utilities**

In `voice-tts.js` line 2 (the import from voice-constants), add `createWavBlob` and `TTS_WS_SAMPLE_RATE`:

Change:
```javascript
import { chunkTextForTTS, WS_SPEAK_PATH } from './voice-constants.js';
```
to:
```javascript
import { chunkTextForTTS, WS_SPEAK_PATH, createWavBlob, TTS_WS_SAMPLE_RATE } from './voice-constants.js';
```

**Step 2: Update doWebSocketTTS to create WAV blob from PCM**

In `doWebSocketTTS`, the `ws.onmessage` handler at line ~203 checks for `msg.type === 'metadata'`. Deepgram's WS TTS actually sends `Flushed` events (the type field is `"Flushed"` in the JSON). Update this check and the blob creation.

Replace the `ws.onmessage` handler (lines 190-221) with:

```javascript
    ws.onmessage = function(event) {
        if (signal.aborted) { cleanup(); return; }

        // Binary frame — accumulate raw PCM audio data
        if (event.data instanceof ArrayBuffer) {
            allBuffers.push(event.data);
            return;
        }

        // Text frame — parse JSON (Flushed event signals chunk complete)
        var msg;
        try { msg = JSON.parse(event.data); } catch (_) { return; }

        if (msg.type === 'Flushed') {
            chunkIndex++;
            if (chunkIndex < textChunks.length) {
                // More chunks to send
                ws.send(JSON.stringify({ text: textChunks[chunkIndex] }));
            } else {
                // All chunks done — wrap PCM in WAV and play
                signal.removeEventListener('abort', onAbort);
                cleanup();

                if (allBuffers.length > 0) {
                    var wavBlob = createWavBlob(allBuffers, TTS_WS_SAMPLE_RATE);
                    playAudioFromBlob(wavBlob, speed, signal, ttsService, btn, showError);
                } else {
                    ttsService.send('ERROR');
                }
            }
        }
    };
```

Key changes:
1. `msg.type === 'metadata'` -> `msg.type === 'Flushed'` (actual Deepgram WS event name)
2. `new Blob(allBuffers, { type: 'audio/mpeg' })` -> `createWavBlob(allBuffers, TTS_WS_SAMPLE_RATE)` (raw PCM needs WAV header)

**Step 3: Commit**

```bash
git add src/static/js/modules/voice-tts.js
git commit -m "fix: WebSocket TTS uses WAV-wrapped PCM instead of MP3

Deepgram's WS TTS sends raw linear16 PCM (not MP3). Wrap accumulated
PCM buffers in a WAV header for browser-native playback via <audio>.
Also fix Flushed event name (was incorrectly checking for 'metadata')."
```

---

### Task 5: Update JS tests for WebSocket TTS changes

**Files:**
- Modify: `tests/js/voice.test.js`

**Step 1: Read the current TTS-related test section**

Read `tests/js/voice.test.js` around the TTS test section (search for "TTS State Machine" and "fetches audio via POST") to understand what needs updating.

**Step 2: Update any tests that check for `audio/mpeg` blob type in WS path**

If there are tests that verify the blob type from WebSocket TTS is `audio/mpeg`, update them to expect `audio/wav`. The REST fallback path (`doFetch`) still uses `audio/mpeg` — only the WS path changes.

**Step 3: Update MockWebSocket to simulate Flushed events**

If tests simulate Deepgram WS messages with `{"type": "metadata", ...}`, update them to use `{"type": "Flushed", ...}`.

**Step 4: Run JS tests**

Run: `cd /Users/abhishek/stuff/ai-adventures/habla-hermano && npx vitest run --reporter=verbose 2>&1 | tail -30`

Expected: All 238 JS tests pass.

**Step 5: Commit**

```bash
git add tests/js/voice.test.js
git commit -m "test: update JS tests for WebSocket TTS PCM/WAV changes"
```

---

### Task 6: Update server-side _forward_deepgram_to_browser metadata handling

**Files:**
- Modify: `src/api/routes/voice.py:390-406`

**Step 1: Review the forwarding function**

The `_forward_deepgram_to_browser` function at line 390 already forwards all message types (bytes and text) as-is. Since the client now handles `Flushed` instead of `metadata`, and the server just proxies, no functional change is needed.

However, update the docstring to reflect the actual protocol:

```python
async def _forward_deepgram_to_browser(dg_ws: Any, websocket: WebSocket) -> None:
    """Forward audio chunks and metadata from Deepgram WS to browser WS.

    Binary frames contain raw linear16 PCM audio (24kHz, mono, 16-bit LE).
    Text frames contain JSON events (Flushed, Cleared, Warning, etc.).
    """
```

**Step 2: Commit**

```bash
git add src/api/routes/voice.py
git commit -m "docs: update TTS WebSocket docstrings for linear16 protocol"
```

---

### Task 7: Run full test suite and verify

**Files:** None (verification only)

**Step 1: Run Python tests**

Run: `cd /Users/abhishek/stuff/ai-adventures/habla-hermano && python -m pytest tests/ -x -q 2>&1 | tail -10`

Expected: All 2,291+ Python tests pass.

**Step 2: Run JS tests**

Run: `cd /Users/abhishek/stuff/ai-adventures/habla-hermano && npx vitest run 2>&1 | tail -10`

Expected: All 238 JS tests pass.

**Step 3: Run linting**

Run: `cd /Users/abhishek/stuff/ai-adventures/habla-hermano && make check 2>&1 | tail -20`

Expected: Clean (ruff + mypy pass).
