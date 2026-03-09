# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **iOS TTS fails after first playback**: Always call `AudioContext.resume()` on every user gesture regardless of reported state — iOS Safari can report `state='running'` but silently refuse to produce audio after a TTS session ends
- **TTS race condition**: Added generation counter to prevent stale cleanup closures from corrupting active TTS sessions when WebSocket `onclose` fires asynchronously
- **TTS WebSocket leak on iOS**: `_stopTTS()` now closes WebSockets in `CONNECTING` state (iOS has slower connections, so WS stays in CONNECTING longer)

## [0.20.0] - 2026-03-09

### Added - Phase 20: Spanish-Inspired Themes
- **4 Spanish culture themes** replacing 3 Nordic themes: Azulejo (cool Mediterranean blue), Terracotta (warm earth tones, default), Flamenco (warm sunset palette), Sangria (deep berry reds)
- **Theme switcher** updated in chat menu with 4 color-coded buttons
- **Design doc**: `docs/design/phase20-spanish-themes.md` with color palette specs and accessibility notes
- **13 screenshots retaken** with new themes across chat, lessons, auth, and menu views

### Removed
- **3 Nordic themes** (Dark, Light, Ocean) replaced entirely by Spanish-inspired themes
- **22 stale screenshots** from `docs/screenshots/` (old Nordic themes, desktop shots, unused variants)

### Changed
- **README.md**: Updated theme section, feature descriptions, test counts, and screenshot references
- **tasks.md**: Corrected theme names, test counts, and phase descriptions

## [0.19.0] - 2026-03-09

### Added - Phase 19: Conversational Lesson Delivery
- **Conversational lesson chat** (`/chat/lesson/{lesson_id}`): Hermano teaches YAML lessons through the chat UI instead of a static lesson player. Lessons flow through a phase machine: intro → teaching → exercise_ask → exercise_eval → complete
- **Lesson chat LangGraph graph** (`src/agent/lesson_chat_graph.py`): Dedicated LangGraph graph for lesson delivery using the same SSE streaming infrastructure as freeform chat
- **Lesson respond node** (`src/agent/nodes/lesson_chat.py`): Phase machine node dispatching to 5 handlers (intro, teaching, exercise_ask, exercise_eval, complete) with step batching (STEP_BATCH_SIZE=3)
- **Lesson chat state** (`src/agent/lesson_chat_state.py`): TypedDict extending conversation fields with lesson tracking (phase, step_index, exercise_index, exercise_results, lesson_score)
- **Lesson-specific prompts** (`src/agent/prompts_lesson_chat.py`): 5 phase-specific system prompts for intro, teaching, exercise ask, exercise eval, and completion
- **Exercise evaluation**: Multiple-choice (letter/number/text parsing), fill-in-the-blank, and translation exercises with correctness checking
- **Lesson progress SSE events**: `lesson_progress`, `exercise_result`, and `lesson_complete` events streamed post-response for UI updates
- **Lesson completion persistence**: Authenticated users get scores and vocabulary persisted via `complete_lesson_and_persist()`
- **Lesson completion UI** (`src/templates/partials/lesson_complete.html`): Celebration screen with score, vocab count, next lesson link, practice with Hermano button
- **CEFR teaching adjustments**: `TEACHING_ADJUSTMENTS` dict in `prompts_lesson_chat.py` with 4 levels (A0/A1/A2/B1), injected into all lesson prompts via `{teaching_adjustments}` placeholder
- **68 new tests**: `tests/agent/nodes/test_lesson_chat.py` (45 tests) and `tests/api/routes/test_lesson_chat.py` (23 tests)
- **Design doc**: `docs/design/phase19-conversational-lessons.md` with architecture and phase machine documentation

### Fixed
- **Lesson progress bar**: `_build_lesson_ui()` accepts step override, computes comprehensive `progress` field; each handler passes post-advance state
- **Checkpoint state persistence**: Route checks for existing checkpoint, only sends full init on first invocation
- **Header layout in lesson mode**: `visibility: hidden` instead of `display: none` for selectors
- **Word bank click-to-insert**: Fixed nonce-based CSP blocking inline event handlers

### Changed
- **Test count**: 2,150 Python tests (up from 2,055), 193 JS tests (up from 189)
- **Source files**: 63 mypy-checked source files (up from 58)

