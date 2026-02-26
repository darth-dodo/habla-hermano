# Feature: Phase 3 - Scaffold Node with Conditional Routing

## Overview

Phase 3 adds a **scaffold node** to the LangGraph conversation flow, providing word banks, hints, and sentence starters for A0-A1 level learners. This phase introduces **conditional routing** - the core LangGraph concept being learned.

**Business Value**: Complete beginners (A0-A1) often feel lost in conversation. Scaffolding provides the "training wheels" that make language learning approachable from day one.

**LangGraph Learning Goal**: Master `add_conditional_edges()` for routing based on state.

---

## Requirements

### Functional Requirements

1. **Conditional Routing**: Graph should route to scaffold node only for A0-A1 levels
2. **Word Bank Generation**: Provide 4-6 contextual words to help user respond
3. **Hint Generation**: Create a simple hint for how to respond
4. **Sentence Starter**: Optionally provide a sentence starter (e.g., "Me llamo...")
5. **Level-Aware Scaffolding**:
   - A0: Full scaffolding (hint + word bank + sentence starter, auto-expanded)
   - A1: Moderate scaffolding (word bank + hint available, collapsed by default)
   - A2-B1: No scaffolding (skip node entirely)

### Non-Functional Requirements

- Scaffold generation should add <500ms to response time
- UI should gracefully degrade if scaffolding is empty
- Scaffolding should not disrupt conversation flow

---

## Architecture

### Graph Structure (Phase 3)

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   respond   │  ← Generate AI response
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │ needs_scaffolding()?    │  ← CONDITIONAL ROUTING
              ▼                         ▼
    ┌─────────────────┐       ┌─────────────────┐
    │    scaffold     │       │     (skip)      │
    │  (A0-A1 only)   │       │   (A2-B1)       │
    └────────┬────────┘       └────────┬────────┘
             │                         │
             └──────────┬──────────────┘
                        │
                 ┌──────▼──────┐
                 │   analyze   │  ← Grammar + vocab extraction
                 └──────┬──────┘
                        │
                 ┌──────▼──────┐
                 │     END     │
                 └─────────────┘
```

### Components

#### 1. Routing Function (`src/agent/routing.py`)

```python
def needs_scaffolding(state: ConversationState) -> Literal["scaffold", "analyze"]:
    """
    Route based on user's CEFR level.

    A0-A1: Route to scaffold node for word bank/hints
    A2-B1: Skip directly to analyze node
    """
    if state["level"] in ["A0", "A1"]:
        return "scaffold"
    return "analyze"
```

**Responsibility**: Determine routing path based on state
**Interface**: Takes ConversationState, returns routing key string

#### 2. Scaffold Node (`src/agent/nodes/scaffold.py`)

```python
async def scaffold_node(state: ConversationState) -> dict:
    """
    Generate scaffolding (word bank, hint, sentence starter) for beginners.

    Analyzes the AI's last response and generates contextual scaffolding
    to help the user formulate their next response.
    """
```

**Responsibility**: Generate contextual scaffolding based on AI response
**Interface**: Takes ConversationState, returns dict with `scaffolding` key

#### 3. Extended State (`src/agent/state.py`)

```python
class ScaffoldingConfig(TypedDict):
    """Scaffolding UI configuration for beginners."""
    enabled: bool
    word_bank: list[str]
    hint_text: str
    sentence_starter: NotRequired[str]
    auto_expand: bool  # True for A0, False for A1
```

**Responsibility**: Define scaffolding data structure
**Interface**: TypedDict with scaffolding configuration

#### 4. Scaffold UI (`src/templates/partials/scaffold.html`)

```html
<!-- Word bank and hints UI for A0-A1 learners -->
<div x-data="{ expanded: {{ 'true' if auto_expand else 'false' }} }">
    <!-- Collapsible hint section -->
    <!-- Word bank as clickable chips -->
    <!-- Sentence starter (if provided) -->
</div>
```

**Responsibility**: Display scaffolding in chat UI
**Interface**: Jinja2 partial receiving scaffolding dict

---

## Data Models

### ScaffoldingConfig (New TypedDict)

```python
class ScaffoldingConfig(TypedDict):
    """Scaffolding UI configuration for A0-A1 learners."""

    # Core fields
    enabled: bool  # Whether scaffolding is active
    word_bank: list[str]  # 4-6 contextual words
    hint_text: str  # Simple hint for responding

    # Optional fields
    sentence_starter: NotRequired[str]  # e.g., "Me llamo..."
    auto_expand: bool  # True for A0 (show immediately), False for A1 (collapsed)
```

### Extended ConversationState

```python
class ConversationState(TypedDict):
    # Existing fields (Phase 2)
    messages: Annotated[list[BaseMessage], add_messages]
    level: str  # A0, A1, A2, B1
    language: str  # es, de, fr
    grammar_feedback: NotRequired[list[GrammarFeedback]]
    new_vocabulary: NotRequired[list[VocabWord]]

    # New field (Phase 3)
    scaffolding: NotRequired[ScaffoldingConfig]
