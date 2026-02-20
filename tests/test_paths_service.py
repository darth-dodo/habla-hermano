"""Tests for learning path service - path building, progress tracking, and navigation.

Validates PathService behavior including:
- Static path construction from lesson YAML data
- Progress mapping from flat LessonProgress records onto hierarchical paths
- Next-lesson navigation through the ordered path structure

All tests use a temporary directory populated with minimal YAML lesson files
so that LessonService can load them and PathService can build real paths.

Important implementation detail: completion is tracked by base lesson ID
(e.g. "greetings-001") across all CEFR levels. Completing a base lesson ID
marks it as done in every unit that contains that ID. This is by design --
the same category lesson exists at each level with the same base ID.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.db.models import LessonProgress
from src.lessons.service import LessonService
from src.services.paths import (
    CATEGORY_ORDER,
    LANGUAGE_META,
    LEVEL_ORDER,
    LearningPath,
    PathService,
    PathUnit,
)

# =============================================================================
# Constants
# =============================================================================

_TEST_LANGUAGE = "es"
_TEST_LANGUAGE_NAME = "Spanish"
_TEST_USER_ID = "test-user-path-001"
_NUM_LEVELS = len(LEVEL_ORDER)  # 4
_NUM_CATEGORIES = len(CATEGORY_ORDER)  # 5
_TOTAL_LESSONS = _NUM_LEVELS * _NUM_CATEGORIES  # 20


# =============================================================================
# Helpers
# =============================================================================


def _minimal_lesson_yaml(
    lesson_id: str,
    title: str,
    language: str,
    level: str,
    category: str,
    icon: str = "📚",
) -> str:
    """Build a minimal valid lesson YAML string for testing.

    Args:
        lesson_id: Unique lesson identifier (e.g. "greetings-001").
        title: Human-readable lesson title.
        language: Language code (es, de, fr).
        level: CEFR level string (A0, A1, A2, B1).
        category: Lesson category slug.
        icon: Display icon.

    Returns:
        YAML string suitable for writing to a .yaml file.
    """
    return f"""\
id: {lesson_id}
title: {title}
description: Test lesson for {category}
language: {language}
level: {level}
category: {category}
icon: "{icon}"
steps:
  - type: instruction
    content: "Welcome to {title}!"
    order: 1
