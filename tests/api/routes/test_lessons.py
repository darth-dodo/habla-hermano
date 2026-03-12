"""Tests for lesson API routes.

Phase 23: Stripped to lesson list route only. Old player routes removed.
"""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import AuthenticatedUser, get_current_user
from src.lessons.models import (
    Lesson,
    LessonContent,
    LessonLevel,
    LessonMetadata,
    LessonStep,
    LessonStepType,
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
            ],
            exercises=[],
        ),
    )


@pytest.fixture
def mock_lesson_service(sample_lesson: Lesson) -> MagicMock:
    """Create mock lesson service."""
    service = MagicMock()
    service.get_lessons_metadata.return_value = [sample_lesson.metadata]
    return service


@pytest.fixture
def app(
    mock_user: AuthenticatedUser,
    mock_lesson_service: MagicMock,
    tmp_path: Path,
) -> Generator[FastAPI, None, None]:
    """Create test FastAPI app with mocked dependencies."""
    from fastapi import FastAPI
    from fastapi.templating import Jinja2Templates

    # Create minimal templates
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

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

    yield app


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Create test client."""
    with TestClient(app) as c:
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
# Edge Cases
# =============================================================================


class TestLessonEdgeCases:
    """Edge case tests for lesson routes."""

    def test_empty_lessons_list(self, client: TestClient, mock_lesson_service: MagicMock) -> None:
        """Empty lessons list should render correctly."""
        mock_lesson_service.get_lessons_metadata.return_value = []

        response = client.get("/lessons/")
        assert response.status_code == 200


# =============================================================================
# Authentication Tests
# =============================================================================


class TestLessonAuthentication:
    """Tests for authentication on lesson routes (guest access allowed)."""

    def test_lessons_allow_guest_access(self, client: TestClient) -> None:
        """GET /lessons should allow guest access (OptionalUserDep)."""
        response = client.get("/lessons/")
        assert response.status_code == 200
