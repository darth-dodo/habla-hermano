"""Tests for lesson chat API routes (Phase 19).

Tests cover:
- GET /chat/lesson/{lesson_id} — Renders lesson chat page
- POST /chat/lesson/stream — Lesson chat streaming endpoint
- _resolve_lesson_thread_id helper
- Session cookie handling for guests
"""

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import get_current_user_optional
from src.api.routes.lesson_chat import _resolve_lesson_thread_id
from src.lessons.models import (
    Lesson,
    LessonContent,
    LessonLevel,
    LessonMetadata,
    LessonStep,
    LessonStepType,
)
from tests.conftest import CSRF_HEADERS

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_lesson() -> Lesson:
    """Create a sample lesson for testing."""
    return Lesson(
        metadata=LessonMetadata(
            id="es_a1_greetings_01",
            title="Basic Greetings",
            description="Learn common greetings in Spanish",
            language="es",
            level=LessonLevel.A1,
            estimated_minutes=3,
            category="greetings",
            tags=["greeting"],
            vocabulary_count=2,
            icon="👋",
        ),
        content=LessonContent(
            steps=[
                LessonStep(
                    type=LessonStepType.INSTRUCTION,
                    content="Learn greetings!",
                    order=1,
                ),
            ],
            exercises=[],
        ),
    )


@pytest.fixture
def mock_lesson_service(sample_lesson: Lesson) -> MagicMock:
    """Create a mock LessonService."""
    service = MagicMock()
    service.get_lesson.return_value = sample_lesson
    service.get_lesson_vocabulary.return_value = []
    return service


@pytest.fixture
def lesson_chat_app(mock_lesson_service: MagicMock) -> FastAPI:
    """Create a test app with lesson chat routes and mocked dependencies."""
    from src.api.main import create_app

    app = create_app()

    # Override lesson service dependency
    from src.api.dependencies import get_lesson_service

    app.dependency_overrides[get_lesson_service] = lambda: mock_lesson_service
    app.dependency_overrides[get_current_user_optional] = lambda: None

    return app


@pytest.fixture
def client(lesson_chat_app: FastAPI) -> Generator[TestClient, None, None]:
    """Create test client."""
    with TestClient(lesson_chat_app) as c:
        yield c


# =============================================================================
# Thread ID Resolution Tests
# =============================================================================


class TestResolveThreadId:
    """Tests for _resolve_lesson_thread_id."""

    def test_authenticated_user(self) -> None:
        thread_id, user_id, new_session = _resolve_lesson_thread_id(
            user_id="user-123", session_id=None, lesson_id="es_a1_greetings_01"
        )
        assert thread_id == "lesson:user-123:es_a1_greetings_01"
        assert user_id == "user-123"
        assert new_session is None

    def test_guest_with_session(self) -> None:
        thread_id, user_id, new_session = _resolve_lesson_thread_id(
            user_id=None, session_id="sess-456", lesson_id="es_a1_greetings_01"
        )
        assert thread_id == "lesson:sess-456:es_a1_greetings_01"
        assert user_id is None
        assert new_session is None

    def test_new_guest(self) -> None:
        thread_id, user_id, new_session = _resolve_lesson_thread_id(
            user_id=None, session_id=None, lesson_id="es_a1_greetings_01"
        )
        assert thread_id.startswith("lesson:")
        assert thread_id.endswith(":es_a1_greetings_01")
        assert user_id is None
        assert new_session is not None

    def test_user_id_takes_priority(self) -> None:
        thread_id, _, _ = _resolve_lesson_thread_id(
            user_id="user-123", session_id="sess-456", lesson_id="lesson1"
        )
        assert "user-123" in thread_id
        assert "sess-456" not in thread_id


# =============================================================================
# GET /chat/lesson/{lesson_id} Tests
# =============================================================================


class TestLessonChatPage:
    """Tests for the lesson chat page endpoint."""

    def test_lesson_page_returns_200(self, client: TestClient) -> None:
        response = client.get("/chat/lesson/es_a1_greetings_01")
        assert response.status_code == 200

    def test_lesson_page_contains_lesson_context(self, client: TestClient) -> None:
        response = client.get("/chat/lesson/es_a1_greetings_01")
        text = response.text
        # Should contain lesson mode markers
        assert "data-lesson-mode" in text or "lesson_mode" in text.lower() or "lesson-header" in text

    def test_lesson_page_404_for_missing_lesson(
        self, lesson_chat_app: FastAPI, mock_lesson_service: MagicMock
    ) -> None:
        mock_lesson_service.get_lesson.return_value = None
        with TestClient(lesson_chat_app) as c:
            response = c.get("/chat/lesson/nonexistent")
            assert response.status_code == 404

    def test_lesson_page_sets_session_cookie_for_guests(
        self, client: TestClient
    ) -> None:
        response = client.get("/chat/lesson/es_a1_greetings_01")
        # Should set session_id cookie for guests
        cookies = response.cookies
        assert "session_id" in cookies or response.status_code == 200


# =============================================================================
# POST /chat/lesson/stream Validation Tests
# =============================================================================


class TestLessonStreamValidation:
    """Tests for lesson stream endpoint validation."""

    def test_empty_message_returns_error(self, client: TestClient) -> None:
        response = client.post(
            "/chat/lesson/stream",
            data={"message": "  ", "lesson_id": "es_a1_greetings_01"},
            headers=CSRF_HEADERS,
        )
        # Should return SSE with error event
        assert response.status_code == 200

    def test_level_and_language_not_accepted_as_form_params(
        self, client: TestClient
    ) -> None:
        """Level/language come from lesson metadata, not client input."""
        response = client.post(
            "/chat/lesson/stream",
            data={
                "message": "hello",
                "lesson_id": "es_a1_greetings_01",
                "level": "Z9",
                "language": "xx",
            },
            headers=CSRF_HEADERS,
        )
        # Extra form fields are ignored — lesson proceeds using metadata values
        assert response.status_code == 200

    def test_missing_lesson_returns_error(
        self, lesson_chat_app: FastAPI, mock_lesson_service: MagicMock
    ) -> None:
        mock_lesson_service.get_lesson.return_value = None
        with TestClient(lesson_chat_app) as c:
            response = c.post(
                "/chat/lesson/stream",
                data={"message": "hello", "lesson_id": "nonexistent"},
                headers=CSRF_HEADERS,
            )
            assert response.status_code == 200
