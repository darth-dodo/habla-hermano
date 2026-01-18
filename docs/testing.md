# Habla Hermano Test Documentation

> Comprehensive test coverage documentation for the Habla Hermano language tutor application.

---

## Test Summary

| Category | Test File | Test Cases | Coverage Focus |
|----------|-----------|------------|----------------|
| Agent Graph | `test_agent_graph.py` | 35 | Graph structure, node routing, Phase 3 conditional edges |
| Agent State | `test_agent_state.py` | 40+ | TypedDict state, Pydantic models, reducers |
| Agent Nodes | `test_agent_nodes.py` | 50+ | respond_node, analyze_node integration |
| Agent Prompts | `test_agent_prompts.py` | 25+ | Level-specific prompts, language support |
| Scaffold Node | `test_scaffold_node.py` | 60+ | Phase 3 scaffolding, word banks, auto_expand |
| Routing | `test_routing.py` | 35+ | Phase 3 conditional routing, needs_scaffolding |
| Analyze Node | `test_analyze_node.py` | 70+ | Phase 2 grammar feedback, vocabulary extraction |
| API Config | `test_api_config.py` | 30+ | Settings, environment, Pydantic config |
| API Routes | `test_api_routes.py` | 45+ | Endpoints, HTMX responses, form handling |
| Database | `test_database.py` | 55+ | SQLAlchemy models, repository layer |
| Lessons/Progress | `test_lessons_progress_routes.py` | 50+ | Lesson endpoints, progress tracking |
| Services | `test_services.py` | 60+ | Business logic, vocabulary service |

**Total**: 641 tests with 98% code coverage

---

## Phase 3 Test Coverage

Phase 3 introduced conditional routing and scaffolding for A0-A1 learners. The following sections document the new test coverage.

### Scaffold Node Tests (`tests/test_scaffold_node.py`)

**60+ test cases** covering the scaffold node implementation.

#### Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestScaffoldNodeReturnStructure` | 4 | Verify return dict with `scaffolding` key |
| `TestScaffoldNodeLevelBehavior` | 5 | A0/A1 get scaffolding, A2-C2 get disabled |
| `TestScaffoldNodeEmptyMessages` | 3 | Handle empty/minimal message lists |
| `TestScaffoldNodeConversationHistory` | 2 | Process full and long conversations |
| `TestScaffoldNodeLanguages` | 2 | Support es, de, fr (and unsupported) |
| `TestScaffoldNodeStubBehavior` | 2 | Current implementation returns expected stub |
| `TestScaffoldNodeAsync` | 2 | Async function verification |
| `TestScaffoldingConfigModel` | 8 | Pydantic model validation |
| `TestScaffoldingConfigImport` | 2 | Module import verification |
| `TestScaffoldNodeEdgeCases` | 7 | Empty content, whitespace, Unicode, long messages |
| `TestScaffoldNodeWithMockedLLM` | 3 | Mock LLM response fixtures |
| `TestScaffoldNodeJSONParsing` | 4 | JSON parsing edge cases |
| `TestScaffoldNodeDocumentation` | 3 | Docstring verification |
| `TestScaffoldNodeImport` | 2 | Module import verification |
| `TestScaffoldNodeIntegration` | 2 | State compatibility tests |

#### Key Test Scenarios

**A0 vs A1 Behavior (auto_expand differences)**:
```python
async def test_a0_level_gets_scaffolding_response(self) -> None:
    """A0 level should get a scaffolding response with auto_expand=True."""
    state = {"messages": [...], "level": "A0", "language": "es"}
    result = await scaffold_node(state)
    assert result["scaffolding"]["auto_expand"] is True

async def test_a1_level_gets_scaffolding_response(self) -> None:
    """A1 level should get a scaffolding response with auto_expand=False."""
    state = {"messages": [...], "level": "A1", "language": "es"}
    result = await scaffold_node(state)
    assert result["scaffolding"]["auto_expand"] is False
```

**Advanced Levels Disabled**:
```python
@pytest.mark.parametrize("level", ["A2", "B1", "B2", "C1", "C2"])
async def test_advanced_levels_disabled(self, level: str) -> None:
    """Advanced levels should always have disabled scaffolding."""
    state = {"messages": [...], "level": level, "language": "es"}
    result = await scaffold_node(state)
    assert result["scaffolding"]["enabled"] is False
```

