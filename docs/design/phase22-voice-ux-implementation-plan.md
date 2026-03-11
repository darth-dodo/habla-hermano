# Phase 22: Voice UX Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the utilitarian voice UI with a Telegram-inspired experience: mic/send button swap, animated recording bar, wavesurfer.js waveform players on AI messages, and animate.css transitions.

**Architecture:** Extend the existing 5-module voice system (voice.js orchestrator + 4 sub-modules). Add wavesurfer.js for waveform rendering, animate.css for transitions. New voice-waveform.js module wraps wavesurfer lifecycle. All state stays in voice.js; sub-modules remain stateless.

**Tech Stack:** Vanilla JS ES modules, wavesurfer.js (npm), animate.css (CDN), FSM (fsm.js), HTMX + Jinja2 templates, Tailwind CSS, Vitest + jsdom.

**Design Doc:** `docs/design/phase22-voice-ux-redesign.md`

---

## Task 1: Install Dependencies

**Files:**
- Modify: `package.json`
- Modify: `src/templates/base.html` (add animate.css CDN link)

**Step 1: Install wavesurfer.js**

```bash
cd /Users/abhishek/stuff/ai-adventures/habla-hermano
npm install --save wavesurfer.js
```

**Step 2: Add animate.css CDN to base.html**

In `src/templates/base.html`, inside `<head>` (after the Tailwind CDN link), add:

```html
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css" />
```

**Step 3: Verify imports work**

Create a temporary test: in browser console on the app, confirm `animate__animated` class exists and wavesurfer.js resolves. Then remove temp code.

**Step 4: Commit**

```bash
git add package.json package-lock.json src/templates/base.html
git commit -m "feat(voice): add wavesurfer.js and animate.css dependencies"
```

---

## Task 2: Mic/Send Button Swap

Replace the always-visible mic + send layout with a single button that swaps between mic (empty input) and send (has text). Crossfade animation via animate.css.

**Files:**
- Modify: `src/templates/chat.html` (lines 339-424, input area)
- Modify: `src/static/js/modules/voice-ui.js` (add swap helpers)
- Modify: `src/static/js/modules/voice-constants.js` (add SEND_ICON)
- Modify: `src/templates/base.html` (CSS for swap animation)
- Test: `tests/js/voice.test.js`

**Step 1: Write failing tests for mic/send swap**

In `tests/js/voice.test.js`, add a new describe block:

```javascript
describe('Mic/Send Button Swap', () => {
    it('shows mic button when input is empty', () => {
        const micBtn = document.getElementById('mic-btn');
        const sendBtn = document.getElementById('send-btn');
        // Trigger input event with empty value
        chatInput.value = '';
        chatInput.dispatchEvent(new Event('input'));
        expect(micBtn.classList.contains('hidden')).toBe(false);
        expect(sendBtn.classList.contains('hidden')).toBe(true);
    });

    it('shows send button when input has text', () => {
        const micBtn = document.getElementById('mic-btn');
        const sendBtn = document.getElementById('send-btn');
        chatInput.value = 'Hola';
        chatInput.dispatchEvent(new Event('input'));
        expect(micBtn.classList.contains('hidden')).toBe(true);
        expect(sendBtn.classList.contains('hidden')).toBe(false);
    });

    it('swaps back to mic when input cleared', () => {
        const micBtn = document.getElementById('mic-btn');
        const sendBtn = document.getElementById('send-btn');
        chatInput.value = 'Hola';
        chatInput.dispatchEvent(new Event('input'));
        chatInput.value = '';
        chatInput.dispatchEvent(new Event('input'));
        expect(micBtn.classList.contains('hidden')).toBe(false);
        expect(sendBtn.classList.contains('hidden')).toBe(true);
    });
});
```

**Step 2: Run tests to verify they fail**

```bash
npx vitest run tests/js/voice.test.js --reporter=verbose 2>&1 | tail -20
```

Expected: FAIL — swap logic doesn't exist yet.

**Step 3: Add SEND_ICON to voice-constants.js**

In `src/static/js/modules/voice-constants.js`, add after the existing icon exports:

```javascript
export var SEND_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
```

**Step 4: Add swap functions to voice-ui.js**

In `src/static/js/modules/voice-ui.js`, add:

```javascript
/**
 * Set up mic/send button swap listener on the input field.
 * Shows mic when empty, send when has text.
 */
export function setupButtonSwap(micButton, sendButton, chatInput) {
    function update() {
        var hasText = chatInput.value.trim().length > 0;
        if (hasText) {
            micButton.classList.add('hidden');
            sendButton.classList.remove('hidden');
        } else {
            micButton.classList.remove('hidden');
            sendButton.classList.add('hidden');
        }
    }
    chatInput.addEventListener('input', update);
    // Initial state
    update();
    return update;
}
```

