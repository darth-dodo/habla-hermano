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

**Branch**: `feature/phase14-learning-paths`
**Phase**: Phase 14 Complete (Structured Learning Paths + Adaptive Recommendations)
**Test Coverage**: 1569+ tests passing (99 new Phase 14 tests)

### Phase 14 Implementation Tasks

#### 🔴 Critical (Core Services - Parallel)

| # | Task | Status | Files | Notes |
|---|------|--------|-------|-------|
| 1 | Implement PathService | ✅ | `src/services/paths.py` | Static path config + progress computation |
| 2 | Implement AdaptiveService | ✅ | `src/services/adaptive.py` | Daily recommendations from progress + vocab |

#### 🟠 High Priority (Routes + Templates - Sequential, depends on #1 & #2)

| # | Task | Status | Files | Notes |
|---|------|--------|-------|-------|
| 3 | Implement learn routes | ✅ | `src/api/routes/learn.py` | GET /learn/, GET /learn/recommendation |
| 4 | Create templates | ✅ | `src/templates/learn.html`, `partials/learn_unit.html`, `partials/learn_recommendation.html` | Path timeline + recommendation card |

#### 🟡 Medium Priority (Integration - depends on #3 & #4)

| # | Task | Status | Files | Notes |
|---|------|--------|-------|-------|
| 5 | Mount learn router in main.py | ✅ | `src/api/main.py` | +2 lines: import + include_router |
| 6 | Add next_path_lesson to lesson completion | ✅ | `src/api/routes/lessons.py` | +15 lines in complete_lesson |
| 7 | Add "Continue Path" button | ✅ | `src/templates/partials/lesson_complete.html` | +12 lines |

#### 🟢 Low Priority (Tests + Validation - depends on all above)

| # | Task | Status | Files | Notes |
|---|------|--------|-------|-------|
| 8 | Write PathService tests | ✅ | `tests/test_paths_service.py` | 27 tests: path building, progress, next lesson |
| 9 | Write AdaptiveService tests | ✅ | `tests/test_adaptive_service.py` | 49 tests: strengths, readiness, recommendations |
| 10 | Write learn routes tests | ✅ | `tests/test_learn_routes.py` | 23 tests: pages, partials, error handling |
| 11 | Run full test suite | ✅ | - | 1569 passed, 1 pre-existing failure (unrelated) |

---

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
| Mobile-First UI | ✅ | Safe areas, dynamic viewport, touch-optimized, all devices |
| Micro-Lessons | ✅ | 60 lessons across 3 languages (es, de, fr) and 4 levels (A0-B1) |
| Lesson Player | ✅ | Step-through with HTMX navigation |
| Progress Dashboard | ✅ | Stats, vocabulary, charts |
| Guest Sessions | ✅ | Anonymous progress, merge on signup |
| AI-Enhanced Lessons | ✅ | LangGraph subgraphs, Hermano personalization |
| Nordic Minimal Design | ✅ | 3 themes (Light/Dark/Ocean), ice blue accents |
| Collapsible Pronunciation Tips | ✅ | Level-based auto-expand, A0 shows encouragement |

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

---

## Completed Phases (6-8)

### Phase 6: Micro-lessons ✅

| Task | Status | Notes |
|------|--------|-------|
| Lesson data model | ✅ | Pydantic models: Lesson, Step, Exercise |
| 5 A0 Spanish lessons | ✅ | Greetings, introductions, numbers, colors, family |
| Lesson UI | ✅ | Step-through with HTMX navigation |
| Lesson → conversation handoff | ✅ | Redirect to chat with lesson context |
| [Design Doc](docs/design/phase6-micro-lessons.md) | ✅ | Full architecture documented |

### Phase 7: Progress Tracking ✅

| Task | Status | Notes |
|------|--------|-------|
| Words learned display | ✅ | VocabularyRepository + progress_vocab.html |
| Dashboard stats | ✅ | ProgressService aggregation |
| Charts | ✅ | vocab_growth, accuracy_trend JSON endpoint |
| Streak calculation | ✅ | Consecutive days algorithm |

### Phase 8: Guest Sessions ✅

