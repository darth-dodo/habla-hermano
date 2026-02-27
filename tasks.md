# Habla Hermano - Task Tracking

> **Source of Truth**: This file is the single source of truth for project state.

## Table of Contents
- [Current State](#current-state)
- [Up Next](#up-next)
- [Completed Phases](#completed-phases)
- [Session Logs](#session-logs)
- [Notes for Future Agents](#notes-for-future-agents)

---

## Current State

**Branch**: `fix/p2-audit-remediation` (P2 remediation complete, PR #41)
**Phase**: Post-Audit Remediation — P1+P2 items complete, P3 pending
**Test Coverage**: 2168+ tests passing (1981 Python + 187 JS), 97% coverage
**Last Audit**: 2026-02-26 (multi-dimensional: security, performance, architecture, workspace hygiene)
**P2 Remediation**: 2026-02-27 → 10/10 MEDIUM severity items complete (B8-B17)
**P1 Remediation**: 2026-02-26 → 7/7 HIGH severity items complete (B1-B7)
**Previous Audit**: 2026-02-22 → remediated 2026-02-23 (23/24 items, A1-A24 excluding A10)

### What's Working

| Feature | Phase | Notes |
|---------|-------|-------|
| Hermano Personality | 1 | Friendly big brother tutor, 4 levels (A0-B1) |
| 3 Languages | 1 | Spanish, German, French via LANGUAGE_ADAPTER |
| Grammar Feedback | 2 | Gentle corrections with expandable tips |
| Scaffolding | 3 | Word banks, hints, sentence starters (A0-A1) |
| Conversation Persistence | 4 | PostgresSaver with MemorySaver fallback |
| Supabase Auth | 5 | JWT tokens + guest sessions + token refresh |
| 60 Micro-Lessons | 6+10 | 3 languages x 4 levels x 5 categories |
| Progress Dashboard | 7 | Stats, vocabulary, charts |
| Guest Sessions | 8 | Chat-only access, auth-gated data features |
| AI-Enhanced Lessons | 9 | LangGraph subgraphs, Hermano personalization |
| Nordic Minimal Design | 11 | 3 themes (Light/Dark/Ocean), pronunciation tips |
| Spaced Repetition | 12 | SM-2 algorithm, chat weaving, dedicated review mode |
| Mobile Responsive | 13 | Safe areas, dynamic viewport, touch-optimized |
| Learning Paths | 14 | Static paths + adaptive daily recommendations |
| SSE Streaming | 15 | Real-time chat via Server-Sent Events |
| Security Hardening | Audit | Headers, signed cookies, XSS sanitization, JWT refresh |
| CSRF Protection | P1 | Custom-header pattern (HX-Request/X-Requested-With) for POST/PUT/DELETE/PATCH |
| WebSocket Auth | P1 | JWT authentication enforced on /ws/transcribe and /ws/speak |
| Layer Architecture | P1 | Canonical modules at src/ level (config, validation, db/client), re-export shims |
| Lesson Completion Service | P1 | Business logic extracted from lessons.py → src/services/lesson_completion.py |
| Voice Conversation | 17 | Deepgram STT (Nova-3) + TTS (Aura-2), WebSocket proxy, graceful degradation |
| ES Module Architecture | 16 | 6 JS modules, 186 Vitest tests, CI/CD integration |
| Voice Improvements | 16 | Floating TTS stop bar, concurrent TTS fix, mobile click reliability |
| CSP Nonce | P2 | Per-request nonce replaces `unsafe-inline` in script-src, all script tags nonced |
| Voice Rate Limiting | P2 | REST: `@rate_limited` decorator; WebSocket: per-connection sliding window limiter |
| LLM/Graph Caching | P2 | `@lru_cache` on `get_llm()`, dict cache per checkpointer for compiled graphs |
| Supabase Admin Singleton | P2 | `@lru_cache` on `get_supabase_admin()` prevents repeated client creation |
| Structured JSON Logging | P2 | `python-json-logger` with `LOG_FORMAT=json` setting for production observability |
| Pydantic V2 ConfigDict | P2 | Models migrated from V1 `class Config` to V2 `model_config = ConfigDict(...)` |
| Error Handling | P2 | Narrowed `except Exception` to specific types in voice routes |

### LangGraph Flow

```
Main Graph:
START → respond → [needs_scaffold?]
                    ├── A0/A1 → scaffold → analyze → END
                    └── A2/B1 → analyze → END

Lesson Subgraph (Phase 9):
START → load_step → enhance_step → END

Exercise Validation Subgraph (Phase 9):
START → validate_exercise → END

Persistence: PostgresSaver (Supabase) with MemorySaver fallback for dev
Auth: Supabase Auth → JWT cookie (with refresh) → Protected routes
```

---

## Up Next

### Phase 16: ES Module Migration + Voice UX — ✅ Complete

| # | Task | Status | Notes |
|---|------|--------|-------|
| E1 | Refactor app.js into ES modules (dom, htmx-handlers, shortcuts, scaffold) | ✅ | 6 modules under `src/static/js/modules/` |
| E2 | Refactor stream.js into ES module | ✅ | `src/static/js/modules/stream.js` |
| E3 | Migrate voice.js to ES module loading | ✅ | `src/static/js/modules/voice.js` (loaded as type="module") |
| E4 | Create AudioWorklet PCM processor | ✅ | `src/static/js/pcm-processor.js` (mobile-safe STT capture) |
| E5 | Mobile-first JS improvements (11 fixes) | ✅ | Touch focus, scroll throttle, keyboard handling, escapeHtml quotes |
| E6 | JavaScript test suite (186 tests) | ✅ | Vitest + jsdom, ~90% coverage on tested modules |
| E7 | Add JS tests to CI/CD pipeline | ✅ | Parallel `test-js` job in GitHub Actions |
| E8 | Floating TTS stop button | ✅ | Always-visible stop control during playback |
| E9 | TTS mutual exclusion | ✅ | Only one TTS session at a time, orphaned WS cleanup |

### Phase 17: Voice Conversation (Deepgram STT/TTS) — ✅ Complete

| # | Task | Status | Notes |
|---|------|--------|-------|
| V1 | Add `DEEPGRAM_API_KEY` to config + `voice_enabled` property | ✅ | `src/api/config.py`, `src/api/dependencies.py` |
| V2 | Create `src/api/routes/voice.py` (WebSocket STT proxy + REST TTS endpoint) | ✅ | `/ws/transcribe`, `POST /api/speak` |
| V3 | Register voice router in `src/api/main.py` | ✅ | `app.include_router(voice.router)` |
| V4 | Create `src/static/js/voice.js` (VoiceManager class) | ✅ | Mic capture, WebSocket STT, TTS playback |
| V5 | Update `chat.html` — mic button + load voice.js | ✅ | Conditional on `voice_enabled` |
| V6 | Update `message_pair.html` — speaker icon on AI responses | ✅ | TTS playback trigger |
| V7 | Add `deepgram-sdk` + `httpx` to `pyproject.toml` | ✅ | `deepgram-sdk>=3.0.0`, `httpx>=0.25.0` |
| V8 | Create `tests/api/routes/test_voice.py` (59 tests) | ✅ | WebSocket + TTS + validation + edge cases |
| V9 | Add voice CSS styles (mic button states, speaker icon) | ✅ | Pulse animation, loading/playing states |

**Design doc**: `docs/design/phase17-voice-conversation.md`
**ADR**: `docs/adr/ADR-010-deepgram-voice-stt-tts.md`

---

### Codebase Audit Findings (2026-02-26) — P1 ✅ Complete, P2 ✅ Complete, P3 Pending

Full audit covering security, performance, architecture, code quality, and workspace hygiene.
Ran 3 parallel specialized agents (security-engineer, architecture-strategist, performance-engineer) plus direct quality checks.

**Scores** (pre-remediation): Code Quality 8/10 | Testing 9/10 | Architecture 6/10 | Security 7/10 | Performance 5/10 | Workspace Hygiene 5/10 | CI/CD 8/10

**Baseline** (post-P2): 2168+ tests (1981 Python + 187 JS), ruff clean, mypy clean (0 issues in 58 files)

#### Priority: P1 — High Severity ✅ All Done

| # | Task | Severity | Status | Notes |
|---|------|----------|--------|-------|
| B1 | Add WebSocket authentication to `/ws/transcribe` and `/ws/speak` | HIGH | ✅ Done | `_authenticate_websocket()` helper validates JWT cookie on connect. Rejects with code 4001 if invalid. `src/api/routes/voice.py` |
| B2 | Add CSRF protection for state-changing POST endpoints | HIGH | ✅ Done | `CSRFMiddleware` in `src/api/middleware.py` — OWASP custom-header pattern (HX-Request/X-Requested-With). 15 tests in `tests/api/test_csrf.py`. |
| B3 | Add `VocabularyRepository.get_by_id()` method | HIGH | ✅ Done | Single-row lookup replaces `get_all()` + Python filter in ReviewService. `src/db/repository.py` |
| B4 | Persist LangGraph checkpointer across requests | HIGH | ✅ Done | Documented singleton pattern with `get_checkpointer()` async context manager. Dev limitation accepted. `src/agent/checkpointer.py` |
| B5 | Fix 9 layer violations (inner layers importing from API) | HIGH | ✅ Done | Created `src/config.py`, `src/validation.py`, `src/db/client.py`. Old locations are re-export shims. 8 inner-layer imports updated. |
| B6 | Fix ReviewService direct DB access bypassing repository | HIGH | ✅ Done | ReviewService now uses `VocabularyRepository` methods exclusively. No more direct `client.table()` calls. `src/services/review.py` |
| B7 | Extract large route files into focused modules (SRP) | HIGH | ✅ Done | `lessons.py` (817→468 lines) — business logic extracted to `src/services/lesson_completion.py`. |

#### Priority: P2 — Medium Severity ✅ All Done

| # | Task | Severity | Status | Notes |
|---|------|----------|--------|-------|
| B8 | Nonce-based CSP for CDN scripts | MEDIUM | ✅ Done | Per-request `secrets.token_urlsafe(16)` nonce in script-src replaces `unsafe-inline`. `unsafe-eval` retained for Tailwind CDN (requires build-time CSS migration to remove). All `<script>` tags in 6 templates use `nonce="{{ request.state.csp_nonce }}"`. 7 tests in `tests/api/test_security_headers.py`. |
| B9 | Add rate limiting to voice endpoints | MEDIUM | ✅ Done | REST: `@rate_limited()` on `POST /api/speak` (10 calls/60s). WebSocket: `WebSocketMessageRateLimiter` class with per-connection sliding window (30 msgs/60s). `src/api/rate_limit.py`, `src/api/routes/voice.py`. |
| B10 | Cache LangGraph graph compilation | MEDIUM | ✅ Done | Module-level `_graph_cache: dict[int, CompiledStateGraph]` keyed by `id(checkpointer)`. `clear_graph_cache()` helper for tests. `src/agent/graph.py`. |
| B11 | Cache `ChatAnthropic` instances per profile | MEDIUM | ✅ Done | `@lru_cache(maxsize=8)` on `get_llm()`. `clear_llm_cache()` helper for test isolation. `src/agent/llm.py`. |
| B12 | Replace full-table scans with server-side queries | MEDIUM | ✅ Done | `get_stats()` uses `get_due_for_review()` + `get_in_rotation_count()`. `get_due_words()` uses `repo.get_due_for_review()` directly. Added `get_in_rotation_count()` to repository. `src/services/review.py`, `src/db/repository.py`. |
| B13 | Verify clean dead code scan | MEDIUM | ✅ Done | `ruff check src/ --select F401,F841,ERA001` — all clean, no dead code found. |
| B14 | Standardize error handling in voice routes | MEDIUM | ✅ Done | Narrowed `except Exception` to `(httpx.HTTPError, ConnectionError, OSError)` in REST TTS, specific WebSocket exception types. Background task retains broad catch with logged type. `src/api/routes/voice.py`. |
| B15 | Cache `get_supabase_admin()` singleton | MEDIUM | ✅ Done | `@lru_cache` on `get_supabase_admin()`. `clear_supabase_cache()` clears both client and admin caches. `src/db/client.py`. |
| B16 | Migrate Pydantic models to V2 ConfigDict | MEDIUM | ✅ Done | Replaced 3x `class Config: from_attributes = True` with `model_config = ConfigDict(from_attributes=True)` in `Vocabulary`, `LearningSession`, `LessonProgress`. `src/db/models.py`. |
| B17 | Add structured JSON logging | MEDIUM | ✅ Done | `python-json-logger>=3.0.0` dependency. `LOG_FORMAT` setting (text/json). JSON formatter auto-selected when `LOG_FORMAT=json`. `src/config.py`, `src/api/main.py`, `pyproject.toml`. |

#### Priority: P3 — Low Severity (Backlog)

| # | Task | Severity | Status | Notes |
|---|------|----------|--------|-------|
| B18 | Clean up 6 orphan PNG screenshots in project root | LOW | ⏳ | `e2e-flow*.png`, `mobile-step1.png` — should be in `docs/screenshots/` or deleted. |
| B19 | Clean up 17 stale worktree branches | LOW | ⏳ | Leftover from parallel agent workflows. `git branch \| wc -l` shows 17 branches. |
| B20 | Reduce `node_modules/` footprint (53M) | LOW | ⏳ | Only needed for Vitest. Consider moving JS tests to CI-only or using lighter test runner. |
| B21 | Add `Cache-Control` headers for static assets | LOW | ⏳ | Static JS/CSS served without cache headers. Add fingerprinting + long-lived cache. |
| B22 | Document Phase 17 voice endpoints in `docs/api.md` | LOW | ⏳ | API docs missing `/ws/transcribe`, `/ws/speak`, `POST /api/speak` endpoints. |
| B23 | Update `docs/architecture.md` with voice/STT/TTS section | LOW | ⏳ | Architecture docs don't cover Deepgram integration or WebSocket proxy pattern. |
| B24 | Add integration tests for WebSocket voice proxy | LOW | ⏳ | Current voice tests mock Deepgram SDK. No actual WebSocket integration tests. |

---

### Codebase Audit Findings (2026-02-22) — ✅ 23/24 Complete

Full audit covering security, architecture, code quality, dependencies, and deployment.
Remediated on 2026-02-23 via `fix/codebase-improvements-2` branch using 10 parallel worktree agents.

#### Priority: P0 — Security Critical ✅ All Done

| # | Task | Severity | Status | Notes |
|---|------|----------|--------|-------|
| A1 | Add security headers middleware | CRITICAL | ✅ Done | `SecurityHeadersMiddleware` in `src/api/middleware.py` — CSP, HSTS, X-Frame-Options, X-Content-Type-Options. |
| A2 | Guard JWT unverified fallback path | CRITICAL | ✅ Done | `ALLOW_UNVERIFIED_JWT` env var (defaults `false`). Unverified path blocked unless explicitly enabled. |
| A3 | Validate guest `session_id` format | CRITICAL | ✅ Done | UUID v4 validation before accepting guest session cookies. |
| A4 | Add `secure` flag to all cookies | HIGH | ✅ Done | Centralized `src/api/cookies.py` utility with environment-aware `secure` flag. |

#### Priority: P1 — Security & Quality ✅ All Done

| # | Task | Severity | Status | Notes |
|---|------|----------|--------|-------|
| A5 | Sanitize LLM output before `\| safe` rendering | HIGH | ✅ Done | Custom `\| sanitize` Jinja2 filter using `nh3` allowlist sanitization in 4 templates. |
| A6 | Escape f-string HTML construction | HIGH | ✅ Done | `markupsafe.escape()` applied to `_make_error_html()` and exercise feedback. |
| A7 | Replace `datetime.utcnow()` with `datetime.now(UTC)` | MEDIUM | ✅ Done | All source + test instances updated. Deprecation warnings reduced from 298 to 54. |
| A8 | Centralize input validation (language, level, days) | MEDIUM | ✅ Done | Shared `src/api/validation.py` with `VALID_LANGUAGES`, `VALID_LEVELS`, bounds checking. |
| A9 | Add non-root user to Dockerfile | MEDIUM | ✅ Done | `appuser` non-root user added to Dockerfile. |

#### Priority: P2 — Hardening ✅ 5/6 Done

| # | Task | Severity | Status | Notes |
|---|------|----------|--------|-------|
| A10 | ~~Implement per-IP rate limiting~~ | HIGH | ❌ Removed | User decision: current global rate limiting is sufficient. |
| A11 | Narrow remaining `except Exception` blocks | MEDIUM | ✅ Done | All 17 broad handlers narrowed to specific types (`APIError`, `httpx.HTTPError`, `anthropic.APIError`, etc.). |
| A12 | Sign review session cookies | MEDIUM | ✅ Done | `itsdangerous` signing via `sign_cookie_value()` / `unsign_json_cookie()` in `src/api/cookies.py`. |
| A13 | Implement JWT token refresh | MEDIUM | ✅ Done | Automatic token refresh middleware checks expiry and refreshes via Supabase API. |
| A14 | Consolidate language metadata (DRY) | MEDIUM | ✅ Done | `src/api/validation.py` — single source of truth for language/level constants. `_get_language_name()` removed from agent nodes. |
| A15 | Extract JSON parsing utility | LOW | ✅ Done | `src/agent/utils.py` with `extract_json_from_markdown()`. |

#### Priority: P3 — Tech Debt ✅ All Done

| # | Task | Severity | Status | Notes |
|---|------|----------|--------|-------|
| A16 | Re-enable mypy for `db/` and `services/` | MEDIUM | ✅ Done | `disallow_untyped_defs = true` for both modules. Type annotations added. |
| A17 | Add Dockerfile HEALTHCHECK | LOW | ✅ Done | `HEALTHCHECK` instruction added to Dockerfile. |
| A18 | Remove dead code | LOW | ✅ Done | Unused `Setting` model removed, legacy `CHECKPOINT_DB_PATH` + `get_checkpoint_db_path()` removed. |
| A19 | Extract stopwords to config | LOW | ✅ Done | Stopwords moved to `data/stopwords.json`, loaded at module level in respond node. |
| A20 | Fix `type: ignore` suppressions | LOW | ✅ Done | Annotated with specific mypy error codes. Unavoidable ones documented. |
| A21 | Reduce JWT error detail leakage | LOW | ✅ Done | Generic error message replaces `f"Invalid token: {e}"`. |
| A22 | Change `.env.example` DEBUG default | LOW | ✅ Done | `DEBUG=false` default + `ALLOW_UNVERIFIED_JWT=false` added. |
| A23 | Enforce coverage in CI | LOW | ✅ Done | `fail_ci_if_error: true` in Codecov action. CI now enforces coverage thresholds. |
| A24 | Reduce conversation version cookie max_age | LOW | ✅ Done | Reduced from 1 year to 30 days. |

---

### Previous Improvements (2026-02-18) — ✅ All Complete

<details>
<summary>Expand completed improvement backlog</summary>

#### Priority: High — ✅ All Done

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Fix `VocabularyRepository.upsert()` race condition | ✅ Done | Insert-first pattern catching PostgreSQL `23505`. `complete_lesson()` also switched to single `.upsert(on_conflict=...)`. `increment_correct()` documented as concurrency-limited. |
| 2 | Remove `get_supabase_admin()` from agent nodes | ✅ Done | User-scoped Supabase client flows through `ConversationState`/`ReviewState` → `supabase_client` field. `chat.py` passes `user_client` into graph state. |

#### Priority: Medium — ✅ All Done

| # | Task | Status | Files | Notes |
|---|------|--------|-------|-------|
| 3 | Extract shared `_get_llm()` factory | ✅ Done | `src/agent/llm.py` | Profile-based config: conversational, analysis, structured, creative, enhancement. |
| 4 | Fix `SupabaseClient = Any` type alias | ✅ Done | `src/api/supabase_client.py` | Now imports `supabase.Client as SupabaseClient`. |
| 5 | Add chat message length validation | ✅ Already done | `src/api/routes/chat.py` | `MAX_MESSAGE_LENGTH = 2000` already exists at line 198. |
| 6 | Fix `new_conversation` checkpoint clearing | ✅ Done | `src/api/routes/chat.py` | Conversation versioning via cookie — new UUID per "new conversation" creates fresh thread_id. |
| 7 | Narrow broad `except Exception` blocks | ✅ Done | `auth.py`, `service.py` | `AuthApiError` in auth routes, `(YAMLError, ValidationError, OSError)` in lesson service. |
| 8 | Move keyword filtering server-side in `get_due_by_keywords()` | ✅ Done | `src/db/repository.py` | Uses `.or_()` with `ilike` filters — no more fetching all rows. |

#### Priority: Low — ✅ All Done

| # | Task | Status | Files | Notes |
|---|------|--------|-------|-------|
| 9 | ~~Remove dead `EffectiveUser` code~~ | ❌ Not dead | `src/api/auth.py` | Actively used for guest session handling. Task invalid. |
| 10 | Delete dead `feedback.py` stub node | ✅ Done | Deleted | 51-line stub, never imported. |
| 11 | Remove stub methods in `VocabularyService` | ✅ Partial | `src/services/vocabulary.py` | `extract_vocabulary()` removed. `get_word_bank()` is NOT a stub — it calls `self._repo.get_recent()`. |
| 12 | Clean up f-string logging | ✅ Done | All agent nodes | Fixed across `scaffold.py`, `analyze.py`, `respond.py`, `review.py`. |
| 13 | Document `learn.py` route in architecture.md | ✅ Done | `docs/architecture.md` | Added Learn (Phase 14) section with endpoint signatures. |
| 14 | Update stale deployment configs | ✅ Done | `render.yaml`, `Dockerfile` | Replaced SQLite references with Supabase env vars. |
| 15 | Consider LLM instance caching | ✅ Done | `src/agent/llm.py` | Profile-based caching via `get_llm()` — instances reused per profile. |

</details>

---

### JavaScript Quality Improvements (2026-02-25 audit) — ✅ All Done

Identified during code review of `src/static/js/` (app.js, stream.js, voice.js — 1549 lines total).
All items resolved as part of Phase 16 ES Module Migration.

#### Priority: Medium — ✅ All Done

| # | Task | File | Status | Notes |
|---|------|------|--------|-------|
| J1 | Remove dead HTMX event handlers | `app.js` | ✅ Done | Dead handlers removed in ESM refactor |
| J2 | Cache DOM elements at init | `app.js` | ✅ Done | `dom.js` caches elements |
| J3 | Fix scroll throttle using `Math.random()` | `stream.js` | ✅ Done | `tokenCounter % 3` deterministic throttle |
| J4 | Cache send button reference in `stream.js` | `stream.js` | ✅ Done | `stream.js` caches send button |

#### Priority: Low / Cleanup — ✅ All Done

| # | Task | File | Status | Notes |
|---|------|------|--------|-------|
| J5 | Remove `console.log` in production | `app.js` | ✅ Done | `console.log` removed in ESM refactor |
| J6 | Remove unused `welcomeMessage` variable | `app.js` | ✅ Done | Dead variable removed in ESM refactor |
| J7 | Standardize `var` → `const`/`let` in `voice.js` | `voice.js` | ✅ N/A | Intentionally ES5 per ADR-009 (loaded as type="module" but uses var/prototype) |
| J8 | Sanitize HTMX error detail before console logging | `app.js` | ✅ Done | `htmx-handlers.js` logs sanitized |

#### Priority: High Effort (Future) — ✅ Done

| # | Task | Status | Notes |
|---|------|--------|-------|
| J9 | Add JS unit tests | ✅ Done | 186 Vitest tests across all modules |

### Future Ideas

| Task | Notes |
|------|-------|
| Scenario roleplay | Ordering food, booking hotel |
| Multiple AI personas | Beyond Hermano |
| Offline mode | PWA with service worker |

---

## Completed Phases

| Phase | Name | Key Deliverable |
|-------|------|-----------------|
| 0 | Project Setup | FastAPI + HTMX + Tailwind, CI/CD, pre-commit |
| 1 | Basic Chat | LangGraph StateGraph, level-adaptive responses |
| 2 | Grammar Feedback | Analyze node, gentle corrections UI |
| 3 | Scaffolding | Conditional routing, word banks, click-to-insert |
| 4 | Persistence | PostgresSaver checkpointing, session management |
| 5 | Supabase Auth | JWT auth, multi-user isolation, 829+ tests |
| 6 | Micro-Lessons | Pydantic models, 5 Spanish A0 lessons, HTMX player |
| 7 | Progress Tracking | Dashboard stats, vocabulary, charts, streaks |
| 8 | Guest Sessions | Session cookies, auth-gated data features |
| 9 | AI-Enhanced Lessons | LangGraph subgraphs, Hermano personalization |
| 10 | Content Expansion | 60 lessons (3 lang x 4 levels x 5 categories) |
| 11 | Nordic Design | 3 themes, pronunciation tips, collapsible UI |
| 12 | Spaced Repetition | SM-2 algorithm, review subgraphs, chat weaving |
| 13 | Mobile Responsive | Safe areas, dynamic viewport, touch-optimized |
| 14 | Learning Paths | PathService, AdaptiveService, learn routes (99 tests) |
| 15 | SSE Streaming | Real-time chat via Server-Sent Events |
| 16 | ES Module Migration | 6 JS modules, 186 Vitest tests, mobile hardening, TTS UX |
| 17 | Voice Conversation | Deepgram STT/TTS, WebSocket proxy, graceful degradation |

Design docs: `docs/design/phase*.md` | ADRs: `docs/adr/ADR-*.md`

---

## Session Logs

### 2026-02-27: P2 Audit Remediation — 10 MEDIUM Severity Items
- **Branch**: `fix/p2-audit-remediation` (PR #41)
- **Scope**: All 10 P2 (MEDIUM severity) findings from 2026-02-26 audit (B8-B17)
- **Method**: Direct implementation across 3 sessions on git worktree
- **Changes**:
  - **B15**: `get_supabase_admin()` cached with `@lru_cache`. `clear_supabase_cache()` clears both.
  - **B16**: Pydantic V2 `model_config = ConfigDict(from_attributes=True)` replaces V1 `class Config`.
  - **B11**: `get_llm()` cached with `@lru_cache(maxsize=8)`. `clear_llm_cache()` for test isolation.
  - **B13**: `ruff check --select F401,F841,ERA001` — all clean, no dead code.
  - **B10**: Graph compilation cached per checkpointer in `_graph_cache` dict. `clear_graph_cache()` helper.
  - **B12**: Review queries use `get_due_for_review()` + `get_in_rotation_count()` instead of `get_all()` + Python filter.
  - **B9**: REST TTS rate-limited with `@rate_limited()` decorator. WebSocket endpoints use `WebSocketMessageRateLimiter` sliding window.
  - **B14**: Narrowed `except Exception` to specific types (`httpx.HTTPError`, `ConnectionError`, `OSError`) in voice routes.
  - **B17**: `python-json-logger` dependency, `LOG_FORMAT` setting, JSON formatter in `main.py`.
  - **B8**: Per-request CSP nonce (`secrets.token_urlsafe(16)`) replaces `unsafe-inline` in script-src. All `<script>` tags across 6 templates use `nonce="{{ request.state.csp_nonce }}"`.
- **Test isolation**: `clear_llm_cache()`, `clear_graph_cache()`, `clear_supabase_cache()` added to autouse `reset_settings` fixture in conftest.py. Fixed PostgREST mock chaining in `csrf_app` fixture.
- **Key new files**: `tests/api/test_security_headers.py` (7 CSP nonce tests)
- **Key modified files**: `src/api/middleware.py`, `src/api/rate_limit.py`, `src/api/routes/voice.py`, `src/agent/graph.py`, `src/agent/llm.py`, `src/db/client.py`, `src/db/models.py`, `src/services/review.py`, `src/db/repository.py`, `src/config.py`, `src/api/main.py`, `pyproject.toml`, `src/templates/base.html` + 4 other templates
- **Results**: 1981 Python tests + 187 JS tests passing, ruff clean, mypy clean (58 source files)
- **E2E Validated**: Playwright MCP verified chat, lessons, and progress pages load with 0 JS errors. CSP nonce confirmed in response headers and rendered HTML.

### 2026-02-26: P1 Audit Remediation — 7 HIGH Severity Items
- **Branch**: `fix/p1-audit-remediation`
- **Scope**: All 7 P1 (HIGH severity) findings from 2026-02-26 audit (B1-B7)
- **Method**: Mix of parallel worktree agents and direct implementation across 2 sessions
- **Changes**:
  - **B1**: WebSocket auth — `_authenticate_websocket()` validates JWT cookie on `/ws/transcribe` and `/ws/speak`. Rejects with code 4001.
  - **B2**: CSRF middleware — `CSRFMiddleware` using OWASP custom-header pattern. `HX-Request: true` (HTMX) or `X-Requested-With: XMLHttpRequest` (fetch). 15 tests.
  - **B3**: `VocabularyRepository.get_by_id()` — single-row lookup, replaces full-table scan in ReviewService.
  - **B4**: Checkpointer docs — documented singleton pattern, dev limitation accepted.
  - **B5**: Layer violations — created `src/config.py`, `src/validation.py`, `src/db/client.py` as canonical modules. Old API locations are re-export shims. 8 inner-layer imports fixed.
  - **B6**: ReviewService — refactored to use VocabularyRepository exclusively, no more direct `client.table()` calls.
  - **B7**: Lesson completion — extracted business logic from `lessons.py` (817→468 lines) into `src/services/lesson_completion.py`.
- **Key new files**: `src/config.py`, `src/validation.py`, `src/db/client.py`, `src/services/lesson_completion.py`, `tests/api/test_csrf.py`
- **Test patches**: ~30 test files updated for relocated mock targets (patch paths changed from `src.api.routes.lessons.*` → `src.services.lesson_completion.*`, `src.api.config.*` → `src.config.*`, etc.)
- **Results**: 1971 Python tests passing (up from 1954), ruff clean, mypy clean (58 source files)

### 2026-02-26: Comprehensive Codebase Audit (Round 2)
- **Branch**: `feat/phase16-esm-migration` (12 commits ahead of main)
- **Scope**: Full multi-dimensional audit — security, performance, architecture, code quality, workspace hygiene
- **Method**: 3 parallel specialized agents (security-engineer, architecture-strategist, performance-engineer) + direct quality checks
- **Direct checks**:
  - `uv run python -m pytest -q --tb=line` → 1954 passed, 5 skipped
  - `uv run ruff check src/ tests/` → all clean
  - `uv run mypy src/` → 0 issues in 54 files
  - `npm test` → 186 JS tests passed
  - Workspace hygiene: 6 orphan PNGs, 17 stale branches, 53M node_modules
- **Results**: 52 total findings across 7 dimensions
  - **Security** (12 findings): WebSocket auth gaps, CSRF missing, CSP too permissive
  - **Performance** (17 findings): Full-table scans in review flow, uncached graph/LLM, no connection pooling
  - **Architecture** (12 findings): 9 layer violations, repository bypass, SRP violations in route files
  - **Workspace** (6 findings): Orphan files, stale branches, node_modules bloat
- **Dimension scores**: Code Quality 8/10, Testing 9/10, Architecture 6/10, Security 7/10, Performance 5/10, Workspace Hygiene 5/10, CI/CD 8/10
- **Action plan**: 24 items (B1-B24) in 3 tiers — 7 HIGH (P1), 10 MEDIUM (P2), 7 LOW (P3)
- **Positive findings**: Clean lint/mypy, comprehensive test suite, strong auth flow, good security headers (post-Feb-23 audit)
- **Vue/TS migration evaluated**: Recommended against — complexity doesn't justify it for ~1500 lines of vanilla JS in server-rendered HTMX app

### 2026-02-25: Phase 16 — ES Module Migration + Voice UX
- **Branch**: `feat/phase16-esm-migration`
- **Scope**: Monolithic JS refactor to 6 ES modules, 186 JS tests, CI integration, mobile-first fixes, TTS UX improvements
- **Key changes**:
  - `app.js` (380 lines) + `stream.js` (388 lines) → 6 modules: main.js, dom.js, stream.js, htmx-handlers.js, shortcuts.js, scaffold.js
  - `voice.js` migrated to module loading with AudioWorklet PCM processor
  - 11 mobile-first JS fixes: touch focus, scroll throttle, keyboard handling, escapeHtml quotes
  - 186 Vitest tests (dom: 37, stream: 24, voice: 87, scaffold: 15, shortcuts: 12, htmx-handlers: 11)
  - CI parallel `test-js` job with Node.js 22
  - Floating TTS stop bar, concurrent TTS fix, mobile click reliability
- **Results**: 2140+ total tests (1954 Python + 186 JS), all passing

### 2026-02-23: Security Audit Remediation — Full Sweep
- **Branch**: `fix/codebase-improvements-2`
- **Scope**: 23 of 24 audit items (A1-A24, A10 removed per user decision)
- **Method**: 10 parallel worktree agents across 3 sessions, merge conflict resolution, test alignment
- **Session 1** (P0+P1): 5 parallel agents completed A1-A9 security critical + quality items
  - A1: SecurityHeadersMiddleware (CSP, HSTS, X-Frame-Options)
  - A2: ALLOW_UNVERIFIED_JWT env guard
  - A3: UUID v4 guest session validation
  - A4: Centralized cookie utility (`src/api/cookies.py`)
  - A5: `nh3` XSS sanitization via `| sanitize` Jinja2 filter
  - A6: `markupsafe.escape()` for f-string HTML
  - A7: `datetime.utcnow()` → `datetime.now(UTC)` (warnings 298→54)
  - A8: Shared validation module (`src/api/validation.py`)
  - A9: Non-root Dockerfile user
  - Plus P3 quick wins: A17, A18, A19, A21, A22
- **Session 2** (P2+P3): 5 parallel agents completed remaining items
  - A11: Narrowed 17 `except Exception` → specific types across src/
  - A12: `itsdangerous` cookie signing for review sessions
  - A13: JWT token refresh middleware
  - A14: Consolidated language metadata into validation module
  - A15: `extract_json_from_markdown()` utility
  - A16+A20+A23: mypy strictness, type:ignore annotations, CI coverage enforcement
  - A24: Cookie max_age 1yr→30d
- **Session 3**: Fixed 20+ test failures from exception narrowing + signed cookie changes
  - Updated ~20 test mocks across 10 files to raise matching specific exceptions
  - Updated review test helpers for signed cookies
  - Added missing VocabularyRepository/ReviewService mocks
- **Results**: 1893 tests passing (up from 1820), ruff clean, mypy clean
- **Key new files**: `src/api/cookies.py`, `src/api/middleware.py`, `src/api/validation.py`, `src/agent/utils.py`, `data/stopwords.json`

### 2026-02-23: Phase 15 SSE Streaming + Bug Fixes
- **Branch**: `feature/sse-streaming` → merged to main as PR #29
- **Deliverables**: `POST /chat/stream` SSE endpoint, `src/api/streaming.py`, `src/static/js/stream.js`, 34 new tests
- **Bug Fix** (PR #30): SSE line ending normalization (CRLF→LF), window.addUserMessage/escapeHtml exports for stream.js
- **Docs**: ADR-009 (ES module refactor), Phase 16 design doc for planned JS restructuring

### 2026-02-22: Comprehensive Codebase Audit
- **Branch**: `main`
- **Scope**: Multi-dimensional audit — security, architecture, code quality, dependencies, deployment
- **Method**: 3 parallel background agents (security-engineer, architecture-explorer, dependency-explorer) + main thread analysis
- **Results**: 1820 tests pass (97% coverage), clean lint/format/mypy, 298 deprecation warnings
- **Findings**: 24 items cataloged (A1-A24): 4 P0 (security critical), 5 P1 (this sprint), 6 P2 (next sprint), 9 P3 (backlog)
- **Key Critical Issues**: Unverified JWT fallback, missing security headers, unvalidated guest session_id, inconsistent cookie `secure` flags
- **Architecture Strengths**: Clean LangGraph pipeline, proper service/repo separation, smart upsert strategy, accurate SM-2 implementation, comprehensive logging
- **Positive Findings**: No eval/exec/os.system, no hardcoded secrets, no SQL injection, no circular imports, rate limiting present on auth+chat

### 2026-02-22: Codebase Improvements — Full Backlog Sweep
- **Branch**: `fix/codebase-improvements`
- **Session 1**: Completed tasks #1, #2, #3, #5, #10, #11 (partial), #12 from the improvement backlog
  - Key fixes: VocabularyRepository race condition (insert-first pattern), admin client removal from agent nodes (RLS enforcement via state), shared LLM factory extraction
  - Discovered: Task #5 already done, Task #9 (`EffectiveUser`) is NOT dead code, Task #11 `get_word_bank()` is not a stub
  - 4 parallel subagents, 20 files changed, net -107 lines
- **Session 2**: Completed remaining tasks #4, #6, #7, #8, #13, #14, #15 via 7 parallel worktree agents
  - Task #4: `SupabaseClient = Any` → `from supabase import Client as SupabaseClient`
  - Task #6: Conversation versioning via `conversation_version` cookie — fresh thread_id per "new conversation"
  - Task #7: Narrowed `except Exception` → `except AuthApiError` (auth), `except (YAMLError, ValidationError, OSError)` (lessons)
  - Task #8: Server-side keyword filtering with `.or_()` + `ilike` — no longer fetches all due words
  - Task #13: Documented learn.py routes in architecture.md
  - Task #14: Dockerfile + render.yaml updated for Supabase (removed SQLite references)
  - Task #15: LLM instance caching already done via profile-based `get_llm()`
  - 11 new tests added (10 chat, 1 repository), 1820 tests passing

### 2026-02-19: Phase 14 — Learning Paths + Adaptive Recommendations
- **Branch**: `feature/phase14-learning-paths`
- Created `src/services/paths.py` (PathService), `src/services/adaptive.py` (AdaptiveService), `src/api/routes/learn.py`, 3 templates
- 99 new tests: `tests/services/test_paths.py` (27), `tests/services/test_adaptive.py` (49), `tests/api/routes/test_learn.py` (23)
- Key decision: No new DB tables — paths are static config, progress derived from existing `lesson_progress`

### 2026-02-04: Phase 11 — Collapsible Pronunciation Tips UI
- Added `PronunciationTip` TypedDict, updated analyze_node to 3-tuple return
- Created `pronunciation_tips.html` partial with Alpine.js expand/collapse
- A0 auto-expands with encouragement text; A1+ collapsed by default

### 2026-02-01: Phase 10 — Lesson Content Expansion
- Parallel 3-agent pattern: Spanish, German, French simultaneously (~65% time savings)
- Created 55 new YAML lesson files, updated LessonService with composite keys

### 2026-01-30: Phase 9 — AI-Enhanced Lessons
- Created LessonState, lesson subgraph (load_step → enhance_step → END)
- Exercise validation subgraph with AI feedback
- Fixed circular imports via lazy imports in node files

### 2025-01-18: Phase 4-5 — Persistence + Supabase Auth Planning
- Phase 4: Checkpointer module, session management, 72 new tests
- Phase 5: ADR-001 for Supabase, design doc, found AsyncSqliteSaver bug → MemorySaver fallback
- Phase 3: Scaffold node, conditional routing, click-to-insert word banks

### 2025-01-17: Phases 1-2 + Test Coverage Upgrade
- Phase 1: LangGraph StateGraph with respond node, HTMX chat UI
- Phase 2: Analyze node for grammar detection, collapsible feedback UI
- Test coverage: 37% → 98% (328 → 641 tests)

---

## Notes for Future Agents

### Quick Reference
- **Personality**: "Hermano" — friendly big brother tutor (see `src/agent/prompts.py`)
- **Language Adapter**: `LANGUAGE_ADAPTER` dict in prompts.py — never use string replacement
- **Auth Flow**: JWT in httponly cookie → automatic refresh → FastAPI validates → Supabase Postgres
- **Guest Flow**: Session cookie (UUID v4 validated) for chat, auth-gated data features (progress, vocab, review)
- **Checkpointer**: PostgresSaver for production, MemorySaver fallback for dev
- **Key Constraint**: `lesson_progress` stores base IDs without language/level scoping; PathService always scopes calls
- **Cookie Security**: All cookies go through `src/api/cookies.py` — signed with `itsdangerous`, environment-aware `secure` flag

### Security Architecture (Post-Audit 2026-02-27)
- **CSP Nonce**: Per-request `secrets.token_urlsafe(16)` nonce in `script-src` replaces `unsafe-inline`. Generated before `call_next()`, stored on `request.state.csp_nonce`. All `<script>` tags use `nonce="{{ request.state.csp_nonce }}"`. `unsafe-eval` retained for Tailwind CDN eval() dependency.
- **CSRF Protection**: `CSRFMiddleware` — OWASP custom-header pattern. POST/PUT/DELETE/PATCH require `HX-Request: true` or `X-Requested-With: XMLHttpRequest`. Returns 403 without.
- **WebSocket Auth**: `/ws/transcribe` and `/ws/speak` validate JWT cookie on connect. Reject with code 4001 if invalid.
- **Security Headers**: `SecurityHeadersMiddleware` adds CSP (nonce-based), HSTS, X-Frame-Options, X-Content-Type-Options
- **Middleware Stack Order**: SecurityHeaders → CSRF → CORS (last `add_middleware()` runs first/outermost)
- **XSS Protection**: LLM output sanitized via `nh3` through `| sanitize` Jinja2 filter; f-string HTML uses `markupsafe.escape()`
- **Cookie Signing**: Review session cookies signed with `itsdangerous` via `sign_cookie_value()` / `unsign_json_cookie()`
- **JWT Unverified Path**: Blocked by default via `ALLOW_UNVERIFIED_JWT=false`; only enable in development
- **Input Validation**: Canonical location `src/validation.py` — language, level, and days bounds checking. `src/api/validation.py` is a re-export shim.
- **Exception Handling**: All `except` blocks catch specific types (`APIError`, `httpx.HTTPError`, `anthropic.APIError`, `ConnectionError`, `OSError`, etc.)
- **Rate Limiting**: Global function-level for chat/auth (not per-IP). Voice endpoints: REST `@rate_limited()` (10/60s), WebSocket `WebSocketMessageRateLimiter` (30 msgs/60s per connection).

### Layer Architecture (Post-P1 Remediation)
Canonical modules at `src/` level prevent inner layers from importing API:
- `src/config.py` — Settings + get_settings (canonical). `src/api/config.py` is a re-export shim.
- `src/validation.py` — VALID_LANGUAGES, VALID_LEVELS, helpers (canonical). `src/api/validation.py` is a re-export shim.
- `src/db/client.py` — get_supabase, get_supabase_admin (canonical). `src/api/supabase_client.py` is a re-export shim.
- Inner layers (agent/, services/, db/) import from canonical locations. API layer can import from either.

### Key New Files (from audit remediation)
- `src/config.py` — Canonical Settings + get_settings (+ `LOG_FORMAT` setting for P2)
- `src/validation.py` — Canonical domain validation constants and helpers
- `src/db/client.py` — Canonical Supabase client factory (+ `@lru_cache` on admin for P2)
- `src/services/lesson_completion.py` — Lesson completion business logic (extracted from lessons.py)
- `tests/api/test_csrf.py` — CSRF middleware test suite (15 tests)
- `tests/api/test_security_headers.py` — CSP nonce test suite (7 tests, P2)
- `src/api/cookies.py` — Centralized cookie utility (signing, secure flag, set/delete helpers)
- `src/api/middleware.py` — SecurityHeadersMiddleware (CSP nonce) + CSRFMiddleware
- `src/api/rate_limit.py` — Rate limiting infrastructure (+ `WebSocketMessageRateLimiter` for P2)
- `src/agent/utils.py` — `extract_json_from_markdown()` utility
- `data/stopwords.json` — Extracted stopwords config

### Key Docs
- `docs/product.md` — What we're building
- `docs/architecture.md` — How we're building it
- `docs/codebase-summary.md` — Full codebase crash course
- `docs/design/` — Phase-by-phase design documents
- `docs/adr/` — Architectural Decision Records

### Quick Commands
```bash
make install        # Install dependencies
make install-hooks  # Install pre-commit hooks
make dev            # Run dev server
make test           # Run tests
make check          # Run all checks (lint + typecheck)
```