**Step 5: Update chat.html markup**

In `src/templates/chat.html`, modify the input area (around lines 353-416):

- Move mic button to be a sibling of send button (both inside the same flex container after the textarea)
- Send button starts with `hidden` class
- Remove the old flex container that grouped mic + speed picker on the left
- Speed picker moves out (will be removed entirely in Task 5)

The new layout should be:

```html
<!-- Input area -->
<div class="flex items-end gap-3 p-4">
    <textarea id="message-input" ...></textarea>
    <div class="flex-shrink-0 relative">
        <button type="button" id="mic-btn" class="p-3 ..." aria-label="Record voice message">
            <!-- mic icon -->
        </button>
        <button type="submit" id="send-btn" class="hidden p-3 ..." aria-label="Send message">
            <!-- send icon -->
        </button>
    </div>
</div>
```

**Step 6: Wire up swap in voice.js initVoice()**

In `src/static/js/modules/voice.js`, in `initVoice()` (around line 244), after the DOM lookups, add:

```javascript
import { setupButtonSwap } from './voice-ui.js';
// ... inside initVoice(), after sendButton lookup:
if (micButton && sendButton && chatInput) {
    setupButtonSwap(micButton, sendButton, chatInput);
}
```

**Step 7: Run tests**

```bash
npx vitest run tests/js/voice.test.js --reporter=verbose 2>&1 | tail -30
```

Expected: New swap tests PASS.

**Step 8: Commit**

```bash
git add src/static/js/modules/voice-constants.js src/static/js/modules/voice-ui.js src/static/js/modules/voice.js src/templates/chat.html tests/js/voice.test.js
git commit -m "feat(voice): mic/send button swap based on input content"
```

---

## Task 3: Recording Bar UI

Replace the current recording indicators (red mic pulse, floating timer pill, floating spinner) with an inline recording bar that replaces the input area.

**Files:**
- Modify: `src/static/js/modules/voice-ui.js` (new recording bar functions)
- Modify: `src/static/js/modules/voice-constants.js` (add STOP_SQUARE_ICON, CANCEL_ICON)
- Modify: `src/static/js/modules/voice.js` (update onSttChange to use recording bar)
- Modify: `src/templates/base.html` (new CSS for recording bar)
- Test: `tests/js/voice.test.js`

**Step 1: Write failing tests for recording bar**

```javascript
describe('Recording Bar', () => {
    it('shows recording bar when recording starts', () => {
        // Simulate STT transition to recording
        sttService.send('START');
        // ... mock connecting -> recording transition
        const recordingBar = document.querySelector('.voice-recording-bar');
        expect(recordingBar).not.toBeNull();
        expect(chatInput.classList.contains('hidden')).toBe(true);
    });

    it('recording bar has cancel button, timer, and waveform area', () => {
        // Start recording
        const recordingBar = document.querySelector('.voice-recording-bar');
        expect(recordingBar.querySelector('.voice-cancel-btn')).not.toBeNull();
        expect(recordingBar.querySelector('.voice-rec-timer')).not.toBeNull();
        expect(recordingBar.querySelector('.voice-rec-waveform')).not.toBeNull();
    });

    it('cancel button restores input bar', () => {
        const cancelBtn = document.querySelector('.voice-cancel-btn');
        cancelBtn.click();
        expect(document.querySelector('.voice-recording-bar')).toBeNull();
        expect(chatInput.classList.contains('hidden')).toBe(false);
    });

    it('stop button triggers processing then restores input', async () => {
        const stopBtn = document.querySelector('.voice-stop-btn');
        stopBtn.click();
        // Should show processing, then restore
        await new Promise(r => setTimeout(r, 2100));
        expect(document.querySelector('.voice-recording-bar')).toBeNull();
    });
});
```

**Step 2: Run tests to verify they fail**

```bash
npx vitest run tests/js/voice.test.js --reporter=verbose 2>&1 | tail -20
```

**Step 3: Add new icons to voice-constants.js**

```javascript
export var STOP_SQUARE_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="6" width="12" height="12" rx="2"></rect></svg>';

export var CANCEL_X_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
```

**Step 4: Add recording bar CSS to base.html**

In `src/templates/base.html`, in the `<style>` section (after existing voice CSS around line 755), add:

