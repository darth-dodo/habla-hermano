# Debug LangGraph Agent

Investigate and fix issues in the LangGraph conversation pipeline.

## When to Use
- Chat responses are incorrect, empty, or missing expected fields
- Scaffolding not appearing for A0/A1 users
- Analysis node not detecting grammar errors or vocabulary
- Review words not being woven into conversations
- Checkpoint/session state issues

## Steps

1. **Identify the failing component**
   - Which node is producing incorrect output? (respond, scaffold, analyze)
   - Is it a routing issue? (conditional edges not working)
   - Is it a state issue? (fields not propagating between nodes)
   - Is it an LLM issue? (prompt producing unexpected output)

2. **Read the relevant code**
   - `src/agent/graph.py` - graph structure and routing
   - `src/agent/state.py` - state definitions
   - `src/agent/nodes/{node}.py` - specific node logic
   - `src/agent/prompts.py` - prompt templates
   - `src/agent/llm.py` - LLM factory configuration

3. **Check the graph flow**
   ```
   Main pipeline:
   START -> respond_node -> [needs_scaffolding?] -> scaffold_node? -> analyze_node -> END

   Review subgraph:
   generate_question -> END
   evaluate_answer -> update_sm2 -> END

   Lesson subgraph:
   load_step -> enhance_step -> END
   ```

4. **Common issues and fixes**

   **Node returns wrong state keys**:
   - Nodes should return ONLY the keys they modify
   - Check ConversationState TypedDict for valid field names
   - Messages use `Annotated[list, add_messages]` reducer (appends, doesn't replace)

   **Scaffolding not appearing**:
   - Check `needs_scaffolding()` routing function
   - A0/A1 should route to scaffold_node, A2/B1 should skip
   - Verify `level` field is populated in state

   **Review words not weaved**:
   - `respond_node` fetches review words from VocabularyRepository
   - Words are added to system prompt for natural inclusion
   - `analyze_node` detects usage and updates SM-2 silently
   - Check that user has vocabulary with `next_review_at <= now()`

   **LLM returning empty or malformed output**:
   - Check `get_llm()` configuration in `src/agent/llm.py`
   - Verify `ANTHROPIC_API_KEY` is set
   - Check prompt formatting (missing format keys cause KeyError)
   - Temperature too high (>0.9) can cause erratic output

   **Checkpoint/state not persisting**:
   - Production: PostgresSaver (needs `SUPABASE_DB_URL`)
   - Development: MemorySaver (in-memory, lost on restart)
   - Thread ID must be consistent across requests (session cookie or user_id)

5. **Write a reproducing test**
   ```python
   async def test_issue_reproduction():
       state = {
           "messages": [HumanMessage(content="Hola")],
           "language": "es",
           "level": "A1",
       }
       with patch("src.agent.llm.get_llm") as mock_llm:
           mock_llm.return_value.ainvoke = AsyncMock(
               return_value=AIMessage(content="response")
           )
           result = await problematic_node(state)
           assert result["expected_field"] == expected_value
   ```

6. **Run targeted tests**
   ```bash
   uv run pytest tests/agent/ -v -k "test_name"
   uv run pytest tests/agent/nodes/test_{node}.py -v
   ```

## State Field Reference
| Field | Type | Set By | Used By |
|-------|------|--------|---------|
| messages | list[BaseMessage] | respond_node | all nodes |
| language | str | initial config | all nodes (prompts) |
| level | str | initial config | routing, scaffolding |
| word_bank | list[str] | scaffold_node | frontend display |
| hint_text | str | scaffold_node | frontend display |
| sentence_starter | str | scaffold_node | frontend display |
| grammar_feedback | str | analyze_node | frontend display |
| new_vocabulary | list[str] | analyze_node | frontend display |
| review_words_offered | list[str] | respond_node | analyze_node |
| review_words_used | list[str] | analyze_node | SM-2 updates |