| Task | Status | Notes |
|------|--------|-------|
| Session ID cookie | ✅ | Anonymous user identification |
| Admin client bypass | ✅ | RLS bypass for guest data |
| Data merge on auth | ✅ | GuestDataMergeService |

### Phase 9: AI-Enhanced Lessons ✅

| Task | Status | Notes |
|------|--------|-------|
| LessonState TypedDict | ✅ | State for lesson subgraph |
| Lesson subgraph | ✅ | load_step → enhance_step → END |
| Exercise validation subgraph | ✅ | validate_exercise → END with AI feedback |
| Hermano lesson enhancement | ✅ | Personalized intros, tips, examples |
| AI-enhanced API endpoints | ✅ | /step/{index}/enhanced, /exercise/{id}/submit/enhanced |
| Lesson prompts | ✅ | get_lesson_enhance_prompt, get_exercise_feedback_prompt |
| E2E testing | ✅ | Playwright validation of AI-enhanced endpoints |

### Phase 10: Lesson Content Expansion ✅

| Task | Status | Notes |
|------|--------|-------|
| Spanish A1-B1 lessons | ✅ | 15 new lessons across 3 levels |
| German A0-B1 lessons | ✅ | 20 lessons covering all levels |
| French A0-B1 lessons | ✅ | 20 lessons covering all levels |
| LessonService composite keys | ✅ | Updated to use lang/level/id keys |
| YAML validation | ✅ | All 60 lessons parse correctly |
| [Design Doc](docs/design/phase10-lesson-content-expansion.md) | ✅ | Multi-agent coordination pattern |

### Phase 11: Nordic Design + Pronunciation Tips ✅

| Task | Status | Notes |
|------|--------|-------|
| Nordic Minimal design system | ✅ | CSS variables, Inter font, ice blue accents |
| 3 themes | ✅ | Light (Nordic Day), Dark (Nordic Night), Ocean |
| Pronunciation tips in prompts | ✅ | Language-specific guidance in LANGUAGE_ADAPTER |
| PronunciationTip TypedDict | ✅ | word, phonetic, tip, audio_hint fields |
| analyze_node extraction | ✅ | Returns 3-tuple: grammar, vocab, pronunciation |
| Collapsible pronunciation UI | ✅ | Alpine.js expand/collapse, speaker icon |
| Level-based auto-expand | ✅ | A0 auto-expands with encouragement text |
| E2E Playwright testing | ✅ | Verified A0 auto-expand, A1 collapsed |
| [Design Doc](docs/design/phase11-nordic-design-pronunciation.md) | ✅ | Full UI implementation documented |

---

### Phase 12: Spaced Repetition ✅

| Task | Status | Notes |
|------|--------|-------|
| SM-2 algorithm | ✅ | ReviewService with scheduling |
| Review subgraphs | ✅ | Question generation + answer evaluation |
| Chat weaving | ✅ | Silent review word integration |
| Dedicated review mode | ✅ | 3 question types (translate, fill_blank, recognize) |
| [Design Doc](docs/design/phase12-spaced-repetition.md) | ✅ | Full architecture documented |

### Phase 13: Mobile Responsive ✅

| Task | Status | Notes |
|------|--------|-------|
| Global foundation | ✅ | viewport-fit=cover, 100dvh, safe areas, touch optimizations |
| Chat page responsive | ✅ | Safe areas, keyboard-aware footer, responsive controls |
| Lesson player responsive | ✅ | Touch targets, overflow handling, title truncation |
| Progress dashboard responsive | ✅ | Chart sizing, mobile spacing, tick count |
| Partial components | ✅ | Full-width on mobile, responsive buttons |
| Lessons + auth pages | ✅ | Multi-line descriptions, safe area padding |
| [Design Doc](docs/design/phase13-mobile-responsive.md) | ✅ | Full architecture documented |

---

## Up Next

### Codebase Improvements (From Analysis)

Identified via deep codebase analysis on 2026-02-18. Ordered by severity/impact.

#### Priority: 🔴 High

