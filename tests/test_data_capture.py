"""Integration tests for data capture in chat and lesson routes.

Phase 7: Tests that vocabulary and session data are captured for any user
with identity (authenticated users, returning guests with cookies, or new
guests via generated session IDs), and that capture errors do not break responses.
"""

from pathlib import Path
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader
from langchain_core.messages import AIMessage, HumanMessage

from src.api.auth import (
    AuthenticatedUser,
    get_current_user_optional,
)
from src.api.dependencies import get_cached_templates
from src.api.routes import chat, lessons
from src.lessons.models import (
    Lesson,
    LessonContent,
    LessonLevel,
    LessonMetadata,
    LessonStep,
    LessonStepType,
)
from src.lessons.service import get_lesson_service

# =============================================================================
# Fixtures
# =============================================================================


class MockJinja2Templates:
    """Mock Jinja2Templates for testing without actual template files."""

    def __init__(self, directory: str) -> None:
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
        from fastapi.responses import HTMLResponse

        if context is None:
            context = {}
        template = self.env.get_template(name)
        content = template.render(**context)
        return HTMLResponse(content=content)


@pytest.fixture
def mock_templates_dir(tmp_path: Path) -> Path:
    """Create temporary directory with stub templates for testing."""
    templates_path = tmp_path / "templates"
    templates_path.mkdir()
    partials_path = templates_path / "partials"
    partials_path.mkdir()

    (templates_path / "chat.html").write_text(
        """<!DOCTYPE html><html><body><h1>Chat</h1></body></html>"""
    )

    (partials_path / "message_pair.html").write_text(
        """<div class="message-pair">
<div class="user-msg">{{ user_message }}</div>
<div class="ai-msg">{{ ai_response }}</div>
</div>"""
    )

    (partials_path / "lesson_complete.html").write_text(
        """<div class="lesson-complete">
<h2>Lesson Complete!</h2>
<p>Score: {{ score }}%</p>
<p>Vocabulary: {{ vocab_count }} words</p>
</div>"""
    )

    return templates_path


@pytest.fixture
def mock_user() -> AuthenticatedUser:
    """Create a mock authenticated user for testing."""
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
                    content="Welcome!",
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
    service.get_lesson.return_value = sample_lesson
    service.get_lesson_vocabulary.return_value = [
        {"word": "hola", "translation": "hello"},
    ]
    return service


@pytest.fixture
def graph_result_with_vocab() -> dict[str, Any]:
    """Graph result that includes new vocabulary."""
    return {
        "messages": [
            HumanMessage(content="Hola"),
            AIMessage(content="Hola! Como estas?"),
        ],
        "level": "A1",
        "language": "es",
        "grammar_feedback": [],
        "new_vocabulary": [
            {"word": "hola", "translation": "hello", "part_of_speech": "interjection"},
            {"word": "como", "translation": "how", "part_of_speech": "adverb"},
        ],
        "scaffolding": {},
    }


@pytest.fixture
def graph_result_without_vocab() -> dict[str, Any]:
    """Graph result with no new vocabulary."""
    return {
        "messages": [
            HumanMessage(content="Hello"),
            AIMessage(content="Hola!"),
        ],
        "level": "A1",
        "language": "es",
        "grammar_feedback": [],
        "new_vocabulary": [],
        "scaffolding": {},
    }


# =============================================================================
# Chat Data Capture Tests
# =============================================================================


