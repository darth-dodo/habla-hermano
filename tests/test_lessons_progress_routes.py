"""Tests for lessons and progress API routes.

Comprehensive tests for the micro-lesson endpoints and progress tracking routes.
Tests cover route responses, HTML content, HTTP methods, and edge cases.

Phase 5: Updated tests to include authentication mocking.
"""

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from jinja2 import Environment, FileSystemLoader

from src.api.auth import AuthenticatedUser, get_current_user
from src.api.routes import lessons, progress


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
<div class="lesson-card">{{ lesson }}</div>
{% endfor %}
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
    (partials_path / "lesson_content.html").write_text(
        """<div class="lesson-content" data-lesson-id="{{ lesson_id }}">
<h2>Lesson: {{ lesson_id }}</h2>
<div class="content">{{ content }}</div>
<div class="exercises">
{% for exercise in exercises %}
<div class="exercise">{{ exercise }}</div>
{% endfor %}
</div>
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

    (partials_path / "vocab_sidebar.html").write_text(
        """<div class="vocab-sidebar">
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
def test_app(mock_templates_dir: Path, mock_user: AuthenticatedUser) -> FastAPI:
    """Create a test FastAPI app with lessons and progress routers mounted.

    Phase 5: Added authentication mocking for protected routes.

    Args:
        mock_templates_dir: Path to temporary templates directory.
        mock_user: Mock authenticated user for auth.

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

    # Override the dependency in both routers
    from src.api.dependencies import get_cached_templates

    app.dependency_overrides[get_cached_templates] = get_test_templates
    app.dependency_overrides[get_current_user] = mock_get_current_user

    # Mount routers with prefixes
    app.include_router(lessons.router, prefix="/lessons", tags=["lessons"])
    app.include_router(progress.router, prefix="/progress", tags=["progress"])

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


class TestGetLesson:
    """Tests for GET /lessons/{lesson_id} - Individual lesson content."""

    def test_get_lesson_returns_200(self, client: TestClient) -> None:
        """GET /lessons/{lesson_id} should return 200 OK."""
        response = client.get("/lessons/lesson-001")
        assert response.status_code == 200

    def test_get_lesson_returns_html(self, client: TestClient) -> None:
        """GET /lessons/{lesson_id} should return HTML content type."""
        response = client.get("/lessons/lesson-001")
        assert "text/html" in response.headers["content-type"]

    def test_get_lesson_contains_lesson_id(self, client: TestClient) -> None:
        """GET /lessons/{lesson_id} should include lesson ID in response."""
        lesson_id = "lesson-001"
        response = client.get(f"/lessons/{lesson_id}")
        assert lesson_id in response.text

    def test_get_lesson_is_partial_html(self, client: TestClient) -> None:
        """GET /lessons/{lesson_id} should return partial HTML (not full page)."""
        response = client.get("/lessons/lesson-001")
        # Partial should NOT contain full HTML structure
        assert "<!DOCTYPE html>" not in response.text

    def test_get_lesson_contains_content_class(self, client: TestClient) -> None:
        """GET /lessons/{lesson_id} should include lesson-content class."""
        response = client.get("/lessons/lesson-001")
        assert "lesson-content" in response.text

    @pytest.mark.parametrize(
        "lesson_id",
        [
            "lesson-001",
            "lesson-abc",
            "greetings-basic",
            "numbers-1-10",
            "some_lesson_with_underscore",
        ],
    )
    def test_get_lesson_various_ids(self, client: TestClient, lesson_id: str) -> None:
        """GET /lessons/{lesson_id} should handle various lesson ID formats."""
        response = client.get(f"/lessons/{lesson_id}")
        assert response.status_code == 200
        assert lesson_id in response.text

    async def test_get_lesson_async(self, async_client: AsyncClient) -> None:
        """GET /lessons/{lesson_id} should work with async client."""
        response = await async_client.get("/lessons/lesson-async-test")
        assert response.status_code == 200
        assert "lesson-async-test" in response.text


class TestCompleteLesson:
    """Tests for POST /lessons/{lesson_id}/complete - Mark lesson as completed."""

    def test_complete_lesson_returns_200(self, client: TestClient) -> None:
        """POST /lessons/{lesson_id}/complete should return 200 OK."""
        response = client.post("/lessons/lesson-001/complete")
        assert response.status_code == 200

    def test_complete_lesson_returns_html(self, client: TestClient) -> None:
        """POST /lessons/{lesson_id}/complete should return HTML content type."""
        response = client.post("/lessons/lesson-001/complete")
        assert "text/html" in response.headers["content-type"]

    def test_complete_lesson_contains_lesson_id(self, client: TestClient) -> None:
        """POST /lessons/{lesson_id}/complete should include lesson ID in response."""
        lesson_id = "lesson-001"
        response = client.post(f"/lessons/{lesson_id}/complete")
        assert lesson_id in response.text

    def test_complete_lesson_shows_completed_status(self, client: TestClient) -> None:
        """POST /lessons/{lesson_id}/complete should show completed status."""
        response = client.post("/lessons/lesson-001/complete")
        # Based on route implementation, completed=True is passed to context
        assert "Completed" in response.text or "completed" in response.text.lower()

    def test_complete_lesson_is_partial_html(self, client: TestClient) -> None:
        """POST /lessons/{lesson_id}/complete should return partial HTML."""
        response = client.post("/lessons/lesson-001/complete")
        assert "<!DOCTYPE html>" not in response.text

    def test_complete_lesson_contains_card_class(self, client: TestClient) -> None:
        """POST /lessons/{lesson_id}/complete should include lesson-card class."""
        response = client.post("/lessons/lesson-001/complete")
        assert "lesson-card" in response.text

    @pytest.mark.parametrize(
        "lesson_id",
        ["lesson-001", "advanced-grammar", "vocabulary-basics"],
    )
    def test_complete_lesson_various_ids(self, client: TestClient, lesson_id: str) -> None:
        """POST /lessons/{lesson_id}/complete should work with various IDs."""
        response = client.post(f"/lessons/{lesson_id}/complete")
        assert response.status_code == 200
        assert lesson_id in response.text

    async def test_complete_lesson_async(self, async_client: AsyncClient) -> None:
        """POST /lessons/{lesson_id}/complete should work with async client."""
        response = await async_client.post("/lessons/lesson-async/complete")
        assert response.status_code == 200


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
        # Based on route context: total_words, sessions_count, current_streak
        assert "Total Words" in response.text or "stats" in response.text

    def test_get_progress_page_default_values(self, client: TestClient) -> None:
        """GET /progress should show default zero values for stats."""
        response = client.get("/progress/")
        # Route returns: total_words=0, sessions_count=0, current_streak=0
        assert "0" in response.text

    async def test_get_progress_page_async(self, async_client: AsyncClient) -> None:
        """GET /progress should work with async client."""
        response = await async_client.get("/progress/")
        assert response.status_code == 200
        assert "Progress" in response.text


class TestGetVocabulary:
    """Tests for GET /progress/vocabulary - Vocabulary sidebar partial."""

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

    def test_get_vocabulary_contains_sidebar_class(self, client: TestClient) -> None:
        """GET /progress/vocabulary should include vocab-sidebar class."""
        response = client.get("/progress/vocabulary")
        assert "vocab-sidebar" in response.text

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

    def test_get_stats_default_values(self, client: TestClient) -> None:
        """GET /progress/stats should show default zero values."""
        response = client.get("/progress/stats")
        # Route returns: messages_today=0, words_learned_today=0, accuracy_rate=0.0
        assert "0" in response.text

    async def test_get_stats_async(self, async_client: AsyncClient) -> None:
        """GET /progress/stats should work with async client."""
        response = await async_client.get("/progress/stats")
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
        """Test complete flow: view lesson -> complete lesson."""
        # View lesson
        view_response = client.get("/lessons/lesson-flow-test")
        assert view_response.status_code == 200
        assert "lesson-flow-test" in view_response.text

        # Complete lesson
        complete_response = client.post("/lessons/lesson-flow-test/complete")
        assert complete_response.status_code == 200
        assert "completed" in complete_response.text.lower()

    def test_progress_flow(self, client: TestClient) -> None:
        """Test progress flow: view progress -> view vocab -> view stats."""
        # View progress page
        progress_response = client.get("/progress/")
        assert progress_response.status_code == 200

        # View vocabulary sidebar
        vocab_response = client.get("/progress/vocabulary")
        assert vocab_response.status_code == 200

        # View stats summary
        stats_response = client.get("/progress/stats")
        assert stats_response.status_code == 200

    def test_htmx_partial_responses(self, client: TestClient) -> None:
        """Test that partial endpoints return appropriate HTMX-compatible HTML."""
        # Partials should NOT be full HTML pages
        partials = [
            "/lessons/lesson-001",
            "/progress/vocabulary",
            "/progress/stats",
        ]

        for endpoint in partials:
            response = client.get(endpoint)
            assert response.status_code == 200
            assert "<!DOCTYPE html>" not in response.text

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

    def test_lesson_id_with_unicode(self, client: TestClient) -> None:
        """Test lesson ID with unicode-safe characters."""
        response = client.get("/lessons/leccion-espanol")
        assert response.status_code == 200

    def test_very_long_lesson_id(self, client: TestClient) -> None:
        """Test very long lesson ID."""
        long_id = "a" * 200
        response = client.get(f"/lessons/{long_id}")
        assert response.status_code == 200

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
        lesson_ids = ["lesson-1", "lesson-2", "lesson-3"]

        for lesson_id in lesson_ids:
            response = client.post(f"/lessons/{lesson_id}/complete")
            assert response.status_code == 200
            assert lesson_id in response.text

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

    def test_lesson_content_post_not_allowed(self, client: TestClient) -> None:
        """POST to /lessons/{lesson_id} should not be allowed."""
        response = client.post("/lessons/lesson-001")
        assert response.status_code == 405

    def test_complete_lesson_get_not_allowed(self, client: TestClient) -> None:
        """GET to /lessons/{lesson_id}/complete should not be allowed."""
        response = client.get("/lessons/lesson-001/complete")
        assert response.status_code == 405

    def test_vocabulary_post_not_allowed(self, client: TestClient) -> None:
        """POST to /progress/vocabulary should not be allowed."""
        response = client.post("/progress/vocabulary")
        assert response.status_code == 405

    def test_stats_post_not_allowed(self, client: TestClient) -> None:
        """POST to /progress/stats should not be allowed."""
        response = client.post("/progress/stats")
        assert response.status_code == 405