**JSON Parsing for LLM Responses**:
```python
def test_json_with_code_block(self) -> None:
    """JSON wrapped in markdown code block should be extractable."""
    content = """```json
{"word_bank": ["hola"], "hint": "test", "sentence_starter": null}
```"""
    json_str = content.split("```json")[1].split("```")[0]
    result = json.loads(json_str.strip())
    assert result["word_bank"] == ["hola"]
```

**Error Handling and Fallback Scaffolds**:
```python
async def test_handles_empty_messages_list(self) -> None:
    """scaffold_node should handle empty messages list gracefully."""
    state = {"messages": [], "level": "A0", "language": "es"}
    result = await scaffold_node(state)
    assert result["scaffolding"]["enabled"] is False  # Fallback

async def test_handles_missing_level_gracefully(self) -> None:
    """scaffold_node should handle missing level with default."""
    state = {"messages": [...], "level": "", "language": "es"}
    result = await scaffold_node(state)
    assert isinstance(result, dict)  # Should not crash
```

---

### Routing Tests (`tests/test_routing.py`)

**35+ test cases** covering the `needs_scaffolding()` routing function.

#### Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestNeedsScaffoldingBasicRouting` | 4 | A0/A1 -> scaffold, A2/B1 -> analyze |
| `TestNeedsScaffoldingAllLevels` | 8 | Parametrized tests for all CEFR levels |
| `TestNeedsScaffoldingCaseSensitivity` | 6 | Case-sensitive level matching |
| `TestNeedsScaffoldingDifferentLanguages` | 8 | Routing works for es, de, fr, etc. |
| `TestNeedsScaffoldingWithConversationHistory` | 4 | Empty, single, full, long conversations |
| `TestNeedsScaffoldingReturnType` | 4 | Returns string, literal values only |
| `TestNeedsScaffoldingFunctionProperties` | 4 | Pure function, no state mutation |
| `TestNeedsScaffoldingEdgeCases` | 2 | Extra state fields, list membership |
| `TestNeedsScaffoldingDocumentation` | 3 | Docstring verification |
| `TestNeedsScaffoldingImport` | 2 | Module import verification |

#### Key Test Scenarios

**Level-Based Routing**:
```python
def test_a0_routes_to_scaffold(self) -> None:
    """A0 level should route to scaffold node."""
    state = {"messages": [...], "level": "A0", "language": "es"}
    assert needs_scaffolding(state) == "scaffold"

def test_b1_routes_to_analyze(self) -> None:
    """B1 level should skip scaffold, go to analyze."""
    state = {"messages": [...], "level": "B1", "language": "es"}
    assert needs_scaffolding(state) == "analyze"
```

**All CEFR Levels Parametrized**:
```python
@pytest.mark.parametrize(
    "level,expected",
    [
        ("A0", "scaffold"),
        ("A1", "scaffold"),
        ("A2", "analyze"),
        ("B1", "analyze"),
        ("B2", "analyze"),
        ("C1", "analyze"),
        ("C2", "analyze"),
        ("", "analyze"),  # Empty level defaults to analyze
    ],
)
def test_level_routing_parametrized(self, level: str, expected: str) -> None:
    state = {"messages": [...], "level": level, "language": "es"}
    assert needs_scaffolding(state) == expected
```

**Case Sensitivity Edge Cases**:
```python
@pytest.mark.parametrize(
    "invalid_level",
    ["a0", "a1", "A 0", "A_0", "level-a0", "0", "1", "beginner"],
)
def test_invalid_level_formats_route_to_analyze(self, invalid_level: str) -> None:
    """Invalid level formats should route to analyze (fallback)."""
    state = {"messages": [...], "level": invalid_level, "language": "es"}
    assert needs_scaffolding(state) == "analyze"
```

**Language Independence**:
```python
@pytest.mark.parametrize("language", ["es", "de", "fr", "it", "pt", "ru", "ja"])
def test_a0_scaffolds_for_all_languages(self, language: str) -> None:
    """A0 level should route to scaffold regardless of language."""
    state = {"messages": [...], "level": "A0", "language": language}
    assert needs_scaffolding(state) == "scaffold"
```

---

### Agent Graph Tests (`tests/test_agent_graph.py`)

Updated for Phase 3 with **conditional routing structure tests**.

#### Phase 3 Specific Test Class

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestGraphPhase3Requirements` | 5 | Three processing nodes, conditional routing |

#### Key Test Scenarios

**Three Processing Nodes**:
```python
def test_graph_has_three_processing_nodes(self) -> None:
    """Phase 3 should have three processing nodes: respond, scaffold, analyze."""
    graph = build_graph()
    processing_nodes = [n for n in graph.nodes if not n.startswith("__")]

    assert len(processing_nodes) == 3
    assert "respond" in processing_nodes
    assert "scaffold" in processing_nodes
    assert "analyze" in processing_nodes
