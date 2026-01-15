"""Repository pattern for data access layer."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import LessonProgress, Session, Setting, Vocabulary


class VocabularyRepository:
    """Data access for vocabulary table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_word_and_language(
        self, word: str, language: str
    ) -> Vocabulary | None:
        """Get vocabulary entry by word and language."""
        stmt = select(Vocabulary).where(
            Vocabulary.word == word, Vocabulary.language == language
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_language(self, language: str) -> Sequence[Vocabulary]:
        """Get all vocabulary for a language."""
        stmt = (
            select(Vocabulary)
            .where(Vocabulary.language == language)
            .order_by(Vocabulary.first_seen_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def upsert(
        self,
        word: str,
        translation: str,
        language: str,
        part_of_speech: str | None = None,
    ) -> Vocabulary:
        """Insert or update vocabulary entry, incrementing times_seen on conflict."""
        stmt = (
            sqlite_insert(Vocabulary)
            .values(
                word=word,
                translation=translation,
                language=language,
                part_of_speech=part_of_speech,
                first_seen_at=datetime.utcnow(),
                times_seen=1,
            )
            .on_conflict_do_update(
                index_elements=["word", "language"],
                set_={
                    "times_seen": Vocabulary.times_seen + 1,
                    "translation": translation,
                    "part_of_speech": part_of_speech,
                },
            )
            .returning(Vocabulary)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.scalar_one()

    async def get_recent(self, language: str, limit: int = 20) -> Sequence[Vocabulary]:
        """Get most recently seen vocabulary."""
        stmt = (
            select(Vocabulary)
            .where(Vocabulary.language == language)
            .order_by(Vocabulary.first_seen_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


class SessionRepository:
    """Data access for sessions table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, language: str, level: str) -> Session:
        """Create a new learning session."""
        db_session = Session(language=language, level=level)
        self._session.add(db_session)
        await self._session.commit()
        await self._session.refresh(db_session)
        return db_session

    async def get_by_id(self, session_id: int) -> Session | None:
        """Get session by ID."""
        stmt = select(Session).where(Session.id == session_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def end_session(
        self, session_id: int, messages_count: int, words_learned: int
    ) -> None:
        """Mark session as ended with statistics."""
        stmt = (
            update(Session)
            .where(Session.id == session_id)
            .values(
                ended_at=datetime.utcnow(),
                messages_count=messages_count,
                words_learned=words_learned,
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def get_all(self, limit: int = 50) -> Sequence[Session]:
        """Get all sessions ordered by start time."""
        stmt = select(Session).order_by(Session.started_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()


class SettingsRepository:
    """Data access for settings table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str) -> str | None:
        """Get setting value by key."""
        stmt = select(Setting).where(Setting.key == key)
        result = await self._session.execute(stmt)
        setting = result.scalar_one_or_none()
        return setting.value if setting else None

    async def set(self, key: str, value: str) -> None:
        """Set or update a setting."""
        stmt = (
            sqlite_insert(Setting)
            .values(key=key, value=value)
            .on_conflict_do_update(index_elements=["key"], set_={"value": value})
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def delete(self, key: str) -> None:
        """Delete a setting."""
        stmt = select(Setting).where(Setting.key == key)
        result = await self._session.execute(stmt)
        setting = result.scalar_one_or_none()
        if setting:
            await self._session.delete(setting)
            await self._session.commit()


class LessonProgressRepository:
    """Data access for lesson_progress table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_lesson_id(self, lesson_id: str) -> LessonProgress | None:
        """Get lesson progress by ID."""
        stmt = select(LessonProgress).where(LessonProgress.lesson_id == lesson_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def complete_lesson(
        self, lesson_id: str, score: int | None = None
    ) -> LessonProgress:
        """Mark lesson as completed with optional score."""
        stmt = (
            sqlite_insert(LessonProgress)
            .values(lesson_id=lesson_id, completed_at=datetime.utcnow(), score=score)
            .on_conflict_do_update(
                index_elements=["lesson_id"],
                set_={"completed_at": datetime.utcnow(), "score": score},
            )
            .returning(LessonProgress)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.scalar_one()

    async def get_completed(self) -> Sequence[LessonProgress]:
        """Get all completed lessons."""
        stmt = (
            select(LessonProgress)
            .where(LessonProgress.completed_at.isnot(None))
            .order_by(LessonProgress.completed_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
