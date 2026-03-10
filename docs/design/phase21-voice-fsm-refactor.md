# Phase 21: Voice Module FSM + AbortController Refactor

## Problem

voice.js (1,047 lines) manages two independent async subsystems (STT and TTS) using scattered boolean flags (`isRecording`, `_ttsPlaying`), a generation counter (`_ttsGeneration`), and manual resource cleanup across 15+ methods. This causes:

1. **TTS audio doesn't play** — iOS AudioContext state transitions silently fail; cleanup races with playback start
2. **TTS gets stuck** — `source.onended` doesn't fire reliably; playing icon persists after audio finishes
3. **STT drops audio** — AudioWorklet connects after WebSocket opens; audio frames sent before pipeline ready
4. **Double-play glitches** — rapid speaker clicks create overlapping TTS sessions with shared mutable state

Root cause: implicit state managed via booleans, with no transition guards to prevent invalid operations.

## Solution

Two changes that address all four symptoms:

1. **Hand-rolled finite state machine** — explicit states with guarded transitions eliminate invalid state combinations
2. **AbortController per session** — single cancellation mechanism replaces scattered manual cleanup

## Architecture

### New file: `src/static/js/modules/fsm.js` (~60 lines)

Generic, reusable FSM with two exports:

```js
export function createMachine(config)
// Returns frozen machine definition { initial, states }

export function interpret(machine, onChange)
// Returns service { state, send(event), matches(state), stop() }
```

Design choices:
- **Immutable machine definition** — `createMachine` returns a frozen object
- **Invalid transitions are no-ops** — `send('BOGUS')` logs `console.warn`, doesn't throw. Stale callbacks safely fire without crashing.
- **Single onChange callback** — no event emitter complexity
- **No async/effects built-in** — FSM is pure state logic. Side effects happen in onChange handler.

### Rewritten file: `src/static/js/modules/voice.js`

Rewritten from prototype pattern to exported functions (matching codebase style: dom.js, stream.js, shortcuts.js). Uses two FSM instances internally.

#### STT State Machine

```
                 START              CONNECTED
  idle ──────────────> connecting ──────────────> recording
   ^                    |                           |
   |                    | ERROR / CANCEL             | STOP
   |                    v                            v
   |                  idle                       processing
   |                                                |
   |                          PROCESSED / ERROR      |
   +─────────────────────────────────────────────────+
```

| State | What's happening | UI |
|-------|------------------|----|
| idle | Nothing active | Mic icon |
| connecting | getUserMedia() + WebSocket opening | Mic icon (brief) |
| recording | Audio flowing to Deepgram via WS | Level bars + timer |
| processing | WS closed, waiting for final transcript | Spinner + "Processing..." pill |

#### TTS State Machine

```
                 PLAY              STREAMING           ALL_ENDED
  idle ──────────────> loading ──────────────> playing ──────────> idle
   ^                    |                        |
   |                    | ERROR / CANCEL          | CANCEL / ERROR
   +────────────────────+────────────────────────+
```

| State | What's happening | UI |
|-------|------------------|----|
| idle | Nothing active | Speaker icon |
| loading | WebSocket connecting to /ws/speak | Speaker with loading state |
| playing | Audio buffers scheduled and playing | Speaker playing icon + stop bar |

#### AbortController Integration

Each STT/TTS session creates one `AbortController`:

- Created on session start transition (START / PLAY)
- `signal` referenced by all async resources (WebSocket handlers, AudioContext callbacks, timers)
- On CANCEL or ERROR: `controller.abort()` triggers cleanup of all resources in one call
- Stale callbacks check `signal.aborted` before acting

This replaces:
- `isRecording` boolean → `sttService.matches('recording')`
- `_ttsPlaying` boolean → `ttsService.matches('playing')`
- `_ttsGeneration` counter → AbortController signal
- Manual cleanup in 6+ methods → single abort handler

#### Public API (exported functions)

```js
export function initVoice()          // Called once on DOMContentLoaded
export function destroyVoice()       // Called on beforeunload
export function toggleRecording()    // Mic button click
export function handleSpeakClick(btn) // Speaker button delegation
export function stopAllTTS()         // External stop (e.g., new message arriving)
```

Internal state (module-scoped, not on window):
- `sttService` — FSM service for STT
- `ttsService` — FSM service for TTS
- `sttAbort` — current STT AbortController (null when idle)
- `ttsAbort` — current TTS AbortController (null when idle)

#### Race Condition Fixes

| Symptom | Current bug | FSM fix |
|---------|------------|---------|
| TTS no audio (iOS) | AudioContext.resume() races with buffer scheduling | loading state waits for resume + WS open before transitioning to playing |
| TTS stuck | source.onended unreliable; cleanup never fires | Fallback timeout + ALL_ENDED event; abort signal ensures cleanup |
| STT drops audio | AudioWorklet async load races with WS.onopen | connecting state waits for BOTH worklet ready + WS open before recording |
| Double-play | Shared mutable state across TTS sessions | PLAY event in loading/playing auto-cancels via abort before starting new session |

## Testing Strategy

- **fsm.js**: Pure unit tests — transition tables, no-op on invalid events, onChange callback, stop()
- **voice.js**: Rewrite existing 1,852-line test suite to use new API. Mock FSM service for isolation.
- All 193 existing JS tests must pass. New tests added for:
  - STT state transitions (idle → connecting → recording → processing → idle)
  - TTS state transitions (idle → loading → playing → idle)
  - AbortController cancellation (signal.aborted checks)
  - Race conditions (rapid clicks, stale callbacks)

## Files Changed

| File | Change |
|------|--------|
| `src/static/js/modules/fsm.js` | NEW — generic FSM (~60 lines) |
| `src/static/js/modules/voice.js` | REWRITE — function-based with FSM + AbortController |
| `tests/js/fsm.test.js` | NEW — FSM unit tests |
| `tests/js/voice.test.js` | REWRITE — updated for new API |

## Non-Goals

- No TypeScript migration
- No changes to backend voice.py
- No changes to audio processing (PCM conversion, downsampling)
- No new npm dependencies
- No changes to HTML templates (voice.js still self-initializes, sets window.voiceManager for backward compat)