| # | Task | Severity | Effort | Files | Notes |
|---|------|----------|--------|-------|-------|
| 1 | Fix `VocabularyRepository.upsert()` race condition | High | Low | `src/db/repository.py` | Read-then-write pattern; concurrent requests can duplicate rows. Use Supabase `upsert()` with `on_conflict` instead. Same issue in `increment_correct()`. |
| 2 | Remove `get_supabase_admin()` from agent nodes | High | Medium | `respond.py`, `analyze.py`, `review.py`, `learn.py` | Agent nodes bypass RLS via admin client. Contradicts Phase 8 simplified guest model. Pass user-scoped client through `ConversationState` instead. |

#### Priority: 🟡 Medium

| # | Task | Severity | Effort | Files | Notes |
|---|------|----------|--------|-------|-------|
| 3 | Extract shared `_get_llm()` factory | Medium | Low | 5 node files under `src/agent/nodes/` | Duplicated in respond, analyze, scaffold, lesson, review — each with different temperature/max_tokens. Create `src/agent/llm.py` with `get_llm(profile: str)`. |
| 4 | Fix `SupabaseClient = Any` type alias | Medium | Medium | `src/api/supabase_client.py`, `pyproject.toml` | Kills type safety for entire data layer. Use `supabase.Client` or a Protocol. Remove stale mypy `ignore_errors = true` for `src.db.*` and `src.services.*`. |
| 5 | Add chat message length validation | Medium | Trivial | `src/api/routes/chat.py` | No limit on user message length — potential API cost abuse. Add `max_length` to Pydantic `ChatRequest` model. |
| 6 | Fix `new_conversation` checkpoint clearing | Medium | Medium | `src/api/routes/chat.py` | Has TODO about Phase 8 checkpoint deletion; authenticated users get a new thread_id but old checkpoints are never cleaned up. Implement proper checkpoint deletion. |
| 7 | Narrow broad `except Exception` blocks | Medium | Medium | 21 instances across codebase | Overly broad exception handling hides bugs. Catch specific exceptions (`SupabaseError`, `ValueError`, `JSONDecodeError`, etc.). |
| 8 | Move keyword filtering server-side in `get_due_by_keywords()` | Medium | Low | `src/db/repository.py` | Fetches ALL due words then filters in Python. Use Supabase `.or()` filter to push keyword matching to the database. |

#### Priority: 🟢 Low

| # | Task | Severity | Effort | Files | Notes |
|---|------|----------|--------|-------|-------|
| 9 | Remove dead `EffectiveUser` code in auth.py | Low | Low | `src/api/auth.py` (lines ~222-285) | ~65 lines of dead code: `EffectiveUser`, `get_effective_user()`, `get_client_for_user()`, `EffectiveUserDep`. Superseded by Phase 8 simplified auth. |
| 10 | Delete dead `feedback.py` stub node | Low | Trivial | `src/agent/nodes/feedback.py` | 51-line stub returning `{"formatted_feedback": []}`. Never imported or used in graph. Remove file and `[Planned]` reference in architecture.md. |
| 11 | Remove stub methods in `VocabularyService` | Low | Low | `src/services/vocabulary.py` | `extract_vocabulary()` and `get_word_bank()` always return `[]` with `# noqa: ARG002`. Actual extraction done by `analyze_node`. Remove stubs or implement properly. |
| 12 | Clean up f-string logging & debug noise | Low | Low | `src/agent/nodes/scaffold.py`, others | Scaffold node has verbose `logger.info(f"scaffold_node called with level=...")`. Use lazy `%s` formatting per Python logging best practice. |
| 13 | Document `learn.py` route in architecture.md | Low | Low | `src/api/routes/learn.py`, `docs/architecture.md` | Route exists on disk but is undocumented. Part of Phase 14 WIP — add to architecture doc when stabilized. |
| 14 | Update stale deployment configs | Low | Low | `render.yaml`, `Dockerfile` | Both reference SQLite (`DATABASE_URL: "sqlite:///..."`) but app uses Supabase PostgreSQL. `.env.example` has `ENABLE_SPACED_REPETITION=false` (feature shipped in Phase 12). |
| 15 | Consider LLM instance caching | Low | Low | `src/agent/nodes/*` | `_get_llm()` creates a new `ChatAnthropic` instance per invocation. If stateless, cache per temperature/max_tokens combo. Low priority — LangChain may handle this internally. |

### Future Ideas (Priority: 🟢 Low)

