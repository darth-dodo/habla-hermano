# Phase 16: ES Module JavaScript Refactor

> Restructure JavaScript from IIFE + window globals to native ES modules with explicit import/export, eliminating implicit cross-file coupling.

---

## Overview

Phase 16 refactors the JavaScript architecture from two monolithic IIFE files communicating via `window.*` globals into a modular ES module structure with explicit dependencies. This is motivated by two production bugs discovered during E2E testing (Phase 15) — both caused by the fragile implicit coupling between `app.js` and `stream.js`.

**Business Value**: Eliminates an entire class of integration bugs (missing exports, load-order dependencies) that are invisible to unit tests and only surface in real browser testing. Future JS development becomes safer and more maintainable.

**ADR Reference**: [ADR-009: ES Module JavaScript Refactor](../adr/ADR-009-es-module-javascript-refactor.md)

---

## Design Decisions

### Native ES Modules Without a Build Step

The refactor uses `<script type="module">` which all target browsers support natively (since 2018, 97%+ global coverage). No bundler, transpiler, or Node.js tooling is introduced. This preserves the ADR-003 constraint: "No JavaScript build step required."

#### Why Not a Bundler

A bundler (Vite, esbuild) would add Node.js as a dependency, `package.json`, `node_modules/`, and a build step to a Python-first project that currently has zero JS build tooling. The total JS surface is ~730 lines across 6 modules — bundling provides negligible benefit at this scale.

#### Why Not TypeScript

TypeScript requires compilation. The type complexity is low (DOM elements, strings, FormData, fetch Response). The bugs that motivated this refactor (missing window export, `\r\n` parsing) would not be caught by TypeScript's type system. JSDoc type annotations provide IDE autocomplete without a compiler.

### Module Decomposition Strategy

The current two files are split along **responsibility boundaries**, not arbitrary size limits:

| Module | Responsibility | Lines (approx) |
|--------|---------------|-----------------|
| `dom.js` | Shared DOM utilities, element refs, HTML escaping | ~80 |
| `stream.js` | SSE streaming client, bubble management | ~200 |
| `shortcuts.js` | Keyboard shortcuts | ~40 |
| `scaffold.js` | Word bank & sentence starter insertion | ~50 |
| `htmx-handlers.js` | HTMX event handlers, new conversation | ~80 |
| `main.js` | Entry point, initialization, window exports | ~40 |

**Total**: ~490 lines (down from 731 — dead code removed)

### Window Exports for Inline HTML Handlers

A small number of functions must remain on `window` because they're called from inline HTML attributes:

```html
<!-- Alpine.js / inline onclick in Jinja2 templates -->
<button onclick="insertWord('hola')">hola</button>
<button onclick="insertStarter('Yo quiero')">Yo quiero...</button>
```

These are exposed in `main.js` as a well-documented, minimal surface:

```javascript
// Explicit window exports for inline HTML handlers only
window.insertWord = insertWord;
window.insertStarter = insertStarter;
```

This is the **only** place `window.*` assignment occurs, making it easy to audit and maintain.

---

## Module Architecture

### Dependency Graph

```
main.js (entry point)
├── import { initDOM, scrollToBottom, focusInput, ... } from './modules/dom.js'
├── import { initStreamingForm } from './modules/stream.js'
│   └── import { scrollToBottom, focusInput, clearInput, addUserMessage, escapeHtml } from './dom.js'
├── import { initKeyboardShortcuts } from './modules/shortcuts.js'
│   └── import { focusInput } from './dom.js'
├── import { insertWord, insertStarter } from './modules/scaffold.js'
│   └── import { getMessageInput } from './dom.js'
└── import { initHTMXHandlers } from './modules/htmx-handlers.js'
    └── import { scrollToBottom, hideLoading } from './dom.js'
```

### Module Specifications

#### `modules/dom.js` — Shared DOM Utilities

The foundation module. Every other module imports from here. No external dependencies.

**Exports**:
```javascript
// Element accessors
export function getChatContainer()    // #chat-container
export function getChatMessages()     // #chat-messages
export function getMessageInput()     // #message-input
export function getChatForm()         // #chat-form
export function getLoadingIndicator() // #loading-indicator

// Utility functions
export function scrollToBottom(smooth = true)
export function focusInput()
export function clearInput()
export function showLoading()
export function hideLoading()
export function addUserMessage(message)
export function escapeHtml(text)
```

**Design Notes**:
- Element accessors are functions (not cached refs) because elements may not exist on every page — `getChatMessages()` returns `null` on `/lessons/` pages
- `scrollToBottom` uses the existing `setTimeout` + `scrollTo` pattern with configurable smooth scrolling
- `escapeHtml` uses the existing `textContent`/`innerHTML` technique (safe, no regex)

