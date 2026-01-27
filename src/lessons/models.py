"""Data models for micro-lessons.

Phase 6: Structured lesson content with steps, exercises, and progress tracking.

Models follow the pattern from product.md:
- Lessons are 2-3 minute focused learning modules
- Steps include instruction, vocabulary, examples, tips, and practice
- Exercises provide interactive practice (multiple choice, fill blank, translate)
- Progress tracks user completion and scores
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

# =============================================================================
# Enums
# =============================================================================


class LessonLevel(str, Enum):
    """CEFR proficiency levels for lessons."""

    A0 = "A0"  # Absolute beginner
    A1 = "A1"  # Beginner
    A2 = "A2"  # Elementary
    B1 = "B1"  # Intermediate


class LessonStepType(str, Enum):
    """Types of lesson steps."""

    INSTRUCTION = "instruction"  # Text explanation
    VOCABULARY = "vocabulary"  # Word list with translations
    EXAMPLE = "example"  # Example sentence/phrase
    TIP = "tip"  # Cultural note or learning tip
    PRACTICE = "practice"  # Exercise reference


class ExerciseType(str, Enum):
    """Types of exercises."""

    MULTIPLE_CHOICE = "multiple_choice"
    FILL_BLANK = "fill_blank"
    TRANSLATE = "translate"


# =============================================================================
# Lesson Metadata
# =============================================================================


class LessonMetadata(BaseModel):
    """Metadata for a lesson - used for listing and filtering.

    Attributes:
        id: Unique lesson identifier (slug format).
        title: Display title for the lesson.
        description: Brief description of what the lesson teaches.
        language: Target language code (es, de, fr).
        level: CEFR proficiency level.
        estimated_minutes: Expected completion time (default 2).
        category: Lesson category for grouping (greetings, food, etc.).
        tags: Searchable tags.
        prerequisites: List of lesson IDs that should be completed first.
        vocabulary_count: Number of vocabulary words in the lesson.
        icon: Emoji icon for display.
    """

    id: str
    title: str
    description: str
    language: str
    level: LessonLevel
    estimated_minutes: int = 2
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    vocabulary_count: int = 0
    icon: str = "📚"

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate language is supported."""
        supported = {"es", "de", "fr"}
        if v not in supported:
            raise ValueError(f"Language must be one of {supported}, got {v}")
        return v


# =============================================================================
# Lesson Steps
# =============================================================================


class LessonStep(BaseModel):
    """A single step in a lesson.

    Attributes:
        type: The type of step (instruction, vocabulary, example, tip, practice).
        content: Main text content for the step.
        order: Display order (1-based).
        target_text: Text in target language (for examples).
        translation: English translation (for examples/vocabulary).
        vocabulary: List of vocabulary items (for vocabulary steps).
        exercise_id: Reference to exercise (for practice steps).
        audio_url: Optional audio file URL.
    """

    type: LessonStepType
    content: str
    order: int
    target_text: str | None = None
    translation: str | None = None
    vocabulary: list[dict[str, str]] = Field(default_factory=list)
    exercise_id: str | None = None
    audio_url: str | None = None


# =============================================================================
# Exercises
# =============================================================================


class Exercise(BaseModel):
    """Base class for exercises."""

    id: str
    type: ExerciseType
    explanation: str | None = None


class MultipleChoiceExercise(Exercise):
    """Multiple choice exercise.

    Attributes:
        question: The question to answer.
        options: List of answer options.
        correct_index: Index of the correct answer (0-based).
        explanation: Shown after answering.
    """

    type: ExerciseType = ExerciseType.MULTIPLE_CHOICE
    question: str
    options: list[str]
    correct_index: int

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: list[str]) -> list[str]:
        """Validate minimum number of options."""
        if len(v) < 2:
            raise ValueError("Multiple choice must have at least 2 options")
        return v

    @model_validator(mode="after")
    def validate_correct_index(self) -> "MultipleChoiceExercise":
        """Validate correct_index is within range."""
        if self.correct_index < 0 or self.correct_index >= len(self.options):
            raise ValueError(
                f"correct_index {self.correct_index} out of range for {len(self.options)} options"
            )
        return self


