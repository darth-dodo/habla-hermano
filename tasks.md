# HablaAI - Task Tracking

> **Source of Truth**: This file is the single source of truth for project state.

## Table of Contents
- [Project Overview](#project-overview)
- [Current Work](#current-work)
- [Completed Phases](#completed-phases)
- [Session Logs](#session-logs)
- [Notes for Future Agents](#notes-for-future-agents)

---

## Project Overview

**HablaAI**: AI language tutor taking learners from A0 (absolute beginner) to B1 (intermediate).

**Tech Stack**: FastAPI + HTMX + LangGraph + Claude API + SQLite

**Learning Goal**: Build proficiency with LangGraph (state management, routing, checkpointing)

**Key Documents**:
- `docs/product.md` - Product specification
- `docs/architecture.md` - Technical architecture with LangGraph learning progression

---

## Current Work

### Active Tasks

| Task | Status | Notes |
|------|--------|-------|
| Phase 1 complete with tests | ✅ | 227 pytest tests, E2E validated, committed to feature/phase1-chat-ui |
| UI modernization | ✅ | 3 themes (dark/light/ocean), optimistic UI, German language support |

### Up Next - Priority Tasks

#### 🔴 Critical (Immediate)

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Create src/ directory structure | ✅ | 🔴 | Completed 2025-01-16 |
| Phase 1 LangGraph: minimal respond node | ✅ | 🔴 | StateGraph, respond node working |
| Basic FastAPI app with HTMX | ✅ | 🔴 | Chat UI functional |

#### 🟠 High Priority (Week 1)

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Phase 2 LangGraph: add analyze node | ⏳ | 🟠 | Learning: multi-node graphs |
| Level selection (A0/A1/A2/B1) | ✅ | 🟠 | Dropdown in UI, passed to graph |
| Grammar feedback display | ⏳ | 🟠 | Collapsed by default |

#### 🟡 Medium Priority (Week 2)

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Phase 3 LangGraph: scaffold node | ⏳ | 🟡 | Learning: conditional routing |
| Word bank UI for A0-A1 | ⏳ | 🟡 | Scaffolding feature |
| Phase 4 LangGraph: checkpointing | ⏳ | 🟡 | Learning: persistence |
| Vocabulary tracking | ⏳ | 🟡 | Save words learned |

#### 🟢 Low Priority (Week 3+)

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Micro-lessons (3-5 for A0-A1) | ⏳ | 🟢 | 2-3 min lessons |
| Progress visualization | ⏳ | 🟢 | Words learned, sessions |
| German language support | ✅ | 🟢 | Language selector with 🇪🇸/🇩🇪 |
| Mobile responsiveness | ⏳ | 🟢 | Polish phase |

---

## Completed Phases

### Phase 0: Documentation & Planning ✅

| Task | Status | Notes |
|------|--------|-------|
| Initial product spec | ✅ | `docs/product.md` |
| Initial architecture | ✅ | `docs/architecture.md` |
| Rework for A0→B1 focus | ✅ | Complete beginners as target |
| Add LangGraph learning progression | ✅ | 6-phase incremental approach |

---

## Session Logs

### Session Log: 2025-01-14

**Session Focus**: Project setup - pre-commit, GitHub Actions, task management

**Key Decisions**:
1. Using `uv` for Python package management
2. Ruff for linting + formatting (replaces Black + isort)
3. MyPy strict mode for type checking
4. tasks.md as single source of truth for project state

**Branch**: `init`
**Commit**: `edc8152` (docs rework)

**Artifacts Created**:
- `pyproject.toml` - Project config with all dependencies
- `.pre-commit-config.yaml` - Pre-commit hooks (ruff, mypy, security)
- `.github/workflows/ci.yml` - CI pipeline (lint, test, security, build)
- `Makefile` - Dev commands
- `.env.example` - Environment template
- `.gitignore` - Standard ignores
- `tasks.md` - This file

**Quality Gates**:
- Pre-commit hooks configured
- CI pipeline ready (will work once src/ exists)

**Next Steps**:
- [x] Create src/ directory structure
- [x] Implement Phase 1 LangGraph (minimal graph)
- [x] Basic FastAPI + HTMX chat UI

---

### Session Log: 2025-01-16

**Session Focus**: Phase 1 Implementation - LangGraph + FastAPI + HTMX

**Approach**: Used `.agentic-framework` parallel coordination pattern with 3 subagents

**Key Decisions**:
1. Parallel agent pattern for independent components
2. claude-sonnet-4-20250514 as LLM model
3. HTMX for server-driven UI with minimal JS
4. Dark theme by default (language learning often evening activity)
5. Level selector in UI (A0/A1/A2/B1) passed to graph

**Branch**: `init`

**Artifacts Created**:
- `src/agent/state.py` - ConversationState TypedDict
- `src/agent/prompts.py` - Level-specific system prompts (A0-B1)
- `src/agent/nodes/respond.py` - Respond node calling Claude
- `src/agent/graph.py` - Minimal StateGraph: START → respond → END
- `src/api/config.py` - Pydantic Settings with env loading
- `src/api/dependencies.py` - FastAPI DI for templates
- `src/api/main.py` - FastAPI app with lifespan, static files
- `src/api/routes/chat.py` - Chat endpoints with LangGraph integration
- `src/templates/base.html` - Base template with Tailwind, HTMX, Alpine.js
- `src/templates/chat.html` - Chat UI with level selector
- `src/templates/partials/message.html` - Message bubble partial
- `src/templates/partials/message_pair.html` - User + AI message pair
- `src/static/css/input.css` - Tailwind input with custom components
- `src/static/js/app.js` - Auto-scroll, focus management, HTMX handlers

**Quality Gates**:
- ✅ Ruff linting: All checks passed
- ✅ MyPy type checking: No issues in 15 files
- ✅ App boots successfully
- ✅ Health endpoint returns 200
- ✅ Chat page renders correctly
- ⏳ E2E test with valid API key (pending user test)

**LangGraph Learning**:
- Learned: StateGraph, TypedDict with Annotated, add_messages reducer
- Learned: Single node graph structure (entry point → node → END)
- Learned: Async node functions returning state updates

**Next Steps**:
- [x] Test E2E with valid ANTHROPIC_API_KEY
- [ ] Phase 2: Add analyze node for grammar feedback
- [ ] Add conversation persistence (checkpointing)

---

### Session Log: 2025-01-16 (E2E Testing)

**Session Focus**: End-to-end testing with Playwright MCP

**Approach**: Used Playwright MCP server for browser automation testing

**Tests Executed**:
1. ✅ Chat page initial load
2. ✅ Level selector dropdown functionality
3. ✅ A0 (Complete Beginner) chat flow - English-heavy response
4. ✅ A1 (Beginner) chat flow - 50/50 Spanish/English mix
5. ✅ B1 (Intermediate) chat flow - 95%+ Spanish response

**Key Observations**:
- Level-specific prompts working correctly
- HTMX form submission and response swapping functional
- Dark theme UI renders properly
- Response times acceptable for Claude API calls

**Artifacts Created**:
- `docs/playwright-e2e.md` - E2E test documentation
- `docs/screenshots/chat-initial.png` - Initial page screenshot
- `docs/screenshots/chat-a0-response.png` - A0 level response
- `docs/screenshots/chat-a1-response.png` - A1 level response
- `docs/screenshots/chat-b1-response.png` - B1 level response

**Bug Fixed**:
- API key not loading in respond node → Fixed by importing from config.get_settings()

**Next Steps**:
- [x] Write comprehensive pytest test suite
- [ ] Create PR for feature/phase1-chat-ui → main

---

### Session Log: 2025-01-16 (Test Suite & Commit)

**Session Focus**: Test suite implementation and commit

**Approach**: Used subagents for parallel test file creation

**What Was Done**:
1. Created 229 pytest tests via subagents
2. Fixed pre-commit hook issues (ruff, mypy, detect-secrets)
3. Committed to feature/phase1-chat-ui branch
4. Pushed to origin

**Test Coverage**:
- `tests/test_agent_state.py` - ConversationState TypedDict tests
- `tests/test_agent_prompts.py` - Prompt generation tests
- `tests/test_agent_graph.py` - Graph structure tests
- `tests/test_api_config.py` - Settings and config tests
- `tests/test_api_routes.py` - FastAPI route tests

**Branch**: `feature/phase1-chat-ui`
**Commit**: `4e218a7`

**Quality Gates**:
- ✅ Ruff linting: All checks passed
- ✅ MyPy type checking: No issues
- ✅ 229 tests passing
- ✅ Pre-commit hooks passing
- ✅ Pushed to origin

**Next Steps**:
- [ ] Create PR for feature/phase1-chat-ui → main
- [ ] Phase 2: Add analyze node for grammar feedback
- [ ] Add conversation persistence (checkpointing)

---

### Session Log: 2025-01-17

**Session Focus**: UI Modernization and German Language Support

**What Was Done**:
1. Modernized UI with 3 theme system (dark/light/ocean)
2. Added optimistic UI for instant message feedback
3. Added German language support with language selector
4. Improved light theme (warm sand with sage green accents)
5. Improved ocean theme (midnight waters with golden sand accents)
6. Updated all documentation

**Key Changes**:
- `src/templates/base.html` - CSS variable theme system with 3 themes
- `src/templates/chat.html` - Language selector, theme toggle, dynamic content
- `src/templates/partials/message_pair.html` - AI-only response (user shown via JS)
- `src/static/js/app.js` - Optimistic UI, escapeHtml, HTMX handlers
- Updated tests to reflect new UI patterns

**Theme Details**:
- **Dark**: Warm charcoal with amber accents (#f59e0b)
- **Light**: Warm sand with sage green accents (#5d7c5d)
- **Ocean**: Midnight blue with golden sand accents (#d4a55a)

**Branch**: `feature/phase1-chat-ui`

**Quality Gates**:
- ✅ 227 tests passing
- ✅ Pre-commit hooks passing
- ✅ Pushed to origin

**Next Steps**:
- [ ] Create PR for feature/phase1-chat-ui → main
- [ ] Phase 2: Add analyze node for grammar feedback

---

## Notes for Future Agents

### Project State
- **Current Phase**: Phase 1 Complete with UI Modernization (227 pytest tests)
- **UI Features**: 3 themes, German support, optimistic UI
- **Test Coverage**: Unit tests in `tests/`, E2E docs in `docs/playwright-e2e.md`
- **Branch**: `feature/phase1-chat-ui` ready for PR to main
- **CI/CD**: GitHub Actions configured
- **Pre-commit**: Hooks defined, need `make install-hooks` to activate

### Key Files to Review
- `docs/product.md` - What we're building (A0→B1 language tutor)
- `docs/architecture.md` - How we're building it (LangGraph progression)
- `tasks.md` - Current state (this file)

### LangGraph Learning Progression

| Phase | Status | Concept |
|-------|--------|---------|
| 1. Minimal Graph | ✅ | StateGraph, TypedDict, single node |
| 2. Multi-node | ⏳ | Sequential edges, state passing |
| 3. Conditional Routing | ⏳ | Branching logic, routing functions |
| 4. Checkpointing | ⏳ | SqliteSaver, thread IDs |
| 5. Complex State | ⏳ | Nested TypedDict, multiple fields |
| 6. Subgraphs | ⏳ | Graph composition (future) |

### Quick Commands

```bash
# Install dependencies
make install

# Install pre-commit hooks
make install-hooks

# Run dev server
make dev

# Run tests
make test

# Run all checks
make check
```

### Environment Setup

```bash
# Copy env template
cp .env.example .env

# Add your Anthropic API key
# Edit .env: ANTHROPIC_API_KEY=your_key_here
```
