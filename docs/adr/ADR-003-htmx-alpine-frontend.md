# ADR-003: HTMX + Alpine.js + Tailwind CSS Frontend Architecture

**Date**: 2025-01-08
**Status**: Accepted
**Context**: Phase 0 (Project Setup), refined through Phase 13 (Mobile Responsive)
**Decider(s)**: Project Owner

---

## Summary

Adopt a server-driven frontend architecture using HTMX for dynamic content swapping, Alpine.js for lightweight client-side state management, and Tailwind CSS for utility-first styling — instead of a JavaScript SPA framework. All HTML is rendered server-side via Jinja2 templates in FastAPI, with HTMX handling AJAX interactions and Alpine.js managing UI micro-state (expand/collapse, theme toggle, word bank click-to-insert).

---

## Problem Statement

### The Challenge

Habla Hermano needs a frontend capable of handling interactive language learning workflows without the overhead of a full JavaScript SPA framework:

1. **Real-time chat UX**: Chat messages must appear dynamically with a streaming-like feel, without full page reloads
2. **Dynamic content swapping**: Lesson steps, exercise validation results, and recommendation cards must load and replace inline
3. **Interactive UI elements**: Collapsible grammar/scaffold/pronunciation cards, theme toggle, word bank click-to-insert
4. **Solo developer simplicity**: One person builds and maintains the entire stack — frontend complexity must stay low
5. **Mobile-responsive**: Full support for mobile browsers including safe area insets on notched devices and dynamic viewport height

### Why This Matters

For a language learning app where the core interaction is a conversation with an AI tutor:
- The server already owns all business logic (LangGraph agent, lesson engine, progress tracking)
- Most interactions are request-response (send message, get reply; advance lesson step, get next step)
- Rich client-side state management adds complexity without proportional value
- Development velocity matters more than client-side sophistication for a solo project

### Success Criteria

- [x] Chat messages send and appear without page reload
- [x] Lesson steps advance inline via HTMX swaps
- [x] Grammar, scaffold, and pronunciation cards expand/collapse with Alpine.js
- [x] Theme toggle persists to localStorage via Alpine.js
- [x] Word bank entries are clickable and insert into the chat input
- [x] Fully mobile-responsive with safe area support for notched devices
- [x] No JavaScript build step required (no webpack, no Vite, no bundler)

---

## Context

### Current State

**Architecture at Decision Time**:
```
Browser ──► FastAPI (Jinja2 Templates)
  │              │
  │ HTMX         │ Server-rendered HTML
  │ requests      │ partials & full pages
  │              │
  ▼              ▼
Alpine.js    Tailwind CSS
(UI state)   (utility classes)
```

**Key Characteristics**:

- FastAPI renders all HTML server-side using Jinja2 templates
- HTMX replaces portions of the DOM via `hx-get`, `hx-post`, `hx-swap` attributes
- Alpine.js manages ephemeral UI state with `x-data`, `x-show`, `x-on` directives
- Tailwind CSS provides styling via utility classes, compiled from `input.css` to `styles.css`

**Technical Constraints**:

- Must integrate with FastAPI's template rendering pipeline
- Must work with LangGraph's server-side streaming responses
- Must support mobile Safari (dynamic viewport, safe areas)
- Must remain maintainable by a solo developer
- No Node.js runtime required in production

### Requirements

**Functional Requirements**:

- Chat message submission and display without page reload
- Lesson step navigation (next/previous) with inline content swap
- Lazy loading of recommendation cards on the learn page
- Collapsible detail cards (grammar feedback, scaffold text, pronunciation guide)
- Theme selection with localStorage persistence
- Word bank interaction (click word to insert into chat input)

**Non-Functional Requirements**:

- **Performance**: Fast Time to Interactive (<1s on WiFi, <3s on 3G) — no large JS bundle to parse
- **Simplicity**: No build pipeline for JavaScript; Tailwind CLI is the only build tool
- **SEO**: Server-rendered HTML is indexable by default
- **Accessibility**: Semantic HTML rendered server-side, ARIA attributes in templates
- **Maintainability**: Adding a new feature = new Jinja2 template + new FastAPI route

**Stakeholder Concerns**:

- Fast development iteration (no compile-wait-reload cycle for JS changes)
- Ability to add new pages and features quickly without frontend framework expertise
- Mobile-first design that works on real phones, not just desktop resizing

---

## Options Considered

### Option A: HTMX + Alpine.js + Tailwind CSS (Server-Driven)

