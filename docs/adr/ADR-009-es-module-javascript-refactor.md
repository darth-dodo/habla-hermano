# ADR-009: ES Module JavaScript Refactor

**Date**: 2026-02-23
**Status**: Proposed
**Context**: Phase 15 complete (SSE Streaming), post-E2E bug discovery
**Decider(s)**: Project Owner

---

## Summary

Refactor the two IIFE-based JavaScript files (`app.js` and `stream.js`) into native ES modules with explicit `import`/`export` statements, eliminating the fragile `window.*` global coupling pattern. No build step is introduced — browsers natively support `<script type="module">`.

---

## Problem Statement

### The Challenge

The current JavaScript architecture uses two IIFEs that communicate via 10 `window.*` global exports. This pattern caused two production bugs discovered during E2E testing:

1. **Bug 1**: `window.addUserMessage` was not exported, causing `TypeError` at runtime — invisible to the 1854 pytest tests
2. **Bug 2**: `\r\n` line ending mismatch in SSE parsing — a cross-concern between `stream.js` and the server's `sse-starlette` library

Both bugs are **integration-level defects** that only manifest in a real browser. The IIFE + `window.*` pattern provides zero compile-time or load-time safety for cross-file dependencies.

### Why This Matters

- **Silent failures**: A missing `window` export produces `undefined` (not an error) until the function is actually called
- **Implicit coupling**: `stream.js` depends on 5 functions from `app.js` but nothing declares this dependency
- **Load-order fragility**: If script tags are reordered in `base.html`, everything breaks silently
- **Growing surface area**: 10 `window` exports across 731 lines — each new feature risks adding more

### Success Criteria

- [ ] All cross-file dependencies use explicit `import`/`export` statements
- [ ] No `window.*` global exports remain for inter-module communication
- [ ] Zero build step required — native ES modules via `<script type="module">`
- [ ] All existing E2E flows pass (chat, lessons, streaming, scaffolding)
- [ ] Dead HTMX handlers cleaned up
- [ ] Shared DOM utilities extracted into a common module

---

## Context

### Current State

**Architecture at Decision Time**:
```
base.html
  ├── <script src="app.js">     ← IIFE, exports 10 functions to window.*
  └── <script src="stream.js">  ← IIFE, reads 5 functions from window.*
```

**Key Characteristics**:

- Two self-contained IIFEs with no formal dependency declaration
- `app.js` (380 lines): DOM utilities, HTMX handlers, keyboard shortcuts, scaffolding helpers
- `stream.js` (351 lines): SSE streaming client, bubble management, error handling
- Cross-file communication exclusively via `window.*` globals
- No build step — raw JS served directly from `src/static/js/`

**Pain Points**:

1. **Missing export caused a production bug** (Bug 1: `window.addUserMessage`)
2. **Dead code accumulation**: HTMX `onBeforeRequest`/`onAfterRequest` handlers contain early-return guards for `chat-form` since Phase 15 moved chat to SSE
3. **Duplicated DOM lookups**: Both files query `chat-messages`, `message-input`, `chat-form`, `loading-indicator` independently
4. **No dependency graph**: Impossible to statically analyze which module needs what

**Technical Constraints**:

- Must work without Node.js or any build tooling (Python-first project)
- Must remain compatible with HTMX, Alpine.js, and existing Jinja2 templates
- Must support the same browser targets (modern evergreen browsers)
- Must preserve `window.*` exports needed by Alpine.js inline handlers (e.g., `onclick="insertWord('hola')"`)

### Requirements

**Functional Requirements**:

1. Chat streaming must continue to work (SSE via fetch + ReadableStream)
2. Keyboard shortcuts must work (Cmd+Enter, Escape, `/` to focus)
3. Scaffolding word bank click-to-insert must work
4. HTMX interactions (lessons, progress, new conversation) must work
5. Alpine.js directives must access necessary functions

**Non-Functional Requirements**:

1. No build step or Node.js dependency
2. No measurable performance regression
3. Clear module boundaries with explicit dependencies
4. Reduced cognitive overhead for future development

---

## Options Considered

### Option 1: Quick Fixes Only (Minimal)

**Description**: Extract shared utilities into `shared.js`, add load-order guards, clean dead code. Keep IIFE pattern.

**Pros**:
- Minimal change, lowest risk
- No template changes needed
- Fastest to implement (~30 min)

**Cons**:
- Does not solve the root cause (implicit `window.*` coupling)
- Load-order bugs remain possible
- Cannot statically analyze dependencies

**Effort**: ~30 minutes
**Risk**: Low

### Option 2: Native ES Modules (Recommended)

**Description**: Restructure into ES modules with explicit `import`/`export`. Use `<script type="module">` in `base.html`. Extract shared utilities into a `dom.js` module.

**Pros**:
- Eliminates entire class of coupling bugs (missing exports become import errors)
- Explicit dependency graph — each module declares what it needs
- Module scoping by default (no IIFE wrappers needed)
- Strict mode automatic
- No build step — native browser support since 2018
- Clean separation of concerns across focused modules

**Cons**:
- Slightly more network requests (one per module file) — negligible at this scale
- `type="module"` scripts are deferred by default (behavior change, but actually beneficial)
- Functions called from inline HTML (`onclick="insertWord()"`) still need `window` exposure
- Requires updating `base.html` script tags

**Effort**: ~2 hours
**Risk**: Low-Medium

### Option 3: Vite/esbuild Build Pipeline

**Description**: Add a lightweight JavaScript bundler. Full ES module support with bundling, minification, tree-shaking, and HMR.

**Pros**:
- All benefits of ES modules plus bundling/minification
- Hot Module Replacement for development
- Tree-shaking eliminates dead code automatically
- Can add TypeScript later with zero friction

**Cons**:
- Introduces Node.js as a development dependency
- Adds `package.json`, `node_modules/`, build scripts
- Build step required before serving (complicates `make dev`)
- Overkill for ~730 lines of JavaScript
- Contradicts ADR-003's explicit "no JavaScript build step" principle

**Effort**: ~4 hours
**Risk**: Medium

### Comparison Matrix

| Criterion (Weight) | Option 1: Quick Fixes | Option 2: ES Modules | Option 3: Build Pipeline |
|---|---|---|---|
| Eliminates coupling bugs (25%) | Partial (3/5) | Full (5/5) | Full (5/5) |
| No build step (20%) | Yes (5/5) | Yes (5/5) | No (1/5) |
| Explicit dependencies (20%) | No (1/5) | Yes (5/5) | Yes (5/5) |
| Implementation effort (15%) | Low (5/5) | Medium (4/5) | High (2/5) |
| Future extensibility (10%) | Low (2/5) | Good (4/5) | Best (5/5) |
| Risk (10%) | Very low (5/5) | Low (4/5) | Medium (3/5) |
| **Weighted Score** | **3.4** | **4.7** | **3.6** |

---

## Decision

**Chosen Option**: Option 2 — Native ES Modules

### Rationale

ES modules solve the **actual problem** (implicit coupling via `window.*` globals) without introducing the **actual risk** (a build pipeline for 730 lines of JS). The pattern that caused Bug 1 becomes structurally impossible — a missing export is an import error at module load time, not a silent `undefined` at call time.

### Key Factors

1. **Root cause elimination**: The IIFE + `window.*` pattern is the root cause of Bug 1. ES modules make cross-file dependencies explicit and fail-fast.
2. **ADR-003 compliance**: ADR-003 explicitly states "No JavaScript build step required." Option 2 preserves this constraint; Option 3 violates it.
3. **Proportional complexity**: 730 lines of JS does not warrant a build pipeline. Native ES modules are the right tool for this scale.
4. **Browser support**: `<script type="module">` is supported by all browsers this project targets (evergreen modern browsers). No polyfill needed.

