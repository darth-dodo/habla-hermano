# Add LangGraph Node

Add a new node to the Habla Hermano LangGraph conversation pipeline.

## When to Use
- Adding a new processing step to the conversation graph (respond -> scaffold -> analyze)
- Creating a new subgraph node (lesson, review)
- Adding conditional routing logic between nodes

## Steps

1. **Understand the current graph structure**
   - Read `src/agent/graph.py` for the main conversation pipeline
   - Read `src/agent/state.py` for `ConversationState` and `ReviewState` definitions
   - Read existing nodes in `src/agent/nodes/` to understand the pattern

2. **Create the node function** in `src/agent/nodes/{name}.py`
   - Import `ConversationState` (or `ReviewState` for review subgraph nodes) from `src/agent/state`
   - Use the centralized LLM factory from `src/agent/llm.py` (`get_llm()` or `get_llm_for_profile()`)
   - Node signature: `async def {name}_node(state: ConversationState) -> dict[str, Any]:`
   - Return a dict with only the state keys that changed
   - Use lazy imports for `src.api.config` to avoid circular dependencies
   - Add logging with `structlog.get_logger()` or `logging.getLogger(__name__)`

3. **Add state fields** if the node produces new data
   - Edit `src/agent/state.py`
   - Add fields to `ConversationState` TypedDict
   - Use `Annotated[list, add_messages]` pattern for message fields
   - Use `Optional[str]` or `Optional[list[str]]` for nullable fields

4. **Wire the node into the graph** in `src/agent/graph.py`
   - Add `graph.add_node("{name}", {name}_node)`
   - Add edges: `graph.add_edge("previous_node", "{name}")` or conditional edges
   - For conditional routing: `graph.add_conditional_edges("source", routing_fn, {...})`

5. **Export from `__init__.py`**
   - Add the node function to `src/agent/nodes/__init__.py`

6. **Write tests** in `tests/agent/nodes/test_{name}.py`
   - Mock the LLM with `unittest.mock.patch` and `AsyncMock`
   - Test with minimal ConversationState dict (only required fields)
   - Test edge cases: empty messages, missing optional fields
   - Follow existing test patterns in `tests/agent/nodes/test_analyze.py`

7. **Run quality checks**
   ```bash
   uv run pytest tests/agent/ -v
   uv run ruff check src/agent/ tests/agent/
   uv run mypy src/agent/
   ```

## Key Patterns

### Node Function Template
```python
async def example_node(state: ConversationState) -> dict[str, Any]:
    from src.api.config import get_settings
    from src.agent.llm import get_llm

    settings = get_settings()
    llm = get_llm(settings)

    messages = state["messages"]
    language = state.get("language", "es")
    level = state.get("level", "A1")

    # Process...

    return {"new_field": result}
```

### Conditional Routing
```python
def should_route(state: ConversationState) -> str:
    level = state.get("level", "A1")
    if level in ("A0", "A1"):
        return "scaffold"
    return "analyze"
```

## Architecture Notes
- The main pipeline is: `respond_node` -> (conditional) -> `scaffold_node` -> `analyze_node` -> END
- A0/A1 levels get scaffolding (word banks, hints), A2/B1 skip to analyze
- Review subgraph is separate: `generate_question` -> END; `evaluate_answer` -> `update_sm2` -> END
- Lesson subgraph: `load_step` -> `enhance_step` -> END
- All nodes use `src/agent/prompts.py` LANGUAGE_ADAPTER for multi-language support
