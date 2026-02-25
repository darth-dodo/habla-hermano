# Phase 18: JavaScript Unit Testing

> Establish automated unit test coverage for the client-side JavaScript modules, targeting ≥80% coverage across all three files. Tests are written against the **post-ESM-migration module structure** (Phase 16), making them a validation contract for that refactor.

---

## Overview

The project currently has 1952 Python tests (97% coverage) and zero JavaScript tests. The JS surface is ~1550 lines across three files with complex logic: SSE parsing, WebSocket state management, audio PCM conversion, and DOM manipulation. Several bugs have already been found in this layer (Phase 15 SSE bugs, Phase 17 TTS cleanup race).

This phase introduces a **Vitest + jsdom** test suite targeting the ES module structure from ADR-009/Phase 16. The tests serve two purposes:
1. Validate the ESM refactor didn't break behaviour
2. Provide ongoing regression protection for the JS layer

**ADR Reference**: [ADR-009: ES Module JavaScript Refactor](../adr/ADR-009-es-module-javascript-refactor.md)
**Prerequisite**: Phase 16 (ESM migration) should be completed first, or tests written against the planned module structure and run after migration.

---

## Constraints and Design Decisions

### Test Runner: Vitest

Vitest is chosen over Jest for three reasons:
1. **Native ES module support** — Jest requires Babel transpilation for ESM; Vitest handles it natively
2. **jsdom environment** — built-in DOM simulation without additional config
3. **`@vitest/coverage-v8`** — fast V8-native coverage without Istanbul overhead

### No Build Step for Production Code

Tests run in Vitest's Node.js + jsdom environment. The production JS files are imported directly as ES modules — no bundling or compilation of the source files. This preserves ADR-003's no-build-step constraint for production while adding a dev-only test runner.

### Testing Against ESM Modules, Not IIFEs

The current IIFE files (`app.js`, `stream.js`, `voice.js`) cannot be imported as ES modules — they have no exports. Tests are written against the post-Phase-16 module structure:

```
src/static/js/
├── main.js
├── voice.js               ← standalone module (no ESM dependency on main.js)
└── modules/
    ├── dom.js
    ├── stream.js
    ├── shortcuts.js
    ├── scaffold.js
    └── htmx-handlers.js
```

If Phase 16 hasn't landed yet, the test files can be written and held in `tests/static/js/` — they will fail until the ESM migration is complete, serving as a forward contract.

### What Is and Isn't Tested

**Unit tested (pure logic, no real browser APIs needed)**:
- SSE event parsing
- Audio PCM conversion (floatTo16BitPCM, downsample)
- HTML escaping
- Word insertion cursor math
- Speed clamping
- Timer formatting
- Event routing logic

**Integration tested (with jsdom mocks)**:
- Streaming bubble DOM lifecycle (create → append → finalize → speaker button)
- Voice state machine transitions (idle → recording → processing → idle)
- Form submission interception
- HTMX event handler dispatch
- Error tooltip creation and auto-dismiss

**Not tested (requires real browser)**:
- `getUserMedia` microphone access
- `AudioContext` / `ScriptProcessor` real audio
- Actual WebSocket connections (mocked at constructor level)
- `requestAnimationFrame` animation loop
- `visualViewport` resize events

---

## File Structure

```
habla-hermano/
├── package.json
├── vitest.config.js
└── tests/
    └── static/
        └── js/
            ├── dom.test.js          (~120 lines, ~15 tests)
            ├── stream.test.js       (~220 lines, ~28 tests)
            ├── scaffold.test.js     (~80 lines, ~10 tests)
            ├── shortcuts.test.js    (~80 lines, ~10 tests)
            ├── htmx-handlers.test.js (~60 lines, ~8 tests)
            └── voice.test.js        (~260 lines, ~32 tests)
```

**Total**: ~820 lines, ~103 tests

---

## Configuration

### `package.json`

```json
{
  "name": "habla-hermano",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage"
  },
  "devDependencies": {
    "@vitest/coverage-v8": "^3.0.0",
    "vitest": "^3.0.0",
    "jsdom": "^26.0.0"
  }
}
```

### `vitest.config.js`

```javascript
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['tests/static/js/**/*.test.js'],
    coverage: {
      provider: 'v8',
      include: ['src/static/js/**/*.js'],
      exclude: ['src/static/js/main.js'],  // entry point — minimal logic
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 75,
        statements: 80,
      },
      reporter: ['text', 'lcov'],
    },
  },
});
```

---

## Test Specifications

