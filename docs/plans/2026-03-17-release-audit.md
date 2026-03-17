# Habla Hermano: General Release Audit

**Date**: 2026-03-17
**Scope**: Full codebase audit for public launch (Render) + open-source release (GitHub)
**Methodology**: 8 parallel specialized agents auditing security, code quality, production readiness, open-source readiness, API/data integrity, frontend/UX, performance, and deployment/ops
**Codebase**: ~48K lines Python (70 files), 13 JS modules, 37 Jinja2 templates, 66 test files

---

## Executive Summary

The codebase is well-architected with strong foundations: comprehensive test coverage (2,270+ tests), clean linting (ruff + mypy strict), proper separation of concerns, and thoughtful security layers (Fernet encryption, RLS, CSRF, CSP). However, several **release-blocking issues** must be addressed before public deployment.

**Critical blockers** (P0): 9 findings across security, open-source hygiene, accessibility, and data integrity.
**High priority** (P1): 24 findings requiring attention before or shortly after launch.
**Medium priority** (P2): 38 findings for post-launch improvement.
**Low priority** (P3): 20 findings for backlog.

---

## P0 -- Release Blockers

These MUST be fixed before any public release.

### SEC-1: Default SECRET_KEY ships as a known string
- **File**: `src/config.py:55`
- **Domain**: Security, Production, Deployment
- **Description**: `SECRET_KEY` defaults to `"change-me-to-a-random-string"`. This value governs cookie signing (itsdangerous), PBKDF2 key derivation for Fernet encryption, and all encrypted data at rest. If a deployer forgets to set the env var, the application starts successfully with a publicly known key. Any attacker can forge sessions and decrypt all PII.
- **Fix**: Add a startup validator that refuses to start when `SECRET_KEY` equals the default and `DEBUG=False`. Make it a required field with no default.

