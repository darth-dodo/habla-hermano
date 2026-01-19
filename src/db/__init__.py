"""Database module for Habla Hermano.

This module provides data access through Supabase Postgres.
All repositories are user-scoped to comply with Row Level Security.
"""

from src.db.models import (
    LearningSession,
    LessonProgress,
    Setting,
    UserProfile,
    Vocabulary,
)
from src.db.repository import (
    LearningSessionRepository,
    LessonProgressRepository,
    UserProfileRepository,
    VocabularyRepository,
)

__all__ = [
    "LearningSession",
    "LearningSessionRepository",
    "LessonProgress",
    "LessonProgressRepository",
    "Setting",
    "UserProfile",
    "UserProfileRepository",
    "Vocabulary",
    "VocabularyRepository",
]
