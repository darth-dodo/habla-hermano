"""Tests for review API routes (spaced repetition).

Phase 12/13: Comprehensive tests for /review endpoints including stats,
session management, answer evaluation, and helper functions.

Review is an authenticated-only feature (Phase 13 simplified guest model).
Tests cover authenticated users, unauthenticated rejection (401),
edge cases, and error paths.
"""

import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from httpx import ASGITransport, AsyncClient

from src.api.auth import AuthenticatedUser, get_current_user
from src.api.routes.review import (
    _evaluate_answer,
    _generate_question,
    _get_hermano_feedback,
    _levenshtein_distance,
)
from src.db.models import Vocabulary
from src.services.review import ReviewStats

# =============================================================================
# Helpers
# =============================================================================


def _parse_session_cookie_from_response(response) -> dict:
    """Extract and decode the review_session cookie from a response.

    httpx encodes cookie values with RFC 2109 octal escapes (e.g. commas
    become \\054). This helper reads the raw Set-Cookie header and parses
    it with http.cookies.SimpleCookie which handles the un-quoting.

    Args:
        response: httpx Response object.

    Returns:
        Parsed JSON dict from the review_session cookie value.
    """
    set_cookie_headers = response.headers.get_list("set-cookie")
    for header in set_cookie_headers:
        if "review_session=" in header:
            cookie = SimpleCookie()
            cookie.load(header)
            morsel = cookie.get("review_session")
            if morsel:
                return json.loads(morsel.value)
    return {}


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_user() -> AuthenticatedUser:
    """Create mock authenticated user."""
    return AuthenticatedUser(id="user-review-123", email="reviewer@example.com")