### Trade-offs Accepted

- Functions called from inline HTML (e.g., Alpine.js `@click` handlers, `onclick` attributes) must still be exposed on `window`. This is a small, well-defined surface (~3 functions: `insertWord`, `insertStarter`, `handleNewConversation`).
- Module scripts are deferred by default, which changes load timing slightly. This is actually beneficial — it guarantees the DOM is ready before modules execute.

---

## Consequences

### Positive Outcomes

1. **Missing export = immediate error**: `import { addUserMessage } from './dom.js'` fails loudly at load time if the export doesn't exist
2. **Dependency graph is visible**: Each file's `import` block shows exactly what it depends on
3. **Module scoping**: No more IIFE boilerplate — modules are scoped by default
4. **Dead code identification**: Unused exports are easy to find with IDE tooling
5. **Cleaner separation**: DOM utilities, streaming, shortcuts, and scaffolding in separate focused modules

### Negative Outcomes

1. **Hybrid global pattern**: A small number of functions still need `window.*` exposure for inline HTML handlers
2. **Additional HTTP requests**: ~5 module files instead of 2, but each is small and HTTP/2 multiplexing makes this negligible

### Technical Debt

- Consider consolidating remaining `window.*` exports by moving inline handlers to Alpine.js `x-on` directives in a future phase
- If JS grows beyond ~2000 lines, revisit Option 3 (build pipeline)

### Risks and Mitigation

**Risk 1**: ES module `import` paths break in production

- **Probability**: Very low (static paths, same server)
- **Impact**: JS fails to load entirely
- **Mitigation**: E2E test suite catches this immediately; rollback is trivial (revert script tags)

**Risk 2**: Inline `onclick` handlers break when IIFEs are removed

- **Probability**: Medium (known surface area)
- **Impact**: Word bank and sentence starters stop working
- **Mitigation**: Audit all inline handlers before refactoring; maintain `window` exports for these specific functions

---

## Implementation Plan

See: `docs/design/phase16-es-module-refactor.md` for detailed implementation design.

### Phases

**Phase 1**: Module Structure (~45 min)

- **Tasks**:
  - [ ] Create `src/static/js/modules/dom.js` — shared DOM utilities
  - [ ] Create `src/static/js/modules/stream.js` — SSE streaming client
  - [ ] Create `src/static/js/modules/shortcuts.js` — keyboard shortcuts
  - [ ] Create `src/static/js/modules/scaffold.js` — word bank & sentence starters
  - [ ] Create `src/static/js/modules/htmx-handlers.js` — HTMX event handlers
  - [ ] Create `src/static/js/main.js` — entry point, wires everything together
- **Deliverable**: New module structure with all code migrated

**Phase 2**: Template Integration (~15 min)

- **Tasks**:
  - [ ] Update `base.html` to use `<script type="module" src="main.js">`
  - [ ] Remove old `<script>` tags for `app.js` and `stream.js`
  - [ ] Verify Alpine.js and HTMX compatibility with module loading
- **Deliverable**: Templates load the new modular JS

**Phase 3**: Cleanup & Validation (~30 min)

- **Tasks**:
  - [ ] Remove dead HTMX guards from handlers
  - [ ] Remove old `app.js` and `stream.js` files
  - [ ] Run full E2E test suite
  - [ ] Verify all 7 E2E flows pass
- **Deliverable**: Clean codebase with passing tests

### Rollback Plan

Revert the `base.html` script tags to the original pattern and restore `app.js`/`stream.js`. The old files can be kept in git history for easy recovery.

---

## Validation

### Pre-Implementation Checklist

- [ ] Decision addresses the original problem (implicit coupling bugs)
- [ ] Success criteria are achievable
- [ ] Risks are identified and mitigated
- [ ] Implementation plan is realistic
- [ ] Dependencies are understood (browser ES module support)
- [ ] Rollback plan exists