| Task | Status | Notes |
|------|--------|-------|
| Voice input/output | ⏳ | Speech-based practice |
| Scenario roleplay | ⏳ | Ordering food, booking hotel |
| Multiple AI personas | ⏳ | Beyond Hermano |
| Offline mode | ⏳ | PWA with service worker |

---

## Session Logs

### Session Log: 2026-02-19 (Phase 14 Implementation - Learning Paths + Adaptive Recommendations)

**Session Focus**: Add structured learning paths and adaptive daily recommendations

**Agent**: Developer (following `.agentic-framework/workflows/feature-development.md`)
**Branch**: `feature/phase14-learning-paths`

**Design Reference**: `.claude/plans/serene-frolicking-stearns.md`

**Key Decisions**:
1. No new DB tables — paths are static config, progress derived from existing `lesson_progress`
2. PathService uses `@lru_cache` singleton (matches existing LessonService pattern)
3. Tasks 1 & 2 (PathService + AdaptiveService) executed in parallel via subagents
4. Lesson ordering: CATEGORY_ORDER within each LEVEL_ORDER unit (20 lessons per language)

**Artifacts Created**:
- `src/services/paths.py` — PathService with path definitions + progress computation (~337 lines)
- `src/services/adaptive.py` — AdaptiveService with daily recommendations (~180 lines)

**Completed (Session 2)**:
- Task 3: `src/api/routes/learn.py` — GET /learn/ + GET /learn/recommendation (~219 lines)
- Task 4: `src/templates/learn.html` (~98 lines), `partials/learn_unit.html` (~188 lines), `partials/learn_recommendation.html` (~68 lines)
- Task 5: `src/api/main.py` — mounted learn router at /learn prefix
- Task 6: `src/api/routes/lessons.py` — added next_path_lesson computation to complete_lesson
- Task 7: `src/templates/partials/lesson_complete.html` — added "Continue Path" button
- Task 8: `tests/test_paths_service.py` — 27 tests (path building, progress, next lesson)
- Task 9: `tests/test_adaptive_service.py` — 49 tests (strengths, readiness, recommendations, suggestion text)
- Task 10: `tests/test_learn_routes.py` — 23 tests (pages, partials, error handling, guest access)
- Task 11: Full suite — 1569 passed, 1 pre-existing failure (unrelated)

**Template Fixes**:
- Fixed `learn_unit.html`: `li.best_score` → `li.score` (matching LessonInUnit dataclass)
- Fixed `learn_recommendation.html`: `{{ category }}` → `{{ cat_strength.category | capitalize }}` (CategoryStrength objects, not strings)
- Fixed Jinja2 scoping: `loop` variable not available in `{% include %}` — pass `unit_index` and `is_last` explicitly from parent

---

### Session Log: 2026-02-04 (Phase 11 Completion - Collapsible Pronunciation Tips UI)

**Session Focus**: Implement collapsible pronunciation tips UI and update documentation

**Context**: Phase 11 Nordic Design + Pronunciation was partially complete. The pronunciation tips were being extracted by analyze_node but not displayed in the UI. User requested implementation of collapsible pronunciation tips similar to grammar feedback.

**Key Changes**:

1. **PronunciationTip TypedDict** (`src/agent/state.py`):
   - Added `PronunciationTip` TypedDict with fields: word, phonetic, tip, audio_hint (optional)
   - Added `pronunciation_tips` field to `ConversationState`

2. **analyze_node updates** (`src/agent/nodes/analyze.py`):
   - Updated `_parse_analysis_response()` to return 3-tuple: (grammar, vocab, pronunciation_tips)
   - Added `_parse_pronunciation_tips()` helper function
   - analyze_node now extracts pronunciation tips from LLM response

3. **Collapsible UI** (`src/templates/partials/pronunciation_tips.html`):
   - Alpine.js `x-data` for expand/collapse state
   - Auto-expand for A0 level: `x-data="{ expanded: {{ 'true' if level == 'A0' else 'false' }} }"`
   - Speaker icon, count display, smooth transitions
   - Nordic Minimal styling (bg-surface-overlay, border-border, text-accent)
   - Beginner encouragement text for A0 level