### SEC-2: Default ENCRYPTION_SALT is predictable
- **File**: `src/config.py:58`
- **Domain**: Security, Deployment
- **Description**: `ENCRYPTION_SALT` defaults to `"habla-hermano-encryption-v1"`. Combined with SEC-1, an attacker who knows the codebase (it's open-source) can derive the exact Fernet key and decrypt all PII fields and checkpoint blobs.
- **Fix**: Require `ENCRYPTION_SALT` to be explicitly set via environment variable in production, or auto-generate and persist on first run.

### SEC-3: SECURITY DEFINER RPC functions bypass RLS
- **File**: `migrations/003_atomic_counter_operations.sql:18-114`
- **Domain**: Data Integrity, Security
- **Description**: All four vocabulary RPC functions (`vocabulary_increment_correct`, `vocabulary_increment_seen`, `vocabulary_upsert_increment`, `vocabulary_update_sm2`) use `SECURITY DEFINER`, executing with superuser privileges. They accept a `p_user_id` parameter as a filter but bypass all RLS. A direct PostgREST `rpc(...)` call with a forged `p_user_id` can modify another user's vocabulary records.
- **Fix**: Change to `SECURITY INVOKER` (respects RLS) or add `AND user_id = auth.uid()` inside each function body, removing the `p_user_id` parameter.

### OSS-1: No LICENSE file
- **File**: Repository root
- **Domain**: Open-Source, Legal
- **Description**: `pyproject.toml` declares `license = "MIT"` but no LICENSE file exists. Without it, the code is legally "all rights reserved" regardless of metadata.
- **Fix**: Create a `LICENSE` file with the full MIT License text.

### OSS-2: No README.md
- **File**: Repository root
- **Domain**: Open-Source
- **Description**: The first thing any visitor sees. `pyproject.toml` references `readme = "README.md"` but the file doesn't exist. Screenshots exist in `docs/screenshots/`.
- **Fix**: Create a comprehensive README with project description, screenshots, quickstart, tech stack, and link to docs.

### OSS-3: Verify secrets never committed to git history
- **File**: `.env` (on disk, gitignored)
- **Domain**: Open-Source, Security
- **Description**: Live API keys (Anthropic, Supabase, Deepgram) exist in the local `.env`. While gitignored, if ever committed in history, they are leaked the moment the repo goes public.
- **Fix**: Run `git log --all -p -- .env` and `trufflehog` on the full history. Rotate ALL API keys before public release regardless.

### A11Y-1: Sidebar has no focus trap or ARIA semantics
- **File**: `src/templates/partials/thread_sidebar.html:87-93`
- **Domain**: Frontend, Accessibility
- **Description**: The sidebar `<aside>` has no `role="dialog"`, no `aria-label`, no focus trap, and no `aria-modal`. Keyboard users can tab behind the overlay. Screen readers cannot detect the sidebar opening.
- **Fix**: Add `role="dialog"`, `aria-label="Navigation sidebar"`, `aria-modal="true"`. Implement focus trap and inert main content.

### A11Y-2: Dropdown menus lack keyboard navigation
- **File**: `src/templates/partials/app_header.html:62-138`
- **Domain**: Frontend, Accessibility
- **Description**: Language and level selector dropdowns use click-only interaction. No `aria-expanded`, no `role="listbox"/"option"`, no arrow-key navigation, no Escape-to-close.
- **Fix**: Add full ARIA listbox pattern with keyboard navigation.

### CQ-1: `chat.py` is a 937-line god file with 4 complexity suppressions
- **File**: `src/api/routes/chat.py`
- **Domain**: Code Quality
- **Description**: Handles page rendering, thread content, sync chat, SSE streaming (freeform + lesson), error streaming, and new conversation creation. `stream_message` alone is 340 lines suppressing 3 complexity rules simultaneously.
- **Fix**: Split into `chat.py` (page/thread rendering) and `chat_stream.py` (SSE streaming). Extract shared identity resolution into a helper.

---

## P1 -- Critical (Fix Before or Shortly After Launch)

### Security

| ID | Finding | File | Fix |
|----|---------|------|-----|
| SEC-4 | WebSocket guest session bypass -- unsigned UUID accepted | `src/api/routes/voice.py:147-154` | Call `unsign_session_id()` instead of plain UUID check |
| SEC-5 | Rate limiting is global, not per-IP/per-user | `src/api/rate_limit.py:62-83` | Implement per-IP rate limiting (slowapi or dict-of-deques) |
| SEC-6 | Guest users get admin (service-role) Supabase client | `src/api/auth.py:424-439` | Document as accepted risk or use restricted wrapper |
| SEC-7 | No startup guard for `ALLOW_UNVERIFIED_JWT=true` | `src/config.py:52` | Reject `ALLOW_UNVERIFIED_JWT=true` when `DEBUG=false` |

### Production Readiness

| ID | Finding | File | Fix |
|----|---------|------|-----|
| PROD-1 | No timeout on Anthropic LLM calls | `src/agent/llm.py:69-79` | Add `timeout=60` to all `ChatAnthropic` instantiations |
| PROD-2 | Non-streaming `POST /chat` has no error handling around `graph.ainvoke()` | `src/api/routes/chat.py:461-476` | Wrap in try/except returning error HTML |
| PROD-3 | Health check is shallow (returns healthy unconditionally) | `src/api/main.py:225-232` | Verify Postgres pool, report 503 if DB unreachable |
| PROD-4 | Supabase down: unhandled error paths | `src/api/routes/chat.py:436` | Add error handling for Supabase connectivity failures |

### Deployment

| ID | Finding | File | Fix |
|----|---------|------|-----|
| DEP-1 | Single uvicorn worker, no concurrency | `render.yaml:41` | Document scaling path; add `--workers` for paid plans |
| DEP-2 | Process-local MemorySaver when no DB URL | `src/agent/checkpointer.py:42-49` | Fail-fast if `SUPABASE_DB_URL` not set in production |
| DEP-3 | Encryption key loss = total data loss, no documentation | `src/db/encryption.py` | Create key management runbook |
| DEP-4 | render.yaml missing critical env vars | `render.yaml` | Add SECRET_KEY, ENCRYPTION_SALT, CORS_ALLOWED_ORIGINS |

### Code Quality

| ID | Finding | File | Fix |
|----|---------|------|-----|
| CQ-2 | Duplicate identity resolution logic (~20 lines) | `src/api/routes/chat.py:438-458 vs 657-680` | Extract to shared helper |
| CQ-3 | Duplicate `_get_language_name` function | `src/agent/nodes/lesson_chat.py:87-89` | Use canonical `src.validation.get_language_name` |
| CQ-4 | `repository.py` is 971 lines with 4 classes | `src/db/repository.py` | Split into per-class files |
| CQ-5 | `stream_chat_events` accepts and returns `Any` | `src/api/streaming.py:69,75` | Type with `CompiledGraph` Protocol |

### Open-Source

| ID | Finding | File | Fix |
|----|---------|------|-----|
| OSS-4 | No database setup documentation | `migrations/` | Create `docs/setup.md` with Supabase + migration guide |
| OSS-5 | No CONTRIBUTING.md | Repository root | Create with dev setup, PR guidelines, code conventions |
| OSS-6 | 40+ screenshot files polluting repo root | Repository root | Delete; add `*.png` exclusion to .gitignore |
| OSS-7 | .gitignore missing `.claude/`, `.serena/` | `.gitignore` | Add tool directory exclusions |

### Performance

| ID | Finding | File | Fix |
|----|---------|------|-----|
| PERF-1 | Tailwind CSS loaded via CDN with runtime JIT | `src/templates/base.html:15` | Switch to build-time CSS compilation |
| PERF-2 | `get_review_stats` makes 3 sequential HTTP round-trips | `src/db/repository.py:683-745` | Create single Postgres RPC function |
| PERF-3 | `get_dashboard_stats` fetches ALL vocabulary rows | `src/services/progress.py:116-118` | Move aggregation server-side |
| PERF-4 | 2-3 LLM calls per freeform message (sequential) | `src/agent/graph.py` | Parallelize scaffold + analyze, or merge into respond |

### Data Integrity

| ID | Finding | File | Fix |
|----|---------|------|-----|
| DATA-1 | `decrypt_field` crashes entire request on corrupted data | `src/db/encryption.py:94` | Add `decrypt_field_safe()` with graceful fallback |
| DATA-2 | Thread deletion not atomic (orphaned checkpoints) | `src/services/threads.py:102-119` | Use transaction or reverse deletion order |

---

## P2 -- Important (Post-Launch)

### Security (6)
- `active_thread` cookie stores unsigned thread_id (`threads.py:143`)
- CSP allows `'unsafe-eval'` for Tailwind CDN (`middleware.py:175`)
- No CSRF on WebSocket upgrade Origin validation (`middleware.py:104`)
- Logout doesn't invalidate server-side session (`routes/auth.py:377-407`)
- Backward-compatible unsigned session_id in HTTP path (`cookies.py:179-187`)
- Thread ID regex allows arbitrary characters in trailing segment (`chat.py:72`)

### Production Readiness (6)
- Auth errors log as `logger.exception` (noisy) (`routes/auth.py:273,356`)
- No request-ID correlation in logs (`main.py:30-46`)
- Supabase client created per-request, no pooling (`db/client.py:85-115`)
- No graceful drain for SSE/WebSocket on shutdown (`main.py:86-87`)
- Checkpoint purge not retried after startup failure (`main.py:78-81`)
- Anthropic API degradation -- no circuit breaker (`streaming.py:178-183`)

### Deployment (6)
- Free plan has cold starts (`render.yaml:24`)
- Dockerfile uses unpinned `uv:latest` (`Dockerfile:23`)
- Dockerfile build differs from render.yaml build (`Dockerfile:37`)
- No readiness probe separate from liveness (`main.py`)
- WebSocket/SSE require session affinity for multi-instance (`voice.py`, `chat.py`)
- No migration runner or versioning system (`migrations/`)

### Code Quality (5)
- `StreamResult` fields use `list[Any]` (`streaming.py:31-33`)
- 5 circular-import inline imports (`llm.py:61`, `auth.py:148,411`, etc.)
- Repeated prompt composition pattern (5x in lesson_chat) (`lesson_chat.py:191+`)
- ThreadService instantiated 11 times in chat.py (`chat.py`)
- 23 bare `except Exception` blocks across codebase

### Frontend & Accessibility (10)
- Chat messages lack `role="log"` and `aria-live` (`chat.html:60`)
- Loading indicator not announced to screen readers (`chat.html:114-127`)
- Feedback buttons invisible to keyboard users (opacity:0) (`message.html:41`)
- Error messages lack `role="alert"` (`login.html:29`, `signup.html:29`)
- Jardin theme `--text-subtle` fails AA contrast (`base.html:270-296`)
- No skip-to-content link (`base.html`)
- Lessons page missing `<main>` landmark (`lessons.html`)
- Theme FOUC on page load (`base.html:864`)
- No dark mode preference detection (`base.html:849`)
- Hardcoded dark-theme error colors in JS (`stream.js:456-463`)

### Performance (10)
- Chart data O(N*D) on full vocabulary set (`progress.py:141-176`)
- Per-request Supabase client creation (`db/client.py:85-115`)
- Unbounded `get_all()` with no pagination (`repository.py:112-131`)
- Lesson prompts redundantly prepend base prompt (`lesson_chat.py:191+`)
- Thread titling creates new ChatAnthropic per call (`thread_titling.py:35-40`)
- Review generates 2 LLM calls per word (`agent/nodes/review.py`)
- Full conversation history sent to LLM each turn (`chat.py:463-476`)
- Static asset cache only 24 hours (`middleware.py:37`)
- Animate.css loaded but minimally used (`base.html:12`)
- Sequential vocab upserts post-stream (6-20 HTTP calls) (`progress.py:198-214`)

---

## P3 -- Backlog (20 findings)

- Signup error may leak internal details (`routes/auth.py:274`)
- Thread title not sanitized with nh3 (`routes/threads.py:108`)
- nh3 doesn't explicitly set `url_schemes` (`sanitize.py:46`)
- Debug mode JWT bypass needs startup warning (`auth.py:327-342`)
- Vocabulary keyword search filter potentially injectable (`repository.py:435-449`)
- Thread ID validation not applied to Form parameter (`chat.py:378,555`)
- No max-length CHECK constraint on thread titles (`migration 005`)
- Review `word_id` not validated against session state (`routes/review.py:309`)
- No checkpoint cleanup/purging mechanism active (`config.py:85`)
- No pagination on `list_threads` (`routes/threads.py:44-64`)
- Migrations not reversible (no DOWN scripts) (`migrations/`)
- Re-export shim modules may confuse contributors (`api/config.py`, etc.)
- Unused `_CONVERSATION_VERSION_MAX_AGE` constant (`chat.py:68`)
- Stale "VocabularyService disabled" comment (`services/__init__.py:4`)
- Cookie name getters could be constants (`routes/review.py:51-58`)
- No `.dockerignore` file
- Google Fonts -- consider self-hosting + preload
- No JS minification or bundling (13 separate modules, ~88KB)
- Voice modules loaded regardless of voice_enabled
- `ScriptProcessor` deprecation (fallback path)

---

## Positive Observations

The audit found many areas of strong engineering:

- **Testing**: 2,270+ passing tests with pytest-xdist parallelization
- **Type safety**: Strict mypy + ruff with zero TODO/FIXME in source
- **Security layers**: Fernet encryption, RLS on all tables, CSP nonces, CSRF middleware, signed cookies, nh3 sanitization
- **WebSocket lifecycle**: Proper cleanup with try/finally, cancel tasks, finalize connections
- **SSE streaming**: Correct EventSourceResponse cleanup on disconnect
- **Session management**: Signed cookies with environment-aware secure flag
- **Mobile foundations**: viewport-fit=cover, safe-area utilities, 100dvh, touch-action, iOS Safari edge cases
- **Theme system**: 5 themes with comprehensive CSS custom properties
- **Lesson caching**: YAML files cached via lru_cache at startup
- **Encryption caching**: PBKDF2 key derivation cached (480K iterations, computed once)
- **Deepgram degradation**: Voice features degrade gracefully when unavailable
- **Dependency licenses**: All MIT/Apache/BSD -- fully compatible

---

## Recommended Remediation Order

### Phase 1: Pre-Release Blockers (P0)
1. Create LICENSE file (MIT)
2. Fail-fast on default SECRET_KEY/ENCRYPTION_SALT in production
3. Fix SECURITY DEFINER RPC functions (change to INVOKER or add auth.uid() checks)
4. Rotate all API keys
5. Run secret scanner on git history
6. Create README.md
7. Fix sidebar accessibility (focus trap, ARIA)
8. Fix dropdown keyboard navigation
9. Split chat.py (god file)

### Phase 2: Launch Hardening (P1)
1. Fix WebSocket session auth bypass
2. Implement per-IP rate limiting
3. Add LLM call timeouts
4. Add error handling to non-streaming chat path
5. Deepen health check
6. Complete render.yaml env vars
7. Switch to build-time Tailwind CSS
8. Create database setup documentation
9. Create CONTRIBUTING.md
10. Clean up repo root screenshots

### Phase 3: Post-Launch Quality (P2)
1. Consolidate database round-trips (RPCs)
2. Add request-ID correlation logging
3. Fix frontend accessibility (aria-live, role=alert, contrast)
4. Implement message windowing for LLM context
5. Add graceful shutdown drain
6. Fix theme FOUC

### Phase 4: Optimization (P3)
- Batch vocab upserts, paginate queries, JS bundling, migration tooling