#### `modules/stream.js` — SSE Streaming Client

Handles the `POST /chat/stream` fetch, SSE parsing, bubble management, and token rendering.

**Exports**:
```javascript
export function initStreamingForm()  // Attaches submit handler to #chat-form
```

**Internal functions** (not exported):
- `parseSSEEvent(eventStr)` — Parse raw SSE text into `{event, data}`
- `createStreamingBubble()` — Create empty AI response bubble with cursor
- `appendToken(bubbleId, content)` — Append text before cursor
- `finalizeBubble(bubbleId)` — Remove cursor
- `insertFeedback(bubbleId, html)` — Insert scaffolding/grammar/pronunciation HTML
- `handleStreamEvent(event, dataStr, bubbleId)` — Event dispatcher
- `streamChat(formData)` — Core streaming function
- `finishStreaming()` — Re-enable input
- `showStreamError(message)` — Error display

**Imports from dom.js**:
```javascript
import { getChatMessages, scrollToBottom, focusInput, clearInput, addUserMessage, escapeHtml } from './dom.js';
```

**Key change from current code**: The `\r\n` normalization (Bug 2 fix) is retained: `buffer = buffer.replace(/\r\n/g, '\n')` before splitting on `\n\n`.

#### `modules/shortcuts.js` — Keyboard Shortcuts

All keyboard event handlers in one place.

**Exports**:
```javascript
export function initKeyboardShortcuts()  // Attaches keydown handler to document
```

**Shortcuts**:
- `Cmd/Ctrl + Enter` — Submit chat form
- `Cmd/Ctrl + Shift + N` — New conversation
- `Escape` — Blur input
- `/` — Focus input (when not in input field)

**Imports from dom.js**:
```javascript
import { getMessageInput, getChatForm, focusInput } from './dom.js';
```

#### `modules/scaffold.js` — Word Bank & Sentence Starters

Handles click-to-insert behavior for scaffolding UI elements.

**Exports**:
```javascript
export function insertWord(word)       // Insert word at cursor position
export function insertStarter(starter) // Replace input with sentence starter
```

**Imports from dom.js**:
```javascript
import { getMessageInput } from './dom.js';
```

**Note**: These functions are also exposed on `window` via `main.js` because they're called from inline `onclick` handlers in server-rendered scaffolding HTML.

#### `modules/htmx-handlers.js` — HTMX Event Handlers

Handles HTMX lifecycle events for non-chat interactions (lessons, progress, new conversation).

**Exports**:
```javascript
export function initHTMXHandlers()  // Attaches all HTMX event listeners
```

**Internal functions**:
- `onAfterSwap(event)` — Scroll + animate after HTMX content swap
- `onResponseError(event)` — Display error message on HTMX failure
- `onNewConversationRequest(event)` — Handle `/new` conversation button
- `handleNewConversation()` — Visual feedback during redirect

**Cleanup from current code**:
- **Removed**: `onBeforeRequest()` — was just `if (event.detail.elt.id === 'chat-form') return;`
- **Removed**: `onAfterRequest()` — was just `if (event.detail.elt.id === 'chat-form') return;`
- These were dead handlers since Phase 15 moved chat away from HTMX

**Imports from dom.js**:
```javascript
import { getChatMessages, getMessageInput, scrollToBottom, hideLoading, escapeHtml } from './dom.js';
```

#### `main.js` — Entry Point

The single entry point loaded by `<script type="module">`. Wires everything together and handles initialization.

```javascript
import { scrollToBottom, focusInput } from './modules/dom.js';
import { initStreamingForm } from './modules/stream.js';
import { initKeyboardShortcuts } from './modules/shortcuts.js';
import { insertWord, insertStarter } from './modules/scaffold.js';
import { initHTMXHandlers } from './modules/htmx-handlers.js';

// ============================================
// Window exports for inline HTML handlers
// ============================================
// These functions are called from onclick="" attributes in
// server-rendered scaffolding HTML. They MUST be on window.
window.insertWord = insertWord;
window.insertStarter = insertStarter;

// ============================================
// Initialization
// ============================================
function init() {
    initHTMXHandlers();
    initStreamingForm();
    initKeyboardShortcuts();

    // Initial state
    scrollToBottom(false);
    focusInput();

    console.log('Habla Hermano initialized');
}

// Module scripts are deferred by default, so DOM is ready.
// But check just in case of dynamic injection.
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// ============================================
// Virtual Keyboard Handling
// ============================================
if ('visualViewport' in window) {
    window.visualViewport.addEventListener('resize', () => {
        const chatContainer = document.getElementById('chat-container');
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    });
}
```

