# Task Management Workflow

**Purpose**: Task tracking and project state management for habla-hermano development sessions.

---

## Core Principles

1. **Single Source of Truth**: `tasks.md` is the canonical reference for project state
2. **Small Steps**: Tasks decomposed into commit-sized units
3. **Quality Gates**: Validation before marking tasks complete
4. **Session Continuity**: Structured logs enable seamless context handoff

---

## Agentic Workflow Phases

| Phase | Agent | Output |
|-------|-------|--------|
| Design | Architect | Design doc in `docs/design/` |
| Implementation | Developer | Working code with tests |
| Validation | QA | Quality report and approval |

---

## Task File Structure (`tasks.md`)

```markdown
# Habla Hermano - Task Tracking

## Current Work
| Task | Status | Notes |
|------|--------|-------|
| Description | done/wip/blocked | Context |

## Up Next
### Critical
| Task | Status | Notes |
|------|--------|-------|

## Notes for Future Agents
- **Current Phase**: [description]
- **Test Coverage**: [X% (N tests)]
- **Key Files**: [list]
```

---

## Session Lifecycle

### Start
```bash
cat tasks.md && git status && git branch
uv run pytest --tb=short
git checkout -b feature/descriptive-name
```

### During
- Commit every 15-30 minutes, update `tasks.md` every 30 minutes
- Run before each commit: `uv run ruff check src/ tests/ && uv run mypy src/ && uv run pytest --tb=short`

### End
```bash
uv run ruff check src/ tests/ && uv run mypy src/ && uv run pytest
# Update tasks.md with session log, then commit and push
```

### Session Log Format

```markdown
### Session Log: YYYY-MM-DD
**Focus**: [description] | **Branch**: `feature/name` | **Commit**: `abc1234`

**Completed**: [list deliverables]
**Quality Gates**: N tests passing, ruff clean, mypy clean
**Next Steps**: [list tasks]
```

---

## Priority Levels

| Level | Label | Response | Examples |
|-------|-------|----------|----------|
| P0 | Critical | Immediate | Broken conversation flow, API down |
| P1 | High | Next session | Major features, performance issues |
| P2 | Medium | This week | Enhancements, refactoring, test gaps |
| P3 | Low | Backlog | Documentation, minor improvements |

---

## Quality Gates

### Pre-Task
- [ ] Read `tasks.md`, check `git status`, verify `uv run pytest` passes

### Post-Task
- [ ] `uv run pytest` passes
- [ ] `uv run ruff check src/ tests/` clean
- [ ] `uv run mypy src/` clean
- [ ] `tasks.md` updated

---

## Related Documents

- [feature-development.md](feature-development.md) -- Feature workflow
- [bug-fix.md](bug-fix.md) -- Bug fix process
- [agent-development.md](agent-development.md) -- LangGraph node development
- [multi-agent-coordination.md](multi-agent-coordination.md) -- Agent coordination
- [deployment.md](deployment.md) -- Render deployment
