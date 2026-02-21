# ADR-002: LangGraph StateGraph for Conversation Engine

**Date**: 2025-01-10
**Status**: Accepted
**Context**: Phase 1-3 (Basic Chat, Grammar Feedback, Scaffolding)
**Decider(s)**: Project Owner

---

## Summary

Adopt LangGraph StateGraph as the conversation engine for Habla Hermano, using conditional routing for scaffolding (A0/A1 only), grammar analysis, and pronunciation tips. This replaces simpler chain-based approaches with a graph that can route dynamically based on CEFR level, enabling level-appropriate pedagogy where beginners get more scaffolding and intermediate learners get deeper grammar analysis.

---

## Problem Statement

### The Challenge

Habla Hermano needs a conversation engine that goes beyond simple prompt-response cycles. The pedagogical requirements vary significantly by CEFR level:

1. **Level-dependent behavior**: A0/A1 learners need scaffolding (hints, translations, encouragement), while A2/B1 learners need grammar analysis and correction
2. **Multi-step AI operations**: A single user message triggers a chain of operations (respond -> scaffold -> analyze) that must compose cleanly
3. **Conditional routing**: Scaffolding should only activate for beginners; intermediate learners skip directly to analysis
4. **Persistence**: Conversations must survive server restarts via checkpointing
5. **Composability**: Lessons and reviews are distinct workflows that need their own graphs, composable with the main conversation

### Why This Matters

A language tutor that treats all learners the same is a poor tutor. The engine must route through different pedagogical paths depending on the learner's level, and it must do so in a way that is maintainable, testable, and extensible as new levels and features are added.

### Success Criteria

- [x] Conditional routing based on CEFR level (A0/A1 vs A2/B1)
- [x] Scaffolding node activates only for beginner levels
- [x] Grammar analysis runs for all levels with level-appropriate depth
- [x] Conversation state persists via PostgresSaver checkpointing
- [x] Subgraphs for lessons and reviews compose with the main graph
- [x] Multi-language support via LANGUAGE_ADAPTER

---

## Context

### Current State

**Before this decision**, the conversation engine was undefined. The simplest approach would be a linear LangChain chain:

```
User Message → LLM Call → Response
```

This works for a basic chatbot but cannot handle:
- Branching logic (scaffold for A0/A1, skip for A2/B1)
- Multi-step post-processing (respond, then scaffold, then analyze)
- Separate workflows for lessons vs free conversation
- State persistence with checkpointing

**Technical Constraints**:

- Must integrate with FastAPI backend (async support required)
- Must support PostgresSaver for production persistence (see ADR-001)
- Must handle multiple target languages (Spanish, French, etc.)
- Must keep response times reasonable (<3s for full pipeline)
- Must be testable at the node level (unit tests per node)

### Requirements

**Functional Requirements**:

- Respond to user messages with level-appropriate conversation
- Scaffold beginner learners with hints, translations, and encouragement
- Analyze grammar for all levels with appropriate depth
- Run lesson workflows (load lesson -> enhance with LLM -> present)
- Run review workflows (generate question -> evaluate answer)

**Non-Functional Requirements**:

- **Testability**: Each node independently testable
- **Extensibility**: Adding a new node (e.g., pronunciation) should not require refactoring existing nodes
- **Persistence**: Native checkpointing support for production deployment
- **Performance**: Full graph execution <3s including LLM calls

---

## Options Considered

### Option A: LangGraph StateGraph (Chosen)

**Description**:
Graph-based state machine using LangGraph's StateGraph with typed state, conditional edges, and native checkpointing. Each AI operation is a node; routing between nodes is controlled by conditional edge functions that inspect conversation state (particularly CEFR level).

**Implementation**:
- `ConversationState` TypedDict with `messages` (using `add_messages` reducer), `level`, `target_language`, and metadata
- Nodes: `respond` (generate tutor response), `scaffold` (add beginner hints), `analyze` (grammar feedback)
- Conditional edge after `respond`: route to `scaffold` if level is A0/A1, else route to `analyze`
- PostgresSaver checkpointer for persistence
- Subgraphs: `lesson_graph` and `review_graph` as separate StateGraphs

**Pros**:

- Conditional routing is a first-class concept (not bolted on)
- Each node has a single responsibility, independently testable
- Native checkpointing via PostgresSaver (see ADR-001)
- Subgraph composition for lessons and reviews
- Built-in state management with typed reducers
- Visual debugging with graph.get_graph().draw_mermaid()

**Cons**:

- More boilerplate than a simple chain
- Learning curve for StateGraph concepts (nodes, edges, reducers)
- LangGraph is a relatively young library with evolving APIs
- Overkill for truly simple conversational flows

**Risks**:

- **API instability**: LangGraph is actively evolving; mitigate by pinning versions
- **Debugging complexity**: Graph execution harder to trace than linear chains; mitigate with logging per node

**Estimated Effort**: 2-3 days for core graph, +1-2 days for subgraphs

---

### Option B: LangChain Chains (Sequential)

**Description**:
Linear chain of LLM calls using LangChain's chain composition (`|` operator). Each step in the chain runs sequentially: respond, then scaffold, then analyze.