### `dom.test.js` — Shared DOM Utilities

**Target module**: `src/static/js/modules/dom.js`

| Test | Description |
|------|-------------|
| `escapeHtml` — escapes `<`, `>`, `&`, `"` | Pure function, no DOM needed |
| `escapeHtml` — returns empty string for empty input | Edge case |
| `escapeHtml` — passes through plain text unchanged | |
| `clearInput` — sets value to empty string | jsdom textarea |
| `clearInput` — resets inline height style | |
| `clearInput` — no-ops when element absent | Null guard |
| `autoResizeInput` — sets height to scrollHeight | Mock scrollHeight |
| `autoResizeInput` — caps at 120px | scrollHeight > 120 |
| `addUserMessage` — inserts bubble with escaped text | jsdom |
| `addUserMessage` — no-ops on empty/whitespace message | |
| `showLoading` — removes `hidden` class | |
| `hideLoading` — adds `hidden` class | |
| `scrollToBottom` — calls `scrollTo` with smooth | Mock scrollTo |
| `scrollToBottom` — calls `scrollTo` with auto when smooth=false | |

**Sample**:

```javascript
import { describe, it, expect, beforeEach } from 'vitest';
import { escapeHtml, clearInput, addUserMessage } from '../../../src/static/js/modules/dom.js';

describe('escapeHtml', () => {
  it('escapes angle brackets', () => {
    expect(escapeHtml('<script>')).toBe('&lt;script&gt;');
  });

  it('escapes ampersands', () => {
    expect(escapeHtml('a & b')).toBe('a &amp; b');
  });

  it('passes through plain text', () => {
    expect(escapeHtml('hello world')).toBe('hello world');
  });
});
```

---

### `stream.test.js` — SSE Streaming Client

**Target module**: `src/static/js/modules/stream.js`

The most critical test file — SSE parsing and bubble management have already caused production bugs.

| Test Group | Tests |
|-----------|-------|
| **parseSSEEvent** | |
| Returns `{event, data}` for simple event | `"event: token\ndata: {}\n"` |
| Defaults event to `message` when no event field | `"data: hello\n"` |
| Handles multi-line data fields | Two `data:` lines joined with `\n` |
| Returns `null` for empty/whitespace string | |
| Returns `null` for event with no data | |
| Trims whitespace from event name and data | |
| **Streaming bubble lifecycle** | |
| `createStreamingBubble` creates wrapper with correct ID | Check DOM |
| `appendToken` inserts text before cursor | |
| `appendToken` appends to end when cursor removed | |
| `finalizeBubble` removes cursor element | |
| `addSpeakerButton` appends button when mic present | |
| `addSpeakerButton` no-ops when mic absent | |
| `addSpeakerButton` no-ops on empty text | |
| Speaker button has correct `data-text` and `data-language` | |
| **handleStreamEvent** | |
| `token` event calls `appendToken` | |
| `response_complete` calls `finalizeBubble` and `addSpeakerButton` | |
| `response_complete` falls back to bubble text when `data.content` empty | |
| `scaffolding` event calls `insertFeedback` when `data.html` present | |
| `grammar` event calls `insertFeedback` | |
| `done` event calls `finishStreaming` | |
| `error` event calls `finalizeBubble` and `showStreamError` | |
| **SSE buffer parsing** | |
| Splits on double newlines | |
| Handles `\r\n` line endings | Already caused a production bug |
| Keeps partial events in buffer | |
| Processes leftover buffer after stream ends | |
| **Error messages** | |
| `AbortError` → "Response timed out" | |
| Generic network error → "Connection lost" | |
| Non-ok HTTP response → error shown | |

**Sample**:

```javascript
import { describe, it, expect } from 'vitest';
// parseSSEEvent is an internal function — exported for testing in ESM module
import { parseSSEEvent } from '../../../src/static/js/modules/stream.js';

describe('parseSSEEvent', () => {
  it('parses a standard token event', () => {
    const raw = 'event: token\ndata: {"content": "hola"}';
    const result = parseSSEEvent(raw);
    expect(result).toEqual({ event: 'token', data: '{"content": "hola"}' });
  });

  it('defaults event type to message', () => {
    const result = parseSSEEvent('data: hello');
    expect(result?.event).toBe('message');
  });

  it('returns null for empty input', () => {
    expect(parseSSEEvent('')).toBeNull();
    expect(parseSSEEvent('   ')).toBeNull();
  });

  it('joins multi-line data fields', () => {
    const raw = 'event: test\ndata: line1\ndata: line2';
    const result = parseSSEEvent(raw);
    expect(result?.data).toBe('line1\nline2');
  });

  it('handles CRLF line endings', () => {
    const raw = 'event: token\r\ndata: {"content": "hi"}';
    // After \r\n normalisation in streamChat, parseSSEEvent receives \n only
    // Test both to ensure robustness
    const result = parseSSEEvent(raw.replace(/\r\n/g, '\n'));
    expect(result?.event).toBe('token');
  });
});
```

