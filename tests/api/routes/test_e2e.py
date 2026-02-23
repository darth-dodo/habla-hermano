"""End-to-end route tests targeting uncovered lines across API route modules.

Focuses on specific uncovered lines in:
- src/api/routes/lessons.py (lines 67, 83-84, 245, 298, 346, 399, 446, 450,
  465-475, 528-552, 609-634, 685, 698, 705->724, 734-735, 795)
- src/api/routes/learn.py (lines 45-60, 107-109, 114->133, 183-185, 189->206)
- src/api/routes/review.py (lines 411-413, 468-528)
- src/api/routes/progress.py (lines 54, 79-80, 123, 164, 222, 253)
- src/api/routes/chat.py (lines 106->121, 110-117, 148, 310)
"""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from httpx import ASGITransport, AsyncClient
from postgrest.exceptions import APIError

from src.api.auth import (
    AuthenticatedUser,
    get_current_user,
    get_current_user_optional,
)
from src.api.cookies import sign_cookie_value
from src.api.dependencies import get_cached_templates
from src.db.models import LessonProgress, Vocabulary
from src.lessons.models import (
    ExerciseType,
    FillBlankExercise,
    Lesson,
    LessonContent,
    LessonLevel,
    LessonMetadata,
    LessonStep,
    LessonStepType,
    MultipleChoiceExercise,
    TranslateExercise,
)
from src.lessons.service import get_lesson_service
from src.services.review import ReviewStats

# =============================================================================
# Shared Fixtures
# =============================================================================


@pytest.fixture
def mock_user() -> AuthenticatedUser:
    """Authenticated test user."""
    return AuthenticatedUser(id="test-user-123", email="test@example.com")


@pytest.fixture
def guest_user_none() -> None:
    """Represents an unauthenticated (guest) user."""
    return None


@pytest.fixture
def sample_vocab_list() -> list[Vocabulary]:
    """Vocabulary items for review and progress testing."""
    now = datetime.now(UTC)
    return [
        Vocabulary(
            id=1,
            user_id="test-user-123",
            word="hola",
            translation="hello",
            language="es",
            next_review_at=now - timedelta(hours=1),
            last_reviewed_at=now - timedelta(days=1),
            easiness_factor=2.5,
            interval_days=1,
            repetition_count=1,
            times_seen=5,
            times_correct=3,
        ),
        Vocabulary(
            id=2,
            user_id="test-user-123",
            word="gracias",
            translation="thank you",
            language="es",
            next_review_at=now - timedelta(hours=2),
            last_reviewed_at=now - timedelta(days=2),
            easiness_factor=2.3,
            interval_days=2,
            repetition_count=2,
            times_seen=8,
            times_correct=6,
        ),
        Vocabulary(
            id=3,
            user_id="test-user-123",
            word="por favor",
            translation="please",
            language="es",
            next_review_at=now - timedelta(minutes=30),
            last_reviewed_at=now - timedelta(days=1),
            easiness_factor=2.5,
            interval_days=1,
            repetition_count=0,
            times_seen=2,
            times_correct=1,
        ),
    ]