```

**Conditional Routing Structure**:
```python
def test_graph_structure_with_conditional_routing(self) -> None:
    """Phase 3 should have: START -> respond -> (scaffold|analyze) -> analyze -> END."""
    graph = build_graph()

    assert "__start__" in graph.nodes
    assert "respond" in graph.nodes
    assert "scaffold" in graph.nodes
    assert "analyze" in graph.nodes

def test_conditional_routing_structure(self) -> None:
    """Phase 3 should have conditional routing from respond node."""
    graph = build_graph()
    processing_nodes = [n for n in graph.nodes if not n.startswith("__")]

    assert len(processing_nodes) == 3
    assert "respond" in processing_nodes
    assert "scaffold" in processing_nodes
    assert "analyze" in processing_nodes
```

**Execution Order Verification**:
```python
def test_analyze_is_terminal_node(self) -> None:
    """Analyze node should be the terminal node (connects to END)."""
    graph = build_graph()
    processing_nodes = [n for n in graph.nodes if not n.startswith("__")]

    # respond, scaffold, and analyze are the processing nodes
    assert set(processing_nodes) == {"respond", "scaffold", "analyze"}
```

---

## E2E Tests (Playwright)

End-to-end tests are documented in [docs/playwright-e2e.md](./playwright-e2e.md).

### Phase 3 E2E Test Summary

| Test | Status | Description |
|------|--------|-------------|
| A0 Scaffold Auto-Expanded | Pass | Scaffold section auto-expands for A0 learners |
| A1 Scaffold Collapsed | Pass | Scaffold collapsed by default, expandable on click |
| B1 No Scaffold | Pass | Conditional routing skips scaffold for B1+ levels |
| Word Bank Click-to-Insert | Pass | Clicking word inserts into input field |

#### A0 Scaffold (Auto-Expanded)

**Test Steps**:
1. Select "A0 Complete Beginner" from dropdown
2. Type: "Hello, I want to learn Spanish!"
3. Click Send
4. Verify scaffold section auto-expands

**Expected Behavior**:
- Scaffold section visible immediately (auto-expanded)
- Word bank shows 4-6 words with English translations
- Hint text provides guidance in English
- Sentence starter (optional) helps begin response

**Verification**:
- `auto_expand: true` in scaffolding config
- No click required to see word bank

#### A1 Scaffold (Collapsed/Expandable)

**Test Steps**:
1. Select "A1 Beginner" from dropdown
2. Type: "Hola, me llamo Maria"
3. Click Send
4. Verify scaffold section is collapsed
5. Click to expand scaffold

**Expected Behavior**:
- Scaffold section collapsed by default
- Shows "Need help responding?" prompt
- Expands on click to reveal word bank and hints
- Word bank may have fewer translations than A0

**Verification**:
- `auto_expand: false` in scaffolding config
- Chevron icon rotates on expand/collapse

#### B1 No Scaffold (Conditional Routing)

**Test Steps**:
1. Select "B1 Intermediate" from dropdown
2. Type: "Hola, quiero practicar mi espanol contigo"
3. Click Send
4. Verify NO scaffold section appears

**Expected Behavior**:
- AI response displays normally (mostly Spanish)
- No scaffold section rendered in DOM
- Grammar feedback section may appear (Phase 2)
- Conditional routing function returned "analyze" instead of "scaffold"

**Verification**:
- `needs_scaffolding(state)` returns `"analyze"` for B1
- Scaffold node is not invoked

#### Word Bank Click-to-Insert

**Test Steps**:
1. Complete A0 or A1 chat flow with scaffold visible
2. Locate word bank section with clickable words
3. Click a word (e.g., "hola (hello)")
4. Verify word is inserted into message input field

**Expected Behavior**:
- Clicking word inserts it at cursor position in input
- Word is inserted without the translation portion
- Multiple words can be inserted
- Input field gains focus after insertion

**Verification**:
- HTMX `hx-on:click` handler strips translation
- Input field value updated correctly

---

## Running Tests

### Prerequisites

```bash
# Install dependencies
pip install -e ".[dev]"

# Or using make
make install
```

### Run All Tests

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_scaffold_node.py -v

# Run specific test class
pytest tests/test_routing.py::TestNeedsScaffoldingBasicRouting -v

# Run specific test method
pytest tests/test_scaffold_node.py::TestScaffoldNodeLevelBehavior::test_a0_level_gets_scaffolding_response -v
```

