"""Tests for services module (levels and vocabulary).

Comprehensive tests for the level detection/adjustment service and
vocabulary extraction/tracking service.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.levels import (
    CEFRLevel,
    LevelAssessment,
    LevelService,
    PerformanceMetrics,
)
from src.services.vocabulary import (
    ExtractedWord,
    VocabularyService,
    VocabularyStats,
)

# =============================================================================
# CEFRLevel Enum Tests
# =============================================================================


class TestCEFRLevel:
    """Test suite for CEFRLevel enum."""

    def test_cefr_level_values(self) -> None:
        """Test all expected CEFR level values exist."""
        assert CEFRLevel.A0.value == "A0"
        assert CEFRLevel.A1.value == "A1"
        assert CEFRLevel.A2.value == "A2"
        assert CEFRLevel.B1.value == "B1"

    def test_cefr_level_count(self) -> None:
        """Test that we have exactly 4 CEFR levels."""
        assert len(list(CEFRLevel)) == 4

    # -------------------------------------------------------------------------
    # from_string() tests
    # -------------------------------------------------------------------------

    def test_from_string_valid_uppercase(self) -> None:
        """Test from_string with valid uppercase input."""
        assert CEFRLevel.from_string("A0") == CEFRLevel.A0
        assert CEFRLevel.from_string("A1") == CEFRLevel.A1
        assert CEFRLevel.from_string("A2") == CEFRLevel.A2
        assert CEFRLevel.from_string("B1") == CEFRLevel.B1

    def test_from_string_valid_lowercase(self) -> None:
        """Test from_string with valid lowercase input."""
        assert CEFRLevel.from_string("a0") == CEFRLevel.A0
        assert CEFRLevel.from_string("a1") == CEFRLevel.A1
        assert CEFRLevel.from_string("a2") == CEFRLevel.A2
        assert CEFRLevel.from_string("b1") == CEFRLevel.B1

    def test_from_string_valid_mixed_case(self) -> None:
        """Test from_string with mixed case input."""
        assert CEFRLevel.from_string("a0") == CEFRLevel.A0
        assert CEFRLevel.from_string("A1") == CEFRLevel.A1

    def test_from_string_with_whitespace(self) -> None:
        """Test from_string handles leading/trailing whitespace."""
        assert CEFRLevel.from_string("  A1  ") == CEFRLevel.A1
        assert CEFRLevel.from_string("\tB1\n") == CEFRLevel.B1

    def test_from_string_invalid_level(self) -> None:
        """Test from_string raises ValueError for invalid levels."""
        with pytest.raises(ValueError, match="Invalid CEFR level"):
            CEFRLevel.from_string("B2")

        with pytest.raises(ValueError, match="Invalid CEFR level"):
            CEFRLevel.from_string("C1")

    def test_from_string_empty_string(self) -> None:
        """Test from_string raises ValueError for empty string."""
        with pytest.raises(ValueError, match="Invalid CEFR level"):
            CEFRLevel.from_string("")

    def test_from_string_numeric(self) -> None:
        """Test from_string raises ValueError for numeric input."""
        with pytest.raises(ValueError, match="Invalid CEFR level"):
            CEFRLevel.from_string("1")

    # -------------------------------------------------------------------------
    # next_level() tests
    # -------------------------------------------------------------------------

    def test_next_level_progression(self) -> None:
        """Test next_level returns correct progression."""
        assert CEFRLevel.A0.next_level() == CEFRLevel.A1
        assert CEFRLevel.A1.next_level() == CEFRLevel.A2
        assert CEFRLevel.A2.next_level() == CEFRLevel.B1

    def test_next_level_at_highest(self) -> None:
        """Test next_level returns None at highest level."""
        assert CEFRLevel.B1.next_level() is None

    def test_next_level_full_chain(self) -> None:
        """Test next_level through full chain."""
        current: CEFRLevel | None = CEFRLevel.A0
        levels_seen = []
        while current is not None:
            levels_seen.append(current)
            current = current.next_level()
        assert levels_seen == [CEFRLevel.A0, CEFRLevel.A1, CEFRLevel.A2, CEFRLevel.B1]

    # -------------------------------------------------------------------------
    # previous_level() tests
    # -------------------------------------------------------------------------

    def test_previous_level_regression(self) -> None:
        """Test previous_level returns correct regression."""
        assert CEFRLevel.B1.previous_level() == CEFRLevel.A2
        assert CEFRLevel.A2.previous_level() == CEFRLevel.A1
        assert CEFRLevel.A1.previous_level() == CEFRLevel.A0

    def test_previous_level_at_lowest(self) -> None:
        """Test previous_level returns None at lowest level."""
        assert CEFRLevel.A0.previous_level() is None

    def test_previous_next_inverse(self) -> None:
        """Test previous_level and next_level are inverses."""
        for level in [CEFRLevel.A1, CEFRLevel.A2]:
            next_level = level.next_level()
            assert next_level is not None
            assert next_level.previous_level() == level

            prev_level = level.previous_level()
            assert prev_level is not None
            assert prev_level.next_level() == level


# =============================================================================
# LevelAssessment Dataclass Tests
# =============================================================================


class TestLevelAssessment:
    """Test suite for LevelAssessment dataclass."""

    def test_level_assessment_creation(self) -> None:
        """Test LevelAssessment can be created with all fields."""
        assessment = LevelAssessment(
            current_level=CEFRLevel.A1,
            suggested_level=CEFRLevel.A2,
            should_adjust=True,
            confidence=0.85,
            reasoning="Test reasoning",
        )
        assert assessment.current_level == CEFRLevel.A1
        assert assessment.suggested_level == CEFRLevel.A2
        assert assessment.should_adjust is True
        assert assessment.confidence == 0.85
        assert assessment.reasoning == "Test reasoning"

    def test_level_assessment_none_suggested_level(self) -> None:
        """Test LevelAssessment can have None suggested_level."""
        assessment = LevelAssessment(
            current_level=CEFRLevel.B1,
            suggested_level=None,
            should_adjust=False,
            confidence=0.8,
            reasoning="No adjustment needed",
        )
        assert assessment.suggested_level is None

    def test_level_assessment_is_frozen(self) -> None:
        """Test LevelAssessment is immutable (frozen dataclass)."""
        assessment = LevelAssessment(
            current_level=CEFRLevel.A0,
            suggested_level=None,
            should_adjust=False,
            confidence=0.5,
            reasoning="Test",
        )
        with pytest.raises(AttributeError):
            assessment.current_level = CEFRLevel.A1  # type: ignore[misc]


# =============================================================================
# PerformanceMetrics Dataclass Tests
# =============================================================================


class TestPerformanceMetrics:
    """Test suite for PerformanceMetrics dataclass."""

    def test_performance_metrics_creation(self) -> None:
        """Test PerformanceMetrics can be created with all fields."""
        metrics = PerformanceMetrics(
            consecutive_correct=5,
            consecutive_errors=0,
            grammar_error_rate=0.1,
            vocabulary_use_rate=0.8,
            message_complexity=0.6,
        )
        assert metrics.consecutive_correct == 5
        assert metrics.consecutive_errors == 0
        assert metrics.grammar_error_rate == 0.1
        assert metrics.vocabulary_use_rate == 0.8
        assert metrics.message_complexity == 0.6

    def test_performance_metrics_is_frozen(self) -> None:
        """Test PerformanceMetrics is immutable (frozen dataclass)."""
        metrics = PerformanceMetrics(
            consecutive_correct=3,
            consecutive_errors=0,
            grammar_error_rate=0.0,
            vocabulary_use_rate=0.5,
            message_complexity=0.5,
        )
        with pytest.raises(AttributeError):
            metrics.consecutive_correct = 10  # type: ignore[misc]


# =============================================================================
# LevelService Tests
# =============================================================================


class TestLevelService:
    """Test suite for LevelService class."""

    @pytest.fixture
    def service(self) -> LevelService:
        """Create LevelService instance for testing."""
        return LevelService()

    # -------------------------------------------------------------------------
    # assess_level() upgrade tests
    # -------------------------------------------------------------------------

    def test_assess_level_upgrade_at_threshold(self, service: LevelService) -> None:
        """Test assess_level suggests upgrade at consecutive_correct threshold."""
        metrics = PerformanceMetrics(
            consecutive_correct=5,  # Exactly at threshold
            consecutive_errors=0,
            grammar_error_rate=0.1,
            vocabulary_use_rate=0.8,
            message_complexity=0.6,
        )
        assessment = service.assess_level(CEFRLevel.A1, metrics)

        assert assessment.should_adjust is True
        assert assessment.suggested_level == CEFRLevel.A2
        assert "readiness for more challenge" in assessment.reasoning

    def test_assess_level_upgrade_above_threshold(self, service: LevelService) -> None:
        """Test assess_level suggests upgrade above threshold."""
        metrics = PerformanceMetrics(
            consecutive_correct=10,  # Above threshold
            consecutive_errors=0,
            grammar_error_rate=0.05,
            vocabulary_use_rate=0.9,
            message_complexity=0.7,
        )
        assessment = service.assess_level(CEFRLevel.A0, metrics)

        assert assessment.should_adjust is True
        assert assessment.suggested_level == CEFRLevel.A1

    def test_assess_level_no_upgrade_below_threshold(self, service: LevelService) -> None:
        """Test assess_level doesn't suggest upgrade below threshold."""
        metrics = PerformanceMetrics(
            consecutive_correct=4,  # Below threshold of 5
            consecutive_errors=0,
            grammar_error_rate=0.15,
            vocabulary_use_rate=0.7,
            message_complexity=0.5,
        )
        assessment = service.assess_level(CEFRLevel.A1, metrics)

        assert assessment.should_adjust is False
        assert assessment.suggested_level is None

    def test_assess_level_no_upgrade_at_max_level(self, service: LevelService) -> None:
        """Test assess_level doesn't suggest upgrade at B1 (max level)."""
        metrics = PerformanceMetrics(
            consecutive_correct=10,
            consecutive_errors=0,
            grammar_error_rate=0.0,
            vocabulary_use_rate=0.95,
            message_complexity=0.9,
        )
        assessment = service.assess_level(CEFRLevel.B1, metrics)

        assert assessment.should_adjust is False
        assert assessment.suggested_level is None

    # -------------------------------------------------------------------------
    # assess_level() downgrade tests
    # -------------------------------------------------------------------------

    def test_assess_level_downgrade_at_threshold(self, service: LevelService) -> None:
        """Test assess_level suggests downgrade at consecutive_errors threshold."""
        metrics = PerformanceMetrics(
            consecutive_correct=0,
            consecutive_errors=3,  # Exactly at threshold
            grammar_error_rate=0.5,
            vocabulary_use_rate=0.3,
            message_complexity=0.2,
        )
        assessment = service.assess_level(CEFRLevel.A2, metrics)

        assert assessment.should_adjust is True
        assert assessment.suggested_level == CEFRLevel.A1
        assert "too challenging" in assessment.reasoning

    def test_assess_level_downgrade_above_threshold(self, service: LevelService) -> None:
        """Test assess_level suggests downgrade above threshold."""
        metrics = PerformanceMetrics(
            consecutive_correct=0,
            consecutive_errors=5,  # Above threshold
            grammar_error_rate=0.6,
            vocabulary_use_rate=0.2,
            message_complexity=0.1,
        )
        assessment = service.assess_level(CEFRLevel.B1, metrics)

        assert assessment.should_adjust is True
        assert assessment.suggested_level == CEFRLevel.A2

    def test_assess_level_no_downgrade_below_threshold(self, service: LevelService) -> None:
        """Test assess_level doesn't suggest downgrade below threshold."""
        metrics = PerformanceMetrics(
            consecutive_correct=0,
            consecutive_errors=2,  # Below threshold of 3
            grammar_error_rate=0.3,
            vocabulary_use_rate=0.5,
            message_complexity=0.4,
        )
        assessment = service.assess_level(CEFRLevel.A1, metrics)

        assert assessment.should_adjust is False
        assert assessment.suggested_level is None

    def test_assess_level_no_downgrade_at_min_level(self, service: LevelService) -> None:
        """Test assess_level doesn't suggest downgrade at A0 (min level)."""
        metrics = PerformanceMetrics(
            consecutive_correct=0,
            consecutive_errors=10,
            grammar_error_rate=0.8,
            vocabulary_use_rate=0.1,
            message_complexity=0.1,
        )
        assessment = service.assess_level(CEFRLevel.A0, metrics)

        assert assessment.should_adjust is False
        assert assessment.suggested_level is None

    # -------------------------------------------------------------------------
    # assess_level() confidence tests
    # -------------------------------------------------------------------------

    def test_assess_level_upgrade_confidence_formula(self, service: LevelService) -> None:
        """Test confidence calculation for upgrade: 0.5 + consecutive_correct * 0.1."""
        metrics = PerformanceMetrics(
            consecutive_correct=5,
            consecutive_errors=0,
            grammar_error_rate=0.1,
            vocabulary_use_rate=0.8,
            message_complexity=0.6,
        )
        assessment = service.assess_level(CEFRLevel.A1, metrics)

        # confidence = min(0.9, 0.5 + 5 * 0.1) = min(0.9, 1.0) = 0.9
        assert assessment.confidence == 0.9

    def test_assess_level_downgrade_confidence_formula(self, service: LevelService) -> None:
        """Test confidence calculation for downgrade: 0.5 + consecutive_errors * 0.1."""
        metrics = PerformanceMetrics(
            consecutive_correct=0,
            consecutive_errors=3,
            grammar_error_rate=0.5,
            vocabulary_use_rate=0.3,
            message_complexity=0.2,
        )
        assessment = service.assess_level(CEFRLevel.A2, metrics)

        # confidence = min(0.9, 0.5 + 3 * 0.1) = min(0.9, 0.8) = 0.8
        assert assessment.confidence == 0.8

    def test_assess_level_no_change_confidence(self, service: LevelService) -> None:
        """Test confidence for no-change assessment is 0.8."""
        metrics = PerformanceMetrics(
            consecutive_correct=2,
            consecutive_errors=1,
            grammar_error_rate=0.2,
            vocabulary_use_rate=0.6,
            message_complexity=0.5,
        )
        assessment = service.assess_level(CEFRLevel.A1, metrics)

        assert assessment.confidence == 0.8
        assert assessment.should_adjust is False

    # -------------------------------------------------------------------------
    # assess_level() edge cases
    # -------------------------------------------------------------------------

    def test_assess_level_upgrade_precedence(self, service: LevelService) -> None:
        """Test upgrade takes precedence when both thresholds are met."""
        metrics = PerformanceMetrics(
            consecutive_correct=5,  # At upgrade threshold
            consecutive_errors=3,  # Also at downgrade threshold
            grammar_error_rate=0.3,
            vocabulary_use_rate=0.5,
            message_complexity=0.5,
        )
        assessment = service.assess_level(CEFRLevel.A1, metrics)

        # Upgrade is checked first, so it should win
        assert assessment.should_adjust is True
        assert assessment.suggested_level == CEFRLevel.A2

    def test_assess_level_all_levels(self, service: LevelService) -> None:
        """Test assess_level works for all CEFR levels."""
        metrics = PerformanceMetrics(
            consecutive_correct=2,
            consecutive_errors=1,
            grammar_error_rate=0.2,
            vocabulary_use_rate=0.6,
            message_complexity=0.5,
        )

        for level in CEFRLevel:
            assessment = service.assess_level(level, metrics)
            assert assessment.current_level == level
            assert isinstance(assessment, LevelAssessment)

    # -------------------------------------------------------------------------
    # detect_initial_level() tests
    # -------------------------------------------------------------------------

    def test_detect_initial_level_returns_a0(self, service: LevelService) -> None:
        """Test detect_initial_level defaults to A0 for new learners."""
        assessment = service.detect_initial_level(
            sample_text="Hola, me llamo Juan.",
            language="es",
        )

        assert assessment.current_level == CEFRLevel.A0
        assert assessment.suggested_level == CEFRLevel.A0
        assert assessment.should_adjust is False
        assert assessment.confidence == 0.5
        assert "Default to A0" in assessment.reasoning

    def test_detect_initial_level_ignores_sample_text(self, service: LevelService) -> None:
        """Test detect_initial_level is a stub that ignores input (for now)."""
        # Complex text should still return A0 (stub behavior)
        assessment = service.detect_initial_level(
            sample_text="El impacto del cambio climatico en los ecosistemas marinos "
            "representa una de las mayores amenazas para la biodiversidad global.",
            language="es",
        )
        assert assessment.current_level == CEFRLevel.A0

    def test_detect_initial_level_ignores_language(self, service: LevelService) -> None:
        """Test detect_initial_level works with different languages."""
        for lang in ["es", "de", "fr", "en"]:
            assessment = service.detect_initial_level(
                sample_text="Sample text",
                language=lang,
            )
            assert assessment.current_level == CEFRLevel.A0

    # -------------------------------------------------------------------------
    # get_scaffolding_requirements() tests
    # -------------------------------------------------------------------------

    def test_scaffolding_a0_all_features_enabled(self, service: LevelService) -> None:
        """Test A0 level has all scaffolding features enabled."""
        scaffolding = service.get_scaffolding_requirements(CEFRLevel.A0)

        assert scaffolding["show_word_bank"] is True
        assert scaffolding["show_translation"] is True
        assert scaffolding["show_hints"] is True
        assert scaffolding["show_sentence_starter"] is True
        assert scaffolding["auto_show_help"] is True

    def test_scaffolding_a1_reduced_features(self, service: LevelService) -> None:
        """Test A1 level has some features disabled."""
        scaffolding = service.get_scaffolding_requirements(CEFRLevel.A1)

        assert scaffolding["show_word_bank"] is True
        assert scaffolding["show_translation"] is True
        assert scaffolding["show_hints"] is True
        assert scaffolding["show_sentence_starter"] is False
        assert scaffolding["auto_show_help"] is False

    def test_scaffolding_a2_minimal_features(self, service: LevelService) -> None:
        """Test A2 level has minimal scaffolding."""
        scaffolding = service.get_scaffolding_requirements(CEFRLevel.A2)

        assert scaffolding["show_word_bank"] is False
        assert scaffolding["show_translation"] is True
        assert scaffolding["show_hints"] is False
        assert scaffolding["show_sentence_starter"] is False
        assert scaffolding["auto_show_help"] is False

    def test_scaffolding_b1_no_features(self, service: LevelService) -> None:
        """Test B1 level has no scaffolding features enabled."""
        scaffolding = service.get_scaffolding_requirements(CEFRLevel.B1)

        assert scaffolding["show_word_bank"] is False
        assert scaffolding["show_translation"] is False
        assert scaffolding["show_hints"] is False
        assert scaffolding["show_sentence_starter"] is False
        assert scaffolding["auto_show_help"] is False

    def test_scaffolding_progressive_reduction(self, service: LevelService) -> None:
        """Test scaffolding features are progressively reduced as level increases."""
        levels = [CEFRLevel.A0, CEFRLevel.A1, CEFRLevel.A2, CEFRLevel.B1]

        previous_true_count = 6  # Start higher than max
        for level in levels:
            scaffolding = service.get_scaffolding_requirements(level)
            true_count = sum(1 for v in scaffolding.values() if v is True)
            assert true_count <= previous_true_count
            previous_true_count = true_count

    def test_scaffolding_returns_dict_with_all_keys(self, service: LevelService) -> None:
        """Test all scaffolding dicts have the same keys."""
        expected_keys = {
            "show_word_bank",
            "show_translation",
            "show_hints",
            "show_sentence_starter",
            "auto_show_help",
        }

        for level in CEFRLevel:
            scaffolding = service.get_scaffolding_requirements(level)
            assert set(scaffolding.keys()) == expected_keys

    # -------------------------------------------------------------------------
    # Threshold constant tests
    # -------------------------------------------------------------------------

    def test_threshold_constants_are_reasonable(self, service: LevelService) -> None:
        """Test threshold constants have sensible values."""
        assert service.CONSECUTIVE_CORRECT_FOR_UPGRADE == 5
        assert service.CONSECUTIVE_ERRORS_FOR_DOWNGRADE == 3
        assert service.CONFIDENCE_THRESHOLD == 0.7