```css
/* Recording bar — replaces input area during recording */
.voice-recording-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background-color: color-mix(in srgb, var(--error) 8%, var(--surface));
    border: 1px solid color-mix(in srgb, var(--error) 30%, var(--border));
    border-radius: 12px;
    width: 100%;
}

.voice-cancel-btn {
    flex-shrink: 0;
    padding: 6px;
    color: var(--text-subtle);
    border-radius: 50%;
    cursor: pointer;
    transition: color 0.15s ease, background-color 0.15s ease;
    background: none;
    border: none;
}
.voice-cancel-btn:hover {
    color: var(--error);
    background-color: color-mix(in srgb, var(--error) 10%, transparent);
}

.voice-rec-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: var(--error);
    animation: voicePulse 1.5s ease-in-out infinite;
    flex-shrink: 0;
}

.voice-rec-timer {
    font-size: 0.8125rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    color: var(--text-primary);
    min-width: 36px;
    flex-shrink: 0;
}

.voice-rec-waveform {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 2px;
    height: 28px;
    overflow: hidden;
}

.voice-rec-bar {
    width: 3px;
    min-height: 4px;
    border-radius: 9999px;
    background-color: var(--error);
    transition: height 0.08s ease-out;
    opacity: 0.7;
}

/* Mic morphs to stop button during recording */
.voice-stop-square {
    background-color: var(--error) !important;
    color: white !important;
}

@media (prefers-reduced-motion: reduce) {
    .voice-rec-dot { animation: none; opacity: 0.8; }
    .voice-rec-bar { height: 12px !important; }
}
```

**Step 5: Add recording bar DOM functions to voice-ui.js**

```javascript
import { CANCEL_X_ICON } from './voice-constants.js';

/**
 * Create and show the recording bar, hiding the input area.
 * Returns { element, timerEl, waveformEl, cancel } for the caller to manage.
 */
export function createRecordingBar(inputContainer, onCancel) {
    // Hide input elements
    var children = Array.from(inputContainer.children);
    children.forEach(function(child) { child.dataset.voiceHidden = ''; child.style.display = 'none'; });

    var bar = document.createElement('div');
    bar.className = 'voice-recording-bar animate__animated animate__fadeIn animate__faster';

    // Cancel button
    var cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'voice-cancel-btn';
    cancelBtn.innerHTML = CANCEL_X_ICON;
    cancelBtn.setAttribute('aria-label', 'Cancel recording');
    cancelBtn.addEventListener('click', function() { onCancel(); });

    // Red dot
    var dot = document.createElement('span');
    dot.className = 'voice-rec-dot';
    dot.setAttribute('aria-hidden', 'true');

    // Timer
    var timerEl = document.createElement('span');
    timerEl.className = 'voice-rec-timer';
    timerEl.textContent = '0:00';

    // Waveform container
    var waveformEl = document.createElement('div');
    waveformEl.className = 'voice-rec-waveform';
    waveformEl.setAttribute('aria-hidden', 'true');
    // Pre-fill with bars
    for (var i = 0; i < 30; i++) {
        var b = document.createElement('div');
        b.className = 'voice-rec-bar';
        b.style.height = '4px';
        waveformEl.appendChild(b);
    }

    bar.appendChild(cancelBtn);
    bar.appendChild(dot);
    bar.appendChild(timerEl);
    bar.appendChild(waveformEl);
    inputContainer.appendChild(bar);

    // Timer interval
    var seconds = 0;
    var timerInterval = setInterval(function() {
        seconds++;
        var m = Math.floor(seconds / 60);
        var s = seconds % 60;
        timerEl.textContent = m + ':' + (s < 10 ? '0' : '') + s;
    }, 1000);

    return {
        element: bar,
        timerEl: timerEl,
        waveformEl: waveformEl,
        cancel: function() { clearInterval(timerInterval); }
    };
}

/**
 * Remove the recording bar and restore the input area.
 * @param {string} animationOut - animate.css class for exit (e.g. 'slideOutLeft' or 'fadeOut')
 */
export function removeRecordingBar(handle, inputContainer, animationOut) {
    if (!handle || !handle.element) return;
    handle.cancel(); // stop timer

    var bar = handle.element;
    if (animationOut) {
        bar.classList.remove('animate__fadeIn');
        bar.classList.add('animate__' + animationOut);
        bar.addEventListener('animationend', function() { cleanup(); }, { once: true });
    } else {
        cleanup();
    }

    function cleanup() {
        if (bar.parentNode) bar.parentNode.removeChild(bar);
        // Restore hidden children
        var children = Array.from(inputContainer.children);
        children.forEach(function(child) {
            if (child.dataset.voiceHidden !== undefined) {
                child.style.display = '';
                delete child.dataset.voiceHidden;
            }
        });
    }
}

/**
 * Animate recording bar waveform from AnalyserNode data.
 */
export function animateRecordingWaveform(analyser, waveformEl, isRecordingFn) {
    if (!analyser || !waveformEl) return { stop: function() {} };
    var bars = waveformEl.querySelectorAll('.voice-rec-bar');
    var dataArray = new Uint8Array(analyser.frequencyBinCount);
    var running = true;

    function draw() {
        if (!running) return;
        analyser.getByteFrequencyData(dataArray);
        var step = Math.floor(dataArray.length / bars.length);
        for (var i = 0; i < bars.length; i++) {
            var value = dataArray[i * step] || 0;
            var height = Math.max(4, (value / 255) * 28);
            bars[i].style.height = height + 'px';
        }
        if (isRecordingFn()) requestAnimationFrame(draw);
    }
    requestAnimationFrame(draw);

    return {
        stop: function() { running = false; }
    };
}
```

