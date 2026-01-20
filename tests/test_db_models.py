"""Tests for database models.

Tests for Pydantic models used with Supabase.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.db.models import (
    LearningSession,
    LessonProgress,
    Setting,
    UserProfile,
    Vocabulary,
)

# =============================================================================
# UserProfile Tests
# =============================================================================


class TestUserProfile:
    """Tests for UserProfile model."""

    def test_create_with_required_fields(self) -> None:
        """Test creating UserProfile with only required fields."""
        profile = UserProfile(id="user-123")

        assert profile.id == "user-123"
        assert profile.display_name is None
        assert profile.preferred_language == "es"
        assert profile.current_level == "A1"

    def test_create_with_all_fields(self) -> None:
        """Test creating UserProfile with all fields."""
        now = datetime.utcnow()
        profile = UserProfile(
            id="user-123",
            display_name="Test User",
            preferred_language="de",
            current_level="B1",
            created_at=now,
            updated_at=now,
        )

        assert profile.id == "user-123"
        assert profile.display_name == "Test User"
        assert profile.preferred_language == "de"
        assert profile.current_level == "B1"
        assert profile.created_at == now
        assert profile.updated_at == now

    def test_default_timestamps(self) -> None:
        """Test that timestamps are auto-generated."""
        profile = UserProfile(id="user-123")

        assert profile.created_at is not None
        assert profile.updated_at is not None
        assert isinstance(profile.created_at, datetime)
        assert isinstance(profile.updated_at, datetime)


# =============================================================================
# Vocabulary Tests
# =============================================================================


class TestVocabulary:
    """Tests for Vocabulary model."""

    def test_create_with_required_fields(self) -> None:
        """Test creating Vocabulary with required fields."""
        vocab = Vocabulary(
            user_id="user-123",
            word="hola",
            translation="hello",
            language="es",
        )

        assert vocab.user_id == "user-123"
        assert vocab.word == "hola"
        assert vocab.translation == "hello"
        assert vocab.language == "es"
        assert vocab.id is None
        assert vocab.part_of_speech is None
        assert vocab.times_seen == 1
        assert vocab.times_correct == 0

    def test_create_with_all_fields(self) -> None:
        """Test creating Vocabulary with all fields."""
        now = datetime.utcnow()
        vocab = Vocabulary(
            id=1,
            user_id="user-123",
            word="hola",
            translation="hello",
            language="es",
            part_of_speech="interjection",
            first_seen_at=now,
            times_seen=5,
            times_correct=3,
        )

        assert vocab.id == 1
        assert vocab.part_of_speech == "interjection"
        assert vocab.first_seen_at == now
        assert vocab.times_seen == 5
        assert vocab.times_correct == 3

    def test_from_attributes_config(self) -> None:
        """Test from_attributes config is enabled."""
        assert Vocabulary.model_config.get("from_attributes") is True


# =============================================================================
# LearningSession Tests
# =============================================================================


class TestLearningSession:
    """Tests for LearningSession model."""

    def test_create_with_required_fields(self) -> None:
        """Test creating LearningSession with required fields."""
        session = LearningSession(
            user_id="user-123",
            language="es",
            level="A1",
        )

        assert session.user_id == "user-123"
        assert session.language == "es"
        assert session.level == "A1"
        assert session.id is None
        assert session.ended_at is None
        assert session.messages_count == 0
        assert session.words_learned == 0

    def test_create_with_all_fields(self) -> None:
        """Test creating LearningSession with all fields."""
        now = datetime.utcnow()
        session = LearningSession(
            id=1,
            user_id="user-123",
            started_at=now,
            ended_at=now,
            language="de",
            level="B1",
            messages_count=10,
            words_learned=5,
        )

        assert session.id == 1
        assert session.started_at == now
        assert session.ended_at == now
        assert session.messages_count == 10
        assert session.words_learned == 5

    def test_from_attributes_config(self) -> None:
        """Test from_attributes config is enabled."""
        assert LearningSession.model_config.get("from_attributes") is True


# =============================================================================
# LessonProgress Tests
# =============================================================================


class TestLessonProgress:
    """Tests for LessonProgress model."""

    def test_create_with_required_fields(self) -> None:
        """Test creating LessonProgress with required fields."""
        progress = LessonProgress(
            user_id="user-123",
            lesson_id="lesson-1",
        )

        assert progress.user_id == "user-123"
        assert progress.lesson_id == "lesson-1"
        assert progress.completed_at is None
        assert progress.score is None

    def test_create_with_all_fields(self) -> None:
        """Test creating LessonProgress with all fields."""
        now = datetime.utcnow()
        progress = LessonProgress(
            user_id="user-123",
            lesson_id="lesson-1",
            completed_at=now,
            score=95,
        )

        assert progress.completed_at == now
        assert progress.score == 95

    def test_from_attributes_config(self) -> None:
        """Test from_attributes config is enabled."""
        assert LessonProgress.model_config.get("from_attributes") is True


# =============================================================================
# Setting Tests
# =============================================================================


class TestSetting:
    """Tests for Setting model."""

    def test_create_setting(self) -> None:
        """Test creating Setting."""
        setting = Setting(
            user_id="user-123",
            key="theme",
            value="dark",
        )

        assert setting.user_id == "user-123"
        assert setting.key == "theme"
        assert setting.value == "dark"

    def test_from_attributes_config(self) -> None:
        """Test from_attributes config is enabled."""
        assert Setting.model_config.get("from_attributes") is True


# =============================================================================
# Model Validation Tests
# =============================================================================


class TestModelValidation:
    """Tests for model validation behavior."""

    def test_vocabulary_missing_required_field(self) -> None:
        """Test Vocabulary requires user_id."""
        with pytest.raises(ValidationError):
            Vocabulary(word="hola", translation="hello", language="es")  # type: ignore

    def test_user_profile_missing_id(self) -> None:
        """Test UserProfile requires id."""
        with pytest.raises(ValidationError):
            UserProfile()  # type: ignore

    def test_learning_session_missing_required(self) -> None:
        """Test LearningSession requires user_id, language, level."""
        with pytest.raises(ValidationError):
            LearningSession(user_id="user-123")  # type: ignore