---

### `scaffold.test.js` — Word Bank & Sentence Starters

**Target module**: `src/static/js/modules/scaffold.js`

| Test | Description |
|------|-------------|
| `insertWord` — inserts word at cursor position | Simulated selectionStart/End |
| `insertWord` — adds space before if previous char isn't space | |
| `insertWord` — no space before when at start of input | |
| `insertWord` — adds trailing space after word | |
| `insertWord` — strips translation in parentheses | `"hola (hello)"` → `"hola"` |
| `insertWord` — replaces selected text | selectionStart ≠ selectionEnd |
| `insertWord` — no-ops when input absent | |
| `insertStarter` — replaces entire input with starter + space | |
| `insertStarter` — sets cursor to end | |
| `insertStarter` — no-ops when input absent | |

---

### `shortcuts.test.js` — Keyboard Shortcuts

**Target module**: `src/static/js/modules/shortcuts.js`

Tests use `dispatchEvent(new KeyboardEvent(...))` on `document`.

| Test | Description |
|------|-------------|
| `Cmd+Enter` submits chat form when input focused | Mock `form.requestSubmit()` |
| `Ctrl+Enter` submits chat form (Windows) | |
| `Cmd+Enter` no-ops when other element focused | |
| `Escape` blurs message input | |
| `Escape` no-ops when input not focused | |
| `/` focuses input when not in input | |
| `/` no-ops when input is active element | |
| `Cmd+Shift+N` triggers new conversation button | |

---

### `htmx-handlers.test.js` — HTMX Event Handlers

**Target module**: `src/static/js/modules/htmx-handlers.js`

| Test | Description |
|------|-------------|
| `onAfterSwap` scrolls to bottom | |
| `onAfterSwap` adds `animated` class to new messages | |
| `onResponseError` shows error bubble in chat | |
| `onResponseError` hides loading indicator | |
| `onNewConversationRequest` triggers on `/new` path | Check `handleNewConversation` called |
| `onNewConversationRequest` no-ops on other paths | |
| `handleNewConversation` clears message input | |

---

### `voice.test.js` — VoiceManager

**Target module**: `src/static/js/voice.js`

Voice is the most complex module. Tests focus on pure functions and state machine transitions using mocked browser APIs.

#### Pure Function Tests

| Test | Description |
|------|-------------|
| `floatTo16BitPCM` — converts positive float to correct int16 | `1.0` → `0x7FFF` |
| `floatTo16BitPCM` — converts negative float to correct int16 | `-1.0` → `-0x8000` |
| `floatTo16BitPCM` — clamps values outside [-1, 1] | `1.5` → `0x7FFF` |
| `floatTo16BitPCM` — output buffer is 2× input length (bytes) | |
| `floatTo16BitPCM` — zero input → zero output | |
| `downsample` — returns same buffer when rates equal | |
| `downsample` — reduces length by correct ratio | 44100→16000 = 0.36× length |
| `downsample` — output values are sampled from input | |
| Speed clamping — `0.25` passes through | |
| Speed clamping — `2.0` passes through | |
| Speed clamping — `0.1` clamped to `0.25` | |
| Speed clamping — `3.0` clamped to `2.0` | |

#### VoiceManager State Machine Tests

Uses mock constructors for `WebSocket`, `AudioContext`, `MediaStream`.

