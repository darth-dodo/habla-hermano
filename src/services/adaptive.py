"""Adaptive daily recommendation service.

Builds personalized learning recommendations by combining path progress,
vocabulary accuracy, and level readiness into a single actionable summary.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.db.models import LessonProgress, Vocabulary
    from src.lessons.models import Lesson
    from src.lessons.service import LessonService
    from src.services.paths import PathService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEVEL_ORDER = ("A0", "A1", "A2", "B1")

CATEGORY_DISPLAY: dict[str, str] = {
    "greetings": "Greetings",
    "introductions": "Introductions",
    "numbers": "Numbers",
    "colors": "Colors",
    "family": "Family",
}

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CategoryStrength:
    """Strength assessment for a single vocabulary category.

    Attributes:
        category: Category slug (e.g. ``"greetings"``).
        total_words: Number of vocabulary words mapped to this category.
        words_seen: Words the user has encountered at least once.
        accuracy: Ratio of correct answers to total attempts (0-1).
        is_weak: ``True`` when accuracy < 0.7 and the user has seen words.
    """

    category: str
    total_words: int
    words_seen: int
    accuracy: float
    is_weak: bool


@dataclass(frozen=True)
class LevelReadiness:
    """Readiness assessment for the user's current level.

    Attributes:
        current_level: CEFR level string (e.g. ``"A1"``).
        completed_in_level: Lessons completed within the current level unit.
        total_in_level: Total lessons available at the current level.
        readiness_pct: Completion percentage (0-100).
        is_ready: ``True`` when all lessons at the level are complete.
        next_level: The next CEFR level, or ``None`` at the highest level.
    """

    current_level: str
    completed_in_level: int
    total_in_level: int
    readiness_pct: float
    is_ready: bool
    next_level: str | None


@dataclass(frozen=True)
class DailyRecommendation:
    """Personalized daily learning recommendation.

    Attributes:
        next_lesson: The next lesson on the user's path, or ``None``.
        review_due_count: Number of vocabulary words due for review today.
        weak_categories: Categories where accuracy is below threshold.
        level_readiness: Current level progress summary, or ``None``.
        suggestion_text: Human-readable recommendation string.
    """

    next_lesson: Lesson | None
    review_due_count: int
    weak_categories: list[CategoryStrength]
    level_readiness: LevelReadiness | None
    suggestion_text: str


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AdaptiveService:
    """Produces daily learning recommendations from path, vocab, and level data."""

    def __init__(self, path_service: PathService, lesson_service: LessonService) -> None:
        self._path_service = path_service
        self._lesson_service = lesson_service

    # -- public API ---------------------------------------------------------

    def get_daily_recommendation(
        self,
        language: str,
        completed_lessons: list[LessonProgress],
        vocab_data: list[Vocabulary],
        review_due_count: int,
    ) -> DailyRecommendation:
        """Build a personalized daily recommendation.

        Args:
            language: Target language code (``"es"``, ``"de"``, ``"fr"``).
            completed_lessons: User's completed lesson records.
            vocab_data: User's vocabulary entries.
            review_due_count: Pre-computed count of words due for review.

        Returns:
            A ``DailyRecommendation`` combining all signals.
        """
        next_lesson = self._path_service.get_next_path_lesson(language, completed_lessons)
        weak_categories = [
            cs for cs in self.get_category_strengths(language, vocab_data) if cs.is_weak
        ]
        level_readiness = self._compute_level_readiness(language, completed_lessons)
        suggestion_text = self._build_suggestion(
            next_lesson, review_due_count, weak_categories, level_readiness,
        )

        return DailyRecommendation(
            next_lesson=next_lesson,
            review_due_count=review_due_count,
            weak_categories=weak_categories,
            level_readiness=level_readiness,
            suggestion_text=suggestion_text,
        )

    def get_category_strengths(
        self, language: str, vocab_data: list[Vocabulary],
    ) -> list[CategoryStrength]:
        """Compute strength per category based on vocabulary accuracy.

        Args:
            language: Target language code.
            vocab_data: User's vocabulary entries.

        Returns:
            One ``CategoryStrength`` per category found for the language.
        """
        lessons = self._lesson_service.get_lessons(language=language)

        # Build word -> category mapping from lesson vocabulary steps.
        word_to_category: dict[str, str] = {}
        for lesson in lessons:
            cat = lesson.metadata.category
            if not cat:
                continue
            for step in lesson.content.steps:
                if step.type.value == "vocabulary":
                    for vocab_item in step.vocabulary:
                        word = vocab_item.get("word", "").lower()
                        if word:
                            word_to_category[word] = cat

        # Group user vocab by category.
        category_vocab: dict[str, list[Vocabulary]] = {}
        for vocab in vocab_data:
            if vocab.language != language:
                continue
            cat = word_to_category.get(vocab.word.lower())
            if cat:
                category_vocab.setdefault(cat, []).append(vocab)

        # Compute per-category strength.
        strengths: list[CategoryStrength] = []
        for cat in self._lesson_service.get_categories(language=language):
            words = category_vocab.get(cat, [])
            total = len(words)
            seen = sum(1 for w in words if w.times_seen > 0)
            total_seen_count = sum(w.times_seen for w in words)
            total_correct_count = sum(w.times_correct for w in words)
            accuracy = (total_correct_count / total_seen_count) if total_seen_count > 0 else 0.0

            strengths.append(CategoryStrength(
                category=cat,
                total_words=total,
                words_seen=seen,
                accuracy=round(accuracy, 2),
                is_weak=accuracy < 0.7 and seen > 0,
            ))

        return strengths

    # -- private helpers ----------------------------------------------------

    def _compute_level_readiness(
        self, language: str, completed_lessons: list[LessonProgress],
    ) -> LevelReadiness | None:
        """Determine current level readiness from path progress.

        Args:
            language: Target language code.
            completed_lessons: User's completed lesson records.

        Returns:
            ``LevelReadiness`` for the active unit, or ``None`` if unavailable.
        """
        path_progress = self._path_service.get_path_progress(language, completed_lessons)
        if not path_progress:
            return None

        idx = path_progress.current_unit_index
        if idx >= len(path_progress.units):
            return None

        current_up = path_progress.units[idx]
        current_level = current_up.unit.level

        try:
            level_idx = LEVEL_ORDER.index(current_level)
            next_level = LEVEL_ORDER[level_idx + 1] if level_idx + 1 < len(LEVEL_ORDER) else None
        except ValueError:
            next_level = None

        total = current_up.total_count
        readiness_pct = (current_up.completed_count / total * 100) if total > 0 else 0.0

        return LevelReadiness(
            current_level=current_level,
            completed_in_level=current_up.completed_count,
            total_in_level=total,
            readiness_pct=round(readiness_pct, 1),
            is_ready=current_up.is_complete,
            next_level=next_level,
        )

    @staticmethod
    def _build_suggestion(
        next_lesson: Lesson | None,
        review_due_count: int,
        weak_categories: list[CategoryStrength],
        level_readiness: LevelReadiness | None,
    ) -> str:
        """Build a human-readable suggestion string.

        Args:
            next_lesson: The next lesson on the user's path.
            review_due_count: Words due for review.
            weak_categories: Categories below the accuracy threshold.
            level_readiness: Current level progress summary.

        Returns:
            A concise recommendation sentence (or sentences).
        """
        parts: list[str] = []

        if review_due_count > 0:
            noun = "word" if review_due_count == 1 else "words"
            parts.append(f"You have {review_due_count} {noun} ready for review.")

        if weak_categories:
            weak_names = [
                CATEGORY_DISPLAY.get(c.category, c.category) for c in weak_categories[:2]
            ]
            parts.append(f"Your {' and '.join(weak_names)} could use some practice.")

        if level_readiness and level_readiness.is_ready and level_readiness.next_level:
            parts.append(
                f"You've completed {level_readiness.current_level}"
                f" -- ready for {level_readiness.next_level}!"
            )
        elif next_lesson:
            parts.append(
                f'Continue with "{next_lesson.metadata.title}" to keep your streak going.'
            )

        if not parts:
            parts.append("Great job! Keep exploring to discover new vocabulary.")

        return " ".join(parts)


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------


@lru_cache
def get_adaptive_service() -> AdaptiveService:
    """Return a cached ``AdaptiveService`` singleton.

    Lazily imports path and lesson services to avoid circular imports.
    """
    from src.lessons.service import get_lesson_service
    from src.services.paths import get_path_service

    return AdaptiveService(get_path_service(), get_lesson_service())
