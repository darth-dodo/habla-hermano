# Multi-Agent Coordination Workflow

**Purpose**: Patterns for coordinating multiple agents working on habla-hermano in parallel or sequence.

**Patterns**: Parallel | Sequential | Hierarchical

---

## Pattern 1: Parallel Coordination

**Use When**: Independent tasks with no shared file dependencies.

### Examples in Habla Hermano

- Agent node development + API route development + lesson content creation
- Tests for different modules (`tests/agent/`, `tests/db/`, `tests/lessons/`)
- Multiple independent prompt template updates

### Setup (Orchestrator)

1. Identify independent task units (no shared files)
2. Create work breakdown with success criteria per agent
3. Set up git worktrees for parallel work:
   ```bash
   git worktree add ../agent-a-workspace feature/task-a
   git worktree add ../agent-b-workspace feature/task-b
   ```
4. Assign agents with clear scope boundaries

### Execution

Each agent independently:
1. Works in assigned worktree
2. Follows standard workflow (design/implement/test)
3. Commits regularly to feature branch
4. Runs validation before signaling completion:
   ```bash
   uv run ruff check src/ tests/
   uv run mypy src/
   uv run pytest
   ```

### Merge (Orchestrator)

1. Verify all agents completed their tasks
2. Merge branches in planned order
3. Resolve any merge conflicts
4. Run integration tests: `uv run pytest`
5. Clean up worktrees: `git worktree remove ../agent-a-workspace`

---

## Pattern 2: Sequential Coordination

**Use When**: Tasks have dependencies and must execute in order.

### Common Sequences in Habla Hermano

- **State --> Node --> Graph**: Add field to `ConversationState` --> implement node --> update graph routing
- **Schema --> Service --> API**: Add Supabase table --> create service layer --> expose via API
- **Design --> Implement --> Test**: Architecture review --> code changes --> validation

### Execution

For each stage:
1. Previous agent completes and signals ready
2. Orchestrator validates handoff criteria
3. Next agent receives context and begins work
4. Agent validates their output before handoff

### Handoff Protocol

Completing agent provides:
- List of deliverables with file locations
- Validation results (tests passing, lint clean)
- Context notes for next agent
- Known issues or considerations

---

## Pattern 3: Hierarchical Coordination

**Use When**: Large-scale work requiring specialized leads.

### Example: New CEFR Level Support

```
Orchestrator
  |-- Lead: Agent Development
  |     |-- Worker: New nodes in src/agent/nodes/
  |     |-- Worker: Routing logic in src/agent/routing.py
  |
  |-- Lead: Content Development
  |     |-- Worker: Lesson content in src/lessons/
  |     |-- Worker: Prompt templates in src/templates/
  |
  |-- Lead: Infrastructure
        |-- Worker: Database schema in src/db/
        |-- Worker: API endpoints in src/api/
```

### Integration Levels

1. Workers complete --> Leads integrate within domain
2. Leads complete --> Orchestrator integrates across domains
3. Final validation: `uv run ruff check && uv run mypy src/ && uv run pytest`

---

## Pattern Selection Guide

| Scenario | Pattern | Rationale |
|----------|---------|-----------|
| Independent features | Parallel | No dependencies, max speed |
| State + node + graph pipeline | Sequential | Each builds on previous |
| New CEFR level or major feature | Hierarchical | Multiple domains, coordination needed |
| Multiple test suites | Parallel | Independent test directories |
| API + prompt + node change | Sequential | Tight coupling between layers |

---

## Coordination Best Practices

- **Clear boundaries**: Define which files each agent owns
- **Quality gates at handoffs**: Validate `uv run pytest` passes before handoff
- **Minimal dependencies**: Reduce cross-task coupling where possible
- **Rollback strategy**: Commit before risky operations for easy revert
- **Communication**: Use structured handoff notes, not ad-hoc descriptions