**Step 6: Update voice.js onSttChange to use recording bar**

Replace the current recording UI logic in `onSttChange()` (lines 76-172 of voice.js). The key changes:

- On `recording` state: create recording bar, morph mic to stop button, start waveform animation
- On `processing` state: show spinner inside recording bar
- On `idle` (from any): remove recording bar with appropriate animation (slideOutLeft for cancel, fadeOut for normal)
- Cancel button sends `sttService.send('CANCEL')`

**Step 7: Run tests**

```bash
npx vitest run tests/js/voice.test.js --reporter=verbose 2>&1 | tail -30
```

**Step 8: Manual smoke test**

```bash
make dev
```

Open browser, test: tap mic → recording bar appears → tap stop → processing → restores. Tap mic → recording → tap cancel → slides out.

**Step 9: Commit**

```bash
git add src/static/js/modules/voice-ui.js src/static/js/modules/voice-constants.js src/static/js/modules/voice.js src/templates/base.html tests/js/voice.test.js
git commit -m "feat(voice): recording bar replaces input during STT"
```

---

## Task 4: Waveform Player Module (voice-waveform.js)

Create a new module that wraps wavesurfer.js for rendering waveform players on AI message bubbles.

**Files:**
- Create: `src/static/js/modules/voice-waveform.js`
- Test: `tests/js/voice-waveform.test.js`

**Step 1: Write failing tests**

Create `tests/js/voice-waveform.test.js`:

```javascript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock wavesurfer.js
vi.mock('wavesurfer.js', () => ({
    default: {
        create: vi.fn(() => ({
            on: vi.fn(),
            loadBlob: vi.fn(),
            play: vi.fn(),
            pause: vi.fn(),
            stop: vi.fn(),
            isPlaying: vi.fn(() => false),
            setPlaybackRate: vi.fn(),
            getPlaybackRate: vi.fn(() => 1),
            getCurrentTime: vi.fn(() => 0),
            getDuration: vi.fn(() => 10),
            destroy: vi.fn(),
            setOptions: vi.fn(),
        }))
    }
}));

import { createWaveformPlayer, destroyWaveformPlayer, SPEED_OPTIONS } from '../src/static/js/modules/voice-waveform.js';

describe('Voice Waveform Player', () => {
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        container.className = 'voice-waveform-container';
        document.body.appendChild(container);
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('creates player with play button, waveform, and speed chip', () => {
        const player = createWaveformPlayer(container, { language: 'es', text: 'Hola' });
        expect(container.querySelector('.voice-wf-play')).not.toBeNull();
        expect(container.querySelector('.voice-wf-wave')).not.toBeNull();
        expect(container.querySelector('.voice-wf-speed')).not.toBeNull();
    });

    it('speed chip cycles through options on click', () => {
        const player = createWaveformPlayer(container, { language: 'es', text: 'Hola' });
        const speedChip = container.querySelector('.voice-wf-speed');
        expect(speedChip.textContent.trim()).toBe('1×');
        speedChip.click();
        expect(speedChip.textContent.trim()).toBe('1.25×');
        speedChip.click();
        expect(speedChip.textContent.trim()).toBe('1.5×');
        speedChip.click();
        expect(speedChip.textContent.trim()).toBe('0.75×');
        speedChip.click();
        expect(speedChip.textContent.trim()).toBe('1×');
    });

    it('destroyWaveformPlayer cleans up wavesurfer instance', () => {
        const player = createWaveformPlayer(container, { language: 'es', text: 'Hola' });
        destroyWaveformPlayer(player);
        // wavesurfer.destroy() should have been called
    });
});
```

**Step 2: Run tests to verify they fail**

```bash
npx vitest run tests/js/voice-waveform.test.js --reporter=verbose 2>&1 | tail -20
```

**Step 3: Implement voice-waveform.js**

Create `src/static/js/modules/voice-waveform.js`:

```javascript
/**
 * Habla Hermano — Voice Waveform Player
 * Phase 22: Wavesurfer.js wrapper for AI message TTS waveforms.
 *
 * Creates/destroys waveform player instances per AI message.
 * Each player: play/pause button + wavesurfer waveform + speed chip + time display.
 */
import WaveSurfer from 'wavesurfer.js';

export var SPEED_OPTIONS = [0.75, 1, 1.25, 1.5];

var PLAY_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
var PAUSE_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>';

/**
 * Create a waveform player inside the given container.
 * @param {HTMLElement} container - the .voice-waveform-container element
 * @param {Object} opts - { language, text }
 * @returns {Object} player handle with { ws, play, pause, destroy, loadBlob, container }
 */
export function createWaveformPlayer(container, opts) {
    // Build DOM structure
    var wrapper = document.createElement('div');
    wrapper.className = 'voice-wf-player';

    // Play/pause button
    var playBtn = document.createElement('button');
    playBtn.type = 'button';
    playBtn.className = 'voice-wf-play';
    playBtn.innerHTML = PLAY_ICON;
    playBtn.setAttribute('aria-label', 'Play audio');

    // Waveform div (wavesurfer mounts here)
    var waveDiv = document.createElement('div');
    waveDiv.className = 'voice-wf-wave';

    // Speed chip
    var speedIdx = 1; // default 1× (index into SPEED_OPTIONS)
    var speedChip = document.createElement('button');
    speedChip.type = 'button';
    speedChip.className = 'voice-wf-speed';
    speedChip.textContent = '1\u00d7'; // 1×
    speedChip.setAttribute('aria-label', 'Playback speed');

    // Time display
    var timeEl = document.createElement('div');
    timeEl.className = 'voice-wf-time';
    timeEl.textContent = '0:00';

    var topRow = document.createElement('div');
    topRow.className = 'voice-wf-top';
    topRow.appendChild(playBtn);
    topRow.appendChild(waveDiv);
    topRow.appendChild(speedChip);

    wrapper.appendChild(topRow);
    wrapper.appendChild(timeEl);
    container.appendChild(wrapper);

    // CSS variables for theme
    var accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#60a5fa';
    var subtle = getComputedStyle(document.documentElement).getPropertyValue('--text-subtle').trim() || '#9ca3af';

    // Create wavesurfer instance
    var ws = WaveSurfer.create({
        container: waveDiv,
        waveColor: subtle + '66', // 40% opacity
        progressColor: accent,
        cursorWidth: 0,
        barWidth: 2,
        barGap: 1,
        barRadius: 2,
        height: 32,
        normalize: true,
        interact: true,
    });

    // Format time helper
    function formatTime(sec) {
        var m = Math.floor(sec / 60);
        var s = Math.floor(sec % 60);
        return m + ':' + (s < 10 ? '0' : '') + s;
    }

    // Playback events
    ws.on('ready', function() {
        timeEl.textContent = formatTime(ws.getDuration());
    });

    ws.on('audioprocess', function() {
        timeEl.textContent = formatTime(ws.getCurrentTime()) + ' / ' + formatTime(ws.getDuration());
    });

    ws.on('finish', function() {
        playBtn.innerHTML = PLAY_ICON;
        playBtn.setAttribute('aria-label', 'Play audio');
        timeEl.textContent = formatTime(ws.getDuration());
    });

    // Play/pause toggle
    playBtn.addEventListener('click', function() {
        if (ws.isPlaying()) {
            ws.pause();
            playBtn.innerHTML = PLAY_ICON;
            playBtn.setAttribute('aria-label', 'Play audio');
        } else {
            ws.play();
            playBtn.innerHTML = PAUSE_ICON;
            playBtn.setAttribute('aria-label', 'Pause audio');
        }
    });

    // Speed chip cycle
    speedChip.addEventListener('click', function() {
        speedIdx = (speedIdx + 1) % SPEED_OPTIONS.length;
        var speed = SPEED_OPTIONS[speedIdx];
        speedChip.textContent = speed + '\u00d7';
        ws.setPlaybackRate(speed);
    });

    var handle = {
        ws: ws,
        container: container,
        opts: opts,
        playBtn: playBtn,
        speedChip: speedChip,
        play: function() { ws.play(); playBtn.innerHTML = PAUSE_ICON; },
        pause: function() { ws.pause(); playBtn.innerHTML = PLAY_ICON; },
        loadBlob: function(blob) { ws.loadBlob(blob); },
        destroy: function() { ws.destroy(); },
    };

    return handle;
}

/**
 * Destroy a waveform player and clean up.
 */
export function destroyWaveformPlayer(handle) {
    if (!handle) return;
    if (handle.ws) handle.ws.destroy();
}
```

**Step 4: Run tests**

```bash
npx vitest run tests/js/voice-waveform.test.js --reporter=verbose 2>&1 | tail -20
```

**Step 5: Commit**

```bash
git add src/static/js/modules/voice-waveform.js tests/js/voice-waveform.test.js
git commit -m "feat(voice): add voice-waveform.js module wrapping wavesurfer.js"
```

---

## Task 5: Waveform Player CSS

Add styles for the waveform player component and the loading shimmer placeholder.

**Files:**
- Modify: `src/templates/base.html` (add waveform player CSS)

**Step 1: Add waveform player CSS**