---

## Template Changes

### base.html Script Section

**Before** (current):
```html
<!-- Custom JavaScript -->
<script src="{{ url_for('static', path='js/app.js') }}"></script>
<script src="{{ url_for('static', path='js/stream.js') }}"></script>

{% block scripts %}{% endblock %}
```

**After**:
```html
<!-- Custom JavaScript (ES Modules) -->
<script type="module" src="{{ url_for('static', path='js/main.js') }}"></script>

{% block scripts %}{% endblock %}
```

**Key behavior change**: `type="module"` scripts are automatically `defer`ed — they execute after DOM parsing completes. This means the `DOMContentLoaded` check in `main.js` is technically redundant but kept as a safety net.

### Compatibility Notes

- **HTMX** (`<script src="htmx.min.js">`): Classic script, unaffected. Loaded before modules.
- **Alpine.js** (`<script defer src="alpine.min.js">`): Already deferred. Will initialize after module scripts.
- **Inline handlers**: `onclick="insertWord('hola')"` works because `main.js` exposes these on `window` during initialization.

---

## File Structure

### Before
```
src/static/js/
├── app.js      (380 lines)
└── stream.js   (351 lines)
```

### After
```
src/static/js/
├── main.js                    (~40 lines)  Entry point
└── modules/
    ├── dom.js                 (~80 lines)  Shared DOM utilities
    ├── stream.js              (~200 lines) SSE streaming client
    ├── shortcuts.js           (~40 lines)  Keyboard shortcuts
    ├── scaffold.js            (~50 lines)  Word bank & starters
    └── htmx-handlers.js       (~80 lines)  HTMX event handlers
```

**Net change**: 731 lines → ~490 lines (241 lines removed: dead code, IIFE boilerplate, duplicated DOM lookups)

---

## Dead Code Removal

The following code is removed during the refactor:

| Code | File | Reason |
|------|------|--------|
| `onBeforeRequest()` | app.js:131-134 | Only checks `if chat-form return` — chat no longer uses HTMX |
| `onAfterRequest()` | app.js:140-143 | Same — dead since Phase 15 |
| IIFE wrappers | both files | ES modules have their own scope — no IIFE needed |
| `'use strict'` declarations | both files | ES modules are strict by default |
| `document.readyState` checks | both files | Consolidated into single check in `main.js` |
| Duplicate `getElements()` pattern | app.js | Replaced by shared `dom.js` accessor functions |

---

## Testing Strategy

### Automated Validation

1. **Existing pytest suite** (1854 tests): Unaffected — tests the Python backend, not JS
2. **E2E via Playwright**: All 7 flows must pass:
   - Flow 1: Chat page initial load
   - Flow 2: Level selector
   - Flow 3: Lessons catalog
   - Flow 4: Hamburger menu
   - Flow 5: Progress empty state
   - Flow 6: Lesson player (full walkthrough)
   - Flow 7: Chat with SSE streaming + scaffolding

### Manual Verification

- Console: Zero errors on page load and during all interactions
- Network: Verify all `.js` module files load with `200 OK`
- Functionality: Word bank insert, sentence starter, keyboard shortcuts

### Browser Compatibility

No compatibility testing needed beyond the existing target (modern evergreen browsers). `<script type="module">` has been supported since:
- Chrome 61 (Sep 2017)
- Firefox 60 (May 2018)
- Safari 11 (Sep 2017)
- Edge 16 (Oct 2017)

---

## Rollback Plan

1. Revert `base.html` to load `app.js` + `stream.js` as classic scripts
2. The old files remain in git history — `git checkout HEAD~1 -- src/static/js/app.js src/static/js/stream.js`
3. Delete the `modules/` directory and `main.js`
4. Total rollback time: < 2 minutes

---

## Migration Checklist

- [ ] Create `src/static/js/modules/` directory
- [ ] Write `modules/dom.js` — extract shared utilities from `app.js`
- [ ] Write `modules/stream.js` — migrate from `stream.js` IIFE, add dom.js imports
- [ ] Write `modules/shortcuts.js` — extract from `app.js`
- [ ] Write `modules/scaffold.js` — extract from `app.js`
- [ ] Write `modules/htmx-handlers.js` — extract from `app.js`, remove dead handlers
- [ ] Write `main.js` — entry point with init and window exports
- [ ] Update `base.html` — single `<script type="module">` tag
- [ ] Run E2E flows 1-7 via Playwright
- [ ] Verify zero console errors
- [ ] Remove old `app.js` and `stream.js`
- [ ] Update MEMORY.md with new JS architecture