**Description**:
Server-rendered Jinja2 templates with HTMX handling all dynamic content swapping via HTML-over-the-wire, Alpine.js providing lightweight client-side reactivity for UI micro-state, and Tailwind CSS for utility-first responsive styling.

**Implementation**:
- HTMX attributes on HTML elements (`hx-post`, `hx-get`, `hx-swap`, `hx-trigger`) drive all server interactions
- FastAPI routes return HTML partials (not JSON) for HTMX requests
- Alpine.js `x-data` scopes manage expand/collapse, theme toggle, and click-to-insert state
- Tailwind CSS utility classes with mobile-first breakpoints (`default` -> `sm:` -> `md:` -> `lg:`)
- Single `app.js` file for custom JavaScript (scroll behavior, event listeners)
- Tailwind CLI compiles `input.css` to `styles.css` (only build step)

**Pros**:

- No JavaScript build pipeline (no webpack, Vite, or bundler)
- Server-authoritative — all logic lives in Python, not duplicated in JS
- Fast Time to Interactive (small JS payload: HTMX ~14KB + Alpine ~15KB gzipped)
- Simple mental model: HTML templates + route handlers
- Adding a feature = adding a template + a route (no component tree, no state management library)
- SEO-friendly by default (server-rendered HTML)
- Excellent caching — HTML partials are cacheable

**Cons**:

- No client-side routing (every navigation is a server round-trip)
- Limited offline capability (no service worker, no client-side data layer)
- Less suitable for highly interactive UIs (drag-and-drop, complex animations)
- Smaller community compared to React/Vue ecosystems
- IDE tooling for HTMX attributes is less mature

**Risks**:

- **HTMX limitations**: Some interactions may require custom JS workarounds
- **Scaling complexity**: If the frontend grows significantly, server-driven approach may feel constrained

**Estimated Effort**: 1-2 days for initial setup, ongoing as features are added

---

### Option B: React SPA (Client-Side Rendering)

**Description**:
Full client-side rendering with React (or Next.js for SSR), using a REST or GraphQL API layer between the frontend and FastAPI backend.

**Implementation**:
- React components for all UI elements
- React Router for client-side navigation
- State management via Context API, Zustand, or Redux
- API layer consuming JSON endpoints from FastAPI
- Vite or Next.js for build tooling

**Pros**:

- Rich client-side interactivity and routing
- Large ecosystem of component libraries and tooling
- Strong TypeScript support and type safety
- Mature testing ecosystem (React Testing Library, Cypress)
- Good for complex, highly interactive UIs

**Cons**:

- Requires separate build pipeline (Node.js, Vite/webpack)
- API duplication: FastAPI must serve JSON AND the React app needs to consume it
- Heavier JavaScript bundle (React ~40KB + router + state library + application code)
- Two mental models: Python backend logic + JavaScript frontend logic
- Slower Time to Interactive on mobile (must download, parse, and execute JS before rendering)
- Overkill for a fundamentally server-driven conversational app

**Risks**:

- **Development velocity**: Maintaining two codebases (Python + React) slows a solo developer
- **Bundle bloat**: Easy to accumulate large JS bundles with React dependencies

**Estimated Effort**: 3-5 days for initial setup, significantly more ongoing

---

### Option C: Vue 3 SPA (Client-Side Rendering)

**Description**:
Client-side rendering with Vue 3 Composition API, Pinia for state management, and Vue Router for navigation, consuming JSON from FastAPI.

**Implementation**:
- Vue 3 Single File Components with Composition API
- Pinia stores for state management
- Vue Router for client-side navigation
- Vite for build tooling
- JSON API layer from FastAPI

**Pros**:

- Lighter than React (~33KB gzipped)
- Reactive system with less boilerplate than React
- Composition API is clean and composable
- Good TypeScript support
- Familiar from other projects in this repository (KwizUp, Spotify Insights)

**Cons**:

- Same SPA complexity issues as React (build pipeline, API duplication, two mental models)
- Still requires Node.js runtime for development and builds
- Client-side rendering means slower TTI on mobile compared to server-rendered HTML
- Overkill for request-response interaction patterns (chat, lesson steps)
- Adds unnecessary client-side state layer when the server already owns all state

**Risks**:

- **Unnecessary complexity**: Vue's reactivity system solves problems this app does not have
- **Maintenance burden**: Two codebases to maintain for one developer

**Estimated Effort**: 3-4 days for initial setup, significantly more ongoing

---

## Comparison Matrix

