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

**Branch**: `main`
**Phase**: Phase 14 Complete
**Test Coverage**: 1820 tests passing, 97% coverage (298 deprecation warnings)
**Last Audit**: 2026-02-22 (multi-dimensional: security, architecture, dependencies, deployment)

### What's Working

| Feature | Phase | Notes |
|---------|-------|-------|
| Hermano Personality | 1 | Friendly big brother tutor, 4 levels (A0-B1) |
| 3 Languages | 1 | Spanish, German, French via LANGUAGE_ADAPTER |
| Grammar Feedback | 2 | Gentle corrections with expandable tips |
| Scaffolding | 3 | Word banks, hints, sentence starters (A0-A1) |
| Conversation Persistence | 4 | PostgresSaver with MemorySaver fallback |
| Supabase Auth | 5 | JWT tokens + guest sessions |
| 60 Micro-Lessons | 6+10 | 3 languages x 4 levels x 5 categories |
| Progress Dashboard | 7 | Stats, vocabulary, charts |
| Guest Sessions | 8 | Chat-only access, auth-gated data features |
| AI-Enhanced Lessons | 9 | LangGraph subgraphs, Hermano personalization |
| Nordic Minimal Design | 11 | 3 themes (Light/Dark/Ocean), pronunciation tips |
| Spaced Repetition | 12 | SM-2 algorithm, chat weaving, dedicated review mode |
| Mobile Responsive | 13 | Safe areas, dynamic viewport, touch-optimized |
| Learning Paths | 14 | Static paths + adaptive daily recommendations |

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
Auth: Supabase Auth → JWT cookie → Protected routes
```

---

## Up Next

### Codebase Audit Findings (2026-02-22)

Full audit covering security, architecture, code quality, dependencies, and deployment.
Ordered by severity. Previous improvement backlog (2026-02-18) is complete — see [Session Logs](#session-logs).

#### Priority: P0 — Security Critical (Fix Before Production)

| # | Task | Severity | Files | Status | Notes |
|---|------|----------|-------|--------|-------|
| A1 | Add security headers middleware | CRITICAL | `src/api/main.py` | ⬜ Todo | No CORS, no CSP, no X-Frame-Options, no HSTS. Add `CORSMiddleware` + custom security headers middleware. |
| A2 | Guard JWT unverified fallback path | CRITICAL | `src/api/auth.py:87-93,108-156` | ⬜ Todo | `_decode_token_unverified()` accepts any forged JWT when Supabase not configured. Add explicit env guard (e.g. `ALLOW_UNVERIFIED_JWT`) that defaults to `false`. |
| A3 | Validate guest `session_id` format | CRITICAL | `src/api/auth.py:260-262` | ⬜ Todo | Raw cookie value used as identity with zero validation. Enforce UUID v4 format before accepting. |
| A4 | Add `secure` flag to all cookies | HIGH | `chat.py`, `review.py`, `lessons.py`, `session.py` | ⬜ Todo | Only auth cookie sets `secure=True`. 7+ other cookie setters omit it. Create centralized cookie utility. |

#### Priority: P1 — Security & Quality (This Sprint)

| # | Task | Severity | Files | Status | Notes |
|---|------|----------|-------|--------|-------|
| A5 | Sanitize LLM output before `\| safe` rendering | HIGH | `src/templates/partials/message_pair.html`, `message.html`, `lesson_step_enhanced.html`, `exercise_feedback_enhanced.html` | ⬜ Todo | Stored XSS risk. Use `nh3` or `bleach` to whitelist-sanitize LLM HTML output server-side. |
| A6 | Escape f-string HTML construction | HIGH | `src/api/routes/chat.py:57-58`, `lessons.py:478-484` | ⬜ Todo | `_make_error_html()` and exercise feedback use raw f-string interpolation. Use `markupsafe.escape()` or template rendering. |
| A7 | Replace `datetime.utcnow()` with `datetime.now(UTC)` | MEDIUM | `src/db/models.py:19,20,32,54`, `src/lessons/models.py:367` + tests | ⬜ Todo | Deprecated since Python 3.12. Produces 298 test warnings. 5 source instances + ~10 test instances. |
| A8 | Centralize input validation (language, level, days) | MEDIUM | `progress.py`, `learn.py`, `lessons.py`, `review.py` | ⬜ Todo | Chat route validates correctly; all other routes accept arbitrary values. Extract shared `VALID_LANGUAGES`/`VALID_LEVELS` constants + `days` bounds (1-365). |
| A9 | Add non-root user to Dockerfile | MEDIUM | `Dockerfile` | ⬜ Todo | Container runs as root. Add `RUN useradd -m appuser` + `USER appuser`. |

#### Priority: P2 — Hardening (Next Sprint)

| # | Task | Severity | Files | Status | Notes |
|---|------|----------|-------|--------|-------|
| A10 | Implement per-IP rate limiting | HIGH | `src/api/rate_limit.py` | ⬜ Todo | Current rate limiter is global (not per-IP). One client can exhaust limit for all users. Consider `slowapi` or Redis-backed. |
| A11 | Narrow remaining `except Exception` blocks | MEDIUM | 17 instances across `src/` | ⬜ Todo | Auth routes partially narrowed (prev sprint). Still 17 broad handlers in agent nodes, routes, services. Catch specific exceptions per context. |
| A12 | Sign review session cookies | MEDIUM | `src/api/routes/review.py:282-288` | ⬜ Todo | Session state stored as plain unsigned JSON in cookie. Users can tamper with scores/word_ids. Use `itsdangerous` or server-side storage. |
| A13 | Implement JWT token refresh | MEDIUM | `src/api/routes/auth.py` | ⬜ Todo | Cookie persists 7 days but Supabase JWT expires in ~1 hour. No refresh mechanism. Users silently lose auth after 1 hour. |
| A14 | Consolidate language metadata (DRY) | MEDIUM | `scaffold.py`, `analyze.py`, `prompts.py`, `paths.py` | ⬜ Todo | `_get_language_name()` duplicated in 2 files. Language metadata fragmented across 3+ modules. Extract to `src/shared/languages.py`. |
| A15 | Extract JSON parsing utility | LOW | `scaffold.py`, `analyze.py` | ⬜ Todo | Identical markdown→JSON extraction pattern duplicated. Create `src/agent/utils.py` with `extract_json_from_markdown()`. |

#### Priority: P3 — Tech Debt (Backlog)

| # | Task | Severity | Files | Status | Notes |
|---|------|----------|-------|--------|-------|
| A16 | Re-enable mypy for `db/` and `services/` | MEDIUM | `pyproject.toml:140-145` | ⬜ Todo | `disallow_untyped_defs = false` for both. Add annotations incrementally. |
| A17 | Add Dockerfile HEALTHCHECK | LOW | `Dockerfile` | ⬜ Todo | Render has health check configured, but Docker itself doesn't. |
| A18 | Remove dead code | LOW | `src/db/models.py` (Setting), `src/agent/checkpointer.py:25,141-151` (SQLite legacy) | ⬜ Todo | Unused `Setting` model, legacy `CHECKPOINT_DB_PATH` + `get_checkpoint_db_path()`. |
| A19 | Extract stopwords to config | LOW | `src/agent/nodes/respond.py:40-270` | ⬜ Todo | 170+ line hardcoded stopwords set. Move to `src/shared/stopwords.py` or YAML config. |
| A20 | Fix `type: ignore` suppressions | LOW | `src/agent/llm.py:68-71`, `src/api/rate_limit.py:55,71` | ⬜ Todo | 7 instances. Some unavoidable (Anthropic SDK), some fixable (ratelimit stubs). |
| A21 | Reduce JWT error detail leakage | LOW | `src/api/auth.py:153-156` | ⬜ Todo | `f"Invalid token: {e}"` exposes PyJWT internals. Use generic message. |
| A22 | Change `.env.example` DEBUG default | LOW | `.env.example:39` | ⬜ Todo | Defaults to `DEBUG=true`. Should be `false` for production safety. |
| A23 | Enforce coverage in CI | LOW | `.github/workflows/ci.yml:125` | ⬜ Todo | `fail_ci_if_error: false` in Codecov action. pyproject.toml enforces locally but CI doesn't. |
| A24 | Reduce conversation version cookie max_age | LOW | `src/api/routes/chat.py:328` | ⬜ Todo | 1-year max_age is excessive. Reduce to 30 days. |

---

### Previous Improvements (2026-02-18) — ✅ All Complete

<details>
<summary>Expand completed improvement backlog</summary>

#### Priority: 🔴 High — ✅ All Done

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Fix `VocabularyRepository.upsert()` race condition | ✅ Done | Insert-first pattern catching PostgreSQL `23505`. `complete_lesson()` also switched to single `.upsert(on_conflict=...)`. `increment_correct()` documented as concurrency-limited. |
| 2 | Remove `get_supabase_admin()` from agent nodes | ✅ Done | User-scoped Supabase client flows through `ConversationState`/`ReviewState` → `supabase_client` field. `chat.py` passes `user_client` into graph state. |

#### Priority: 🟡 Medium — ✅ All Done

| # | Task | Status | Files | Notes |
|---|------|--------|-------|-------|
| 3 | Extract shared `_get_llm()` factory | ✅ Done | `src/agent/llm.py` | Profile-based config: conversational, analysis, structured, creative, enhancement. |
| 4 | Fix `SupabaseClient = Any` type alias | ✅ Done | `src/api/supabase_client.py` | Now imports `supabase.Client as SupabaseClient`. |
| 5 | Add chat message length validation | ✅ Already done | `src/api/routes/chat.py` | `MAX_MESSAGE_LENGTH = 2000` already exists at line 198. |
| 6 | Fix `new_conversation` checkpoint clearing | ✅ Done | `src/api/routes/chat.py` | Conversation versioning via cookie — new UUID per "new conversation" creates fresh thread_id. |
| 7 | Narrow broad `except Exception` blocks | ✅ Done | `auth.py`, `service.py` | `AuthApiError` in auth routes, `(YAMLError, ValidationError, OSError)` in lesson service. |
| 8 | Move keyword filtering server-side in `get_due_by_keywords()` | ✅ Done | `src/db/repository.py` | Uses `.or_()` with `ilike` filters — no more fetching all rows. |

#### Priority: 🟢 Low — ✅ All Done

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
| Voice input/output | Speech-based practice |
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

Design docs: `docs/design/phase*.md` | ADRs: `docs/adr/ADR-*.md`

---

## Session Logs

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
- **Auth Flow**: JWT in httponly cookie → FastAPI validates → Supabase Postgres
- **Guest Flow**: Session cookie for chat, auth-gated data features (progress, vocab, review)
- **Checkpointer**: PostgresSaver for production, MemorySaver fallback for dev
- **Key Constraint**: `lesson_progress` stores base IDs without language/level scoping; PathService always scopes calls

### Audit Context (2026-02-22)
- **Security Priority**: P0 items (A1-A4) must be fixed before any production deployment
- **Cookie Pattern**: Auth cookies use `secure=True`, all others don't — needs centralized utility
- **Exception Handling**: Auth routes partially narrowed (sprint 2026-02-22), but 17 broad `except Exception` remain across agent nodes and routes
- **Language Metadata**: Duplicated in 3+ places — consolidation into shared module will fix both DRY and input validation issues
- **Template XSS**: `| safe` filter used on LLM output in 4 templates — sanitize server-side before rendering
- **Rate Limiting**: Global (function-level), not per-IP — single abusive client can lock out all users

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