In `src/templates/base.html`, in the `<style>` section, add:

```css
/* Waveform player on AI messages */
.voice-wf-player {
    padding: 8px 12px;
    background-color: var(--surface-overlay);
    border: 1px solid var(--border);
    border-radius: 12px 12px 0 0;
    border-bottom: none;
}

.voice-wf-top {
    display: flex;
    align-items: center;
    gap: 8px;
}

.voice-wf-play {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: none;
    border: none;
    color: var(--accent);
    cursor: pointer;
    transition: background-color 0.15s ease;
}
.voice-wf-play:hover {
    background-color: color-mix(in srgb, var(--accent) 10%, transparent);
}

.voice-wf-wave {
    flex: 1;
    height: 32px;
    min-width: 0;
}

.voice-wf-speed {
    flex-shrink: 0;
    padding: 2px 8px;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-subtle);
    background-color: var(--surface-elevated);
    border: 1px solid var(--border);
    border-radius: 999px;
    cursor: pointer;
    transition: color 0.15s ease, border-color 0.15s ease;
    font-variant-numeric: tabular-nums;
}
.voice-wf-speed:hover {
    color: var(--accent);
    border-color: var(--accent);
}

.voice-wf-time {
    font-size: 0.6875rem;
    color: var(--text-subtle);
    text-align: right;
    padding-top: 4px;
    font-variant-numeric: tabular-nums;
}

/* Loading shimmer before audio ready */
.voice-wf-loading {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 32px;
    padding: 0 4px;
}
.voice-wf-loading-dot {
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background-color: var(--text-subtle);
    opacity: 0.3;
    animation: wfShimmer 1.4s ease-in-out infinite;
}
.voice-wf-loading-dot:nth-child(2) { animation-delay: 0.2s; }
.voice-wf-loading-dot:nth-child(3) { animation-delay: 0.4s; }
.voice-wf-loading-dot:nth-child(4) { animation-delay: 0.6s; }
.voice-wf-loading-dot:nth-child(5) { animation-delay: 0.8s; }

@keyframes wfShimmer {
    0%, 100% { opacity: 0.3; transform: scaleY(1); }
    50% { opacity: 0.8; transform: scaleY(2.5); }
}

@media (prefers-reduced-motion: reduce) {
    .voice-wf-loading-dot { animation: none; opacity: 0.5; }
}
```

**Step 2: Commit**

```bash
git add src/templates/base.html
git commit -m "feat(voice): add waveform player and loading shimmer CSS"
```

---

## Task 6: AI Message Waveform Integration

Replace the speaker icon button on AI messages with the waveform player container. Wire up TTS to collect audio as a blob and feed it to wavesurfer.

**Files:**
- Modify: `src/templates/partials/message.html` (replace speaker button with waveform container)
- Modify: `src/static/js/modules/voice-tts.js` (collect audio blob during streaming)
- Modify: `src/static/js/modules/voice.js` (wire waveform player into TTS flow)
- Test: `tests/js/voice.test.js`

**Step 1: Write failing tests**

In `tests/js/voice.test.js`, add:

```javascript
describe('AI Message Waveform Player', () => {
    it('creates waveform player when play is triggered on a message', () => {
        // Create a mock message container
        var msgContainer = document.createElement('div');
        msgContainer.className = 'voice-waveform-container';
        msgContainer.dataset.text = 'Hola mundo';
        msgContainer.dataset.language = 'es';
        document.body.appendChild(msgContainer);

        // Trigger play
        msgContainer.querySelector('.voice-wf-play').click();
        // Player should exist
        expect(msgContainer.querySelector('.voice-wf-player')).not.toBeNull();
    });
});
```

**Step 2: Run to verify fail**

```bash
npx vitest run tests/js/voice.test.js --reporter=verbose 2>&1 | tail -20
```

**Step 3: Update message.html**

Replace the speaker button (lines ~29-42 of `src/templates/partials/message.html`) with:

```html
{% if voice_enabled and not is_user %}
<div class="voice-waveform-container"
     data-text="{{ ai_response | e }}"
     data-language="{{ language }}">
    <!-- Waveform player created by JS on first play -->
    <div class="voice-wf-player">
        <div class="voice-wf-top">
            <button type="button" class="voice-wf-play" aria-label="Play audio">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            </button>
            <div class="voice-wf-wave">
                <div class="voice-wf-loading" aria-hidden="true">
                    <span class="voice-wf-loading-dot"></span>
                    <span class="voice-wf-loading-dot"></span>
                    <span class="voice-wf-loading-dot"></span>
                    <span class="voice-wf-loading-dot"></span>
                    <span class="voice-wf-loading-dot"></span>
                </div>
            </div>
            <button type="button" class="voice-wf-speed" aria-label="Playback speed">1×</button>
        </div>
        <div class="voice-wf-time">0:00</div>
    </div>
</div>
{% endif %}
```