4. **Template integration** (`src/templates/partials/message_pair.html`):
   - Added include for `pronunciation_tips.html` partial
   - Updated header comment with pronunciation_tips and level variables

5. **Test fixes**:
   - Updated `test_analyze_node.py`: All unpacking changed from 2-tuple to 3-tuple
   - Updated `test_agent_state.py`: Changed field count test to expect 7 fields
   - Updated `test_api_routes.py`: Changed "tutor" to "conversation partner" assertion

**E2E Testing** (Playwright MCP):
- ✅ A1 level: Pronunciation tips collapsed by default, shows "1 pronunciation tip" button
- ✅ A1 level: Click expands to show tip with phonetic and guidance
- ✅ A0 level: Pronunciation tips auto-expanded
- ✅ A0 level: Beginner encouragement text displays
- Screenshots: `pronunciation-tips-expanded.png`, `pronunciation-tips-a0-auto-expanded.png`

**Documentation Updates**:
- `README.md`: Added mermaid diagram, updated feature table, test count to 1017
- `docs/design/phase11-nordic-design-pronunciation.md`: Added Collapsible UI section with mermaid diagrams
- `docs/architecture.md`: Added PronunciationTip TypedDict, updated analyze_node, test count
- `docs/product.md`: Rewrote Pronunciation Tips section with collapsible UI explanation
- `docs/codebase-summary.md`: Updated version to 1.4, test count to 1017, added pronunciation_tips
- `tasks.md`: Phase 11 marked complete with full task breakdown

**Quality Gates**:
- ✅ All 1017 tests passing
- ✅ E2E Playwright tests verified
- ✅ All documentation updated

**Files Created**:
- `src/templates/partials/pronunciation_tips.html`

**Files Modified**:
- `src/agent/state.py` (PronunciationTip TypedDict)
- `src/agent/nodes/analyze.py` (3-tuple return, pronunciation extraction)
- `src/templates/partials/message_pair.html` (include pronunciation partial)
- `src/api/routes/chat.py` (pass pronunciation_tips and level to template)
- `tests/test_analyze_node.py` (3-tuple unpacking)
- `tests/test_agent_state.py` (7 fields, new test)
- `tests/test_api_routes.py` (conversation partner assertion)

**Branch**: `main`

---

### Session Log: 2026-02-01 (Phase 10 Implementation - Lesson Content Expansion)

**Session Focus**: Expand lesson content from 5 Spanish A0 lessons to 60 lessons across 3 languages and 4 CEFR levels

**Context**: User requested Phase 10 implementation to add German and French lessons, plus higher levels (A1-B1) for all languages.

**Approach**: Used parallel multi-agent coordination pattern:
- 3 agents ran simultaneously (Spanish, German, French)
- Each agent created lessons for their language independently
- No file conflicts due to separate language directories
- ~65% time savings vs sequential execution

**Key Changes**:

1. **Created 55 new lesson files**:
   - Spanish: 15 new lessons (A1, A2, B1 × 5 categories)
   - German: 20 new lessons (A0, A1, A2, B1 × 5 categories)
   - French: 20 new lessons (A0, A1, A2, B1 × 5 categories)

2. **Updated LessonService** (`src/lessons/service.py`):
   - Added `_get_lesson_key()` helper for composite keys
   - Keys now use format: `{language}/{level}/{lesson_id}`
   - Updated `get_lesson()` to support scoped lookups

3. **Level Guidelines Applied**:
   - A0: 6 vocab, 3 exercises (100% multiple choice)
   - A1: 8 vocab, 4 exercises (50% MC, 50% fill blank)
   - A2: 10 vocab, 4 exercises (25% MC, 25% fill, 50% translate)
   - B1: 12 vocab, 5 exercises (20% MC, 20% fill, 60% translate)

4. **Language-Specific Features**:
   - German: Noun genders (der/die/das), umlauts, formal Sie/du
   - French: Accents, liaison rules, formal vous/tu
   - Spanish: Accents, ser vs estar, regional variations

**Bug Fixes During Implementation**:
- Fixed numeric options in German number lessons (must be strings)
- Fixed unused loop variable lint error (`key` → `_key`)