## [0.18.1] - 2026-03-02

### Fixed - P3 Audit Remediation (7 LOW severity items, B18-B24)
- **Workspace cleanup** (B18-B19): Deleted 8 orphan `e2e-*.png` screenshots and 17 stale local branches
- **Dependency management** (B20): Evaluated `node_modules` (53M is minimal), pinned exact npm versions, added `.npmrc`
- **Cache-Control headers** (B21): Static `/static/` assets get `max-age=3600` (debug) or `max-age=86400` (production) via `SecurityHeadersMiddleware`
- **Voice endpoint docs** (B22): ~350 lines documenting `/ws/transcribe`, `/ws/speak`, `POST /api/speak` in `docs/api.md`
- **Voice architecture docs** (B23): ~290 lines covering STT/TTS data flows, proxy pattern, error handling in `docs/architecture.md`
- **Voice integration tests** (B24): 67 transport-level WebSocket tests in `tests/api/routes/test_voice_integration.py`

## [0.18.0] - 2026-03-01

### Fixed - P2 Audit Remediation (10 MEDIUM severity items, B8-B17)
- **Nonce-based CSP** (B8): `'unsafe-inline'` replaced with per-request nonce for all inline scripts; `'unsafe-eval'` retained for Tailwind CDN only
- **Voice rate limiting** (B9): REST `@rate_limited` decorator + WebSocket per-connection sliding window limiter
- **LangGraph compilation caching** (B10): Compiled graphs cached per checkpointer instance
- **ChatAnthropic caching** (B11): LLM instances cached per profile via `@lru_cache`
- **ReviewService server-side queries** (B12): Replaced full-table scans with server-side PostgREST queries
- **Dead code verification** (B13): Scan confirmed clean — no changes needed
- **Narrowed exception handling** (B14): `except Exception:` replaced with specific types in voice routes
- **Supabase admin singleton** (B15): `get_supabase_admin()` cached with `@lru_cache`
- **Pydantic V2 migration** (B16): `class Config` → `model_config = ConfigDict(...)` across all models
- **Structured JSON logging** (B17): `python-json-logger` with `LOG_FORMAT=json` setting for production observability

## [0.17.0] - 2026-02-26

### Fixed - P1 Audit Remediation (7 HIGH severity items, B1-B7)
- **WebSocket auth** (B1): JWT authentication enforced on `/ws/transcribe` and `/ws/speak` — reject 4001 on invalid credentials
- **CSRF middleware** (B2): OWASP custom-header pattern — POST/PUT/DELETE/PATCH require `HX-Request: true` or `X-Requested-With: XMLHttpRequest`
- **VocabularyRepository** (B3): Added `get_by_id()` single-row lookup method
- **Checkpointer documentation** (B4): Singleton pattern documented in `src/agent/checkpointer.py`
- **Layer architecture** (B5): Canonical modules at `src/` level (`config.py`, `validation.py`, `db/client.py`) with re-export shims in `src/api/`
- **ReviewService repository pattern** (B6): Uses repository exclusively, no direct Supabase calls
- **Lesson completion extraction** (B7): Business logic extracted from `lessons.py` (817→468 lines) into `src/services/lesson_completion.py`

## [0.16.0] - 2026-02-25

### Added - Phase 16: ES Module JavaScript Refactor & Phase 17 Voice Improvements
- **ES Module architecture**: Refactored monolithic `app.js` (380 lines) and `stream.js` (388 lines) into 6 focused ES modules: `main.js`, `dom.js`, `stream.js`, `htmx-handlers.js`, `shortcuts.js`, `scaffold.js`
- **AudioWorklet PCM processor** (`src/static/js/pcm-processor.js`): Mobile-safe audio capture for STT with ScriptProcessor fallback
- **JavaScript test suite**: 186 Vitest tests across 6 test files with ~90% coverage on tested modules
- **CI/CD JavaScript tests**: Parallel `test-js` job in GitHub Actions with Node.js 22 and Vitest
- **Floating TTS stop button**: Always-visible stop control during text-to-speech playback
- **TTS mutual exclusion**: Only one TTS session can play at a time; new requests stop the previous

