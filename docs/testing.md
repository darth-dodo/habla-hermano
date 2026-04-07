# Habla Hermano Test Documentation

> Comprehensive test coverage documentation for the Habla Hermano language tutor application.

---

## Table of Contents

- [Test Summary](#test-summary)
- [Running Tests](#running-tests)
- [Phase 3 Test Coverage](#phase-3-test-coverage)
- [Phase 6 Test Coverage](#phase-6-test-coverage)
- [Phase 7 Test Coverage](#phase-7-test-coverage)
- [Phase 12 Test Coverage](#phase-12-test-coverage)
- [Phase 13 Test Coverage](#phase-13-test-coverage)
- [Phase 14 Test Coverage](#phase-14-test-coverage)
- [Phase 19/23 Test Coverage](#phase-1923-test-coverage)
- [Phase 26 Test Coverage](#phase-26-test-coverage)
- [JavaScript Test Suite](#javascript-test-suite)
- [E2E Tests (Playwright)](#e2e-tests-playwright)
- [Test Fixtures](#test-fixtures)
- [Test Coverage Goals](#test-coverage-goals)
- [Test Architecture](#test-architecture)
- [Continuous Integration](#continuous-integration)
- [Related Documentation](#related-documentation)

---

## Test Summary

| Category | Test File | Test Cases | Coverage Focus |
|----------|-----------|------------|----------------|
| Agent Graph | `agent/test_graph.py` | 35 | Graph structure, node routing, Phase 3 conditional edges |
| Agent State | `agent/test_state.py` | 40+ | TypedDict state, Pydantic models, reducers |
| Agent Nodes | `agent/nodes/test_nodes.py` | 50+ | respond_node, analyze_node integration |
| Agent Prompts | `agent/test_prompts.py` | 25+ | Level-specific prompts, language support |
| Scaffold Node | `agent/nodes/test_scaffold.py` | 60+ | Phase 3 scaffolding, word banks, auto_expand |
| Routing | `agent/test_routing.py` | 35+ | Phase 3 conditional routing, needs_scaffolding |
| Analyze Node | `agent/nodes/test_analyze.py` | 70+ | Phase 2 grammar feedback, vocabulary extraction |
| Review Graph | `agent/test_review_graph.py` | 30+ | Review graph structure and execution |
| Agent Coverage | `agent/test_coverage.py` | 20+ | Agent module test coverage validation |
| Review Nodes | `agent/nodes/test_review.py` | 25+ | Review node implementations |
| API Config | `api/test_config.py` | 30+ | Settings, environment, Pydantic config |
| Chat Routes | `api/routes/test_chat.py` | 45+ | Endpoints, HTMX responses, form handling |
| Auth | `api/test_auth.py` | 50+ | JWT validation, signup/login flows, token expiration |
| Auth Routes | `api/routes/test_auth.py` | 30+ | Auth API endpoint tests |
| Checkpointer | `agent/test_checkpointer.py` | 30+ | PostgresSaver/MemorySaver fallback, thread IDs |
| Session | `api/test_session.py` | 20+ | Thread ID management, cookie lifecycle |
| Persistence | `api/test_persistence.py` | 25+ | End-to-end auth + persistence workflows |
| DB Models | `db/test_models.py` | 25+ | Pydantic models for Supabase |
| DB Encryption | `db/test_encryption.py` | 10 | FernetCipher, EncryptedSerializer, round-trip, backward compat |
| DB Repository | `db/test_repository.py` | 49+ | Data access layer with mocked client, encrypt-on-write, decrypt-on-read |
| Supabase Client | `api/test_supabase_client.py` | 15+ | Client singleton, cache management |
| CSRF Middleware | `api/test_csrf.py` | 15 | CSRF token validation, safe/unsafe methods, exempt paths |
| Services Levels | `services/test_levels.py` | 20+ | CEFR level detection |
| Services Vocab | `services/test_vocabulary.py` | 20+ | Vocabulary tracking |
| Lessons/Progress | `api/routes/test_progress.py` | 50+ | Lesson endpoints, progress tracking |
| Lesson Models | `lessons/test_models.py` | 36 | Phase 6 lesson data model validation |
| Lesson Service | `lessons/test_service.py` | 20 | Phase 6 lesson service functionality |
| Lesson Routes | `api/routes/test_lessons.py` | 30 | Phase 6 lesson API endpoints (list, detail, progress) |
| Progress Service | `services/test_progress.py` | 25+ | Phase 7 dashboard stats, chart data |
| Data Capture | `api/test_data_capture.py` | 20+ | Phase 7 vocabulary/session capture integration |
| Review Service | `services/test_review.py` | 30+ | Phase 12 spaced repetition review scheduling |
| Input Validation | `api/routes/test_validation.py` | 25+ | Input validation and sanitization |
| Review Routes | `api/routes/test_review.py` | 20+ | Review API endpoints |
| Learn Routes | `api/routes/test_learn.py` | 23 | Phase 14 learn page rendering, HTMX partials, guest vs auth users |
| E2E Routes | `api/routes/test_e2e.py` | 30+ | End-to-end route integration tests |
| Path Service | `services/test_paths.py` | 27 | Phase 14 path building, progress tracking, next lesson detection |
| Adaptive Service | `services/test_adaptive.py` | 49 | Phase 14 daily recommendations, category strengths, level readiness |
| Coverage Services | `services/test_coverage.py` | 20+ | Service module coverage validation |
| JS DOM | `tests/js/dom.test.js` | 37 | DOM utilities, scroll behavior, focus management, escapeHtml |
| JS Stream | `tests/js/stream.test.js` | 29 | SSE parsing, streaming bubble, token append, TTS speaker buttons |
| JS Voice | `tests/js/voice.test.js` | 112 | VoiceManager lifecycle, STT recording, TTS playback, error handling, voice sub-modules |
| JS Scaffold | `tests/js/scaffold.test.js` | 15 | Click-to-insert word bank functionality |
| JS Shortcuts | `tests/js/shortcuts.test.js` | 12 | Keyboard shortcuts (/, Shift+Enter, Escape, Cmd+Shift+N) |
| JS HTMX | `tests/js/htmx-handlers.test.js` | 11 | HTMX event handlers (afterSwap, scroll, errors) |
| Lesson Chat Node | `agent/nodes/test_lesson_chat.py` | 45 | Phase 19/23 lesson respond node, phase machine, exercise evaluation |
| Chat Routes (Lesson) | `api/routes/test_chat.py` | 16 | Phase 23 unified chat routes: lesson mode, thread ID, streaming, resume |
| Answer Normalization | `agent/nodes/test_lesson_chat.py` | 15 | Phase 23 normalize_answer, fill-blank, translate normalization |
| LLM Translation Eval | `agent/nodes/test_lesson_chat.py` | 8 | Phase 23 LLM-based translation evaluation |
| Thread API | `api/test_threads.py` | 9 | Phase 26 thread CRUD endpoints, auth enforcement, RLS boundary |
| Thread Service | `services/test_threads.py` | 11 | Phase 26 ThreadService CRUD, thread ID format, `touch()` timestamp |
| Thread Titling | `services/test_thread_titling.py` | 5 | Phase 26 auto-title via Claude Haiku, fallback, truncation, quote stripping |
| Thread Messages | `services/test_thread_messages.py` | 5 | Phase 26 LangGraph checkpoint extraction, role mapping, empty/error handling |
| Checkpoint Purge | `agent/test_checkpoint_purge.py` | 13 | Checkpoint cleanup and purge logic |
| LLM Zero Retention | `agent/test_llm_zero_retention.py` | 4 | Anthropic zero-retention header enforcement |
| Auth Cache | `api/routes/test_auth_cache.py` | 7 | Auth page Cache-Control headers |
| Password Reset | `api/routes/test_auth_password_reset.py` | 13 | Forgot password, reset password flows via Supabase Auth |
| Voice Routes | `api/routes/test_voice.py` | 55 | STT/TTS endpoint validation, auth, rate limiting |
| Voice Integration | `api/routes/test_voice_integration.py` | 60 | WebSocket STT/TTS proxy integration tests |
| Chat Security | `api/test_chat_security.py` | 3 | Chat route security hardening |
| Privacy Routes | `api/test_privacy.py` | 16 | Privacy page, delete history, delete account |
| Sanitization | `api/test_sanitize.py` | 43 | Input sanitization with nh3 and markupsafe |
| Security Headers | `api/test_security_headers.py` | 17 | CSP, HSTS, X-Frame-Options, Cache-Control |
| SSE Streaming | `api/test_streaming.py` | 34 | Server-Sent Events streaming logic |
| Fernet Cipher | `db/test_fernet_cipher.py` | 10 | FernetCipher encrypt/decrypt, key derivation |
| Repository Encryption | `db/test_repository_encryption.py` | 19 | Encrypt-on-write, decrypt-on-read boundary |
| Data Retention | `services/test_data_retention.py` | 6 | Data retention and cleanup policies |
| Rate Limiting | `test_rate_limiting.py` | 13 | REST and WebSocket rate limit enforcement |
| JS FSM | `tests/js/fsm.test.js` | 21 | Finite state machine: createMachine, interpret, transitions |

**Total**: ~2,529 tests (2,291 Python + 238 JavaScript) with 97% code coverage

---

## Running Tests

### Parallel Execution with pytest-xdist

Tests run in parallel using `pytest-xdist` with `-n auto`, which auto-detects the number of CPU cores and distributes tests across worker processes. This significantly reduces the total test run time for the 2,291 Python test suite.

```bash
# Default: parallel execution (auto-detect cores)
make test
# or directly:
pytest -n auto

# Serial execution (useful for debugging or inspecting output):
pytest -n0
# or disable the plugin entirely:
pytest -p no:xdist
```

All tests are isolated and safe for parallel execution — there is no shared state between tests. Database calls are mocked via Supabase client fixtures, and LLM calls are mocked via `get_llm` patches, so no real external services are contacted during the test run.

### LLM Mocking Strategy

Tests that exercise agent nodes (e.g. `respond_node`, `scaffold_node`, `lesson_respond_node`) mock `get_llm` from `src.agent.llm` to return a fake `ChatAnthropic` instance. This prevents real API calls to Anthropic, ensures deterministic outputs, and keeps the test suite fast. The typical pattern:

```python
@patch("src.agent.llm.get_llm")
async def test_node_behavior(self, mock_get_llm):
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(content="mocked response")
    mock_get_llm.return_value = mock_llm

    result = await some_node(state)
    # assertions on result ...
```

This approach applies to all LangGraph node tests, including the lesson chat phase machine and LLM-based translation evaluation.

---

## Phase 3 Test Coverage

Phase 3 introduced conditional routing and scaffolding for A0-A1 learners. The following sections document the new test coverage.

### Scaffold Node Tests (`tests/agent/nodes/test_scaffold.py`)

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

### Routing Tests (`tests/agent/test_routing.py`)

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

### Agent Graph Tests (`tests/agent/test_graph.py`)

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

### Lesson Model Tests (`tests/lessons/test_models.py`)

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

### Lesson Service Tests (`tests/lessons/test_service.py`)

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

### Lesson Route Tests (`tests/api/routes/test_lessons.py`)

**30 test cases** covering lesson list, detail, and progress API endpoints. (Phase 23 removed the step-based `/lessons/{id}/play` player endpoint; lessons are now delivered conversationally through the unified chat route.)

#### Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestLessonListEndpoint` | 8 | GET /lessons with filters |
| `TestLessonDetailEndpoint` | 6 | GET /lessons/{id} |
| `TestLessonProgressEndpoints` | 10 | Progress save/retrieve/update |
| `TestGuestAccess` | 6 | Unauthenticated user lesson access |

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

**Guest Access (Unauthenticated Users)**:
```python
async def test_guest_can_view_lesson_list(self, async_client) -> None:
    """Unauthenticated users should view lesson catalog."""
    response = await async_client.get("/lessons")

    assert response.status_code == 200
    assert len(response.json()["lessons"]) > 0

async def test_guest_can_start_lesson(self, async_client) -> None:
    """Unauthenticated users should start lesson via chat."""
    response = await async_client.get("/?lesson=greetings-a1")

    assert response.status_code == 200

async def test_guest_progress_uses_session(self, async_client) -> None:
    """Guest progress should be stored in session, not database."""
    response = await async_client.get("/?lesson=greetings-a1")

    assert response.status_code == 200
    # Progress tracked via session cookie, not user_id
    assert "session" in response.cookies or response.headers.get("Set-Cookie")
```

---

### Phase 6/23 E2E Browser Tests (Playwright)

End-to-end browser testing for lesson discovery and conversational lesson delivery.

| Test | Status | Description |
|------|--------|-------------|
| Lesson Catalog Display | Pass | Lessons render with correct metadata |
| Level Filter UI | Pass | Dropdown filters lessons by CEFR level |
| Lesson Chat Flow | Pass | Conversational lesson delivery through unified chat |
| Progress Indicator | Pass | Visual progress bar updates during lesson phases |
| Completion Overlay | Pass | Completion overlay with score displays at end |

> **Note**: Phase 23 replaced the step-based lesson player with conversational delivery through the main chat route (`GET /?lesson={id}`). The old `/lessons/{id}/play` navigation tests are no longer applicable.

---

## Phase 7 Test Coverage

Phase 7 introduced the progress dashboard with learning statistics, vocabulary tracking visualization, and session history. Tests validate the ProgressService and data capture integration.

### Progress Service Tests (`tests/services/test_progress.py`)

**25+ test cases** covering the ProgressService for dashboard data aggregation.

#### Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestProgressServiceDashboardStats` | 8 | Dashboard statistics aggregation |
| `TestProgressServiceChartData` | 7 | Time-series data for charts |
| `TestProgressServiceRecordActivity` | 6 | Chat activity recording |
| `TestProgressServiceEdgeCases` | 4 | Empty data, missing user, error handling |

#### Key Test Scenarios

**Dashboard Statistics Aggregation**:
```python
async def test_get_dashboard_stats_returns_complete_data(self) -> None:
    """Dashboard stats should include all required metrics."""
    service = ProgressService()
    stats = await service.get_dashboard_stats(user_id="test-user")

    assert "total_vocabulary" in stats
    assert "total_sessions" in stats
    assert "total_lessons_completed" in stats
    assert "current_streak" in stats
    assert "level_progress" in stats

async def test_dashboard_stats_calculates_streak_correctly(self) -> None:
    """Streak calculation should count consecutive activity days."""
    service = ProgressService()
    # Setup user with 5 consecutive days of activity
    stats = await service.get_dashboard_stats(user_id="active-user")

    assert stats["current_streak"] == 5
```

**Chart Data Generation**:
```python
async def test_get_vocabulary_chart_data(self) -> None:
    """Chart data should return time-series vocabulary counts."""
    service = ProgressService()
    chart_data = await service.get_vocabulary_chart_data(
        user_id="test-user",
        days=7
    )

    assert len(chart_data) == 7
    assert all("date" in point and "count" in point for point in chart_data)

async def test_get_session_chart_data(self) -> None:
    """Chart data should return time-series session counts."""
    service = ProgressService()
    chart_data = await service.get_session_chart_data(
        user_id="test-user",
        days=30
    )

    assert len(chart_data) == 30
    assert all("date" in point and "duration" in point for point in chart_data)
```

**Record Chat Activity**:
```python
async def test_record_chat_activity_creates_session(self) -> None:
    """Recording activity should create or update session record."""
    service = ProgressService()
    await service.record_chat_activity(
        user_id="test-user",
        message_count=5,
        vocabulary_learned=["hola", "adios"]
    )

    stats = await service.get_dashboard_stats(user_id="test-user")
    assert stats["total_sessions"] >= 1

async def test_record_chat_activity_increments_vocabulary(self) -> None:
    """Recording activity should add new vocabulary to user total."""
    service = ProgressService()
    initial_stats = await service.get_dashboard_stats(user_id="test-user")
    initial_vocab = initial_stats["total_vocabulary"]

    await service.record_chat_activity(
        user_id="test-user",
        message_count=3,
        vocabulary_learned=["gracias", "por favor"]
    )

    updated_stats = await service.get_dashboard_stats(user_id="test-user")
    assert updated_stats["total_vocabulary"] == initial_vocab + 2
```

---

### Data Capture Integration Tests (`tests/api/test_data_capture.py`)

**20+ test cases** covering vocabulary and session capture in chat and lesson routes.

#### Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestChatVocabularyCapture` | 8 | Vocabulary extraction during chat |
| `TestLessonSessionCapture` | 7 | Session tracking during lesson play |
| `TestCaptureIntegration` | 5 | End-to-end capture verification |

#### Key Test Scenarios

**Chat Vocabulary Capture**:
```python
async def test_chat_captures_vocabulary_from_response(self, async_client) -> None:
    """Chat endpoint should capture vocabulary from AI response analysis."""
    response = await async_client.post(
        "/chat",
        data={"message": "Hola, como estas?"},
        cookies={"session_id": "test-session"}
    )

    assert response.status_code == 200
    # Verify vocabulary was captured
    vocab_response = await async_client.get("/progress/vocabulary")
    assert len(vocab_response.json()["vocabulary"]) > 0

async def test_chat_captures_vocabulary_with_auth_user(self, async_client) -> None:
    """Authenticated user vocabulary should be stored in database."""
    response = await async_client.post(
        "/chat",
        data={"message": "Me llamo Carlos"},
        headers={"Authorization": "Bearer valid-token"}
    )

    assert response.status_code == 200
    # Vocabulary persisted to user account
```

**Lesson Session Capture**:
```python
async def test_lesson_chat_creates_session_record(self, async_client) -> None:
    """Starting a lesson via chat should create a session record."""
    response = await async_client.get("/?lesson=greetings-a1")

    assert response.status_code == 200
    # Session record created
    sessions = await async_client.get("/progress/sessions")
    assert any(s["lesson_id"] == "greetings-a1" for s in sessions.json()["sessions"])

async def test_lesson_completion_records_vocabulary(self, async_client) -> None:
    """Completing a lesson should record vocabulary from lesson content."""
    # Lesson completion handled through conversational chat flow
    # Vocabulary captured via lesson respond node's complete phase
    vocab_response = await async_client.get("/progress/vocabulary")
    vocab_words = [v["word"] for v in vocab_response.json()["vocabulary"]]
    assert "hola" in vocab_words or "buenos dias" in vocab_words
```

---

## Phase 12 Test Coverage

Phase 12 introduced spaced repetition for vocabulary review. Tests validate the review scheduling service.

### Review Service Tests (`tests/services/test_review.py`)

**30+ test cases** covering the ReviewService for spaced repetition scheduling.

#### Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestReviewScheduling` | 10+ | Review interval scheduling and due date calculation |
| `TestReviewQualityProcessing` | 10+ | Quality response processing and repetition updates |
| `TestReviewServiceEdgeCases` | 10+ | Edge cases, empty queues, new vs existing items |

---

## Phase 13 Test Coverage

Phase 13 focused on mobile responsive design improvements (CSS/template changes). No dedicated test files were added as changes were primarily visual/layout adjustments validated through manual and E2E browser testing.

---

## Phase 14 Test Coverage

Phase 14 introduced learning paths and adaptive recommendations. 99 new tests were added covering the PathService, AdaptiveService, and learn routes.

### Path Service Tests (`tests/services/test_paths.py`)

**27 test cases** covering the PathService for structured learning path management.

#### Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestPathBuilding` | 8+ | Learning path construction from lesson catalog |
| `TestPathProgress` | 8+ | Progress tracking across path milestones |
| `TestNextLessonDetection` | 6+ | Next recommended lesson identification |
| `TestPathEdgeCases` | 5+ | Empty paths, missing lessons, boundary conditions |

### Adaptive Service Tests (`tests/services/test_adaptive.py`)

**49 test cases** covering the AdaptiveService for personalized learning recommendations.

#### Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestDailyRecommendations` | 12+ | Daily recommendation generation and prioritization |
| `TestCategoryStrengths` | 10+ | Category strength scoring and analysis |
| `TestLevelReadiness` | 8+ | CEFR level readiness assessment |
| `TestSuggestionTextBuilding` | 10+ | Human-readable suggestion text generation |
| `TestWeakCategoryDetection` | 9+ | Weak category identification and targeting |

### Learn Route Tests (`tests/api/routes/test_learn.py`)

**23 test cases** covering the learn page endpoints and HTMX partial rendering.

#### Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestLearnPageRendering` | 8+ | GET /learn/ full page rendering |
| `TestRecommendationPartial` | 6+ | GET /learn/recommendation HTMX partial |
| `TestGuestVsAuthUsers` | 5+ | Guest and authenticated user behavior differences |
| `TestLearnRouteErrors` | 4+ | Error handling and language parameter validation |

---

## Phase 19/23 Test Coverage

Phase 19 introduced conversational lesson delivery through the chat UI. Phase 23 unified lessons into the main chat route (`GET /` with `?lesson=` param and `POST /chat/stream` with `lesson_id`), removing the separate `/chat/lesson/` routes. Tests cover the lesson respond node phase machine, unified routing, answer normalization, and LLM-based evaluation.

### Lesson Chat Node Tests (`tests/agent/nodes/test_lesson_chat.py`)

**45+ test cases** covering the lesson respond node and answer normalization.

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestParseMcAnswer` | 9 | Multiple-choice answer parsing (letter, digit, text match, ambiguous) |
| `TestHelpers` | 5 | Ordered steps, exercises, language name, lesson UI builder |
| `TestHandleIntro` | 3 | Intro phase: LLM call, phase transition, lesson UI |
| `TestHandleTeaching` | 6 | Teaching phase: step batching, practice skip, phase transitions |
| `TestHandleExerciseAsk` | 3 | Exercise ask: presentation, overflow to complete, UI events |
| `TestHandleExerciseEval` | 10 | Exercise eval: MC/fill-blank/translate, correctness, result recording |
| `TestHandleComplete` | 4 | Completion: score calculation, vocabulary count, UI events |
| `TestLessonRespondNode` | 5 | Main dispatch: phase routing, unknown phase fallback |
| `TestNormalizeAnswer` | 6 | Phase 23 answer normalization: accents, punctuation, casing, whitespace |
| `TestFillBlankNormalization` | 6 | Phase 23 fill-blank exercise normalization: articles, extra words, partial |
| `TestTranslateNormalization` | 3 | Phase 23 translation exercise normalization: equivalences, synonyms |
| `TestTranslateExerciseLLMEval` | 8 | Phase 23 LLM-based translation evaluation: correct/incorrect/partial, fallback |

### Unified Chat Route Tests — Lesson Mode (`tests/api/routes/test_chat.py`)

Phase 23 merged lesson routes into the main chat endpoints. **16 test cases** cover lesson-specific behavior within the unified routes.

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestChatPageLessonMode` | 4 | GET / with `?lesson=` param: 200, lesson context, 404 unknown, session cookie |
| `TestResolveLessonThreadId` | 3 | Thread ID generation: `lesson-{id}-{user}` format, guest fallback, deterministic |
| `TestStreamMessageLessonMode` | 5 | POST /chat/stream with `lesson_id`: graph invocation, SSE events, validation |
| `TestLessonResume` | 4 | Checkpoint-based resume: existing checkpoint loads state, new lesson initializes |

---

## Phase 26 Test Coverage

Phase 26 introduced conversation threads, allowing authenticated users to maintain multiple independent chat histories. Thirty new tests cover the thread API routes, the ThreadService data layer, auto-title generation, and message history extraction from LangGraph checkpoints.

### Thread API Tests (`tests/api/test_threads.py`)

**9 test cases** covering the CRUD endpoints at `/threads/`.

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestThreadAuth` | 1 | Unauthenticated `GET /threads/` returns 401 |
| `TestListThreads` | 2 | Empty list and populated list serialisation |
| `TestCreateThread` | 2 | Default language/level, explicit params, 201 response |
| `TestRenameThread` | 2 | Successful rename returns updated title; 404 when thread not found |
| `TestDeleteThread` | 2 | 204 with empty body; idempotent delete of nonexistent thread |

All tests use `CSRF_HEADERS` from `tests/conftest.py` and patch `_get_thread_service` to inject a pre-configured `MagicMock`, keeping tests free of database connections. Auth is overridden via FastAPI's dependency injection (`get_current_user`).

### Thread Service Tests (`tests/services/test_threads.py`)

**11 test cases** covering `ThreadService` CRUD with a mocked Supabase client.

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestCreateThread` | 3 | Returns `ConversationThread`, generates `user:{uid}:{uuid4}` thread ID, defaults language/level |
| `TestListThreads` | 2 | Empty result; ordered list mapped to `ConversationThread` objects |
| `TestGetThread` | 2 | Returns model when found; returns `None` when row absent |
| `TestUpdateTitle` | 1 | Calls `update` with correct title and `updated_at` |
| `TestTouch` | 1 | Updates `updated_at` only, no `title` key |
| `TestDeleteThread` | 2 | Calls `delete` chain with `user_id` and `thread_id` eq filters |

### Thread Titling Tests (`tests/services/test_thread_titling.py`)

**5 test cases** covering `generate_thread_title`, an async function that calls Claude Haiku to produce a short conversation title.

| Test | Purpose |
|------|---------|
| `test_generate_title_returns_string` | LLM response content becomes the title |
| `test_generate_title_truncates_long_input` | Input messages are capped at 200 chars before the prompt is sent |
| `test_generate_title_handles_error` | LLM exception falls back to `"New conversation"` |
| `test_generate_title_strips_quotes` | Leading/trailing quotes are removed from the LLM output |
| `test_generate_title_returns_default_on_empty` | Whitespace-only LLM response returns `"New conversation"` |

All tests patch `src.services.thread_titling.ChatAnthropic` with an `AsyncMock` so no real API calls are made.

### Thread Messages Tests (`tests/services/test_thread_messages.py`)

**5 test cases** covering `get_thread_messages`, which reads the LangGraph checkpoint state for a given `thread_id` and returns a flat list of `{"role": ..., "content": ...}` dicts.

| Test | Purpose |
|------|---------|
| `test_get_messages_empty_thread` | State with no `messages` key returns `[]` |
| `test_get_messages_no_state` | `aget_state` returning `None` returns `[]` |
| `test_get_messages_with_history` | Four-message conversation mapped to correct roles in order |
| `test_get_messages_filters_system_messages` | `SystemMessage` objects are excluded; only `HumanMessage`/`AIMessage` pass through |
| `test_get_messages_handles_error` | Checkpointer context manager exception returns `[]` without raising |

Tests patch both `get_checkpointer` (as an async context manager) and `build_graph` to isolate the extraction logic from LangGraph internals.

---

## JavaScript Test Suite

**Framework**: Vitest 3.x + jsdom environment
**Location**: `tests/js/`
**Total**: 238 tests across 8 test files
**Coverage**: ~90% on tested modules (dom, stream, voice, scaffold, lesson, theme)

### Running JavaScript Tests

```bash
# Run all JS tests
npx vitest run

# Run with coverage
npx vitest run --coverage

# Run in watch mode
npx vitest
```

### Test Architecture

The JavaScript test suite uses jsdom to simulate a browser DOM environment. Key patterns:

- **DOM mocking**: Tests create minimal HTML structures matching the chat page layout
- **WebSocket mocking**: Custom WebSocket mock class for STT/TTS WebSocket testing
- **AudioContext mocking**: Stubs for AudioContext, MediaRecorder, getUserMedia
- **Module isolation**: Each test file imports only the module under test

### Notable Shortcut Test Change (Phase 26)

The `Cmd/Ctrl + Shift + N` test in `shortcuts.test.js` was updated in Phase 26. The shortcut now navigates to a new conversation by setting `window.location.href = '/'` instead of the previous approach of triggering an HTMX action on the new-chat button. Because jsdom prevents direct assignment to `window.location`, the test uses a `delete window.location` workaround before replacing it with a plain object:

```javascript
beforeEach(() => {
    // jsdom prevents location.assign spy; replace with a plain mock instead
    delete window.location;
    window.location = { href: '' };
    initKeyboardShortcuts();
});

it('navigates to / to start a new conversation', () => {
    pressKey('N', { metaKey: true, shiftKey: true });
    expect(window.location.href).toBe('/');
});
```

This replaces the former pattern that relied on `htmx.trigger()` dispatching a click on `#new-chat-btn`.

### CI Integration

JavaScript tests run in a parallel CI job (`test-js`) alongside Python tests:
- Node.js 22
- `npm ci` for reproducible installs
- `npx vitest run` for test execution

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
pytest tests/agent/nodes/test_scaffold.py -v

# Run specific test class
pytest tests/agent/test_routing.py::TestNeedsScaffoldingBasicRouting -v

# Run specific test method
pytest tests/agent/nodes/test_scaffold.py::TestScaffoldNodeLevelBehavior::test_a0_level_gets_scaffolding_response -v
```

### Run Tests by Category

```bash
# Agent tests only
pytest tests/agent/ -v

# API tests only
pytest tests/api/ -v

# Service tests only
pytest tests/services/ -v

# DB tests only
pytest tests/db/ -v

# Lesson tests only
pytest tests/lessons/ -v

# Route tests only
pytest tests/api/routes/ -v

# Phase 3 specific tests
pytest tests/agent/nodes/test_scaffold.py tests/agent/test_routing.py -v
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
# CSRF_HEADERS constant — used by all test clients to satisfy CSRF middleware
CSRF_HEADERS = {"x-csrf-token": "test-csrf-token"}

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

### Supabase Chain Mock (Thread Service Tests)

The thread service tests (`tests/services/test_threads.py`) use a helper that builds a `MagicMock` for the Supabase PostgREST client. Every chained method (`select`, `insert`, `update`, `delete`, `eq`, `order`) returns the same `mock_table` object, so assertions can inspect any step in the chain. The `not_` property requires `PropertyMock` because Supabase exposes it as a property, not a method:

```python
def _make_mock_client(data=None):
    mock_client = MagicMock()
    mock_table = MagicMock()

    for method in ("select", "insert", "update", "delete", "eq", "order"):
        setattr(mock_table, method, MagicMock(return_value=mock_table))

    mock_table.execute = MagicMock(return_value=MagicMock(data=data or []))
    type(mock_table).not_ = PropertyMock(return_value=mock_table)
    mock_client.table = MagicMock(return_value=mock_table)

    return mock_client, mock_table
```

This mirrors the pattern established in the DB repository tests and is the standard approach for any service that calls `.table().select().eq().order().execute()`.

---

## Test Coverage Goals

| Module | Current | Target |
|--------|---------|--------|
| `src/agent/` | 97%+ | 90%+ |
| `src/api/` | 96%+ | 90%+ |
| `src/db/` | 97%+ | 90%+ |
| `src/services/` | 97%+ | 90%+ |
| `src/lessons/` | 97%+ | 90%+ |
| `src/static/js/` | ~90% | 80%+ |
| **Overall** | **97% (Python), ~90% (JS)** | **90%+** |

### Coverage Commands

```bash
# Generate coverage report
pytest tests/ --cov=src --cov-report=html

# View coverage in terminal
pytest tests/ --cov=src --cov-report=term-missing

# Check coverage threshold
pytest tests/ --cov=src --cov-fail-under=97
```

---

## Test Architecture

### Test Organization

```
tests/
├── conftest.py                    # Shared fixtures
├── __init__.py
├── agent/                         # Agent module tests (mirrors src/agent/)
│   ├── __init__.py
│   ├── test_graph.py              # Graph structure tests
│   ├── test_state.py              # State definition tests
│   ├── test_prompts.py            # Prompt template tests
│   ├── test_routing.py            # Phase 3 routing logic
│   ├── test_checkpointer.py       # Checkpointer fallback tests
│   ├── test_review_graph.py       # Review graph tests
│   ├── test_coverage.py           # Agent coverage validation
│   └── nodes/                     # Agent node tests (mirrors src/agent/nodes/)
│       ├── __init__.py
│       ├── test_nodes.py          # Node function tests
│       ├── test_analyze.py        # Phase 2 analyze node
│       ├── test_scaffold.py       # Phase 3 scaffold node
│       ├── test_review.py         # Review node tests
│       └── test_lesson_chat.py    # Phase 19/23 lesson chat node + answer normalization
├── api/                           # API module tests (mirrors src/api/)
│   ├── __init__.py
│   ├── test_auth.py               # JWT validation, signup/login flows
│   ├── test_config.py             # Configuration tests
│   ├── test_csrf.py               # CSRF middleware tests (15 tests)
│   ├── test_session.py            # Thread ID management, cookies
│   ├── test_supabase_client.py    # Client singleton tests
│   ├── test_data_capture.py       # Vocabulary/session capture
│   ├── test_persistence.py        # Auth + persistence integration
│   ├── test_threads.py            # Phase 26 thread CRUD endpoints, auth, RLS boundary
│   └── routes/                    # Route tests (mirrors src/api/routes/)
│       ├── __init__.py
│       ├── test_chat.py           # Chat endpoint tests + Phase 23 lesson mode
│       ├── test_auth.py           # Auth route tests
│       ├── test_learn.py          # Learn page routes
│       ├── test_lessons.py        # Lesson API endpoints
│       ├── test_progress.py       # Progress route tests
│       ├── test_review.py         # Review route tests
│       ├── test_validation.py     # Input validation tests
│       └── test_e2e.py            # E2E route integration tests
├── db/                            # Database tests (mirrors src/db/)
│   ├── __init__.py
│   ├── test_models.py             # Pydantic models for Supabase
│   └── test_repository.py         # Data access layer tests
├── lessons/                       # Lesson tests (mirrors src/lessons/)
│   ├── __init__.py
│   ├── test_models.py             # Lesson data model validation
│   └── test_service.py            # Lesson service functionality
├── services/                      # Service tests (mirrors src/services/)
│   ├── __init__.py
│   ├── test_adaptive.py           # Adaptive recommendations
│   ├── test_coverage.py           # Service coverage validation
│   ├── test_progress.py           # Progress dashboard service
│   ├── test_review.py             # Spaced repetition review service
│   ├── test_paths.py              # Learning path service
│   ├── test_levels.py             # CEFR level detection
│   ├── test_vocabulary.py         # Vocabulary tracking
│   ├── test_threads.py            # Phase 26 ThreadService CRUD, touch, thread ID format
│   ├── test_thread_titling.py     # Phase 26 auto-title generation, fallback, truncation
│   └── test_thread_messages.py    # Phase 26 LangGraph checkpoint message extraction
└── js/                            # JavaScript tests (Vitest + jsdom)
    ├── dom.test.js                # DOM utilities, scroll, focus, escapeHtml
    ├── stream.test.js             # SSE parsing, streaming bubble, TTS buttons
    ├── voice.test.js              # VoiceManager lifecycle, STT, TTS playback
    ├── scaffold.test.js           # Click-to-insert word bank
    ├── shortcuts.test.js          # Keyboard shortcuts (/, Shift+Enter, Escape)
    ├── htmx-handlers.test.js      # HTMX event handlers (afterSwap, scroll)
    ├── lesson.test.js             # Lesson mode detection, progress bar, completion overlay
    └── theme.test.js              # Theme picker, localStorage persistence
```

### Test Naming Conventions

**Python**:
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

**JavaScript**:
- Test files: `<module>.test.js`
- Test suites: `describe('<ModuleName>', ...)`
- Test cases: `it('should <behavior_description>', ...)`

Example:
```javascript
describe('VoiceManager', () => {
  it('should initialize with microphone access', () => {
    // ...
  });
});
```

### Test Categories

1. **Unit Tests**: Test individual functions in isolation
2. **Integration Tests**: Test node interactions and graph execution
3. **API Tests**: Test HTTP endpoints with mocked dependencies
4. **JavaScript Tests**: Test client-side DOM, streaming, voice, and UI behavior (Vitest + jsdom)
5. **E2E Tests**: Test full user flows via Playwright MCP

---

## Continuous Integration

Tests run on every push via GitHub Actions. mypy strict checks cover 58 source files.

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
      - run: pytest tests/ --cov=src --cov-fail-under=97

  test-js:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
      - run: npm ci
      - run: npx vitest run
```

---

## Related Documentation

- [Architecture](./architecture.md) - Technical architecture and LangGraph progression
- [Playwright E2E](./playwright-e2e.md) - End-to-end test documentation with screenshots
- [Product](./product.md) - Product requirements and features