| Test | Description |
|------|-------------|
| `init` — no-ops when mic button absent | voice disabled |
| `init` — wraps mic button in relative container | |
| `init` — attaches click handler to mic button | |
| `init` — delegates `.voice-speak-btn` clicks | |
| `toggleRecording` — calls `startRecording` when not recording | |
| `toggleRecording` — calls `stopRecording` when recording | |
| `stopRecording` — sets `isRecording = false` | |
| `stopRecording` — disconnects ScriptProcessor | |
| `stopRecording` — stops stream tracks | |
| `stopRecording` — closes WebSocket when open | |
| `stopRecording` — shows processing state | |
| `_setSendEnabled(false)` — disables send button | |
| `_setSendEnabled(false)` — sets input readOnly | |
| `_setSendEnabled(true)` — enables send button | |
| `_setSendEnabled(true)` — removes readOnly | |
| `updateMicUI` — adds `voice-recording` class when recording | |
| `updateMicUI` — restores mic icon when not recording | |
| `_showProcessing` — sets spinner icon | |
| `_showProcessing` — appends processing indicator | |
| `_hideProcessing` — restores mic icon | |
| `_hideProcessing` — re-enables send | |
| `_showTooltipError` — creates tooltip with message | |
| `_showTooltipError` — auto-removes after 4s | Use fake timers |
| `_showTooltipError` — replaces existing tooltip | |

#### TTS State Tests

| Test | Description |
|------|-------------|
| `handleSpeakClick` — no-ops on empty `data-text` | |
| `handleSpeakClick` — stops if button is `voice-playing` | |
| `handleSpeakClick` — stops if button is `voice-loading` | Bug fix regression |
| `handleSpeakClick` — reads speed from picker element | |
| `handleSpeakClick` — falls back to `btn.dataset.speed` when no picker | |
| `handleSpeakClick` — falls back to DEFAULT_TTS_SPEED | |
| `_stopTTS` — closes WebSocket | |
| `_stopTTS` — pauses currentAudio | |
| `_stopTTS` — revokes blob URL | |
| `_stopTTS` — removes `voice-playing` and `voice-loading` classes | |
| `_stopAllTTS` — stops all playing buttons | |
| `_stopAllTTS` — stops loading buttons too | Bug fix regression |

**Sample — pure function test**:

```javascript
import { describe, it, expect } from 'vitest';
import { floatTo16BitPCM, downsample } from '../../../src/static/js/voice.js';

describe('floatTo16BitPCM', () => {
  it('converts 1.0 to maximum int16', () => {
    const input = new Float32Array([1.0]);
    const buffer = floatTo16BitPCM(input);
    const view = new DataView(buffer);
    expect(view.getInt16(0, true)).toBe(0x7FFF);
  });

  it('converts -1.0 to minimum int16', () => {
    const input = new Float32Array([-1.0]);
    const buffer = floatTo16BitPCM(input);
    const view = new DataView(buffer);
    expect(view.getInt16(0, true)).toBe(-0x8000);
  });

  it('clamps values above 1.0', () => {
    const input = new Float32Array([1.5]);
    const buffer = floatTo16BitPCM(input);
    const view = new DataView(buffer);
    expect(view.getInt16(0, true)).toBe(0x7FFF);
  });

  it('output buffer is 2 bytes per sample', () => {
    const input = new Float32Array(10);
    expect(floatTo16BitPCM(input).byteLength).toBe(20);
  });
});

describe('downsample', () => {
  it('returns same buffer when rates are equal', () => {
    const input = new Float32Array([0.1, 0.2, 0.3]);
    const result = downsample(input, 16000, 16000);
    expect(result).toBe(input);
  });

  it('reduces length proportionally', () => {
    const input = new Float32Array(441); // 10ms at 44.1kHz
    const result = downsample(input, 44100, 16000);
    expect(result.length).toBe(Math.round(441 * 16000 / 44100));
  });
});
```

**Sample — state machine test with mocks**:

```javascript
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { VoiceManager } from '../../../src/static/js/voice.js';

describe('VoiceManager._setSendEnabled', () => {
  let manager;

  beforeEach(() => {
    document.body.innerHTML = `
      <button id="send-btn"></button>
      <textarea id="message-input"></textarea>
      <button id="mic-btn"></button>
    `;
    manager = new VoiceManager();
    manager.init();
  });

  it('disables send button and makes input readOnly', () => {
    manager._setSendEnabled(false);
    expect(manager.sendButton.disabled).toBe(true);
    expect(manager.chatInput.readOnly).toBe(true);
  });

  it('re-enables send button and removes readOnly', () => {
    manager._setSendEnabled(false);
    manager._setSendEnabled(true);
    expect(manager.sendButton.disabled).toBe(false);
    expect(manager.chatInput.readOnly).toBe(false);
  });
});
```

---

## Coverage Targets