### Changed
- **Voice module mobile hardening**: AudioWorklet with ScriptProcessor fallback, track interruption recovery, visibility change handling, double-init guard
- **Streaming module improvements**: Deterministic scroll throttle (`tokenCounter % 3`), offline detection, speaker button with `pointer-events-none` SVGs
- **DOM utilities**: Touch-aware `focusInput()` skips keyboard on mobile, added `focusInputExplicit()` for explicit user actions, `escapeHtml()` now escapes quotes
- **Keyboard shortcuts**: Skip `/` shortcut in textarea elements, use explicit focus
- **Virtual keyboard handling**: `requestAnimationFrame`-throttled `visualViewport.resize` handler

### Fixed
- **TTS click reliability on mobile**: Added `pointer-events-none` to SVG icons inside speaker buttons, increased touch target, removed `pointer-events: none` from loading state CSS
- **Concurrent TTS race condition**: `_stopAllTTS()` now kills orphaned WebSockets in CONNECTING state and stops REST fallback audio

## [0.15.0] - 2026-02-24

### Added - Phase 17: Voice Conversation (Deepgram STT/TTS)
- **Speech-to-text** via WebSocket proxy (`/ws/transcribe`): Browser MediaRecorder captures audio, FastAPI proxies to Deepgram Nova-3 with code-switching support
- **Text-to-speech** via REST proxy (`POST /api/speak`): Streams audio from Deepgram Aura-2 as audio/mpeg
- **WebSocket TTS streaming** (`/ws/speak`): Low-latency PCM audio streaming with AudioContext playback
- **VoiceManager** (`src/static/js/voice.js`): Mic capture, STT WebSocket, TTS playback with speed control (0.75x-1.25x)
- **Language-matched voices**: Spanish (celeste), German (elara/julius), French (agathe/hector)
- **TTS speed picker**: 3-button speed selector (0.75x, 1x, 1.25x) in chat footer
- **Recording UI**: Audio level bars, recording timer, processing spinner
- **Graceful degradation**: Voice UI hidden when `DEEPGRAM_API_KEY` not configured
- **61 voice tests**: WebSocket STT proxy, REST TTS, WebSocket TTS, validation, edge cases
- **ADR-010**: Deepgram voice STT/TTS architectural decision record
- **CSP updates**: `media-src blob:`, `connect-src ws: wss:` for voice WebSocket and audio playback

### Changed
- **Security headers**: `Permissions-Policy: microphone=(self)` for voice STT
- **Dependencies**: Added `deepgram-sdk>=6.0.0`, `httpx>=0.25.0`, `websockets>=13.0`

## [0.14.1] - 2026-02-23

### Added - Phase 15: SSE Streaming
- **Server-Sent Events**: Real-time chat token streaming via `sse-starlette`
- **Streaming endpoint** (`POST /chat/stream`): Replaces synchronous POST with SSE stream for progressive AI response rendering
- **Streaming client** (`src/static/js/modules/stream.js`): Client-side SSE parser with ReadableStream API, streaming bubble with cursor, throttled auto-scroll
- **Token-by-token rendering**: AI responses appear incrementally with a blinking cursor, replacing the "Thinking..." spinner
- **Feedback sections**: Grammar, scaffolding, and pronunciation feedback rendered as server-side HTML and injected after response completion
- **Abort handling**: 60-second timeout with `AbortController`, offline detection, graceful error display

### Changed
- **Chat form submission**: Intercepted by streaming module — sends via `fetch()` instead of HTMX POST
- **Dependencies**: Added `sse-starlette>=1.8.0`

## [0.14.0] - 2026-02-22

### Added
- **Claude Code skills** (`.claude/skills/`): 11 project-specific development workflow skills covering LangGraph nodes, FastAPI routes, services, repositories, prompts, HTMX templates, YAML lessons, testing, debugging, quality checks, and feature phase planning

### Changed
- **Default LLM switched to Haiku 4.5** from Claude Sonnet 4 — ~10x lower cost and faster response times while retaining sufficient capability for structured language tutoring tasks (ADR-008)