| Criteria                    | Weight | Option A (HTMX+Alpine) | Option B (React SPA) | Option C (Vue SPA) |
| --------------------------- | ------ | ----------------------- | --------------------- | ------------------- |
| **Development Simplicity**  | High   | 5                       | 2                     | 3                   |
| **Time to Interactive**     | High   | 5                       | 2                     | 3                   |
| **Maintainability (Solo)**  | High   | 5                       | 2                     | 3                   |
| **Server Integration**      | High   | 5                       | 3                     | 3                   |
| **Mobile Performance**      | High   | 5                       | 3                     | 3                   |
| **Client Interactivity**    | Medium | 3                       | 5                     | 5                   |
| **Ecosystem & Tooling**     | Medium | 3                       | 5                     | 4                   |
| **Offline Capability**      | Low    | 1                       | 4                     | 4                   |
| **SEO Friendliness**        | Low    | 5                       | 2                     | 2                   |
| **Total Score**             | -      | **37**                  | 28                    | 30                  |

**Scoring**: 1 = Poor, 2 = Below Average, 3 = Acceptable, 4 = Good, 5 = Excellent

---

## Decision

### Chosen Option

**Selected**: Option A: HTMX + Alpine.js + Tailwind CSS

**Rationale**:
Habla Hermano is fundamentally a server-driven application. The AI tutor, lesson engine, progress tracking, and vocabulary management all live on the server. The frontend's job is to present server-rendered HTML and facilitate request-response interactions (send a chat message, get a reply; advance a lesson step, get the next step). HTMX is purpose-built for this pattern. Alpine.js fills the narrow gap for client-side UI state (expand/collapse, theme toggle) without requiring a full framework. Tailwind CSS provides rapid styling with no runtime cost.

**Key Factors**:

- The interaction model is request-response, not rich client-side state management
- One developer maintaining one codebase (Python) is faster than maintaining two (Python + JS framework)
- No JavaScript build step means instant iteration on template changes
- HTMX's ~14KB + Alpine's ~15KB gzipped is dramatically lighter than any SPA framework
- Server-rendered HTML means fast Time to Interactive on mobile devices

**Trade-offs Accepted**:

- No client-side routing (acceptable: pages are fast to load server-side)
- No offline support (acceptable: the app requires an AI backend to function)
- Limited rich client-side interactivity (acceptable: the app does not need it)

---

## Consequences

### Positive Outcomes

**Immediate Benefits**:

- No JavaScript build pipeline to configure, maintain, or debug
- Server-authoritative architecture — all logic in Python, no duplication in JavaScript
- Fast page loads: server-rendered HTML with minimal JS overhead
- Adding a new feature is as simple as creating a Jinja2 template and a FastAPI route
- Mobile performance is excellent due to small JS payload

**Long-term Benefits**:

- Low maintenance burden: HTMX and Alpine.js are stable, minimal-API libraries
- Easy onboarding: anyone who knows HTML can understand the templates
- Security: server-rendered HTML means no sensitive logic exposed to the client
- Progressive enhancement: core functionality works even with JavaScript disabled (forms still POST)

### Negative Outcomes

**Immediate Costs**:

- Learning HTMX attribute patterns (`hx-get`, `hx-swap`, `hx-trigger`, `hx-target`)
- Some interactions require creative HTMX solutions (e.g., scroll-to-bottom after chat message swap)
- Custom `app.js` needed for behaviors HTMX and Alpine.js do not cover natively

**Technical Debt Created**:

- Inline HTMX attributes in templates can become verbose for complex interactions
- `app.js` may grow organically if many custom behaviors are added

**Trade-offs**:

- No offline support (the app requires server connectivity to function regardless)
- No client-side routing (page transitions involve full-page or partial server responses)
- Complex animations or drag-and-drop would require additional JS libraries

### Risks and Mitigation

**Risk 1**: HTMX cannot handle a required interaction pattern

- **Probability**: Low
- **Impact**: Workaround needed in custom JavaScript
- **Mitigation**: HTMX has extension points; `app.js` can handle edge cases

**Risk 2**: Alpine.js state management becomes too complex

- **Probability**: Low (current use cases are simple: expand/collapse, theme toggle)
- **Impact**: Messy inline `x-data` directives in templates
- **Mitigation**: Extract complex state into Alpine.js components or `app.js` modules

**Risk 3**: Tailwind CSS utility classes create verbose HTML

- **Probability**: Medium
- **Impact**: Templates become harder to read
- **Mitigation**: Use `@apply` in `input.css` for repeated patterns; extract Jinja2 macros for component reuse

---

## Key Patterns

### HTMX Interaction Patterns

**Chat Message Submission**:
```html
<form hx-post="/chat/send" hx-target="#messages" hx-swap="beforeend">
  <input type="text" name="message" />
  <button type="submit">Send</button>
</form>
```