class TestChatDataCaptureAuthenticated:
    """Tests that chat route captures vocab data for authenticated users."""

    def test_chat_captures_vocab_for_authenticated_user(
        self,
        mock_templates_dir: Path,
        mock_user: AuthenticatedUser,
        graph_result_with_vocab: dict,
    ) -> None:
        """POST /chat should call ProgressService.record_chat_activity for auth users."""
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: mock_user

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=graph_result_with_vocab)

        class MockCheckpointerCtx:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, *args):
                pass

        with (
            patch("src.api.routes.chat.build_graph", return_value=mock_graph),
            patch("src.api.routes.chat.get_checkpointer", return_value=MockCheckpointerCtx()),
            patch("src.api.routes.chat.ProgressService") as MockProgressService,
        ):
            mock_service_instance = MagicMock()
            MockProgressService.return_value = mock_service_instance

            app.include_router(chat.router)
            client = TestClient(app)

            response = client.post(
                "/chat",
                data={"message": "Hola", "level": "A1", "language": "es"},
            )

            assert response.status_code == 200
            MockProgressService.assert_called_once_with(mock_user.id, client=None)
            mock_service_instance.record_chat_activity.assert_called_once_with(
                language="es",
                level="A1",
                new_vocab=graph_result_with_vocab["new_vocabulary"],
            )

    def test_chat_skips_capture_when_no_vocab(
        self,
        mock_templates_dir: Path,
        mock_user: AuthenticatedUser,
        graph_result_without_vocab: dict,
    ) -> None:
        """POST /chat should NOT call ProgressService when new_vocabulary is empty."""
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: mock_user

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=graph_result_without_vocab)

        class MockCheckpointerCtx:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, *args):
                pass

        with (
            patch("src.api.routes.chat.build_graph", return_value=mock_graph),
            patch("src.api.routes.chat.get_checkpointer", return_value=MockCheckpointerCtx()),
            patch("src.api.routes.chat.ProgressService") as MockProgressService,
        ):
            app.include_router(chat.router)
            client = TestClient(app)

            response = client.post(
                "/chat",
                data={"message": "Hello", "level": "A1", "language": "es"},
            )

            assert response.status_code == 200
            MockProgressService.assert_not_called()


class TestChatDataCaptureGuest:
    """Tests that chat route captures data for guest users via session ID."""

    def test_chat_captures_vocab_for_guest_user(
        self,
        mock_templates_dir: Path,
        graph_result_with_vocab: dict,
    ) -> None:
        """POST /chat should call ProgressService for guest users with a new session ID."""
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        # Return None for guest user
        app.dependency_overrides[get_current_user_optional] = lambda: None

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=graph_result_with_vocab)

        class MockCheckpointerCtx:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, *args):
                pass

        mock_admin_client = MagicMock()

        with (
            patch("src.api.routes.chat.build_graph", return_value=mock_graph),
            patch("src.api.routes.chat.get_checkpointer", return_value=MockCheckpointerCtx()),
            patch("src.api.routes.chat.ProgressService") as MockProgressService,
            patch("src.api.routes.chat.get_supabase_admin", return_value=mock_admin_client),
        ):
            mock_service_instance = MagicMock()
            MockProgressService.return_value = mock_service_instance

            app.include_router(chat.router)
            client = TestClient(app)

            response = client.post(
                "/chat",
                data={"message": "Hola", "level": "A1", "language": "es"},
            )

            assert response.status_code == 200
            # Guest gets a new_session_id (UUID), so ProgressService is called
            MockProgressService.assert_called_once_with(ANY, client=mock_admin_client)
            mock_service_instance.record_chat_activity.assert_called_once_with(
                language="es",
                level="A1",
                new_vocab=graph_result_with_vocab["new_vocabulary"],
            )


