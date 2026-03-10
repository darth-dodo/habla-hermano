# Phase 22: Voice UX Redesign (Telegram-style)

## Goal

Replace the utilitarian voice UI with a polished, Telegram-inspired experience. Tap-to-toggle recording with an animated recording bar, wavesurfer.js waveform players on AI messages, and animate.css transitions throughout.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Gesture model | Tap-to-toggle (not hold-to-record) | Full Telegram gestures too risky on vanilla JS + HTMX stack; tap model reuses existing FSM |
| User voice messages | Transcript as text bubble (current) | AI tutor needs text for correction; waveform bubble adds no value for STT |
| AI TTS display | Waveform player above text | Voice-native feel; users can seek, replay, adjust speed per-message |
| Speed control | Per-message chip on waveform | Replaces global header picker; contextual and discoverable |
| Waveform library | wavesurfer.js (~30KB gzip) | Battle-tested, ESM, barWidth/barGap rendering, loadBlob(), setPlaybackRate() |
| Animation library | animate.css (~16KB gzip, CDN) | Cross-browser, prefers-reduced-motion support, slideIn/fadeIn/pulse utilities |

## Recording Input

### Button Swap

Mic button shows when input is empty, send button shows when input has text. Crossfade via `fadeIn`/`fadeOut` (`animate__faster`, 500ms).

```
[  Type a message...              ] [mic]    -- empty: mic button
[  Hola, como estas?              ] [send]   -- has text: send button
```

### Recording States

**Idle -> Recording** (tap mic):

```
+----------------------------------------------+
|  [x]    * 0:03    ||||||||||||||||||||        |  -- replaces input bar
+----------------------------------------------+
                                          [stop]  -- stop button (square icon)
```

- Input bar morphs into recording bar (`fadeIn animate__faster`)
- Cancel [x] on left, red dot + timer center, live waveform bars right
- Mic button morphs into stop button (square icon)
- Background shifts to subtle red tint

**Recording -> Processing** (tap stop):

- Brief spinner (2s auto-dismiss, `pulse animate__fast`)
- Recording bar morphs back to input bar
- Transcript populates input, auto-sends

**Cancel** (tap x):

- Recording bar: `slideOutLeft animate__faster`
- Input bar returns: `slideInRight animate__faster`
- No transcript, back to idle

### Live Waveform Bars

Driven by AnalyserNode (current audio pipeline). Bars rendered as thin rounded rectangles, animated at ~60fps via requestAnimationFrame. Replaces old level bars with wider visualization inside the recording bar.

## AI Message Waveform Player

### Layout

Each AI message renders a waveform player above the text content:

```
+-------------------------------------+
|  >  |..||||.||||||.||||..|||.|  1x  |  -- wavesurfer.js waveform
|     0:00 ---------------- 0:08      |  -- current time / duration
+-------------------------------------+
|  Hola, como estas hoy? Me alegra    |  -- text response (always visible)
|  mucho verte de nuevo.              |
+-------------------------------------+
```

### Waveform Player Elements

- **Play/pause button** (triangle/bars) on the left
- **Waveform bar** via wavesurfer.js (barWidth: 2, barGap: 1, barRadius: 2, height: 32)
- **Speed chip** on the right -- current rate (1x), tap to cycle: 0.75x -> 1x -> 1.25x -> 1.5x
- **Time display** below waveform: current position / total duration

### Colors (theme-aware)

- Waveform unplayed: `var(--text-subtle)` at 40% opacity
- Waveform played (progress): `var(--accent)`
- Play button: `var(--accent)`
- Speed chip: `var(--text-subtle)` text, `var(--surface-overlay)` background

### Behavior

- Tap play: TTS streams via WebSocket, wavesurfer renders waveform from assembled audio blob, progress sweeps as it plays
- Tap pause: Pauses mid-stream, tap again to resume
- Tap speed chip: Cycles speed, applies immediately via `setPlaybackRate()`
- Tap waveform: Seek to position
- Another message play tapped: Current stops, new starts

### Loading State

Before audio is ready (during WebSocket stream):

```
+-------------------------------------+
|  >  | . . . . . . . . . . . . . |  |  -- shimmer/pulse placeholder
+-------------------------------------+
```

### When TTS Not Available

Waveform section does not render. Text-only bubble as today.

## Stop Bar

Appears above input area during TTS playback:

```
+----------------------------------------------+
|          pause  Now playing...  [stop]        |  -- fadeInUp animate__faster
+----------------------------------------------+
[  Type a message...              ] [mic]
```

- `fadeInUp` on appear, `fadeOutDown` on dismiss
- Stop button cancels TTS, removes bar

## Interaction Priority

- Recording takes precedence: tapping mic while TTS plays stops TTS first, then starts recording
- New TTS cancels old: tapping play on different message stops current one

## Animation Map (animate.css)

| Transition | Class | Speed |
|-----------|-------|-------|
| Mic <-> send button swap | `fadeIn` / `fadeOut` | `animate__faster` (500ms) |
| Input bar -> recording bar | `fadeIn` | `animate__faster` |
| Recording bar -> cancel | `slideOutLeft` | `animate__faster` |
| Input bar returns after cancel | `slideInRight` | `animate__faster` |
| Processing spinner | `pulse` | `animate__fast` (800ms) |
| Stop button appears | `fadeIn` | `animate__faster` |
| Stop bar appear/dismiss | `fadeInUp` / `fadeOutDown` | `animate__faster` |
| Waveform player appear (new message) | `fadeIn` | `animate__faster` |

## Dependencies

| Package | Size | Delivery | Purpose |
|---------|------|----------|---------|
| wavesurfer.js | ~30KB gzip | npm + ES import | Waveform rendering on AI messages |
| animate.css | ~16KB gzip | CDN `<link>` in `<head>` | UI transition animations |

## Files Changed

| File | Change |
|------|--------|
| `voice-ui.js` | Recording bar DOM, mic/send swap, animate.css class helpers |
| `voice.js` | Updated STT/TTS state handlers for new UI transitions |
| `voice-tts.js` | Collect audio blob for wavesurfer (currently streams and discards) |
| `voice-constants.js` | New icons (stop square, play, pause), remove old speaker icons |
| `chat.html` | Mic/send button swap markup, animate.css CDN link |
| `message.html` | Replace speaker icon with waveform player container |
| `base.html` | New CSS for recording bar, waveform player, stop bar (replaces old voice styles) |
| `voice.test.js` | Update tests for new UI behaviors |

## New File

| File | Purpose |
|------|---------|
| `voice-waveform.js` | Wavesurfer.js wrapper -- create/destroy instances per message, HTMX swap lifecycle |

## What Gets Removed

- Speaker icon button (`.voice-speak-btn`) -> replaced by waveform player
- Level bars (`.voice-level-bars`) -> replaced by recording bar waveform
- Timer pill (`.voice-timer`) -> timer moves inside recording bar
- Processing spinner floater -> processing inline in recording bar
- TTS speed picker in header -> speed chip on each waveform

## Summary

| Component | Before | After |
|-----------|--------|-------|
| Mic input | Static mic button, always visible | Mic/send swap, tap-to-toggle recording bar with waveform + timer |
| AI TTS | Small speaker icon per message | Wavesurfer.js waveform player with play/pause, seek, speed chip |
| Speed control | 3-button picker in header | Per-message speed chip on waveform (tap to cycle) |
| Stop bar | Functional but plain | Restyled with animate.css transitions |
| Animations | Hand-rolled CSS keyframes | animate.css for transitions + custom keyframes for recording pulse |
| New deps | None | wavesurfer.js (30KB) + animate.css (16KB) |