**Lesson Step Navigation**:
```html
<button hx-get="/lessons/{id}/step/next" hx-target="#lesson-content" hx-swap="innerHTML">
  Next Step
</button>
```

**Lazy Loading Recommendations**:
```html
<div hx-get="/learn/recommendation" hx-trigger="load delay:500ms" hx-swap="innerHTML">
  <!-- Loading placeholder -->
</div>
```

### Alpine.js State Patterns

**Collapsible Cards**:
```html
<div x-data="{ expanded: false }">
  <button @click="expanded = !expanded">Grammar Feedback</button>
  <div x-show="expanded" x-transition>
    <!-- Card content -->
  </div>
</div>
```

**Theme Selector (localStorage persistence)**:
```html
<div x-data="{ theme: localStorage.getItem('theme') || 'default' }">
  <select x-model="theme" @change="localStorage.setItem('theme', theme)">
    <option value="default">Default</option>
    <option value="dark">Dark</option>
  </select>
</div>
```

### Tailwind CSS Mobile Patterns

**Responsive Layout (mobile-first)**:
```html
<div class="px-4 sm:px-6 md:px-8 lg:max-w-4xl lg:mx-auto">
  <!-- Content scales from mobile to desktop -->
</div>
```

**Safe Area Support (notched devices)**:
```css
.chat-container {
  padding-bottom: calc(env(safe-area-inset-bottom) + 1rem);
  height: 100dvh; /* Dynamic viewport height for mobile browsers */
}
```

---

## Implementation Plan

### Phases

**Phase 0**: Initial Setup

- **Tasks**:
  - [x] Configure Jinja2 template rendering in FastAPI
  - [x] Add HTMX and Alpine.js via CDN links in `base.html`
  - [x] Configure Tailwind CSS CLI build (`input.css` -> `styles.css`)
  - [x] Create `base.html` layout template with responsive meta tags
- **Deliverable**: Working template rendering with HTMX, Alpine.js, and Tailwind

**Phase 1-4**: Core Feature Templates

- **Tasks**:
  - [x] Build `chat.html` with HTMX message submission
  - [x] Build `lesson_player.html` with HTMX step navigation
  - [x] Build `learn.html` with lazy-loaded recommendation cards
  - [x] Build `progress.html` with vocabulary display
  - [x] Add Alpine.js expand/collapse to feedback cards
- **Deliverable**: All core pages functional with HTMX + Alpine.js

**Phase 13**: Mobile Responsive Refinement

- **Tasks**:
  - [x] Add `100dvh` for dynamic viewport height
  - [x] Add `env(safe-area-inset-*)` for notched devices
  - [x] Refine responsive breakpoints across all templates
  - [x] Test on real mobile devices (iOS Safari, Android Chrome)
- **Deliverable**: Fully mobile-responsive frontend

### Key Files

| File | Purpose |
| ---- | ------- |
| `src/templates/base.html` | Root layout: CDN imports, nav, responsive meta, safe area CSS |
| `src/templates/chat.html` | Chat interface: HTMX message send/receive, Alpine.js cards |
| `src/templates/lesson_player.html` | Lesson UI: HTMX step navigation, exercise validation |
| `src/templates/learn.html` | Learning hub: HTMX lazy loading, recommendation cards |
| `src/static/js/app.js` | Custom JS: scroll behavior, event listeners, theme init |
| `src/static/css/input.css` | Tailwind source: `@apply` rules, custom CSS, safe area styles |
| `src/static/css/styles.css` | Tailwind output: compiled utility classes (generated, not edited) |

---

## Validation

### Pre-Implementation Checklist

- [x] Decision addresses the original problem
- [x] Success criteria are achievable
- [x] Risks are identified and mitigated
- [x] Implementation plan is realistic
- [x] Dependencies are understood
- [x] Rollback plan exists (swap HTMX for traditional form submissions)

### Architect Quality Standards

- [x] **Simplicity**: No build step for JavaScript, minimal framework overhead
- [x] **Maintainability**: Templates are plain HTML with declarative attributes
- [x] **Performance**: Sub-30KB JavaScript payload (HTMX + Alpine.js gzipped)
- [x] **Scalability**: Server-rendered HTML scales with server capacity, not client device power
- [x] **Trade-offs**: Limited client-side interactivity accepted for development velocity

### Post-Implementation Validation

**Success Metrics**:

