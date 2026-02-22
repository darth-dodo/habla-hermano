# Write Tests

Create pytest tests following the Habla Hermano testing patterns.

## When to Use
- Writing tests for new features or bug fixes
- Adding missing test coverage
- Creating integration tests for API endpoints

## Steps

1. **Identify the test type and location**
   | Component | Test Location | Fixtures |
   |-----------|--------------|----------|
   | Agent nodes | `tests/agent/nodes/test_{name}.py` | ConversationState dicts, mock LLM |
   | Agent graph | `tests/agent/test_graph.py` | Mock nodes, graph builder |
   | API routes | `tests/api/test_{name}.py` | test_client, async_client, mock_user |
   | Services | `tests/services/test_{name}.py` | Mock repositories |
   | Repositories | `tests/db/test_repository.py` | mock_supabase_client |
   | Lessons | `tests/lessons/test_{name}.py` | YAML fixtures |

2. **Use shared fixtures from `conftest.py`**
   - `mock_user` - AuthenticatedUser(id="test-user-123", email="test@example.com")
   - `auth_token` - Valid JWT token
   - `auth_headers` - {"Authorization": "Bearer {token}"}
   - `mock_supabase_client` - MagicMock with table/auth operations
   - `mock_settings` - Settings with test API key
   - `test_client` - Sync FastAPI TestClient (mocked graph + auth)
   - `async_client` - Async httpx client
   - `mock_compiled_graph` - MagicMock with ainvoke

3. **Write the test following project conventions**

   **Agent node test**:
   ```python
   from unittest.mock import AsyncMock, MagicMock, patch
   from langchain_core.messages import AIMessage, HumanMessage

   async def test_node_produces_expected_output():
       state = {
           "messages": [HumanMessage(content="Hola")],
           "language": "es",
           "level": "A1",
       }
       mock_llm = MagicMock()
       mock_llm.ainvoke = AsyncMock(
           return_value=AIMessage(content="Expected response")
       )
       with patch("src.agent.nodes.{name}.get_llm", return_value=mock_llm):
           result = await node_function(state)
       assert "expected_field" in result
   ```

   **API route test (sync)**:
   ```python
   def test_endpoint_returns_200(test_client):
       response = test_client.get("/path")
       assert response.status_code == 200

   def test_post_endpoint(test_client):
       response = test_client.post(
           "/path",
           data={"key": "value"},
           headers={"Content-Type": "application/x-www-form-urlencoded"},
       )
       assert response.status_code == 200
   ```

   **Service test**:
   ```python
   def test_service_method():
       mock_client = MagicMock()
       service = SomeService("user-123", client=mock_client)
       # Mock the repository's response
       mock_table = MagicMock()
       mock_client.table.return_value = mock_table
       mock_table.select.return_value = mock_table
       mock_table.eq.return_value = mock_table
       mock_table.execute.return_value = MagicMock(data=[{"col": "val"}])

       result = service.method()
       assert result == expected
   ```

   **Repository test**:
   ```python
   def test_repo_query():
       mock_client = MagicMock()
       mock_table = MagicMock()
       mock_client.table.return_value = mock_table
       # Chain the fluent API
       mock_table.select.return_value = mock_table
       mock_table.eq.return_value = mock_table
       mock_table.execute.return_value = MagicMock(data=[...])

       repo = SomeRepository("user-123", client=mock_client)
       result = repo.some_method()

       mock_client.table.assert_called_with("table_name")
       assert len(result) == expected_count
   ```

4. **Test naming conventions**
   - `test_{what}_{condition}` - e.g., `test_analyze_node_extracts_vocabulary`
   - `test_{what}_when_{scenario}` - e.g., `test_scaffold_when_level_is_a0`
   - `test_{what}_returns_{expected}` - e.g., `test_progress_returns_empty_for_new_user`

5. **Run and verify**
   ```bash
   # Run specific test file
   uv run pytest tests/{path}/test_{name}.py -v

   # Run with coverage for the module
   uv run pytest tests/{path}/ --cov=src.{module} --cov-report=term-missing

   # Run all tests
   uv run pytest -v
   ```

## Testing Conventions
- `asyncio_mode = "auto"` - no need for `@pytest.mark.asyncio`
- Fixtures auto-reset settings cache and rate limits between tests
- Mock external services (Supabase, Anthropic API) - never call real APIs in tests
- Use `MagicMock` for sync, `AsyncMock` for async operations
- Chain Supabase fluent API mocks: `.table().select().eq().execute()`
- Current coverage: 1810 tests, 97% coverage