**Implementation**:
- RunnableSequence chaining prompt | llm | parser for each step
- Conditional logic via Python if/else wrapping chain invocation
- Manual state passing between chain steps

**Pros**:

- Simpler mental model (linear pipeline)
- Less boilerplate for basic flows
- Well-documented with many examples

**Cons**:

- No native conditional routing (must wrap in Python control flow)
- No subgraph composition (lessons/reviews would be separate, unrelated chains)
- No built-in checkpointing (must implement manually)
- Adding new steps requires modifying the chain definition
- State management is manual (passing dicts between steps)

**Risks**:

- **Complexity creep**: Conditional logic in Python quickly becomes tangled as levels and features grow
- **No persistence**: Must build custom checkpointing

**Estimated Effort**: 1-2 days for basic chain, +3-4 days for custom persistence and routing

---

### Option C: Custom State Machine

**Description**:
Hand-rolled state machine with explicit state transitions, custom node execution, and manual persistence.

**Implementation**:
- Python classes for states and transitions
- Custom dispatcher for node execution
- Manual serialization for persistence
- Custom graph traversal logic

**Pros**:

- Full control over every aspect of execution
- No external dependencies beyond the LLM client
- Can optimize for specific use case

**Cons**:

- Reinventing well-solved problems (state management, checkpointing, graph traversal)
- No ecosystem tooling (visualization, debugging)
- Significant maintenance burden
- Must implement checkpointing from scratch
- Testing infrastructure must be built from scratch

**Risks**:

- **Maintenance burden**: Every feature LangGraph provides for free must be maintained
- **Bug surface area**: Custom state machines are notoriously difficult to get right

**Estimated Effort**: 5-7 days + ongoing maintenance

---

## Comparison Matrix

| Criteria                    | Weight | Option A (LangGraph) | Option B (Chains) | Option C (Custom) |
| --------------------------- | ------ | -------------------- | ------------------ | ------------------ |
| **Conditional Routing**     | High   | 5                    | 2                  | 4                  |
| **Checkpointing**           | High   | 5                    | 1                  | 2                  |
| **Testability**             | High   | 5                    | 3                  | 4                  |
| **Extensibility**           | High   | 5                    | 2                  | 3                  |
| **Subgraph Composition**    | High   | 5                    | 1                  | 3                  |
| **Implementation Effort**   | Medium | 4                    | 4                  | 2                  |
| **Simplicity**              | Medium | 3                    | 5                  | 2                  |
| **Dependency Footprint**    | Low    | 3                    | 3                  | 5                  |
| **Total Score**             | -      | **35**               | 21                 | 25                 |

**Scoring**: 1 = Poor, 2 = Below Average, 3 = Acceptable, 4 = Good, 5 = Excellent
**Note**: For negative criteria (Effort, Simplicity inverted), higher score = better outcome

---

## Decision

### Chosen Option

**Selected**: Option A: LangGraph StateGraph

**Rationale**:
LangGraph StateGraph provides conditional routing as a first-class concept, which is critical for level-based scaffolding. The native checkpointing via PostgresSaver (see ADR-001) eliminates custom persistence code. Subgraph composition cleanly separates lesson and review workflows from the main conversation graph. Each node has a single responsibility, making the system testable and extensible.

**Key Factors**:

- Conditional routing is the core requirement (A0/A1 scaffolding vs A2/B1 analysis)
- PostgresSaver checkpointing integrates directly with Supabase (ADR-001)
- Subgraph composition keeps lesson and review logic isolated
- Node-level testability aligns with project quality standards
- Graph visualization aids debugging and documentation

**Trade-offs Accepted**:

- More boilerplate than a simple chain (acceptable for routing flexibility)
- LangGraph learning curve (one-time investment, team is small)
- Dependency on LangGraph library evolution (mitigated by version pinning)

---

## Architecture

### Main Conversation Graph

```
START
  │
  ▼
respond (generate tutor response)
  │
  ▼
[conditional: needs_scaffold?]
  │                    │
  │ level=A0/A1        │ level=A2/B1
  ▼                    ▼
scaffold            analyze
(hints,             (grammar
translations,       feedback,
encouragement)      corrections)
  │                    │
  ▼                    ▼
  └────────┬───────────┘
           │
           ▼
          END
```

### State Definition

```python
class ConversationState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    level: str           # CEFR level: A0, A1, A2, B1
    target_language: str  # es, fr, de, etc.
    session_id: str
    vocabulary: list[str]
    grammar_notes: list[str]
```

### Routing Logic

```python
def needs_scaffold(state: ConversationState) -> str:
    """Route to scaffold for beginners, analyze for intermediate."""
    if state["level"] in ("A0", "A1"):
        return "scaffold"
    return "analyze"
```

### Subgraphs

**Lesson Graph**: `START -> load_lesson -> enhance_with_llm -> END`
- Loads structured lesson content, enhances with conversational framing

**Review Graph**: `START -> generate_question -> [wait for answer] -> evaluate_answer -> END`
- Generates level-appropriate review questions, evaluates user responses

### Key Components

