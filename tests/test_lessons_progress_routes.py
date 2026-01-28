"""Tests for lessons and progress API routes.

Comprehensive tests for the micro-lesson endpoints and progress tracking routes.
Tests cover route responses, HTML content, HTTP methods, and edge cases.

Phase 5: Updated tests to include authentication mocking.
Phase 6: Updated tests to match new lesson API design with LessonService.
Phase 7: Updated progress route tests for real ProgressService/VocabularyRepository.
"""

from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from jinja2 import Environment, FileSystemLoader

from src.api.auth import AuthenticatedUser, get_current_user_optional
from src.api.routes import lessons, progress
from src.lessons.models import (
    Lesson,
    LessonContent,
    LessonLevel,
    LessonMetadata,
    LessonStep,
    LessonStepType,
)
from src.lessons.service import get_lesson_service
from src.services.progress import DashboardStats


@pytest.fixture
def mock_templates_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create temporary directory with stub templates for testing.

    Creates minimal HTML templates needed to test route responses
    without depending on actual template files.

    Args:
        tmp_path: pytest temporary path fixture.

    Yields:
        Path: Path to temporary templates directory.
    """
    templates_path = tmp_path / "templates"
    templates_path.mkdir()

    # Create partials directory
    partials_path = templates_path / "partials"
    partials_path.mkdir()

    # Create main templates
    (templates_path / "lessons.html").write_text(
        """<!DOCTYPE html>
<html>
<head><title>Lessons</title></head>
<body>
<h1>Lessons - {{ language }} ({{ level }})</h1>
<div class="lessons-list">
{% for lesson in lessons %}
<div class="lesson-card">{{ lesson.id }}</div>
{% endfor %}
</div>
</body>
</html>"""
    )

    (templates_path / "lesson_player.html").write_text(
        """<!DOCTYPE html>
<html>
<head><title>{{ lesson.metadata.title }}</title></head>
<body>
<div class="lesson-player" data-lesson-id="{{ lesson.metadata.id }}">
    <h1>{{ lesson.metadata.title }}</h1>
    <div class="progress">Step {{ current_step + 1 }} of {{ total_steps }}</div>
</div>
</body>
</html>"""
    )

    (templates_path / "progress.html").write_text(
        """<!DOCTYPE html>
<html>
<head><title>Progress</title></head>
<body>
<h1>Progress</h1>
<div class="stats">
<p>Total Words: {{ total_words }}</p>
<p>Sessions: {{ sessions_count }}</p>
<p>Current Streak: {{ current_streak }}</p>
<p>Lessons Completed: {{ lessons_completed }}</p>
</div>
<div class="vocabulary-list">
{% for word in vocabulary %}
<div class="vocab-item">{{ word }}</div>
{% endfor %}
</div>
</body>
</html>"""
    )

    # Create partial templates
    (partials_path / "lesson_step.html").write_text(
        """<div class="step" data-step="{{ step_index }}" data-type="{{ step.type }}">
<div class="step-content">{{ step.content }}</div>
</div>"""
    )

    (partials_path / "lesson_complete.html").write_text(
        """<div class="lesson-complete">
<h2>Lesson Complete!</h2>
<p>Score: {{ score }}%</p>
<p>Vocabulary: {{ vocab_count }} words</p>
<a href="/chat">Practice with Hermano</a>
</div>"""
    )

    (partials_path / "lesson_card.html").write_text(
        """<div class="lesson-card" data-lesson-id="{{ lesson_id }}">
<h3>{{ lesson_id }}</h3>
{% if completed %}
<span class="status">Completed</span>
{% else %}
<span class="status">In Progress</span>
{% endif %}
</div>"""
    )

    (partials_path / "progress_vocab.html").write_text(
        """<div class="progress-vocab">
<h3>Vocabulary ({{ language }})</h3>
<ul>
{% for word in vocabulary %}
<li class="vocab-word">{{ word }}</li>
{% endfor %}
</ul>
</div>"""
    )

    (partials_path / "stats_summary.html").write_text(
        """<div class="stats-summary">