**Step 4: Modify voice-tts.js to collect audio blob**

In `streamTTS()` (lines 50-175 of voice-tts.js), the audio is currently played directly from AudioBufferSourceNodes and discarded. We need to also accumulate the raw PCM chunks into an array and, after playback completes, assemble them into a WAV blob.

Add at the top of `streamTTS()`:

```javascript
var audioChunks = []; // collect PCM chunks for waveform
```

In the WebSocket `onmessage` handler where `data instanceof ArrayBuffer`, after converting to Float32, also push the chunk:

```javascript
audioChunks.push(new Float32Array(pcmData));
```

Add a new exported helper to assemble chunks into a WAV blob:

```javascript
/**
 * Assemble Float32 PCM chunks into a WAV Blob for wavesurfer.
 */
export function assembleWavBlob(chunks, sampleRate) {
    var totalLength = chunks.reduce(function(sum, c) { return sum + c.length; }, 0);
    var merged = new Float32Array(totalLength);
    var offset = 0;
    for (var i = 0; i < chunks.length; i++) {
        merged.set(chunks[i], offset);
        offset += chunks[i].length;
    }
    // WAV header
    var buffer = new ArrayBuffer(44 + merged.length * 2);
    var view = new DataView(buffer);
    function writeString(o, s) { for (var j = 0; j < s.length; j++) view.setUint8(o + j, s.charCodeAt(j)); }
    writeString(0, 'RIFF');
    view.setUint32(4, 36 + merged.length * 2, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM
    view.setUint16(22, 1, true); // mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(36, 'data');
    view.setUint32(40, merged.length * 2, true);
    for (var k = 0; k < merged.length; k++) {
        var s = Math.max(-1, Math.min(1, merged[k]));
        view.setInt16(44 + k * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return new Blob([buffer], { type: 'audio/wav' });
}
```

After playback finishes (in the `ALL_ENDED` path), expose the blob via a callback:

```javascript
// At the end of streamTTS, when sending ALL_ENDED:
var wavBlob = assembleWavBlob(audioChunks, sampleRate);
if (typeof onAudioReady === 'function') onAudioReady(wavBlob);
```

Update `streamTTS` signature to accept `onAudioReady` callback.

**Step 5: Wire waveform into voice.js**

In `handleSpeakClick()` (voice.js), when calling `streamTTS()`, pass an `onAudioReady` callback that:

1. Finds the `.voice-waveform-container` for the clicked button
2. Calls `createWaveformPlayer()` (or gets existing handle)
3. Calls `player.loadBlob(wavBlob)` to render the waveform

In `onTtsChange()`, when entering `playing`, replace the old icon manipulation with waveform player state updates.

**Step 6: Update event delegation**

In `initVoice()`, update the click delegation (line ~255) to handle `.voice-wf-play` clicks instead of `.voice-speak-btn`:

```javascript
document.addEventListener('click', function(e) {
    var playBtn = e.target.closest('.voice-wf-play');
    if (playBtn) {
        var container = playBtn.closest('.voice-waveform-container');
        if (container) handleSpeakClick(container);
    }
});
```

Update `handleSpeakClick()` to accept a container element instead of a button, and read `data-text` and `data-language` from the container.

**Step 7: Run tests**

```bash
npx vitest run tests/js/voice.test.js --reporter=verbose 2>&1 | tail -30
npx vitest run tests/js/voice-waveform.test.js --reporter=verbose 2>&1 | tail -20
```

**Step 8: Commit**

```bash
git add src/templates/partials/message.html src/static/js/modules/voice-tts.js src/static/js/modules/voice.js src/static/js/modules/voice-waveform.js tests/js/voice.test.js
git commit -m "feat(voice): waveform player on AI messages with wavesurfer.js"
```

---

## Task 7: Stop Bar Redesign

Restyle the stop bar with animate.css transitions.

**Files:**
- Modify: `src/static/js/modules/voice-ui.js` (update createStopBar/removeStopBar)
- Modify: `src/templates/base.html` (update stop bar CSS)
- Test: `tests/js/voice.test.js`

**Step 1: Update createStopBar in voice-ui.js**

Modify `createStopBar()` (around line 184) to use animate.css classes:

```javascript
export function createStopBar(onStop) {
    var bar = document.createElement('div');
    bar.className = 'voice-stop-bar animate__animated animate__fadeInUp animate__faster';
    // ... rest of current implementation ...
    return bar;
}
```

Modify `removeStopBar()` to animate out:

```javascript
export function removeStopBar(bar) {
    if (!bar || !bar.parentNode) return;
    bar.classList.remove('animate__fadeInUp');
    bar.classList.add('animate__fadeOutDown');
    bar.addEventListener('animationend', function() {
        if (bar.parentNode) bar.parentNode.removeChild(bar);
    }, { once: true });
}
```