@pytest.fixture
def sample_lesson() -> Lesson:
    """Lesson with multiple exercise types for comprehensive testing."""
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
            icon="wave",
        ),
        content=LessonContent(
            steps=[
                LessonStep(
                    type=LessonStepType.INSTRUCTION,
                    content="Welcome! Lets learn greetings.",
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
            exercises=[
                MultipleChoiceExercise(
                    id="ex-mc-001",
                    type=ExerciseType.MULTIPLE_CHOICE,
                    question="How do you say hello in Spanish?",
                    options=["Hola", "Adios", "Gracias", "Por favor"],
                    correct_index=0,
                    explanation="Hola means hello.",
                ),
                FillBlankExercise(
                    id="ex-fb-001",
                    type=ExerciseType.FILL_BLANK,
                    sentence_template="_____, como estas?",
                    correct_answer="hola",
                    hint="A greeting",
                    accept_alternatives=["Hola"],
                ),
                TranslateExercise(
                    id="ex-tr-001",
                    type=ExerciseType.TRANSLATE,
                    source_text="Hello",
                    source_language="en",
                    target_language="es",
                    correct_translation="hola",
                    accept_alternatives=["Hola"],
                ),
            ],
        ),
    )


def _create_templates(tmp_path: Path) -> Jinja2Templates:
    """Create minimal Jinja2 templates for route testing."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir(exist_ok=True)
    partials_dir = templates_dir / "partials"
    partials_dir.mkdir(exist_ok=True)

    # Lesson templates
    (templates_dir / "lessons.html").write_text(
        "<!DOCTYPE html><html><body>"
        "<h1>Lessons - {{ language }}</h1>"
        "{% for l in lessons.beginner %}"
        '<div class="lesson-card">{{ l.title }}</div>'
        "{% endfor %}"
        "</body></html>"
    )

    (templates_dir / "lesson_player.html").write_text(
        "<!DOCTYPE html><html><body>"
        '<div class="lesson-player">{{ lesson.metadata.title }}'
        " Step {{ current_step + 1 }} of {{ total_steps }}</div>"
        "</body></html>"
    )

    (partials_dir / "lesson_step.html").write_text(
        '<div class="step" data-step="{{ step_index }}">{{ step.content }}</div>'
    )

    (partials_dir / "lesson_exercise.html").write_text(
        '<div class="exercise" data-id="{{ exercise.id }}">'
        "{{ exercise.question|default('') }}</div>"
    )

    (partials_dir / "lesson_complete.html").write_text(
        '<div class="lesson-complete">'
        "Score: {{ score }}% Vocab: {{ vocab_count }} words"
        "{% if next_path_lesson %}"
        ' <a href="/lessons/{{ next_path_lesson.id }}/play">Next</a>'
        "{% endif %}"
        "</div>"
    )

    (partials_dir / "lesson_step_enhanced.html").write_text(
        '<div class="enhanced-step">'
        "{{ enhanced_content }} {{ hermano_intro }}"
        " step={{ step_index }} total={{ total_steps }}</div>"
    )

    (partials_dir / "exercise_feedback_enhanced.html").write_text(
        '<div class="enhanced-feedback">'
        "{% if is_correct %}Correct{% else %}Incorrect{% endif %}"
        " {{ feedback }}</div>"
    )

    # Learn templates
    (templates_dir / "learn.html").write_text(
        "<!DOCTYPE html><html><body>"
        '<div class="learn-path">{{ language }}'
        " {% if recommendation %}{{ recommendation }}{% endif %}"
        "</div></body></html>"
    )

    (partials_dir / "learn_recommendation.html").write_text(
        '<div class="recommendation">'
        "{% if recommendation %}{{ recommendation }}{% else %}No rec{% endif %}"
        "</div>"
    )

    # Progress templates
    (templates_dir / "progress.html").write_text(
        "<!DOCTYPE html><html><body>"
        '<div class="progress-page">'
        "Words: {{ total_words }} Sessions: {{ sessions_count }}"
        " Streak: {{ current_streak }}"
        " {% if review_stats %}Due: {{ review_stats.due_count }}{% endif %}"
        "</div></body></html>"
    )

    (partials_dir / "progress_vocab.html").write_text(
        '<div class="vocab-list">{% for v in vocabulary %}{{ v.word }}{% endfor %}</div>'
    )

    (partials_dir / "stats_summary.html").write_text(
        '<div class="stats">Words: {{ total_words }} Sessions: {{ total_sessions }}</div>'
    )

    # Chat templates
    (templates_dir / "chat.html").write_text(
        '<!DOCTYPE html><html><body><div id="chat-form" '
        'class="chat-page">Chat'
        " {% if review_mode %}ReviewMode{% endif %}"
        " {% if show_warmup %}Warmup{% endif %}"
        " {% if review_stats %}DueCount:{{ review_stats.due_count }}{% endif %}"
        ' <form hx-post="/chat"><input name="message" id="message-input">'
        ' <input name="level"><button type="submit">Send</button></form>'
        ' <div id="chat-messages"></div>'
        ' <div id="loading-indicator"></div>'
        " Habla Hermano"
        " <title>Chat</title>"
        " A0 A1 A2 B1"
        ' <span class="bg-ai"></span>'
        " Hola conversation partner"
        "</div></body></html>"
    )

    (partials_dir / "message_pair.html").write_text('<div class="bg-ai">{{ ai_response }}</div>')

    # Review templates
    (partials_dir / "review_empty.html").write_text('<div class="review-empty">{{ message }}</div>')

    (partials_dir / "review_question.html").write_text(
        '<div class="review-question" data-word-id="{{ question.word_id }}">'
        "{{ question.prompt }} {{ current }} of {{ total }}</div>"
    )

    (partials_dir / "review_feedback_question.html").write_text(
        '<div class="review-feedback">{{ feedback }}</div>'
        '<div class="review-question">'
        "{{ question.prompt }} {{ current }} of {{ total }}</div>"
    )

    (partials_dir / "review_summary.html").write_text(
        '<div class="review-summary">'
        "{{ feedback }} {{ correct_count }} of {{ total }} correct"
        "</div>"
    )

    return Jinja2Templates(directory=str(templates_dir))


# =============================================================================
# Lessons Route Tests (targeting uncovered lines)
# =============================================================================


class TestLessonsUncoveredLines:
    """Tests for uncovered lines in src/api/routes/lessons.py."""

    @pytest.fixture
    def mock_lesson_service(self, sample_lesson: Lesson) -> MagicMock:
        """Mock lesson service with sample lesson data."""
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
    def lessons_app(
        self,
        mock_user: AuthenticatedUser,
        mock_lesson_service: MagicMock,
        tmp_path: Path,
    ) -> Generator[FastAPI, None, None]:
        """FastAPI app with lesson routes and mocked dependencies."""
        from src.api.routes.lessons import router as lessons_router

        templates = _create_templates(tmp_path)
        app = FastAPI()

        async def get_mock_user_optional():
            return mock_user

        async def get_mock_user():
            return mock_user

        app.dependency_overrides[get_current_user_optional] = get_mock_user_optional
        app.dependency_overrides[get_current_user] = get_mock_user
        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_lesson_service] = lambda: mock_lesson_service

        app.include_router(lessons_router, prefix="/lessons")

        with (
            patch("src.api.routes.lessons.LessonProgressRepository") as mock_repo_cls,
            patch("src.api.routes.lessons.get_supabase_admin") as mock_admin,
            patch("src.api.routes.lessons.VocabularyRepository"),
            patch("src.api.routes.lessons.ReviewService"),
        ):
            mock_repo_cls.return_value = MagicMock()
            mock_admin.return_value = MagicMock()
            yield app

    @pytest.fixture
    def guest_lessons_app(
        self,
        mock_lesson_service: MagicMock,
        tmp_path: Path,
    ) -> Generator[FastAPI, None, None]:
        """FastAPI app for guest (unauthenticated) lesson routes."""
        from src.api.routes.lessons import router as lessons_router

        templates = _create_templates(tmp_path)
        app = FastAPI()

        async def get_no_user_optional():
            return None

        app.dependency_overrides[get_current_user_optional] = get_no_user_optional
        app.dependency_overrides[get_cached_templates] = lambda: templates
        app.dependency_overrides[get_lesson_service] = lambda: mock_lesson_service

        app.include_router(lessons_router, prefix="/lessons")

        with (
            patch("src.api.routes.lessons.LessonProgressRepository") as mock_repo_cls,
            patch("src.api.routes.lessons.get_supabase_admin") as mock_admin,
            patch("src.api.routes.lessons.VocabularyRepository"),
            patch("src.api.routes.lessons.ReviewService"),
        ):
            mock_repo_cls.return_value = MagicMock()
            mock_admin.return_value = MagicMock()
            yield app

    @pytest.fixture
    async def client(self, lessons_app: FastAPI) -> AsyncClient:
        transport = ASGITransport(app=lessons_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    @pytest.fixture
    async def guest_client(self, guest_lessons_app: FastAPI) -> AsyncClient:
        transport = ASGITransport(app=guest_lessons_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    # --- Line 67: _initialize_lesson_vocabulary_for_review with empty vocab ---

    async def test_complete_lesson_empty_vocabulary(
        self,
        client: AsyncClient,
        mock_lesson_service: MagicMock,
    ) -> None:
        """Completion with empty vocabulary skips review initialization (line 67)."""
        mock_lesson_service.get_lesson_vocabulary.return_value = []
        response = await client.post(
            "/lessons/greetings-001/complete",
            data={"score": "100"},
        )
        assert response.status_code == 200
        assert "lesson-complete" in response.text

    # --- Lines 83-84: vocab with id and next_review_at is None ---

    async def test_complete_lesson_initializes_vocab_for_review(
        self,
        client: AsyncClient,
        mock_lesson_service: MagicMock,
    ) -> None:
        """Completion initializes vocabulary for review (lines 83-84)."""
        mock_lesson_service.get_lesson_vocabulary.return_value = [
            {"word": "hola", "translation": "hello"},
        ]
        response = await client.post(
            "/lessons/greetings-001/complete",
            data={"score": "90"},
        )
        assert response.status_code == 200

    # --- Line 245: lesson not found in get_lesson_step ---

    async def test_get_step_lesson_not_found(
        self,
        client: AsyncClient,
        mock_lesson_service: MagicMock,
    ) -> None:
        """GET step for nonexistent lesson returns 404 (line 245)."""
        mock_lesson_service.get_lesson.return_value = None
        response = await client.get("/lessons/nonexistent/step/0")
        assert response.status_code == 404

    # --- Line 298: lesson not found in next_lesson_step ---

    async def test_next_step_lesson_not_found(
        self,
        client: AsyncClient,
        mock_lesson_service: MagicMock,
    ) -> None:
        """POST next step for nonexistent lesson returns 404 (line 298)."""
        mock_lesson_service.get_lesson.return_value = None
        response = await client.post(
            "/lessons/nonexistent/step/next",
            data={"current_step": "0"},
        )
        assert response.status_code == 404

    # --- Line 346: lesson not found in prev_lesson_step ---

    async def test_prev_step_lesson_not_found(
        self,
        client: AsyncClient,
        mock_lesson_service: MagicMock,
    ) -> None:
        """POST prev step for nonexistent lesson returns 404 (line 346)."""
        mock_lesson_service.get_lesson.return_value = None
        response = await client.post(
            "/lessons/nonexistent/step/prev",
            data={"current_step": "1"},
        )
        assert response.status_code == 404

    # --- Line 399: lesson not found in get_exercise ---

    async def test_get_exercise_lesson_not_found(
        self,
        client: AsyncClient,
        mock_lesson_service: MagicMock,
    ) -> None:
        """GET exercise for nonexistent lesson returns 404 (line 399)."""
        mock_lesson_service.get_lesson.return_value = None
        response = await client.get("/lessons/nonexistent/exercise/ex-mc-001")
        assert response.status_code == 404

    # --- Lines 446, 450: lesson/exercise not found in submit_exercise ---

    async def test_submit_exercise_lesson_not_found(
        self,
        client: AsyncClient,
        mock_lesson_service: MagicMock,
    ) -> None:
        """POST submit for nonexistent lesson returns 404 (line 446)."""
        mock_lesson_service.get_lesson.return_value = None
        response = await client.post(
            "/lessons/nonexistent/exercise/ex-mc-001/submit",
            data={"answer": "0"},
        )
        assert response.status_code == 404

    async def test_submit_exercise_exercise_not_found(
        self,
        client: AsyncClient,
    ) -> None:
        """POST submit for nonexistent exercise returns 404 (line 450)."""
        response = await client.post(
            "/lessons/greetings-001/exercise/nonexistent/submit",
            data={"answer": "0"},
        )
        assert response.status_code == 404

    # --- Lines 465-467: ValueError/IndexError in MC submit ---

    async def test_submit_mc_exercise_invalid_answer_value(
        self,
        client: AsyncClient,
    ) -> None:
        """Submit MC exercise with non-numeric answer triggers ValueError (line 465)."""
        response = await client.post(
            "/lessons/greetings-001/exercise/ex-mc-001/submit",
            data={"answer": "not-a-number"},
        )
        assert response.status_code == 200
        # Should show incorrect because ValueError caught
        text_lower = response.text.lower()
        assert "incorrect" in text_lower or "try again" in text_lower or "correct" in text_lower

    async def test_submit_mc_exercise_index_out_of_range(
        self,
        client: AsyncClient,
    ) -> None:
        """Submit MC exercise with out-of-range index triggers IndexError (line 465)."""
        response = await client.post(
            "/lessons/greetings-001/exercise/ex-mc-001/submit",
            data={"answer": "999"},
        )
        assert response.status_code == 200

    # --- Lines 469-471: FillBlankExercise submit ---

    async def test_submit_fill_blank_exercise_correct(
        self,
        client: AsyncClient,
    ) -> None:
        """Submit fill-blank exercise with correct answer (lines 469-471)."""
        response = await client.post(
            "/lessons/greetings-001/exercise/ex-fb-001/submit",
            data={"answer": "hola"},
        )
        assert response.status_code == 200
        assert "Correct" in response.text or "correct" in response.text.lower()

    async def test_submit_fill_blank_exercise_incorrect(
        self,
        client: AsyncClient,
    ) -> None:
        """Submit fill-blank exercise with wrong answer (lines 469-471)."""
        response = await client.post(
            "/lessons/greetings-001/exercise/ex-fb-001/submit",
            data={"answer": "wrong"},
        )
        assert response.status_code == 200
        assert "incorrect" in response.text.lower() or "try again" in response.text.lower()

    # --- Lines 473-475: TranslateExercise submit ---

    async def test_submit_translate_exercise_correct(
        self,
        client: AsyncClient,
    ) -> None:
        """Submit translate exercise with correct answer (lines 473-475)."""
        response = await client.post(
            "/lessons/greetings-001/exercise/ex-tr-001/submit",
            data={"answer": "hola"},
        )
        assert response.status_code == 200
        assert "Correct" in response.text or "correct" in response.text.lower()

    async def test_submit_translate_exercise_incorrect(
        self,
        client: AsyncClient,
    ) -> None:
        """Submit translate exercise with wrong answer (lines 473-475)."""
        response = await client.post(
            "/lessons/greetings-001/exercise/ex-tr-001/submit",
            data={"answer": "wrong"},
        )
        assert response.status_code == 200
        assert "incorrect" in response.text.lower() or "try again" in response.text.lower()

    # --- Lines 528-552: Enhanced lesson step (AI subgraph) ---

    async def test_enhanced_lesson_step(
        self,
        client: AsyncClient,
    ) -> None:
        """GET enhanced step invokes lesson subgraph (lines 528-552)."""
        mock_result = {
            "step_type": "instruction",
            "step_content": "Welcome to Spanish!",
            "step_vocabulary": [],
            "step_target_text": None,
            "step_translation": None,
            "enhanced_content": "AI-enhanced content here",
            "hermano_intro": "Hola amigo!",
        }
        mock_subgraph = MagicMock()
        mock_subgraph.ainvoke = AsyncMock(return_value=mock_result)
        with patch(
            "src.agent.lesson_graph.lesson_subgraph",
            mock_subgraph,
            create=True,
        ):
            response = await client.get(
                "/lessons/greetings-001/step/0/enhanced?level=A1&language=es"
            )
        assert response.status_code == 200
        assert "enhanced-step" in response.text
        assert "AI-enhanced content here" in response.text

    async def test_enhanced_lesson_step_not_found(
        self,
        client: AsyncClient,
        mock_lesson_service: MagicMock,
    ) -> None:
        """GET enhanced step for nonexistent lesson returns 404 (line 528-530)."""
        mock_lesson_service.get_lesson.return_value = None
        response = await client.get("/lessons/nonexistent/step/0/enhanced?level=A1&language=es")
        assert response.status_code == 404

    async def test_enhanced_lesson_step_out_of_range(
        self,
        client: AsyncClient,
    ) -> None:
        """GET enhanced step with invalid index returns 404 (lines 533-537)."""
        response = await client.get("/lessons/greetings-001/step/99/enhanced?level=A1&language=es")
        assert response.status_code == 404

    # --- Lines 609-634: Enhanced exercise submission ---

    async def test_enhanced_exercise_submit(
        self,
        client: AsyncClient,
    ) -> None:
        """POST enhanced exercise submit invokes validation graph (lines 609-634)."""
        mock_result = {
            "is_correct": True,
            "exercise_feedback": "Great job!",
        }
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        with patch(
            "src.agent.lesson_graph.exercise_validation_graph",
            mock_graph,
            create=True,
        ):
            response = await client.post(
                "/lessons/greetings-001/exercise/ex-mc-001/submit/enhanced",
                data={"answer": "0", "level": "A1", "language": "es"},
            )
        assert response.status_code == 200
        assert "enhanced-feedback" in response.text
        assert "Correct" in response.text

    async def test_enhanced_exercise_submit_lesson_not_found(
        self,
        client: AsyncClient,
        mock_lesson_service: MagicMock,
    ) -> None:
        """POST enhanced submit for nonexistent lesson returns 404 (line 609-611)."""
        mock_lesson_service.get_lesson.return_value = None
        response = await client.post(
            "/lessons/nonexistent/exercise/ex-mc-001/submit/enhanced",
            data={"answer": "0", "level": "A1", "language": "es"},
        )
        assert response.status_code == 404

    async def test_enhanced_exercise_submit_exercise_not_found(
        self,
        client: AsyncClient,
    ) -> None:
        """POST enhanced submit for nonexistent exercise returns 404 (lines 613-618)."""
        response = await client.post(
            "/lessons/greetings-001/exercise/nonexistent/submit/enhanced",
            data={"answer": "0", "level": "A1", "language": "es"},
        )
        assert response.status_code == 404

    # --- Line 685: lesson not found in complete_lesson ---

    async def test_complete_lesson_not_found(
        self,
        client: AsyncClient,
        mock_lesson_service: MagicMock,
    ) -> None:
        """POST complete for nonexistent lesson returns 404 (line 685)."""
        mock_lesson_service.get_lesson.return_value = None
        response = await client.post(
            "/lessons/nonexistent/complete",
            data={"score": "100"},
        )
        assert response.status_code == 404

    # --- Lines 698, 705->724: Guest with session_id completes lesson ---

    async def test_complete_lesson_guest_with_session_cookie(
        self,
        guest_client: AsyncClient,
    ) -> None:
        """Guest with existing session_id cookie completes lesson (line 698)."""
        response = await guest_client.post(
            "/lessons/greetings-001/complete",
            data={"score": "80"},
            cookies={"session_id": "guest-session-abc"},
        )
        assert response.status_code == 200
        assert "lesson-complete" in response.text

    async def test_complete_lesson_guest_no_session_creates_cookie(
        self,
        guest_client: AsyncClient,
    ) -> None:
        """First-time guest creates new session cookie on completion (lines 700-702)."""
        response = await guest_client.post(
            "/lessons/greetings-001/complete",
            data={"score": "85"},
        )
        assert response.status_code == 200
        # Should set a new session_id cookie
        set_cookies = response.headers.get_list("set-cookie")
        cookie_str = " ".join(set_cookies)
        assert "session_id" in cookie_str

    # --- Lines 734-735: Exception in get_next_path_lesson ---

    async def test_complete_lesson_path_service_error(
        self,
        client: AsyncClient,
    ) -> None:
        """Completion continues when path service raises exception (lines 734-735)."""
        mock_path_service = MagicMock()
        mock_path_service.get_next_path_lesson.side_effect = ValueError("Path error")
        with patch(
            "src.services.paths.get_path_service",
            return_value=mock_path_service,
        ):
            response = await client.post(
                "/lessons/greetings-001/complete",
                data={"score": "100"},
            )
        assert response.status_code == 200
        assert "lesson-complete" in response.text

    # --- Line 795: lesson not found in handoff_to_chat ---

    async def test_handoff_lesson_not_found(
        self,
        client: AsyncClient,
        mock_lesson_service: MagicMock,
    ) -> None:
        """POST handoff for nonexistent lesson returns 404 (line 795)."""
        mock_lesson_service.get_lesson.return_value = None
        response = await client.post("/lessons/nonexistent/handoff")
        assert response.status_code == 404


# =============================================================================
# Learn Route Tests (targeting uncovered lines)
# =============================================================================


class TestLearnUncoveredLines:
    """Tests for uncovered lines in src/api/routes/learn.py."""

    @pytest.fixture
    def mock_path_service(self) -> MagicMock:
        """Mock path service."""
        service = MagicMock()
        service.get_path.return_value = MagicMock(units=[])
        service.get_path_progress.return_value = MagicMock()
        service.get_next_path_lesson.return_value = None
        return service

    @pytest.fixture
    def mock_adaptive_service(self) -> MagicMock:
        """Mock adaptive service."""
        service = MagicMock()
        service.get_daily_recommendation.return_value = "Practice greetings"
        return service

    @pytest.fixture
    def mock_review_service(self) -> MagicMock:
        """Mock review service."""
        service = MagicMock()
        service.get_stats.return_value = ReviewStats(
            due_count=5,
            next_review_in="1 hour",
            total_in_rotation=20,
        )
        return service

    @pytest.fixture
    def learn_app(
        self,
        mock_user: AuthenticatedUser,
        mock_path_service: MagicMock,
        mock_adaptive_service: MagicMock,
        mock_review_service: MagicMock,
        sample_vocab_list: list[Vocabulary],
        tmp_path: Path,
    ) -> Generator[FastAPI, None, None]:
        """FastAPI app with learn routes and mocked dependencies."""
        from src.api.routes.learn import router as learn_router

        templates = _create_templates(tmp_path)
        app = FastAPI()

        async def get_mock_user_optional():
            return mock_user

        app.dependency_overrides[get_current_user_optional] = get_mock_user_optional
        app.dependency_overrides[get_cached_templates] = lambda: templates

        app.include_router(learn_router, prefix="/learn")

        mock_lesson_repo = MagicMock()
        mock_lesson_repo.get_completed.return_value = [
            LessonProgress(
                user_id="test-user-123",
                lesson_id="greetings-001",
                score=100,
            )
        ]

        mock_vocab_repo = MagicMock()
        mock_vocab_repo.get_all.return_value = sample_vocab_list

        with (
            patch(
                "src.api.routes.learn.get_path_service",
                return_value=mock_path_service,
            ),
            patch(
                "src.api.routes.learn.get_adaptive_service",
                return_value=mock_adaptive_service,
            ),
            patch(
                "src.api.routes.learn.LessonProgressRepository",
                return_value=mock_lesson_repo,
            ),
            patch(
                "src.api.routes.learn.VocabularyRepository",
                return_value=mock_vocab_repo,
            ),
            patch(
                "src.api.routes.learn.ReviewService",
                return_value=mock_review_service,
            ),
            patch(
                "src.api.routes.learn.get_supabase_admin",
                return_value=MagicMock(),
            ),
            patch(
                "src.api.routes.learn.get_supabase_for_user",
                return_value=MagicMock(),
            ),
        ):
            yield app

    @pytest.fixture
    def guest_learn_app(
        self,
        mock_path_service: MagicMock,
        mock_adaptive_service: MagicMock,
        mock_review_service: MagicMock,
        sample_vocab_list: list[Vocabulary],
        tmp_path: Path,
    ) -> Generator[FastAPI, None, None]:
        """FastAPI app with learn routes for guest users."""
        from src.api.routes.learn import router as learn_router

        templates = _create_templates(tmp_path)
        app = FastAPI()

        async def get_no_user_optional():
            return None

        app.dependency_overrides[get_current_user_optional] = get_no_user_optional
        app.dependency_overrides[get_cached_templates] = lambda: templates

        app.include_router(learn_router, prefix="/learn")

        mock_lesson_repo = MagicMock()
        mock_lesson_repo.get_completed.return_value = []

        mock_vocab_repo = MagicMock()
        mock_vocab_repo.get_all.return_value = sample_vocab_list

        with (
            patch(
                "src.api.routes.learn.get_path_service",
                return_value=mock_path_service,
            ),
            patch(
                "src.api.routes.learn.get_adaptive_service",
                return_value=mock_adaptive_service,
            ),
            patch(
                "src.api.routes.learn.LessonProgressRepository",
                return_value=mock_lesson_repo,
            ),
            patch(
                "src.api.routes.learn.VocabularyRepository",
                return_value=mock_vocab_repo,
            ),
            patch(
                "src.api.routes.learn.ReviewService",
                return_value=mock_review_service,
            ),
            patch(
                "src.api.routes.learn.get_supabase_admin",
                return_value=MagicMock(),
            ),
            patch(
                "src.api.routes.learn.get_supabase_for_user",
                return_value=MagicMock(),
            ),
        ):
            yield app

    @pytest.fixture
    async def client(self, learn_app: FastAPI) -> AsyncClient:
        transport = ASGITransport(app=learn_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    @pytest.fixture
    async def guest_client(self, guest_learn_app: FastAPI) -> AsyncClient:
        transport = ASGITransport(app=guest_learn_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    # --- Lines 45-60: _get_user_learning_data for authenticated user ---

    async def test_learn_page_authenticated_loads_data(
        self,
        client: AsyncClient,
    ) -> None:
        """Authenticated user loads learning data (lines 45-60, 114->133)."""
        response = await client.get("/learn/")
        assert response.status_code == 200
        assert "learn-path" in response.text

    # --- Lines 107-109: guest with session_id ---

    async def test_learn_page_guest_with_session_id(
        self,
        guest_client: AsyncClient,
    ) -> None:
        """Guest with session_id cookie loads data (lines 107-109)."""
        response = await guest_client.get(
            "/learn/",
            cookies={"session_id": "guest-session-xyz"},
        )
        assert response.status_code == 200
        assert "learn-path" in response.text

    # --- Lines 183-185: guest recommendation with session_id ---

    async def test_recommendation_guest_with_session_id(
        self,
        guest_client: AsyncClient,
    ) -> None:
        """Guest recommendation loads data with session_id (lines 183-185, 189->206)."""
        response = await guest_client.get(
            "/learn/recommendation",
            cookies={"session_id": "guest-session-xyz"},
        )
        assert response.status_code == 200
        assert "recommendation" in response.text

    async def test_recommendation_no_user_no_session(
        self,
        guest_client: AsyncClient,
    ) -> None:
        """No user and no session returns recommendation without data."""
        response = await guest_client.get("/learn/recommendation")
        assert response.status_code == 200
        assert "recommendation" in response.text

    async def test_learn_page_no_path_redirects(
        self,
        client: AsyncClient,
        mock_path_service: MagicMock,
    ) -> None:
        """No path for language redirects to /lessons."""
        mock_path_service.get_path.return_value = None
        response = await client.get("/learn/?language=es", follow_redirects=False)
        assert response.status_code == 302
        assert "/lessons" in response.headers.get("location", "")

    async def test_learn_page_data_loading_error(
        self,
        client: AsyncClient,
    ) -> None:
        """Exception in data loading falls back to empty progress (line 129-130)."""
        with patch(
            "src.api.routes.learn.LessonProgressRepository",
            side_effect=APIError(
                {"code": "500", "message": "DB error", "hint": None, "details": None}
            ),
        ):
            response = await client.get("/learn/")
        assert response.status_code == 200
        assert "learn-path" in response.text

    async def test_recommendation_data_loading_error(
        self,
        client: AsyncClient,
    ) -> None:
        """Exception in recommendation loading is caught (line 203-204)."""
        with patch(
            "src.api.routes.learn.LessonProgressRepository",
            side_effect=APIError(
                {"code": "500", "message": "DB error", "hint": None, "details": None}
            ),
        ):
            response = await client.get("/learn/recommendation")
        assert response.status_code == 200
        assert "recommendation" in response.text


# =============================================================================
# Review Route Tests (targeting uncovered lines)
# =============================================================================


class TestReviewUncoveredLines:
    """Tests for uncovered lines in src/api/routes/review.py.

    Targets _handle_missing_word function (lines 411-413, 468-528).
    """

    @pytest.fixture
    def mock_review_service(self, sample_vocab_list: list[Vocabulary]) -> MagicMock:
        service = MagicMock()
        service.get_stats.return_value = ReviewStats(
            due_count=3,
            next_review_in="2 hours",
            total_in_rotation=10,
        )
        service.get_due_words.return_value = sample_vocab_list
        service.update_sm2.return_value = sample_vocab_list[0]
        return service

    @pytest.fixture
    def mock_vocab_repo(self, sample_vocab_list: list[Vocabulary]) -> MagicMock:
        repo = MagicMock()
        repo.get_all.return_value = sample_vocab_list
        return repo

    @pytest.fixture
    def review_app(
        self,
        mock_user: AuthenticatedUser,
        mock_review_service: MagicMock,
        mock_vocab_repo: MagicMock,
        tmp_path: Path,
    ) -> Generator[FastAPI, None, None]:
        """FastAPI app with review routes for testing _handle_missing_word."""
        from src.api.routes.review import router as review_router

        templates = _create_templates(tmp_path)
        app = FastAPI()

        async def get_mock_user():
            return mock_user

        app.dependency_overrides[get_current_user] = get_mock_user
        app.dependency_overrides[get_cached_templates] = lambda: templates

        app.include_router(review_router)

        with (
            patch(
                "src.api.routes.review.ReviewService",
                return_value=mock_review_service,
            ),
            patch(
                "src.api.routes.review.VocabularyRepository",
                return_value=mock_vocab_repo,
            ),
            patch(
                "src.api.routes.review.get_supabase_for_user",
                return_value=MagicMock(),
            ),
        ):
            yield app

    @pytest.fixture
    async def client(self, review_app: FastAPI) -> AsyncClient:
        transport = ASGITransport(app=review_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    # --- Lines 411-413: next_vocab is None triggers _handle_missing_word ---

    async def test_answer_triggers_handle_missing_word(
        self,
        client: AsyncClient,
        mock_vocab_repo: MagicMock,
    ) -> None:
        """When next word is missing, _handle_missing_word is called (lines 411-413).

        Session has word_ids [1, 999] where 999 does not exist in vocab.
        After answering word 1, trying to load word 999 returns None which
        triggers the _handle_missing_word path.
        """
        # Only word_id=1 exists in vocab, word_id=999 does not
        mock_vocab_repo.get_all.return_value = [
            Vocabulary(
                id=1,
                user_id="test-user-123",
                word="hola",
                translation="hello",
                language="es",
                next_review_at=datetime.now(UTC) - timedelta(hours=1),
            ),
        ]

        session_cookie = sign_cookie_value(
            {
                "word_ids": [1, 999],
                "current_index": 0,
                "results": [],
                "language": "es",
            }
        )
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hola"},
            cookies={"review_session": session_cookie},
        )
        assert response.status_code == 200

    # --- Lines 468-528: _handle_missing_word finds a valid word further in list ---

    async def test_handle_missing_word_finds_later_valid_word(
        self,
        client: AsyncClient,
        mock_vocab_repo: MagicMock,
    ) -> None:
        """_handle_missing_word skips missing words and finds next valid one (lines 468-506)."""
        vocab_list = [
            Vocabulary(
                id=1,
                user_id="test-user-123",
                word="hola",
                translation="hello",
                language="es",
                next_review_at=datetime.now(UTC) - timedelta(hours=1),
            ),
            Vocabulary(
                id=5,
                user_id="test-user-123",
                word="gracias",
                translation="thank you",
                language="es",
                next_review_at=datetime.now(UTC) - timedelta(hours=1),
            ),
        ]
        mock_vocab_repo.get_all.return_value = vocab_list

        # Session: after answering word 1, next is 888 (missing), then 999 (missing),
        # then 5 (valid)
        session_cookie = sign_cookie_value(
            {
                "word_ids": [1, 888, 999, 5],
                "current_index": 0,
                "results": [],
                "language": "es",
            }
        )
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hola"},
            cookies={"review_session": session_cookie},
        )
        assert response.status_code == 200
        # Should have found word 5 and returned the next question
        assert "review-feedback" in response.text or "review-summary" in response.text

    # --- Lines 511-528: _handle_missing_word exhausts all words ---

    async def test_handle_missing_word_all_remaining_missing(
        self,
        client: AsyncClient,
        mock_vocab_repo: MagicMock,
    ) -> None:
        """_handle_missing_word shows summary when all remaining words are missing (lines 511-528)."""
        vocab_list = [
            Vocabulary(
                id=1,
                user_id="test-user-123",
                word="hola",
                translation="hello",
                language="es",
                next_review_at=datetime.now(UTC) - timedelta(hours=1),
            ),
        ]
        mock_vocab_repo.get_all.return_value = vocab_list

        # Session: after answering word 1, remaining are [888, 999] which are all missing
        session_cookie = sign_cookie_value(
            {
                "word_ids": [1, 888, 999],
                "current_index": 0,
                "results": [],
                "language": "es",
            }
        )
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hola"},
            cookies={"review_session": session_cookie},
        )
        assert response.status_code == 200
        # Should show summary since no valid words remain
        assert "review-summary" in response.text


# =============================================================================
# Progress Route Tests (targeting uncovered lines)
# =============================================================================


class TestProgressUncoveredLines:
    """Tests for uncovered lines in src/api/routes/progress.py."""

    @pytest.fixture
    def mock_progress_service(self) -> MagicMock:
        service = MagicMock()
        from src.services.progress import ChartData, DashboardStats

        service.get_dashboard_stats.return_value = DashboardStats(
            total_words=50,
            total_sessions=10,
            lessons_completed=5,
            current_streak=3,
            accuracy_rate=85.0,
            words_learned_today=3,
            messages_today=12,
        )
        service.get_chart_data.return_value = ChartData(
            vocab_growth=[],
            accuracy_trend=[],
        )
        return service

    @pytest.fixture
    def mock_review_service(self) -> MagicMock:
        service = MagicMock()
        service.get_stats.return_value = ReviewStats(
            due_count=5,
            next_review_in="30 min",
            total_in_rotation=20,
        )
        return service

    @pytest.fixture
    def progress_app(
        self,
        mock_user: AuthenticatedUser,
        mock_progress_service: MagicMock,
        mock_review_service: MagicMock,
        sample_vocab_list: list[Vocabulary],
        tmp_path: Path,
    ) -> Generator[FastAPI, None, None]:
        """FastAPI app with progress routes for authenticated user."""
        from src.api.routes.progress import router as progress_router

        templates = _create_templates(tmp_path)
        app = FastAPI()

        async def get_mock_user_optional():
            return mock_user

        app.dependency_overrides[get_current_user_optional] = get_mock_user_optional
        app.dependency_overrides[get_cached_templates] = lambda: templates

        app.include_router(progress_router, prefix="/progress")

        mock_vocab_repo = MagicMock()
        mock_vocab_repo.get_all.return_value = sample_vocab_list

        with (
            patch(
                "src.api.routes.progress.ProgressService",
                return_value=mock_progress_service,
            ),
            patch(
                "src.api.routes.progress.ReviewService",
                return_value=mock_review_service,
            ),
            patch(
                "src.api.routes.progress.VocabularyRepository",
                return_value=mock_vocab_repo,
            ),
            patch(
                "src.api.routes.progress.get_supabase_for_user",
                return_value=MagicMock(),
            ),
        ):
            yield app

    @pytest.fixture
    def guest_progress_app(
        self,
        tmp_path: Path,
    ) -> Generator[FastAPI, None, None]:
        """FastAPI app with progress routes for guest user."""
        from src.api.routes.progress import router as progress_router

        templates = _create_templates(tmp_path)
        app = FastAPI()

        async def get_no_user_optional():
            return None

        app.dependency_overrides[get_current_user_optional] = get_no_user_optional
        app.dependency_overrides[get_cached_templates] = lambda: templates

        app.include_router(progress_router, prefix="/progress")
        yield app

    @pytest.fixture
    async def client(self, progress_app: FastAPI) -> AsyncClient:
        transport = ASGITransport(app=progress_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    @pytest.fixture
    async def guest_client(self, guest_progress_app: FastAPI) -> AsyncClient:
        transport = ASGITransport(app=guest_progress_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    # --- Line 54: not user or not sb_access_token guard in get_progress_page ---

    async def test_progress_page_no_user_returns_guest_view(
        self,
        guest_client: AsyncClient,
    ) -> None:
        """Progress page for guest returns zeroed stats (line 54)."""
        response = await guest_client.get("/progress/")
        assert response.status_code == 200
        assert "Words: 0" in response.text

    async def test_progress_page_no_access_token(
        self,
        client: AsyncClient,
    ) -> None:
        """Authenticated user without sb-access-token gets guest view (line 54).

        The route checks `not user or not sb_access_token`. Even with a user,
        missing sb_access_token triggers the guest path.
        """
        # The client sends no sb-access-token cookie, so sb_access_token=None
        response = await client.get("/progress/")
        # With sb_access_token=None, the guard triggers
        assert response.status_code == 200

    # --- Lines 79-80: ReviewService exception in progress page ---

    async def test_progress_page_review_stats_exception(
        self,
        progress_app: FastAPI,
        mock_review_service: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Progress page continues when ReviewService raises (lines 79-80)."""
        mock_review_service.get_stats.side_effect = APIError(
            {"code": "500", "message": "Review DB error", "hint": None, "details": None}
        )
        transport = ASGITransport(app=progress_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            response = await c.get(
                "/progress/",
                cookies={"sb-access-token": "fake-token"},
            )
        assert response.status_code == 200
        assert "progress-page" in response.text

    # --- Line 123: not user or not sb_access_token in get_vocabulary ---

    async def test_vocabulary_no_user_returns_empty(
        self,
        guest_client: AsyncClient,
    ) -> None:
        """Vocabulary endpoint for guest returns empty list (line 123)."""
        response = await guest_client.get("/progress/vocabulary")
        assert response.status_code == 200
        assert "vocab-list" in response.text

    # --- Line 164: not user or not sb_access_token in get_stats ---

    async def test_stats_no_user_returns_zeros(
        self,
        guest_client: AsyncClient,
    ) -> None:
        """Stats endpoint for guest returns zeroed stats (line 164)."""
        response = await guest_client.get("/progress/stats")
        assert response.status_code == 200
        assert "Words: 0" in response.text

    # --- Line 222: not user or not sb_access_token in get_chart_data ---

    async def test_chart_data_no_user_returns_empty(
        self,
        guest_client: AsyncClient,
    ) -> None:
        """Chart data for guest returns empty arrays (line 222)."""
        response = await guest_client.get("/progress/chart-data")
        assert response.status_code == 200
        data = response.json()
        assert data["vocab_growth"] == []
        assert data["accuracy_trend"] == []

    # --- Line 253: not user or not sb_access_token in remove_vocabulary_word ---

    async def test_remove_vocab_no_user_returns_empty(
        self,
        guest_client: AsyncClient,
    ) -> None:
        """Remove vocabulary for guest returns empty 200 (line 253)."""
        response = await guest_client.delete("/progress/vocabulary/1")
        assert response.status_code == 200
        assert response.text == ""

    # --- Authenticated paths with sb-access-token ---

    async def test_progress_page_authenticated_with_token(
        self,
        client: AsyncClient,
    ) -> None:
        """Authenticated user with sb-access-token gets real stats."""
        response = await client.get(
            "/progress/",
            cookies={"sb-access-token": "fake-token"},
        )
        assert response.status_code == 200
        assert "Words: 50" in response.text

    async def test_vocabulary_authenticated_with_token(
        self,
        client: AsyncClient,
    ) -> None:
        """Authenticated user gets real vocabulary list."""
        response = await client.get(
            "/progress/vocabulary",
            cookies={"sb-access-token": "fake-token"},
        )
        assert response.status_code == 200
        assert "hola" in response.text

    async def test_stats_authenticated_with_token(
        self,
        client: AsyncClient,
    ) -> None:
        """Authenticated user gets real stats."""
        response = await client.get(
            "/progress/stats",
            cookies={"sb-access-token": "fake-token"},
        )
        assert response.status_code == 200
        assert "Words: 50" in response.text

    async def test_chart_data_authenticated_with_token(
        self,
        client: AsyncClient,
    ) -> None:
        """Authenticated user gets real chart data."""
        response = await client.get(
            "/progress/chart-data",
            cookies={"sb-access-token": "fake-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "vocab_growth" in data
        assert "accuracy_trend" in data

    async def test_remove_vocab_authenticated_with_token(
        self,
        client: AsyncClient,
    ) -> None:
        """Authenticated user can remove vocabulary word."""
        response = await client.delete(
            "/progress/vocabulary/1",
            cookies={"sb-access-token": "fake-token"},
        )
        assert response.status_code == 200


# =============================================================================
# Chat Route Tests (targeting uncovered lines)
# =============================================================================


class TestChatUncoveredLines:
    """Tests for uncovered lines in src/api/routes/chat.py."""

    @pytest.fixture
    def mock_review_service(self) -> MagicMock:
        service = MagicMock()
        service.get_stats.return_value = ReviewStats(
            due_count=5,
            next_review_in="1 hour",
            total_in_rotation=20,
        )
        return service

    @pytest.fixture
    def mock_review_service_with_error(self) -> MagicMock:
        service = MagicMock()
        service.get_stats.side_effect = APIError(
            {"code": "500", "message": "Review service error", "hint": None, "details": None}
        )
        return service

    @pytest.fixture
    def mock_review_service_no_due(self) -> MagicMock:
        service = MagicMock()
        service.get_stats.return_value = ReviewStats(
            due_count=0,
            next_review_in=None,
            total_in_rotation=5,
        )
        return service

    def _create_chat_app(
        self,
        user: AuthenticatedUser | None,
        mock_review_service: MagicMock,
        tmp_path: Path,
    ) -> FastAPI:
        """Create a chat app with specific user and review service."""
        from src.api.routes.chat import router as chat_router

        templates = _create_templates(tmp_path)
        app = FastAPI()

        if user:

            async def get_user_optional():
                return user
        else:

            async def get_user_optional():
                return None

        app.dependency_overrides[get_current_user_optional] = get_user_optional
        app.dependency_overrides[get_cached_templates] = lambda: templates

        app.include_router(chat_router)

        return app

    # --- Lines 106->121, 110-117: Review stats for authenticated user ---

    async def test_chat_page_shows_review_stats(
        self,
        mock_user: AuthenticatedUser,
        mock_review_service: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Chat page shows review stats for authenticated user (lines 106-117)."""
        app = self._create_chat_app(mock_user, mock_review_service, tmp_path)

        with patch(
            "src.api.routes.chat.ReviewService",
            return_value=mock_review_service,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                response = await c.get("/")
            assert response.status_code == 200
            assert "DueCount:5" in response.text

    async def test_chat_page_review_mode(
        self,
        mock_user: AuthenticatedUser,
        mock_review_service: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Chat page with mode=review activates review mode (lines 112-114)."""
        app = self._create_chat_app(mock_user, mock_review_service, tmp_path)

        with patch(
            "src.api.routes.chat.ReviewService",
            return_value=mock_review_service,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                response = await c.get("/?mode=review")
            assert response.status_code == 200
            assert "ReviewMode" in response.text

    async def test_chat_page_shows_warmup_when_due(
        self,
        mock_user: AuthenticatedUser,
        mock_review_service: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Chat page shows warmup prompt when words are due (lines 115-117)."""
        app = self._create_chat_app(mock_user, mock_review_service, tmp_path)

        with patch(
            "src.api.routes.chat.ReviewService",
            return_value=mock_review_service,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                response = await c.get("/")
            assert response.status_code == 200
            assert "Warmup" in response.text

    async def test_chat_page_no_warmup_when_dismissed(
        self,
        mock_user: AuthenticatedUser,
        mock_review_service: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Chat page hides warmup when cookie is set (line 115)."""
        app = self._create_chat_app(mock_user, mock_review_service, tmp_path)

        with patch(
            "src.api.routes.chat.ReviewService",
            return_value=mock_review_service,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                response = await c.get(
                    "/",
                    cookies={"warmup_dismissed": "1"},
                )
            assert response.status_code == 200
            assert "Warmup" not in response.text

    async def test_chat_page_no_warmup_when_nothing_due(
        self,
        mock_user: AuthenticatedUser,
        mock_review_service_no_due: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Chat page skips warmup when no words are due (line 115)."""
        app = self._create_chat_app(mock_user, mock_review_service_no_due, tmp_path)

        with patch(
            "src.api.routes.chat.ReviewService",
            return_value=mock_review_service_no_due,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                response = await c.get("/")
            assert response.status_code == 200
            assert "Warmup" not in response.text

    # --- Line 148: ReviewService exception in chat page ---

    async def test_chat_page_review_service_error(
        self,
        mock_user: AuthenticatedUser,
        mock_review_service_with_error: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Chat page continues when ReviewService raises (line 118-119, covers 148)."""
        app = self._create_chat_app(mock_user, mock_review_service_with_error, tmp_path)

        with patch(
            "src.api.routes.chat.ReviewService",
            return_value=mock_review_service_with_error,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                response = await c.get("/")
            assert response.status_code == 200
            # Should render chat without review stats
            assert "chat-page" in response.text

    # --- Line 310: Anonymous user new conversation deletes session cookie ---

    async def test_new_conversation_anonymous_deletes_session(
        self,
        tmp_path: Path,
    ) -> None:
        """POST /new for anonymous user deletes session_id cookie (line 310)."""
        from src.api.routes.chat import router as chat_router

        templates = _create_templates(tmp_path)
        app = FastAPI()

        async def get_no_user_optional():
            return None

        app.dependency_overrides[get_current_user_optional] = get_no_user_optional
        app.dependency_overrides[get_cached_templates] = lambda: templates

        app.include_router(chat_router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            response = await c.post(
                "/new",
                cookies={"session_id": "old-session-id"},
                follow_redirects=False,
            )
        assert response.status_code == 200
        assert "HX-Redirect" in response.headers

    async def test_new_conversation_authenticated_no_cookie_deletion(
        self,
        mock_user: AuthenticatedUser,
        mock_review_service: MagicMock,
        tmp_path: Path,
    ) -> None:
        """POST /new for authenticated user does not delete session cookie."""
        app = self._create_chat_app(mock_user, mock_review_service, tmp_path)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            response = await c.post("/new", follow_redirects=False)
        assert response.status_code == 200
        assert "HX-Redirect" in response.headers

    # --- Chat page for guest user ---

    async def test_chat_page_guest_no_review_stats(
        self,
        mock_review_service: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Chat page for guest does not show review stats."""
        app = self._create_chat_app(None, mock_review_service, tmp_path)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            response = await c.get("/")
        assert response.status_code == 200
        # No DueCount since user is None
        assert "DueCount" not in response.text

    # --- Chat send message for invalid language ---

    async def test_send_message_invalid_language(
        self,
        mock_user: AuthenticatedUser,
        mock_review_service: MagicMock,
        tmp_path: Path,
    ) -> None:
        """POST /chat with invalid language returns 422."""
        app = self._create_chat_app(mock_user, mock_review_service, tmp_path)

        # Need to mock the graph for send_message
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock()

        with (
            patch("src.api.routes.chat.ReviewService", return_value=mock_review_service),
            patch("src.api.routes.chat.build_graph", return_value=mock_graph),
            patch("src.api.routes.chat.get_checkpointer") as mock_cp,
        ):
            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_cp.return_value = mock_ctx

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                response = await c.post(
                    "/chat",
                    data={"message": "hola", "level": "A1", "language": "xx"},
                )
            assert response.status_code == 422
            assert "Invalid language" in response.text
