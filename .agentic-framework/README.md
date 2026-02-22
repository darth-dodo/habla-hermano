# Habla Hermano -- Agentic Framework

Project-specific agent collaboration framework extending SuperClaude for habla-hermano, an AI language tutor (A0 to B1) built with Python 3.11+, FastAPI, LangGraph, LangChain, Supabase, and Anthropic Claude.

SuperClaude handles generic AI behavior (personas, MCP orchestration, thinking modes, token efficiency). This framework adds habla-hermano-specific context: LangGraph graph topology, CEFR-based curriculum design, prompt engineering patterns, and deployment configuration.

---

## Quick Start

The entry point is `config.yml`. It defines the tech stack, quality gate commands, persona focus areas, workflow phases, and deployment settings.

```bash
# Development
make dev                                    # or: uv run uvicorn src.api.main:app --reload --port 8000

# Quality checks
uv run ruff check src/ tests/              # Lint
uv run ruff format --check src/ tests/     # Format check
uv run mypy src/                           # Type check
uv run pytest                              # Tests
uv run pytest --cov=src --cov-report=term-missing  # Tests with coverage

# All checks at once
make check
```

See `config.yml` for the full command reference, including `lint_fix`, `format`, `test_fast`, `db_init`, `db_seed`, and `pre_commit`.

---

## Directory Structure

```
.agentic-framework/
├── README.md                          # This file
├── config.yml                         # Project configuration (entry point)
├── personas/
│   ├── architect.yml                  # System design -- habla-hermano-specific
│   ├── developer.yml                  # Implementation and coding
│   ├── qa.yml                         # Testing and validation
│   ├── writer.yml                     # Documentation and content
│   ├── agent-developer.yml            # LangGraph node development specialist
│   └── language-expert.yml            # Language pedagogy specialist
├── workflows/
│   ├── feature-development.md         # Design, implement, validate cycle
│   ├── bug-fix.md                     # Investigate, fix, verify cycle
│   ├── content-creation.md            # Documentation and content workflow
│   ├── multi-agent-coordination.md    # Parallel and sequential agent patterns
│   ├── task-management.md             # Task tracking and session lifecycle
│   ├── agent-development.md           # LangGraph node development workflow
│   └── deployment.md                  # Render deployment workflow
├── quality-gates/
│   ├── README.md                      # Quality gate system overview
│   ├── generic-gates.md               # Language-agnostic 7-gate reference
│   └── examples/
│       └── python.md                  # Python-specific gate implementations
├── integration/
│   ├── session-template.md            # Persona-aware session log template
│   └── handoff-template.md            # Agent-to-agent handoff documentation
└── templates/
    ├── project-config.yml             # Starter project configuration
    └── adr-template.md                # Architecture decision record template
```

---

## Personas

Six persona files on disk, with two additional personas (backend, security) defined in `config.yml` for habla-hermano-specific focus areas.

| Persona | File | Description |
|---------|------|-------------|
| **Architect** | `architect.yml` | LangGraph graph topology, state schema design, subgraph boundaries. **Project-specific**: includes graph topology map, CEFR routing, and Supabase state boundaries. |
| **Developer** | `developer.yml` | Feature implementation with BDD (red/green/refactor), debugging, optimization. |
| **QA** | `qa.yml` | Test planning, quality gate validation, deployment approval. |
| **Writer** | `writer.yml` | Technical documentation, API docs, content creation. |
| **Agent Developer** | `agent-developer.yml` | LangGraph node development specialist: graph design, node conventions, state schemas. |
| **Language Expert** | `language-expert.yml` | Language pedagogy specialist: CEFR curriculum, lesson scaffolding, assessment design. |
| **Backend** | `config.yml` | FastAPI routes, LangGraph nodes, Supabase integration, prompt engineering. Config-only persona. |
| **Security** | `config.yml` | JWT verification, Supabase auth, input validation, rate limiting. Config-only persona. |

The architect persona is the most project-specific -- it encodes the conversation/lesson/exercise/review graph topology, CEFR-level conditional routing, and the service layer boundary rules.

---

## Workflows

Seven workflow files, plus one additional workflow (lesson_creation) defined in `config.yml`.

| Workflow | File / Source | Phases |
|----------|--------------|--------|
| Feature Development | `feature-development.md` | Design (architect) -> Implement (backend) -> Validate (qa) |
| Bug Fix | `bug-fix.md` | Investigate -> Fix -> Verify |
| Content Creation | `content-creation.md` | Outline -> Write -> Review |
| Multi-Agent | `multi-agent-coordination.md` | Coordinate -> Parallel Work -> Merge |
| Task Management | `task-management.md` | Track -> Update -> Handoff |
| Agent Development | `agent-development.md` | Graph Design -> Node Implementation -> Prompt Authoring -> Testing. **Project-specific**: for adding new LangGraph nodes. |
| Deployment | `deployment.md` | Pre-deploy -> Deploy -> Post-deploy verification + rollback. |
| **Lesson Creation** | `config.yml` | Curriculum Design -> Template Implementation -> Agent Integration. **Project-specific**: for building new lesson types. Config-only workflow. |

---

## Quality Gates

Seven gates enforced through `config.yml` commands. This is a Python-only project; all commands use `uv` as the package runner. Accessibility is omitted (backend API, not a UI).

| Gate | Command | Status |
|------|---------|--------|
| 1. Syntax | `uv run python -m py_compile src/api/main.py` | Enabled |
| 2. Types | `uv run mypy src/` | Enabled (strict) |
| 3. Lint | `uv run ruff check src/ tests/` | Enabled (zero warnings) |
| 4. Security | `uv run pip-audit` | Enabled |
| 5. Tests | `uv run pytest --cov=src --cov-report=term-missing` | Enabled (70% threshold) |
| 6. Performance | -- | Disabled |
| 7. Integration | `uv run pytest -m integration` | Enabled |

See `quality-gates/` for the full gate system documentation and language-specific examples.

---

## Integration with SuperClaude

**SuperClaude handles** (do not duplicate here):
- Generic persona system (architect, frontend, backend, security, etc.)
- MCP server orchestration (Context7, Sequential, Playwright, etc.)
- Thinking modes (`--think`, `--think-hard`, `--ultrathink`)
- Token efficiency and compression
- Command system (`/build`, `/analyze`, `/improve`, etc.)
- Task management and wave orchestration

**This framework adds**:
- Habla-hermano tech stack context (FastAPI + LangGraph + Supabase + Anthropic Claude)
- LangGraph-specific patterns: graph topology, state schemas, conditional edges, subgraph composition
- CEFR curriculum design: A0-B1 level progression, lesson creation, spaced repetition (SM-2)
- Prompt engineering context for language tutoring agents
- Deployment configuration (Render, `render.yaml`, health checks)
- Project-specific quality gate commands and thresholds
