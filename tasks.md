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

**Branch**: `docs/phase17-voice-deepgram` (active development)
**Phase**: Phase 17 — Voice Conversation (Deepgram STT/TTS)
**Test Coverage**: 1952 tests passing, 5 skipped, 97% coverage (52 warnings)
**Last Audit**: 2026-02-22 (multi-dimensional: security, architecture, dependencies, deployment)
**Audit Remediation**: 2026-02-23 — 23 of 24 items complete (A1-A24, excluding A10)

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
| Voice Conversation | 17 | Deepgram STT (Nova-3) + TTS (Aura-2), WebSocket proxy, graceful degradation |

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

### Future Ideas

| Task | Notes |
|------|-------|
| ~~Voice input/output~~ | ~~Speech-based practice~~ → **Phase 17 in progress** |
| Scenario roleplay | Ordering food, booking hotel |
| Multiple AI personas | Beyond Hermano |
| Offline mode | PWA with service worker |
| ES Module migration | See ADR-009 and `docs/design/phase16-esm.md` |

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

Design docs: `docs/design/phase*.md` | ADRs: `docs/adr/ADR-*.md`

---

## Session Logs

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

### Security Architecture (Post-Audit 2026-02-23)
- **Security Headers**: `SecurityHeadersMiddleware` adds CSP, HSTS, X-Frame-Options, X-Content-Type-Options
- **XSS Protection**: LLM output sanitized via `nh3` through `| sanitize` Jinja2 filter; f-string HTML uses `markupsafe.escape()`
- **Cookie Signing**: Review session cookies signed with `itsdangerous` via `sign_cookie_value()` / `unsign_json_cookie()`
- **JWT Unverified Path**: Blocked by default via `ALLOW_UNVERIFIED_JWT=false`; only enable in development
- **Input Validation**: Centralized in `src/api/validation.py` — language, level, and days bounds checking
- **Exception Handling**: All `except` blocks catch specific types (`APIError`, `httpx.HTTPError`, `anthropic.APIError`, etc.)
- **Rate Limiting**: Global function-level (not per-IP) — acceptable for current scale

### Key New Files (from audit remediation)
- `src/api/cookies.py` — Centralized cookie utility (signing, secure flag, set/delete helpers)
- `src/api/middleware.py` — Security headers middleware
- `src/api/validation.py` — Shared input validation (language, level, days)
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
