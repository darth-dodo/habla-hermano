"""Tests for database repository module.

Tests for Supabase data access layer with mocked client.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.db.models import UserProfile, Vocabulary
from src.db.repository import UserProfileRepository, VocabularyRepository

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
