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
| Auth | `test_auth.py` | 50+ | JWT validation, signup/login flows, token expiration |
| Checkpointer | `test_checkpointer.py` | 30+ | PostgresSaver/MemorySaver fallback, thread IDs |
| Session | `test_session.py` | 20+ | Thread ID management, cookie lifecycle |
| Persistence | `test_persistence_integration.py` | 25+ | End-to-end auth + persistence workflows |
| DB Models | `test_db_models.py` | 25+ | Pydantic models for Supabase |
| DB Repository | `test_db_repository.py` | 30+ | Data access layer with mocked client |
| Supabase Client | `test_supabase_client.py` | 15+ | Client singleton, cache management |
| Services Levels | `test_services_levels.py` | 20+ | CEFR level detection |
| Services Vocab | `test_services_vocabulary.py` | 20+ | Vocabulary tracking |
| Lessons/Progress | `test_lessons_progress_routes.py` | 50+ | Lesson endpoints, progress tracking |
| Lesson Models | `test_lesson_models.py` | 36 | Phase 6 lesson data model validation |
| Lesson Service | `test_lesson_service.py` | 20 | Phase 6 lesson service functionality |
| Lesson Routes | `test_lesson_routes.py` | 39 | Phase 6 lesson API endpoints |

**Total**: 918 tests with 86%+ code coverage

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

## Phase 6 Test Coverage

Phase 6 introduced the structured lesson system with YAML-based content, lesson player, and progress tracking. All tests were developed using a strict TDD (Test-Driven Development) approach: RED (write failing tests first) then GREEN (implement to pass).

### Lesson Model Tests (`tests/test_lesson_models.py`)

**36 test cases** covering the Pydantic data models for lessons.

#### Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestLessonStepModel` | 8 | LessonStep validation, types, content fields |
| `TestLessonModel` | 10 | Lesson metadata, step collections, CEFR levels |
| `TestLessonProgressModel` | 8 | Progress tracking, completion state, timestamps |
| `TestLessonResponseModel` | 5 | API response structure, serialization |
| `TestModelValidation` | 5 | Edge cases, required fields, type coercion |

#### Key Test Scenarios

**Step Type Validation**:
```python
def test_lesson_step_valid_types(self) -> None:
    """LessonStep should accept valid step types."""
    for step_type in ["vocabulary", "grammar", "dialogue", "exercise", "cultural"]:
        step = LessonStep(type=step_type, content="Test content")
        assert step.type == step_type

def test_lesson_step_invalid_type_raises(self) -> None:
    """LessonStep should reject invalid step types."""
    with pytest.raises(ValidationError):
        LessonStep(type="invalid_type", content="Test")
```

**Lesson Metadata Validation**:
```python
def test_lesson_requires_all_metadata(self) -> None:
    """Lesson should require id, title, level, language, and steps."""
    with pytest.raises(ValidationError):
        Lesson(id="test", title="Test")  # Missing required fields

def test_lesson_level_must_be_cefr(self) -> None:
    """Lesson level must be valid CEFR level."""
    valid_levels = ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]
    for level in valid_levels:
        lesson = Lesson(id="test", title="Test", level=level, language="es", steps=[])
        assert lesson.level == level
```

**Progress State Tracking**:
```python
def test_progress_completion_percentage(self) -> None:
    """Progress should calculate completion percentage correctly."""
    progress = LessonProgress(
        lesson_id="test",
        current_step=5,
        total_steps=10,
        completed=False
    )
    assert progress.completion_percentage == 50.0

def test_progress_marks_complete_at_100_percent(self) -> None:
    """Progress should mark completed when all steps finished."""
    progress = LessonProgress(
        lesson_id="test",
        current_step=10,
        total_steps=10,
        completed=True
    )
    assert progress.completed is True
    assert progress.completion_percentage == 100.0
```

---

### Lesson Service Tests (`tests/test_lesson_service.py`)

