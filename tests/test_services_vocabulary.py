"""Tests for vocabulary service module.

Tests for vocabulary extraction and management service.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.services.vocabulary import (
    ExtractedWord,
    VocabularyService,
    VocabularyStats,
)


# =============================================================================
# ExtractedWord Tests
# =============================================================================


class TestExtractedWord:
    """Tests for ExtractedWord dataclass."""

    def test_create_extracted_word(self) -> None:
        """Test creating ExtractedWord."""
        word = ExtractedWord(
            word="hola",
            translation="hello",
            part_of_speech="interjection",
            context="Hola, ¿cómo estás?",
        )

        assert word.word == "hola"
        assert word.translation == "hello"
        assert word.part_of_speech == "interjection"
        assert word.context == "Hola, ¿cómo estás?"

    def test_extracted_word_is_frozen(self) -> None:
        """Test ExtractedWord is immutable."""
        word = ExtractedWord(
            word="hola",
            translation="hello",
            part_of_speech="interjection",
            context="test",
        )

        with pytest.raises(AttributeError):
            word.word = "adiós"  # type: ignore[misc]

    def test_extracted_word_with_none_pos(self) -> None:
        """Test ExtractedWord with None part_of_speech."""
        word = ExtractedWord(
            word="hola",
            translation="hello",
            part_of_speech=None,
            context="test",
        )

        assert word.part_of_speech is None


# =============================================================================
# VocabularyStats Tests
# =============================================================================


class TestVocabularyStats:
    """Tests for VocabularyStats dataclass."""

    def test_create_vocabulary_stats(self) -> None:
        """Test creating VocabularyStats."""
        stats = VocabularyStats(
            total_words=100,
            words_by_part_of_speech={"noun": 40, "verb": 30, "adjective": 20},
            most_seen=[("hola", 50), ("gracias", 30)],
            recently_learned=["buenos", "días"],
        )

        assert stats.total_words == 100
        assert stats.words_by_part_of_speech["noun"] == 40
        assert stats.most_seen[0] == ("hola", 50)
        assert "buenos" in stats.recently_learned

    def test_vocabulary_stats_is_frozen(self) -> None:
        """Test VocabularyStats is immutable."""
        stats = VocabularyStats(
            total_words=100,
            words_by_part_of_speech={},
            most_seen=[],
            recently_learned=[],
        )

        with pytest.raises(AttributeError):
            stats.total_words = 200  # type: ignore[misc]


# =============================================================================
# VocabularyService Tests
# =============================================================================


class TestVocabularyService:
    """Tests for VocabularyService class."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mock VocabularyRepository."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            yield mock_instance

    def test_init_creates_repository(self, mock_repo: MagicMock) -> None:
        """Test service creates repository with user_id."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_class:
            VocabularyService("user-123")

            mock_class.assert_called_once_with("user-123")

    def test_extract_vocabulary_returns_empty_list(
        self, mock_repo: MagicMock
    ) -> None:
        """Test extract_vocabulary returns empty list (stub implementation)."""
        service = VocabularyService("user-123")

        result = service.extract_vocabulary(
            text="Hola, ¿cómo estás?",
            language="es",
            level="A1",
        )

        assert result == []
        assert isinstance(result, list)

    def test_save_vocabulary_counts_new_words(self, mock_repo: MagicMock) -> None:
        """Test save_vocabulary counts new words correctly."""
        mock_repo.get_by_word_and_language.return_value = None  # Word doesn't exist

        service = VocabularyService("user-123")
        words = [
            ExtractedWord(
                word="hola", translation="hello", part_of_speech="interjection", context=""
            ),
            ExtractedWord(
                word="adiós", translation="goodbye", part_of_speech="interjection", context=""
            ),
        ]

        result = service.save_vocabulary(words, language="es")

        assert result == 2
        assert mock_repo.upsert.call_count == 2

    def test_save_vocabulary_doesnt_count_existing(
        self, mock_repo: MagicMock
    ) -> None:
        """Test save_vocabulary doesn't count existing words as new."""
        # First word exists, second doesn't
        mock_repo.get_by_word_and_language.side_effect = [MagicMock(), None]

        service = VocabularyService("user-123")
        words = [
            ExtractedWord(
                word="hola", translation="hello", part_of_speech=None, context=""
            ),
            ExtractedWord(
                word="nuevo", translation="new", part_of_speech=None, context=""
            ),
        ]

        result = service.save_vocabulary(words, language="es")

        assert result == 1  # Only one new word

    def test_save_vocabulary_calls_upsert(self, mock_repo: MagicMock) -> None:
        """Test save_vocabulary calls upsert with correct arguments."""
        mock_repo.get_by_word_and_language.return_value = None

        service = VocabularyService("user-123")
        words = [
            ExtractedWord(
                word="hola",
                translation="hello",
                part_of_speech="interjection",
                context="",
            )
        ]

        service.save_vocabulary(words, language="es")

        mock_repo.upsert.assert_called_once_with(
            word="hola",
            translation="hello",
            language="es",
            part_of_speech="interjection",
        )

    def test_get_word_bank_returns_recent_words(
        self, mock_repo: MagicMock
    ) -> None:
        """Test get_word_bank returns recent vocabulary words."""
        mock_vocab = [
            MagicMock(word="hola"),
            MagicMock(word="gracias"),
            MagicMock(word="por favor"),
        ]
        mock_repo.get_recent.return_value = mock_vocab

        service = VocabularyService("user-123")
        result = service.get_word_bank(language="es", count=3)

        assert result == ["hola", "gracias", "por favor"]
        mock_repo.get_recent.assert_called_once_with("es", limit=3)

    def test_get_word_bank_default_count(self, mock_repo: MagicMock) -> None:
        """Test get_word_bank uses default count of 6."""
        mock_repo.get_recent.return_value = []

        service = VocabularyService("user-123")
        service.get_word_bank(language="es")

        mock_repo.get_recent.assert_called_once_with("es", limit=6)

    def test_get_statistics_returns_stats(self, mock_repo: MagicMock) -> None:
        """Test get_statistics returns VocabularyStats."""
        mock_vocab = [
            MagicMock(word="hola", part_of_speech="noun", times_seen=10),
            MagicMock(word="gracias", part_of_speech="noun", times_seen=5),
            MagicMock(word="correr", part_of_speech="verb", times_seen=3),
        ]
        mock_recent = [
            MagicMock(word="nuevo"),
            MagicMock(word="reciente"),
        ]
        mock_repo.get_all.return_value = mock_vocab
        mock_repo.get_recent.return_value = mock_recent

        service = VocabularyService("user-123")
        result = service.get_statistics(language="es")

        assert isinstance(result, VocabularyStats)
        assert result.total_words == 3
        assert result.words_by_part_of_speech["noun"] == 2
        assert result.words_by_part_of_speech["verb"] == 1
        assert result.recently_learned == ["nuevo", "reciente"]

    def test_get_statistics_most_seen_sorted(
        self, mock_repo: MagicMock
    ) -> None:
        """Test get_statistics returns most_seen sorted by times_seen."""
        mock_vocab = [
            MagicMock(word="c", part_of_speech=None, times_seen=1),
            MagicMock(word="a", part_of_speech=None, times_seen=10),
            MagicMock(word="b", part_of_speech=None, times_seen=5),
        ]
        mock_repo.get_all.return_value = mock_vocab
        mock_repo.get_recent.return_value = []

        service = VocabularyService("user-123")
        result = service.get_statistics(language="es")

        # Should be sorted by times_seen descending
        assert result.most_seen[0] == ("a", 10)
        assert result.most_seen[1] == ("b", 5)
        assert result.most_seen[2] == ("c", 1)

    def test_get_statistics_handles_empty_vocabulary(
        self, mock_repo: MagicMock
    ) -> None:
        """Test get_statistics handles empty vocabulary."""
        mock_repo.get_all.return_value = []
        mock_repo.get_recent.return_value = []

        service = VocabularyService("user-123")
        result = service.get_statistics(language="es")

        assert result.total_words == 0
        assert result.words_by_part_of_speech == {}
        assert result.most_seen == []
        assert result.recently_learned == []

    def test_get_statistics_handles_none_part_of_speech(
        self, mock_repo: MagicMock
    ) -> None:
        """Test get_statistics skips None part_of_speech in counts."""
        mock_vocab = [
            MagicMock(word="hola", part_of_speech=None, times_seen=1),
            MagicMock(word="gracias", part_of_speech="noun", times_seen=1),
        ]
        mock_repo.get_all.return_value = mock_vocab
        mock_repo.get_recent.return_value = []

        service = VocabularyService("user-123")
        result = service.get_statistics(language="es")

        # Only 'noun' should be counted
        assert result.words_by_part_of_speech == {"noun": 1}
