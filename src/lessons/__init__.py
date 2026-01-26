"""Micro-lessons module for Habla Hermano.

Phase 6: Structured 2-3 minute learning modules that unlock conversation abilities.

This module provides:
- Lesson data models (metadata, steps, exercises)
- Lesson service for loading and filtering lessons
- User progress tracking
"""

from src.lessons.models import (
    Exercise,
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
from src.lessons.service import LessonService, get_lesson_service

__all__ = [
    "Exercise",
    "ExerciseType",
    "FillBlankExercise",
    "Lesson",
    "LessonContent",
    "LessonLevel",
    "LessonMetadata",
    "LessonService",
    "LessonStep",
    "LessonStepType",
    "MultipleChoiceExercise",
    "TranslateExercise",
    "UserLessonProgress",
    "get_lesson_service",
]