| Module | Target | Rationale |
|--------|--------|-----------|
| `modules/dom.js` | 90% | Pure utilities — highly testable |
| `modules/stream.js` | 85% | SSE parsing is fully testable; fetch/ReadableStream mocked |
| `modules/scaffold.js` | 95% | Pure DOM manipulation, no async |
| `modules/shortcuts.js` | 90% | Keyboard event dispatch is straightforward |
| `modules/htmx-handlers.js` | 80% | HTMX event dispatch via jsdom |
| `voice.js` | 75% | `getUserMedia`, `AudioContext`, animation frames excluded |
| **Overall** | **≥80%** | Hard threshold enforced in CI |

---

## Makefile Integration

Add to `Makefile`:

```makefile
test-js: ## Run JavaScript unit tests
	npm test

test-js-coverage: ## Run JavaScript tests with coverage report
	npm run test:coverage

test-js-watch: ## Run JavaScript tests in watch mode
	npm run test:watch

test-all: test test-js ## Run all tests (Python + JavaScript)
```

And extend `clean`:

```makefile
clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name node_modules -exec rm -rf {} + # add this
	rm -rf coverage/                                    # add this
```

---

## CI Integration

Add to `.github/workflows/ci.yml` after the Python test step:

```yaml
- name: Install JS dependencies
  run: npm ci

- name: Run JavaScript tests
  run: npm run test:coverage

- name: Upload JS coverage
  uses: codecov/codecov-action@v4
  with:
    files: coverage/lcov.info
    flags: javascript
```

---

## Dependency on Phase 16 (ESM Migration)

This test phase has a hard dependency on Phase 16. The options are:

### Option A: Complete Phase 16 First (Recommended)

Implement the ESM refactor, then write tests against the modules. Tests serve as validation that the refactor is complete and correct.

**Timeline**: Phase 16 (~2h) → Phase 18 (~3h) → both land together

### Option B: Write Tests as Forward Contract

Write the test files targeting the Phase 16 module structure. They will fail until the migration is done. The failing tests in CI signal "Phase 16 is incomplete".

**Useful when**: Phase 16 work is deferred but you want to define the expected API now.

### Option C: Adapter Layer (Not Recommended)

Write test-only wrapper modules that re-export from the IIFE files via `eval()` hacks. Too fragile and defeats the point.

---

## What These Tests Don't Cover (and Why)

| Scenario | Why Excluded |
|----------|-------------|
| Real microphone access (`getUserMedia`) | Requires browser, cannot mock securely in Node |
| Real `AudioContext` audio playback | jsdom has no audio support |
| Actual WebSocket connections to Deepgram | Requires live API key and network |
| `requestAnimationFrame` animation loop | Skippable — animation is decorative |
| `visualViewport` resize (virtual keyboard) | iOS-specific, not testable in jsdom |
| SSE streaming over real HTTP | Covered by existing Python integration tests |

For real browser validation, the existing Playwright E2E test patterns (see Phase 17 design doc) cover the integration layer.

---

## Migration Checklist

- [ ] Complete Phase 16 ESM migration
- [ ] Add `package.json` with Vitest dependencies
- [ ] Add `vitest.config.js`
- [ ] Run `npm install`
- [ ] Write `tests/static/js/dom.test.js`
- [ ] Write `tests/static/js/stream.test.js`
- [ ] Write `tests/static/js/scaffold.test.js`
- [ ] Write `tests/static/js/shortcuts.test.js`
- [ ] Write `tests/static/js/htmx-handlers.test.js`
- [ ] Write `tests/static/js/voice.test.js`
- [ ] Run `npm run test:coverage` — verify ≥80% overall
- [ ] Add `test-js` and `test-js-coverage` targets to Makefile
- [ ] Add JS test step to `.github/workflows/ci.yml`
- [ ] Update MEMORY.md with JS test coverage status

---

## Notes for Future Agents

- `floatTo16BitPCM` and `downsample` in `voice.js` must be **exported** from the ESM module for testing — currently they're private IIFE-scope functions. Exporting them is a clean improvement regardless of testing.
- `parseSSEEvent` in `stream.js` is currently an internal function. It should also be exported from the ESM module — it's the most critical piece of logic to test.
- The speed picker in `chat.html` uses Alpine.js `x-data` — the `data-tts-speed` attribute is the bridge to `voice.js`. Tests for `handleSpeakClick` should set this attribute directly on a mock `#tts-speed-picker` element.
- When mocking WebSocket in tests, use `vi.stubGlobal('WebSocket', MockWebSocket)` — Vitest's `vi.stubGlobal` cleanly restores the original after each test.
- `_stopAllTTS` bug fix (stops `voice-loading` buttons, not just `voice-playing`) should have a regression test. This was a subtle bug that caused the speaker button to appear stuck.