**Quality Gates**:
- ✅ All 60 YAML files parse without errors
- ✅ LessonService loads all 60 lessons correctly
- ✅ All 1016 tests passing
- ✅ Vocabulary counts match level guidelines
- ✅ Exercise type distribution matches guidelines

**Files Created**:
- `data/lessons/de/**/*.yaml` (20 files)
- `data/lessons/fr/**/*.yaml` (20 files)
- `data/lessons/es/{A1,A2,B1}/*.yaml` (15 files)
- `docs/design/phase10-lesson-content-expansion.md`

**Files Modified**:
- `src/lessons/service.py` (composite key support)

**Branch**: `feat/phase10-lesson-content-expansion`

---

### Session Log: 2026-01-30 (Phase 9 Implementation - AI-Enhanced Lessons)

**Session Focus**: Implement AI-enhanced lesson delivery via LangGraph subgraphs

**Context**: User requested Phase 9 implementation to add AI personalization to the micro-lessons system using LangGraph subgraphs.

**Key Changes**:

1. **Created LessonState** (`src/agent/lesson_state.py`):
   - TypedDict for lesson subgraph state
   - Fields for step data, AI enhancement, and exercise validation

2. **Created lesson nodes** (`src/agent/nodes/lesson.py`):
   - `load_step_node`: Loads step data from YAML lessons
   - `enhance_step_node`: Hermano enhances with personalized intros, tips, examples
   - `validate_exercise_node`: AI-generated feedback for exercise answers

3. **Created lesson subgraphs** (`src/agent/lesson_graph.py`):
   - `build_lesson_subgraph()`: load_step → enhance_step → END
   - `build_exercise_validation_graph()`: validate → END

4. **Added lesson prompts** (`src/agent/prompts.py`):
   - `get_lesson_enhance_prompt()`: Generates context-aware enhancement prompts
   - `get_exercise_feedback_prompt()`: Generates personalized exercise feedback

5. **Added API endpoints** (`src/api/routes/lessons.py`):
   - GET `/lessons/{id}/step/{index}/enhanced`: AI-enhanced step content
   - POST `/lessons/{id}/exercise/{id}/submit/enhanced`: AI feedback on answers

6. **Added templates**:
   - `partials/lesson_step_enhanced.html`: Enhanced step display
   - `partials/exercise_result_enhanced.html`: AI feedback display

**Bug Fixes During Implementation**:
- **Circular imports**: Fixed lazy imports in analyze.py, respond.py, scaffold.py, lesson.py
- **Anthropic API error**: Added HumanMessage to LLM calls (Anthropic requires at least one)
- **Test mock locations**: Updated patch targets from module-level to src.api.config.get_settings

**E2E Testing** (Playwright MCP):
- ✅ Lessons page loads correctly
- ✅ Lesson player navigates through steps
- ✅ AI-enhanced endpoint returns personalized content
- ✅ Exercise validation with AI feedback works
- ✅ Chat functionality verified

**Quality Gates**:
- ✅ All 1016 tests passing
- ✅ Playwright E2E tests passing
- ✅ Documentation updated

**Files Created**:
- `src/agent/lesson_state.py`
- `src/agent/nodes/lesson.py`
- `src/agent/lesson_graph.py`
- `src/templates/partials/lesson_step_enhanced.html`
- `src/templates/partials/exercise_result_enhanced.html`

**Files Modified**:
- `src/agent/prompts.py` (added lesson prompts)
- `src/api/routes/lessons.py` (added enhanced endpoints)
- `src/agent/nodes/analyze.py` (lazy import fix)
- `src/agent/nodes/respond.py` (lazy import fix)
- `src/agent/nodes/scaffold.py` (lazy import fix)
- `tests/test_agent_nodes.py` (mock patch fix)
- `tests/test_analyze_node.py` (mock patch fix)

