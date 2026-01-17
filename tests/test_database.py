"""Tests for database module (models, repository, seed).

Comprehensive tests for SQLAlchemy models, repository pattern implementations,
and database seeding functionality.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.models import (
    Base,
    LessonProgress,
    Session,
    Setting,
    Vocabulary,
    get_session_factory,
)
from src.db.repository import (
    LessonProgressRepository,
    SessionRepository,
    SettingsRepository,
    VocabularyRepository,
)
from src.db.seed import DEFAULT_SETTINGS, seed_settings

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
async def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncSession:
    """Create a database session for testing."""
    async_session = async_sessionmaker(
        db_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with async_session() as session:
        yield session


# =============================================================================
# Model Tests
# =============================================================================


class TestVocabularyModel:
    """Tests for Vocabulary SQLAlchemy model."""

    async def test_vocabulary_creation_with_all_fields(self, db_session: AsyncSession) -> None:
        """Test creating Vocabulary with all fields."""
        vocab = Vocabulary(
            word="hola",
            translation="hello",
            language="es",
            part_of_speech="interjection",
            first_seen_at=datetime.utcnow(),
            times_seen=5,
        )
        db_session.add(vocab)
        await db_session.commit()
        await db_session.refresh(vocab)

        assert vocab.id is not None
        assert vocab.word == "hola"
        assert vocab.translation == "hello"
        assert vocab.language == "es"
        assert vocab.part_of_speech == "interjection"
        assert vocab.times_seen == 5

    async def test_vocabulary_creation_minimal(self, db_session: AsyncSession) -> None:
        """Test creating Vocabulary with minimal required fields."""
        vocab = Vocabulary(
            word="adios",
            translation="goodbye",
            language="es",
        )
        db_session.add(vocab)
        await db_session.commit()
        await db_session.refresh(vocab)

        assert vocab.id is not None
        assert vocab.word == "adios"
        assert vocab.times_seen == 1  # Default value
        assert vocab.first_seen_at is not None  # Default value

    async def test_vocabulary_repr(self, db_session: AsyncSession) -> None:
        """Test Vocabulary __repr__ method."""
        vocab = Vocabulary(word="gracias", translation="thank you", language="es")
        repr_str = repr(vocab)
        assert "Vocabulary" in repr_str
        assert "gracias" in repr_str
        assert "es" in repr_str

    async def test_vocabulary_unique_constraint(self, db_session: AsyncSession) -> None:
        """Test unique constraint on word+language combination."""
        from sqlalchemy.exc import IntegrityError

        vocab1 = Vocabulary(word="casa", translation="house", language="es")
        db_session.add(vocab1)
        await db_session.commit()

        # Same word, same language should fail
        vocab2 = Vocabulary(word="casa", translation="home", language="es")
        db_session.add(vocab2)

        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestSessionModel:
    """Tests for Session SQLAlchemy model."""

    async def test_session_creation_with_all_fields(self, db_session: AsyncSession) -> None:
        """Test creating Session with all fields."""
        now = datetime.utcnow()
        session = Session(
            language="es",
            level="A1",
            started_at=now,
            ended_at=now + timedelta(hours=1),
            messages_count=15,
            words_learned=8,
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        assert session.id is not None
        assert session.language == "es"
        assert session.level == "A1"
        assert session.messages_count == 15
        assert session.words_learned == 8

    async def test_session_creation_minimal(self, db_session: AsyncSession) -> None:
        """Test creating Session with minimal required fields."""
        session = Session(language="de", level="A0")
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        assert session.id is not None
        assert session.messages_count == 0  # Default value
        assert session.words_learned == 0  # Default value
        assert session.ended_at is None  # Default value

    async def test_session_repr(self, db_session: AsyncSession) -> None:
        """Test Session __repr__ method."""
        session = Session(language="es", level="B1")
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        repr_str = repr(session)
        assert "Session" in repr_str
        assert "es" in repr_str
        assert "B1" in repr_str


class TestSettingModel:
    """Tests for Setting SQLAlchemy model."""

    async def test_setting_creation(self, db_session: AsyncSession) -> None:
        """Test creating Setting."""
        setting = Setting(key="theme", value="dark")
        db_session.add(setting)
        await db_session.commit()
        await db_session.refresh(setting)

        assert setting.key == "theme"
        assert setting.value == "dark"

    async def test_setting_repr(self, db_session: AsyncSession) -> None:
        """Test Setting __repr__ method."""
        setting = Setting(key="language", value="es")
        repr_str = repr(setting)
        assert "Setting" in repr_str
        assert "language" in repr_str


class TestLessonProgressModel:
    """Tests for LessonProgress SQLAlchemy model."""

    async def test_lesson_progress_creation_with_all_fields(self, db_session: AsyncSession) -> None:
        """Test creating LessonProgress with all fields."""
        progress = LessonProgress(
            lesson_id="es-a1-basics",
            completed_at=datetime.utcnow(),
            score=85,
        )
        db_session.add(progress)
        await db_session.commit()
        await db_session.refresh(progress)

        assert progress.lesson_id == "es-a1-basics"
        assert progress.completed_at is not None
        assert progress.score == 85

    async def test_lesson_progress_creation_minimal(self, db_session: AsyncSession) -> None:
        """Test creating LessonProgress with minimal fields."""
        progress = LessonProgress(lesson_id="es-a1-greetings")
        db_session.add(progress)
        await db_session.commit()
        await db_session.refresh(progress)

        assert progress.lesson_id == "es-a1-greetings"
        assert progress.completed_at is None  # Default value
        assert progress.score is None  # Default value

    async def test_lesson_progress_repr(self, db_session: AsyncSession) -> None:
        """Test LessonProgress __repr__ method."""
        progress = LessonProgress(lesson_id="test-lesson", score=90)
        repr_str = repr(progress)
        assert "LessonProgress" in repr_str
        assert "test-lesson" in repr_str
        assert "90" in repr_str


class TestDatabaseInit:
    """Tests for database initialization functions."""

    async def test_init_db_creates_tables(self, db_engine) -> None:
        """Test init_db creates all expected tables."""
        async with db_engine.connect() as conn:
            tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())

        expected_tables = ["vocabulary", "sessions", "settings", "lesson_progress"]
        for table in expected_tables:
            assert table in tables

    def test_get_session_factory_returns_factory(self) -> None:
        """Test get_session_factory returns a valid session maker."""
        factory = get_session_factory()
        assert factory is not None
        assert callable(factory)


# =============================================================================
# Repository Tests
# =============================================================================


class TestVocabularyRepository:
    """Tests for VocabularyRepository data access layer."""

    async def test_get_by_word_and_language_found(self, db_session: AsyncSession) -> None:
        """Test retrieving an existing vocabulary entry."""
        vocab = Vocabulary(word="hola", translation="hello", language="es")
        db_session.add(vocab)
        await db_session.commit()

        repo = VocabularyRepository(db_session)
        result = await repo.get_by_word_and_language("hola", "es")

        assert result is not None
        assert result.word == "hola"
        assert result.translation == "hello"

    async def test_get_by_word_and_language_not_found(self, db_session: AsyncSession) -> None:
        """Test retrieving a non-existent vocabulary entry."""
        repo = VocabularyRepository(db_session)
        result = await repo.get_by_word_and_language("nonexistent", "es")

        assert result is None

    async def test_get_by_word_and_language_wrong_language(self, db_session: AsyncSession) -> None:
        """Test that word lookup is language-specific."""
        vocab = Vocabulary(word="casa", translation="house", language="es")
        db_session.add(vocab)
        await db_session.commit()

        repo = VocabularyRepository(db_session)
        result = await repo.get_by_word_and_language("casa", "de")

        assert result is None

    async def test_get_all_by_language(self, db_session: AsyncSession) -> None:
        """Test retrieving all vocabulary for a language."""
        words = [
            Vocabulary(word="uno", translation="one", language="es"),
            Vocabulary(word="dos", translation="two", language="es"),
            Vocabulary(word="eins", translation="one", language="de"),
        ]
        for word in words:
            db_session.add(word)
        await db_session.commit()

        repo = VocabularyRepository(db_session)
        spanish_words = await repo.get_all_by_language("es")

        assert len(spanish_words) == 2
        word_texts = {w.word for w in spanish_words}
        assert "uno" in word_texts
        assert "dos" in word_texts

    async def test_get_all_by_language_empty(self, db_session: AsyncSession) -> None:
        """Test retrieving vocabulary for a language with no entries."""
        repo = VocabularyRepository(db_session)
        result = await repo.get_all_by_language("fr")

        assert len(result) == 0

    async def test_get_all_by_language_ordered_by_first_seen(
        self, db_session: AsyncSession
    ) -> None:
        """Test that vocabulary is ordered by first_seen_at descending."""
        now = datetime.utcnow()
        old_vocab = Vocabulary(
            word="viejo",
            translation="old",
            language="es",
            first_seen_at=now - timedelta(days=1),
        )
        new_vocab = Vocabulary(
            word="nuevo",
            translation="new",
            language="es",
            first_seen_at=now,
        )

        db_session.add(old_vocab)
        db_session.add(new_vocab)
        await db_session.commit()

        repo = VocabularyRepository(db_session)
        result = await repo.get_all_by_language("es")

        assert len(result) == 2
        # Most recent should be first (descending order)
        assert result[0].word == "nuevo"
        assert result[1].word == "viejo"

    async def test_upsert_new_entry(self, db_session: AsyncSession) -> None:
        """Test inserting a new vocabulary entry via upsert."""
        repo = VocabularyRepository(db_session)

        result = await repo.upsert(
            word="mesa",
            translation="table",
            language="es",
            part_of_speech="noun",
        )

        assert result is not None
        assert result.word == "mesa"
        assert result.translation == "table"
        assert result.language == "es"
        assert result.part_of_speech == "noun"
        assert result.times_seen == 1

    async def test_upsert_existing_entry_increments_times_seen(
        self, db_session: AsyncSession
    ) -> None:
        """Test that upsert increments times_seen for existing entries."""
        repo = VocabularyRepository(db_session)

        # First insert
        first = await repo.upsert(
            word="silla",
            translation="chair",
            language="es",
        )
        assert first.times_seen == 1

        # Second upsert - should increment
        await repo.upsert(
            word="silla",
            translation="chair",
            language="es",
        )
        # Expire session cache to get fresh data from database
        db_session.expire_all()
        second = await repo.get_by_word_and_language("silla", "es")
        assert second is not None
        assert second.times_seen == 2

        # Third upsert
        await repo.upsert(
            word="silla",
            translation="chair (updated)",
            language="es",
        )
        db_session.expire_all()
        third = await repo.get_by_word_and_language("silla", "es")
        assert third is not None
        assert third.times_seen == 3
        assert third.translation == "chair (updated)"

    async def test_upsert_updates_translation_and_pos(self, db_session: AsyncSession) -> None:
        """Test that upsert updates translation and part_of_speech."""
        repo = VocabularyRepository(db_session)

        # Initial insert
        await repo.upsert(
            word="comer",
            translation="to eat",
            language="es",
            part_of_speech="verb",
        )

        # Update with different translation and part_of_speech
        result = await repo.upsert(
            word="comer",
            translation="to eat (infinitive)",
            language="es",
            part_of_speech="verb-infinitive",
        )

        assert result.translation == "to eat (infinitive)"
        assert result.part_of_speech == "verb-infinitive"

    async def test_upsert_without_part_of_speech(self, db_session: AsyncSession) -> None:
        """Test upserting vocabulary without part_of_speech."""
        repo = VocabularyRepository(db_session)

        result = await repo.upsert(
            word="bien",
            translation="well",
            language="es",
        )

        assert result.part_of_speech is None

    async def test_get_recent(self, db_session: AsyncSession) -> None:
        """Test retrieving recently seen vocabulary."""
        repo = VocabularyRepository(db_session)

        # Create multiple entries
        for i in range(5):
            await repo.upsert(
                word=f"word{i}",
                translation=f"translation{i}",
                language="es",
            )

        result = await repo.get_recent("es", limit=3)

        assert len(result) == 3

    async def test_get_recent_default_limit(self, db_session: AsyncSession) -> None:
        """Test get_recent with default limit of 20."""
        repo = VocabularyRepository(db_session)

        # Create 25 entries
        for i in range(25):
            await repo.upsert(
                word=f"palabra{i}",
                translation=f"word{i}",
                language="es",
            )

        result = await repo.get_recent("es")

        assert len(result) == 20  # Default limit

    async def test_get_recent_respects_language(self, db_session: AsyncSession) -> None:
        """Test that get_recent only returns words for specified language."""
        repo = VocabularyRepository(db_session)

        await repo.upsert(word="hola", translation="hello", language="es")
        await repo.upsert(word="guten", translation="good", language="de")

        spanish_recent = await repo.get_recent("es", limit=10)
        german_recent = await repo.get_recent("de", limit=10)

        assert len(spanish_recent) == 1
        assert spanish_recent[0].word == "hola"
        assert len(german_recent) == 1
        assert german_recent[0].word == "guten"


class TestSessionRepository:
    """Tests for SessionRepository data access layer."""

    async def test_create_session(self, db_session: AsyncSession) -> None:
        """Test creating a new learning session."""
        repo = SessionRepository(db_session)

        result = await repo.create(language="es", level="A1")

        assert result is not None
        assert result.id is not None
        assert result.language == "es"
        assert result.level == "A1"
        assert result.messages_count == 0
        assert result.words_learned == 0
        assert result.started_at is not None
        assert result.ended_at is None

    async def test_get_by_id_found(self, db_session: AsyncSession) -> None:
        """Test retrieving an existing session by ID."""
        repo = SessionRepository(db_session)

        created = await repo.create(language="de", level="A2")
        result = await repo.get_by_id(created.id)

        assert result is not None
        assert result.id == created.id
        assert result.language == "de"
        assert result.level == "A2"

    async def test_get_by_id_not_found(self, db_session: AsyncSession) -> None:
        """Test retrieving a non-existent session."""
        repo = SessionRepository(db_session)

        result = await repo.get_by_id(99999)

        assert result is None

    async def test_end_session(self, db_session: AsyncSession) -> None:
        """Test ending a session with statistics."""
        repo = SessionRepository(db_session)

        # Create session
        session = await repo.create(language="es", level="B1")
        assert session.ended_at is None

        # End session
        await repo.end_session(
            session_id=session.id,
            messages_count=15,
            words_learned=8,
        )

        # Verify updates
        updated = await repo.get_by_id(session.id)
        assert updated is not None
        assert updated.ended_at is not None
        assert updated.messages_count == 15
        assert updated.words_learned == 8

    async def test_end_session_nonexistent(self, db_session: AsyncSession) -> None:
        """Test ending a non-existent session (should not raise)."""
        repo = SessionRepository(db_session)

        # Should not raise an error
        await repo.end_session(
            session_id=99999,
            messages_count=10,
            words_learned=5,
        )

    async def test_get_all(self, db_session: AsyncSession) -> None:
        """Test retrieving all sessions."""
        repo = SessionRepository(db_session)

        # Create multiple sessions
        await repo.create(language="es", level="A0")
        await repo.create(language="es", level="A1")
        await repo.create(language="de", level="A0")

        result = await repo.get_all()

        assert len(result) == 3

    async def test_get_all_with_limit(self, db_session: AsyncSession) -> None:
        """Test retrieving sessions with a limit."""
        repo = SessionRepository(db_session)

        # Create 5 sessions
        for i in range(5):
            await repo.create(language="es", level=f"A{i % 2}")

        result = await repo.get_all(limit=3)

        assert len(result) == 3

    async def test_get_all_ordered_by_started_at(self, db_session: AsyncSession) -> None:
        """Test that sessions are ordered by started_at descending."""
        repo = SessionRepository(db_session)

        # Create sessions
        first = await repo.create(language="es", level="A0")
        second = await repo.create(language="es", level="A1")

        result = await repo.get_all()

        # Most recent should be first
        assert result[0].id == second.id
        assert result[1].id == first.id

    async def test_get_all_empty(self, db_session: AsyncSession) -> None:
        """Test retrieving sessions when none exist."""
        repo = SessionRepository(db_session)

        result = await repo.get_all()

        assert len(result) == 0


class TestSettingsRepository:
    """Tests for SettingsRepository data access layer."""

    async def test_set_new_setting(self, db_session: AsyncSession) -> None:
        """Test setting a new configuration value."""
        repo = SettingsRepository(db_session)

        await repo.set("theme", "dark")

        result = await repo.get("theme")
        assert result == "dark"

    async def test_set_update_existing(self, db_session: AsyncSession) -> None:
        """Test updating an existing setting."""
        repo = SettingsRepository(db_session)

        await repo.set("language", "es")
        await repo.set("language", "de")

        result = await repo.get("language")
        assert result == "de"

    async def test_get_existing(self, db_session: AsyncSession) -> None:
        """Test getting an existing setting value."""
        repo = SettingsRepository(db_session)

        await repo.set("level", "A1")
        result = await repo.get("level")

        assert result == "A1"

    async def test_get_nonexistent(self, db_session: AsyncSession) -> None:
        """Test getting a non-existent setting returns None."""
        repo = SettingsRepository(db_session)

        result = await repo.get("nonexistent_key")

        assert result is None

    async def test_delete_existing(self, db_session: AsyncSession) -> None:
        """Test deleting an existing setting."""
        repo = SettingsRepository(db_session)

        await repo.set("to_delete", "value")
        await repo.delete("to_delete")

        result = await repo.get("to_delete")
        assert result is None

    async def test_delete_nonexistent(self, db_session: AsyncSession) -> None:
        """Test deleting a non-existent setting (should not raise)."""
        repo = SettingsRepository(db_session)

        # Should not raise an error
        await repo.delete("nonexistent_key")

    async def test_multiple_settings(self, db_session: AsyncSession) -> None:
        """Test managing multiple settings."""
        repo = SettingsRepository(db_session)

        await repo.set("setting1", "value1")
        await repo.set("setting2", "value2")
        await repo.set("setting3", "value3")

        assert await repo.get("setting1") == "value1"
        assert await repo.get("setting2") == "value2"
        assert await repo.get("setting3") == "value3"

    async def test_set_empty_value(self, db_session: AsyncSession) -> None:
        """Test setting an empty string as value."""
        repo = SettingsRepository(db_session)

        await repo.set("empty_setting", "")

        result = await repo.get("empty_setting")
        assert result == ""

    async def test_set_long_value(self, db_session: AsyncSession) -> None:
        """Test setting a long text value."""
        repo = SettingsRepository(db_session)

        long_value = "x" * 10000
        await repo.set("long_setting", long_value)

        result = await repo.get("long_setting")
        assert result == long_value


class TestLessonProgressRepository:
    """Tests for LessonProgressRepository data access layer."""

    async def test_get_by_lesson_id_found(self, db_session: AsyncSession) -> None:
        """Test retrieving existing lesson progress."""
        progress = LessonProgress(
            lesson_id="es-a1-basics",
            completed_at=datetime.utcnow(),
            score=90,
        )
        db_session.add(progress)
        await db_session.commit()

        repo = LessonProgressRepository(db_session)
        result = await repo.get_by_lesson_id("es-a1-basics")

        assert result is not None
        assert result.lesson_id == "es-a1-basics"
        assert result.score == 90

    async def test_get_by_lesson_id_not_found(self, db_session: AsyncSession) -> None:
        """Test retrieving non-existent lesson progress."""
        repo = LessonProgressRepository(db_session)

        result = await repo.get_by_lesson_id("nonexistent-lesson")

        assert result is None

    async def test_complete_lesson_new(self, db_session: AsyncSession) -> None:
        """Test completing a new lesson."""
        repo = LessonProgressRepository(db_session)

        result = await repo.complete_lesson("es-a1-greetings", score=85)

        assert result is not None
        assert result.lesson_id == "es-a1-greetings"
        assert result.completed_at is not None
        assert result.score == 85

    async def test_complete_lesson_update_existing(self, db_session: AsyncSession) -> None:
        """Test re-completing an existing lesson updates score."""
        repo = LessonProgressRepository(db_session)

        # First completion
        first = await repo.complete_lesson("es-a1-numbers", score=70)
        first_completed_at = first.completed_at

        # Re-complete with better score
        await repo.complete_lesson("es-a1-numbers", score=95)

        # Expire session cache to get fresh data from database
        db_session.expire_all()
        second = await repo.get_by_lesson_id("es-a1-numbers")
        assert second is not None
        assert second.lesson_id == "es-a1-numbers"
        assert second.score == 95
        # completed_at should be updated
        assert second.completed_at is not None
        assert second.completed_at >= first_completed_at

    async def test_complete_lesson_without_score(self, db_session: AsyncSession) -> None:
        """Test completing a lesson without providing a score."""
        repo = LessonProgressRepository(db_session)

        result = await repo.complete_lesson("es-a1-practice")

        assert result is not None
        assert result.lesson_id == "es-a1-practice"
        assert result.completed_at is not None
        assert result.score is None

    async def test_get_completed(self, db_session: AsyncSession) -> None:
        """Test retrieving all completed lessons."""
        repo = LessonProgressRepository(db_session)

        # Create some completed lessons
        await repo.complete_lesson("lesson-1", score=80)
        await repo.complete_lesson("lesson-2", score=90)
        await repo.complete_lesson("lesson-3", score=85)

        result = await repo.get_completed()

        assert len(result) == 3
        lesson_ids = {lp.lesson_id for lp in result}
        assert "lesson-1" in lesson_ids
        assert "lesson-2" in lesson_ids
        assert "lesson-3" in lesson_ids

    async def test_get_completed_excludes_incomplete(self, db_session: AsyncSession) -> None:
        """Test that get_completed excludes lessons without completed_at."""
        # Create incomplete lesson directly
        incomplete = LessonProgress(lesson_id="incomplete-lesson")
        db_session.add(incomplete)
        await db_session.commit()

        repo = LessonProgressRepository(db_session)

        # Complete a lesson
        await repo.complete_lesson("complete-lesson", score=100)

        result = await repo.get_completed()

        assert len(result) == 1
        assert result[0].lesson_id == "complete-lesson"

    async def test_get_completed_ordered_by_completed_at(self, db_session: AsyncSession) -> None:
        """Test that completed lessons are ordered by completed_at descending."""
        repo = LessonProgressRepository(db_session)

        # Complete lessons in order
        await repo.complete_lesson("first-lesson", score=70)
        await repo.complete_lesson("second-lesson", score=80)
        await repo.complete_lesson("third-lesson", score=90)

        result = await repo.get_completed()

        # Most recently completed should be first
        assert result[0].lesson_id == "third-lesson"
        assert result[1].lesson_id == "second-lesson"
        assert result[2].lesson_id == "first-lesson"

    async def test_get_completed_empty(self, db_session: AsyncSession) -> None:
        """Test get_completed when no lessons are completed."""
        repo = LessonProgressRepository(db_session)

        result = await repo.get_completed()

        assert len(result) == 0


# =============================================================================
# Seed Module Tests
# =============================================================================


class TestSeedModule:
    """Tests for database seeding functionality."""

    async def test_default_settings_constant(self) -> None:
        """Test that DEFAULT_SETTINGS contains expected keys."""
        assert "current_language" in DEFAULT_SETTINGS
        assert "current_level" in DEFAULT_SETTINGS
        assert "scaffolding_enabled" in DEFAULT_SETTINGS
        assert "auto_translate" in DEFAULT_SETTINGS

        # Verify default values
        assert DEFAULT_SETTINGS["current_language"] == "es"
        assert DEFAULT_SETTINGS["current_level"] == "A0"
        assert DEFAULT_SETTINGS["scaffolding_enabled"] == "true"
        assert DEFAULT_SETTINGS["auto_translate"] == "true"

    async def test_seed_settings_creates_defaults(self, db_session: AsyncSession) -> None:
        """Test that seed_settings creates all default settings."""
        await seed_settings(db_session)

        repo = SettingsRepository(db_session)

        for key, expected_value in DEFAULT_SETTINGS.items():
            actual_value = await repo.get(key)
            assert actual_value == expected_value, f"Setting {key} mismatch"

    async def test_seed_settings_does_not_overwrite_existing(
        self, db_session: AsyncSession
    ) -> None:
        """Test that seed_settings preserves existing settings."""
        repo = SettingsRepository(db_session)

        # Set a custom value before seeding
        await repo.set("current_language", "de")

        # Run seeding
        await seed_settings(db_session)

        # Custom value should be preserved
        result = await repo.get("current_language")
        assert result == "de"

    async def test_seed_settings_idempotent(self, db_session: AsyncSession) -> None:
        """Test that seed_settings can be run multiple times safely."""
        # Run seeding twice
        await seed_settings(db_session)
        await seed_settings(db_session)

        repo = SettingsRepository(db_session)

        # Settings should still be correct
        for key, expected_value in DEFAULT_SETTINGS.items():
            actual_value = await repo.get(key)
            assert actual_value == expected_value


# =============================================================================
# Integration Tests
# =============================================================================


class TestDatabaseIntegration:
    """Integration tests combining multiple repositories and models."""

    async def test_full_session_workflow(self, db_session: AsyncSession) -> None:
        """Test a complete session workflow with vocabulary tracking."""
        session_repo = SessionRepository(db_session)
        vocab_repo = VocabularyRepository(db_session)
        settings_repo = SettingsRepository(db_session)

        # 1. Set up settings
        await settings_repo.set("current_language", "es")
        await settings_repo.set("current_level", "A1")

        # 2. Start a session
        session = await session_repo.create(language="es", level="A1")
        assert session.id is not None

        # 3. Learn some vocabulary
        await vocab_repo.upsert("hola", "hello", "es", "interjection")
        await vocab_repo.upsert("adios", "goodbye", "es", "interjection")
        await vocab_repo.upsert("gracias", "thank you", "es", "interjection")

        # 4. End the session
        await session_repo.end_session(
            session_id=session.id,
            messages_count=10,
            words_learned=3,
        )

        # 5. Verify state
        completed_session = await session_repo.get_by_id(session.id)
        assert completed_session is not None
        assert completed_session.ended_at is not None
        assert completed_session.words_learned == 3

        vocab_count = await vocab_repo.get_all_by_language("es")
        assert len(vocab_count) == 3

    async def test_lesson_progress_with_vocabulary(self, db_session: AsyncSession) -> None:
        """Test lesson completion with associated vocabulary learning."""
        lesson_repo = LessonProgressRepository(db_session)
        vocab_repo = VocabularyRepository(db_session)

        # Complete a lesson
        await lesson_repo.complete_lesson("es-a1-greetings", score=85)

        # Learn vocabulary from that lesson
        await vocab_repo.upsert("buenos dias", "good morning", "es")
        await vocab_repo.upsert("buenas noches", "good night", "es")

        # Verify
        lesson = await lesson_repo.get_by_lesson_id("es-a1-greetings")
        assert lesson is not None
        assert lesson.score == 85

        vocab = await vocab_repo.get_all_by_language("es")
        assert len(vocab) == 2

    async def test_concurrent_vocabulary_upserts(self, db_session: AsyncSession) -> None:
        """Test that multiple upserts to the same word work correctly."""
        repo = VocabularyRepository(db_session)

        # Simulate multiple encounters with the same word
        for _ in range(5):
            await repo.upsert("importante", "important", "es", "adjective")

        # Verify times_seen
        result = await repo.get_by_word_and_language("importante", "es")
        assert result is not None
        assert result.times_seen == 5

    async def test_multi_language_vocabulary_separation(self, db_session: AsyncSession) -> None:
        """Test that vocabulary is properly separated by language."""
        repo = VocabularyRepository(db_session)

        # Add same word in different languages
        await repo.upsert("si", "yes", "es")
        await repo.upsert("si", "if", "it")  # Italian
        await repo.upsert("ja", "yes", "de")

        # Verify language separation
        spanish = await repo.get_by_word_and_language("si", "es")
        italian = await repo.get_by_word_and_language("si", "it")
        german = await repo.get_by_word_and_language("ja", "de")

        assert spanish.translation == "yes"
        assert italian.translation == "if"
        assert german.translation == "yes"

        # Verify get_all_by_language
        spanish_all = await repo.get_all_by_language("es")
        assert len(spanish_all) == 1
