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

**Branch**: `feature/phase14-learning-paths`
**Phase**: Phase 14 Complete (Structured Learning Paths + Adaptive Recommendations)
**Test Coverage**: 1810 tests passing, 97% coverage

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

### Codebase Improvements (From Analysis)

Identified via deep codebase analysis on 2026-02-18. Ordered by severity/impact.

#### Priority: 🔴 High

| # | Task | Effort | Files | Notes |
|---|------|--------|-------|-------|
| 1 | Fix `VocabularyRepository.upsert()` race condition | Low | `src/db/repository.py` | Read-then-write pattern; use Supabase `upsert()` with `on_conflict`. Same issue in `increment_correct()`. |
| 2 | Remove `get_supabase_admin()` from agent nodes | Medium | `respond.py`, `analyze.py`, `review.py`, `learn.py` | Agent nodes bypass RLS via admin client. Pass user-scoped client through `ConversationState` instead. |

#### Priority: 🟡 Medium

| # | Task | Effort | Files | Notes |
|---|------|--------|-------|-------|
| 3 | Extract shared `_get_llm()` factory | Low | 5 node files under `src/agent/nodes/` | Create `src/agent/llm.py` with `get_llm(profile: str)`. |
| 4 | Fix `SupabaseClient = Any` type alias | Medium | `src/api/supabase_client.py`, `pyproject.toml` | Use `supabase.Client` or a Protocol. |
| 5 | Add chat message length validation | Trivial | `src/api/routes/chat.py` | No limit on user message length. |
| 6 | Fix `new_conversation` checkpoint clearing | Medium | `src/api/routes/chat.py` | Old checkpoints never cleaned up. |
| 7 | Narrow broad `except Exception` blocks | Medium | 21 instances across codebase | Catch specific exceptions. |
| 8 | Move keyword filtering server-side in `get_due_by_keywords()` | Low | `src/db/repository.py` | Fetches ALL due words then filters in Python. |

#### Priority: 🟢 Low

| # | Task | Effort | Files | Notes |
|---|------|--------|-------|-------|
| 9 | Remove dead `EffectiveUser` code | Low | `src/api/auth.py` | ~65 lines of dead code from pre-Phase 8. |
| 10 | Delete dead `feedback.py` stub node | Trivial | `src/agent/nodes/feedback.py` | 51-line stub, never imported. |
| 11 | Remove stub methods in `VocabularyService` | Low | `src/services/vocabulary.py` | `extract_vocabulary()` and `get_word_bank()` always return `[]`. |
| 12 | Clean up f-string logging | Low | `src/agent/nodes/scaffold.py` | Use lazy `%s` formatting. |
| 13 | Document `learn.py` route in architecture.md | Low | `docs/architecture.md` | Phase 14 route undocumented. |
| 14 | Update stale deployment configs | Low | `render.yaml`, `Dockerfile` | Reference SQLite but app uses Supabase. |
| 15 | Consider LLM instance caching | Low | `src/agent/nodes/*` | New `ChatAnthropic` per invocation. |

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