**Branch**: `main`

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
- **Current Phase**: Phase 14 Complete (Structured Learning Paths + Adaptive Recommendations)
- **Lesson Content**: 60 lessons across 3 languages (es, de, fr) × 4 levels (A0-B1) × 5 categories
- **Personality**: "Hermano" - friendly big brother tutor, encouraging and casual
- **Graph Structure**: Main: respond → [conditional] → scaffold OR analyze → END; Lesson: load_step → enhance_step → END
- **Persistence**: PostgresSaver (Supabase) with MemorySaver fallback for dev
- **Auth**: Email/password via Supabase Auth with JWT tokens + guest sessions
- **UI Features**: Nordic Minimal design (3 themes), 3 languages, optimistic UI, grammar feedback, collapsible pronunciation tips, scaffolding, AI-enhanced lessons, progress dashboard, spaced repetition, mobile responsive, structured learning paths, adaptive recommendations
- **Test Coverage**: 1569+ tests, 86%+ coverage
- **Branch**: `feature/phase14-learning-paths`

### Phase 14: Learning Paths (Complete)
- **PathService**: `src/services/paths.py` — Static path config + progress computation
- **AdaptiveService**: `src/services/adaptive.py` — Daily recommendations from progress + vocab
- **Learn Routes**: `src/api/routes/learn.py` — GET /learn/, GET /learn/recommendation
- **Templates**: `src/templates/learn.html`, `partials/learn_unit.html`, `partials/learn_recommendation.html`
- **Tests**: 99 new tests (27 PathService + 49 AdaptiveService + 23 learn routes)
- **Known Constraint**: `lesson_progress` stores base IDs without language/level scoping; PathService always scopes `get_lesson()` calls with language+level

### Key Implementation Notes
- **ADR**: `docs/adr/ADR-001-supabase-integration.md` - Decision rationale
- **Design Docs**: `docs/design/phase*.md` - Phase-by-phase architecture
- **Key Pattern**: `user_id` becomes `thread_id` (single conversation per user)
- **Auth Flow**: JWT in httponly cookie → FastAPI validates → Supabase Postgres
- **Guest Flow**: session_id cookie → admin client → RLS bypass → merge on auth
- **Checkpointer**: PostgresSaver for production, MemorySaver fallback for dev
- **RLS**: All tables have Row Level Security policies

### Lesson System (Phase 6 + Phase 10)
- **Models**: `src/lessons/models.py` - Lesson, Step, Exercise, Progress
- **Service**: `src/lessons/service.py` - YAML loading with composite keys (lang/level/id), filtering, vocabulary extraction
- **Content**: `data/lessons/{es,de,fr}/{A0,A1,A2,B1}/*.yaml` - 60 lessons total
- **Routes**: `src/api/routes/lessons.py` - Full HTMX lesson player
- **Templates**: `lesson_player.html`, `partials/lesson_step.html`, `partials/lesson_exercise.html`
- **Categories**: greetings, introductions, numbers, colors, family

### Progress System (Phase 7-8)
- **Service**: `src/services/progress.py` - ProgressService aggregation
- **Repository**: `src/db/repository.py` - VocabularyRepository, LessonProgressRepository
- **Merge**: `src/services/merge.py` - GuestDataMergeService for auth data transfer

### AI-Enhanced Lessons (Phase 9)
- **State**: `src/agent/lesson_state.py` - LessonState TypedDict
- **Graph**: `src/agent/lesson_graph.py` - lesson_subgraph, exercise_validation_graph
- **Nodes**: `src/agent/nodes/lesson.py` - load_step_node, enhance_step_node, validate_exercise_node
- **Prompts**: `src/agent/prompts.py` - get_lesson_enhance_prompt, get_exercise_feedback_prompt
- **Templates**: `partials/lesson_step_enhanced.html`, `partials/exercise_result_enhanced.html`

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
- `tasks.md` - Current state (this file)

### LangGraph Learning Progression

| Phase | Status | Concept |
|-------|--------|---------|
| 1. Minimal Graph | ✅ | StateGraph, TypedDict, single node |
| 2. Multi-node | ✅ | Sequential edges, state passing |
| 3. Conditional Routing | ✅ | Branching logic, routing functions |
| 4. Checkpointing | ✅ | PostgresSaver, thread IDs, conversation persistence |
| 5. PostgresSaver | ✅ | Production persistence with Supabase Postgres |
| 6. Complex State | ✅ | Lesson models, progress tracking, multiple TypedDicts |
| 7. Subgraphs | ✅ | Graph composition, lesson subgraph as callable node |
| 8. Multi-Agent | ✅ | Parallel content creation with 3 agents (Phase 10) |

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