### Fixed
- **VocabularyRepository race condition**: Switch `upsert()` to insert-first pattern catching PostgreSQL duplicate key errors (23505)
- **LessonProgressRepository race condition**: Switch `complete_lesson()` to single upsert operation
- **RLS enforcement in agent nodes**: Remove `get_supabase_admin()` from agent nodes; pass user-scoped Supabase client through LangGraph state so Row Level Security policies are always enforced
- **Centralized LLM factory**: Extract shared `src/agent/llm.py` from 5 duplicate `_get_llm()` functions with profile-based configuration (`conversation`, `analysis`, `scaffolding`, `review`)
- **Dead code removal**: Delete unused `feedback.py` stub node, remove unused `extract_vocabulary()`, clean up dead `EffectiveUser` code
- **Logging hygiene**: Replace f-string logging with lazy `%`-formatting across all agent nodes
- **Agentic framework cleanup**: Audit and streamline `.agentic-framework/` for habla-hermano (net -10K lines)

## [0.13.0] - 2026-02-21

### Added - Phase 14: Learning Paths & Adaptive Recommendations
- **PathService** (`src/services/paths.py`): Structured learning paths organizing 60 lessons into language -> CEFR level units -> category-ordered progressions
- **AdaptiveService** (`src/services/adaptive.py`): Personalized daily recommendations combining path progress, vocabulary accuracy (category strengths), level readiness, and review schedules
- **Learning path page** (`GET /learn/`): Full-page path overview with visual timeline, unit progress, and adaptive recommendation card
- **Recommendation endpoint** (`GET /learn/recommendation`): HTMX lazy-loaded partial for the daily recommendation card
- **Data models**: PathUnit, LearningPath, LessonInUnit, UnitProgress, PathProgress, CategoryStrength, LevelReadiness, DailyRecommendation
- **Continue Path button**: Post-lesson-completion flow linking to learning path
- **Templates**: `learn.html` (full path page), `partials/learn_recommendation.html` (recommendation card)
- **99 new tests**: PathService (27), AdaptiveService (49), learn routes (23) — total suite now 1569+ tests at 86%+ coverage

## [0.12.0] - 2026-02-17

