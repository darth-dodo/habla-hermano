"""Tests for lesson service - loading, filtering, and managing lessons.

TDD: These tests define the expected behavior for the lesson service.
Implementation follows to make these tests pass.

Phase 6: Micro-lessons feature.
"""

from pathlib import Path

import pytest

from src.lessons.models import (
    Lesson,
    LessonLevel,
    LessonMetadata,
    UserLessonProgress,
)
from src.lessons.service import LessonService

# =============================================================================
# LessonService Initialization Tests
# =============================================================================


class TestLessonServiceInit:
    """Tests for LessonService initialization."""

    def test_create_service_with_directory(self, tmp_path: Path) -> None:
        """LessonService should accept lessons directory path."""
        service = LessonService(lessons_dir=tmp_path)
        assert service.lessons_dir == tmp_path

    def test_service_default_directory(self) -> None:
        """LessonService should default to data/lessons directory."""
        service = LessonService()
        assert service.lessons_dir.name == "lessons"

    def test_service_loads_lessons_on_init(self, sample_lessons_dir: Path) -> None:
        """LessonService should load all lessons during initialization."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        assert len(service._lessons) > 0


# =============================================================================
# Lesson Loading Tests
# =============================================================================


class TestLessonLoading:
    """Tests for loading lessons from YAML files."""

    def test_load_lesson_from_yaml(self, sample_lessons_dir: Path) -> None:
        """LessonService should load lesson from YAML file."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        lesson = service.get_lesson("greetings-001")
        assert lesson is not None
        assert lesson.metadata.id == "greetings-001"

    def test_load_lesson_not_found(self, sample_lessons_dir: Path) -> None:
        """LessonService should return None for nonexistent lesson."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        lesson = service.get_lesson("nonexistent-lesson")
        assert lesson is None

    def test_load_all_lessons(self, sample_lessons_dir: Path) -> None:
        """LessonService.get_all_lessons should return all loaded lessons."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        lessons = service.get_all_lessons()
        assert len(lessons) >= 1
        assert all(isinstance(lesson, Lesson) for lesson in lessons)

    def test_lesson_yaml_structure(self, sample_lessons_dir: Path) -> None:
        """Loaded lesson should have correct structure from YAML."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        lesson = service.get_lesson("greetings-001")

        assert lesson is not None
        # Metadata
        assert lesson.metadata.title
        assert lesson.metadata.language == "es"
        assert lesson.metadata.level in [LessonLevel.A0, LessonLevel.A1]

        # Content
        assert len(lesson.content.steps) > 0


# =============================================================================
# Lesson Filtering Tests
# =============================================================================


class TestLessonFiltering:
    """Tests for filtering lessons by language, level, etc."""

    def test_filter_by_language(self, sample_lessons_dir: Path) -> None:
        """LessonService.get_lessons_by_language should filter by language."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        spanish_lessons = service.get_lessons_by_language("es")

        assert len(spanish_lessons) >= 1
        assert all(lesson.metadata.language == "es" for lesson in spanish_lessons)

    def test_filter_by_level(self, sample_lessons_dir: Path) -> None:
        """LessonService.get_lessons_by_level should filter by CEFR level."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        a0_lessons = service.get_lessons_by_level(LessonLevel.A0)

        assert all(lesson.metadata.level == LessonLevel.A0 for lesson in a0_lessons)

    def test_filter_by_language_and_level(self, sample_lessons_dir: Path) -> None:
        """LessonService.get_lessons should filter by both language and level."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        lessons = service.get_lessons(language="es", level=LessonLevel.A0)

        for lesson in lessons:
            assert lesson.metadata.language == "es"
            assert lesson.metadata.level == LessonLevel.A0

    def test_filter_by_category(self, sample_lessons_dir: Path) -> None:
        """LessonService.get_lessons should filter by category."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        greeting_lessons = service.get_lessons(category="greetings")

        for lesson in greeting_lessons:
            assert lesson.metadata.category == "greetings"

    def test_filter_empty_results(self, sample_lessons_dir: Path) -> None:
        """LessonService should return empty list when no matches."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        lessons = service.get_lessons(language="jp")  # Japanese not supported

        assert lessons == []

    def test_get_lesson_metadata_only(self, sample_lessons_dir: Path) -> None:
        """LessonService.get_lessons_metadata should return only metadata."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        metadata_list = service.get_lessons_metadata(language="es")

        assert len(metadata_list) >= 1
        assert all(isinstance(m, LessonMetadata) for m in metadata_list)


# =============================================================================
# Lesson Categories Tests
# =============================================================================


class TestLessonCategories:
    """Tests for lesson category management."""

    def test_get_all_categories(self, sample_lessons_dir: Path) -> None:
        """LessonService.get_categories should return unique categories."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        categories = service.get_categories()

        assert isinstance(categories, list)
        assert len(categories) == len(set(categories))  # All unique

    def test_get_categories_by_language(self, sample_lessons_dir: Path) -> None:
        """LessonService.get_categories should filter by language."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        categories = service.get_categories(language="es")

        assert isinstance(categories, list)


# =============================================================================
# User Progress Integration Tests
# =============================================================================


class TestUserProgressIntegration:
    """Tests for lesson service with user progress."""

    def test_get_lessons_with_progress(
        self, sample_lessons_dir: Path, mock_user_progress: list[UserLessonProgress]
    ) -> None:
        """LessonService should merge lessons with user progress."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        lessons_with_progress = service.get_lessons_with_progress(
            user_id="user-123",
            progress_data=mock_user_progress,
            language="es",
        )

        # Each result should have lesson and progress
        for item in lessons_with_progress:
            assert "lesson" in item
            assert "progress" in item

    def test_get_next_recommended_lesson(
        self, sample_lessons_dir: Path, mock_user_progress: list[UserLessonProgress]
    ) -> None:
        """LessonService should recommend next uncompleted lesson."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        next_lesson = service.get_next_recommended(
            user_id="user-123",
            progress_data=mock_user_progress,
            language="es",
            level=LessonLevel.A0,
        )

        # Should return a lesson or None if all completed
        assert next_lesson is None or isinstance(next_lesson, Lesson)

    def test_get_completed_lessons_count(
        self, sample_lessons_dir: Path, mock_user_progress: list[UserLessonProgress]
    ) -> None:
        """LessonService should count completed lessons."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        completed_count = service.get_completed_count(
            progress_data=mock_user_progress,
            language="es",
        )

        assert isinstance(completed_count, int)
        assert completed_count >= 0