# =============================================================================
# ExtractedWord Dataclass Tests
# =============================================================================


class TestExtractedWord:
    """Test suite for ExtractedWord dataclass."""

    def test_extracted_word_creation(self) -> None:
        """Test ExtractedWord can be created with all fields."""
        word = ExtractedWord(
            word="hola",
            translation="hello",
            part_of_speech="interjection",
            context="Hola, como estas?",
        )
        assert word.word == "hola"
        assert word.translation == "hello"
        assert word.part_of_speech == "interjection"
        assert word.context == "Hola, como estas?"

    def test_extracted_word_with_none_pos(self) -> None:
        """Test ExtractedWord can have None part_of_speech."""
        word = ExtractedWord(
            word="hola",
            translation="hello",
            part_of_speech=None,
            context="Hola!",
        )
        assert word.part_of_speech is None

    def test_extracted_word_is_frozen(self) -> None:
        """Test ExtractedWord is immutable (frozen dataclass)."""
        word = ExtractedWord(
            word="hola",
            translation="hello",
            part_of_speech="interjection",
            context="Hola!",
        )
        with pytest.raises(AttributeError):
            word.word = "adios"  # type: ignore[misc]


# =============================================================================
# VocabularyStats Dataclass Tests
# =============================================================================


class TestVocabularyStats:
    """Test suite for VocabularyStats dataclass."""

    def test_vocabulary_stats_creation(self) -> None:
        """Test VocabularyStats can be created with all fields."""
        stats = VocabularyStats(
            total_words=100,
            words_by_part_of_speech={"noun": 40, "verb": 30, "adjective": 20},
            most_seen=[("hola", 50), ("gracias", 45)],
            recently_learned=["nuevo", "palabra"],
        )
        assert stats.total_words == 100
        assert stats.words_by_part_of_speech["noun"] == 40
        assert stats.most_seen[0] == ("hola", 50)
        assert "nuevo" in stats.recently_learned

    def test_vocabulary_stats_empty_collections(self) -> None:
        """Test VocabularyStats works with empty collections."""
        stats = VocabularyStats(
            total_words=0,
            words_by_part_of_speech={},
            most_seen=[],
            recently_learned=[],
        )
        assert stats.total_words == 0
        assert len(stats.words_by_part_of_speech) == 0
        assert len(stats.most_seen) == 0
        assert len(stats.recently_learned) == 0


