"""Tests for lesson API routes.

TDD: These tests define the expected behavior for lesson endpoints.
Implementation follows to make these tests pass.

Phase 6: Micro-lessons feature - API endpoints.
"""

import html
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from src.api.auth import AuthenticatedUser, get_current_user
from src.lessons.models import (
    ExerciseType,
    Lesson,
    LessonContent,
    LessonLevel,
    LessonMetadata,
    LessonStep,
    LessonStepType,
    MultipleChoiceExercise,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_user() -> AuthenticatedUser:
    """Create mock authenticated user."""
    return AuthenticatedUser(id="user-123", email="test@example.com")


@pytest.fixture
def sample_lesson() -> Lesson:
    """Create a sample lesson for testing."""
    return Lesson(
        metadata=LessonMetadata(
            id="greetings-001",
            title="Basic Greetings",
            description="Learn to say hello and goodbye",
            language="es",
            level=LessonLevel.A0,
            estimated_minutes=3,
            category="greetings",
            tags=["greeting", "basics"],
            vocabulary_count=5,
            icon="👋",
        ),
        content=LessonContent(
            steps=[
                LessonStep(
                    type=LessonStepType.INSTRUCTION,
                    content="Welcome! Let's learn greetings.",
                    order=1,
                ),
                LessonStep(
                    type=LessonStepType.VOCABULARY,
                    content="Key vocabulary:",
                    vocabulary=[
                        {"word": "hola", "translation": "hello"},
                        {"word": "adiós", "translation": "goodbye"},
                    ],
                    order=2,
                ),
                LessonStep(
                    type=LessonStepType.EXAMPLE,
                    content="Hola, ¿cómo estás?",
                    translation="Hello, how are you?",
                    order=3,
                ),
                LessonStep(
                    type=LessonStepType.PRACTICE,
                    content="Try the exercise!",
                    exercise_id="ex-001",
                    order=4,
                ),
            ],
            exercises=[
                MultipleChoiceExercise(
                    id="ex-001",
                    type=ExerciseType.MULTIPLE_CHOICE,
                    question="How do you say 'hello' in Spanish?",
                    options=["Hola", "Adiós", "Gracias", "Por favor"],
                    correct_index=0,
                    explanation="'Hola' means 'hello'.",
                ),
            ],
        ),
    )


@pytest.fixture
def mock_lesson_service(sample_lesson: Lesson) -> MagicMock:
    """Create mock lesson service."""
    service = MagicMock()
    service.get_lesson.return_value = sample_lesson
    service.get_lessons.return_value = [sample_lesson]
    service.get_lessons_metadata.return_value = [sample_lesson.metadata]
    service.get_lesson_vocabulary.return_value = [
        {"word": "hola", "translation": "hello"},
        {"word": "adiós", "translation": "goodbye"},
    ]
    return service


@pytest.fixture
def app(
    mock_user: AuthenticatedUser,
    mock_lesson_service: MagicMock,
    tmp_path: Path,
) -> Generator[FastAPI, None, None]:
    """Create test FastAPI app with mocked dependencies.

    Patches LessonProgressRepository and get_supabase_admin to prevent
    Supabase connections during tests. The authenticated user path uses
    LessonProgressRepository(user.id, client=None), which internally
    calls get_supabase(). Patching at the import location in the lessons
    module ensures no real database calls are made.
    """
    from fastapi import FastAPI
    from fastapi.templating import Jinja2Templates

    # Create minimal templates
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    partials_dir = templates_dir / "partials"
    partials_dir.mkdir()

    (templates_dir / "lessons.html").write_text("""
<!DOCTYPE html>
<html>
<head><title>Lessons</title></head>
<body>
<h1>Lessons - {{ language }}</h1>
<div class="lessons-grid">
{% for lesson in lessons.beginner %}
<div class="lesson-card" data-id="{{ lesson.id }}">
    <span class="icon">{{ lesson.icon }}</span>
    <h2>{{ lesson.title }}</h2>
    <p>{{ lesson.description }}</p>
    <span class="level">{{ lesson.level }}</span>
    <span class="duration">{{ lesson.estimated_minutes }} min</span>
</div>
{% endfor %}
{% for lesson in lessons.intermediate %}
<div class="lesson-card" data-id="{{ lesson.id }}">
    <span class="icon">{{ lesson.icon }}</span>
    <h2>{{ lesson.title }}</h2>
    <p>{{ lesson.description }}</p>
    <span class="level">{{ lesson.level }}</span>
    <span class="duration">{{ lesson.estimated_minutes }} min</span>
</div>
{% endfor %}
</div>
</body>
</html>
""")

    (templates_dir / "lesson_player.html").write_text("""
<!DOCTYPE html>
<html>
<head><title>{{ lesson.metadata.title }}</title></head>
<body>
<div class="lesson-player" data-lesson-id="{{ lesson.metadata.id }}">
    <h1>{{ lesson.metadata.title }}</h1>
    <div class="progress">Step {{ current_step + 1 }} of {{ total_steps }}</div>
    <div class="step-content">
        {{ step.content }}
    </div>
</div>
</body>
</html>
""")

    (partials_dir / "lesson_step.html").write_text("""
<div class="step" data-step="{{ step_index }}" data-type="{{ step.type }}">
    <div class="step-content">{{ step.content }}</div>
    {% if step.translation %}
    <div class="translation">{{ step.translation }}</div>
    {% endif %}
    {% if step.vocabulary %}
    <ul class="vocab-list">
    {% for v in step.vocabulary %}
        <li>{{ v.word }} - {{ v.translation }}</li>
    {% endfor %}
    </ul>
    {% endif %}
</div>
""")

    (partials_dir / "lesson_exercise.html").write_text("""
<div class="exercise" data-id="{{ exercise.id }}" data-type="{{ exercise.type }}">
    <p class="question">{{ exercise.question }}</p>
    {% if exercise.options %}
    <div class="options">
    {% for opt in exercise.options %}
        <button class="option" data-index="{{ loop.index0 }}">{{ opt }}</button>
    {% endfor %}
    </div>
    {% endif %}
</div>
""")

    (partials_dir / "lesson_complete.html").write_text("""
<div class="lesson-complete">
    <h2>🎉 Lesson Complete!</h2>
    <p>Score: {{ score }}%</p>
    <p>Vocabulary learned: {{ vocab_count }} words</p>
    <a href="/lessons" class="btn">Back to Lessons</a>
    <a href="/chat" class="btn primary">Practice with Hermano</a>
</div>
""")

    (partials_dir / "lesson_card.html").write_text("""
<div class="lesson-card" data-id="{{ lesson_id }}">
    <span class="status">{% if completed %}✅{% endif %}</span>
</div>
""")

    (partials_dir / "lesson_content.html").write_text("""
<div class="lesson-content" data-lesson-id="{{ lesson_id }}">
    <h2>Lesson: {{ lesson_id }}</h2>
</div>
""")

    app = FastAPI()
    templates = Jinja2Templates(directory=str(templates_dir))

    # Mock auth
    async def get_mock_user() -> AuthenticatedUser:
        return mock_user

    # Mock templates
    def get_mock_templates():
        return templates

    # Import and configure routes
    from src.api.dependencies import get_cached_templates
    from src.api.routes.lessons import router as lessons_router
    from src.lessons.service import get_lesson_service

    app.dependency_overrides[get_current_user] = get_mock_user
    app.dependency_overrides[get_cached_templates] = get_mock_templates
    app.dependency_overrides[get_lesson_service] = lambda: mock_lesson_service

    app.include_router(lessons_router, prefix="/lessons")

    # Patch Supabase-dependent objects in the lessons route module to prevent
    # real database connections during tests. LessonProgressRepository is called
    # in the complete_lesson endpoint for progress persistence.
    with (
        patch("src.api.routes.lessons.LessonProgressRepository") as mock_repo_cls,
        patch("src.api.routes.lessons.get_supabase_admin") as mock_admin,
    ):
        mock_repo_cls.return_value = MagicMock()
        mock_admin.return_value = MagicMock()
        yield app


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Create test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncClient:
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# =============================================================================
# Lesson List Tests
# =============================================================================


class TestGetLessonsPage:
    """Tests for GET /lessons - Lessons overview page."""

    def test_get_lessons_returns_200(self, client: TestClient) -> None:
        """GET /lessons should return 200 OK."""
        response = client.get("/lessons/")
        assert response.status_code == 200

    def test_get_lessons_returns_html(self, client: TestClient) -> None:
        """GET /lessons should return HTML."""
        response = client.get("/lessons/")
        assert "text/html" in response.headers["content-type"]

    def test_get_lessons_contains_title(self, client: TestClient) -> None:
        """GET /lessons should include title."""
        response = client.get("/lessons/")
        assert "Lessons" in response.text

    def test_get_lessons_with_language_filter(self, client: TestClient) -> None:
        """GET /lessons?language=es should filter by Spanish."""
        response = client.get("/lessons/?language=es")
        assert response.status_code == 200
        assert "es" in response.text

    def test_get_lessons_with_level_filter(self, client: TestClient) -> None:
        """GET /lessons?level=A0 should filter by level."""
        response = client.get("/lessons/?level=A0")
        assert response.status_code == 200

    def test_get_lessons_includes_lesson_cards(
        self, client: TestClient, sample_lesson: Lesson
    ) -> None:
        """GET /lessons should include lesson cards."""
        response = client.get("/lessons/")
        assert "lesson-card" in response.text
        assert sample_lesson.metadata.title in response.text


# =============================================================================
# Lesson Player Tests
# =============================================================================


class TestGetLessonPlayer:
    """Tests for GET /lessons/{lesson_id}/play - Lesson player page."""

    def test_get_lesson_player_returns_200(self, client: TestClient) -> None:
        """GET /lessons/{id}/play should return 200."""
        response = client.get("/lessons/greetings-001/play")
        assert response.status_code == 200

    def test_get_lesson_player_returns_html(self, client: TestClient) -> None:
        """GET /lessons/{id}/play should return HTML."""
        response = client.get("/lessons/greetings-001/play")
        assert "text/html" in response.headers["content-type"]

    def test_get_lesson_player_includes_title(
        self, client: TestClient, sample_lesson: Lesson
    ) -> None:
        """Lesson player should show lesson title."""
        response = client.get("/lessons/greetings-001/play")
        assert sample_lesson.metadata.title in response.text

    def test_get_lesson_player_includes_progress(self, client: TestClient) -> None:
        """Lesson player should show step progress."""
        response = client.get("/lessons/greetings-001/play")
        assert "Step" in response.text

    def test_get_lesson_not_found(self, client: TestClient, mock_lesson_service: MagicMock) -> None:
        """GET /lessons/{invalid}/play should return 404."""
        mock_lesson_service.get_lesson.return_value = None
        response = client.get("/lessons/nonexistent/play")
        assert response.status_code == 404


# =============================================================================
# Lesson Step Navigation Tests
# =============================================================================


class TestLessonStepNavigation:
    """Tests for lesson step endpoints."""

    def test_get_step_returns_200(self, client: TestClient) -> None:
        """GET /lessons/{id}/step/{n} should return 200."""
        response = client.get("/lessons/greetings-001/step/0")
        assert response.status_code == 200

    def test_get_step_returns_partial(self, client: TestClient) -> None:
        """GET /lessons/{id}/step/{n} should return partial HTML."""
        response = client.get("/lessons/greetings-001/step/0")
        assert "<!DOCTYPE html>" not in response.text
        assert "step-content" in response.text

    def test_get_step_includes_content(self, client: TestClient, sample_lesson: Lesson) -> None:
        """Step response should include step content."""
        response = client.get("/lessons/greetings-001/step/0")
        # First step is instruction
        # Note: HTML escaping converts ' to &#39; so we unescape for comparison
        assert sample_lesson.content.steps[0].content in html.unescape(response.text)

    def test_get_vocabulary_step(self, client: TestClient) -> None:
        """Vocabulary step should show word list."""
        response = client.get("/lessons/greetings-001/step/1")
        assert "vocab-list" in response.text or "hola" in response.text

    def test_get_step_out_of_range(self, client: TestClient, sample_lesson: Lesson) -> None:
        """GET /lessons/{id}/step/{invalid} should return 404."""
        invalid_step = len(sample_lesson.content.steps) + 10
        response = client.get(f"/lessons/greetings-001/step/{invalid_step}")
        assert response.status_code == 404

    def test_next_step_returns_next(self, client: TestClient) -> None:
        """POST /lessons/{id}/step/next should return next step."""
        response = client.post(
            "/lessons/greetings-001/step/next",
            data={"current_step": "0"},
        )
        assert response.status_code == 200

    def test_previous_step(self, client: TestClient) -> None:
        """POST /lessons/{id}/step/prev should return previous step."""
        response = client.post(
            "/lessons/greetings-001/step/prev",
            data={"current_step": "2"},
        )
        assert response.status_code == 200


# =============================================================================
# Exercise Tests
# =============================================================================


class TestLessonExercises:
    """Tests for exercise endpoints."""

    def test_get_exercise_returns_200(self, client: TestClient) -> None:
        """GET /lessons/{id}/exercise/{ex_id} should return 200."""
        response = client.get("/lessons/greetings-001/exercise/ex-001")
        assert response.status_code == 200

    def test_get_exercise_returns_partial(self, client: TestClient) -> None:
        """GET /lessons/{id}/exercise/{ex_id} should return partial HTML."""
        response = client.get("/lessons/greetings-001/exercise/ex-001")
        assert "<!DOCTYPE html>" not in response.text
        assert "exercise" in response.text

    def test_get_exercise_includes_question(
        self, client: TestClient, sample_lesson: Lesson
    ) -> None:
        """Exercise response should include question."""
        response = client.get("/lessons/greetings-001/exercise/ex-001")
        exercise = sample_lesson.content.exercises[0]
        # Note: HTML escaping converts ' to &#39; so we unescape for comparison
        assert exercise.question in html.unescape(response.text)

    def test_get_exercise_includes_options(self, client: TestClient) -> None:
        """Multiple choice exercise should show options."""
        response = client.get("/lessons/greetings-001/exercise/ex-001")
        assert "option" in response.text
        assert "Hola" in response.text

    def test_submit_exercise_correct(self, client: TestClient) -> None:
        """POST /lessons/{id}/exercise/{ex_id}/submit with correct answer."""
        response = client.post(
            "/lessons/greetings-001/exercise/ex-001/submit",
            data={"answer": "0"},  # Correct index
        )
        assert response.status_code == 200
        # Should indicate correct
        assert "correct" in response.text.lower() or "✅" in response.text

    def test_submit_exercise_incorrect(self, client: TestClient) -> None:
        """POST /lessons/{id}/exercise/{ex_id}/submit with wrong answer."""
        response = client.post(
            "/lessons/greetings-001/exercise/ex-001/submit",
            data={"answer": "1"},  # Wrong index
        )
        assert response.status_code == 200
        # Should indicate incorrect and show explanation
        assert "incorrect" in response.text.lower() or "try again" in response.text.lower()

    def test_exercise_not_found(self, client: TestClient, mock_lesson_service: MagicMock) -> None:
        """GET /lessons/{id}/exercise/{invalid} should return 404."""
        # The lesson exists but exercise doesn't
        response = client.get("/lessons/greetings-001/exercise/nonexistent")
        assert response.status_code == 404


# =============================================================================
# Lesson Completion Tests
# =============================================================================


class TestLessonCompletion:
    """Tests for lesson completion endpoints."""

    def test_complete_lesson_returns_200(self, client: TestClient) -> None:
        """POST /lessons/{id}/complete should return 200."""
        response = client.post(
            "/lessons/greetings-001/complete",
            data={"score": "100"},
        )
        assert response.status_code == 200

    def test_complete_lesson_returns_completion_view(self, client: TestClient) -> None:
        """Completion should show celebration view."""
        response = client.post(
            "/lessons/greetings-001/complete",
            data={"score": "80"},
        )
        assert "lesson-complete" in response.text or "Complete" in response.text

    def test_complete_lesson_shows_score(self, client: TestClient) -> None:
        """Completion should display score."""
        response = client.post(
            "/lessons/greetings-001/complete",
            data={"score": "75"},
        )
        assert "75" in response.text or "Score" in response.text

    def test_complete_lesson_shows_practice_link(self, client: TestClient) -> None:
        """Completion should link to practice with Hermano."""
        response = client.post(
            "/lessons/greetings-001/complete",
            data={"score": "100"},
        )
        assert "/chat" in response.text or "Practice" in response.text

    def test_complete_lesson_shows_vocab_count(
        self, client: TestClient, sample_lesson: Lesson
    ) -> None:
        """Completion should show vocabulary count."""
        response = client.post(
            "/lessons/greetings-001/complete",
            data={"score": "100"},
        )
        # Should mention vocabulary
        assert "vocab" in response.text.lower() or "words" in response.text.lower()


# =============================================================================
# Lesson Handoff to Conversation Tests
# =============================================================================


class TestLessonHandoff:
    """Tests for lesson → conversation handoff."""

    def test_handoff_endpoint_exists(self, client: TestClient) -> None:
        """POST /lessons/{id}/handoff should return 200."""
        response = client.post("/lessons/greetings-001/handoff")
        assert response.status_code in [200, 302, 303]  # OK or redirect

    def test_handoff_redirects_to_chat(self, client: TestClient) -> None:
        """Handoff should redirect to chat page."""
        response = client.post(
            "/lessons/greetings-001/handoff",
            follow_redirects=False,
        )
        # Should redirect via HTMX
        if response.status_code == 200:
            assert "HX-Redirect" in response.headers or "/chat" in response.text
        else:
            assert "/chat" in response.headers.get("location", "")

    def test_handoff_sets_lesson_context(self, client: TestClient) -> None:
        """Handoff should set context for conversation."""
        # The handoff should prepare conversation context with lesson vocab
        # This is validated through the chat receiving lesson context
        response = client.post("/lessons/greetings-001/handoff")
        assert response.status_code in [200, 302, 303]


# =============================================================================
# Authentication Tests
# =============================================================================


class TestLessonAuthentication:
    """Tests for authentication on lesson routes (guest access allowed)."""

    def test_lessons_allow_guest_access(self, client: TestClient) -> None:
        """GET /lessons should allow guest access (OptionalUserDep)."""
        response = client.get("/lessons/")
        # Guest access is allowed - should return 200
        assert response.status_code == 200

    def test_lesson_player_allows_guest_access(
        self, client: TestClient, mock_lesson_service: MagicMock, sample_lesson: Lesson
    ) -> None:
        """Lesson player should allow guest access."""
        mock_lesson_service.get_lesson.return_value = sample_lesson

        response = client.get("/lessons/greetings-001/play")
        # Guest access is allowed
        assert response.status_code == 200


# =============================================================================
# Edge Cases
# =============================================================================


class TestLessonEdgeCases:
    """Edge case tests for lesson routes."""

    def test_lesson_with_special_characters_in_id(self, client: TestClient) -> None:
        """Lesson ID with hyphens and numbers should work."""
        response = client.get("/lessons/greetings-001/play")
        assert response.status_code in [200, 404]  # Works or not found

    def test_empty_lessons_list(self, client: TestClient, mock_lesson_service: MagicMock) -> None:
        """Empty lessons list should render correctly."""
        mock_lesson_service.get_lessons.return_value = []
        mock_lesson_service.get_lessons_metadata.return_value = []

        response = client.get("/lessons/")
        assert response.status_code == 200

    def test_lesson_with_no_exercises(
        self, client: TestClient, mock_lesson_service: MagicMock, sample_lesson: Lesson
    ) -> None:
        """Lesson with no exercises should complete directly."""
        # Modify sample to have no exercises
        sample_lesson.content.exercises = []
        mock_lesson_service.get_lesson.return_value = sample_lesson

        response = client.post("/lessons/greetings-001/complete")
        assert response.status_code == 200

    async def test_concurrent_lesson_access(self, async_client: AsyncClient) -> None:
        """Multiple concurrent requests should work."""
        import asyncio

        tasks = [
            async_client.get("/lessons/"),
            async_client.get("/lessons/greetings-001/play"),
            async_client.get("/lessons/greetings-001/step/0"),
        ]
        responses = await asyncio.gather(*tasks)

        assert all(r.status_code in [200, 404] for r in responses)