# =============================================================================
# Lesson Vocabulary Extraction Tests
# =============================================================================


class TestVocabularyExtraction:
    """Tests for extracting vocabulary from lessons."""

    def test_get_lesson_vocabulary(self, sample_lessons_dir: Path) -> None:
        """LessonService.get_lesson_vocabulary should extract all vocab words."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        vocab = service.get_lesson_vocabulary("greetings-001")

        assert isinstance(vocab, list)
        # Each vocab item should have word and translation
        for item in vocab:
            assert "word" in item
            assert "translation" in item

    def test_vocabulary_extraction_from_steps(self, sample_lessons_dir: Path) -> None:
        """Vocabulary should be extracted from vocabulary steps."""
        service = LessonService(lessons_dir=sample_lessons_dir)
        vocab = service.get_lesson_vocabulary("greetings-001")

        # Should find vocab from vocabulary steps
        words = [v["word"] for v in vocab]
        # At least some basic greetings vocabulary
        assert len(words) > 0


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_lessons_dir(tmp_path: Path) -> Path:
    """Create sample lesson YAML files for testing."""
    lessons_dir = tmp_path / "lessons"
    lessons_dir.mkdir()

    # Spanish A0 lesson
    spanish_dir = lessons_dir / "es" / "A0"
    spanish_dir.mkdir(parents=True)

    greetings_yaml = """
id: greetings-001
title: Basic Greetings
description: Learn to say hello and goodbye in Spanish
language: es
level: A0
estimated_minutes: 3
category: greetings
tags:
  - greeting
  - basics
  - hello
vocabulary_count: 5
icon: "👋"

steps:
  - type: instruction
    content: "Welcome! Let's learn how to greet people in Spanish."
    order: 1

  - type: vocabulary
    content: "Key vocabulary for this lesson:"
    vocabulary:
      - word: hola
        translation: hello
      - word: adiós
        translation: goodbye
      - word: buenos días
        translation: good morning
      - word: buenas tardes
        translation: good afternoon
      - word: buenas noches
        translation: good night
    order: 2

  - type: example
    content: "Hola, ¿cómo estás?"
    translation: "Hello, how are you?"
    order: 3

  - type: tip
    content: "💡 'Hola' can be used at any time of day!"
    order: 4

  - type: practice
    content: "Now try the exercise!"
    exercise_id: "ex-mc-greet-001"
    order: 5

exercises:
  - id: ex-mc-greet-001
    type: multiple_choice
    question: "How do you say 'hello' in Spanish?"
    options:
      - Hola
      - Adiós
      - Gracias
      - Por favor
    correct_index: 0
    explanation: "'Hola' means 'hello' in Spanish."
"""
    (spanish_dir / "greetings-001.yaml").write_text(greetings_yaml)

    # Second lesson for filtering tests
    intro_yaml = """
id: introductions-001
title: Introducing Yourself
description: Learn to introduce yourself
language: es
level: A0
estimated_minutes: 3
category: introductions
tags:
  - introduction
  - name
vocabulary_count: 4
icon: "🙋"

steps:
  - type: instruction
    content: "Let's learn to introduce yourself!"
    order: 1

  - type: vocabulary
    content: "Key vocabulary:"
    vocabulary:
      - word: me llamo
        translation: my name is
      - word: mucho gusto
        translation: nice to meet you
    order: 2

exercises: []
"""
    (spanish_dir / "introductions-001.yaml").write_text(intro_yaml)

    return lessons_dir


@pytest.fixture
def mock_user_progress() -> list[UserLessonProgress]:
    """Create mock user progress data."""
    from datetime import datetime

    return [
        UserLessonProgress(
            user_id="user-123",
            lesson_id="greetings-001",
            started_at=datetime.utcnow(),
            current_step=5,
            total_steps=5,
            completed_exercises=["ex-mc-greet-001"],
            total_exercises=1,
            completed_at=datetime.utcnow(),
        ),
    ]