### Added - Security Hardening
- **Server-side JWT verification** (#20): Replace insecure `verify_signature=False` with Supabase `auth.get_user()` server-side validation; forged tokens now rejected; local dev uses explicit fallback with WARNING log
- **Chat input validation** (#21): MAX_MESSAGE_LENGTH (2000 chars), CEFR level validation (A0/A1/A2/B1 only), language validation (es/de/fr only), empty/whitespace rejection; returns HTMX-compatible HTML error fragments (422)
- **Rate limiting** (#23): IP-based rate limiting via `ratelimit` library — auth endpoints: 5 req/min, chat endpoint: 20 req/min; custom async-compatible decorator factory for FastAPI

## [0.11.0] - 2026-02-16

### Changed - Simplified Guest Auth Model
- **Guest access simplified to chat-only** (#18): Remove guest data persistence (vocabulary, progress, sessions); remove `GuestDataMergeService` and guest-to-auth merge logic; remove service key requirement for guest operations
- Guests now get full chat functionality (LangGraph checkpointing), grammar feedback, and pronunciation tips — but no vocabulary tracking, progress data, or spaced repetition (requires authentication)
- **User-scoped Supabase client** for RLS compliance: Add `get_supabase_for_user()` to create JWT-authenticated clients; all data routes now use the user's token instead of the anon client
- Clear architectural separation: chat for all, persistence for authenticated users only

## [0.10.0] - 2026-02-16

### Changed - Phase 13: Mobile-Responsive Design
- Comprehensive mobile-responsive design across all pages
- Added `viewport-fit=cover` for edge-to-edge rendering on notched devices
- Added dynamic viewport height (`100dvh`) to account for mobile browser chrome
- Added safe area inset utilities (`safe-top`, `safe-bottom`, `safe-x`) for notched phones
- Added virtual keyboard scroll handling via `visualViewport` API
- Added touch-optimized interactions: `touch-action: manipulation`, 16px input font-size
- Chat page: responsive header controls, keyboard-aware footer with safe areas
- Lesson player: responsive footer with larger touch targets, overflow handling, title truncation
- Progress dashboard: responsive chart sizing, tighter mobile spacing, reduced tick count
- Scaffold/pronunciation/grammar partials: full-width on mobile (`max-w-full sm:max-w-[85%]`)
- Review partials: full-width buttons on mobile, responsive padding
- Lessons page: multi-line card descriptions on mobile (`line-clamp-2`)
- Auth pages: safe area padding for notched devices
- Mobile scrollbar hiding for native overlay scrollbar experience
- Design doc: docs/design/phase13-mobile-responsive.md

## [0.9.0] - 2026-02-12

### Added - Phase 12: Spaced Repetition
- ReviewService with SM-2 scheduling (easiness factor, intervals, repetition count)
- Intelligent chat weaving: due review words naturally woven into Hermano's conversations
- Dedicated review mode with conversational micro-quizzes (not flashcards)
- Review session API: /review/start, /review/next, /review/submit, /review/stats
- Review state tracking in LangGraph with review_words_offered and review_words_used
- Topical word matching: reviews words that fit current conversation context
- Quality score inference from answer correctness (no manual rating buttons)
- Silent review tracking: SM-2 updates when users naturally use review words in chat
- Review stats on progress page with due count and next review time
- Chat warmup prompt when words are due for review
- Session size options: Quick (5), Regular (10), All due words
- Design doc: docs/design/phase12-spaced-repetition.md

### Changed
- Vocabulary model extended with SM-2 fields: easiness_factor, interval_days, repetition_count, next_review_at, last_reviewed_at
- VocabularyRepository extended with get_due_for_review, get_due_by_keywords, update_review_schedule, get_review_stats
- Chat route now passes user_id to graph for review word weaving
- Respond node fetches topical review words and adds them to system prompt
- Analyze node tracks review word usage and updates SM-2 silently

## [0.8.0] - 2026-02-04

### Added - Phase 11: Nordic Minimal Design & Pronunciation
- Pronunciation tips integrated into all CEFR level prompts (A0-B1)
- Language-specific pronunciation data: tricky_sounds, stress_rule, sound_tip
- PRONUNCIATION TIPS sections in prompts for natural pronunciation coaching
- Design doc: docs/design/phase11-nordic-design-pronunciation.md

### Changed
- Complete UI redesign with Nordic Minimal theme (cool grays, ice blue accents)
- Typography updated to Inter font family for cleaner readability
- Three theme variants: Light (Nordic Day), Dark (Nordic Night), Ocean
- Simplified chat header with icon-based branding
- Compact lesson cards with badge-style level indicators
- Minimal lesson player with thin progress bar

## [0.7.0] - 2026-02-01

### Added - Phase 10: Lesson Content Expansion
- German lessons: 20 lessons (A0-B1) with noun genders, umlauts, formal/informal distinction
- French lessons: 20 lessons (A0-B1) with accents, liaison rules, formal/informal distinction
- Spanish A1-B1 lessons: 15 new lessons building on existing A0 content
- Composite key system for LessonService (`lang/level/id` format)
- Level-appropriate exercise types: A0 (MC only) -> B1 (MC + fill + translate)

### Changed
- LessonService now uses composite keys for unique lesson identification
- get_lesson() supports scoped lookups by language and level

## [0.6.1] - 2026-02-01

### Added - Phase 9: AI-Enhanced Lessons with LangGraph Subgraphs
- LessonState TypedDict for lesson subgraph state management
- Lesson subgraph: load_step -> enhance_step -> END
- Exercise validation subgraph with AI-generated feedback
- Lesson nodes: load_step_node, enhance_step_node, validate_exercise_node
- Lesson prompts: get_lesson_enhance_prompt, get_exercise_feedback_prompt
- API endpoints for AI-enhanced step content and exercise feedback
- Templates for enhanced lesson display
- 1016 total tests

### Fixed
- Circular imports resolved with lazy `get_settings` imports in agent nodes and lesson routes

## [0.6.0] - 2026-01-28

### Added - Phase 7 & 8: Progress Tracking & Guest Sessions
- **ProgressService** for dashboard stats computation and chart data generation
- **VocabularyRepository** for storing and retrieving learned vocabulary items
- **LearningSessionRepository** for tracking learning session metadata
- **LessonProgressRepository** for micro-lesson completion tracking
- Progress dashboard page with vocabulary list, stats summary, and interactive charts
- Chart.js integration for visualizing learning progress over time
- Vocabulary and session data capture in chat and lesson routes
- HTMX partials: progress_vocab.html and stats_summary.html for dynamic updates
- Session-based guest tracking via session_id cookie (httponly, 7-day expiry)
- GuestDataMergeService for merging guest vocabulary and progress data on signup/login
- `_resolve_identity()` helper for unified auth/guest handling across routes
- Fire-and-forget pattern for data capture (failures don't block responses)

### Changed
- Navigation updated to include progress dashboard link
- Chat and lesson routes now capture data for both authenticated users and guests
- Schema migration to drop FK constraints for guest UUIDs

### Fixed
- Progress route type annotation corrected for `_resolve_identity` return type (#12)

## [0.5.0] - 2026-01-25

### Added - Phase 6: Micro-Lessons
- 5 initial Spanish A0 lessons in YAML format (greetings, numbers, colors, family, introductions)
- LessonService for loading and validating YAML lesson files
- Lesson models: Lesson, LessonStep, LessonExercise with Pydantic validation
- Lesson catalog page with card-based browsing
- Lesson player with step navigation and exercise submission (HTMX-driven)
- Lesson completion tracking and handoff to chat
- Hamburger menu navigation for mobile

## [0.4.0] - 2026-01-18

### Added
- Hermano personality: friendly big brother language tutor with consistent voice across all levels
- LANGUAGE_ADAPTER dictionary pattern for clean language switching in prompts
- Extensible language support structure (Spanish, German, French)

### Changed
- Project renamed from habla-ai to habla-hermano
- Renamed 38 files to reflect new branding
- System prompts rewritten with Hermano personality characteristics
- Language adaptation now uses dictionary-based format strings instead of string replacement
- All documentation updated to reflect Hermano personality

### Personality by Level
- A0: Supportive big brother for absolute beginners, heavy encouragement
- A1: Chill friend who spent a year abroad, relaxed guidance
- A2: Challenges learners while keeping it fun and conversational
- B1: Peer-to-peer natural conversation partner

## [0.3.0] - 2026-01-18

### Added - Phase 3: Scaffold Node
- Word bank generation for A0-A1 learners with contextual vocabulary
- Hint text to guide learner responses
- Sentence starters to help beginners formulate responses
- Click-to-insert functionality for word bank items
- Conditional graph routing: A0-A1 learners routed to scaffold node, A2-B1 skip to end
- Auto-expand scaffold for A0 level, collapsed for A1
- ScaffoldingConfig Pydantic model for type-safe scaffold data
- Comprehensive test coverage for scaffold node (16 tests)
- Routing logic tests (10 tests)
- E2E test documentation for scaffold scenarios

### Changed
- LangGraph now uses conditional edges for level-based routing
- Updated message_pair.html template to include scaffold partial
- Added Alpine.js interactions for collapsible scaffold UI

## [0.2.0] - 2026-01-15

### Added - Phase 2: Grammar Analysis
- Grammar correction detection and gentle feedback generation
- Collapsible grammar feedback UI with expand/collapse animations
- Grammar tips displayed inline with conversation flow
- GrammarFeedback Pydantic model for structured feedback data
- Comprehensive test coverage for analyze node
- Desktop and mobile screenshot documentation

### Changed
- LangGraph StateGraph extended with analyze node after respond node
- Message pair template updated to include grammar feedback section
- UI styling enhanced for grammar tip visibility

## [0.1.0] - 2026-01-13

### Added - Phase 1: Core Chat
- Basic conversation flow with respond node
- HTMX-powered real-time chat interface
- Jinja2 templates with Tailwind CSS styling
- Three theme options: Dark, Light, Ocean
- Four proficiency levels: A0, A1, A2, B1
- Two target languages: Spanish and German
- FastAPI backend with WebSocket-style HTMX updates
- Session-based conversation state management
- Mobile-responsive design
- Initial test suite with pytest

### Changed
- Project structure established with src/ directory layout
- Development tooling configured (Ruff, MyPy, pre-commit)

## [0.0.1] - 2026-01-12

### Added
- Initial project setup
- Repository structure and configuration
- Development environment setup with uv
- Basic FastAPI application skeleton
- Makefile for common development commands
- GitHub Actions workflow for CI
- Pre-commit hooks configuration