- **LEVEL_PROMPTS**: Dict mapping CEFR levels to system prompts with level-appropriate instructions
- **LANGUAGE_ADAPTER**: Handles multi-language support (Spanish, French, etc.) with language-specific pronunciation and grammar rules

---

## Consequences

### Positive Outcomes

**Immediate Benefits**:

- Clean separation of concerns: each node does one thing (respond, scaffold, analyze)
- Conditional routing handles level-based pedagogy without tangled if/else
- Native checkpointing via PostgresSaver works out of the box with Supabase
- Subgraphs keep lesson and review logic isolated from conversation flow

**Long-term Benefits**:

- Adding new nodes (e.g., pronunciation tips, cultural notes) requires only adding a node and an edge
- New CEFR levels (B2, C1) can be supported by extending the routing function
- Graph visualization provides living documentation of the conversation flow
- Checkpointing enables features like conversation resume and progress tracking

### Negative Outcomes

**Immediate Costs**:

- LangGraph dependency adds to the project's dependency tree
- StateGraph boilerplate for what could start as a simple chat
- Team must learn LangGraph concepts (nodes, edges, reducers, checkpointers)

**Technical Debt Created**:

- Minimal; the graph structure is clean and each node is independently replaceable

**Trade-offs**:

- Simple operations (just responding) still go through the graph machinery (acceptable overhead)
- Graph debugging requires understanding of LangGraph internals (mitigated by per-node logging)

### Risks and Mitigation

**Risk 1**: LangGraph API changes in future versions

- **Probability**: Medium (library is actively evolving)
- **Impact**: Refactoring required for breaking changes
- **Mitigation**: Pin LangGraph version, update deliberately, keep nodes loosely coupled to framework

**Risk 2**: Graph complexity grows unwieldy as features are added

- **Probability**: Low (subgraph composition manages complexity)
- **Impact**: Harder to understand and debug the full flow
- **Mitigation**: Keep subgraphs small, document graph topology, use visualization tools

**Risk 3**: Performance overhead from graph execution

- **Probability**: Low (graph overhead is negligible vs LLM latency)
- **Impact**: Slower response times
- **Mitigation**: Profile execution, optimize hot paths, LLM calls dominate latency regardless

---

## Key Files

| File | Purpose |
| ---- | ------- |
| `src/agent/graph.py` | Main conversation StateGraph definition |
| `src/agent/state.py` | ConversationState TypedDict and reducers |
| `src/agent/routing.py` | Conditional routing functions (needs_scaffold, etc.) |
| `src/agent/nodes/respond.py` | Tutor response generation node |
| `src/agent/nodes/scaffold.py` | Beginner scaffolding node (A0/A1) |
| `src/agent/nodes/analyze.py` | Grammar analysis node |
| `src/agent/prompts.py` | LEVEL_PROMPTS dict and LANGUAGE_ADAPTER |
| `src/agent/lesson_graph.py` | Lesson subgraph (load -> enhance -> END) |
| `src/agent/review_graph.py` | Review subgraph (generate_question -> evaluate_answer) |

---

## Related Decisions

**Supersedes**:

- None (first conversation engine decision)

**Related To**:

- ADR-001: Supabase provides PostgresSaver for LangGraph checkpointing

**Depends On**:

- ADR-001 (PostgresSaver requires Supabase Postgres)

**Informs**:

- Future ADRs for new graph nodes (pronunciation, cultural context)
- Future ADRs for advanced routing (B2/C1 levels, adaptive difficulty)
- Future ADRs for real-time features (streaming responses via graph)

---

## References

### External Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/) - Official docs
- [LangGraph StateGraph Tutorial](https://langchain-ai.github.io/langgraph/tutorials/introduction/) - Getting started
- [LangGraph Checkpointing](https://langchain-ai.github.io/langgraph/concepts/persistence/) - Persistence patterns
- [CEFR Levels](https://www.coe.int/en/web/common-european-framework-reference-languages/level-descriptions) - Level definitions

### Code References

- `src/agent/graph.py` - Main graph implementation
- `src/agent/state.py` - State definition
- `src/agent/nodes/` - Individual node implementations

---

## Metadata

**ADR Number**: 002
**Created**: 2025-01-10
**Last Updated**: 2025-01-10
**Version**: 1.0

**Authors**: Claude (AI Assistant)
**Reviewers**: Project Owner

**Tags**: langgraph, conversation-engine, state-machine, conditional-routing, scaffolding, cefr

**Project Phase**: Development

---

## Notes

This ADR establishes the foundational architecture for Habla Hermano's conversation engine. The choice of LangGraph StateGraph over simpler alternatives is driven by the pedagogical requirement to treat learners differently based on their CEFR level. A linear chain cannot cleanly express "scaffold if beginner, analyze if intermediate" without becoming tangled, while a graph makes this routing explicit and visual.

The relationship with ADR-001 is direct: Supabase Postgres (chosen in ADR-001) provides the backing store for LangGraph's PostgresSaver checkpointer, enabling persistent conversations without custom persistence code.

---

**Status**: ACCEPTED
**Next Review**: 2025-02-10