<p>Messages Today: {{ messages_today }}</p>
<p>Words Learned Today: {{ words_learned_today }}</p>
<p>Accuracy: {{ accuracy_rate }}%</p>
<p>Total Words: {{ total_words }}</p>
<p>Total Sessions: {{ total_sessions }}</p>
</div>"""
    )

    yield templates_path


class MockJinja2Templates:
    """Mock Jinja2Templates for testing without actual template files."""

    def __init__(self, directory: str) -> None:
        """Initialize mock templates.

        Args:
            directory: Path to templates directory.
        """
        self.env = Environment(
            loader=FileSystemLoader(directory),
            autoescape=True,
        )

    def TemplateResponse(
        self,
        request: Any,
        name: str,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Render a template response.

        Args:
            request: FastAPI request object.
            name: Template name.
            context: Template context dictionary.

        Returns:
            HTMLResponse with rendered template.
        """
        from fastapi.responses import HTMLResponse

        if context is None:
            context = {}

        template = self.env.get_template(name)
        content = template.render(**context)
        return HTMLResponse(content=content)


@pytest.fixture
def mock_user() -> AuthenticatedUser:
    """Create a mock authenticated user for testing.

    Returns:
        AuthenticatedUser: Test user instance.
    """
    return AuthenticatedUser(
        id="test-user-123",
        email="test@example.com",
    )