- Time to Interactive: Target <1s on WiFi, <3s on 3G
- JavaScript payload: Target <50KB gzipped (HTMX + Alpine.js + app.js)
- Lighthouse Performance score: Target 90+
- Mobile usability: No Lighthouse mobile issues

**Validation Tests**:

- [x] Chat messages appear without page reload
- [x] Lesson steps advance via HTMX swap
- [x] Collapsible cards expand/collapse with Alpine.js
- [x] Theme persists across page navigation via localStorage
- [x] Layout renders correctly on mobile with safe area insets

**Review Date**: 2025-02-08 (1 month post-initial implementation)

---

## Related Decisions

**Supersedes**:

- None (frontend approach was established from the start)

**Related To**:

- ADR-001: Supabase Integration — Auth UI (login/signup forms) built with this same HTMX + Alpine.js approach

**Depends On**:

- FastAPI as the backend framework (provides Jinja2 template rendering)

**Informs**:

- Future decisions about adding richer client-side features (e.g., voice input, drag-and-drop exercises)
- Any future decision to migrate to an SPA would supersede this ADR

---

## References

### External Resources

- [HTMX Documentation](https://htmx.org/docs/) - Official HTMX reference
- [Alpine.js Documentation](https://alpinejs.dev/) - Official Alpine.js reference
- [Tailwind CSS Documentation](https://tailwindcss.com/docs) - Official Tailwind reference
- [HTMX + FastAPI](https://htmx.org/server-examples/) - Server integration patterns
- [Dynamic Viewport Units](https://web.dev/viewport-units/) - `dvh` unit explanation

### Code References

- `src/templates/base.html` - Root layout with CDN imports and responsive configuration
- `src/templates/chat.html` - Primary HTMX interaction surface (chat send/receive)
- `src/templates/lesson_player.html` - HTMX step navigation and exercise validation
- `src/templates/learn.html` - HTMX lazy loading pattern for recommendation cards
- `src/static/js/app.js` - Custom JavaScript for behaviors beyond HTMX/Alpine.js
- `src/static/css/input.css` - Tailwind source with custom CSS and safe area styles

---

## Discussion and Updates

### Decision History

**2025-01-08**: Proposed

- Initial decision to use HTMX + Alpine.js + Tailwind CSS as part of Phase 0 project setup
- Rationale: server-driven app does not need a JavaScript SPA framework

**2025-01-08**: Accepted

- Decision approved; initial templates built with this stack

**2025-01-25**: Refined (Phase 13 - Mobile Responsive)

- Added `100dvh` for dynamic viewport height on mobile browsers
- Added `env(safe-area-inset-*)` for notched device support
- Validated responsive behavior across iOS Safari and Android Chrome

### Questions Raised

**Q1**: Should we add a JavaScript bundler for tree-shaking and minification?

- **A**: No. HTMX and Alpine.js are loaded via CDN (already minified). `app.js` is small enough to serve directly. If `app.js` grows significantly, revisit.

**Q2**: Should we use HTMX WebSocket extension for real-time chat?

- **A**: Not yet. The current `hx-post` + `hx-swap` pattern provides adequate chat UX. WebSocket can be added later if true real-time features are needed.

**Q3**: What about TypeScript for `app.js`?

- **A**: No. The file is small (<200 lines) and handles simple DOM interactions. TypeScript would require a build step, contradicting a key benefit of this architecture.

### Feedback Incorporated

- Mobile-first responsive design was elevated in priority after Phase 13 testing on real devices
- Safe area support was added based on iPhone testing with notched displays
- `100dvh` was adopted over `100vh` after observing address bar behavior in mobile Safari

---

## Metadata

**ADR Number**: 003
**Created**: 2025-01-08
**Last Updated**: 2025-01-25
**Version**: 1.1

**Authors**: Claude (AI Assistant)
**Reviewers**: Project Owner

**Tags**: frontend, htmx, alpine.js, tailwind, server-rendered, mobile-responsive, jinja2

**Project Phase**: Development

---

## Notes

This ADR documents a foundational architectural choice that shapes the entire developer experience of Habla Hermano. By choosing server-rendered HTML with HTMX over a JavaScript SPA, the project trades rich client-side interactivity for development simplicity, fast page loads, and a single-codebase mental model. This trade-off is well-suited to a conversational language learning app where the server already owns all state and the primary interaction pattern is request-response.

The decision has held up well through 13 phases of development, with no feature blocked by the lack of a client-side framework. The Alpine.js additions for expand/collapse and theme toggle demonstrate that targeted client-side reactivity can be added incrementally without adopting a full SPA architecture.

---

**Status**: ACCEPTED
**Next Review**: 2025-02-08
