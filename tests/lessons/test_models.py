"""Tests for micro-lesson data models and structures.

TDD: These tests define the expected behavior for lesson models.
Implementation follows to make these tests pass.

Phase 6: Micro-lessons feature - structured 2-3 minute learning modules.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.lessons.models import (
    ExerciseType,
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

# =============================================================================
# LessonMetadata Tests
# =============================================================================


class TestLessonMetadata:
    """Tests for LessonMetadata model."""

    def test_create_minimal_metadata(self) -> None:
        """LessonMetadata should accept minimal required fields."""
        metadata = LessonMetadata(
            id="greetings-001",
            title="Basic Greetings",
            description="Learn to say hello and goodbye",
            language="es",
            level=LessonLevel.A0,
        )
        assert metadata.id == "greetings-001"
        assert metadata.title == "Basic Greetings"
        assert metadata.language == "es"
        assert metadata.level == LessonLevel.A0

    def test_metadata_with_all_fields(self) -> None:
        """LessonMetadata should accept all optional fields."""
        metadata = LessonMetadata(
            id="greetings-001",
            title="Basic Greetings",
            description="Learn to say hello and goodbye",
            language="es",
            level=LessonLevel.A0,
            estimated_minutes=3,
            category="greetings",
            tags=["greeting", "basics", "hello"],
            prerequisites=[],
            vocabulary_count=5,
            icon="👋",
        )
        assert metadata.estimated_minutes == 3
        assert metadata.category == "greetings"
        assert "hello" in metadata.tags
        assert metadata.icon == "👋"

    def test_metadata_default_estimated_minutes(self) -> None:
        """LessonMetadata should default to 2 minutes."""
        metadata = LessonMetadata(
            id="test",
            title="Test",
            description="Test",
            language="es",
            level=LessonLevel.A0,
        )
        assert metadata.estimated_minutes == 2

    def test_metadata_invalid_language(self) -> None:
        """LessonMetadata should reject unsupported languages."""
        with pytest.raises(ValidationError):
            LessonMetadata(
                id="test",
                title="Test",
                description="Test",
                language="xx",  # Invalid language code
                level=LessonLevel.A0,
            )

    def test_metadata_supported_languages(self) -> None:
        """LessonMetadata should accept all supported languages."""
        for lang in ["es", "de", "fr"]:
            metadata = LessonMetadata(
                id="test",
                title="Test",
                description="Test",
                language=lang,
                level=LessonLevel.A0,
            )
            assert metadata.language == lang

    def test_metadata_all_levels(self) -> None:
        """LessonMetadata should accept all CEFR levels."""
        for level in [LessonLevel.A0, LessonLevel.A1, LessonLevel.A2, LessonLevel.B1]:
            metadata = LessonMetadata(
                id="test",
                title="Test",
                description="Test",
                language="es",
                level=level,
            )
            assert metadata.level == level


# =============================================================================
# LessonStep Tests
# =============================================================================


class TestLessonStep:
    """Tests for LessonStep model."""

    def test_create_instruction_step(self) -> None:
        """LessonStep should create instruction type."""
        step = LessonStep(
            type=LessonStepType.INSTRUCTION,
            content="In Spanish, we say 'Hola' to greet someone.",
            order=1,
        )
        assert step.type == LessonStepType.INSTRUCTION
        assert "Hola" in step.content
        assert step.order == 1

    def test_create_example_step(self) -> None:
        """LessonStep should create example type with target_text."""
        step = LessonStep(
            type=LessonStepType.EXAMPLE,
            content="Hola, ¿cómo estás?",
            target_text="Hola, ¿cómo estás?",
            translation="Hello, how are you?",
            order=2,
        )
        assert step.type == LessonStepType.EXAMPLE
        assert step.translation == "Hello, how are you?"

    def test_create_vocabulary_step(self) -> None:
        """LessonStep should create vocabulary type with word list."""
        step = LessonStep(
            type=LessonStepType.VOCABULARY,
            content="Key vocabulary for this lesson:",
            vocabulary=[
                {"word": "hola", "translation": "hello"},
                {"word": "adiós", "translation": "goodbye"},
            ],
            order=3,
        )
        assert step.type == LessonStepType.VOCABULARY
        assert len(step.vocabulary) == 2
        assert step.vocabulary[0]["word"] == "hola"

    def test_create_practice_step(self) -> None:
        """LessonStep should create practice type with exercise reference."""
        step = LessonStep(
            type=LessonStepType.PRACTICE,
            content="Now try it yourself!",
            exercise_id="ex-001",
            order=4,
        )
        assert step.type == LessonStepType.PRACTICE
        assert step.exercise_id == "ex-001"

    def test_create_tip_step(self) -> None:
        """LessonStep should create tip/cultural note type."""
        step = LessonStep(
            type=LessonStepType.TIP,
            content="💡 In Spain, people often greet with two kisses on the cheek!",
            order=5,
        )
        assert step.type == LessonStepType.TIP

    def test_step_audio_url_optional(self) -> None:
        """LessonStep should allow optional audio URL."""
        step = LessonStep(
            type=LessonStepType.EXAMPLE,
            content="Hola",
            audio_url="/audio/hola.mp3",
            order=1,
        )
        assert step.audio_url == "/audio/hola.mp3"


# =============================================================================
# Exercise Tests
# =============================================================================


class TestMultipleChoiceExercise:
    """Tests for multiple choice exercise type."""

    def test_create_multiple_choice(self) -> None:
        """MultipleChoiceExercise should store question and options."""
        exercise = MultipleChoiceExercise(
            id="ex-mc-001",
            type=ExerciseType.MULTIPLE_CHOICE,
            question="How do you say 'hello' in Spanish?",
            options=["Hola", "Adiós", "Gracias", "Por favor"],
            correct_index=0,
            explanation="'Hola' means 'hello' in Spanish.",
        )
        assert exercise.type == ExerciseType.MULTIPLE_CHOICE
        assert len(exercise.options) == 4
        assert exercise.correct_index == 0
        assert exercise.options[exercise.correct_index] == "Hola"

    def test_multiple_choice_validates_correct_index(self) -> None:
        """MultipleChoiceExercise should validate correct_index is in range."""
        with pytest.raises(ValidationError):
            MultipleChoiceExercise(
                id="ex-mc-002",
                type=ExerciseType.MULTIPLE_CHOICE,
                question="Test",
                options=["A", "B"],
                correct_index=5,  # Out of range
            )

    def test_multiple_choice_minimum_options(self) -> None:
        """MultipleChoiceExercise should require at least 2 options."""
        with pytest.raises(ValidationError):
            MultipleChoiceExercise(
                id="ex-mc-003",
                type=ExerciseType.MULTIPLE_CHOICE,
                question="Test",
                options=["Only one"],  # Too few
                correct_index=0,
            )


class TestFillBlankExercise:
    """Tests for fill-in-the-blank exercise type."""

    def test_create_fill_blank(self) -> None:
        """FillBlankExercise should store sentence with blank."""
        exercise = FillBlankExercise(
            id="ex-fb-001",
            type=ExerciseType.FILL_BLANK,
            sentence_template="_____, me llamo Juan.",
            correct_answer="Hola",
            hint="A common greeting",
            accept_alternatives=["hola", "HOLA"],
        )
        assert exercise.type == ExerciseType.FILL_BLANK
        assert "_____" in exercise.sentence_template
        assert exercise.correct_answer == "Hola"
        assert "hola" in exercise.accept_alternatives

    def test_fill_blank_check_answer_correct(self) -> None:
        """FillBlankExercise.check_answer should accept correct answer."""
        exercise = FillBlankExercise(
            id="ex-fb-002",
            type=ExerciseType.FILL_BLANK,
            sentence_template="_____, ¿cómo estás?",
            correct_answer="Hola",
            accept_alternatives=["hola"],
        )
        assert exercise.check_answer("Hola") is True
        assert exercise.check_answer("hola") is True  # Case insensitive alternative

    def test_fill_blank_check_answer_wrong(self) -> None:
        """FillBlankExercise.check_answer should reject wrong answer."""
        exercise = FillBlankExercise(
            id="ex-fb-003",
            type=ExerciseType.FILL_BLANK,
            sentence_template="_____, ¿cómo estás?",
            correct_answer="Hola",
        )
        assert exercise.check_answer("Adiós") is False


class TestTranslateExercise:
    """Tests for translation exercise type."""

    def test_create_translate(self) -> None:
        """TranslateExercise should store source and target."""
        exercise = TranslateExercise(
            id="ex-tr-001",
            type=ExerciseType.TRANSLATE,
            source_text="Hello, my name is Maria.",
            source_language="en",
            target_language="es",
            correct_translation="Hola, me llamo Maria.",
            accept_alternatives=[
                "Hola, mi nombre es Maria.",
                "Hola, me llamo María.",
            ],
        )
        assert exercise.type == ExerciseType.TRANSLATE
        assert exercise.source_language == "en"
        assert exercise.target_language == "es"

    def test_translate_check_answer(self) -> None:
        """TranslateExercise.check_answer should handle alternatives."""
        exercise = TranslateExercise(
            id="ex-tr-002",
            type=ExerciseType.TRANSLATE,
            source_text="Hello",
            source_language="en",
            target_language="es",
            correct_translation="Hola",
            accept_alternatives=["hola", "¡Hola!"],
        )
        assert exercise.check_answer("Hola") is True
        assert exercise.check_answer("hola") is True
        assert exercise.check_answer("¡Hola!") is True
        assert exercise.check_answer("Adiós") is False


# =============================================================================
# LessonContent Tests
# =============================================================================


class TestLessonContent:
    """Tests for LessonContent model (full lesson structure)."""

    def test_create_lesson_content(self) -> None:
        """LessonContent should combine steps and exercises."""
        content = LessonContent(
            steps=[
                LessonStep(
                    type=LessonStepType.INSTRUCTION,
                    content="Let's learn greetings!",
                    order=1,
                ),
                LessonStep(
                    type=LessonStepType.EXAMPLE,
                    content="Hola",
                    translation="Hello",
                    order=2,
                ),
            ],
            exercises=[
                MultipleChoiceExercise(
                    id="ex-001",
                    type=ExerciseType.MULTIPLE_CHOICE,
                    question="What does 'Hola' mean?",
                    options=["Hello", "Goodbye", "Please", "Thank you"],
                    correct_index=0,
                ),
            ],
        )
        assert len(content.steps) == 2
        assert len(content.exercises) == 1

    def test_lesson_content_get_ordered_steps(self) -> None:
        """LessonContent.get_ordered_steps should return steps in order."""
        content = LessonContent(
            steps=[
                LessonStep(type=LessonStepType.TIP, content="Tip", order=3),
                LessonStep(type=LessonStepType.INSTRUCTION, content="First", order=1),
                LessonStep(type=LessonStepType.EXAMPLE, content="Second", order=2),
            ],
            exercises=[],
        )
        ordered = content.get_ordered_steps()
        assert ordered[0].content == "First"
        assert ordered[1].content == "Second"
        assert ordered[2].content == "Tip"

    def test_lesson_content_get_exercise_by_id(self) -> None:
        """LessonContent.get_exercise_by_id should find exercise."""
        content = LessonContent(
            steps=[],
            exercises=[
                MultipleChoiceExercise(
                    id="ex-001",
                    type=ExerciseType.MULTIPLE_CHOICE,
                    question="Q1",
                    options=["A", "B"],
                    correct_index=0,
                ),
                FillBlankExercise(
                    id="ex-002",
                    type=ExerciseType.FILL_BLANK,
                    sentence_template="_____ test",
                    correct_answer="The",
                ),
            ],
        )
        ex = content.get_exercise_by_id("ex-002")
        assert ex is not None
        assert ex.id == "ex-002"
        assert ex.type == ExerciseType.FILL_BLANK

    def test_lesson_content_exercise_not_found(self) -> None:
        """LessonContent.get_exercise_by_id should return None if not found."""
        content = LessonContent(steps=[], exercises=[])
        assert content.get_exercise_by_id("nonexistent") is None


# =============================================================================
# Full Lesson Tests
# =============================================================================


class TestLesson:
    """Tests for complete Lesson model."""

    def test_create_full_lesson(self) -> None:
        """Lesson should combine metadata and content."""
        lesson = Lesson(
            metadata=LessonMetadata(
                id="greetings-001",
                title="Basic Greetings",
                description="Learn to say hello",
                language="es",
                level=LessonLevel.A0,
            ),
            content=LessonContent(
                steps=[
                    LessonStep(
                        type=LessonStepType.INSTRUCTION,
                        content="Welcome!",
                        order=1,
                    ),
                ],
                exercises=[],
            ),
        )
        assert lesson.metadata.id == "greetings-001"
        assert len(lesson.content.steps) == 1

    def test_lesson_step_count(self) -> None:
        """Lesson.step_count should return number of steps."""
        lesson = Lesson(
            metadata=LessonMetadata(
                id="test",
                title="Test",
                description="Test",
                language="es",
                level=LessonLevel.A0,
            ),
            content=LessonContent(
                steps=[
                    LessonStep(type=LessonStepType.INSTRUCTION, content="1", order=1),
                    LessonStep(type=LessonStepType.EXAMPLE, content="2", order=2),
                    LessonStep(type=LessonStepType.TIP, content="3", order=3),
                ],
                exercises=[],
            ),
        )
        assert lesson.step_count == 3

    def test_lesson_exercise_count(self) -> None:
        """Lesson.exercise_count should return number of exercises."""
        lesson = Lesson(
            metadata=LessonMetadata(
                id="test",
                title="Test",
                description="Test",
                language="es",
                level=LessonLevel.A0,
            ),
            content=LessonContent(
                steps=[],
                exercises=[
                    MultipleChoiceExercise(
                        id="ex-1",
                        type=ExerciseType.MULTIPLE_CHOICE,
                        question="Q",
                        options=["A", "B"],
                        correct_index=0,
                    ),
                    FillBlankExercise(
                        id="ex-2",
                        type=ExerciseType.FILL_BLANK,
                        sentence_template="_____",
                        correct_answer="X",
                    ),
                ],
            ),
        )
        assert lesson.exercise_count == 2


# =============================================================================
# UserLessonProgress Tests
# =============================================================================


class TestUserLessonProgress:
    """Tests for user progress tracking on lessons."""

    def test_create_progress(self) -> None:
        """UserLessonProgress should track user's lesson state."""
        progress = UserLessonProgress(
            user_id="user-123",
            lesson_id="greetings-001",
            started_at=datetime.utcnow(),
            current_step=0,
            completed_exercises=[],
        )
        assert progress.user_id == "user-123"
        assert progress.lesson_id == "greetings-001"
        assert progress.current_step == 0
        assert progress.completed_at is None
        assert progress.is_completed is False

    def test_progress_mark_completed(self) -> None:
        """UserLessonProgress.mark_completed should set completion time."""
        progress = UserLessonProgress(
            user_id="user-123",
            lesson_id="greetings-001",
            started_at=datetime.utcnow(),
            current_step=5,
            completed_exercises=["ex-1", "ex-2"],
        )
        progress.mark_completed()
        assert progress.completed_at is not None
        assert progress.is_completed is True

    def test_progress_completion_percentage(self) -> None:
        """UserLessonProgress.completion_percentage should calculate progress."""
        progress = UserLessonProgress(
            user_id="user-123",
            lesson_id="greetings-001",
            started_at=datetime.utcnow(),
            current_step=2,
            total_steps=5,
            completed_exercises=["ex-1"],
            total_exercises=2,
        )
        # 2/5 steps = 40%, 1/2 exercises = 50%, average = 45%
        # Or simpler: (2 + 1) / (5 + 2) = 3/7 ≈ 43%
        percentage = progress.completion_percentage
        assert 0 <= percentage <= 100

    def test_progress_score_calculation(self) -> None:
        """UserLessonProgress should calculate score from exercise results."""
        progress = UserLessonProgress(
            user_id="user-123",
            lesson_id="greetings-001",
            started_at=datetime.utcnow(),
            current_step=5,
            exercise_results={"ex-1": True, "ex-2": True, "ex-3": False},
        )
        assert progress.score == 67  # 2/3 correct = 66.67% rounded


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and validation."""

    def test_empty_lesson_content(self) -> None:
        """LessonContent should allow empty steps and exercises."""
        content = LessonContent(steps=[], exercises=[])
        assert len(content.steps) == 0
        assert len(content.exercises) == 0

    def test_lesson_id_validation(self) -> None:
        """Lesson IDs should follow slug format."""
        # Valid slugs
        valid_ids = ["greetings-001", "basic_greetings", "lesson1", "a0-spanish-hello"]
        for lesson_id in valid_ids:
            metadata = LessonMetadata(
                id=lesson_id,
                title="Test",
                description="Test",
                language="es",
                level=LessonLevel.A0,
            )
            assert metadata.id == lesson_id

    def test_exercise_with_empty_options(self) -> None:
        """MultipleChoiceExercise should reject empty options."""
        with pytest.raises(ValidationError):
            MultipleChoiceExercise(
                id="ex-bad",
                type=ExerciseType.MULTIPLE_CHOICE,
                question="Test",
                options=[],  # Empty
                correct_index=0,
            )

    def test_vocabulary_step_empty_list(self) -> None:
        """Vocabulary step should allow empty vocabulary list."""
        step = LessonStep(
            type=LessonStepType.VOCABULARY,
            content="No vocabulary yet",
            vocabulary=[],
            order=1,
        )
        assert step.vocabulary == []

    def test_progress_with_no_exercises(self) -> None:
        """UserLessonProgress should handle lessons with no exercises."""
        progress = UserLessonProgress(
            user_id="user-123",
            lesson_id="no-exercises",
            started_at=datetime.utcnow(),
            current_step=3,
            total_steps=3,
            completed_exercises=[],
            total_exercises=0,
        )
        assert progress.completion_percentage >= 0
