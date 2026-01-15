"""Database module for HablaAI."""

from src.db.models import (
    Base,
    LessonProgress,
    Session,
    Setting,
    Vocabulary,
    async_session_factory,
    engine,
    get_session_factory,
    init_db,
)
from src.db.repository import (
    LessonProgressRepository,
    SessionRepository,
    SettingsRepository,
    VocabularyRepository,
)
from src.db.seed import seed_database

__all__ = [
    "Base",
    "LessonProgress",
    "LessonProgressRepository",
    "Session",
    "SessionRepository",
    "Setting",
    "SettingsRepository",
    "Vocabulary",
    "VocabularyRepository",
    "async_session_factory",
    "engine",
    "get_session_factory",
    "init_db",
    "seed_database",
]