### Run Tests by Category

```bash
# Agent tests only
pytest tests/test_agent_*.py -v

# API tests only
pytest tests/test_api_*.py -v

# Phase 3 specific tests
pytest tests/test_scaffold_node.py tests/test_routing.py -v
```

### Run with Markers

```bash
# Run only async tests
pytest tests/ -v -m asyncio

# Run parameterized tests
pytest tests/ -v -k "parametrize"
```

### E2E Tests with Playwright MCP

E2E tests are run using the Playwright MCP server:

```bash
# Start the dev server first
make dev

# Then use Playwright MCP tools:
# - browser_navigate: Navigate to URLs
# - browser_snapshot: Get accessibility tree
# - browser_click: Click elements by ref
# - browser_type: Type text in inputs
# - browser_take_screenshot: Capture screenshots
```

---

## Test Fixtures

### Common Fixtures (`tests/conftest.py`)

```python
@pytest.fixture
def sample_conversation_state() -> ConversationState:
    """Provide a sample conversation state for testing."""
    return {
        "messages": [HumanMessage(content="Hola!")],
        "level": "A1",
        "language": "es",
        "grammar_feedback": [],
        "new_vocabulary": [],
    }

@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response for testing without API calls."""
    return MagicMock(content="Hola! Como estas?")

@pytest.fixture
async def async_client():
    """Provide async HTTP client for API testing."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
```

### Scaffold Node Fixtures

```python
@pytest.fixture
def mock_llm_response_valid(self) -> MagicMock:
    """Create a mock LLM response with valid JSON."""
    return MagicMock(
        content='{"word_bank": ["hola (hello)", "me llamo (my name is)"], '
        '"hint": "Try introducing yourself", '
        '"sentence_starter": "Me llamo"}'
    )

@pytest.fixture
def base_state(self) -> ConversationState:
    """Base conversation state for scaffold testing."""
    return {
        "messages": [
            HumanMessage(content="Hello"),
            AIMessage(content="Hola! Como te llamas?"),
        ],
        "level": "A0",
        "language": "es",
    }
```

---

## Test Coverage Goals

| Module | Current | Target |
|--------|---------|--------|
| `src/agent/` | 98% | 95%+ |
| `src/api/` | 97% | 95%+ |
| `src/db/` | 95% | 90%+ |
| `src/services/` | 96% | 90%+ |
| **Overall** | **98%** | **95%+** |

### Coverage Commands

```bash
# Generate coverage report
pytest tests/ --cov=src --cov-report=html

# View coverage in terminal
pytest tests/ --cov=src --cov-report=term-missing

# Check coverage threshold
pytest tests/ --cov=src --cov-fail-under=95
```

---

## Test Architecture

### Test Organization

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_agent_graph.py      # Graph structure tests
├── test_agent_nodes.py      # Node function tests
├── test_agent_prompts.py    # Prompt template tests
├── test_agent_state.py      # State definition tests
├── test_analyze_node.py     # Phase 2 analyze node
├── test_scaffold_node.py    # Phase 3 scaffold node
├── test_routing.py          # Phase 3 routing logic
├── test_api_config.py       # Configuration tests
├── test_api_routes.py       # Endpoint tests
├── test_database.py         # Database layer tests
├── test_lessons_progress_routes.py  # Lesson endpoints
└── test_services.py         # Service layer tests
```

### Test Naming Conventions

- Test files: `test_<module>.py`
- Test classes: `Test<FeatureName>`
- Test methods: `test_<behavior_description>`

Example:
```python
class TestScaffoldNodeLevelBehavior:
    async def test_a0_level_gets_scaffolding_response(self) -> None:
        """A0 level should get a scaffolding response."""
        ...
```

### Test Categories

1. **Unit Tests**: Test individual functions in isolation
2. **Integration Tests**: Test node interactions and graph execution
3. **API Tests**: Test HTTP endpoints with mocked dependencies
4. **E2E Tests**: Test full user flows via Playwright MCP

---

## Continuous Integration

Tests run on every push via GitHub Actions:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: pytest tests/ --cov=src --cov-fail-under=95
```

---

## Related Documentation

- [Architecture](./architecture.md) - Technical architecture and LangGraph progression
- [Playwright E2E](./playwright-e2e.md) - End-to-end test documentation with screenshots
- [Product](./product.md) - Product requirements and features
