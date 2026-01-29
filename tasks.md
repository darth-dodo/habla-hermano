# Habla Hermano - Task Tracking

> **Source of Truth**: This file is the single source of truth for project state.

## Table of Contents
- [Project Overview](#project-overview)
- [Current State](#current-state)
- [Completed Phases](#completed-phases)
- [Up Next](#up-next)
- [Session Logs](#session-logs)
- [Notes for Future Agents](#notes-for-future-agents)

---

## Project Overview

**Habla Hermano**: AI language tutor taking learners from A0 (absolute beginner) to B1 (intermediate).

**Tech Stack**: FastAPI + HTMX + LangGraph + Claude API + Supabase

**Learning Goal**: Build proficiency with LangGraph (state management, routing, checkpointing) and production deployment

**Key Documents**:
- `docs/product.md` - Product specification
- `docs/architecture.md` - Technical architecture
- `docs/design/` - Phase-by-phase design documents
- `docs/adr/` - Architectural Decision Records

---

## Current State

**Branch**: `feature/phase7-progress-tracking` (pending PR to main)
**Phase**: Phase 8 Complete (Guest Session Support)
**Test Coverage**: 1016+ tests, 86%+ coverage

### What's Working

| Feature | Status | Notes |
|---------|--------|-------|
| Hermano Personality | ✅ | Friendly big brother tutor with consistent voice |
| Scaffolded Conversation | ✅ | Chat with Hermano who adapts to level |
| 4 Proficiency Levels | ✅ | A0, A1, A2, B1 with distinct Hermano behavior |
| 3 Languages | ✅ | Spanish, German, French via LANGUAGE_ADAPTER |
| Grammar Feedback | ✅ | Gentle corrections with expandable tips |
| Word Banks & Hints | ✅ | Contextual help for A0-A1 learners |
| Sentence Starters | ✅ | Partial sentences to get beginners going |
| Conditional Routing | ✅ | A0-A1 → scaffold, A2-B1 → skip |
| Conversation Persistence | ✅ | PostgresSaver with MemorySaver fallback |
| User Authentication | ✅ | Supabase Auth with JWT tokens |
| Session Management | ✅ | JWT in httponly cookies, 7-day expiry |
| Multi-User Support | ✅ | User ID → Thread ID isolation |
| New Conversation | ✅ | Clear session and start fresh |
| 3 Themes | ✅ | Dark, Light, Ocean |
| Mobile-First UI | ✅ | Works on all devices |
| Micro-Lessons | ✅ | 5 Spanish A0 lessons with exercises |
| Lesson Player | ✅ | Step-through UI with progress bar |
| Interactive Exercises | ✅ | Multiple choice, fill blank, translate |
| Lesson → Chat Handoff | ✅ | Practice learned patterns with Hermano |
| Guest Access | ✅ | Lessons playable without authentication |
| Hamburger Menu | ✅ | Consolidated nav: Lessons, New Chat, Theme, Auth |
| Progress Dashboard | ✅ | Vocabulary, sessions, streaks, Chart.js charts |
| Guest Progress | ✅ | Session-based tracking via cookies |
| Data Merge on Auth | ✅ | Guest data merges on signup/login |

### LangGraph Flow

```
START → respond → [needs_scaffold?]
                    ├── A0/A1 → scaffold → analyze → END
                    └── A2/B1 → analyze → END

Persistence: PostgresSaver (Supabase) with MemorySaver fallback for dev
Auth: Supabase Auth → JWT cookie → Protected routes
Lessons: Standalone YAML-based system (orthogonal to graph)
Progress: ProgressService aggregates vocabulary, sessions, lessons
Guest: session_id cookie → admin client → same tables (RLS bypass)
```

---

## Completed Phases

### Phase 0: Project Setup ✅
- Project scaffolding with uv package manager
- FastAPI + HTMX + Tailwind CSS stack
- Pre-commit hooks, CI/CD pipeline
- [Design Doc](docs/design/phase0-project-setup.md)

### Phase 1: Basic Chat ✅
- LangGraph StateGraph with respond node
- Level-adaptive AI responses (A0-B1)
- HTMX chat UI with themes
- [Design Doc](docs/design/phase1-basic-chat.md)

### Phase 2: Grammar Feedback ✅
- Analyze node for grammar detection
- "Gentle nudge" correction pattern
- Collapsible feedback UI with severity colors
- [Design Doc](docs/design/phase2-grammar-feedback.md)

### Phase 3: Scaffolding ✅
- Scaffold node with word banks, hints, sentence starters
- Conditional routing based on learner level
- A0: auto-expanded, A1: collapsed, A2-B1: skipped
- Click-to-insert word bank functionality
- [Design Doc](docs/design/phase3-scaffold-node.md)

### Phase 4: Persistence ✅
- LangGraph checkpointing with PostgresSaver (AsyncSqliteSaver had bug)
- MemorySaver fallback for development without Supabase
- Thread ID management via user authentication
- Conversation history persists in PostgreSQL
- "New Conversation" button with `/new` endpoint
- [Design Doc](docs/design/phase4-persistence.md)

### Phase 5: Supabase Auth ✅
- Supabase Auth with email/password authentication
- JWT token validation with `CurrentUserDep` dependency
- Protected routes for chat and main interface
- Login/signup/logout endpoints and UI
- User ID → Thread ID mapping for conversation isolation
- 829+ tests, 86%+ coverage
- [ADR](docs/adr/ADR-001-supabase-integration.md), [Design Doc](docs/design/phase5-supabase-auth.md)

### Phase 6: Micro-Lessons ✅
- Lesson data models (Pydantic): LessonMetadata, LessonStep, Exercise, UserLessonProgress
- LessonService for YAML loading with filtering by language/level/category
- 5 Spanish A0 lessons: greetings, introductions, numbers, colors, family
- Interactive lesson player with step navigation (HTMX partials)
- 3 exercise types: multiple choice, fill blank, translate
- Lesson completion view with chat handoff ("Practice with Hermano")
- Guest access via `OptionalUserDep` (no auth required for lessons)
- Hamburger menu consolidating nav (Lessons, New Chat, Theme, Auth)
- 166 new tests (TDD approach), Playwright browser testing
- 918+ tests, 86%+ coverage
- [Design Doc](docs/design/phase6-micro-lessons.md)

### Phase 7: Progress Tracking ✅
- ProgressService for dashboard stats and chart data
- VocabularyRepository, LearningSessionRepository, LessonProgressRepository
- Progress dashboard with Chart.js visualizations (vocab growth, accuracy trend)
- Vocabulary and session capture in chat and lesson routes
- HTMX partials for stats_summary and progress_vocab
- 1016+ tests, 86%+ coverage
- [Design Doc](docs/design/phase7-progress-tracking.md)

### Phase 8: Guest Session Support ✅
- Session-based guest tracking via session_id cookie (httponly, 7-day expiry)
- Guest data stored in same Supabase tables using admin client (RLS bypass)
- GuestDataMergeService for merging guest data on signup/login
- `_resolve_identity()` helper for unified auth/guest handling
- Fire-and-forget pattern: capture failures never block responses
- Schema migration to drop FK constraints for guest UUIDs
- [Design Doc](docs/design/phase8-guest-session-support.md)

---

## Up Next

### Phase 9: Content Expansion (Priority: 🟢 Low)

| Task | Status | Notes |
|------|--------|-------|
| German A0 lessons | ⏳ | Mirror Spanish lesson topics |
| French A0 lessons | ⏳ | Mirror Spanish lesson topics |
| A1 lessons (all languages) | ⏳ | More complex patterns and vocabulary |
| Audio pronunciation | ⏳ | Audio files for vocabulary items |

### Phase 10: Adaptive Learning (Priority: 🟢 Low)

| Task | Status | Notes |
|------|--------|-------|
| Lesson recommendations | ⏳ | Based on chat vocabulary gaps |
| Spaced repetition | ⏳ | Review scheduling for vocabulary |
| Level-up suggestions | ⏳ | Progress-based level promotion |

---

## Session Logs

### Session Log: 2026-01-29 (Phase 7 & 8 Implementation - Progress Tracking + Guest Sessions)

**Session Focus**: Phase 7 (Progress Tracking Dashboard) and Phase 8 (Guest Session Support)

**Approach**: Used parallel subagents from `.agentic-framework` for implementation and testing

**Key Changes**:

1. **ProgressService** (`src/services/progress.py`):
   - `get_dashboard_stats()` - aggregates total_words, total_sessions, lessons_completed, current_streak, accuracy_rate, words_learned_today, messages_today
   - `get_chart_data()` - generates vocab_growth and accuracy_trend for Chart.js
   - `record_chat_activity()` - captures vocabulary and session data from chat

2. **Repository Updates** (`src/db/repository.py`):
   - Added `client` parameter to VocabularyRepository, LearningSessionRepository, LessonProgressRepository
   - Allows admin client injection for guest writes (RLS bypass)

3. **GuestDataMergeService** (`src/services/merge.py`):
   - `merge_all()` orchestrates vocabulary, session, and lesson merge
   - `_merge_vocabulary()` - transfers unique words, merges counters for duplicates
   - `_merge_sessions()` - transfers all sessions
   - `_merge_lessons()` - transfers unique, keeps higher score for duplicates

4. **Guest Identity Resolution** (`src/api/routes/progress.py`):
   - `_resolve_identity()` helper returns (effective_id, client) tuple
   - Authenticated users: (user.id, None)
   - Guests: (session_id, admin_client)
   - Missing admin client: (None, None) → empty state

5. **Data Capture Integration**:
   - `chat.py` - captures vocabulary via `record_chat_activity()` for auth and guests
   - `lessons.py` - captures lesson completion for auth and guests
   - `auth.py` - triggers `merge_all()` on signup/login with session_id cookie

6. **Schema Changes** (`data/schema_migration_guest_progress.sql`):
   - Drop FK constraints on vocabulary, learning_sessions, lesson_progress
   - Guest UUIDs stored in user_id column (not in auth.users)

7. **Templates**:
   - `progress.html` - Dashboard with stats cards and Chart.js charts
   - `partials/stats_summary.html` - Stats card partial (HTMX)
   - `partials/progress_vocab.html` - Vocabulary list partial (HTMX)

**Design Patterns**:
- **Fire-and-forget**: Data capture wrapped in try/except, failures logged but don't block
- **Admin client for guests**: `get_supabase_admin()` bypasses RLS for guest writes
- **Unified identity**: `_resolve_identity()` abstracts auth vs guest handling
- **Merge on auth**: Both signup and login check for session_id cookie and merge

**Test Coverage**:
- `test_progress_service.py` - 25+ tests for ProgressService
- `test_data_capture.py` - 20+ tests for vocabulary/session capture integration
- `test_merge_service.py` - 30+ tests for GuestDataMergeService
- `test_guest_progress.py` - 23+ tests for E2E guest flows
- Total: 1016+ tests, 86%+ coverage

**Playwright E2E Verification**:
- ✅ Guest sees Progress link in nav
- ✅ Guest with no cookie sees empty progress page
- ✅ Guest visits lessons page
- ✅ Guest lesson completion creates session cookie
- ✅ Guest can view progress without login
- ✅ Progress page displays correctly

**Bug Fix During Implementation**:
- **Issue**: 500 error on guest lesson completion
- **Root Cause**: `get_supabase_admin()` called outside try/except when SUPABASE_SERVICE_KEY missing
- **Fix**: Moved admin client calls inside try/except blocks in chat.py, lessons.py, progress.py

**Documentation**:
- Expanded `docs/design/phase7-progress-tracking.md` (2KB → 1000+ lines)
- Created `docs/design/phase8-guest-session-support.md`
- Updated README, CHANGELOG, architecture.md, product.md, api.md
- Updated testing.md, codebase-summary.md, playwright-e2e.md

**Branch**: `feature/phase7-progress-tracking`

**Commits**:
- `71315e8` - feat: add session-based guest progress tracking (Phase 7 & 8)
- `9d7ff44` - docs: update all documentation for Phase 7 & 8
- `3c30a49` - fix: correct type annotation for _resolve_identity return type

**Quality Gates**:
- ✅ All 1016+ tests passing
- ✅ Lint passing (ruff)
- ✅ Format passing (ruff-format)
- ✅ Type check passing (mypy)
- ✅ Pre-commit hooks passing
- ✅ Playwright E2E tests passing

**Next Steps**:
- [ ] Merge PR to main
- [ ] Phase 9: Content Expansion (German, French A0 lessons)

---

### Session Log: 2026-01-27 (Phase 6 Implementation - Micro-Lessons)

**Session Focus**: Phase 6 - Structured micro-lessons with interactive exercises and HTMX UI

**Approach**: TDD (RED then GREEN) with Playwright browser testing for real user flows

**Key Changes**:

1. **Lesson data models** (`src/lessons/models.py`):
   - `LessonMetadata`, `LessonStep`, `LessonContent`, `Lesson` Pydantic models
   - `ExerciseType` enum: multiple_choice, fill_blank, translate
   - `LessonStepType` enum: instruction, vocabulary, example, tip, practice
   - `UserLessonProgress` model with completion tracking
   - All exercises implement `check_answer()` with case-insensitive matching

2. **Lesson service** (`src/lessons/service.py`):
   - YAML file loading from `data/lessons/` with recursive directory scanning
   - Filtering by language, level, category
   - `@lru_cache` singleton via `get_lesson_service()`
   - Vocabulary extraction, category listing, progress integration

3. **5 Spanish A0 lessons** (`data/lessons/es/A0/`):
   - `greetings-001.yaml` - Basic greetings (6 vocab)
   - `introductions-001.yaml` - Introducing yourself (8 vocab)
   - `numbers-001.yaml` - Numbers 1-10 (10 vocab)
   - `colors-001.yaml` - Colors (8 vocab)
   - `family-001.yaml` - Family members (8 vocab)

4. **API routes** (`src/api/routes/lessons.py`):
   - GET `/lessons/` - Lesson catalog with beginner/intermediate grouping
   - GET `/lessons/{id}/play` - Interactive lesson player
   - GET `/lessons/{id}/step/{index}` - HTMX step partial
   - POST `/lessons/{id}/step/next` and `/step/prev` - Navigation
   - GET `/lessons/{id}/exercise/{id}` - Exercise rendering
   - POST `/lessons/{id}/exercise/{id}/submit` - Answer checking with feedback
   - POST `/lessons/{id}/complete` - Completion celebration
   - POST `/lessons/{id}/handoff` - Redirect to chat with lesson context
   - All endpoints use `OptionalUserDep` for guest access

5. **Templates**:
   - `lesson_player.html` - Full player with progress bar and nav
   - `partials/lesson_step.html` - Step types (instruction, vocab, example, tip, practice)
   - `partials/lesson_exercise.html` - Exercise UI (multiple choice, fill blank, translate)
   - `partials/lesson_complete.html` - Completion celebration with chat handoff

6. **Hamburger menu** (`src/templates/chat.html`):
   - Consolidated cluttered header into dropdown menu
   - Left: menu (Lessons, New Chat, Theme, Login/Logout)
   - Center: logo with brand
   - Right: compact language and level selectors

**Design Patterns**:
- **Service layer**: `LessonService` with dependency injection (`LessonServiceDep`)
- **YAML content management**: Easy authoring, version-controlled lessons
- **HTMX partials**: Step navigation via partial HTML swaps
- **Guest access**: `OptionalUserDep` - no auth required for lessons

**Test Coverage**:
- 166 new tests across 4 files (TDD approach)
- `tests/test_lesson_models.py` - 36 tests (models, validation, exercise checking)
- `tests/test_lesson_routes.py` - 39 tests (API endpoints, HTMX responses)
- `tests/test_lesson_service.py` - 20 tests (YAML loading, filtering)
- `tests/test_lessons_progress_routes.py` - 71 tests (progress tracking)
- Total: 918+ tests, 86%+ coverage

**Documentation**:
- Created `docs/design/phase6-micro-lessons.md` (715 lines)
- Updated `docs/api.md`, `docs/architecture.md`, `docs/testing.md`
- Updated `docs/product.md`, `docs/codebase-summary.md`, `docs/playwright-e2e.md`
- Updated `README.md` with micro-lessons and guest access

**Branch**: `main` (merged via PR #10)

---

### Session Log: 2025-01-18 (Phase 5 Planning - Supabase Integration)

**Session Focus**: Plan production-ready multi-user authentication with Supabase

**Context**: User requested production deployment capability. Current MemorySaver loses data on restart and has no user isolation.

**Key Decisions**:
1. **Auth Method**: Email/password only (no OAuth initially)
2. **Conversations**: Single conversation per user (user_id = thread_id)
3. **Data Storage**: All data in Supabase Postgres with RLS
4. **Checkpointer**: PostgresSaver replaces MemorySaver

**Documentation Created**:
1. **ADR-001** (`docs/adr/ADR-001-supabase-integration.md`):
   - Compared 3 options: Supabase, Self-Hosted, Firebase
   - Supabase selected for native PostgresSaver support and RLS
   - Full risk assessment and rollback plan

2. **Phase 5 Design Doc** (`docs/design/phase5-supabase-auth.md`):
   - Architecture diagrams for auth flow
   - Database schema with RLS policies
   - Implementation code examples
   - 7-phase implementation plan

**Bug Fix During E2E Testing**:
- **Issue**: AsyncSqliteSaver throws `AttributeError: 'Connection' object has no attribute 'is_alive'`
- **Root Cause**: Bug in langgraph-checkpoint-sqlite 3.0.2
- **Fix**: Switched to MemorySaver for in-process persistence
- **Files Changed**: `src/agent/checkpointer.py`, `tests/test_checkpointer.py`, `tests/test_persistence_integration.py`

**E2E Validation** (Playwright):
- ✅ Chat working with MemorySaver
- ✅ Persistence across page refresh (AI remembers context)
- ✅ New Conversation clears memory correctly

**Quality Gates**:
- ✅ All 826 tests passing
- ✅ E2E tests passing via Playwright MCP

**Branch**: `main`

**Next Steps**: Begin Phase 5 implementation starting with dependencies and configuration.

---

### Session Log: 2025-01-18 (Phase 4 Implementation)

**Session Focus**: Phase 4 LangGraph - Conversation persistence with checkpointing

**Approach**: Used parallel subagents from `.agentic-framework`:
- Agent A: Backend (checkpointer, graph, session management)
- Agent B: Frontend (UI for new conversation button)
- Agent C: Tests (unit + integration tests)

**Key Changes**:

1. **Created checkpointer module** (`src/agent/checkpointer.py`):
   - `AsyncSqliteSaver` wrapper for LangGraph persistence
   - Async context manager pattern
   - Database stored in `data/checkpoints.db`

2. **Created session management** (`src/api/session.py`):
   - Thread ID via cookies (`habla_thread_id`)
   - 30-day cookie expiry
   - `get_thread_id()`, `set_thread_id()`, `clear_thread_id()` functions

3. **Updated graph** (`src/agent/graph.py`):
   - `build_graph(checkpointer=None)` - optional checkpointer parameter
   - Compiles with checkpointer for persistence

4. **Updated chat routes** (`src/api/routes/chat.py`):
   - `/chat` endpoint now uses checkpointer and thread_id
   - Added `/new` endpoint to start fresh conversation
   - HTMX redirect via `HX-Redirect` header

5. **Updated UI** (`src/templates/index.html`):
   - Added "New Conversation" button in header
   - HTMX `hx-post="/new"` with redirect handling

**LangGraph Learning**:
- Learned: `AsyncSqliteSaver` for async SQLite persistence
- Learned: `config={"configurable": {"thread_id": "xxx"}}` pattern
- Learned: Checkpointer as optional parameter to `graph.compile()`
- Learned: Thread isolation for multiple conversations

**Test Coverage**:
- 72 new tests across 3 test files
- `tests/test_checkpointer.py` - Checkpointer functionality
- `tests/test_session.py` - Session management
- `tests/test_persistence_integration.py` - Integration tests
- Total: 827 tests, 98% coverage

**Key Fixes During Implementation**:
- Fixed async context manager mock in `conftest.py` (caused 25 test failures)
- Fixed LangGraph checkpointer type validation (requires real checkpointer, not MagicMock)
- Fixed mypy errors with `BaseCheckpointSaver[Any]` type parameter

**Documentation**:
- Created `docs/design/phase4-persistence.md`
- Updated `tasks.md` with Phase 4 completion

**Quality Gates**:
- ✅ All 827 tests passing
- ✅ Lint passing
- ✅ Format passing
- ✅ Type check passing

**Branch**: `main`

---

### Session Log: 2025-01-18 (Habla Hermano Rename & Personality)

**Session Focus**: Rename project to "Habla Hermano" and create the Hermano personality

**Key Changes**:

1. **Project Rename**: habla-ai → habla-hermano
   - 38 files renamed across the codebase
   - All imports and references updated
   - Repository structure maintained

2. **Hermano Personality** (`src/agent/prompts.py`):
   - Created "Hermano" as a friendly, laid-back big brother figure
   - Patient, encouraging, makes learning feel like chatting with a friend
   - Celebrates small wins without being condescending
   - Uses casual, warm language appropriate to each level

3. **Language Adapter Pattern** (`src/agent/prompts.py`):
   - Replaced string replacement with `LANGUAGE_ADAPTER` dictionary
   - Clean separation of language-specific vocabulary
   - Supports Spanish, German, French with extensible structure
   - Format dict approach for prompt templating

4. **Personality by Level**:
   - A0: Supportive big brother for absolute beginners, heavy encouragement
   - A1: Chill friend who spent a year abroad, relaxed guidance
   - A2: Challenges learners while keeping it fun and conversational
   - B1: Peer-to-peer natural conversation partner

**Technical Details**:

The `LANGUAGE_ADAPTER` dictionary pattern:
```python
LANGUAGE_ADAPTER = {
    "es": {"language_name": "Spanish", "hello": "Hola", ...},
    "de": {"language_name": "German", "hello": "Hallo", ...},
    "fr": {"language_name": "French", "hello": "Bonjour", ...},
}
```

Prompts use `{language_name}`, `{hello}`, etc. placeholders filled via `.format(**format_dict)`.

**Documentation Updates**:
- README.md updated with Hermano personality
- CHANGELOG.md entry for v0.4.0
- docs/product.md updated with Hermano description
- docs/architecture.md with language adapter section
- docs/design/phase1-basic-chat.md with new prompt patterns

**Branch**: `main`

---

### Session Log: 2025-01-18 (Phase 3 Implementation)

**Session Focus**: Phase 3 LangGraph - Scaffold node with conditional routing

**Approach**: Used parallel subagents for implementation:
- Agent A: Scaffold node implementation (backend)
- Agent B: Scaffold UI templates (frontend)
- Agent C: Scaffold node tests (quality)

**Key Changes**:

1. **Extended ConversationState** (`src/agent/state.py`):
   - Added `ScaffoldingConfig` Pydantic model
   - Fields: enabled, word_bank, hint_text, sentence_starter, auto_expand

2. **Created routing logic** (`src/agent/routing.py`):
   - `needs_scaffold()` function for conditional routing
   - Returns True for A0/A1, False for A2/B1

3. **Created scaffold node** (`src/agent/nodes/scaffold.py`):
   - Generates word banks based on AI's last response
   - Level-aware: A0 gets translations, A1 gets plain words
   - auto_expand: True for A0, False for A1

4. **Updated graph** (`src/agent/graph.py`):
   - Changed from linear to conditional routing
   - `respond → [conditional] → scaffold OR analyze → END`

5. **Created scaffold UI** (`src/templates/partials/scaffold.html`):
   - Collapsible section with Alpine.js
   - Word bank with clickable chips
   - Click-to-insert functionality
   - Hint and sentence starter display

6. **Added click-to-insert** (`src/static/js/app.js`):
   - `insertWord()` function strips translations
   - Inserts word at cursor position in input

**LangGraph Learning**:
- Learned: Conditional edges with routing functions
- Learned: `add_conditional_edges()` API
- Learned: Routing functions return node names

**Test Coverage**:
- 16 new tests in `tests/test_scaffold_node.py`
- 10 new tests in `tests/test_routing.py`
- Updated `tests/test_agent_graph.py` for Phase 3 structure

**E2E Testing**:
- ✅ A0 scaffold auto-expanded with translated word bank
- ✅ A1 scaffold collapsed, expandable on click
- ✅ B1 no scaffold (conditional routing working)
- ✅ Word bank click-to-insert functionality

**Documentation**:
- Created `docs/design/phase3-scaffold-node.md`
- Created `docs/design/phase0-project-setup.md`
- Created `docs/design/phase1-basic-chat.md`
- Created `docs/design/phase2-grammar-feedback.md`
- Updated `docs/playwright-e2e.md` with scaffold tests
- Updated `docs/product.md` with current state
- Updated `docs/api.md` with ScaffoldingConfig
- Updated `docs/testing.md` with Phase 3 coverage
- Created `CHANGELOG.md`
- Rewrote `README.md` with product focus and ocean theme screenshots

**Branch**: `feature/phase3-scaffold-node`

**Commits**:
- `56702f2` - feat: implement Phase 3 scaffold node with conditional routing
- `56192d3` - docs: update all documentation for Phase 3
- `84b0bf0` - docs: rewrite README with product focus and ocean theme screenshots
- `b910cfc` - docs: fix language count to 3 (Spanish, German, French)
- `4c22832` - docs: add design documents for Phase 0, 1, and 2

**Quality Gates**:
- ✅ All tests passing
- ✅ Pre-commit hooks passing
- ✅ E2E tests documented
- ✅ All documentation updated

**Next Steps**:
- [ ] Create PR for feature/phase3-scaffold-node → main
- [ ] Phase 4: Persistence with LangGraph checkpointing

---

### Session Log: 2025-01-17 (Test Coverage Upgrade)

**Session Focus**: Comprehensive test coverage upgrade from 37% to 98%

**What Was Done**:
1. Created comprehensive test suites across all modules
2. Fixed analyze.py edge cases
3. Committed to `feat/test-coverage-upgrade` branch

**Coverage Metrics**:
- Before: 37% coverage
- After: 98% coverage
- Tests: 328 → 641 (313 new tests)

---

### Session Log: 2025-01-17 (Phase 2 Implementation)

**Session Focus**: Phase 2 LangGraph - Multi-node graph with analyze node

**Key Changes**:
1. Extended ConversationState with grammar_feedback and new_vocabulary
2. Created analyze node for grammar detection
3. Updated graph: respond → analyze → END
4. Created collapsible feedback UI

**LangGraph Learning**:
- Learned: Chaining nodes sequentially
- Learned: State passing between nodes

---

### Session Log: 2025-01-17 (UI Modernization)

**Session Focus**: UI Modernization and German Language Support

**What Was Done**:
1. 3 theme system (dark/light/ocean)
2. Optimistic UI for instant feedback
3. German language support
4. Language selector with flags

---

### Session Log: 2025-01-16 (Phase 1 Implementation)

**Session Focus**: Phase 1 Implementation - LangGraph + FastAPI + HTMX

**What Was Done**:
1. Created LangGraph StateGraph with respond node
2. Built HTMX chat UI with level selector
3. 229 tests passing

---

## Notes for Future Agents

### Project State
- **Current Phase**: Phase 8 Complete (Guest Session Support)
- **Personality**: "Hermano" - friendly big brother tutor, encouraging and casual
- **Graph Structure**: respond → [conditional] → scaffold OR analyze → END
- **Lessons**: Standalone YAML-based system, orthogonal to LangGraph
- **Progress**: ProgressService aggregates vocabulary, sessions, lessons with Chart.js
- **Persistence**: PostgresSaver (Supabase) with MemorySaver fallback for dev
- **Auth**: Email/password via Supabase Auth with JWT tokens
- **Guest Support**: session_id cookie → admin client → same tables (RLS bypass)
- **UI Features**: 3 themes, 3 languages, hamburger menu, progress dashboard, lesson player
- **Test Coverage**: 1016+ tests, 86%+ coverage
- **Branch**: `feature/phase7-progress-tracking` (pending PR)

### Phase 4 & 5 Implementation Notes
- **ADR**: `docs/adr/ADR-001-supabase-integration.md` - Decision rationale
- **Design**: `docs/design/phase4-persistence.md`, `docs/design/phase5-supabase-auth.md`
- **Key Pattern**: `user_id` becomes `thread_id` (single conversation per user)
- **Auth Flow**: JWT in httponly cookie → FastAPI validates → Supabase Postgres
- **Checkpointer**: PostgresSaver for production, MemorySaver fallback for dev
- **RLS**: All tables have Row Level Security policies

### Phase 6 Implementation Notes
- **Design**: `docs/design/phase6-micro-lessons.md`
- **Lesson Data**: YAML files in `data/lessons/{language}/{level}/{id}.yaml`
- **Service Pattern**: `LessonService` with `@lru_cache` singleton, injected via `LessonServiceDep`
- **Guest Access**: All lesson endpoints use `OptionalUserDep` (no auth required)
- **Exercise Validation**: `check_answer()` on each exercise model, case-insensitive
- **Handoff**: Lesson completion → redirect to `/chat?lesson={id}&topic={category}`
- **Content**: 5 Spanish A0 lessons (~40 vocabulary items, multiple exercises each)
- **Adding Lessons**: Create YAML in `data/lessons/{lang}/{level}/`, service auto-discovers

### Phase 7 & 8 Implementation Notes
- **Design**: `docs/design/phase7-progress-tracking.md`, `docs/design/phase8-guest-session-support.md`
- **ProgressService**: Aggregates data from 3 repositories (vocabulary, sessions, lessons)
- **DashboardStats**: total_words, total_sessions, lessons_completed, current_streak, accuracy_rate, words_learned_today, messages_today
- **ChartData**: vocab_growth (date, count), accuracy_trend (date, accuracy) for Chart.js
- **Guest Identity**: `_resolve_identity()` returns (effective_id, client) tuple
- **Admin Client**: `get_supabase_admin()` bypasses RLS for guest writes
- **Merge Service**: `GuestDataMergeService.merge_all()` on signup/login
- **Fire-and-Forget**: All capture/merge calls wrapped in try/except, failures logged but don't block
- **Session Cookie**: `session_id` httponly cookie, samesite=lax, 7-day expiry
- **Schema**: FK constraints dropped on vocabulary, learning_sessions, lesson_progress for guest UUIDs

### Hermano Personality Guidelines
When modifying prompts or adding new features, maintain Hermano's voice:
- Warm and encouraging, never condescending
- Uses casual language ("Nice!", "You got this!")
- Celebrates small wins genuinely
- Shares relatable moments ("This one tripped me up at first too")
- Feels like texting a supportive friend

### Language Adapter Pattern
The `LANGUAGE_ADAPTER` dict in `src/agent/prompts.py` handles language switching:
- Add new languages by adding entries to the dictionary
- Prompts use `{language_name}`, `{hello}`, `{my_name_is}` placeholders
- Never use string replacement for language adaptation

### Key Files to Review
- `docs/product.md` - What we're building (includes Hermano personality)
- `docs/architecture.md` - How we're building it (includes language adapter)
- `docs/design/` - Phase-by-phase design documents
- `docs/adr/` - Architectural Decision Records
- `src/agent/prompts.py` - Hermano prompts and language adapter
- `src/lessons/` - Lesson models, service, and public API
- `src/api/routes/lessons.py` - Lesson endpoints
- `src/services/progress.py` - ProgressService for dashboard
- `src/services/merge.py` - GuestDataMergeService for auth merge
- `data/lessons/` - YAML lesson content
- `tasks.md` - Current state (this file)

### LangGraph Learning Progression

| Phase | Status | Concept |
|-------|--------|---------|
| 1. Minimal Graph | ✅ | StateGraph, TypedDict, single node |
| 2. Multi-node | ✅ | Sequential edges, state passing |
| 3. Conditional Routing | ✅ | Branching logic, routing functions |
| 4. Checkpointing | ✅ | PostgresSaver, thread IDs, conversation persistence |
| 5. PostgresSaver | ✅ | Production persistence with Supabase Postgres |
| 6. Complex State | ✅ | Nested TypedDict, multiple fields (DashboardStats, ChartData) |
| 7. Subgraphs | ⏳ | Graph composition |

> **Note**: Phase 6 (Micro-Lessons) did not introduce new LangGraph concepts.
> Lessons are a standalone system orthogonal to the conversation graph.

### Quick Commands

```bash
make install        # Install dependencies
make install-hooks  # Install pre-commit hooks
make dev            # Run dev server
make test           # Run tests
make check          # Run all checks (lint + typecheck)
```

### Environment Setup

```bash
cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY=your_key_here

# For Phase 5 (Supabase):
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_ANON_KEY=your-anon-key
# SUPABASE_SERVICE_KEY=your-service-key
# SUPABASE_JWT_SECRET=your-jwt-secret
# SUPABASE_DB_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres  # pragma: allowlist secret
```