```

---

## API Contracts

### Scaffold Node LLM Prompt

```python
SCAFFOLD_PROMPT = """
You are helping a {level} level {language} learner respond to a conversation.

The AI tutor just said: "{ai_response}"

Generate scaffolding to help the learner respond:

1. WORD BANK: 4-6 relevant words/phrases they might use
2. HINT: A simple tip for how to respond (1 sentence in English)
3. SENTENCE STARTER: A partial sentence to get them started (optional, only if natural)

Level-specific guidelines:
- A0: Very basic words, include translations in parentheses
- A1: Simple phrases, minimal translations

Return JSON:
{{
    "word_bank": ["word1 (translation)", "word2", ...],
    "hint": "Try telling them about...",
    "sentence_starter": "Me gusta..." or null
}}
"""
```

### Chat Route Update

The `/chat` endpoint will be updated to include scaffolding in the template response:

```python
return templates.TemplateResponse(
    "partials/message_pair.html",
    {
        "request": request,
        "ai_message": result["messages"][-1].content,
        "grammar_feedback": result.get("grammar_feedback", []),
        "new_vocabulary": result.get("new_vocabulary", []),
        "scaffolding": result.get("scaffolding", {}),  # NEW
    }
)
```

---

## Dependencies

### External Libraries

- `langchain-anthropic`: Already installed (Claude API calls)
- `langgraph`: Already installed (conditional routing)

### Internal Modules

- `src/agent/state.py`: Extended with ScaffoldingConfig
- `src/agent/graph.py`: Updated with conditional edges
- `src/api/routes/chat.py`: Pass scaffolding to templates
- `src/templates/chat.html`: Include scaffold partial

---

## Implementation Plan

### Task Breakdown (Parallel Subagent Pattern)

Following `.agentic-framework/workflows/multi-agent-coordination.md`:

| Agent | Task | Duration | Dependencies |
|-------|------|----------|--------------|
| **Orchestrator** | Coordinate subagents, merge results | 30min | None |
| **Agent A** | Backend: scaffold node + routing | 1-2h | Design doc |
| **Agent B** | Frontend: scaffold UI templates | 1h | Design doc |
| **Agent C** | Testing: scaffold node tests | 1h | Agent A partial |

### Detailed Task List

#### Agent A: Backend (scaffold node + routing)

1. Create `src/agent/routing.py` with `needs_scaffolding()` function
2. Add `ScaffoldingConfig` to `src/agent/state.py`
3. Create `src/agent/nodes/scaffold.py` with scaffold node
4. Update `src/agent/graph.py` with conditional routing
5. Update `src/api/routes/chat.py` to pass scaffolding to templates

#### Agent B: Frontend (scaffold UI)

1. Create `src/templates/partials/scaffold.html`
2. Update `src/templates/partials/message_pair.html` to include scaffold
3. Add word bank click-to-insert JavaScript
4. Style scaffolding for all 3 themes (dark/light/ocean)

#### Agent C: Testing

1. Create `tests/test_routing.py` for routing function tests
2. Create `tests/test_scaffold_node.py` for scaffold node tests
3. Update `tests/test_agent_graph.py` for conditional routing tests
4. Add integration tests for full flow with scaffolding

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM generates poor word banks | Medium | Medium | Add validation, fallback to generic words |
| Scaffold adds too much latency | Low | Medium | Use faster model settings, consider caching |
| Conditional routing not tested properly | Medium | High | Comprehensive unit tests for routing function |
| UI breaks on empty scaffolding | Low | Low | Defensive template rendering |

---

## Testing Strategy

### Unit Tests

- `test_routing.py`: Test routing function returns correct paths
  - A0 → "scaffold"
  - A1 → "scaffold"
  - A2 → "analyze"
  - B1 → "analyze"

- `test_scaffold_node.py`: Test scaffold generation
  - Returns valid ScaffoldingConfig
  - Handles empty AI response gracefully
  - Respects level-specific guidelines

### Integration Tests

- `test_agent_graph.py`: Test conditional routing in graph
  - A0 flow: respond → scaffold → analyze → END
  - B1 flow: respond → analyze → END

### E2E Tests (Playwright)

- Test A0 chat shows word bank and hints
- Test A1 chat shows collapsed scaffolding
- Test B1 chat shows no scaffolding
- Test word bank click inserts text into input

---

## Success Criteria

### Functional

- [ ] A0 users see auto-expanded scaffolding with word bank
- [ ] A1 users see collapsed scaffolding (expandable)
- [ ] A2-B1 users see no scaffolding
- [ ] Word bank words are contextually relevant
- [ ] Hints are helpful and in English

### Technical

- [ ] Conditional routing works correctly in graph
- [ ] Scaffold node generates valid JSON
- [ ] UI renders scaffolding without errors
- [ ] All tests passing (target: maintain 98% coverage)

### Performance

- [ ] Scaffold generation adds <500ms to response
- [ ] No degradation in A2-B1 response times

---

## Appendix: LangGraph Conditional Edges Reference

```python
from langgraph.graph import StateGraph, END

def build_graph():
    graph = StateGraph(ConversationState)

    # Add nodes
    graph.add_node("respond", respond_node)
    graph.add_node("scaffold", scaffold_node)  # NEW
    graph.add_node("analyze", analyze_node)

    # Set entry point
    graph.set_entry_point("respond")

    # Conditional routing after respond
    graph.add_conditional_edges(
        "respond",  # Source node
        needs_scaffolding,  # Routing function
        {
            "scaffold": "scaffold",  # If returns "scaffold"
            "analyze": "analyze",    # If returns "analyze"
        }
    )

    # Scaffold always goes to analyze
    graph.add_edge("scaffold", "analyze")

    # Analyze ends the graph
    graph.add_edge("analyze", END)

    return graph.compile()
```

This is the key LangGraph pattern being learned in Phase 3.
