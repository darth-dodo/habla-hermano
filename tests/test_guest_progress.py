"""Integration tests for end-to-end guest progress tracking flow.

Verifies that guest users (identified by session_id cookie) can have their
vocabulary captured during chat, lesson completions persisted, and progress
data retrieved across all progress endpoints. Each test creates its own
FastAPI app with appropriate dependency overrides and patches to isolate
the guest flow without touching Supabase or real services.
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader
from langchain_core.messages import AIMessage, HumanMessage

from src.api.auth import get_current_user_optional
from src.api.dependencies import get_cached_templates
from src.api.routes import chat, lessons, progress
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

    (templates_path / "progress.html").write_text(
        """<!DOCTYPE html><html><body>
<h1>Progress</h1>
<p>Words: {{ total_words }}</p>
<p>Sessions: {{ sessions_count }}</p>
<p>Streak: {{ current_streak }}</p>
<p>Lessons: {{ lessons_completed }}</p>
</body></html>"""
    )

    (partials_path / "progress_vocab.html").write_text(
        """<div class="vocabulary">
{% for word in vocabulary %}
<span>{{ word }}</span>
{% endfor %}
</div>"""
    )

    (partials_path / "stats_summary.html").write_text(
        """<div class="stats">
<p>Words: {{ total_words }}</p>
<p>Sessions: {{ total_sessions }}</p>
<p>Streak: {{ current_streak }}</p>
</div>"""
    )

    return templates_path


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


# =============================================================================
# Guest Chat Capture Tests
# =============================================================================


class TestGuestChatCapture:
    """Tests that chat route captures vocabulary data for guest users."""

    def test_guest_chat_captures_vocab_with_existing_session(
        self,
        mock_templates_dir: Path,
        graph_result_with_vocab: dict[str, Any],
    ) -> None:
        """POST /chat with session_id cookie and vocab in response captures data.

        When a guest with an existing session_id cookie sends a chat message
        that produces new vocabulary, ProgressService should be called with
        the session_id and the admin Supabase client.
        """
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: None

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=graph_result_with_vocab)

        class MockCheckpointerCtx:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, *args):
                pass

        mock_admin_client = MagicMock(name="admin-client")

        with (
            patch("src.api.routes.chat.build_graph", return_value=mock_graph),
            patch(
                "src.api.routes.chat.get_checkpointer",
                return_value=MockCheckpointerCtx(),
            ),
            patch("src.api.routes.chat.ProgressService") as MockProgressService,
            patch(
                "src.api.routes.chat.get_supabase_admin",
                return_value=mock_admin_client,
            ),
        ):
            mock_service_instance = MagicMock()
            MockProgressService.return_value = mock_service_instance

            app.include_router(chat.router)
            client = TestClient(app)
            client.cookies.set("session_id", "test-guest-session-123")

            response = client.post(
                "/chat",
                data={"message": "Hola", "level": "A1", "language": "es"},
            )

            assert response.status_code == 200
            MockProgressService.assert_called_once_with(
                "test-guest-session-123", client=mock_admin_client
            )
            mock_service_instance.record_chat_activity.assert_called_once_with(
                language="es",
                level="A1",
                new_vocab=graph_result_with_vocab["new_vocabulary"],
            )

    def test_guest_chat_creates_session_and_captures(
        self,
        mock_templates_dir: Path,
        graph_result_with_vocab: dict[str, Any],
    ) -> None:
        """POST /chat without cookie generates a new session_id and captures vocab.

        A brand-new guest (no session_id cookie) should get a UUID assigned,
        ProgressService should be called with that UUID and admin client,
        and the session_id cookie should be set on the response.
        """
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: None

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=graph_result_with_vocab)

        class MockCheckpointerCtx:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, *args):
                pass

        mock_admin_client = MagicMock(name="admin-client")

        with (
            patch("src.api.routes.chat.build_graph", return_value=mock_graph),
            patch(
                "src.api.routes.chat.get_checkpointer",
                return_value=MockCheckpointerCtx(),
            ),
            patch("src.api.routes.chat.ProgressService") as MockProgressService,
            patch(
                "src.api.routes.chat.get_supabase_admin",
                return_value=mock_admin_client,
            ),
        ):
            mock_service_instance = MagicMock()
            MockProgressService.return_value = mock_service_instance

            app.include_router(chat.router)
            client = TestClient(app)
            # No session_id cookie set

            response = client.post(
                "/chat",
                data={"message": "Hola", "level": "A1", "language": "es"},
            )

            assert response.status_code == 200

            # ProgressService should have been called with a new UUID and admin client
            MockProgressService.assert_called_once()
            call_args = MockProgressService.call_args
            new_uuid = call_args[0][0]
            assert isinstance(new_uuid, str)
            assert len(new_uuid) == 36  # UUID format
            assert call_args[1]["client"] is mock_admin_client

            mock_service_instance.record_chat_activity.assert_called_once_with(
                language="es",
                level="A1",
                new_vocab=graph_result_with_vocab["new_vocabulary"],
            )

            # Verify session_id cookie is set on the response
            set_cookie_header = response.headers.get("set-cookie", "")
            assert "session_id=" in set_cookie_header


# =============================================================================
# Guest Lesson Completion Tests
# =============================================================================


class TestGuestLessonCompletion:
    """Tests that lesson completion is persisted for guest users."""

    def test_guest_lesson_complete_with_session_cookie(
        self,
        mock_templates_dir: Path,
        mock_lesson_service: MagicMock,
    ) -> None:
        """POST /lessons/{id}/complete with session_id cookie persists completion.

        Guest with an existing session_id cookie completing a lesson should
        trigger LessonProgressRepository with the session_id and admin client.
        """
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: None
        app.dependency_overrides[get_lesson_service] = lambda: mock_lesson_service

        mock_admin_client = MagicMock(name="admin-client")

        with (
            patch("src.api.routes.lessons.LessonProgressRepository") as MockRepo,
            patch(
                "src.api.routes.lessons.get_supabase_admin",
                return_value=mock_admin_client,
            ),
        ):
            mock_repo_instance = MagicMock()
            MockRepo.return_value = mock_repo_instance

            app.include_router(lessons.router, prefix="/lessons")
            client = TestClient(app)
            client.cookies.set("session_id", "test-guest-session-123")

            response = client.post(
                "/lessons/test-lesson-001/complete",
                data={"score": "85"},
            )

            assert response.status_code == 200
            MockRepo.assert_called_once_with("test-guest-session-123", client=mock_admin_client)
            mock_repo_instance.complete_lesson.assert_called_once_with("test-lesson-001", score=85)

    def test_guest_lesson_complete_creates_session(
        self,
        mock_templates_dir: Path,
        mock_lesson_service: MagicMock,
    ) -> None:
        """POST /lessons/{id}/complete without cookie creates a session and persists.

        A first-time guest with no session_id cookie completing a lesson should
        get a new UUID assigned, LessonProgressRepository called with admin
        client, and the session_id cookie set on the response.
        """
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: None
        app.dependency_overrides[get_lesson_service] = lambda: mock_lesson_service

        mock_admin_client = MagicMock(name="admin-client")

        with (
            patch("src.api.routes.lessons.LessonProgressRepository") as MockRepo,
            patch(
                "src.api.routes.lessons.get_supabase_admin",
                return_value=mock_admin_client,
            ),
        ):
            mock_repo_instance = MagicMock()
            MockRepo.return_value = mock_repo_instance

            app.include_router(lessons.router, prefix="/lessons")
            client = TestClient(app)
            # No session_id cookie set

            response = client.post("/lessons/test-lesson-001/complete")

            assert response.status_code == 200

            # LessonProgressRepository should have been called with a new UUID
            MockRepo.assert_called_once()
            call_args = MockRepo.call_args
            new_uuid = call_args[0][0]
            assert isinstance(new_uuid, str)
            assert len(new_uuid) == 36  # UUID format
            assert call_args[1]["client"] is mock_admin_client

            mock_repo_instance.complete_lesson.assert_called_once()

            # Verify session_id cookie is set on the response
            set_cookie_header = response.headers.get("set-cookie", "")
            assert "session_id=" in set_cookie_header

    def test_guest_lesson_complete_default_score(
        self,
        mock_templates_dir: Path,
        mock_lesson_service: MagicMock,
    ) -> None:
        """POST /lessons/{id}/complete without score param uses default 100.

        When no score form field is submitted, the endpoint should default
        to score=100.
        """
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: None
        app.dependency_overrides[get_lesson_service] = lambda: mock_lesson_service

        mock_admin_client = MagicMock(name="admin-client")

        with (
            patch("src.api.routes.lessons.LessonProgressRepository") as MockRepo,
            patch(
                "src.api.routes.lessons.get_supabase_admin",
                return_value=mock_admin_client,
            ),
        ):
            mock_repo_instance = MagicMock()
            MockRepo.return_value = mock_repo_instance

            app.include_router(lessons.router, prefix="/lessons")
            client = TestClient(app)
            client.cookies.set("session_id", "test-guest-session-123")

            response = client.post("/lessons/test-lesson-001/complete")

            assert response.status_code == 200
            mock_repo_instance.complete_lesson.assert_called_once_with("test-lesson-001", score=100)


# =============================================================================
# Guest Progress Access Tests
# =============================================================================


class TestGuestProgressAccess:
    """Tests that progress routes serve data for guest users and handle no-session."""

    def test_guest_progress_page_with_session(
        self,
        mock_templates_dir: Path,
    ) -> None:
        """GET /progress/ with session_id cookie returns 200 with real stats.

        A guest with a session_id cookie should have ProgressService called
        with their session_id and admin client, returning dashboard stats.
        """
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: None

        mock_admin_client = MagicMock(name="admin-client")
        mock_stats = DashboardStats(
            total_words=10,
            total_sessions=3,
            lessons_completed=2,
            current_streak=1,
            accuracy_rate=85.0,
            words_learned_today=5,
            messages_today=12,
        )

        with (
            patch("src.api.routes.progress.ProgressService") as MockProgressService,
            patch(
                "src.api.routes.progress.get_supabase_admin",
                return_value=mock_admin_client,
            ),
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.get_dashboard_stats.return_value = mock_stats
            MockProgressService.return_value = mock_service_instance

            app.include_router(progress.router, prefix="/progress")
            client = TestClient(app)
            client.cookies.set("session_id", "test-guest-session-123")

            response = client.get("/progress/")

            assert response.status_code == 200
            MockProgressService.assert_called_once_with(
                "test-guest-session-123", client=mock_admin_client
            )
            mock_service_instance.get_dashboard_stats.assert_called_once()
            assert "Words: 10" in response.text

    def test_guest_progress_page_no_session(
        self,
        mock_templates_dir: Path,
    ) -> None:
        """GET /progress/ without cookie returns 200 with zeroed empty state.

        A guest with no session_id cookie should receive an empty progress
        page with zero values and no ProgressService call.
        """
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: None

        with (
            patch("src.api.routes.progress.ProgressService") as MockProgressService,
            patch("src.api.routes.progress.get_supabase_admin"),
        ):
            app.include_router(progress.router, prefix="/progress")
            client = TestClient(app)

            response = client.get("/progress/")

            assert response.status_code == 200
            MockProgressService.assert_not_called()
            assert "Words: 0" in response.text

    def test_guest_vocabulary_with_session(
        self,
        mock_templates_dir: Path,
    ) -> None:
        """GET /progress/vocabulary with session_id cookie calls VocabularyRepository.

        A guest with a session cookie should have VocabularyRepository
        instantiated with the session_id and admin client.
        """
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: None

        mock_admin_client = MagicMock(name="admin-client")

        with (
            patch("src.api.routes.progress.VocabularyRepository") as MockVocabRepo,
            patch(
                "src.api.routes.progress.get_supabase_admin",
                return_value=mock_admin_client,
            ),
        ):
            mock_repo_instance = MagicMock()
            mock_repo_instance.get_all.return_value = []
            MockVocabRepo.return_value = mock_repo_instance

            app.include_router(progress.router, prefix="/progress")
            client = TestClient(app)
            client.cookies.set("session_id", "test-guest-session-123")

            response = client.get("/progress/vocabulary")

            assert response.status_code == 200
            MockVocabRepo.assert_called_once_with(
                "test-guest-session-123", client=mock_admin_client
            )
            mock_repo_instance.get_all.assert_called_once()

    def test_guest_vocabulary_no_session(
        self,
        mock_templates_dir: Path,
    ) -> None:
        """GET /progress/vocabulary without cookie returns 200 with empty list.

        No session_id cookie should skip VocabularyRepository and return
        an empty vocabulary template.
        """
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: None

        with (
            patch("src.api.routes.progress.VocabularyRepository") as MockVocabRepo,
            patch("src.api.routes.progress.get_supabase_admin"),
        ):
            app.include_router(progress.router, prefix="/progress")
            client = TestClient(app)

            response = client.get("/progress/vocabulary")

            assert response.status_code == 200
            MockVocabRepo.assert_not_called()

    def test_guest_stats_with_session(
        self,
        mock_templates_dir: Path,
    ) -> None:
        """GET /progress/stats with cookie calls ProgressService for stats.

        A guest with a session_id cookie should trigger ProgressService
        with the session_id and admin client to fetch dashboard stats.
        """
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: None

        mock_admin_client = MagicMock(name="admin-client")
        mock_stats = DashboardStats(
            total_words=5,
            total_sessions=2,
            lessons_completed=1,
            current_streak=1,
            accuracy_rate=90.0,
            words_learned_today=3,
            messages_today=8,
        )

        with (
            patch("src.api.routes.progress.ProgressService") as MockProgressService,
            patch(
                "src.api.routes.progress.get_supabase_admin",
                return_value=mock_admin_client,
            ),
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.get_dashboard_stats.return_value = mock_stats
            MockProgressService.return_value = mock_service_instance

            app.include_router(progress.router, prefix="/progress")
            client = TestClient(app)
            client.cookies.set("session_id", "test-guest-session-123")

            response = client.get("/progress/stats")

            assert response.status_code == 200
            MockProgressService.assert_called_once_with(
                "test-guest-session-123", client=mock_admin_client
            )
            mock_service_instance.get_dashboard_stats.assert_called_once()

    def test_guest_chart_data_no_session(self) -> None:
        """GET /progress/chart-data without cookie returns empty JSON.

        No session_id cookie should return an empty chart data response
        without calling ProgressService.
        """
        app = FastAPI()

        app.dependency_overrides[get_current_user_optional] = lambda: None

        with (
            patch("src.api.routes.progress.ProgressService") as MockProgressService,
            patch("src.api.routes.progress.get_supabase_admin"),
        ):
            app.include_router(progress.router, prefix="/progress")
            client = TestClient(app)

            response = client.get("/progress/chart-data")

            assert response.status_code == 200
            MockProgressService.assert_not_called()
            data = response.json()
            assert data == {"vocab_growth": [], "accuracy_trend": []}

    def test_guest_delete_vocab_with_session(self) -> None:
        """DELETE /progress/vocabulary/1 with cookie calls VocabularyRepository.delete.

        A guest with a session_id cookie should be able to delete a
        vocabulary word through VocabularyRepository.
        """
        app = FastAPI()

        app.dependency_overrides[get_current_user_optional] = lambda: None

        mock_admin_client = MagicMock(name="admin-client")

        with (
            patch("src.api.routes.progress.VocabularyRepository") as MockVocabRepo,
            patch(
                "src.api.routes.progress.get_supabase_admin",
                return_value=mock_admin_client,
            ),
        ):
            mock_repo_instance = MagicMock()
            MockVocabRepo.return_value = mock_repo_instance

            app.include_router(progress.router, prefix="/progress")
            client = TestClient(app)
            client.cookies.set("session_id", "test-guest-session-123")

            response = client.delete("/progress/vocabulary/1")

            assert response.status_code == 200
            MockVocabRepo.assert_called_once_with(
                "test-guest-session-123", client=mock_admin_client
            )
            mock_repo_instance.delete.assert_called_once_with(1)

    def test_guest_delete_vocab_no_session(self) -> None:
        """DELETE /progress/vocabulary/1 without cookie returns 200 (no-op).

        No session_id cookie should result in an empty 200 response
        without calling VocabularyRepository.
        """
        app = FastAPI()

        app.dependency_overrides[get_current_user_optional] = lambda: None

        with (
            patch("src.api.routes.progress.VocabularyRepository") as MockVocabRepo,
            patch("src.api.routes.progress.get_supabase_admin"),
        ):
            app.include_router(progress.router, prefix="/progress")
            client = TestClient(app)

            response = client.delete("/progress/vocabulary/1")

            assert response.status_code == 200
            MockVocabRepo.assert_not_called()


# =============================================================================
# Guest Error Resilience Tests
# =============================================================================


class TestGuestErrorResilience:
    """Tests that guest progress operations degrade gracefully on errors."""

    def test_guest_chat_returns_response_on_capture_failure(
        self,
        mock_templates_dir: Path,
        graph_result_with_vocab: dict[str, Any],
    ) -> None:
        """POST /chat still returns 200 even if ProgressService raises.

        When ProgressService.record_chat_activity raises an exception during
        guest vocab capture, the chat response should still be returned
        successfully.
        """
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: None

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=graph_result_with_vocab)

        class MockCheckpointerCtx:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, *args):
                pass

        mock_admin_client = MagicMock(name="admin-client")

        with (
            patch("src.api.routes.chat.build_graph", return_value=mock_graph),
            patch(
                "src.api.routes.chat.get_checkpointer",
                return_value=MockCheckpointerCtx(),
            ),
            patch("src.api.routes.chat.ProgressService") as MockProgressService,
            patch(
                "src.api.routes.chat.get_supabase_admin",
                return_value=mock_admin_client,
            ),
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.record_chat_activity.side_effect = RuntimeError(
                "DB connection failed"
            )
            MockProgressService.return_value = mock_service_instance

            app.include_router(chat.router)
            client = TestClient(app)
            client.cookies.set("session_id", "test-guest-session-123")

            response = client.post(
                "/chat",
                data={"message": "Hola", "level": "A1", "language": "es"},
            )

            # Response should succeed despite capture failure
            assert response.status_code == 200
            assert "Hola" in response.text

    def test_guest_lesson_returns_response_on_persistence_failure(
        self,
        mock_templates_dir: Path,
        mock_lesson_service: MagicMock,
    ) -> None:
        """POST /lessons/{id}/complete still returns 200 if LessonProgressRepository raises.

        When LessonProgressRepository.complete_lesson raises an exception
        during guest lesson persistence, the completion response should
        still be returned successfully.
        """
        app = FastAPI()
        templates = MockJinja2Templates(directory=str(mock_templates_dir))

        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_current_user_optional] = lambda: None
        app.dependency_overrides[get_lesson_service] = lambda: mock_lesson_service

        mock_admin_client = MagicMock(name="admin-client")

        with (
            patch("src.api.routes.lessons.LessonProgressRepository") as MockRepo,
            patch(
                "src.api.routes.lessons.get_supabase_admin",
                return_value=mock_admin_client,
            ),
        ):
            mock_repo_instance = MagicMock()
            mock_repo_instance.complete_lesson.side_effect = RuntimeError("DB connection failed")
            MockRepo.return_value = mock_repo_instance

            app.include_router(lessons.router, prefix="/lessons")
            client = TestClient(app)
            client.cookies.set("session_id", "test-guest-session-123")

            response = client.post("/lessons/test-lesson-001/complete")

            # Response should succeed despite persistence failure
            assert response.status_code == 200
            assert "Complete" in response.text