@pytest.fixture
def sample_lesson() -> Lesson:
    """Create a sample lesson for testing."""
    return Lesson(
        metadata=LessonMetadata(
            id="test-lesson-001",
            title="Test Lesson",
            description="A test lesson",
            language="es",
            level=LessonLevel.A0,
            estimated_minutes=3,
            category="test",
            tags=["test"],
            vocabulary_count=2,
            icon="test-icon",
        ),
        content=LessonContent(
            steps=[
                LessonStep(
                    type=LessonStepType.INSTRUCTION,
                    content="Welcome to the test lesson!",
                    order=1,
                ),
                LessonStep(
                    type=LessonStepType.VOCABULARY,
                    content="Key vocabulary:",
                    vocabulary=[
                        {"word": "hola", "translation": "hello"},
                        {"word": "adios", "translation": "goodbye"},
                    ],
                    order=2,
                ),
            ],
            exercises=[],
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
        {"word": "adios", "translation": "goodbye"},
    ]
    return service


@pytest.fixture
def mock_dashboard_stats() -> DashboardStats:
    """Create mock dashboard stats for testing.

    Returns:
        DashboardStats: Stats with known test values.
    """
    return DashboardStats(
        total_words=42,
        total_sessions=10,
        lessons_completed=5,
        current_streak=3,
        accuracy_rate=87.5,
        words_learned_today=7,
        messages_today=15,
    )


@pytest.fixture
def mock_progress_service(mock_dashboard_stats: DashboardStats) -> MagicMock:
    """Create a mock ProgressService instance.

    Args:
        mock_dashboard_stats: Dashboard stats to return from the mock.

    Returns:
        MagicMock: Mock ProgressService.
    """
    service = MagicMock()
    service.get_dashboard_stats.return_value = mock_dashboard_stats
    service.get_chart_data.return_value = MagicMock(
        to_dict=MagicMock(
            return_value={
                "vocab_growth": [{"date": "2026-01-27", "cumulative_words": 42}],
                "accuracy_trend": [{"date": "2026-01-27", "accuracy": 87.5}],
            }
        )
    )
    return service


@pytest.fixture
def mock_vocab_repo() -> MagicMock:
    """Create a mock VocabularyRepository instance.

    Returns:
        MagicMock: Mock VocabularyRepository.
    """
    repo = MagicMock()
    repo.get_all.return_value = []
    repo.delete.return_value = None
    return repo


@pytest.fixture
def test_app(
    mock_templates_dir: Path,
    mock_user: AuthenticatedUser,
    mock_lesson_service: MagicMock,
    mock_progress_service: MagicMock,
    mock_vocab_repo: MagicMock,
) -> FastAPI:
    """Create a test FastAPI app with lessons and progress routers mounted.

    Phase 5: Added authentication mocking for protected routes.
    Phase 6: Added LessonService mocking.
    Phase 7: Added ProgressService and VocabularyRepository mocking.

    Args:
        mock_templates_dir: Path to temporary templates directory.
        mock_user: Mock authenticated user for auth.
        mock_lesson_service: Mock lesson service.
        mock_progress_service: Mock progress service.
        mock_vocab_repo: Mock vocabulary repository.

    Returns:
        FastAPI: Configured test application.
    """
    app = FastAPI(title="Test App")

    # Create mock templates
    templates = MockJinja2Templates(directory=str(mock_templates_dir))

    def get_test_templates() -> MockJinja2Templates:
        return templates

    # Mock auth dependency
    async def mock_get_current_user() -> AuthenticatedUser:
        return mock_user

    # Mock lesson service
    def get_mock_lesson_service() -> MagicMock:
        return mock_lesson_service

    # Override the dependency in both routers
    from src.api.dependencies import get_cached_templates

    app.dependency_overrides[get_cached_templates] = get_test_templates
    app.dependency_overrides[get_current_user_optional] = mock_get_current_user
    app.dependency_overrides[get_lesson_service] = get_mock_lesson_service

    # Mount routers with prefixes
    app.include_router(lessons.router, prefix="/lessons", tags=["lessons"])
    app.include_router(progress.router, prefix="/progress", tags=["progress"])

    # Patch ProgressService and VocabularyRepository where they are imported in the routes
    app._progress_service_patcher = patch(
        "src.api.routes.progress.ProgressService",
        return_value=mock_progress_service,
    )
    app._vocab_repo_patcher = patch(
        "src.api.routes.progress.VocabularyRepository",
        return_value=mock_vocab_repo,
    )
    # Patch LessonProgressRepository in lessons routes for complete_lesson endpoint
    app._lesson_progress_repo_patcher = patch(
        "src.api.routes.lessons.LessonProgressRepository",
        return_value=MagicMock(),
    )
    app._progress_service_patcher.start()
    app._vocab_repo_patcher.start()
    app._lesson_progress_repo_patcher.start()

    return app


@pytest.fixture
def client(test_app: FastAPI) -> Generator[TestClient, None, None]:
    """Create synchronous test client.

    Args:
        test_app: FastAPI test application.

    Yields:
        TestClient: Synchronous HTTP client for testing.
    """
    with TestClient(test_app) as c:
        yield c

    # Stop patchers after client is done
    test_app._progress_service_patcher.stop()
    test_app._vocab_repo_patcher.stop()
    test_app._lesson_progress_repo_patcher.stop()


@pytest.fixture
async def async_client(test_app: FastAPI) -> AsyncClient:
    """Create async test client.

    Args:
        test_app: FastAPI test application.

    Returns:
        AsyncClient: Async HTTP client for testing.
    """
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    # Stop patchers after client is done
    test_app._progress_service_patcher.stop()
    test_app._vocab_repo_patcher.stop()
    test_app._lesson_progress_repo_patcher.stop()


# =============================================================================
# Lessons Route Tests
# =============================================================================


class TestGetLessonsPage:
    """Tests for GET /lessons - Lessons overview page."""

    def test_get_lessons_page_returns_200(self, client: TestClient) -> None:
        """GET /lessons should return 200 OK."""
        response = client.get("/lessons/")
        assert response.status_code == 200

    def test_get_lessons_page_returns_html(self, client: TestClient) -> None:
        """GET /lessons should return HTML content type."""
        response = client.get("/lessons/")
        assert "text/html" in response.headers["content-type"]

    def test_get_lessons_page_contains_title(self, client: TestClient) -> None:
        """GET /lessons should include Lessons title in response."""
        response = client.get("/lessons/")
        assert "Lessons" in response.text

    def test_get_lessons_page_contains_language(self, client: TestClient) -> None:
        """GET /lessons should include language in context."""
        response = client.get("/lessons/")
        # Default language is "es" based on route implementation
        assert "es" in response.text

    def test_get_lessons_page_contains_level(self, client: TestClient) -> None:
        """GET /lessons should include level in context."""
        response = client.get("/lessons/")
        # Default level is "A1" based on route implementation
        assert "A1" in response.text

    def test_get_lessons_page_has_lessons_container(self, client: TestClient) -> None:
        """GET /lessons should include lessons list container."""
        response = client.get("/lessons/")
        assert "lessons-list" in response.text

    def test_get_lessons_page_is_full_html(self, client: TestClient) -> None:
        """GET /lessons should return full HTML page."""
        response = client.get("/lessons/")
        assert "<!DOCTYPE html>" in response.text
        assert "<html" in response.text
        assert "</html>" in response.text

    async def test_get_lessons_page_async(self, async_client: AsyncClient) -> None:
        """GET /lessons should work with async client."""
        response = await async_client.get("/lessons/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestGetLessonPlayer:
    """Tests for GET /lessons/{lesson_id}/play - Lesson player page."""

    def test_get_lesson_player_returns_200(self, client: TestClient) -> None:
        """GET /lessons/{lesson_id}/play should return 200 OK."""
        response = client.get("/lessons/test-lesson-001/play")
        assert response.status_code == 200

    def test_get_lesson_player_returns_html(self, client: TestClient) -> None:
        """GET /lessons/{lesson_id}/play should return HTML content type."""
        response = client.get("/lessons/test-lesson-001/play")
        assert "text/html" in response.headers["content-type"]

    def test_get_lesson_player_contains_lesson_title(
        self, client: TestClient, sample_lesson: Lesson
    ) -> None:
        """GET /lessons/{lesson_id}/play should include lesson title."""
        response = client.get("/lessons/test-lesson-001/play")
        assert sample_lesson.metadata.title in response.text

    def test_get_lesson_player_is_full_html(self, client: TestClient) -> None:
        """GET /lessons/{lesson_id}/play should return full HTML page."""
        response = client.get("/lessons/test-lesson-001/play")
        assert "<!DOCTYPE html>" in response.text

    def test_get_lesson_player_contains_progress(self, client: TestClient) -> None:
        """GET /lessons/{lesson_id}/play should include step progress."""
        response = client.get("/lessons/test-lesson-001/play")
        assert "Step" in response.text

    def test_get_lesson_not_found(self, client: TestClient, mock_lesson_service: MagicMock) -> None:
        """GET /lessons/{invalid}/play should return 404."""
        mock_lesson_service.get_lesson.return_value = None
        response = client.get("/lessons/nonexistent/play")
        assert response.status_code == 404

    async def test_get_lesson_player_async(self, async_client: AsyncClient) -> None:
        """GET /lessons/{lesson_id}/play should work with async client."""
        response = await async_client.get("/lessons/test-lesson-001/play")
        assert response.status_code == 200


class TestLessonStepNavigation:
    """Tests for lesson step navigation endpoints."""

    def test_get_step_returns_200(self, client: TestClient) -> None:
        """GET /lessons/{id}/step/{n} should return 200."""
        response = client.get("/lessons/test-lesson-001/step/0")
        assert response.status_code == 200

    def test_get_step_returns_partial(self, client: TestClient) -> None:
        """GET /lessons/{id}/step/{n} should return partial HTML."""
        response = client.get("/lessons/test-lesson-001/step/0")
        assert "<!DOCTYPE html>" not in response.text
        assert "step-content" in response.text

    def test_get_step_out_of_range(
        self, client: TestClient, mock_lesson_service: MagicMock
    ) -> None:
        """GET /lessons/{id}/step/{invalid} should return 404."""
        response = client.get("/lessons/test-lesson-001/step/999")
        assert response.status_code == 404


class TestCompleteLesson:
    """Tests for POST /lessons/{lesson_id}/complete - Mark lesson as completed."""

    def test_complete_lesson_returns_200(self, client: TestClient) -> None:
        """POST /lessons/{lesson_id}/complete should return 200 OK."""
        response = client.post("/lessons/test-lesson-001/complete")
        assert response.status_code == 200

    def test_complete_lesson_returns_html(self, client: TestClient) -> None:
        """POST /lessons/{lesson_id}/complete should return HTML content type."""
        response = client.post("/lessons/test-lesson-001/complete")
        assert "text/html" in response.headers["content-type"]

    def test_complete_lesson_shows_completed_status(self, client: TestClient) -> None:
        """POST /lessons/{lesson_id}/complete should show completed status."""
        response = client.post("/lessons/test-lesson-001/complete")
        assert "Complete" in response.text or "completed" in response.text.lower()

    def test_complete_lesson_is_partial_html(self, client: TestClient) -> None:
        """POST /lessons/{lesson_id}/complete should return partial HTML."""
        response = client.post("/lessons/test-lesson-001/complete")
        assert "<!DOCTYPE html>" not in response.text

    def test_complete_lesson_contains_score(self, client: TestClient) -> None:
        """POST /lessons/{lesson_id}/complete should show score."""
        response = client.post("/lessons/test-lesson-001/complete", data={"score": "85"})
        assert "85" in response.text or "Score" in response.text

    def test_complete_lesson_shows_practice_link(self, client: TestClient) -> None:
        """POST /lessons/{lesson_id}/complete should link to chat."""
        response = client.post("/lessons/test-lesson-001/complete")
        assert "/chat" in response.text or "Practice" in response.text

    async def test_complete_lesson_async(self, async_client: AsyncClient) -> None:
        """POST /lessons/{lesson_id}/complete should work with async client."""
        response = await async_client.post("/lessons/test-lesson-001/complete")
        assert response.status_code == 200


class TestLessonHandoff:
    """Tests for POST /lessons/{lesson_id}/handoff - Handoff to chat."""

    def test_handoff_returns_200(self, client: TestClient) -> None:
        """POST /lessons/{id}/handoff should return 200."""
        response = client.post("/lessons/test-lesson-001/handoff")
        assert response.status_code == 200

    def test_handoff_has_redirect_header(self, client: TestClient) -> None:
        """POST /lessons/{id}/handoff should have HX-Redirect header."""
        response = client.post("/lessons/test-lesson-001/handoff")
        assert "HX-Redirect" in response.headers
        assert "/chat" in response.headers["HX-Redirect"]


# =============================================================================
# Progress Route Tests
# =============================================================================


class TestGetProgressPage:
    """Tests for GET /progress - Progress overview page."""

    def test_get_progress_page_returns_200(self, client: TestClient) -> None:
        """GET /progress should return 200 OK."""
        response = client.get("/progress/")
        assert response.status_code == 200

    def test_get_progress_page_returns_html(self, client: TestClient) -> None:
        """GET /progress should return HTML content type."""
        response = client.get("/progress/")
        assert "text/html" in response.headers["content-type"]

    def test_get_progress_page_contains_title(self, client: TestClient) -> None:
        """GET /progress should include Progress title."""
        response = client.get("/progress/")
        assert "Progress" in response.text

    def test_get_progress_page_is_full_html(self, client: TestClient) -> None:
        """GET /progress should return full HTML page."""
        response = client.get("/progress/")
        assert "<!DOCTYPE html>" in response.text
        assert "</html>" in response.text

    def test_get_progress_page_contains_stats(self, client: TestClient) -> None:
        """GET /progress should include statistics section."""
        response = client.get("/progress/")
        assert "Total Words" in response.text or "stats" in response.text

    def test_get_progress_page_shows_real_stats(self, client: TestClient) -> None:
        """GET /progress should show real stats from ProgressService."""
        response = client.get("/progress/")
        # Mock DashboardStats has total_words=42, current_streak=3
        assert "42" in response.text
        assert "3" in response.text

    def test_get_progress_page_shows_lessons_completed(self, client: TestClient) -> None:
        """GET /progress should show lessons completed count."""
        response = client.get("/progress/")
        # Mock DashboardStats has lessons_completed=5
        assert "5" in response.text

    async def test_get_progress_page_async(self, async_client: AsyncClient) -> None:
        """GET /progress should work with async client."""
        response = await async_client.get("/progress/")
        assert response.status_code == 200
        assert "Progress" in response.text


class TestGetVocabulary:
    """Tests for GET /progress/vocabulary - Vocabulary partial."""

    def test_get_vocabulary_returns_200(self, client: TestClient) -> None:
        """GET /progress/vocabulary should return 200 OK."""
        response = client.get("/progress/vocabulary")
        assert response.status_code == 200

    def test_get_vocabulary_returns_html(self, client: TestClient) -> None:
        """GET /progress/vocabulary should return HTML content type."""
        response = client.get("/progress/vocabulary")
        assert "text/html" in response.headers["content-type"]

    def test_get_vocabulary_is_partial_html(self, client: TestClient) -> None:
        """GET /progress/vocabulary should return partial HTML."""
        response = client.get("/progress/vocabulary")
        assert "<!DOCTYPE html>" not in response.text

    def test_get_vocabulary_contains_vocab_class(self, client: TestClient) -> None:
        """GET /progress/vocabulary should include progress-vocab class."""
        response = client.get("/progress/vocabulary")
        assert "progress-vocab" in response.text

    def test_get_vocabulary_contains_language(self, client: TestClient) -> None:
        """GET /progress/vocabulary should include language in context."""
        response = client.get("/progress/vocabulary")
        # Default language is "es" based on route implementation
        assert "es" in response.text

    def test_get_vocabulary_empty_list(self, client: TestClient) -> None:
        """GET /progress/vocabulary should handle empty vocabulary list."""
        response = client.get("/progress/vocabulary")
        # Should still return 200 with empty list
        assert response.status_code == 200

    def test_get_vocabulary_calls_repo(
        self, client: TestClient, mock_vocab_repo: MagicMock
    ) -> None:
        """GET /progress/vocabulary should call VocabularyRepository.get_all."""
        client.get("/progress/vocabulary")
        mock_vocab_repo.get_all.assert_called_once_with(language="es")

    def test_get_vocabulary_with_language_param(
        self, client: TestClient, mock_vocab_repo: MagicMock
    ) -> None:
        """GET /progress/vocabulary?language=de should filter by language."""
        client.get("/progress/vocabulary?language=de")
        mock_vocab_repo.get_all.assert_called_once_with(language="de")

    async def test_get_vocabulary_async(self, async_client: AsyncClient) -> None:
        """GET /progress/vocabulary should work with async client."""
        response = await async_client.get("/progress/vocabulary")
        assert response.status_code == 200


class TestGetStats:
    """Tests for GET /progress/stats - Session statistics summary."""

    def test_get_stats_returns_200(self, client: TestClient) -> None:
        """GET /progress/stats should return 200 OK."""
        response = client.get("/progress/stats")
        assert response.status_code == 200

    def test_get_stats_returns_html(self, client: TestClient) -> None:
        """GET /progress/stats should return HTML content type."""
        response = client.get("/progress/stats")
        assert "text/html" in response.headers["content-type"]

    def test_get_stats_is_partial_html(self, client: TestClient) -> None:
        """GET /progress/stats should return partial HTML."""
        response = client.get("/progress/stats")
        assert "<!DOCTYPE html>" not in response.text

    def test_get_stats_contains_summary_class(self, client: TestClient) -> None:
        """GET /progress/stats should include stats-summary class."""
        response = client.get("/progress/stats")
        assert "stats-summary" in response.text

    def test_get_stats_contains_messages_today(self, client: TestClient) -> None:
        """GET /progress/stats should include messages_today stat."""
        response = client.get("/progress/stats")
        assert "Messages Today" in response.text

    def test_get_stats_contains_words_learned(self, client: TestClient) -> None:
        """GET /progress/stats should include words_learned_today stat."""
        response = client.get("/progress/stats")
        assert "Words Learned Today" in response.text

    def test_get_stats_contains_accuracy(self, client: TestClient) -> None:
        """GET /progress/stats should include accuracy_rate stat."""
        response = client.get("/progress/stats")
        assert "Accuracy" in response.text

    def test_get_stats_shows_real_values(self, client: TestClient) -> None:
        """GET /progress/stats should show real values from ProgressService."""
        response = client.get("/progress/stats")
        # Mock DashboardStats has messages_today=15, words_learned_today=7, accuracy_rate=87.5
        assert "15" in response.text
        assert "7" in response.text
        assert "87.5" in response.text

    def test_get_stats_shows_total_words(self, client: TestClient) -> None:
        """GET /progress/stats should show total_words from ProgressService."""
        response = client.get("/progress/stats")
        # Mock DashboardStats has total_words=42
        assert "42" in response.text

    async def test_get_stats_async(self, async_client: AsyncClient) -> None:
        """GET /progress/stats should work with async client."""
        response = await async_client.get("/progress/stats")
        assert response.status_code == 200


class TestGetChartData:
    """Tests for GET /progress/chart-data - Chart data JSON endpoint."""

    def test_get_chart_data_returns_200(self, client: TestClient) -> None:
        """GET /progress/chart-data should return 200 OK."""
        response = client.get("/progress/chart-data")
        assert response.status_code == 200

    def test_get_chart_data_returns_json(self, client: TestClient) -> None:
        """GET /progress/chart-data should return JSON content type."""
        response = client.get("/progress/chart-data")
        assert "application/json" in response.headers["content-type"]

    def test_get_chart_data_contains_vocab_growth(self, client: TestClient) -> None:
        """GET /progress/chart-data should include vocab_growth."""
        response = client.get("/progress/chart-data")
        data = response.json()
        assert "vocab_growth" in data
        assert len(data["vocab_growth"]) > 0

    def test_get_chart_data_contains_accuracy_trend(self, client: TestClient) -> None:
        """GET /progress/chart-data should include accuracy_trend."""
        response = client.get("/progress/chart-data")
        data = response.json()
        assert "accuracy_trend" in data
        assert len(data["accuracy_trend"]) > 0

    def test_get_chart_data_with_language_param(
        self, client: TestClient, mock_progress_service: MagicMock
    ) -> None:
        """GET /progress/chart-data?language=de should pass language to service."""
        client.get("/progress/chart-data?language=de")
        mock_progress_service.get_chart_data.assert_called_once_with(language="de", days=30)

    def test_get_chart_data_with_days_param(
        self, client: TestClient, mock_progress_service: MagicMock
    ) -> None:
        """GET /progress/chart-data?days=7 should pass days to service."""
        client.get("/progress/chart-data?days=7")
        mock_progress_service.get_chart_data.assert_called_once_with(language="es", days=7)

    async def test_get_chart_data_async(self, async_client: AsyncClient) -> None:
        """GET /progress/chart-data should work with async client."""
        response = await async_client.get("/progress/chart-data")
        assert response.status_code == 200


class TestRemoveVocabularyWord:
    """Tests for DELETE /progress/vocabulary/{word_id} - Remove vocabulary word."""

    def test_remove_vocabulary_word_returns_200(self, client: TestClient) -> None:
        """DELETE /progress/vocabulary/{word_id} should return 200 OK."""
        response = client.delete("/progress/vocabulary/1")
        assert response.status_code == 200

    def test_remove_vocabulary_word_returns_html(self, client: TestClient) -> None:
        """DELETE /progress/vocabulary/{word_id} should return HTML content type."""
        response = client.delete("/progress/vocabulary/1")
        assert "text/html" in response.headers["content-type"]

    def test_remove_vocabulary_word_returns_empty(self, client: TestClient) -> None:
        """DELETE /progress/vocabulary/{word_id} should return empty response for HTMX swap."""
        response = client.delete("/progress/vocabulary/1")
        # Based on route implementation, returns empty string
        assert response.text == ""

    def test_remove_vocabulary_word_calls_repo(
        self, client: TestClient, mock_vocab_repo: MagicMock
    ) -> None:
        """DELETE /progress/vocabulary/{word_id} should call VocabularyRepository.delete."""
        client.delete("/progress/vocabulary/42")
        mock_vocab_repo.delete.assert_called_once_with(42)

    @pytest.mark.parametrize("word_id", [1, 10, 100, 999999])
    def test_remove_vocabulary_word_various_ids(self, client: TestClient, word_id: int) -> None:
        """DELETE /progress/vocabulary/{word_id} should accept various word IDs."""
        response = client.delete(f"/progress/vocabulary/{word_id}")
        assert response.status_code == 200

    def test_remove_vocabulary_word_invalid_id_format(self, client: TestClient) -> None:
        """DELETE /progress/vocabulary/{word_id} should reject non-integer ID."""
        response = client.delete("/progress/vocabulary/invalid")
        # FastAPI returns 422 for invalid path parameter type
        assert response.status_code == 422

    def test_remove_vocabulary_word_negative_id(self, client: TestClient) -> None:
        """DELETE /progress/vocabulary/{word_id} should handle negative IDs."""
        # Currently the route accepts any integer
        response = client.delete("/progress/vocabulary/-1")
        # Depending on validation, this might be 200 or 422
        assert response.status_code in [200, 422]

    async def test_remove_vocabulary_word_async(self, async_client: AsyncClient) -> None:
        """DELETE /progress/vocabulary/{word_id} should work with async client."""
        response = await async_client.delete("/progress/vocabulary/42")
        assert response.status_code == 200
        assert response.text == ""


# =============================================================================
# Integration Tests
# =============================================================================


class TestLessonsAndProgressIntegration:
    """Integration tests for lessons and progress routes working together."""

    def test_both_routers_accessible(self, client: TestClient) -> None:
        """Both lessons and progress routes should be accessible."""
        lessons_response = client.get("/lessons/")
        progress_response = client.get("/progress/")

        assert lessons_response.status_code == 200
        assert progress_response.status_code == 200

    def test_lesson_completion_flow(self, client: TestClient) -> None:
        """Test complete flow: play lesson -> complete lesson."""
        # Play lesson
        play_response = client.get("/lessons/test-lesson-001/play")
        assert play_response.status_code == 200

        # Complete lesson
        complete_response = client.post("/lessons/test-lesson-001/complete")
        assert complete_response.status_code == 200
        assert "complete" in complete_response.text.lower()

    def test_progress_flow(self, client: TestClient) -> None:
        """Test progress flow: view progress -> view vocab -> view stats."""
        # View progress page
        progress_response = client.get("/progress/")
        assert progress_response.status_code == 200

        # View vocabulary partial
        vocab_response = client.get("/progress/vocabulary")
        assert vocab_response.status_code == 200

        # View stats summary
        stats_response = client.get("/progress/stats")
        assert stats_response.status_code == 200

    def test_full_page_responses(self, client: TestClient) -> None:
        """Test that full page endpoints return complete HTML."""
        full_pages = [
            "/lessons/",
            "/progress/",
        ]

        for endpoint in full_pages:
            response = client.get(endpoint)
            assert response.status_code == 200
            assert "<!DOCTYPE html>" in response.text
            assert "</html>" in response.text


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_word_id_zero(self, client: TestClient) -> None:
        """Test word ID of zero."""
        response = client.delete("/progress/vocabulary/0")
        assert response.status_code == 200

    def test_word_id_max_int(self, client: TestClient) -> None:
        """Test word ID at maximum integer boundary."""
        max_id = 2147483647  # Max 32-bit signed integer
        response = client.delete(f"/progress/vocabulary/{max_id}")
        assert response.status_code == 200

    def test_concurrent_lesson_completions(self, client: TestClient) -> None:
        """Test multiple lesson completions in sequence."""
        for _ in range(3):
            response = client.post("/lessons/test-lesson-001/complete")
            assert response.status_code == 200

    def test_repeated_vocabulary_deletion(self, client: TestClient) -> None:
        """Test deleting the same vocabulary word multiple times."""
        # This tests idempotency
        for _ in range(3):
            response = client.delete("/progress/vocabulary/1")
            assert response.status_code == 200
            assert response.text == ""


class TestHTTPMethods:
    """Tests for correct HTTP method handling."""

    def test_lessons_page_post_not_allowed(self, client: TestClient) -> None:
        """POST to /lessons/ should not be allowed (no route defined)."""
        response = client.post("/lessons/")
        assert response.status_code == 405  # Method Not Allowed

    def test_progress_page_post_not_allowed(self, client: TestClient) -> None:
        """POST to /progress/ should not be allowed."""
        response = client.post("/progress/")
        assert response.status_code == 405

    def test_complete_lesson_get_not_allowed(self, client: TestClient) -> None:
        """GET to /lessons/{lesson_id}/complete should not be allowed."""
        response = client.get("/lessons/test-lesson-001/complete")
        assert response.status_code == 405

    def test_vocabulary_post_not_allowed(self, client: TestClient) -> None:
        """POST to /progress/vocabulary should not be allowed."""
        response = client.post("/progress/vocabulary")
        assert response.status_code == 405

    def test_stats_post_not_allowed(self, client: TestClient) -> None:
        """POST to /progress/stats should not be allowed."""
        response = client.post("/progress/stats")
        assert response.status_code == 405
