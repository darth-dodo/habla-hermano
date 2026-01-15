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
| Project setup (config, CI, pre-commit) | ✅ | Complete |
| Create src/ directory structure | ✅ | Complete - parallel agent workflow |
| Phase 1 LangGraph: minimal respond node | ✅ | StateGraph with respond node |
| Basic FastAPI app with HTMX | ✅ | Templates + routes created |

### Up Next - Priority Tasks

#### 🔴 Critical (Immediate)

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Wire up LangGraph to Claude API | ⏳ | 🔴 | Connect respond_node to real LLM |
| Test basic chat flow end-to-end | ⏳ | 🔴 | Verify HTMX + FastAPI + LangGraph |

#### 🟠 High Priority (Week 1)

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Phase 2 LangGraph: add analyze node | ⏳ | 🟠 | Learning: multi-node graphs |
| Level selection (A0/A1/A2/B1) | ⏳ | 🟠 | Different prompts per level |
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
| German language support | ⏳ | 🟢 | If time permits |
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

### Session Log: 2025-01-15

**Session Focus**: Create complete src/ directory structure using parallel agents

**Workflow**: Multi-agent parallel coordination (`.agentic-framework/workflows/multi-agent-coordination.md`)

**Agents Used**:
1. Agent A (python-expert): API module - FastAPI routes, config, dependencies
2. Agent B (python-expert): Agent module - LangGraph graph, state, prompts, nodes
3. Agent C (python-expert): DB + Services - SQLAlchemy models, repository, services
4. Agent D (frontend-architect): Templates + Static - Jinja2, Tailwind, HTMX

**Branch**: `feature/src-structure`

**Artifacts Created**:
```
src/
├── api/
│   ├── main.py, config.py, dependencies.py
│   └── routes/ (chat.py, lessons.py, progress.py)
├── agent/
│   ├── graph.py, state.py, prompts.py
│   └── nodes/ (respond.py, analyze.py, scaffold.py, feedback.py)
├── db/
│   └── models.py, repository.py, seed.py
├── services/
│   └── vocabulary.py, levels.py
├── templates/
│   ├── base.html, chat.html, lessons.html
│   └── partials/ (message, scaffold, feedback, vocab_sidebar)
└── static/
    ├── css/input.css
    └── js/app.js
data/
├── .gitkeep
└── lessons/.gitkeep
```

**Quality Gates**:
- ✅ ruff check: All passed
- ✅ mypy --strict: No issues in 25 source files

**Key Decisions**:
1. Phase 1 LangGraph: Single respond node (START → respond → END)
2. ConversationState with messages (add_messages reducer), level, language
3. LEVEL_PROMPTS for A0/A1/A2/B1 (Spanish focus)
4. Tailwind CDN + HTMX for frontend (no build step needed initially)
5. Mobile-first, dark mode support in templates

**Next Steps**:
- [ ] Wire respond_node to Claude API (langchain-anthropic)
- [ ] Test end-to-end chat flow
- [ ] Add database initialization

---

## Notes for Future Agents

### Project State
- **Current Phase**: Setup → Moving to Phase 1 Implementation
- **Test Coverage**: N/A (no tests yet)
- **CI/CD**: GitHub Actions configured, waiting for src/
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