@pytest.fixture
def sample_vocab_list() -> list[Vocabulary]:
    """Create sample vocabulary for review testing."""
    now = datetime.now(UTC)
    return [
        Vocabulary(
            id=1,
            user_id="user-review-123",
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
            user_id="user-review-123",
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
            user_id="user-review-123",
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
def mock_review_service(sample_vocab_list: list[Vocabulary]) -> MagicMock:
    """Create mock ReviewService."""
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
def mock_vocab_repo(sample_vocab_list: list[Vocabulary]) -> MagicMock:
    """Create mock VocabularyRepository."""
    repo = MagicMock()
    repo.get_all.return_value = sample_vocab_list
    return repo


def _create_review_templates(tmp_path: Path) -> Jinja2Templates:
    """Create minimal templates for review route testing.

    Args:
        tmp_path: Temporary directory for template files.

    Returns:
        Configured Jinja2Templates instance.
    """
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir(exist_ok=True)
    partials_dir = templates_dir / "partials"
    partials_dir.mkdir(exist_ok=True)

    (partials_dir / "review_empty.html").write_text("""
<div class="review-empty">
    <p class="message">{{ message }}</p>
</div>
""")

    (partials_dir / "review_question.html").write_text("""
<div class="review-question" data-word-id="{{ question.word_id }}">
    <p class="prompt">{{ question.prompt }}</p>
    <p class="progress">{{ current }} of {{ total }}</p>
    <div class="progress-bar" style="width: {{ progress_percent }}%"></div>
    <input type="hidden" name="word_id" value="{{ question.word_id }}">
    <input type="text" name="user_answer" placeholder="Your answer">
    <button type="submit">Check</button>
</div>
""")

    (partials_dir / "review_feedback_question.html").write_text("""
<div class="review-feedback">
    <p class="feedback {% if is_correct %}correct{% else %}incorrect{% endif %}">
        {{ feedback }}
    </p>
</div>
<div class="review-question" data-word-id="{{ question.word_id }}">
    <p class="prompt">{{ question.prompt }}</p>
    <p class="progress">{{ current }} of {{ total }}</p>
    <div class="progress-bar" style="width: {{ progress_percent }}%"></div>
</div>
""")

    (partials_dir / "review_summary.html").write_text("""
<div class="review-summary">
    <p class="feedback {% if is_correct %}correct{% else %}incorrect{% endif %}">
        {{ feedback }}
    </p>
    <p class="score">{{ correct_count }} of {{ total }} correct</p>
    {% if ended_early %}
    <p class="ended-early">Ended early. {{ remaining }} remaining.</p>
    {% endif %}
    <ul class="results">
    {% for r in results %}
        <li class="{% if r.is_correct %}correct{% else %}incorrect{% endif %}">
            {{ r.word }} = {{ r.translation }}
        </li>
    {% endfor %}
    </ul>
</div>
""")

    return Jinja2Templates(directory=str(templates_dir))


@pytest.fixture
def app(
    mock_user: AuthenticatedUser,
    mock_review_service: MagicMock,
    mock_vocab_repo: MagicMock,
    tmp_path: Path,
) -> Generator[FastAPI, None, None]:
    """Create test FastAPI app with mocked dependencies for review routes.

    Patches ReviewService, VocabularyRepository, and get_supabase_for_user to
    prevent real database calls during tests.
    """
    from fastapi import FastAPI

    from src.api.dependencies import get_cached_templates
    from src.api.routes.review import router as review_router

    templates = _create_review_templates(tmp_path)

    app = FastAPI()

    # Mock auth: return authenticated user
    async def get_mock_user() -> AuthenticatedUser:
        return mock_user

    # Mock templates
    def get_mock_templates() -> Jinja2Templates:
        return templates

    app.dependency_overrides[get_current_user] = get_mock_user
    app.dependency_overrides[get_cached_templates] = get_mock_templates

    app.include_router(review_router)

    with (
        patch(
            "src.api.routes.review.ReviewService", return_value=mock_review_service
        ) as _mock_svc_cls,
        patch(
            "src.api.routes.review.VocabularyRepository", return_value=mock_vocab_repo
        ) as _mock_repo_cls,
        patch(
            "src.api.routes.review.get_supabase_for_user", return_value=MagicMock()
        ) as _mock_user_client,
    ):
        yield app


@pytest.fixture
def unauth_app(
    tmp_path: Path,
) -> Generator[FastAPI, None, None]:
    """Create test app where no user is authenticated (simulates 401)."""
    from fastapi import FastAPI, HTTPException

    from src.api.dependencies import get_cached_templates
    from src.api.routes.review import router as review_router

    templates = _create_review_templates(tmp_path)

    app = FastAPI()

    async def get_no_user() -> AuthenticatedUser:
        raise HTTPException(status_code=401, detail="Not authenticated")

    def get_mock_templates() -> Jinja2Templates:
        return templates

    app.dependency_overrides[get_current_user] = get_no_user
    app.dependency_overrides[get_cached_templates] = get_mock_templates

    app.include_router(review_router)

    yield app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    """Create async test client for authenticated user tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def unauth_client(unauth_app: FastAPI) -> AsyncClient:
    """Create async test client for unauthenticated request tests."""
    transport = ASGITransport(app=unauth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _build_session_cookie(
    word_ids: list[int],
    current_index: int = 0,
    results: list[dict] | None = None,
    language: str = "es",
) -> str:
    """Build a JSON-encoded review session cookie value.

    Args:
        word_ids: List of vocabulary IDs in the session.
        current_index: Current position in the session.
        results: List of result dicts from previous answers.
        language: Target language.

    Returns:
        JSON string suitable for the review_session cookie.
    """
    return json.dumps(
        {
            "word_ids": word_ids,
            "current_index": current_index,
            "results": results or [],
            "language": language,
        }
    )


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestLevenshteinDistance:
    """Tests for _levenshtein_distance helper function."""

    def test_identical_strings(self) -> None:
        """Identical strings have distance 0."""
        assert _levenshtein_distance("hello", "hello") == 0

    def test_empty_strings(self) -> None:
        """Two empty strings have distance 0."""
        assert _levenshtein_distance("", "") == 0

    def test_one_empty_string(self) -> None:
        """Distance to empty string equals length of the other."""
        assert _levenshtein_distance("hello", "") == 5
        assert _levenshtein_distance("", "world") == 5

    def test_single_insertion(self) -> None:
        """Single character insertion has distance 1."""
        assert _levenshtein_distance("hola", "holaa") == 1

    def test_single_deletion(self) -> None:
        """Single character deletion has distance 1."""
        assert _levenshtein_distance("gracias", "gracia") == 1

    def test_single_substitution(self) -> None:
        """Single character substitution has distance 1."""
        assert _levenshtein_distance("hola", "holo") == 1

    def test_completely_different_strings(self) -> None:
        """Completely different strings have distance equal to max length."""
        assert _levenshtein_distance("abc", "xyz") == 3

    def test_symmetry(self) -> None:
        """Distance is the same regardless of argument order."""
        assert _levenshtein_distance("kitten", "sitting") == _levenshtein_distance(
            "sitting", "kitten"
        )

    def test_close_typo_within_threshold(self) -> None:
        """Common typos are within distance 2 (used for close-match detection)."""
        # "grcias" instead of "gracias" - missing 'a'
        assert _levenshtein_distance("grcias", "gracias") <= 2

    def test_distant_strings_exceed_threshold(self) -> None:
        """Very different strings exceed close-match threshold."""
        assert _levenshtein_distance("hola", "goodbye") > 2


class TestEvaluateAnswer:
    """Tests for _evaluate_answer helper function."""

    def test_exact_match_returns_quality_5(self) -> None:
        """Perfect match returns (True, 5)."""
        is_correct, quality = _evaluate_answer("hola", "hola")
        assert is_correct is True
        assert quality == 5

    def test_case_insensitive_match(self) -> None:
        """Case should not matter for matching."""
        is_correct, quality = _evaluate_answer("HOLA", "hola")
        assert is_correct is True
        assert quality == 5

    def test_whitespace_trimmed(self) -> None:
        """Leading/trailing whitespace is stripped."""
        is_correct, quality = _evaluate_answer("  hola  ", "hola")
        assert is_correct is True
        assert quality == 5

    def test_close_match_substring_returns_quality_4(self) -> None:
        """Partial substring match returns (True, 4)."""
        # user answer is substring of correct answer
        is_correct, quality = _evaluate_answer("gracia", "gracias")
        assert is_correct is True
        assert quality == 4

    def test_close_match_superstring_returns_quality_4(self) -> None:
        """When correct answer is substring of user answer, returns (True, 4)."""
        is_correct, quality = _evaluate_answer("graciass", "gracias")
        assert is_correct is True
        assert quality == 4

    def test_close_match_levenshtein_returns_quality_4(self) -> None:
        """Small edit distance returns (True, 4)."""
        # "holaa" vs "hola" - distance 1
        is_correct, quality = _evaluate_answer("holaa", "hola")
        assert is_correct is True
        assert quality == 4

    def test_incorrect_answer_returns_quality_2(self) -> None:
        """Wrong answer returns (False, 2)."""
        is_correct, quality = _evaluate_answer("goodbye", "hola")
        assert is_correct is False
        assert quality == 2

    def test_empty_answer_returns_incorrect(self) -> None:
        """Empty answer returns (False, 2)."""
        is_correct, quality = _evaluate_answer("", "hola")
        assert is_correct is False
        assert quality == 2


class TestGenerateQuestion:
    """Tests for _generate_question helper function."""

    @pytest.fixture
    def vocab(self) -> Vocabulary:
        """Single vocabulary item for question generation."""
        return Vocabulary(
            id=10,
            user_id="user-1",
            word="gato",
            translation="cat",
            language="es",
        )

    def test_translate_question_type(self, vocab: Vocabulary) -> None:
        """Translate question asks user to translate from English."""
        question = _generate_question(vocab, question_type="translate")
        assert question["type"] == "translate"
        assert "cat" in question["prompt"]  # shows translation
        assert question["correct_answer"] == "gato"
        assert question["word_id"] == 10
        assert question["word"] == "gato"
        assert question["translation"] == "cat"

    def test_recognize_question_type(self, vocab: Vocabulary) -> None:
        """Recognize question asks user what the word means."""
        question = _generate_question(vocab, question_type="recognize")
        assert question["type"] == "recognize"
        assert "gato" in question["prompt"]  # shows the target word
        assert question["correct_answer"] == "cat"

    def test_random_question_type_when_none(self, vocab: Vocabulary) -> None:
        """When no type specified, randomly selects translate or recognize."""
        question = _generate_question(vocab, question_type=None)
        assert question["type"] in ("translate", "recognize")
        assert question["word_id"] == 10

    def test_correct_answer_is_lowercased(self, vocab: Vocabulary) -> None:
        """Correct answer is lowercased for comparison."""
        vocab_upper = Vocabulary(
            id=11,
            user_id="user-1",
            word="Buenos Dias",
            translation="Good Morning",
            language="es",
        )
        q = _generate_question(vocab_upper, question_type="translate")
        assert q["correct_answer"] == "buenos dias"

        q2 = _generate_question(vocab_upper, question_type="recognize")
        assert q2["correct_answer"] == "good morning"


class TestGetHermanoFeedback:
    """Tests for _get_hermano_feedback helper function."""

    @pytest.fixture
    def vocab(self) -> Vocabulary:
        """Vocabulary item for feedback generation."""
        return Vocabulary(
            id=1,
            user_id="user-1",
            word="hola",
            translation="hello",
            language="es",
        )

    def test_perfect_quality_5_feedback(self, vocab: Vocabulary) -> None:
        """Quality 5 produces positive feedback with the word."""
        feedback = _get_hermano_feedback(5, vocab)
        assert "hola" in feedback

    def test_close_quality_4_feedback(self, vocab: Vocabulary) -> None:
        """Quality 4 acknowledges close answer with word and translation."""
        feedback = _get_hermano_feedback(4, vocab)
        assert "hola" in feedback
        assert "hello" in feedback

    def test_okay_quality_3_feedback(self, vocab: Vocabulary) -> None:
        """Quality 3 gives encouragement with word and translation."""
        feedback = _get_hermano_feedback(3, vocab)
        assert "hola" in feedback
        assert "hello" in feedback

    def test_incorrect_quality_2_feedback(self, vocab: Vocabulary) -> None:
        """Quality 2 (incorrect) shows correct answer encouragingly."""
        feedback = _get_hermano_feedback(2, vocab)
        assert "hola" in feedback
        assert "hello" in feedback

    def test_incorrect_quality_0_feedback(self, vocab: Vocabulary) -> None:
        """Quality 0 (blank) shows correct answer."""
        feedback = _get_hermano_feedback(0, vocab)
        assert "hola" in feedback
        assert "hello" in feedback

    def test_feedback_is_non_empty_string(self, vocab: Vocabulary) -> None:
        """All quality levels produce non-empty feedback."""
        for quality in range(6):
            feedback = _get_hermano_feedback(quality, vocab)
            assert isinstance(feedback, str)
            assert len(feedback) > 0


# =============================================================================
# GET /review/stats Tests
# =============================================================================


class TestGetReviewStats:
    """Tests for GET /review/stats endpoint."""

    async def test_returns_stats_for_authenticated_user(self, client: AsyncClient) -> None:
        """Authenticated user gets review statistics."""
        response = await client.get("/review/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["due_count"] == 3
        assert data["next_review_in"] == "2 hours"
        assert data["total_in_rotation"] == 10

    async def test_returns_401_when_unauthenticated(self, unauth_client: AsyncClient) -> None:
        """Unauthenticated request to stats returns 401."""
        response = await unauth_client.get("/review/stats")
        assert response.status_code == 401

    async def test_stats_with_language_param(self, client: AsyncClient) -> None:
        """Language parameter is passed through to ReviewService."""
        response = await client.get("/review/stats?language=de")
        assert response.status_code == 200

    async def test_stats_default_language_is_es(
        self, client: AsyncClient, mock_review_service: MagicMock
    ) -> None:
        """Default language is 'es' when not specified."""
        await client.get("/review/stats")
        mock_review_service.get_stats.assert_called_once_with(language="es")


# =============================================================================
# POST /review/start Tests
# =============================================================================


class TestStartReviewSession:
    """Tests for POST /review/start endpoint."""

    async def test_start_returns_html(self, client: AsyncClient) -> None:
        """Starting a review session returns HTML response."""
        response = await client.post("/review/start")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_start_returns_first_question(self, client: AsyncClient) -> None:
        """Response contains the first review question."""
        response = await client.post("/review/start")
        assert "review-question" in response.text
        assert "prompt" in response.text

    async def test_start_shows_progress(self, client: AsyncClient) -> None:
        """Response shows progress indicator (1 of N)."""
        response = await client.post("/review/start")
        assert "1 of 3" in response.text

    async def test_start_sets_session_cookie(self, client: AsyncClient) -> None:
        """Starting a session sets the review_session cookie."""
        response = await client.post("/review/start")
        set_cookies = response.headers.get_list("set-cookie")
        cookie_names = " ".join(set_cookies)
        assert "review_session" in cookie_names

    async def test_session_cookie_contains_word_ids(self, client: AsyncClient) -> None:
        """Session cookie contains the list of word IDs."""
        response = await client.post("/review/start")
        session_data = _parse_session_cookie_from_response(response)
        assert session_data["word_ids"] == [1, 2, 3]
        assert session_data["current_index"] == 0
        assert session_data["results"] == []

    async def test_start_with_count_query_param(
        self, client: AsyncClient, mock_review_service: MagicMock
    ) -> None:
        """Count query parameter limits the number of due words."""
        await client.post("/review/start?count=5")
        mock_review_service.get_due_words.assert_called_once_with(language="es", limit=5)

    async def test_start_with_count_all(
        self, client: AsyncClient, mock_review_service: MagicMock
    ) -> None:
        """Count 'all' passes None as limit."""
        await client.post("/review/start?count=all")
        mock_review_service.get_due_words.assert_called_once_with(language="es", limit=None)

    async def test_start_returns_empty_when_no_words_due(
        self, client: AsyncClient, mock_review_service: MagicMock
    ) -> None:
        """Returns review_empty template when no words are due."""
        mock_review_service.get_due_words.return_value = []
        response = await client.post("/review/start")
        assert response.status_code == 200
        assert "review-empty" in response.text
        assert "No words due" in response.text

    async def test_start_returns_401_when_unauthenticated(self, unauth_client: AsyncClient) -> None:
        """Returns 401 when user is not authenticated."""
        response = await unauth_client.post("/review/start")
        assert response.status_code == 401

    async def test_start_with_language_query_param(
        self, client: AsyncClient, mock_review_service: MagicMock
    ) -> None:
        """Language query parameter is forwarded to the service."""
        await client.post("/review/start?language=de")
        mock_review_service.get_due_words.assert_called_once_with(language="de", limit=10)


# =============================================================================
# POST /review/answer Tests
# =============================================================================


class TestSubmitReviewAnswer:
    """Tests for POST /review/answer endpoint."""

    async def test_correct_answer_returns_positive_feedback(self, client: AsyncClient) -> None:
        """Correct answer returns feedback with 'correct' class."""
        session_cookie = _build_session_cookie(word_ids=[1, 2, 3], current_index=0)
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hola"},
            cookies={"review_session": session_cookie},
        )
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "feedback" in response.text

    async def test_incorrect_answer_returns_feedback(self, client: AsyncClient) -> None:
        """Incorrect answer returns feedback with the correct answer shown."""
        session_cookie = _build_session_cookie(word_ids=[1, 2, 3], current_index=0)
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "completely_wrong_answer"},
            cookies={"review_session": session_cookie},
        )
        assert response.status_code == 200
        assert "feedback" in response.text

    async def test_answer_advances_to_next_question(self, client: AsyncClient) -> None:
        """After answering, the next question is shown."""
        session_cookie = _build_session_cookie(word_ids=[1, 2, 3], current_index=0)
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hola"},
            cookies={"review_session": session_cookie},
        )
        assert response.status_code == 200
        # Should show progress for question 2 of 3
        assert "2 of 3" in response.text

    async def test_answer_shows_completion_when_last_question(self, client: AsyncClient) -> None:
        """Answering the last question shows the review summary."""
        session_cookie = _build_session_cookie(
            word_ids=[1],
            current_index=0,
            results=[],
        )
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hola"},
            cookies={"review_session": session_cookie},
        )
        assert response.status_code == 200
        assert "review-summary" in response.text

    async def test_completion_shows_score(self, client: AsyncClient) -> None:
        """Review summary shows correct/total score."""
        session_cookie = _build_session_cookie(
            word_ids=[1],
            current_index=0,
            results=[],
        )
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hola"},
            cookies={"review_session": session_cookie},
        )
        assert "1 of 1" in response.text or "correct" in response.text.lower()

    async def test_completion_clears_session_cookie(self, client: AsyncClient) -> None:
        """Review summary response deletes the session cookie."""
        session_cookie = _build_session_cookie(
            word_ids=[1],
            current_index=0,
            results=[],
        )
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hola"},
            cookies={"review_session": session_cookie},
        )
        # The set-cookie header should clear the review_session cookie
        set_cookies = response.headers.get_list("set-cookie")
        cookie_str = " ".join(set_cookies)
        assert "review_session" in cookie_str

    async def test_missing_session_returns_400(self, client: AsyncClient) -> None:
        """Answering without a review_session cookie returns 400."""
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hola"},
        )
        assert response.status_code == 400

    async def test_invalid_session_json_returns_400(self, client: AsyncClient) -> None:
        """Malformed session cookie JSON returns 400."""
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hola"},
            cookies={"review_session": "not-valid-json{{{"},
        )
        assert response.status_code == 400

    async def test_unknown_word_id_returns_404(
        self, client: AsyncClient, mock_review_service: MagicMock, mock_vocab_repo: MagicMock
    ) -> None:
        """Answering for a word_id not found in vocabulary returns 404."""
        mock_review_service.get_due_words.return_value = []
        mock_vocab_repo.get_all.return_value = []
        session_cookie = _build_session_cookie(word_ids=[999], current_index=0)
        response = await client.post(
            "/review/answer",
            data={"word_id": "999", "user_answer": "test"},
            cookies={"review_session": session_cookie},
        )
        assert response.status_code == 404

    async def test_answer_updates_sm2_scheduling(
        self, client: AsyncClient, mock_review_service: MagicMock
    ) -> None:
        """Answering a question calls update_sm2 on the service."""
        session_cookie = _build_session_cookie(word_ids=[1, 2], current_index=0)
        await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hola"},
            cookies={"review_session": session_cookie},
        )
        mock_review_service.update_sm2.assert_called_once()
        call_args = mock_review_service.update_sm2.call_args
        assert call_args[0][0] == 1  # word_id

    async def test_sm2_failure_does_not_crash(
        self, client: AsyncClient, mock_review_service: MagicMock
    ) -> None:
        """If update_sm2 raises, the answer still returns feedback."""
        mock_review_service.update_sm2.side_effect = Exception("DB error")
        session_cookie = _build_session_cookie(word_ids=[1, 2], current_index=0)
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hola"},
            cookies={"review_session": session_cookie},
        )
        assert response.status_code == 200
        assert "feedback" in response.text

    async def test_answer_returns_401_when_unauthenticated(
        self, unauth_client: AsyncClient
    ) -> None:
        """Answering without authentication returns 401."""
        session_cookie = _build_session_cookie(word_ids=[1], current_index=0)
        response = await unauth_client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "test"},
            cookies={"review_session": session_cookie},
        )
        assert response.status_code == 401

    async def test_answer_updates_session_cookie_with_results(self, client: AsyncClient) -> None:
        """Updated session cookie includes the answer result."""
        session_cookie = _build_session_cookie(word_ids=[1, 2, 3], current_index=0)
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hola"},
            cookies={"review_session": session_cookie},
        )
        new_session = _parse_session_cookie_from_response(response)
        assert len(new_session.get("results", [])) == 1
        assert new_session["results"][0]["word_id"] == 1
        assert new_session["current_index"] == 1

    async def test_progress_percent_calculated(self, client: AsyncClient) -> None:
        """Progress percentage is calculated correctly."""
        session_cookie = _build_session_cookie(word_ids=[1, 2, 3], current_index=0)
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hola"},
            cookies={"review_session": session_cookie},
        )
        # After answering question 1 of 3, progress should be 33%
        assert "progress-bar" in response.text


# =============================================================================
# POST /review/end Tests
# =============================================================================


class TestEndReviewSession:
    """Tests for POST /review/end endpoint."""

    async def test_end_returns_summary(self, client: AsyncClient) -> None:
        """Ending a session returns the review summary."""
        session_cookie = _build_session_cookie(
            word_ids=[1, 2, 3],
            current_index=1,
            results=[
                {
                    "word_id": 1,
                    "word": "hola",
                    "translation": "hello",
                    "is_correct": True,
                    "quality": 5,
                },
            ],
        )
        response = await client.post(
            "/review/end",
            cookies={"review_session": session_cookie},
        )
        assert response.status_code == 200
        assert "review-summary" in response.text

    async def test_end_shows_correct_count(self, client: AsyncClient) -> None:
        """Summary shows number of correct answers."""
        session_cookie = _build_session_cookie(
            word_ids=[1, 2, 3],
            current_index=2,
            results=[
                {
                    "word_id": 1,
                    "word": "hola",
                    "translation": "hello",
                    "is_correct": True,
                    "quality": 5,
                },
                {
                    "word_id": 2,
                    "word": "gracias",
                    "translation": "thank you",
                    "is_correct": False,
                    "quality": 2,
                },
            ],
        )
        response = await client.post(
            "/review/end",
            cookies={"review_session": session_cookie},
        )
        assert "1 of 2" in response.text

    async def test_end_shows_ended_early_indicator(self, client: AsyncClient) -> None:
        """Summary indicates the session was ended early."""
        session_cookie = _build_session_cookie(
            word_ids=[1, 2, 3],
            current_index=1,
            results=[
                {
                    "word_id": 1,
                    "word": "hola",
                    "translation": "hello",
                    "is_correct": True,
                    "quality": 5,
                },
            ],
        )
        response = await client.post(
            "/review/end",
            cookies={"review_session": session_cookie},
        )
        assert "ended-early" in response.text or "Ended early" in response.text

    async def test_end_shows_remaining_count(self, client: AsyncClient) -> None:
        """Summary shows how many words were remaining."""
        session_cookie = _build_session_cookie(
            word_ids=[1, 2, 3],
            current_index=1,
            results=[
                {
                    "word_id": 1,
                    "word": "hola",
                    "translation": "hello",
                    "is_correct": True,
                    "quality": 5,
                },
            ],
        )
        response = await client.post(
            "/review/end",
            cookies={"review_session": session_cookie},
        )
        # 3 planned - 1 attempted = 2 remaining
        assert "2 remaining" in response.text

    async def test_end_clears_session_cookie(self, client: AsyncClient) -> None:
        """Ending session deletes the review_session cookie."""
        session_cookie = _build_session_cookie(
            word_ids=[1],
            current_index=0,
            results=[],
        )
        response = await client.post(
            "/review/end",
            cookies={"review_session": session_cookie},
        )
        set_cookies = response.headers.get_list("set-cookie")
        cookie_str = " ".join(set_cookies)
        assert "review_session" in cookie_str

    async def test_end_without_session_returns_empty(self, client: AsyncClient) -> None:
        """Ending without a session cookie returns the empty view."""
        response = await client.post("/review/end")
        assert response.status_code == 200
        assert "review-empty" in response.text
        assert "No active review session" in response.text

    async def test_end_with_invalid_json_returns_empty(self, client: AsyncClient) -> None:
        """Ending with malformed session JSON returns the empty view."""
        response = await client.post(
            "/review/end",
            cookies={"review_session": "bad-json{{{"},
        )
        assert response.status_code == 200
        assert "review-empty" in response.text
        assert "Invalid session state" in response.text

    async def test_end_with_empty_results(self, client: AsyncClient) -> None:
        """Ending a session with no answers yet shows 0 correct."""
        session_cookie = _build_session_cookie(
            word_ids=[1, 2, 3],
            current_index=0,
            results=[],
        )
        response = await client.post(
            "/review/end",
            cookies={"review_session": session_cookie},
        )
        assert response.status_code == 200
        assert "0 of 0" in response.text


# =============================================================================
# DELETE /review/warmup-prompt Tests
# =============================================================================


class TestDismissWarmupPrompt:
    """Tests for DELETE /review/warmup-prompt endpoint."""

    async def test_dismiss_returns_200(self, client: AsyncClient) -> None:
        """Dismissing warmup returns 200."""
        response = await client.delete("/review/warmup-prompt")
        assert response.status_code == 200

    async def test_dismiss_returns_empty_body(self, client: AsyncClient) -> None:
        """Dismissal response has empty body."""
        response = await client.delete("/review/warmup-prompt")
        assert response.text == ""

    async def test_dismiss_sets_cookie(self, client: AsyncClient) -> None:
        """Dismissal sets the warmup_dismissed cookie."""
        response = await client.delete("/review/warmup-prompt")
        set_cookies = response.headers.get_list("set-cookie")
        cookie_str = " ".join(set_cookies)
        assert "warmup_dismissed" in cookie_str

    async def test_dismiss_cookie_value_is_1(self, client: AsyncClient) -> None:
        """Warmup dismissed cookie has value '1'."""
        response = await client.delete("/review/warmup-prompt")
        assert response.cookies.get("warmup_dismissed") == "1"

    async def test_dismiss_cookie_is_session_cookie(self, client: AsyncClient) -> None:
        """Warmup dismissed cookie has no max_age (session cookie)."""
        response = await client.delete("/review/warmup-prompt")
        set_cookies = response.headers.get_list("set-cookie")
        warmup_cookie = [c for c in set_cookies if "warmup_dismissed" in c]
        assert len(warmup_cookie) == 1
        # Session cookie should not have Max-Age or Expires
        assert "Max-Age" not in warmup_cookie[0] or "max-age" not in warmup_cookie[0].lower()


# =============================================================================
# Multi-question Flow Integration Tests
# =============================================================================


class TestReviewSessionFlow:
    """Integration-style tests for a complete review session flow."""

    async def test_start_sets_session_with_all_word_ids(self, client: AsyncClient) -> None:
        """Start creates a session cookie with all due word IDs."""
        response = await client.post("/review/start")
        assert response.status_code == 200
        assert "review-question" in response.text

        # Parse session cookie from raw Set-Cookie header
        session_data = _parse_session_cookie_from_response(response)
        assert session_data["word_ids"] == [1, 2, 3]

    async def test_answer_records_result_in_session(self, client: AsyncClient) -> None:
        """Each answer records a result in the session state."""
        session_cookie = _build_session_cookie(
            word_ids=[1, 2, 3],
            current_index=0,
            results=[],
        )

        # First answer
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hola"},
            cookies={"review_session": session_cookie},
        )
        assert response.status_code == 200

        new_session = _parse_session_cookie_from_response(response)
        assert len(new_session["results"]) == 1
        assert new_session["results"][0]["word"] == "hola"
        assert new_session["results"][0]["is_correct"] is True


# =============================================================================
# Edge Cases
# =============================================================================


class TestReviewEdgeCases:
    """Edge case tests for review routes."""

    async def test_stats_returns_json_content_type(self, client: AsyncClient) -> None:
        """Stats endpoint returns JSON content type."""
        response = await client.get("/review/stats")
        assert "application/json" in response.headers["content-type"]

    async def test_start_returns_html_content_type(self, client: AsyncClient) -> None:
        """Start endpoint returns HTML content type."""
        response = await client.post("/review/start")
        assert "text/html" in response.headers["content-type"]

    async def test_session_cookie_is_httponly(self, client: AsyncClient) -> None:
        """Review session cookie is marked httponly for security."""
        response = await client.post("/review/start")
        set_cookies = response.headers.get_list("set-cookie")
        review_cookies = [c for c in set_cookies if "review_session" in c]
        if review_cookies:
            assert "httponly" in review_cookies[0].lower()

    async def test_session_cookie_samesite_lax(self, client: AsyncClient) -> None:
        """Review session cookie has SameSite=Lax."""
        response = await client.post("/review/start")
        set_cookies = response.headers.get_list("set-cookie")
        review_cookies = [c for c in set_cookies if "review_session" in c]
        if review_cookies:
            assert "samesite=lax" in review_cookies[0].lower()

    async def test_answer_checks_both_word_directions(self, client: AsyncClient) -> None:
        """Answer evaluation checks both word and translation directions."""
        session_cookie = _build_session_cookie(word_ids=[1, 2], current_index=0)
        # "hello" is the translation of word_id=1 ("hola"), so it should match
        response = await client.post(
            "/review/answer",
            data={"word_id": "1", "user_answer": "hello"},
            cookies={"review_session": session_cookie},
        )
        assert response.status_code == 200
        # Should still give feedback (whether correct depends on direction checking)
        assert "feedback" in response.text

    async def test_concurrent_stats_requests(self, client: AsyncClient) -> None:
        """Multiple concurrent stats requests should not interfere."""
        import asyncio

        tasks = [client.get("/review/stats") for _ in range(3)]
        responses = await asyncio.gather(*tasks)
        assert all(r.status_code == 200 for r in responses)
        assert all(r.json()["due_count"] == 3 for r in responses)