class FillBlankExercise(Exercise):
    """Fill-in-the-blank exercise.

    Attributes:
        sentence_template: Sentence with _____ for the blank.
        correct_answer: The correct answer.
        hint: Optional hint text.
        accept_alternatives: Alternative correct answers.
    """

    type: ExerciseType = ExerciseType.FILL_BLANK
    sentence_template: str
    correct_answer: str
    hint: str | None = None
    accept_alternatives: list[str] = Field(default_factory=list)

    def check_answer(self, answer: str) -> bool:
        """Check if answer is correct.

        Args:
            answer: User's answer.

        Returns:
            True if correct (case-insensitive match with alternatives).
        """
        correct_answers = [self.correct_answer.lower()] + [
            alt.lower() for alt in self.accept_alternatives
        ]
        return answer.lower() in correct_answers


class TranslateExercise(Exercise):
    """Translation exercise.

    Attributes:
        source_text: Text to translate.
        source_language: Language of source text.
        target_language: Language to translate to.
        correct_translation: Expected translation.
        accept_alternatives: Alternative correct translations.
    """

    type: ExerciseType = ExerciseType.TRANSLATE
    source_text: str
    source_language: str
    target_language: str
    correct_translation: str
    accept_alternatives: list[str] = Field(default_factory=list)

    def check_answer(self, answer: str) -> bool:
        """Check if translation is correct.

        Args:
            answer: User's translation.

        Returns:
            True if correct (case-insensitive match with alternatives).
        """
        correct_answers = [self.correct_translation.lower()] + [
            alt.lower() for alt in self.accept_alternatives
        ]
        return answer.lower() in correct_answers


# Type alias for any exercise
AnyExercise = MultipleChoiceExercise | FillBlankExercise | TranslateExercise


# =============================================================================
# Lesson Content
# =============================================================================


class LessonContent(BaseModel):
    """Full content of a lesson.

    Attributes:
        steps: List of lesson steps.
        exercises: List of exercises.
    """

    steps: list[LessonStep] = Field(default_factory=list)
    exercises: list[AnyExercise] = Field(default_factory=list)

    def get_ordered_steps(self) -> list[LessonStep]:
        """Get steps sorted by order.

        Returns:
            List of steps sorted by order field.
        """
        return sorted(self.steps, key=lambda s: s.order)

    def get_exercise_by_id(self, exercise_id: str) -> AnyExercise | None:
        """Get exercise by ID.

        Args:
            exercise_id: The exercise ID to find.

        Returns:
            The exercise or None if not found.
        """
        for exercise in self.exercises:
            if exercise.id == exercise_id:
                return exercise
        return None


# =============================================================================
# Full Lesson
# =============================================================================


class Lesson(BaseModel):
    """Complete lesson with metadata and content.

    Attributes:
        metadata: Lesson metadata for listing/filtering.
        content: Full lesson content with steps and exercises.
    """

    metadata: LessonMetadata
    content: LessonContent

    @property
    def step_count(self) -> int:
        """Get number of steps in the lesson."""
        return len(self.content.steps)

    @property
    def exercise_count(self) -> int:
        """Get number of exercises in the lesson."""
        return len(self.content.exercises)


# =============================================================================
# User Progress
# =============================================================================


class UserLessonProgress(BaseModel):
    """User's progress on a lesson.

    Attributes:
        user_id: User identifier.
        lesson_id: Lesson identifier.
        started_at: When the user started the lesson.
        completed_at: When the user completed (None if not completed).
        current_step: Current step index (0-based).
        total_steps: Total number of steps.
        completed_exercises: List of completed exercise IDs.
        total_exercises: Total number of exercises.
        exercise_results: Map of exercise_id to correct (True/False).
    """

    user_id: str
    lesson_id: str
    started_at: datetime
    completed_at: datetime | None = None
    current_step: int = 0
    total_steps: int = 0
    completed_exercises: list[str] = Field(default_factory=list)
    total_exercises: int = 0
    exercise_results: dict[str, bool] = Field(default_factory=dict)

    @property
    def is_completed(self) -> bool:
        """Check if lesson is completed."""
        return self.completed_at is not None

    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage.

        Returns:
            Percentage (0-100) based on steps and exercises completed.
        """
        total = self.total_steps + self.total_exercises
        if total == 0:
            return 100.0 if self.is_completed else 0.0

        completed = self.current_step + len(self.completed_exercises)
        return min(100.0, (completed / total) * 100)

    @property
    def score(self) -> int:
        """Calculate score from exercise results.

        Returns:
            Score as percentage (0-100), rounded.
        """
        if not self.exercise_results:
            return 0

        correct = sum(1 for result in self.exercise_results.values() if result)
        total = len(self.exercise_results)
        return round((correct / total) * 100)

    def mark_completed(self) -> None:
        """Mark the lesson as completed."""
        self.completed_at = datetime.utcnow()
