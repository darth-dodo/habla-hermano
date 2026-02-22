"""Tests for database repository module.

Tests for Supabase data access layer with mocked client.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from postgrest.exceptions import APIError

from src.db.models import LearningSession, LessonProgress, UserProfile, Vocabulary
from src.db.repository import (
    LearningSessionRepository,
    LessonProgressRepository,
    UserProfileRepository,
    VocabularyRepository,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_supabase() -> MagicMock:
    """Create a mock Supabase client."""
    return MagicMock()


@pytest.fixture
def mock_get_supabase(mock_supabase: MagicMock):
    """Patch get_supabase to return mock client."""
    with patch("src.db.repository.get_supabase", return_value=mock_supabase):
        yield mock_supabase


# =============================================================================
# UserProfileRepository Tests
# =============================================================================


class TestUserProfileRepository:
    """Tests for UserProfileRepository class."""

    def test_init_stores_user_id(self, mock_get_supabase: MagicMock) -> None:
        """Test repository stores user_id."""
        repo = UserProfileRepository("user-123")

        assert repo._user_id == "user-123"

    def test_get_returns_profile(self, mock_get_supabase: MagicMock) -> None:
        """Test get returns UserProfile when found."""
        mock_get_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "user-123",
                    "display_name": "Test User",
                    "preferred_language": "es",
                    "current_level": "A1",
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ]
        )

        repo = UserProfileRepository("user-123")
        result = repo.get()

        assert result is not None
        assert isinstance(result, UserProfile)
        assert result.id == "user-123"
        assert result.display_name == "Test User"

    def test_get_returns_none_when_not_found(self, mock_get_supabase: MagicMock) -> None:
        """Test get returns None when profile not found."""
        mock_get_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        repo = UserProfileRepository("user-123")
        result = repo.get()

        assert result is None

    def test_update_with_display_name(self, mock_get_supabase: MagicMock) -> None:
        """Test update with display_name."""
        mock_get_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "user-123",
                    "display_name": "New Name",
                    "preferred_language": "es",
                    "current_level": "A1",
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ]
        )

        repo = UserProfileRepository("user-123")
        result = repo.update(display_name="New Name")

        assert result is not None
        assert result.display_name == "New Name"

    def test_update_with_preferred_language(self, mock_get_supabase: MagicMock) -> None:
        """Test update with preferred_language."""
        mock_get_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "user-123",
                    "display_name": None,
                    "preferred_language": "de",
                    "current_level": "A1",
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ]
        )

        repo = UserProfileRepository("user-123")
        result = repo.update(preferred_language="de")

        assert result is not None
        assert result.preferred_language == "de"

    def test_update_with_current_level(self, mock_get_supabase: MagicMock) -> None:
        """Test update with current_level."""
        mock_get_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "user-123",
                    "display_name": None,
                    "preferred_language": "es",
                    "current_level": "B1",
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ]
        )

        repo = UserProfileRepository("user-123")
        result = repo.update(current_level="B1")

        assert result is not None
        assert result.current_level == "B1"

    def test_update_returns_none_when_not_found(self, mock_get_supabase: MagicMock) -> None:
        """Test update returns None when profile not found."""
        mock_get_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        repo = UserProfileRepository("user-123")
        result = repo.update(display_name="New Name")

        assert result is None


# =============================================================================
# VocabularyRepository Tests
# =============================================================================


class TestVocabularyRepository:
    """Tests for VocabularyRepository class."""

    def test_init_stores_user_id(self, mock_get_supabase: MagicMock) -> None:
        """Test repository stores user_id."""
        repo = VocabularyRepository("user-123")

        assert repo._user_id == "user-123"

    def test_get_all_returns_vocabulary_list(self, mock_get_supabase: MagicMock) -> None:
        """Test get_all returns list of Vocabulary."""
        # Mock the chain: table().select().eq(user_id).order().execute()
        mock_query = MagicMock()
        mock_get_supabase.table.return_value.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.execute.return_value = MagicMock(
            data=[
                {
                    "id": 1,
                    "user_id": "user-123",
                    "word": "hola",
                    "translation": "hello",
                    "language": "es",
                    "part_of_speech": "interjection",
                    "first_seen_at": datetime.now(UTC).isoformat(),
                    "times_seen": 5,
                    "times_correct": 3,
                },
                {
                    "id": 2,
                    "user_id": "user-123",
                    "word": "adiós",
                    "translation": "goodbye",
                    "language": "es",
                    "part_of_speech": "interjection",
                    "first_seen_at": datetime.now(UTC).isoformat(),
                    "times_seen": 3,
                    "times_correct": 2,
                },
            ]
        )

        repo = VocabularyRepository("user-123")
        result = repo.get_all()

        assert len(result) == 2
        assert all(isinstance(v, Vocabulary) for v in result)
        assert result[0].word == "hola"
        assert result[1].word == "adiós"

    def test_get_all_with_language_filter(self, mock_get_supabase: MagicMock) -> None:
        """Test get_all with language filter."""
        # Mock the chain: table().select().eq(user_id).order().eq(language).execute()
        mock_query = MagicMock()
        mock_get_supabase.table.return_value.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.execute.return_value = MagicMock(
            data=[
                {
                    "id": 1,
                    "user_id": "user-123",
                    "word": "hola",
                    "translation": "hello",
                    "language": "es",
                    "part_of_speech": None,
                    "first_seen_at": datetime.now(UTC).isoformat(),
                    "times_seen": 1,
                    "times_correct": 0,
                }
            ]
        )

        repo = VocabularyRepository("user-123")
        result = repo.get_all(language="es")

        assert len(result) == 1
        assert result[0].language == "es"

    def test_get_all_returns_empty_list(self, mock_get_supabase: MagicMock) -> None:
        """Test get_all returns empty list when no vocabulary."""
        # Mock the chain: table().select().eq(user_id).order().execute()
        mock_query = MagicMock()
        mock_get_supabase.table.return_value.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[])

        repo = VocabularyRepository("user-123")
        result = repo.get_all()

        assert result == []


# =============================================================================
# VocabularyRepository.upsert() Tests
# =============================================================================


class TestVocabularyUpsert:
    """Tests for VocabularyRepository.upsert() race-condition-safe implementation."""

    def test_upsert_inserts_new_word(self, mock_get_supabase: MagicMock) -> None:
        """Insert succeeds on first attempt for a new word."""
        mock_query = _chainable_query(mock_get_supabase)
        new_row = _make_vocab_row("hola", "hello", word_id=1)
        mock_query.execute.return_value = MagicMock(data=[new_row])

        repo = VocabularyRepository("user-123")
        result = repo.upsert("hola", "hello", "es", part_of_speech="interjection")

        assert isinstance(result, Vocabulary)
        assert result.word == "hola"
        assert result.times_seen == 1
        mock_query.insert.assert_called_once()
        call_data = mock_query.insert.call_args[0][0]
        assert call_data["word"] == "hola"
        assert call_data["times_seen"] == 1
        assert call_data["times_correct"] == 0

    def test_upsert_updates_on_duplicate_key(self, mock_get_supabase: MagicMock) -> None:
        """Insert fails with 23505, then falls back to read + update."""
        mock_query = _chainable_query(mock_get_supabase)

        existing_row = _make_vocab_row("hola", "hello", word_id=1, times_seen=3)
        updated_row = _make_vocab_row("hola", "hi", word_id=1, times_seen=4)

        # insert raises duplicate key error, then select returns existing,
        # then update returns updated row
        mock_query.execute.side_effect = [
            APIError({"code": "23505", "message": "duplicate key", "hint": None, "details": None}),
            MagicMock(data=[existing_row]),  # get_by_word_and_language
            MagicMock(data=[updated_row]),   # update
        ]

        # Override insert to raise the APIError
        def _raise_on_execute():
            raise _make_api_error()

        # Reset the mock - insert().execute() should raise
        mock_insert_chain = MagicMock()
        mock_query.insert.return_value = mock_insert_chain
        mock_insert_chain.execute.side_effect = _make_api_error()

        # select chain returns existing row
        mock_select_chain = MagicMock()
        mock_query.select.return_value = mock_select_chain
        mock_select_chain.eq.return_value = mock_select_chain
        mock_select_chain.execute.return_value = MagicMock(data=[existing_row])

        # update chain returns updated row
        mock_update_chain = MagicMock()
        mock_query.update.return_value = mock_update_chain
        mock_update_chain.eq.return_value = mock_update_chain
        mock_update_chain.execute.return_value = MagicMock(data=[updated_row])

        repo = VocabularyRepository("user-123")
        result = repo.upsert("hola", "hi", "es")

        assert isinstance(result, Vocabulary)
        assert result.times_seen == 4
        mock_query.insert.assert_called_once()
        mock_query.update.assert_called_once()
        update_data = mock_query.update.call_args[0][0]
        assert update_data["translation"] == "hi"
        assert update_data["times_seen"] == 4

    def test_upsert_reraises_non_duplicate_api_error(
        self, mock_get_supabase: MagicMock
    ) -> None:
        """Non-23505 APIError is not swallowed."""
        mock_query = _chainable_query(mock_get_supabase)

        mock_insert_chain = MagicMock()
        mock_query.insert.return_value = mock_insert_chain
        mock_insert_chain.execute.side_effect = _make_api_error(
            code="42501", message="permission denied"
        )

        repo = VocabularyRepository("user-123")

        with pytest.raises(APIError) as exc_info:
            repo.upsert("hola", "hello", "es")

        assert exc_info.value.code == "42501"

    def test_upsert_raises_runtime_error_if_missing_after_conflict(
        self, mock_get_supabase: MagicMock
    ) -> None:
        """RuntimeError raised if row vanishes between conflict and select."""
        mock_query = _chainable_query(mock_get_supabase)

        # insert raises duplicate key
        mock_insert_chain = MagicMock()
        mock_query.insert.return_value = mock_insert_chain
        mock_insert_chain.execute.side_effect = _make_api_error()

        # select returns empty (row was somehow deleted between conflict and read)
        mock_select_chain = MagicMock()
        mock_query.select.return_value = mock_select_chain
        mock_select_chain.eq.return_value = mock_select_chain
        mock_select_chain.execute.return_value = MagicMock(data=[])

        repo = VocabularyRepository("user-123")

        with pytest.raises(RuntimeError, match="not found after conflict"):
            repo.upsert("hola", "hello", "es")


# =============================================================================
# Repository Pattern Tests
# =============================================================================


class TestRepositoryPattern:
    """Tests for repository pattern implementation."""

    def test_user_profile_repo_uses_correct_table(self, mock_get_supabase: MagicMock) -> None:
        """Test UserProfileRepository uses user_profiles table."""
        mock_get_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        repo = UserProfileRepository("user-123")
        repo.get()

        mock_get_supabase.table.assert_called_with("user_profiles")

    def test_vocabulary_repo_uses_correct_table(self, mock_get_supabase: MagicMock) -> None:
        """Test VocabularyRepository uses vocabulary table."""
        mock_get_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        repo = VocabularyRepository("user-123")
        repo.get_all()

        mock_get_supabase.table.assert_called_with("vocabulary")

    def test_learning_session_repo_uses_correct_table(self, mock_get_supabase: MagicMock) -> None:
        """Test LearningSessionRepository uses learning_sessions table."""
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[])
        repo = LearningSessionRepository("user-123")
        repo.get_all()
        mock_get_supabase.table.assert_called_with("learning_sessions")

    def test_lesson_progress_repo_uses_correct_table(self, mock_get_supabase: MagicMock) -> None:
        """Test LessonProgressRepository uses lesson_progress table."""
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[])
        repo = LessonProgressRepository("user-123")
        repo.get_all()
        mock_get_supabase.table.assert_called_with("lesson_progress")


# =============================================================================
# Helpers
# =============================================================================

FIXED_NOW = datetime(2025, 6, 20, 12, 0, 0, tzinfo=UTC)
FIXED_NOW_ISO = FIXED_NOW.isoformat()


def _chainable_query(mock_client: MagicMock) -> MagicMock:
    """Create a chainable mock query that returns itself for any method call."""
    mock_query = MagicMock()
    mock_client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.insert.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.upsert.return_value = mock_query
    mock_query.delete.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.not_.return_value = mock_query
    mock_query.not_.is_.return_value = mock_query
    mock_query.is_.return_value = mock_query
    mock_query.lte.return_value = mock_query
    mock_query.gt.return_value = mock_query
    mock_query.or_.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query
    return mock_query


def _make_api_error(code: str = "23505", message: str = "duplicate key") -> APIError:
    """Build a postgrest APIError for testing conflict handling."""
    return APIError({"code": code, "message": message, "hint": None, "details": None})


def _make_vocab_row(
    word: str = "hola",
    translation: str = "hello",
    word_id: int = 1,
    next_review_at: str | None = None,
    last_reviewed_at: str | None = None,
    easiness_factor: float = 2.5,
    interval_days: int = 0,
    repetition_count: int = 0,
    times_seen: int = 1,
    times_correct: int = 0,
) -> dict:
    """Build a vocabulary row dict for mock responses."""
    return {
        "id": word_id,
        "user_id": "user-123",
        "word": word,
        "translation": translation,
        "language": "es",
        "part_of_speech": None,
        "first_seen_at": FIXED_NOW_ISO,
        "times_seen": times_seen,
        "times_correct": times_correct,
        "easiness_factor": easiness_factor,
        "interval_days": interval_days,
        "repetition_count": repetition_count,
        "next_review_at": next_review_at,
        "last_reviewed_at": last_reviewed_at,
    }


# =============================================================================
# VocabularyRepository Spaced Repetition Tests
# =============================================================================


class TestVocabularyRepositorySR:
    """Tests for VocabularyRepository spaced repetition methods."""

    def test_get_due_for_review_returns_vocab(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(
            data=[_make_vocab_row("gato", "cat", next_review_at=FIXED_NOW_ISO)]
        )
        repo = VocabularyRepository("user-123")
        result = repo.get_due_for_review("es")
        assert len(result) == 1
        assert isinstance(result[0], Vocabulary)
        assert result[0].word == "gato"

    def test_get_due_for_review_empty(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[])
        repo = VocabularyRepository("user-123")
        result = repo.get_due_for_review("es")
        assert result == []

    def test_get_due_by_keywords_empty_keywords(self, mock_get_supabase: MagicMock) -> None:
        repo = VocabularyRepository("user-123")
        result = repo.get_due_by_keywords("es", [], limit=5)
        assert result == []

    def test_get_due_by_keywords_matches_word(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(
            data=[
                _make_vocab_row("gato", "cat", word_id=1, next_review_at=FIXED_NOW_ISO),
            ]
        )
        repo = VocabularyRepository("user-123")
        result = repo.get_due_by_keywords("es", ["gato"])
        assert len(result) == 1
        assert result[0].word == "gato"
        mock_query.or_.assert_called_once_with(
            "word.ilike.%gato%,translation.ilike.%gato%"
        )

    def test_get_due_by_keywords_matches_translation(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(
            data=[
                _make_vocab_row("perro", "dog", word_id=2, next_review_at=FIXED_NOW_ISO),
            ]
        )
        repo = VocabularyRepository("user-123")
        result = repo.get_due_by_keywords("es", ["dog"])
        assert len(result) == 1
        assert result[0].word == "perro"
        mock_query.or_.assert_called_once_with(
            "word.ilike.%dog%,translation.ilike.%dog%"
        )

    def test_get_due_by_keywords_case_insensitive(self, mock_get_supabase: MagicMock) -> None:
        """ilike is case-insensitive in PostgreSQL, so the filter uses keywords as-is."""
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(
            data=[_make_vocab_row("Gato", "Cat", word_id=1, next_review_at=FIXED_NOW_ISO)]
        )
        repo = VocabularyRepository("user-123")
        result = repo.get_due_by_keywords("es", ["GATO"])
        assert len(result) == 1
        mock_query.or_.assert_called_once_with(
            "word.ilike.%GATO%,translation.ilike.%GATO%"
        )

    def test_get_due_by_keywords_no_matches(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[])
        repo = VocabularyRepository("user-123")
        result = repo.get_due_by_keywords("es", ["zzzzz"])
        assert result == []

    def test_get_due_by_keywords_respects_limit(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(
            data=[
                _make_vocab_row("gato", "cat", word_id=1, next_review_at=FIXED_NOW_ISO),
                _make_vocab_row("gata", "female cat", word_id=2, next_review_at=FIXED_NOW_ISO),
            ]
        )
        repo = VocabularyRepository("user-123")
        result = repo.get_due_by_keywords("es", ["gat"], limit=2)
        assert len(result) == 2
        mock_query.limit.assert_called_with(2)

    def test_get_due_by_keywords_multiple_keywords(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(
            data=[
                _make_vocab_row("gato", "cat", word_id=1, next_review_at=FIXED_NOW_ISO),
                _make_vocab_row("perro", "dog", word_id=2, next_review_at=FIXED_NOW_ISO),
            ]
        )
        repo = VocabularyRepository("user-123")
        result = repo.get_due_by_keywords("es", ["gato", "perro"])
        assert len(result) == 2
        mock_query.or_.assert_called_once_with(
            "word.ilike.%gato%,translation.ilike.%gato%,"
            "word.ilike.%perro%,translation.ilike.%perro%"
        )

    def test_update_review_schedule_with_direct_fields(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        updated_row = _make_vocab_row(
            "hola", "hello", easiness_factor=2.1, interval_days=6, repetition_count=3
        )
        mock_query.execute.return_value = MagicMock(data=[updated_row])
        repo = VocabularyRepository("user-123")
        result = repo.update_review_schedule(
            1,
            {
                "easiness_factor": 2.1,
                "interval_days": 6,
                "repetition_count": 3,
            },
        )
        assert result is not None
        assert result.easiness_factor == 2.1
        assert result.interval_days == 6

    def test_update_review_schedule_with_datetime_fields(
        self, mock_get_supabase: MagicMock
    ) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        updated_row = _make_vocab_row(
            "hola",
            "hello",
            next_review_at=FIXED_NOW_ISO,
            last_reviewed_at=FIXED_NOW_ISO,
        )
        mock_query.execute.return_value = MagicMock(data=[updated_row])
        repo = VocabularyRepository("user-123")
        result = repo.update_review_schedule(
            1,
            {
                "next_review_at": FIXED_NOW,
                "last_reviewed_at": FIXED_NOW,
            },
        )
        assert result is not None
        call_args = mock_query.update.call_args[0][0]
        assert call_args["next_review_at"] == FIXED_NOW_ISO

    def test_update_review_schedule_with_increment_seen(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        updated_row = _make_vocab_row("hola", "hello", times_seen=6)
        mock_query.execute.side_effect = [
            MagicMock(data=[{"times_seen": 5, "times_correct": 2}]),
            MagicMock(data=[updated_row]),
        ]
        repo = VocabularyRepository("user-123")
        result = repo.update_review_schedule(
            1,
            {
                "easiness_factor": 2.5,
                "increment_seen": True,
            },
        )
        assert result is not None
        call_args = mock_query.update.call_args[0][0]
        assert call_args["times_seen"] == 6

    def test_update_review_schedule_with_increment_correct(
        self, mock_get_supabase: MagicMock
    ) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        updated_row = _make_vocab_row("hola", "hello", times_correct=3)
        mock_query.execute.side_effect = [
            MagicMock(data=[{"times_seen": 5, "times_correct": 2}]),
            MagicMock(data=[updated_row]),
        ]
        repo = VocabularyRepository("user-123")
        result = repo.update_review_schedule(
            1,
            {
                "easiness_factor": 2.5,
                "increment_correct": True,
            },
        )
        assert result is not None
        call_args = mock_query.update.call_args[0][0]
        assert call_args["times_correct"] == 3

    def test_update_review_schedule_with_both_increments(
        self, mock_get_supabase: MagicMock
    ) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        updated_row = _make_vocab_row("hola", "hello", times_seen=6, times_correct=3)
        mock_query.execute.side_effect = [
            MagicMock(data=[{"times_seen": 5, "times_correct": 2}]),
            MagicMock(data=[updated_row]),
        ]
        repo = VocabularyRepository("user-123")
        result = repo.update_review_schedule(
            1,
            {
                "increment_seen": True,
                "increment_correct": True,
            },
        )
        assert result is not None
        call_args = mock_query.update.call_args[0][0]
        assert call_args["times_seen"] == 6
        assert call_args["times_correct"] == 3

    def test_update_review_schedule_increment_no_data(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        updated_row = _make_vocab_row("hola", "hello", easiness_factor=2.0)
        mock_query.execute.side_effect = [
            MagicMock(data=[]),  # No current data found
            MagicMock(data=[updated_row]),
        ]
        repo = VocabularyRepository("user-123")
        result = repo.update_review_schedule(
            1,
            {
                "easiness_factor": 2.0,
                "increment_seen": True,
            },
        )
        assert result is not None
        call_args = mock_query.update.call_args[0][0]
        assert "times_seen" not in call_args

    def test_update_review_schedule_empty_updates(self, mock_get_supabase: MagicMock) -> None:
        repo = VocabularyRepository("user-123")
        result = repo.update_review_schedule(1, {})
        assert result is None

    def test_update_review_schedule_only_increment_not_found(
        self, mock_get_supabase: MagicMock
    ) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[])
        repo = VocabularyRepository("user-123")
        result = repo.update_review_schedule(1, {"increment_seen": True})
        assert result is None

    def test_update_review_schedule_returns_none_on_empty(
        self, mock_get_supabase: MagicMock
    ) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[])
        repo = VocabularyRepository("user-123")
        result = repo.update_review_schedule(1, {"easiness_factor": 2.0})
        assert result is None

    def test_build_review_update_data_direct_fields(self, mock_get_supabase: MagicMock) -> None:
        repo = VocabularyRepository("user-123")
        result = repo._build_review_update_data(
            {
                "easiness_factor": 1.8,
                "interval_days": 10,
                "repetition_count": 4,
            }
        )
        assert result == {"easiness_factor": 1.8, "interval_days": 10, "repetition_count": 4}

    def test_build_review_update_data_datetime_conversion(
        self, mock_get_supabase: MagicMock
    ) -> None:
        repo = VocabularyRepository("user-123")
        result = repo._build_review_update_data(
            {
                "next_review_at": FIXED_NOW,
                "last_reviewed_at": FIXED_NOW,
            }
        )
        assert result["next_review_at"] == FIXED_NOW_ISO
        assert result["last_reviewed_at"] == FIXED_NOW_ISO

    def test_build_review_update_data_string_passthrough(
        self, mock_get_supabase: MagicMock
    ) -> None:
        repo = VocabularyRepository("user-123")
        result = repo._build_review_update_data({"next_review_at": FIXED_NOW_ISO})
        assert result["next_review_at"] == FIXED_NOW_ISO

    def test_build_review_update_data_ignores_unknown(self, mock_get_supabase: MagicMock) -> None:
        repo = VocabularyRepository("user-123")
        result = repo._build_review_update_data({"increment_seen": True, "unknown_field": "foo"})
        assert result == {}

    def test_build_review_update_data_empty(self, mock_get_supabase: MagicMock) -> None:
        repo = VocabularyRepository("user-123")
        result = repo._build_review_update_data({})
        assert result == {}

    def test_apply_increment_flags_seen(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[{"times_seen": 10, "times_correct": 5}])
        repo = VocabularyRepository("user-123")
        update_data: dict = {}
        repo._apply_increment_flags(1, {"increment_seen": True}, update_data)
        assert update_data["times_seen"] == 11

    def test_apply_increment_flags_correct(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[{"times_seen": 10, "times_correct": 5}])
        repo = VocabularyRepository("user-123")
        update_data: dict = {}
        repo._apply_increment_flags(1, {"increment_correct": True}, update_data)
        assert update_data["times_correct"] == 6

    def test_apply_increment_flags_both(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[{"times_seen": 10, "times_correct": 5}])
        repo = VocabularyRepository("user-123")
        update_data: dict = {}
        repo._apply_increment_flags(
            1, {"increment_seen": True, "increment_correct": True}, update_data
        )
        assert update_data["times_seen"] == 11
        assert update_data["times_correct"] == 6

    def test_apply_increment_flags_no_data(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[])
        repo = VocabularyRepository("user-123")
        update_data: dict = {"easiness_factor": 2.0}
        repo._apply_increment_flags(1, {"increment_seen": True}, update_data)
        assert update_data == {"easiness_factor": 2.0}

    def test_apply_increment_flags_defaults_to_zero(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[{}])
        repo = VocabularyRepository("user-123")
        update_data: dict = {}
        repo._apply_increment_flags(
            1, {"increment_seen": True, "increment_correct": True}, update_data
        )
        assert update_data["times_seen"] == 1
        assert update_data["times_correct"] == 1

    def test_get_review_stats_returns_stats(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        next_review_iso = "2025-06-20T12:00:00+00:00"
        mock_query.execute.side_effect = [
            MagicMock(count=3),
            MagicMock(count=10),
            MagicMock(data=[{"next_review_at": next_review_iso}]),
        ]
        repo = VocabularyRepository("user-123")
        result = repo.get_review_stats("es")
        assert result["due_count"] == 3
        assert result["total_in_rotation"] == 10
        assert result["next_review_at"] == next_review_iso

    def test_get_review_stats_with_none_counts(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.side_effect = [
            MagicMock(count=None),
            MagicMock(count=None),
            MagicMock(data=[]),
        ]
        repo = VocabularyRepository("user-123")
        result = repo.get_review_stats("es")
        assert result["due_count"] == 0
        assert result["total_in_rotation"] == 0
        assert result["next_review_at"] is None

    def test_get_review_stats_no_next_review(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.side_effect = [
            MagicMock(count=5),
            MagicMock(count=5),
            MagicMock(data=[]),
        ]
        repo = VocabularyRepository("user-123")
        result = repo.get_review_stats("es")
        assert result["next_review_at"] is None


# =============================================================================
# LearningSessionRepository Tests
# =============================================================================


class TestLearningSessionRepository:
    """Tests for LearningSessionRepository class."""

    def test_init_stores_user_id(self, mock_get_supabase: MagicMock) -> None:
        repo = LearningSessionRepository("user-123")
        assert repo._user_id == "user-123"

    def test_init_with_custom_client(self) -> None:
        custom_client = MagicMock()
        repo = LearningSessionRepository("user-123", client=custom_client)
        assert repo._client is custom_client

    def test_create_returns_learning_session(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        session_row = {
            "id": 42,
            "user_id": "user-123",
            "language": "es",
            "level": "A1",
            "started_at": FIXED_NOW_ISO,
            "ended_at": None,
            "messages_count": 0,
            "words_learned": 0,
        }
        mock_query.execute.return_value = MagicMock(data=[session_row])
        repo = LearningSessionRepository("user-123")
        result = repo.create("es", "A1")
        assert isinstance(result, LearningSession)
        assert result.id == 42
        assert result.language == "es"
        mock_get_supabase.table.assert_called_with("learning_sessions")

    def test_get_by_id_found(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        session_row = {
            "id": 42,
            "user_id": "user-123",
            "language": "es",
            "level": "A1",
            "started_at": FIXED_NOW_ISO,
            "ended_at": None,
            "messages_count": 5,
            "words_learned": 3,
        }
        mock_query.execute.return_value = MagicMock(data=[session_row])
        repo = LearningSessionRepository("user-123")
        result = repo.get_by_id(42)
        assert result is not None
        assert result.id == 42

    def test_get_by_id_not_found(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[])
        repo = LearningSessionRepository("user-123")
        result = repo.get_by_id(999)
        assert result is None

    def test_end_session_calls_update(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[])
        repo = LearningSessionRepository("user-123")
        repo.end_session(42, messages_count=10, words_learned=5)
        mock_query.update.assert_called_once()
        call_args = mock_query.update.call_args[0][0]
        assert call_args["messages_count"] == 10
        assert call_args["words_learned"] == 5
        assert "ended_at" in call_args

    def test_get_all_returns_sessions(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(
            data=[
                {
                    "id": 1,
                    "user_id": "user-123",
                    "language": "es",
                    "level": "A1",
                    "started_at": FIXED_NOW_ISO,
                    "ended_at": FIXED_NOW_ISO,
                    "messages_count": 10,
                    "words_learned": 5,
                },
                {
                    "id": 2,
                    "user_id": "user-123",
                    "language": "de",
                    "level": "A2",
                    "started_at": FIXED_NOW_ISO,
                    "ended_at": None,
                    "messages_count": 3,
                    "words_learned": 1,
                },
            ]
        )
        repo = LearningSessionRepository("user-123")
        result = repo.get_all(limit=50)
        assert len(result) == 2
        assert all(isinstance(s, LearningSession) for s in result)

    def test_get_all_returns_empty(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[])
        repo = LearningSessionRepository("user-123")
        result = repo.get_all()
        assert result == []

    def test_get_active_found(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        session_row = {
            "id": 42,
            "user_id": "user-123",
            "language": "es",
            "level": "A1",
            "started_at": FIXED_NOW_ISO,
            "ended_at": None,
            "messages_count": 3,
            "words_learned": 1,
        }
        mock_query.execute.return_value = MagicMock(data=[session_row])
        repo = LearningSessionRepository("user-123")
        result = repo.get_active()
        assert result is not None
        assert result.ended_at is None

    def test_get_active_not_found(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[])
        repo = LearningSessionRepository("user-123")
        result = repo.get_active()
        assert result is None


# =============================================================================
# LessonProgressRepository Tests
# =============================================================================


class TestLessonProgressRepository:
    """Tests for LessonProgressRepository class."""

    def test_init_stores_user_id(self, mock_get_supabase: MagicMock) -> None:
        repo = LessonProgressRepository("user-123")
        assert repo._user_id == "user-123"

    def test_init_with_custom_client(self) -> None:
        custom_client = MagicMock()
        repo = LessonProgressRepository("user-123", client=custom_client)
        assert repo._client is custom_client

    def test_get_by_lesson_id_found(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        progress_row = {
            "user_id": "user-123",
            "lesson_id": "lesson-1",
            "completed_at": FIXED_NOW_ISO,
            "score": 85,
        }
        mock_query.execute.return_value = MagicMock(data=[progress_row])
        repo = LessonProgressRepository("user-123")
        result = repo.get_by_lesson_id("lesson-1")
        assert result is not None
        assert isinstance(result, LessonProgress)
        assert result.score == 85

    def test_get_by_lesson_id_not_found(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[])
        repo = LessonProgressRepository("user-123")
        result = repo.get_by_lesson_id("nonexistent")
        assert result is None

    def test_complete_lesson_new(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        new_row = {
            "user_id": "user-123",
            "lesson_id": "lesson-1",
            "completed_at": FIXED_NOW_ISO,
            "score": 90,
        }
        mock_query.execute.return_value = MagicMock(data=[new_row])
        repo = LessonProgressRepository("user-123")
        result = repo.complete_lesson("lesson-1", score=90)
        assert isinstance(result, LessonProgress)
        assert result.score == 90
        # Verify it uses upsert with on_conflict
        mock_query.upsert.assert_called_once()
        call_data = mock_query.upsert.call_args[0][0]
        assert call_data["user_id"] == "user-123"
        assert call_data["lesson_id"] == "lesson-1"
        assert call_data["score"] == 90
        assert mock_query.upsert.call_args[1]["on_conflict"] == "user_id,lesson_id"

    def test_complete_lesson_re_complete(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        updated_row = {
            "user_id": "user-123",
            "lesson_id": "lesson-1",
            "completed_at": FIXED_NOW_ISO,
            "score": 95,
        }
        mock_query.execute.return_value = MagicMock(data=[updated_row])
        repo = LessonProgressRepository("user-123")
        result = repo.complete_lesson("lesson-1", score=95)
        assert result.score == 95
        # Still uses upsert - same code path for new and existing
        mock_query.upsert.assert_called_once()

    def test_complete_lesson_without_score(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        new_row = {
            "user_id": "user-123",
            "lesson_id": "lesson-1",
            "completed_at": FIXED_NOW_ISO,
            "score": None,
        }
        mock_query.execute.return_value = MagicMock(data=[new_row])
        repo = LessonProgressRepository("user-123")
        result = repo.complete_lesson("lesson-1")
        assert result.score is None
        call_data = mock_query.upsert.call_args[0][0]
        assert call_data["score"] is None

    def test_get_completed_returns_list(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(
            data=[
                {
                    "user_id": "user-123",
                    "lesson_id": "lesson-1",
                    "completed_at": FIXED_NOW_ISO,
                    "score": 85,
                },
                {
                    "user_id": "user-123",
                    "lesson_id": "lesson-2",
                    "completed_at": FIXED_NOW_ISO,
                    "score": 92,
                },
            ]
        )
        repo = LessonProgressRepository("user-123")
        result = repo.get_completed()
        assert len(result) == 2
        assert all(isinstance(p, LessonProgress) for p in result)

    def test_get_completed_returns_empty(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[])
        repo = LessonProgressRepository("user-123")
        result = repo.get_completed()
        assert result == []

    def test_get_all_returns_list(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(
            data=[
                {
                    "user_id": "user-123",
                    "lesson_id": "lesson-1",
                    "completed_at": FIXED_NOW_ISO,
                    "score": 85,
                },
            ]
        )
        repo = LessonProgressRepository("user-123")
        result = repo.get_all()
        assert len(result) == 1

    def test_get_all_returns_empty(self, mock_get_supabase: MagicMock) -> None:
        mock_query = _chainable_query(mock_get_supabase)
        mock_query.execute.return_value = MagicMock(data=[])
        repo = LessonProgressRepository("user-123")
        result = repo.get_all()
        assert result == []
