"""Lesson service for loading, filtering, and managing lessons.

Phase 6: Provides lesson management functionality including:
- Loading lessons from YAML files
- Filtering by language, level, category
- User progress integration
- Vocabulary extraction
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict

import yaml

from src.lessons.models import (
    AnyExercise,
    FillBlankExercise,
    Lesson,
    LessonContent,
    LessonLevel,
    LessonMetadata,
    LessonStep,
    LessonStepType,
    MultipleChoiceExercise,
    TranslateExercise,
    UserLessonProgress,
)


class LessonWithProgress(TypedDict):
    """TypedDict for lesson with associated progress."""

    lesson: Lesson
    progress: UserLessonProgress | None


class LessonService:
    """Service for loading and managing lessons.

    Attributes:
        lessons_dir: Path to the lessons directory.
    """

    def __init__(self, lessons_dir: Path | None = None) -> None:
        """Initialize the lesson service.

        Args:
            lessons_dir: Path to lessons directory. Defaults to data/lessons.
        """
        if lessons_dir is None:
            # Default to data/lessons relative to project root
            self.lessons_dir = Path(__file__).parent.parent.parent / "data" / "lessons"
        else:
            self.lessons_dir = lessons_dir

        self._lessons: dict[str, Lesson] = {}
        self._load_all_lessons()

    def _load_all_lessons(self) -> None:
        """Load all lessons from the lessons directory."""
        if not self.lessons_dir.exists():
            return

        # Walk through all YAML files in subdirectories
        for yaml_file in self.lessons_dir.rglob("*.yaml"):
            try:
                lesson = self._load_lesson_file(yaml_file)
                if lesson:
                    self._lessons[lesson.metadata.id] = lesson
            except Exception as e:
                # Log but continue loading other lessons
                print(f"Warning: Failed to load lesson from {yaml_file}: {e}")

        # Also check for .yml extension
        for yaml_file in self.lessons_dir.rglob("*.yml"):
            try:
                lesson = self._load_lesson_file(yaml_file)
                if lesson:
                    self._lessons[lesson.metadata.id] = lesson
            except Exception as e:
                print(f"Warning: Failed to load lesson from {yaml_file}: {e}")

    def _load_lesson_file(self, path: Path) -> Lesson | None:
        """Load a single lesson from a YAML file.

        Args:
            path: Path to the YAML file.

        Returns:
            Lesson object or None if parsing fails.
        """
        with path.open(encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f)

        if not data:
            return None

        # Parse metadata
        metadata = LessonMetadata(
            id=data.get("id", path.stem),
            title=data.get("title", "Untitled"),
            description=data.get("description", ""),
            language=data.get("language", "es"),
            level=LessonLevel(data.get("level", "A0")),
            estimated_minutes=data.get("estimated_minutes", 2),
            category=data.get("category"),
            tags=data.get("tags", []),
            prerequisites=data.get("prerequisites", []),
            vocabulary_count=data.get("vocabulary_count", 0),
            icon=data.get("icon", "📚"),
        )

        # Parse steps
        steps: list[LessonStep] = []
        for step_data in data.get("steps", []):
            step = LessonStep(
                type=LessonStepType(step_data.get("type", "instruction")),
                content=step_data.get("content", ""),
                order=step_data.get("order", len(steps) + 1),
                target_text=step_data.get("target_text"),
                translation=step_data.get("translation"),
                vocabulary=step_data.get("vocabulary", []),
                exercise_id=step_data.get("exercise_id"),
                audio_url=step_data.get("audio_url"),
            )
            steps.append(step)

        # Parse exercises
        exercises: list[AnyExercise] = []
        for ex_data in data.get("exercises", []):
            exercise = self._parse_exercise(ex_data)
            if exercise:
                exercises.append(exercise)

        content = LessonContent(steps=steps, exercises=exercises)
        return Lesson(metadata=metadata, content=content)

    def _parse_exercise(self, data: dict[str, Any]) -> AnyExercise | None:
        """Parse exercise data into the appropriate exercise type.

        Args:
            data: Exercise data dictionary.

        Returns:
            Exercise object or None.
        """
        ex_type = data.get("type", "multiple_choice")

        if ex_type == "multiple_choice":
            return MultipleChoiceExercise(
                id=data.get("id", ""),
                question=data.get("question", ""),
                options=data.get("options", []),
                correct_index=data.get("correct_index", 0),
                explanation=data.get("explanation"),
            )
        elif ex_type == "fill_blank":
            return FillBlankExercise(
                id=data.get("id", ""),
                sentence_template=data.get("sentence_template", ""),
                correct_answer=data.get("correct_answer", ""),
                hint=data.get("hint"),
                accept_alternatives=data.get("accept_alternatives", []),
                explanation=data.get("explanation"),
            )
        elif ex_type == "translate":
            return TranslateExercise(
                id=data.get("id", ""),
                source_text=data.get("source_text", ""),
                source_language=data.get("source_language", "en"),
                target_language=data.get("target_language", "es"),
                correct_translation=data.get("correct_translation", ""),
                accept_alternatives=data.get("accept_alternatives", []),
                explanation=data.get("explanation"),
            )

        return None

    # =========================================================================
    # Public API
    # =========================================================================

    def get_lesson(self, lesson_id: str) -> Lesson | None:
        """Get a lesson by ID.

        Args:
            lesson_id: The lesson identifier.

        Returns:
            Lesson or None if not found.
        """
        return self._lessons.get(lesson_id)

    def get_all_lessons(self) -> list[Lesson]:
        """Get all loaded lessons.

        Returns:
            List of all lessons.
        """
        return list(self._lessons.values())

    def get_lessons(
        self,
        language: str | None = None,
        level: LessonLevel | None = None,
        category: str | None = None,
    ) -> list[Lesson]:
        """Get lessons with optional filters.

        Args:
            language: Filter by language code.
            level: Filter by CEFR level.
            category: Filter by category.

        Returns:
            Filtered list of lessons.
        """
        lessons = self.get_all_lessons()

        if language:
            lessons = [lesson for lesson in lessons if lesson.metadata.language == language]
        if level:
            lessons = [lesson for lesson in lessons if lesson.metadata.level == level]
        if category:
            lessons = [lesson for lesson in lessons if lesson.metadata.category == category]

        return lessons

    def get_lessons_by_language(self, language: str) -> list[Lesson]:
        """Get lessons for a specific language.

        Args:
            language: Language code (es, de, fr).

        Returns:
            List of lessons in that language.
        """
        return self.get_lessons(language=language)

    def get_lessons_by_level(self, level: LessonLevel) -> list[Lesson]:
        """Get lessons for a specific CEFR level.

        Args:
            level: CEFR level.

        Returns:
            List of lessons at that level.
        """
        return self.get_lessons(level=level)

    def get_lessons_metadata(
        self,
        language: str | None = None,
        level: LessonLevel | None = None,
    ) -> list[LessonMetadata]:
        """Get only metadata for lessons (for listing).

        Args:
            language: Filter by language.
            level: Filter by level.

        Returns:
            List of lesson metadata objects.
        """
        lessons = self.get_lessons(language=language, level=level)
        return [lesson.metadata for lesson in lessons]

    def get_categories(self, language: str | None = None) -> list[str]:
        """Get unique categories from lessons.

        Args:
            language: Filter by language.

        Returns:
            List of unique category names.
        """
        lessons = self.get_lessons(language=language) if language else self.get_all_lessons()
        categories = {lesson.metadata.category for lesson in lessons if lesson.metadata.category}
        return sorted(categories)

    def get_lesson_vocabulary(self, lesson_id: str) -> list[dict[str, str]]:
        """Extract vocabulary from a lesson.

        Args:
            lesson_id: The lesson identifier.

        Returns:
            List of vocabulary items with word and translation.
        """
        lesson = self.get_lesson(lesson_id)
        if not lesson:
            return []

        vocabulary: list[dict[str, str]] = []
        for step in lesson.content.steps:
            if step.type == LessonStepType.VOCABULARY:
                vocabulary.extend(step.vocabulary)

        return vocabulary

    # =========================================================================
    # User Progress Integration
    # =========================================================================

    def get_lessons_with_progress(
        self,
        user_id: str,
        progress_data: list[UserLessonProgress],
        language: str | None = None,
        level: LessonLevel | None = None,
    ) -> list[LessonWithProgress]:
        """Get lessons merged with user progress.

        Args:
            user_id: User identifier.
            progress_data: List of user progress records.
            language: Filter by language.
            level: Filter by level.

        Returns:
            List of dicts with 'lesson' and 'progress' keys.
        """
        lessons = self.get_lessons(language=language, level=level)
        progress_map = {p.lesson_id: p for p in progress_data if p.user_id == user_id}

        result: list[LessonWithProgress] = []
        for lesson in lessons:
            result.append(
                LessonWithProgress(
                    lesson=lesson,
                    progress=progress_map.get(lesson.metadata.id),
                )
            )

        return result

    def get_next_recommended(
        self,
        user_id: str,
        progress_data: list[UserLessonProgress],
        language: str,
        level: LessonLevel,
    ) -> Lesson | None:
        """Get the next recommended uncompleted lesson.

        Args:
            user_id: User identifier.
            progress_data: List of user progress records.
            language: Target language.
            level: Current CEFR level.

        Returns:
            Next uncompleted lesson or None if all completed.
        """
        lessons_with_progress = self.get_lessons_with_progress(
            user_id=user_id,
            progress_data=progress_data,
            language=language,
            level=level,
        )

        for item in lessons_with_progress:
            progress = item["progress"]
            if progress is None or not progress.is_completed:
                return item["lesson"]

        return None

    def get_completed_count(
        self,
        progress_data: list[UserLessonProgress],
        language: str | None = None,
    ) -> int:
        """Count completed lessons.

        Args:
            progress_data: List of user progress records.
            language: Filter by language.

        Returns:
            Number of completed lessons.
        """
        lessons = self.get_lessons(language=language) if language else self.get_all_lessons()
        lesson_ids = {lesson.metadata.id for lesson in lessons}

        completed = sum(1 for p in progress_data if p.lesson_id in lesson_ids and p.is_completed)

        return completed


@lru_cache
def get_lesson_service() -> LessonService:
    """Get cached lesson service instance.

    Returns:
        Singleton LessonService instance.
    """
    return LessonService()
