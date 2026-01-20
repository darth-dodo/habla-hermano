"""Tests for levels service module.

Tests for CEFR level detection and management.
"""

import pytest

from src.services.levels import (
    CEFRLevel,
    LevelAssessment,
    PerformanceMetrics,
)

# =============================================================================
# CEFRLevel Tests
# =============================================================================


class TestCEFRLevel:
    """Tests for CEFRLevel enum."""

    def test_level_values(self) -> None:
        """Test all CEFR level values."""
        assert CEFRLevel.A0.value == "A0"
        assert CEFRLevel.A1.value == "A1"
        assert CEFRLevel.A2.value == "A2"
        assert CEFRLevel.B1.value == "B1"

    def test_from_string_valid_uppercase(self) -> None:
        """Test from_string with uppercase input."""
        assert CEFRLevel.from_string("A1") == CEFRLevel.A1
        assert CEFRLevel.from_string("B1") == CEFRLevel.B1

    def test_from_string_valid_lowercase(self) -> None:
        """Test from_string with lowercase input."""
        assert CEFRLevel.from_string("a1") == CEFRLevel.A1
        assert CEFRLevel.from_string("b1") == CEFRLevel.B1

    def test_from_string_with_whitespace(self) -> None:
        """Test from_string strips whitespace."""
        assert CEFRLevel.from_string("  A1  ") == CEFRLevel.A1
        assert CEFRLevel.from_string("\tA2\n") == CEFRLevel.A2

    def test_from_string_invalid_raises(self) -> None:
        """Test from_string raises ValueError for invalid level."""
        with pytest.raises(ValueError) as exc_info:
            CEFRLevel.from_string("C1")

        assert "Invalid CEFR level" in str(exc_info.value)

    def test_from_string_empty_raises(self) -> None:
        """Test from_string raises ValueError for empty string."""
        with pytest.raises(ValueError):
            CEFRLevel.from_string("")

    def test_next_level_a0(self) -> None:
        """Test next_level from A0."""
        assert CEFRLevel.A0.next_level() == CEFRLevel.A1

    def test_next_level_a1(self) -> None:
        """Test next_level from A1."""
        assert CEFRLevel.A1.next_level() == CEFRLevel.A2

    def test_next_level_a2(self) -> None:
        """Test next_level from A2."""
        assert CEFRLevel.A2.next_level() == CEFRLevel.B1

    def test_next_level_b1_returns_none(self) -> None:
        """Test next_level from B1 returns None (highest level)."""
        assert CEFRLevel.B1.next_level() is None

    def test_previous_level_b1(self) -> None:
        """Test previous_level from B1."""
        assert CEFRLevel.B1.previous_level() == CEFRLevel.A2

    def test_previous_level_a2(self) -> None:
        """Test previous_level from A2."""
        assert CEFRLevel.A2.previous_level() == CEFRLevel.A1

    def test_previous_level_a1(self) -> None:
        """Test previous_level from A1."""
        assert CEFRLevel.A1.previous_level() == CEFRLevel.A0

    def test_previous_level_a0_returns_none(self) -> None:
        """Test previous_level from A0 returns None (lowest level)."""
        assert CEFRLevel.A0.previous_level() is None

    def test_level_is_string_enum(self) -> None:
        """Test CEFRLevel is a string enum."""
        assert isinstance(CEFRLevel.A1.value, str)
        # String enum allows using value directly
        assert str(CEFRLevel.A1) == "CEFRLevel.A1"

    def test_level_comparison(self) -> None:
        """Test level enum members can be compared."""
        assert CEFRLevel.A0 == CEFRLevel.A0
        assert CEFRLevel.A1 != CEFRLevel.A2


# =============================================================================
# LevelAssessment Tests
# =============================================================================


class TestLevelAssessment:
    """Tests for LevelAssessment dataclass."""

    def test_create_assessment(self) -> None:
        """Test creating LevelAssessment."""
        assessment = LevelAssessment(
            current_level=CEFRLevel.A1,
            suggested_level=CEFRLevel.A2,
            should_adjust=True,
            confidence=0.85,
            reasoning="User consistently performs above A1 level",
        )

        assert assessment.current_level == CEFRLevel.A1
        assert assessment.suggested_level == CEFRLevel.A2
        assert assessment.should_adjust is True
        assert assessment.confidence == 0.85
        assert "above A1" in assessment.reasoning

    def test_assessment_no_adjustment(self) -> None:
        """Test LevelAssessment when no adjustment needed."""
        assessment = LevelAssessment(
            current_level=CEFRLevel.A1,
            suggested_level=None,
            should_adjust=False,
            confidence=0.9,
            reasoning="User is appropriately placed at A1",
        )

        assert assessment.suggested_level is None
        assert assessment.should_adjust is False

    def test_assessment_is_frozen(self) -> None:
        """Test LevelAssessment is immutable."""
        assessment = LevelAssessment(
            current_level=CEFRLevel.A1,
            suggested_level=None,
            should_adjust=False,
            confidence=0.9,
            reasoning="Test",
        )

        with pytest.raises(AttributeError):
            assessment.should_adjust = True  # type: ignore[misc]


# =============================================================================
# PerformanceMetrics Tests
# =============================================================================


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics dataclass."""

    def test_create_metrics(self) -> None:
        """Test creating PerformanceMetrics."""
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

    def test_metrics_with_errors(self) -> None:
        """Test PerformanceMetrics with error counts."""
        metrics = PerformanceMetrics(
            consecutive_correct=0,
            consecutive_errors=3,
            grammar_error_rate=0.5,
            vocabulary_use_rate=0.3,
            message_complexity=0.2,
        )

        assert metrics.consecutive_correct == 0
        assert metrics.consecutive_errors == 3
        assert metrics.grammar_error_rate == 0.5

    def test_metrics_is_frozen(self) -> None:
        """Test PerformanceMetrics is immutable."""
        metrics = PerformanceMetrics(
            consecutive_correct=5,
            consecutive_errors=0,
            grammar_error_rate=0.1,
            vocabulary_use_rate=0.8,
            message_complexity=0.6,
        )

        with pytest.raises(AttributeError):
            metrics.consecutive_correct = 10  # type: ignore[misc]

    def test_metrics_float_rates(self) -> None:
        """Test PerformanceMetrics accepts float rates between 0 and 1."""
        metrics = PerformanceMetrics(
            consecutive_correct=0,
            consecutive_errors=0,
            grammar_error_rate=0.0,
            vocabulary_use_rate=1.0,
            message_complexity=0.5,
        )

        assert metrics.grammar_error_rate == 0.0
        assert metrics.vocabulary_use_rate == 1.0
