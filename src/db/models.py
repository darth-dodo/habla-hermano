"""SQLAlchemy 2.0 async models for Habla Hermano."""

from datetime import datetime

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all models."""

    pass


class Vocabulary(Base):
    """Vocabulary learned across all sessions."""

    __tablename__ = "vocabulary"
    __table_args__ = (UniqueConstraint("word", "language", name="uq_word_language"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str] = mapped_column(String(100), nullable=False)
    translation: Mapped[str] = mapped_column(String(200), nullable=False)
    language: Mapped[str] = mapped_column(String(5), nullable=False)  # 'es' or 'de'
    part_of_speech: Mapped[str | None] = mapped_column(String(20))
    first_seen_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    times_seen: Mapped[int] = mapped_column(default=1)

    def __repr__(self) -> str:
        return f"<Vocabulary(word={self.word!r}, language={self.language!r})>"


class Session(Base):
    """Session statistics for learning tracking."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(default=None)
    language: Mapped[str] = mapped_column(String(5), nullable=False)
    level: Mapped[str] = mapped_column(String(5), nullable=False)  # A0, A1, A2, B1
    messages_count: Mapped[int] = mapped_column(default=0)
    words_learned: Mapped[int] = mapped_column(default=0)

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, language={self.language!r}, level={self.level!r})>"


class Setting(Base):
    """User settings (single user for MVP)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<Setting(key={self.key!r})>"


class LessonProgress(Base):
    """Lesson completion and scoring."""

    __tablename__ = "lesson_progress"

    lesson_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    score: Mapped[int | None] = mapped_column(default=None)

    def __repr__(self) -> str:
        return f"<LessonProgress(lesson_id={self.lesson_id!r}, score={self.score})>"


# Database engine and session factory
DATABASE_URL = "sqlite+aiosqlite:///data/habla.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get async session factory for dependency injection."""
    return async_session_factory