**Step 2: Run tests**

```bash
npx vitest run tests/js/voice.test.js --reporter=verbose 2>&1 | tail -20
```

**Step 3: Commit**

```bash
git add src/static/js/modules/voice-ui.js src/templates/base.html tests/js/voice.test.js
git commit -m "feat(voice): animate stop bar with fadeInUp/fadeOutDown"
```

---

## Task 8: Remove Old Voice UI Elements

Clean up deprecated voice UI: old speaker button styles, old level bars, old timer pill, old processing spinner floater, header speed picker.

**Files:**
- Modify: `src/templates/base.html` (remove old voice CSS)
- Modify: `src/templates/chat.html` (remove speed picker from header)
- Modify: `src/static/js/modules/voice-ui.js` (remove deprecated functions)
- Modify: `src/static/js/modules/voice-constants.js` (remove old SPEAKER_ICON, SPEAKER_PLAYING_ICON)
- Test: `tests/js/voice.test.js`

**Step 1: Identify and remove old CSS classes**

From `base.html`, remove or mark as deprecated:
- `.voice-speak-btn`, `.voice-speak-btn.voice-loading`, `.voice-speak-btn.voice-playing`
- `.voice-level-bars`, `.voice-bar` (old 4-bar level indicator)
- `.voice-timer`, `.voice-timer::before` (old floating timer pill)
- `.voice-processing-indicator`

Keep: `.voice-recording` keyframe (still used by recording bar dot), `.voice-spinner` (still used in processing).

**Step 2: Remove speed picker from chat.html**

Remove the `#tts-speed-picker` div and related Alpine.js `x-data` (lines ~370-390 of chat.html). Speed is now per-waveform.

**Step 3: Remove deprecated functions from voice-ui.js**

Remove: `showMicRecording()`, `restoreMicIcon()`, `startTimer()`, `stopTimer()`, `startLevelAnimation()`, `showProcessing()`, `hideProcessing()`.

Keep: `setSendEnabled()`, `showTooltipError()`, `createStopBar()`, `removeStopBar()`, and the new functions from Tasks 2-3.

**Step 4: Remove old icon constants**

From `voice-constants.js`, remove `SPEAKER_ICON` and `SPEAKER_PLAYING_ICON` (no longer used — waveform player has its own icons). Keep `MIC_ICON` and `STOP_ICON`.

**Step 5: Update voice.js imports**

Remove imports of deleted functions. Update `onSttChange` and `onTtsChange` to only use new functions.

**Step 6: Update tests**

Remove/update tests that reference old UI elements. Ensure all remaining tests pass.

**Step 7: Run full test suite**

```bash
npx vitest run --reporter=verbose 2>&1 | tail -40
```

**Step 8: Commit**

```bash
git add -A
git commit -m "refactor(voice): remove deprecated voice UI elements and speed picker"
```

---

## Task 9: Integration Testing & Polish

Manual testing across browsers and final polish pass.

**Step 1: Run full JS test suite**

```bash
npx vitest run --reporter=verbose 2>&1 | tail -40
```

All tests must pass.

**Step 2: Run Python tests (ensure no regressions)**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -20
```

**Step 3: Manual browser testing checklist**

- [ ] Empty input shows mic button, typing shows send button
- [ ] Tap mic → recording bar appears with timer and waveform
- [ ] Tap stop → processing → transcript sends
- [ ] Tap cancel → recording bar slides out, input returns
- [ ] AI message shows waveform player with loading dots
- [ ] Tap play → audio streams, waveform renders, progress sweeps
- [ ] Tap pause → pauses, tap again → resumes
- [ ] Tap speed chip → cycles 1× → 1.25× → 1.5× → 0.75× → 1×
- [ ] Tap play on different message → current stops, new plays
- [ ] Stop bar appears during playback, dismiss works
- [ ] All 4 themes render correctly (Azulejo, Terracotta, Flamenco, Sangria)
- [ ] Mobile: touch targets adequate, no gesture conflicts
- [ ] prefers-reduced-motion: animations disabled
- [ ] Lesson chat mode: same behavior as regular chat

**Step 4: Fix any issues found**

Address bugs from manual testing.

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat(voice): Phase 22 voice UX redesign complete"
```

---

## Task Summary

| Task | Description | Est. Complexity |
|------|-------------|-----------------|
| 1 | Install dependencies | Low |
| 2 | Mic/send button swap | Medium |
| 3 | Recording bar UI | High |
| 4 | Waveform player module | High |
| 5 | Waveform player CSS | Low |
| 6 | AI message waveform integration | High |
| 7 | Stop bar redesign | Low |
| 8 | Remove old voice UI | Medium |
| 9 | Integration testing & polish | Medium |