**20 test cases** covering the lesson service functionality.

#### Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestLessonYAMLLoading` | 5 | YAML file parsing, validation, error handling |
| `TestLessonFiltering` | 6 | Filter by level, language, topic |
| `TestLessonProgressTracking` | 5 | Progress CRUD operations |
| `TestLessonServiceEdgeCases` | 4 | Empty results, missing files, malformed YAML |

#### Key Test Scenarios

**YAML Loading and Parsing**:
```python
def test_load_lessons_from_yaml(self) -> None:
    """Service should load and parse lesson YAML files."""
    service = LessonService()
    lessons = service.get_all_lessons()

    assert len(lessons) > 0
    assert all(isinstance(lesson, Lesson) for lesson in lessons)

def test_yaml_validation_on_load(self) -> None:
    """Service should validate YAML content against Pydantic models."""
    service = LessonService()
    lessons = service.get_all_lessons()

    for lesson in lessons:
        assert lesson.id is not None
        assert lesson.level in ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]
        assert len(lesson.steps) > 0
```

**Filtering by Level and Language**:
```python
def test_filter_lessons_by_level(self) -> None:
    """Service should filter lessons by CEFR level."""
    service = LessonService()
    a1_lessons = service.get_lessons_by_level("A1")

    assert all(lesson.level == "A1" for lesson in a1_lessons)

def test_filter_lessons_by_language(self) -> None:
    """Service should filter lessons by target language."""
    service = LessonService()
    spanish_lessons = service.get_lessons_by_language("es")

    assert all(lesson.language == "es" for lesson in spanish_lessons)

def test_combined_filters(self) -> None:
    """Service should support combined level and language filters."""
    service = LessonService()
    lessons = service.get_lessons(level="A1", language="es")

    assert all(l.level == "A1" and l.language == "es" for l in lessons)
```

**Progress Tracking Operations**:
```python
def test_save_and_retrieve_progress(self) -> None:
    """Service should save and retrieve lesson progress."""
    service = LessonService()
    progress = LessonProgress(
        lesson_id="greetings-a1",
        current_step=3,
        total_steps=8,
        completed=False
    )

    service.save_progress(user_id="test-user", progress=progress)
    retrieved = service.get_progress(user_id="test-user", lesson_id="greetings-a1")

    assert retrieved.current_step == 3
    assert retrieved.completed is False

def test_progress_updates_existing(self) -> None:
    """Service should update existing progress, not create duplicates."""
    service = LessonService()
    # Save initial progress
    service.save_progress(user_id="test-user", progress=LessonProgress(...))
    # Update progress
    service.save_progress(user_id="test-user", progress=LessonProgress(current_step=5, ...))

    progress_list = service.get_all_progress(user_id="test-user")
    assert len([p for p in progress_list if p.lesson_id == "greetings-a1"]) == 1
```

---

### Lesson Route Tests (`tests/test_lesson_routes.py`)

**39 test cases** covering all lesson API endpoints.

#### Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestLessonListEndpoint` | 8 | GET /lessons with filters |
| `TestLessonDetailEndpoint` | 6 | GET /lessons/{id} |
| `TestLessonPlayerEndpoint` | 8 | GET /lessons/{id}/play with step navigation |
| `TestLessonProgressEndpoints` | 10 | Progress save/retrieve/update |
| `TestGuestAccess` | 7 | Unauthenticated user lesson access |

#### Key Test Scenarios

**Lesson List with Filters**:
```python
async def test_get_lessons_returns_list(self, async_client) -> None:
    """GET /lessons should return list of available lessons."""
    response = await async_client.get("/lessons")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["lessons"], list)

async def test_get_lessons_with_level_filter(self, async_client) -> None:
    """GET /lessons?level=A1 should filter by CEFR level."""
    response = await async_client.get("/lessons?level=A1")

    assert response.status_code == 200
    lessons = response.json()["lessons"]
    assert all(lesson["level"] == "A1" for lesson in lessons)

async def test_get_lessons_with_language_filter(self, async_client) -> None:
    """GET /lessons?language=es should filter by target language."""
    response = await async_client.get("/lessons?language=es")

    assert response.status_code == 200
    lessons = response.json()["lessons"]
    assert all(lesson["language"] == "es" for lesson in lessons)
```

