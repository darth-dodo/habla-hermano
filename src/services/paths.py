"""Learning path service for structured lesson progression.

Organizes lessons into ordered paths by language, with units per CEFR level.
Provides progress tracking by mapping flat lesson completion data onto the
hierarchical path structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING

from src.api.validation import LANGUAGE_NAMES

if TYPE_CHECKING:
    from src.db.models import LessonProgress
    from src.lessons.models import Lesson
    from src.lessons.service import LessonService

# =============================================================================
# Constants
# =============================================================================

CATEGORY_ORDER: tuple[str, ...] = ("greetings", "introductions", "numbers", "colors", "family")
LEVEL_ORDER: tuple[str, ...] = ("A0", "A1", "A2", "B1")
# Re-export for backwards compatibility with tests
LANGUAGE_META: dict[str, str] = LANGUAGE_NAMES
LEVEL_META: dict[str, dict[str, str]] = {
    "A0": {
        "title": "Absolute Beginner",
        "icon": "\U0001f331",
        "description": "Your first words and phrases",
    },
    "A1": {
        "title": "Beginner",
        "icon": "\U0001f4d6",
        "description": "Basic conversations and introductions",
    },
    "A2": {
        "title": "Elementary",
        "icon": "\U0001f680",
        "description": "Everyday situations and simple interactions",
    },
    "B1": {
        "title": "Intermediate",
        "icon": "\U0001f3af",
        "description": "Express opinions and handle most situations",
    },
}

# =============================================================================
# Data Models
# =============================================================================


@dataclass(frozen=True)
class PathUnit:
    """A unit within a learning path, representing a single CEFR level.

    Attributes:
        level: CEFR level code (e.g. "A0").
        title: Human-readable level title.
        description: Short description of what the learner will achieve.
        icon: Emoji icon for display.
        lesson_ids: Ordered tuple of base lesson IDs in this unit.
    """

    level: str
    title: str
    description: str
    icon: str
    lesson_ids: tuple[str, ...]


@dataclass(frozen=True)
class LearningPath:
    """Full learning path for a single language.

    Attributes:
        language: Language code (es, de, fr).
        language_name: Human-readable language name.
        units: Ordered tuple of units from beginner to advanced.
    """

    language: str
    language_name: str
    units: tuple[PathUnit, ...]


@dataclass(frozen=True)
class LessonInUnit:
    """A lesson decorated with its completion status within a unit.

    Attributes:
        lesson: The full lesson object.
        is_completed: Whether the user has completed this lesson.
        score: The user's score if completed, otherwise None.
    """

    lesson: Lesson
    is_completed: bool
    score: int | None


@dataclass
class UnitProgress:
    """A unit with aggregated completion data.

    Attributes:
        unit: The static path unit definition.
        lessons: Lessons with their individual completion status.
        completed_count: Number of lessons completed in this unit.
        total_count: Total number of lessons in this unit.
        is_complete: Whether every lesson in the unit is completed.
    """

    unit: PathUnit
    lessons: list[LessonInUnit] = field(default_factory=list)
    completed_count: int = 0
    total_count: int = 0
    is_complete: bool = False


@dataclass
class PathProgress:
    """Full path progress combining static structure with user completion data.

    Attributes:
        path: The static learning path definition.
        units: Units with per-lesson completion data.
        overall_completed: Total lessons completed across all units.
        overall_total: Total lessons across all units.
        current_unit_index: Index of the first non-complete unit (or last if all done).
        next_lesson: The first uncompleted lesson, or None if all done.
        completion_percentage: Overall completion as a percentage (0.0-100.0).
    """

    path: LearningPath
    units: list[UnitProgress] = field(default_factory=list)
    overall_completed: int = 0
    overall_total: int = 0
    current_unit_index: int = 0
    next_lesson: Lesson | None = None
    completion_percentage: float = 0.0


# =============================================================================
# Service
# =============================================================================


class PathService:
    """Service for building and querying structured learning paths.

    Constructs static path definitions from the lesson catalog on init,
    then provides methods to overlay user progress data onto that structure.

    Attributes:
        _lesson_service: Underlying lesson service for lesson lookups.
        _paths: Cached path definitions keyed by language code.
    """

    def __init__(self, lesson_service: LessonService) -> None:
        """Initialize the path service.

        Args:
            lesson_service: Lesson service instance used to verify and
                retrieve lessons by ID, language, and level.
        """
        self._lesson_service = lesson_service
        self._paths: dict[str, LearningPath] = {}
        self._build_paths()

    def _build_paths(self) -> None:
        """Build static path definitions for each supported language.

        Iterates over all language/level/category combinations and verifies
        that each expected lesson exists in the lesson service before
        including it in the path.
        """
        for lang, lang_name in LANGUAGE_META.items():
            units: list[PathUnit] = []
            for level in LEVEL_ORDER:
                lesson_ids: list[str] = []
                for cat in CATEGORY_ORDER:
                    lid = f"{cat}-001"
                    lesson = self._lesson_service.get_lesson(lid, language=lang, level=level)
                    if lesson:
                        lesson_ids.append(lid)
                meta = LEVEL_META[level]
                if lesson_ids:
                    units.append(
                        PathUnit(
                            level=level,
                            title=meta["title"],
                            description=meta["description"],
                            icon=meta["icon"],
                            lesson_ids=tuple(lesson_ids),
                        )
                    )
            if units:
                self._paths[lang] = LearningPath(
                    language=lang,
                    language_name=lang_name,
                    units=tuple(units),
                )

    def get_path(self, language: str) -> LearningPath | None:
        """Get the static learning path for a language.

        Args:
            language: Language code (es, de, fr).

        Returns:
            LearningPath or None if the language is not supported.
        """
        return self._paths.get(language)

    def get_path_progress(
        self,
        language: str,
        completed_lessons: list[LessonProgress],
    ) -> PathProgress | None:
        """Map flat completion data onto the hierarchical path structure.

        Takes a list of lesson progress records and overlays them onto the
        static path definition to produce a fully decorated progress view.

        Args:
            language: Language code (es, de, fr).
            completed_lessons: List of LessonProgress records for the user.

        Returns:
            PathProgress with per-lesson and per-unit completion data,
            or None if no path exists for the given language.
        """
        path = self.get_path(language)
        if not path:
            return None

        completed_ids = {lp.lesson_id for lp in completed_lessons if lp.completed_at is not None}
        completed_scores = {
            lp.lesson_id: lp.score for lp in completed_lessons if lp.completed_at is not None
        }

        unit_progresses: list[UnitProgress] = []
        overall_completed = 0
        overall_total = 0
        current_unit_index = len(path.units) - 1
        next_lesson: Lesson | None = None
        found_current = False

        for i, unit in enumerate(path.units):
            lessons_in_unit: list[LessonInUnit] = []
            unit_completed = 0

            for lid in unit.lesson_ids:
                lesson = self._lesson_service.get_lesson(lid, language=language, level=unit.level)
                is_done = lid in completed_ids
                if is_done:
                    unit_completed += 1
                if lesson:
                    lessons_in_unit.append(
                        LessonInUnit(
                            lesson=lesson,
                            is_completed=is_done,
                            score=completed_scores.get(lid),
                        )
                    )
                    if not is_done and next_lesson is None:
                        next_lesson = lesson

            total = len(unit.lesson_ids)
            is_unit_complete = unit_completed == total and total > 0

            unit_progresses.append(
                UnitProgress(
                    unit=unit,
                    lessons=lessons_in_unit,
                    completed_count=unit_completed,
                    total_count=total,
                    is_complete=is_unit_complete,
                )
            )
            overall_completed += unit_completed
            overall_total += total

            if not is_unit_complete and not found_current:
                current_unit_index = i
                found_current = True

        pct = (overall_completed / overall_total * 100) if overall_total > 0 else 0.0

        return PathProgress(
            path=path,
            units=unit_progresses,
            overall_completed=overall_completed,
            overall_total=overall_total,
            current_unit_index=current_unit_index,
            next_lesson=next_lesson,
            completion_percentage=round(pct, 1),
        )

    def get_next_path_lesson(
        self,
        language: str,
        completed_lessons: list[LessonProgress],
    ) -> Lesson | None:
        """Get the next uncompleted lesson in the path.

        Convenience method that delegates to get_path_progress and
        returns just the next lesson.

        Args:
            language: Language code (es, de, fr).
            completed_lessons: List of LessonProgress records for the user.

        Returns:
            The first uncompleted Lesson in the path, or None.
        """
        progress = self.get_path_progress(language, completed_lessons)
        if progress:
            return progress.next_lesson
        return None


# =============================================================================
# Singleton
# =============================================================================


@lru_cache
def get_path_service() -> PathService:
    """Get cached path service singleton.

    Returns:
        PathService instance backed by the singleton LessonService.
    """
    from src.lessons.service import get_lesson_service

    return PathService(get_lesson_service())