# =============================================================================
# VocabularyService Tests
# =============================================================================


class TestVocabularyService:
    """Test suite for VocabularyService class."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create mock AsyncSession."""
        return MagicMock()

    @pytest.fixture
    def mock_vocabulary_items(self) -> list[MagicMock]:
        """Create sample Vocabulary model instances for testing."""
        items = []
        now = datetime.utcnow()

        item1 = MagicMock()
        item1.id = 1
        item1.word = "hola"
        item1.translation = "hello"
        item1.language = "es"
        item1.part_of_speech = "interjection"
        item1.first_seen_at = now
        item1.times_seen = 10
        items.append(item1)

        item2 = MagicMock()
        item2.id = 2
        item2.word = "gracias"
        item2.translation = "thank you"
        item2.language = "es"
        item2.part_of_speech = "interjection"
        item2.first_seen_at = now
        item2.times_seen = 8
        items.append(item2)

        item3 = MagicMock()
        item3.id = 3
        item3.word = "libro"
        item3.translation = "book"
        item3.language = "es"
        item3.part_of_speech = "noun"
        item3.first_seen_at = now
        item3.times_seen = 5
        items.append(item3)

        return items

    # -------------------------------------------------------------------------
    # extract_vocabulary() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_extract_vocabulary_returns_empty_list(self, mock_session: MagicMock) -> None:
        """Test extract_vocabulary stub returns empty list."""
        with patch("src.services.vocabulary.VocabularyRepository"):
            service = VocabularyService(mock_session)
            result = await service.extract_vocabulary(
                text="Hola, como estas?",
                language="es",
                level="A1",
            )
            assert result == []
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_extract_vocabulary_accepts_various_inputs(self, mock_session: MagicMock) -> None:
        """Test extract_vocabulary accepts various input combinations."""
        with patch("src.services.vocabulary.VocabularyRepository"):
            service = VocabularyService(mock_session)

            # Different languages
            for lang in ["es", "de"]:
                result = await service.extract_vocabulary(
                    text="Test text",
                    language=lang,
                    level="A0",
                )
                assert result == []

            # Different levels
            for level in ["A0", "A1", "A2", "B1"]:
                result = await service.extract_vocabulary(
                    text="Test text",
                    language="es",
                    level=level,
                )
                assert result == []

    # -------------------------------------------------------------------------
    # save_vocabulary() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_save_vocabulary_empty_list(self, mock_session: MagicMock) -> None:
        """Test save_vocabulary with empty list returns 0."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo

            service = VocabularyService(mock_session)
            result = await service.save_vocabulary(words=[], language="es")

            assert result == 0
            mock_repo.get_by_word_and_language.assert_not_called()
            mock_repo.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_vocabulary_new_words(self, mock_session: MagicMock) -> None:
        """Test save_vocabulary counts new words correctly."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_by_word_and_language.return_value = None  # Word doesn't exist
            mock_repo_class.return_value = mock_repo

            service = VocabularyService(mock_session)
            words = [
                ExtractedWord(
                    word="hola",
                    translation="hello",
                    part_of_speech="interjection",
                    context="Hola!",
                ),
                ExtractedWord(
                    word="adios",
                    translation="goodbye",
                    part_of_speech="interjection",
                    context="Adios!",
                ),
            ]
            result = await service.save_vocabulary(words=words, language="es")

            assert result == 2
            assert mock_repo.get_by_word_and_language.call_count == 2
            assert mock_repo.upsert.call_count == 2

    @pytest.mark.asyncio
    async def test_save_vocabulary_existing_words(
        self, mock_session: MagicMock, mock_vocabulary_items: list[MagicMock]
    ) -> None:
        """Test save_vocabulary returns 0 for existing words."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            # Simulate word already exists
            mock_repo.get_by_word_and_language.return_value = mock_vocabulary_items[0]
            mock_repo_class.return_value = mock_repo

            service = VocabularyService(mock_session)
            words = [
                ExtractedWord(
                    word="hola",
                    translation="hello",
                    part_of_speech="interjection",
                    context="Hola!",
                ),
            ]
            result = await service.save_vocabulary(words=words, language="es")

            assert result == 0
            mock_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_vocabulary_mixed_new_and_existing(
        self, mock_session: MagicMock, mock_vocabulary_items: list[MagicMock]
    ) -> None:
        """Test save_vocabulary correctly counts mix of new and existing words."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            # First word exists, second is new
            mock_repo.get_by_word_and_language.side_effect = [
                mock_vocabulary_items[0],  # "hola" exists
                None,  # "nuevo" is new
            ]
            mock_repo_class.return_value = mock_repo

            service = VocabularyService(mock_session)
            words = [
                ExtractedWord(
                    word="hola",
                    translation="hello",
                    part_of_speech="interjection",
                    context="Hola!",
                ),
                ExtractedWord(
                    word="nuevo",
                    translation="new",
                    part_of_speech="adjective",
                    context="Es nuevo",
                ),
            ]
            result = await service.save_vocabulary(words=words, language="es")

            assert result == 1  # Only one new word

    @pytest.mark.asyncio
    async def test_save_vocabulary_upsert_called_with_correct_args(
        self, mock_session: MagicMock
    ) -> None:
        """Test save_vocabulary calls upsert with correct arguments."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_by_word_and_language.return_value = None
            mock_repo_class.return_value = mock_repo

            service = VocabularyService(mock_session)
            words = [
                ExtractedWord(
                    word="libro",
                    translation="book",
                    part_of_speech="noun",
                    context="El libro es interesante",
                ),
            ]
            await service.save_vocabulary(words=words, language="es")

            mock_repo.upsert.assert_called_once_with(
                word="libro",
                translation="book",
                language="es",
                part_of_speech="noun",
            )

    # -------------------------------------------------------------------------
    # get_word_bank() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_word_bank_returns_words(
        self, mock_session: MagicMock, mock_vocabulary_items: list[MagicMock]
    ) -> None:
        """Test get_word_bank returns list of word strings."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_recent.return_value = mock_vocabulary_items[:2]
            mock_repo_class.return_value = mock_repo

            service = VocabularyService(mock_session)
            result = await service.get_word_bank(language="es", count=6)

            assert result == ["hola", "gracias"]
            mock_repo.get_recent.assert_called_once_with("es", limit=6)

    @pytest.mark.asyncio
    async def test_get_word_bank_empty_result(self, mock_session: MagicMock) -> None:
        """Test get_word_bank returns empty list when no vocabulary exists."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_recent.return_value = []
            mock_repo_class.return_value = mock_repo

            service = VocabularyService(mock_session)
            result = await service.get_word_bank(language="de")

            assert result == []

    @pytest.mark.asyncio
    async def test_get_word_bank_default_count(self, mock_session: MagicMock) -> None:
        """Test get_word_bank uses default count of 6."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_recent.return_value = []
            mock_repo_class.return_value = mock_repo

            service = VocabularyService(mock_session)
            await service.get_word_bank(language="es")

            mock_repo.get_recent.assert_called_once_with("es", limit=6)

    @pytest.mark.asyncio
    async def test_get_word_bank_custom_count(self, mock_session: MagicMock) -> None:
        """Test get_word_bank accepts custom count parameter."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_recent.return_value = []
            mock_repo_class.return_value = mock_repo

            service = VocabularyService(mock_session)
            await service.get_word_bank(language="es", count=10)

            mock_repo.get_recent.assert_called_once_with("es", limit=10)

    @pytest.mark.asyncio
    async def test_get_word_bank_ignores_topic(self, mock_session: MagicMock) -> None:
        """Test get_word_bank currently ignores topic parameter (stub behavior)."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_recent.return_value = []
            mock_repo_class.return_value = mock_repo

            service = VocabularyService(mock_session)
            await service.get_word_bank(language="es", topic="food")

            # Topic is ignored in current stub implementation
            mock_repo.get_recent.assert_called_once()

    # -------------------------------------------------------------------------
    # get_statistics() tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_statistics_returns_stats(
        self, mock_session: MagicMock, mock_vocabulary_items: list[MagicMock]
    ) -> None:
        """Test get_statistics returns VocabularyStats with correct data."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_all_by_language.return_value = mock_vocabulary_items
            mock_repo.get_recent.return_value = mock_vocabulary_items[:2]
            mock_repo_class.return_value = mock_repo

            service = VocabularyService(mock_session)
            stats = await service.get_statistics(language="es")

            assert stats.total_words == 3
            assert stats.words_by_part_of_speech == {"interjection": 2, "noun": 1}
            assert stats.most_seen[0] == ("hola", 10)
            assert stats.most_seen[1] == ("gracias", 8)
            assert "hola" in stats.recently_learned

    @pytest.mark.asyncio
    async def test_get_statistics_empty_vocabulary(self, mock_session: MagicMock) -> None:
        """Test get_statistics with no vocabulary returns empty stats."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_all_by_language.return_value = []
            mock_repo.get_recent.return_value = []
            mock_repo_class.return_value = mock_repo

            service = VocabularyService(mock_session)
            stats = await service.get_statistics(language="de")

            assert stats.total_words == 0
            assert stats.words_by_part_of_speech == {}
            assert stats.most_seen == []
            assert stats.recently_learned == []

    @pytest.mark.asyncio
    async def test_get_statistics_words_without_pos(self, mock_session: MagicMock) -> None:
        """Test get_statistics handles words without part_of_speech."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            item = MagicMock()
            item.id = 1
            item.word = "test"
            item.translation = "test"
            item.language = "es"
            item.part_of_speech = None  # No part of speech
            item.first_seen_at = datetime.utcnow()
            item.times_seen = 5

            mock_repo = AsyncMock()
            mock_repo.get_all_by_language.return_value = [item]
            mock_repo.get_recent.return_value = [item]
            mock_repo_class.return_value = mock_repo

            service = VocabularyService(mock_session)
            stats = await service.get_statistics(language="es")

            assert stats.total_words == 1
            assert stats.words_by_part_of_speech == {}  # None POS not counted

    @pytest.mark.asyncio
    async def test_get_statistics_most_seen_limit(self, mock_session: MagicMock) -> None:
        """Test get_statistics limits most_seen to top 10."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            # Create 15 vocabulary items
            items = []
            for i in range(15):
                item = MagicMock()
                item.id = i
                item.word = f"word{i}"
                item.translation = f"translation{i}"
                item.language = "es"
                item.part_of_speech = "noun"
                item.first_seen_at = datetime.utcnow()
                item.times_seen = 15 - i  # Descending times_seen
                items.append(item)

            mock_repo = AsyncMock()
            mock_repo.get_all_by_language.return_value = items
            mock_repo.get_recent.return_value = items[:5]
            mock_repo_class.return_value = mock_repo

            service = VocabularyService(mock_session)
            stats = await service.get_statistics(language="es")

            assert len(stats.most_seen) == 10
            # First item should have highest times_seen
            assert stats.most_seen[0][1] == 15

    @pytest.mark.asyncio
    async def test_get_statistics_recently_learned_limit(self, mock_session: MagicMock) -> None:
        """Test get_statistics requests limit of 10 for recently learned."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_all_by_language.return_value = []
            mock_repo.get_recent.return_value = []
            mock_repo_class.return_value = mock_repo

            service = VocabularyService(mock_session)
            await service.get_statistics(language="es")

            mock_repo.get_recent.assert_called_once_with("es", limit=10)

    # -------------------------------------------------------------------------
    # Service initialization tests
    # -------------------------------------------------------------------------

    def test_vocabulary_service_initializes_repository(self, mock_session: MagicMock) -> None:
        """Test VocabularyService creates VocabularyRepository on init."""
        with patch("src.services.vocabulary.VocabularyRepository") as mock_repo_class:
            service = VocabularyService(mock_session)

            mock_repo_class.assert_called_once_with(mock_session)
            assert service._session == mock_session