class TestChatDataCaptureErrorResilience:
    """Tests that data capture errors do not break the chat response."""

    def test_chat_returns_response_even_if_capture_fails(
        self,
        mock_templates_dir: Path,
        mock_user: AuthenticatedUser,
        graph_result_with_vocab: dict,
    ) -> None:
        """POST /chat should still return 200 even if ProgressService raises."""
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: mock_user

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=graph_result_with_vocab)

        class MockCheckpointerCtx:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, *args):
                pass

        with (
            patch("src.api.routes.chat.build_graph", return_value=mock_graph),
            patch("src.api.routes.chat.get_checkpointer", return_value=MockCheckpointerCtx()),
            patch("src.api.routes.chat.ProgressService") as MockProgressService,
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.record_chat_activity.side_effect = RuntimeError(
                "DB connection failed"
            )
            MockProgressService.return_value = mock_service_instance

            app.include_router(chat.router)
            client = TestClient(app)

            response = client.post(
                "/chat",
                data={"message": "Hola", "level": "A1", "language": "es"},
            )

            # Response should succeed despite capture failure
            assert response.status_code == 200
            assert "Hola" in response.text


# =============================================================================
# Lesson Completion Persistence Tests
# =============================================================================


class TestLessonCompletionPersistenceAuthenticated:
    """Tests that lesson completion is persisted for authenticated users."""

    def test_complete_lesson_persists_for_authenticated_user(
        self,
        mock_templates_dir: Path,
        mock_user: AuthenticatedUser,
        mock_lesson_service: MagicMock,
    ) -> None:
        """POST /lessons/{id}/complete should call LessonProgressRepository for auth users."""
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: mock_user
        app.dependency_overrides[get_lesson_service] = lambda: mock_lesson_service

        with patch("src.api.routes.lessons.LessonProgressRepository") as MockRepo:
            mock_repo_instance = MagicMock()
            MockRepo.return_value = mock_repo_instance

            app.include_router(lessons.router, prefix="/lessons")
            client = TestClient(app)

            response = client.post(
                "/lessons/test-lesson-001/complete",
                data={"score": "85"},
            )

            assert response.status_code == 200
            MockRepo.assert_called_once_with(mock_user.id, client=None)
            mock_repo_instance.complete_lesson.assert_called_once_with("test-lesson-001", score=85)

    def test_complete_lesson_persists_default_score(
        self,
        mock_templates_dir: Path,
        mock_user: AuthenticatedUser,
        mock_lesson_service: MagicMock,
    ) -> None:
        """POST /lessons/{id}/complete without score should use default score 100."""
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: mock_user
        app.dependency_overrides[get_lesson_service] = lambda: mock_lesson_service

        with patch("src.api.routes.lessons.LessonProgressRepository") as MockRepo:
            mock_repo_instance = MagicMock()
            MockRepo.return_value = mock_repo_instance

            app.include_router(lessons.router, prefix="/lessons")
            client = TestClient(app)

            response = client.post("/lessons/test-lesson-001/complete")

            assert response.status_code == 200
            mock_repo_instance.complete_lesson.assert_called_once_with("test-lesson-001", score=100)


class TestLessonCompletionPersistenceGuest:
    """Tests that lesson completion is persisted for guest users via session ID."""

    def test_complete_lesson_persists_for_guest(
        self,
        mock_templates_dir: Path,
        mock_lesson_service: MagicMock,
    ) -> None:
        """POST /lessons/{id}/complete should call LessonProgressRepository for guests."""
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        # Return None for guest user
        app.dependency_overrides[get_current_user_optional] = lambda: None
        app.dependency_overrides[get_lesson_service] = lambda: mock_lesson_service

        mock_admin_client = MagicMock()

        with (
            patch("src.api.routes.lessons.LessonProgressRepository") as MockRepo,
            patch("src.api.routes.lessons.get_supabase_admin", return_value=mock_admin_client),
        ):
            mock_repo_instance = MagicMock()
            MockRepo.return_value = mock_repo_instance

            app.include_router(lessons.router, prefix="/lessons")
            client = TestClient(app)

            response = client.post("/lessons/test-lesson-001/complete")

            assert response.status_code == 200
            # Guest gets a new_session_id (UUID), so repo is called
            MockRepo.assert_called_once_with(ANY, client=mock_admin_client)
            mock_repo_instance.complete_lesson.assert_called_once_with("test-lesson-001", score=100)


class TestLessonCompletionErrorResilience:
    """Tests that persistence errors do not break lesson completion responses."""

    def test_complete_lesson_returns_response_even_if_persistence_fails(
        self,
        mock_templates_dir: Path,
        mock_user: AuthenticatedUser,
        mock_lesson_service: MagicMock,
    ) -> None:
        """POST /lessons/{id}/complete should still return 200 if persistence raises."""
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: mock_user
        app.dependency_overrides[get_lesson_service] = lambda: mock_lesson_service

        with patch("src.api.routes.lessons.LessonProgressRepository") as MockRepo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.complete_lesson.side_effect = RuntimeError("DB connection failed")
            MockRepo.return_value = mock_repo_instance

            app.include_router(lessons.router, prefix="/lessons")
            client = TestClient(app)

            response = client.post("/lessons/test-lesson-001/complete")

            # Response should succeed despite persistence failure
            assert response.status_code == 200
            assert "Complete" in response.text

    def test_complete_lesson_returns_response_if_repo_init_fails(
        self,
        mock_templates_dir: Path,
        mock_user: AuthenticatedUser,
        mock_lesson_service: MagicMock,
    ) -> None:
        """POST /lessons/{id}/complete should still return 200 if repo constructor raises."""
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: mock_user
        app.dependency_overrides[get_lesson_service] = lambda: mock_lesson_service

        with patch("src.api.routes.lessons.LessonProgressRepository") as MockRepo:
            MockRepo.side_effect = RuntimeError("Cannot connect to Supabase")

            app.include_router(lessons.router, prefix="/lessons")
            client = TestClient(app)

            response = client.post("/lessons/test-lesson-001/complete")

            # Response should succeed despite persistence failure
            assert response.status_code == 200
            assert "Complete" in response.text