exercises: []
"""


def _make_lesson_progress(
    lesson_id: str,
    completed: bool = False,
    score: int | None = None,
    user_id: str = _TEST_USER_ID,
) -> LessonProgress:
    """Build a LessonProgress instance for testing.

    Args:
        lesson_id: The lesson this progress is for.
        completed: Whether to mark the lesson as completed.
        score: Optional score value.
        user_id: User identifier.

    Returns:
        LessonProgress with completed_at set if completed is True.
    """
    return LessonProgress(
        user_id=user_id,
        lesson_id=lesson_id,
        completed_at=datetime.now(UTC) if completed else None,
        score=score if completed else None,
    )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def full_lessons_dir(tmp_path: Path) -> Path:
    """Create a temporary lessons directory with all 20 lessons for Spanish.

    Populates es/{A0,A1,A2,B1}/{category}-001.yaml for every combination
    of LEVEL_ORDER x CATEGORY_ORDER, giving PathService a complete dataset
    to build a full 4-unit path.

    Returns:
        Path to the root lessons directory.
    """
    lessons_dir = tmp_path / "lessons"

    for level in LEVEL_ORDER:
        level_dir = lessons_dir / _TEST_LANGUAGE / level
        level_dir.mkdir(parents=True)

        for cat in CATEGORY_ORDER:
            lid = f"{cat}-001"
            title = f"{cat.title()} {level}"
            yaml_content = _minimal_lesson_yaml(
                lesson_id=lid,
                title=title,
                language=_TEST_LANGUAGE,
                level=level,
                category=cat,
            )
            (level_dir / f"{lid}.yaml").write_text(yaml_content)

    return lessons_dir


@pytest.fixture
def lesson_service(full_lessons_dir: Path) -> LessonService:
    """Create a LessonService backed by the full temporary lessons directory."""
    return LessonService(lessons_dir=full_lessons_dir)


@pytest.fixture
def path_service(lesson_service: LessonService) -> PathService:
    """Create a PathService backed by the test LessonService."""
    return PathService(lesson_service)


@pytest.fixture
def all_lesson_ids() -> list[str]:
    """Return all unique base lesson IDs in CATEGORY_ORDER.

    Since completion is tracked by base ID and the same IDs appear in every
    unit, completing these 5 IDs effectively completes all 20 path slots.
    """
    return [f"{cat}-001" for cat in CATEGORY_ORDER]


@pytest.fixture
def all_completed(all_lesson_ids: list[str]) -> list[LessonProgress]:
    """Create LessonProgress entries marking every base lesson ID as completed."""
    return [
        _make_lesson_progress(lesson_id=lid, completed=True, score=85) for lid in all_lesson_ids
    ]


# =============================================================================
# Path Building Tests
# =============================================================================


class TestPathBuilding:
    """Tests for static path construction from lesson data."""

    def test_path_builds_for_supported_language(self, path_service: PathService) -> None:
        """get_path should return a LearningPath for a supported language."""
        path = path_service.get_path(_TEST_LANGUAGE)

        assert path is not None
        assert isinstance(path, LearningPath)

    def test_path_has_correct_number_of_units(self, path_service: PathService) -> None:
        """Path should contain one unit per CEFR level (4 units for full data)."""
        path = path_service.get_path(_TEST_LANGUAGE)

        assert path is not None
        assert len(path.units) == _NUM_LEVELS

    def test_each_unit_has_correct_number_of_lessons(self, path_service: PathService) -> None:
        """Each unit should contain one lesson per category (5 lessons)."""
        path = path_service.get_path(_TEST_LANGUAGE)

        assert path is not None
        for unit in path.units:
            assert len(unit.lesson_ids) == _NUM_CATEGORIES, (
                f"Unit {unit.level} has {len(unit.lesson_ids)} lessons, expected {_NUM_CATEGORIES}"
            )

    def test_get_path_returns_none_for_unsupported_language(
        self, path_service: PathService
    ) -> None:
        """get_path should return None for a language not in LANGUAGE_META."""
        result = path_service.get_path("jp")

        assert result is None

    def test_lesson_ids_match_category_order(self, path_service: PathService) -> None:
        """Lesson IDs within each unit should follow CATEGORY_ORDER."""
        path = path_service.get_path(_TEST_LANGUAGE)

        assert path is not None
        expected_ids = tuple(f"{cat}-001" for cat in CATEGORY_ORDER)
        for unit in path.units:
            assert unit.lesson_ids == expected_ids

    def test_unit_levels_match_level_order(self, path_service: PathService) -> None:
        """Unit levels should appear in the same order as LEVEL_ORDER."""
        path = path_service.get_path(_TEST_LANGUAGE)

        assert path is not None
        unit_levels = tuple(unit.level for unit in path.units)
        assert unit_levels == LEVEL_ORDER

    def test_language_name_is_correct(self, path_service: PathService) -> None:
        """LearningPath.language_name should match LANGUAGE_META."""
        path = path_service.get_path(_TEST_LANGUAGE)

        assert path is not None
        assert path.language == _TEST_LANGUAGE
        assert path.language_name == _TEST_LANGUAGE_NAME

    def test_units_are_frozen_dataclass(self, path_service: PathService) -> None:
        """PathUnit instances should be frozen (immutable)."""
        path = path_service.get_path(_TEST_LANGUAGE)

        assert path is not None
        unit = path.units[0]
        assert isinstance(unit, PathUnit)
        with pytest.raises(AttributeError):
            unit.level = "B2"  # type: ignore[misc]

    def test_path_not_built_when_no_lessons_exist(self, tmp_path: Path) -> None:
        """PathService should not build a path when the lessons directory is empty."""
        empty_dir = tmp_path / "empty_lessons"
        empty_dir.mkdir()
        ls = LessonService(lessons_dir=empty_dir)
        ps = PathService(ls)

        for lang in LANGUAGE_META:
            assert ps.get_path(lang) is None


# =============================================================================
# Path Progress Tests
# =============================================================================


class TestPathProgress:
    """Tests for mapping completion data onto the path structure.

    Key design note: completion is tracked by base lesson ID (e.g. "greetings-001")
    not scoped to a specific level. So completing "greetings-001" marks it done in
    the A0 unit, A1 unit, A2 unit, and B1 unit simultaneously. This means
    completing N base IDs counts as N * NUM_LEVELS total completions.
    """

    def test_no_completions_all_zeros(self, path_service: PathService) -> None:
        """With no completions, counters should be zero and next_lesson is the first lesson."""
        progress = path_service.get_path_progress(_TEST_LANGUAGE, [])

        assert progress is not None
        assert progress.overall_completed == 0
        assert progress.overall_total == _TOTAL_LESSONS
        assert progress.current_unit_index == 0
        assert progress.next_lesson is not None
        assert progress.next_lesson.metadata.id == f"{CATEGORY_ORDER[0]}-001"

    def test_partial_completion_counts_across_all_units(self, path_service: PathService) -> None:
        """Completing a base ID counts once per unit that contains it.

        Completing 2 base IDs with 4 levels means 2 * 4 = 8 overall completions.
        The next_lesson should be the first uncompleted lesson in the first unit.
        """
        completed = [
            _make_lesson_progress(f"{CATEGORY_ORDER[0]}-001", completed=True, score=90),
            _make_lesson_progress(f"{CATEGORY_ORDER[1]}-001", completed=True, score=80),
        ]

        progress = path_service.get_path_progress(_TEST_LANGUAGE, completed)

        assert progress is not None
        # 2 base IDs completed across 4 units each = 8 total
        assert progress.overall_completed == 2 * _NUM_LEVELS
        # First unit is not fully complete (only 2 of 5 categories done)
        assert progress.current_unit_index == 0
        # Next lesson is the third category in the first unit
        assert progress.next_lesson is not None
        assert progress.next_lesson.metadata.id == f"{CATEGORY_ORDER[2]}-001"

    def test_all_base_ids_completed_marks_all_units_complete(
        self, path_service: PathService
    ) -> None:
        """Completing all 5 base IDs marks all 4 units as complete simultaneously."""
        completed = [
            _make_lesson_progress(f"{cat}-001", completed=True, score=85) for cat in CATEGORY_ORDER
        ]

        progress = path_service.get_path_progress(_TEST_LANGUAGE, completed)

        assert progress is not None
        # All units complete since every base ID is covered
        for unit_progress in progress.units:
            assert unit_progress.is_complete is True
        assert progress.next_lesson is None

    def test_all_completed_full_progress(
        self,
        path_service: PathService,
        all_completed: list[LessonProgress],
    ) -> None:
        """Completing all lessons should yield 100% and next_lesson = None."""
        progress = path_service.get_path_progress(_TEST_LANGUAGE, all_completed)

        assert progress is not None
        assert progress.overall_completed == progress.overall_total
        assert progress.completion_percentage == 100.0
        assert progress.next_lesson is None

    def test_completion_percentage_calculation(self, path_service: PathService) -> None:
        """completion_percentage should be (completed / total) * 100, rounded to 1 decimal."""
        # Complete 2 of 5 base IDs: 2 * 4 = 8 out of 20
        completed = [
            _make_lesson_progress(f"{CATEGORY_ORDER[0]}-001", completed=True, score=70),
            _make_lesson_progress(f"{CATEGORY_ORDER[1]}-001", completed=True, score=70),
        ]

        progress = path_service.get_path_progress(_TEST_LANGUAGE, completed)

        assert progress is not None
        expected_pct = round(8 / _TOTAL_LESSONS * 100, 1)  # 40.0
        assert progress.completion_percentage == expected_pct

    def test_score_mapped_from_lesson_progress(self, path_service: PathService) -> None:
        """Score from LessonProgress should appear on the corresponding LessonInUnit."""
        completed = [
            _make_lesson_progress(f"{CATEGORY_ORDER[0]}-001", completed=True, score=92),
        ]

        progress = path_service.get_path_progress(_TEST_LANGUAGE, completed)

        assert progress is not None
        first_unit = progress.units[0]
        first_lesson_in_unit = first_unit.lessons[0]
        assert first_lesson_in_unit.is_completed is True
        assert first_lesson_in_unit.score == 92

    def test_score_appears_in_every_unit_for_same_base_id(self, path_service: PathService) -> None:
        """The same score should appear in every unit for a completed base ID."""
        completed = [
            _make_lesson_progress(f"{CATEGORY_ORDER[0]}-001", completed=True, score=77),
        ]

        progress = path_service.get_path_progress(_TEST_LANGUAGE, completed)

        assert progress is not None
        for unit_progress in progress.units:
            first_lesson = unit_progress.lessons[0]
            assert first_lesson.is_completed is True
            assert first_lesson.score == 77

    def test_incomplete_lesson_has_no_score(self, path_service: PathService) -> None:
        """A lesson not in completed_lessons should have is_completed=False and score=None."""
        progress = path_service.get_path_progress(_TEST_LANGUAGE, [])

        assert progress is not None
        first_unit = progress.units[0]
        first_lesson_in_unit = first_unit.lessons[0]
        assert first_lesson_in_unit.is_completed is False
        assert first_lesson_in_unit.score is None

    def test_progress_returns_none_for_unsupported_language(
        self, path_service: PathService
    ) -> None:
        """get_path_progress should return None for an unsupported language."""
        result = path_service.get_path_progress("jp", [])

        assert result is None

    def test_unit_progress_counts(self, path_service: PathService) -> None:
        """UnitProgress should correctly count completed and total lessons per unit.

        Completing 3 base IDs means 3 of 5 are done in every unit.
        """
        completed = [
            _make_lesson_progress(f"{CATEGORY_ORDER[i]}-001", completed=True, score=75)
            for i in range(3)
        ]

        progress = path_service.get_path_progress(_TEST_LANGUAGE, completed)

        assert progress is not None
        # Every unit sees the same 3 completions
        for unit_progress in progress.units:
            assert unit_progress.completed_count == 3
            assert unit_progress.total_count == _NUM_CATEGORIES
            assert unit_progress.is_complete is False

    def test_lesson_progress_without_completed_at_not_counted(
        self, path_service: PathService
    ) -> None:
        """A LessonProgress with completed_at=None should not count as completed."""
        not_completed = [
            _make_lesson_progress(f"{CATEGORY_ORDER[0]}-001", completed=False),
        ]

        progress = path_service.get_path_progress(_TEST_LANGUAGE, not_completed)

        assert progress is not None
        assert progress.overall_completed == 0
        first_lesson = progress.units[0].lessons[0]
        assert first_lesson.is_completed is False

    def test_current_unit_index_is_last_when_all_complete(
        self,
        path_service: PathService,
        all_completed: list[LessonProgress],
    ) -> None:
        """When all units are complete, current_unit_index should be the last unit index."""
        progress = path_service.get_path_progress(_TEST_LANGUAGE, all_completed)

        assert progress is not None
        assert progress.current_unit_index == _NUM_LEVELS - 1


# =============================================================================
# Get Next Path Lesson Tests
# =============================================================================


class TestGetNextPathLesson:
    """Tests for the get_next_path_lesson convenience method."""

    def test_returns_first_lesson_when_nothing_completed(self, path_service: PathService) -> None:
        """With no completions, should return the very first lesson in the path."""
        next_lesson = path_service.get_next_path_lesson(_TEST_LANGUAGE, [])

        assert next_lesson is not None
        assert next_lesson.metadata.id == f"{CATEGORY_ORDER[0]}-001"
        assert next_lesson.metadata.level.value == LEVEL_ORDER[0]

    def test_returns_correct_next_after_partial_completion(self, path_service: PathService) -> None:
        """After completing the first base ID, the next uncompleted is the second category."""
        completed = [
            _make_lesson_progress(f"{CATEGORY_ORDER[0]}-001", completed=True, score=80),
        ]

        next_lesson = path_service.get_next_path_lesson(_TEST_LANGUAGE, completed)

        assert next_lesson is not None
        assert next_lesson.metadata.id == f"{CATEGORY_ORDER[1]}-001"

    def test_returns_none_when_all_completed(
        self,
        path_service: PathService,
        all_completed: list[LessonProgress],
    ) -> None:
        """When every base lesson ID is completed, should return None."""
        next_lesson = path_service.get_next_path_lesson(_TEST_LANGUAGE, all_completed)

        assert next_lesson is None

    def test_returns_none_for_unsupported_language(self, path_service: PathService) -> None:
        """For an unsupported language, should return None."""
        next_lesson = path_service.get_next_path_lesson("jp", [])

        assert next_lesson is None

    def test_skips_completed_finds_first_gap(self, path_service: PathService) -> None:
        """When first and third base IDs are completed, should return the second."""
        completed = [
            _make_lesson_progress(f"{CATEGORY_ORDER[0]}-001", completed=True, score=80),
            _make_lesson_progress(f"{CATEGORY_ORDER[2]}-001", completed=True, score=70),
        ]

        next_lesson = path_service.get_next_path_lesson(_TEST_LANGUAGE, completed)

        assert next_lesson is not None
        assert next_lesson.metadata.id == f"{CATEGORY_ORDER[1]}-001"

    def test_next_lesson_is_in_first_unit_level(self, path_service: PathService) -> None:
        """The next uncompleted lesson should be returned from the first unit (A0)."""
        completed = [
            _make_lesson_progress(f"{CATEGORY_ORDER[0]}-001", completed=True, score=80),
        ]

        next_lesson = path_service.get_next_path_lesson(_TEST_LANGUAGE, completed)

        assert next_lesson is not None
        # Should come from the first unit that has uncompleted lessons
        assert next_lesson.metadata.level.value == LEVEL_ORDER[0]