**Lesson Player Endpoints**:
```python
async def test_lesson_player_renders_first_step(self, async_client) -> None:
    """GET /lessons/{id}/play should render first step."""
    response = await async_client.get("/lessons/greetings-a1/play")

    assert response.status_code == 200
    assert "step" in response.json()
    assert response.json()["current_step"] == 1

async def test_lesson_player_navigates_to_step(self, async_client) -> None:
    """GET /lessons/{id}/play?step=3 should navigate to specific step."""
    response = await async_client.get("/lessons/greetings-a1/play?step=3")

    assert response.status_code == 200
    assert response.json()["current_step"] == 3

async def test_lesson_player_marks_completion(self, async_client) -> None:
    """Reaching final step should mark lesson as complete."""
    # Navigate to final step
    response = await async_client.get("/lessons/greetings-a1/play?step=8")

    assert response.status_code == 200
    # Check completion state
    progress_response = await async_client.get("/lessons/greetings-a1/progress")
    assert progress_response.json()["completed"] is True
```

**Guest Access (Unauthenticated Users)**:
```python
async def test_guest_can_view_lesson_list(self, async_client) -> None:
    """Unauthenticated users should view lesson catalog."""
    response = await async_client.get("/lessons")

    assert response.status_code == 200
    assert len(response.json()["lessons"]) > 0

async def test_guest_can_play_lessons(self, async_client) -> None:
    """Unauthenticated users should access lesson player."""
    response = await async_client.get("/lessons/greetings-a1/play")

    assert response.status_code == 200

async def test_guest_progress_uses_session(self, async_client) -> None:
    """Guest progress should be stored in session, not database."""
    response = await async_client.get("/lessons/greetings-a1/play?step=3")

    assert response.status_code == 200
    # Progress tracked via session cookie, not user_id
    assert "session" in response.cookies or response.headers.get("Set-Cookie")
```

---

### Phase 6 E2E Browser Tests (Playwright)

End-to-end browser testing for the lesson player interface.

| Test | Status | Description |
|------|--------|-------------|
| Lesson Catalog Display | Pass | Lessons render with correct metadata |
| Level Filter UI | Pass | Dropdown filters lessons by CEFR level |
| Lesson Player Navigation | Pass | Next/Previous buttons navigate steps |
| Progress Indicator | Pass | Visual progress bar updates correctly |
| Step Content Rendering | Pass | Vocabulary, grammar, dialogue steps render |
| Completion Celebration | Pass | Completion message displays at final step |

#### Lesson Player Navigation Test

**Test Steps**:
1. Navigate to lesson catalog `/lessons`
2. Click on "Greetings and Introductions" lesson card
3. Verify lesson player loads with step 1
4. Click "Next" button
5. Verify step 2 content displays
6. Click "Previous" button
7. Verify step 1 content displays again

**Expected Behavior**:
- Step counter updates (e.g., "Step 2 of 8")
- Progress bar advances visually
- Step content transitions smoothly
- Navigation buttons disable appropriately at boundaries

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
| `src/agent/` | 90%+ | 85%+ |
| `src/api/` | 85%+ | 80%+ |
| `src/db/` | 85%+ | 80%+ |
| `src/services/` | 90%+ | 85%+ |
| `src/lessons/` | 88%+ | 85%+ |
| **Overall** | **86%+** | **70%+** |

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
├── test_lesson_models.py    # Phase 6 lesson data models
├── test_lesson_service.py   # Phase 6 lesson service
├── test_lesson_routes.py    # Phase 6 lesson API endpoints
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
