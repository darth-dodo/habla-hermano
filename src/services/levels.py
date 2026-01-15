"""Level detection and adjustment service."""

from dataclasses import dataclass
from enum import Enum


class CEFRLevel(str, Enum):
    """CEFR language proficiency levels."""

    A0 = "A0"
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"

    @classmethod
    def from_string(cls, value: str) -> "CEFRLevel":
        """Parse CEFR level from string."""
        normalized = value.upper().strip()
        try:
            return cls(normalized)
        except ValueError as err:
            raise ValueError(f"Invalid CEFR level: {value}") from err

    def next_level(self) -> "CEFRLevel | None":
        """Get the next CEFR level, or None if at highest."""
        levels = list(CEFRLevel)
        idx = levels.index(self)
        if idx < len(levels) - 1:
            return levels[idx + 1]
        return None

    def previous_level(self) -> "CEFRLevel | None":
        """Get the previous CEFR level, or None if at lowest."""
        levels = list(CEFRLevel)
        idx = levels.index(self)
        if idx > 0:
            return levels[idx - 1]
        return None


@dataclass(frozen=True)
class LevelAssessment:
    """Assessment of learner's current performance relative to their level."""

    current_level: CEFRLevel
    suggested_level: CEFRLevel | None
    should_adjust: bool
    confidence: float
    reasoning: str


@dataclass(frozen=True)
class PerformanceMetrics:
    """Metrics used to assess level appropriateness."""

    consecutive_correct: int
    consecutive_errors: int
    grammar_error_rate: float
    vocabulary_use_rate: float
    message_complexity: float


class LevelService:
    """Service for detecting and adjusting learner levels."""

    # Thresholds for level adjustment
    CONSECUTIVE_CORRECT_FOR_UPGRADE = 5
    CONSECUTIVE_ERRORS_FOR_DOWNGRADE = 3
    CONFIDENCE_THRESHOLD = 0.7

    def assess_level(
        self,
        current_level: CEFRLevel,
        metrics: PerformanceMetrics,
    ) -> LevelAssessment:
        """
        Assess whether the learner's level should be adjusted.

        This is a stub implementation. In production, this would use
        more sophisticated analysis including LLM assessment of
        message complexity and grammar accuracy.

        Args:
            current_level: The learner's current CEFR level
            metrics: Performance metrics from recent messages

        Returns:
            Assessment with suggested level change if appropriate
        """
        if metrics.consecutive_correct >= self.CONSECUTIVE_CORRECT_FOR_UPGRADE:
            next_level = current_level.next_level()
            if next_level:
                return LevelAssessment(
                    current_level=current_level,
                    suggested_level=next_level,
                    should_adjust=True,
                    confidence=min(0.9, 0.5 + metrics.consecutive_correct * 0.1),
                    reasoning="Consistent correct responses suggest readiness for more challenge",
                )

        if metrics.consecutive_errors >= self.CONSECUTIVE_ERRORS_FOR_DOWNGRADE:
            prev_level = current_level.previous_level()
            if prev_level:
                return LevelAssessment(
                    current_level=current_level,
                    suggested_level=prev_level,
                    should_adjust=True,
                    confidence=min(0.9, 0.5 + metrics.consecutive_errors * 0.1),
                    reasoning="Multiple errors suggest current level may be too challenging",
                )

        return LevelAssessment(
            current_level=current_level,
            suggested_level=None,
            should_adjust=False,
            confidence=0.8,
            reasoning="Performance is appropriate for current level",
        )

    def detect_initial_level(
        self,
        sample_text: str,  # noqa: ARG002
        language: str,  # noqa: ARG002
    ) -> LevelAssessment:
        """
        Detect initial CEFR level from a writing sample.

        This is a stub implementation. In production, this would use
        LLM analysis to assess vocabulary range, grammar complexity,
        and overall proficiency.

        Args:
            sample_text: A writing sample from the learner
            language: The target language code

        Returns:
            Assessment with detected level
        """
        return LevelAssessment(
            current_level=CEFRLevel.A0,
            suggested_level=CEFRLevel.A0,
            should_adjust=False,
            confidence=0.5,
            reasoning="Default to A0 for new learners; will adjust based on performance",
        )

    def get_scaffolding_requirements(self, level: CEFRLevel) -> dict[str, bool]:
        """
        Get scaffolding requirements for a given level.

        Args:
            level: The CEFR level

        Returns:
            Dictionary of scaffolding feature flags
        """
        scaffolding_map: dict[CEFRLevel, dict[str, bool]] = {
            CEFRLevel.A0: {
                "show_word_bank": True,
                "show_translation": True,
                "show_hints": True,
                "show_sentence_starter": True,
                "auto_show_help": True,
            },
            CEFRLevel.A1: {
                "show_word_bank": True,
                "show_translation": True,
                "show_hints": True,
                "show_sentence_starter": False,
                "auto_show_help": False,
            },
            CEFRLevel.A2: {
                "show_word_bank": False,
                "show_translation": True,
                "show_hints": False,
                "show_sentence_starter": False,
                "auto_show_help": False,
            },
            CEFRLevel.B1: {
                "show_word_bank": False,
                "show_translation": False,
                "show_hints": False,
                "show_sentence_starter": False,
                "auto_show_help": False,
            },
        }
        return scaffolding_map.get(level, scaffolding_map[CEFRLevel.A0])
