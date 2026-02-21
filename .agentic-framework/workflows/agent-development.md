# Agent Development Workflow

**Purpose**: Workflow for developing new LangGraph agent nodes for habla-hermano.

**Agents**: Architect (Design) --> Developer (Implement) --> QA (Validate)

---

## Phase 1: Design (Architect)

**Objective**: Define the node's purpose, I/O contract, and state schema impact.

### Tasks

- [ ] Define the node's role in the conversation graph
- [ ] Specify inputs/outputs on `ConversationState` (use `NotRequired` for new fields)
- [ ] Design routing logic: does this node need a conditional edge?
- [ ] Identify prompt template(s) the node will use
- [ ] Decide placement in graph (see structure below)

### Graph Structure Reference

Current flow (`src/agent/graph.py`): `START -> respond -> [scaffold | analyze] -> analyze -> END`
- A0-A1: respond -> scaffold -> analyze -> END
- A2-B1: respond -> analyze -> END
- Routing: `src/agent/routing.py` uses `needs_scaffolding()`

### State Schema (`src/agent/state.py`)

Key fields: `messages` (add_messages reducer), `level` (A0-B1), `language` (es/de/fr), `user_id`, `grammar_feedback`, `new_vocabulary`, `scaffolding`, `pronunciation_tips`, `review_words_offered/used`.

New fields: add to `ConversationState` with `NotRequired`, create supporting `TypedDict`/`BaseModel` as needed.

### Quality Gate: Design Review

- [ ] Node purpose is clear and non-overlapping with existing nodes
- [ ] State changes are backward-compatible
- [ ] Graph placement and routing logic defined

---

## Phase 2: Implement (Developer)

**Objective**: Build the node, update the graph, and write tests.

### Step 1: Create Node (`src/agent/nodes/your_node.py`)

```python
from src.agent.state import ConversationState

def your_node(state: ConversationState) -> dict:
    """Brief description. Returns dict with state updates."""
    level = state["level"]
    return {"your_field": computed_value}
```

### Step 2: Update Prompts

Add templates in `src/templates/` or update `src/agent/prompts.py` if the node uses LLM calls.

### Step 3: Update Graph (`src/agent/graph.py`)

1. Import the node
2. `graph.add_node("your_node", your_node)`
3. Add edges/conditional edges
4. Update `src/agent/routing.py` if conditional logic needed

### Step 4: Write Tests (`tests/agent/nodes/test_your_node.py`)

```python
from src.agent.nodes.your_node import your_node

def test_your_node_basic():
    state = {"messages": [], "level": "A1", "language": "es"}
    result = your_node(state)
    assert "your_field" in result
```

Also add graph integration test in `tests/agent/test_graph.py`.

### Step 5: Validate

```bash
uv run ruff check src/agent/ tests/agent/
uv run mypy src/agent/
uv run pytest tests/agent/ -v && uv run pytest
```

### Quality Gate: Implementation Review

- [ ] Node follows existing patterns (reference: `src/agent/nodes/respond.py`)
- [ ] Graph compiles, unit + integration tests pass
- [ ] No lint/type errors

---

## Phase 3: Validate (QA)

### Tasks

- [ ] Run full test suite: `uv run pytest --tb=short`
- [ ] Verify correct output for each CEFR level (A0, A1, A2, B1)
- [ ] Test with real conversation flow (manual or integration test)
- [ ] Check existing nodes are unaffected (no regressions)
- [ ] Validate `ConversationState` changes are backward-compatible

### Quality Gate: Final Validation

- [ ] `uv run ruff check && uv run mypy src/ && uv run pytest` all pass
- [ ] Node works for all CEFR levels, no regressions, ready for merge

---

## Existing Nodes Reference

| Node | File | Purpose |
|------|------|---------|
| `respond_node` | `src/agent/nodes/respond.py` | Generate AI tutor response |
| `analyze_node` | `src/agent/nodes/analyze.py` | Grammar/vocabulary analysis |
| `scaffold_node` | `src/agent/nodes/scaffold.py` | Word banks/hints for A0-A1 |
| `feedback_node` | `src/agent/nodes/feedback.py` | Structured feedback |
| `lesson_node` | `src/agent/nodes/lesson.py` | Lesson delivery |
| `review_node` | `src/agent/nodes/review.py` | Spaced repetition review |

---

## Related Documents

- [feature-development.md](feature-development.md) -- General feature workflow
- [deployment.md](deployment.md) -- Deploy after node is merged to main
- [task-management.md](task-management.md) -- Task tracking and session lifecycle