### Post-Implementation Validation

**Success Metrics**:

- Zero `window.*` exports for inter-module communication (inline HTML handlers excluded)
- All 7 E2E flows pass
- No JavaScript console errors on page load
- Module load time < 100ms (negligible vs current)

**Validation Tests**:

- [ ] Chat streaming works (SSE tokens render in real time)
- [ ] Scaffolding word bank click-to-insert works
- [ ] Keyboard shortcuts work (Cmd+Enter, Escape, `/`)
- [ ] Lesson player works (HTMX step navigation)
- [ ] Theme toggle works (Alpine.js)
- [ ] New conversation works (HTMX + redirect)
- [ ] Mobile responsive behavior preserved

---

## Related Decisions

**Supersedes**: None (this refactors the JS architecture established in ADR-003, but doesn't change the HTMX + Alpine.js + Tailwind stack)

**Related To**:
- ADR-003: HTMX + Alpine.js Frontend — establishes the "no build step" constraint this ADR preserves
- Phase 15: SSE Streaming — introduced `stream.js` and the cross-file coupling that caused Bug 1

**Depends On**:
- Browser support for `<script type="module">` (universal in target browsers since 2018)

**Informs**:
- Future TypeScript migration would build on this ES module structure
- Future build pipeline (if needed) would be simpler with ES modules already in place

---

## References

### External Resources

- [MDN: JavaScript Modules](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules) — Official ES module documentation
- [Can I Use: ES Modules](https://caniuse.com/es6-module) — 97%+ global browser support
- [V8: JavaScript Modules](https://v8.dev/features/modules) — Performance characteristics of native modules

### Code References

- `src/static/js/app.js` — Current main JS file (380 lines, IIFE)
- `src/static/js/stream.js` — Current streaming client (351 lines, IIFE)
- `src/templates/base.html:535-539` — Current script loading pattern

---

## Discussion and Updates

### Decision History

**2026-02-23**: Proposed

- Motivated by two production bugs found during Playwright E2E testing
- Bug 1 (`window.addUserMessage` not exported) directly caused by IIFE + window.* pattern
- Bug 2 (`\r\n` vs `\n` SSE parsing) is a cross-concern that better module structure makes easier to test

### Questions Raised

**Q1**: Should we use TypeScript instead of plain ES modules?

- **A**: No. TypeScript requires a build step, contradicting ADR-003. The JS surface is 730 lines with low type complexity. JSDoc annotations can provide IDE type hints without compilation. See decision discussion in conversation history.

**Q2**: Will `<script type="module">` break HTMX or Alpine.js?

- **A**: No. HTMX and Alpine.js are loaded via CDN `<script>` tags (classic scripts). Module scripts and classic scripts coexist. The only interaction is via DOM events and `window.*` globals for inline handlers, which are preserved.

**Q3**: Should we use import maps for cleaner import paths?

- **A**: Not necessary at this scale. Relative paths (`./modules/dom.js`) are clear enough for 5-6 modules. Import maps add complexity without proportional benefit.

---

## Metadata

**ADR Number**: 009
**Created**: 2026-02-23
**Last Updated**: 2026-02-23
**Version**: 1.0

**Authors**: Claude (AI Assistant)
**Reviewers**: Project Owner

**Tags**: javascript, es-modules, refactor, frontend, no-build-step, dependency-management

**Project Phase**: Post-Phase 15

---

## Notes

This ADR addresses a gap in the original frontend architecture (ADR-003). When ADR-003 was written, the project had a single small `app.js` file (~200 lines). Phase 15 introduced a second JS file (`stream.js`) with cross-file dependencies, creating the coupling bug class that this refactor eliminates. The ES module approach preserves ADR-003's core principle — no JavaScript build step — while adding the dependency safety that a multi-file JS architecture requires.

---

**Status**: PROPOSED
**Next Review**: After implementation
