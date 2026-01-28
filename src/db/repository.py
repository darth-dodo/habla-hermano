"""Repository pattern for Supabase data access layer.

Provides typed data access classes for each table, handling CRUD operations
through the Supabase client. All repositories are user-scoped for RLS compliance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.api.supabase_client import get_supabase

if TYPE_CHECKING:
    from supabase import Client as SupabaseClient
from src.db.models import LearningSession, LessonProgress, UserProfile, Vocabulary


class UserProfileRepository:
    """Data access for user_profiles table."""

    def __init__(self, user_id: str) -> None:
        """Initialize repository for a specific user.

        Args:
            user_id: Supabase auth user UUID.
        """
        self._user_id = user_id
        self._client = get_supabase()

    def get(self) -> UserProfile | None:
        """Get the user's profile.

        Returns:
            UserProfile if found, None otherwise.
        """
        response = self._client.table("user_profiles").select("*").eq("id", self._user_id).execute()
        if response.data:
            return UserProfile(**response.data[0])
        return None

    def update(
        self,
        display_name: str | None = None,
        preferred_language: str | None = None,
        current_level: str | None = None,
    ) -> UserProfile | None:
        """Update the user's profile.

        Args:
            display_name: Optional new display name.
            preferred_language: Optional new preferred language.
            current_level: Optional new CEFR level.

        Returns:
            Updated UserProfile if successful, None otherwise.
        """
        update_data: dict[str, Any] = {"updated_at": datetime.now(UTC).isoformat()}

        if display_name is not None:
            update_data["display_name"] = display_name
        if preferred_language is not None:
            update_data["preferred_language"] = preferred_language
        if current_level is not None:
            update_data["current_level"] = current_level

        response = (
            self._client.table("user_profiles")
            .update(update_data)
            .eq("id", self._user_id)
            .execute()
        )
        if response.data:
            return UserProfile(**response.data[0])
        return None


class VocabularyRepository:
    """Data access for vocabulary table."""

    def __init__(self, user_id: str, client: SupabaseClient | None = None) -> None:
        """Initialize repository for a specific user.

        Args:
            user_id: Supabase auth user UUID or guest session UUID.
            client: Optional Supabase client. Defaults to anon client.
                    Pass admin client for guest (session-based) access.
        """
        self._user_id = user_id
        self._client = client or get_supabase()

    def get_all(self, language: str | None = None) -> list[Vocabulary]:
        """Get all vocabulary for the user.

        Args:
            language: Optional language filter (es, de).

        Returns:
            List of Vocabulary entries.
        """
        query = (
            self._client.table("vocabulary")
            .select("*")
            .eq("user_id", self._user_id)
            .order("first_seen_at", desc=True)
        )
        if language:
            query = query.eq("language", language)

        response = query.execute()
        return [Vocabulary(**item) for item in response.data]

    def get_by_word_and_language(self, word: str, language: str) -> Vocabulary | None:
        """Get vocabulary entry by word and language.

        Args:
            word: The word to look up.
            language: Language code (es, de).

        Returns:
            Vocabulary if found, None otherwise.
        """
        response = (
            self._client.table("vocabulary")
            .select("*")
            .eq("user_id", self._user_id)
            .eq("word", word)
            .eq("language", language)
            .execute()
        )
        if response.data:
            return Vocabulary(**response.data[0])
        return None

    def upsert(
        self,
        word: str,
        translation: str,
        language: str,
        part_of_speech: str | None = None,
    ) -> Vocabulary:
        """Insert or update vocabulary entry.

        If the word already exists for this user/language, increments times_seen.

        Args:
            word: The vocabulary word.
            translation: Translation to user's native language.
            language: Target language code (es, de).
            part_of_speech: Optional grammatical category.

        Returns:
            The created or updated Vocabulary entry.
        """
        existing = self.get_by_word_and_language(word, language)

        if existing:
            # Update existing entry - increment times_seen
            response = (
                self._client.table("vocabulary")
                .update(
                    {
                        "translation": translation,
                        "part_of_speech": part_of_speech,
                        "times_seen": existing.times_seen + 1,
                    }
                )
                .eq("id", existing.id)
                .execute()
            )
        else:
            # Insert new entry
            response = (
                self._client.table("vocabulary")
                .insert(
                    {
                        "user_id": self._user_id,
                        "word": word,
                        "translation": translation,
                        "language": language,
                        "part_of_speech": part_of_speech,
                        "first_seen_at": datetime.now(UTC).isoformat(),
                        "times_seen": 1,
                        "times_correct": 0,
                    }
                )
                .execute()
            )

        return Vocabulary(**response.data[0])

    def get_recent(self, language: str, limit: int = 20) -> list[Vocabulary]:
        """Get most recently seen vocabulary.

        Args:
            language: Language code (es, de).
            limit: Maximum number of entries to return.

        Returns:
            List of recent Vocabulary entries.
        """
        response = (
            self._client.table("vocabulary")
            .select("*")
            .eq("user_id", self._user_id)
            .eq("language", language)
            .order("first_seen_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [Vocabulary(**item) for item in response.data]

    def delete(self, word_id: int) -> None:
        """Delete a vocabulary entry.

        Args:
            word_id: The vocabulary entry ID.
        """
        self._client.table("vocabulary").delete().eq("id", word_id).eq(
            "user_id", self._user_id
        ).execute()

    def increment_correct(self, word_id: int) -> None:
        """Increment the times_correct counter for a vocabulary entry.

        Args:
            word_id: The vocabulary entry ID.
        """
        # First get current value
        response = (
            self._client.table("vocabulary")
            .select("times_correct")
            .eq("id", word_id)
            .eq("user_id", self._user_id)
            .execute()
        )
        if response.data:
            current = response.data[0].get("times_correct", 0)
            self._client.table("vocabulary").update({"times_correct": current + 1}).eq(
                "id", word_id
            ).execute()


class LearningSessionRepository:
    """Data access for learning_sessions table."""

    def __init__(self, user_id: str, client: SupabaseClient | None = None) -> None:
        """Initialize repository for a specific user.

        Args:
            user_id: Supabase auth user UUID or guest session UUID.
            client: Optional Supabase client. Defaults to anon client.
                    Pass admin client for guest (session-based) access.
        """
        self._user_id = user_id
        self._client = client or get_supabase()

    def create(self, language: str, level: str) -> LearningSession:
        """Create a new learning session.

        Args:
            language: Target language (es, de).
            level: CEFR level (A0, A1, A2, B1).

        Returns:
            The created LearningSession.
        """
        response = (
            self._client.table("learning_sessions")
            .insert(
                {
                    "user_id": self._user_id,
                    "language": language,
                    "level": level,
                    "started_at": datetime.now(UTC).isoformat(),
                    "messages_count": 0,
                    "words_learned": 0,
                }
            )
            .execute()
        )
        return LearningSession(**response.data[0])

    def get_by_id(self, session_id: int) -> LearningSession | None:
        """Get session by ID.

        Args:
            session_id: The session ID.

        Returns:
            LearningSession if found, None otherwise.
        """
        response = (
            self._client.table("learning_sessions")
            .select("*")
            .eq("id", session_id)
            .eq("user_id", self._user_id)
            .execute()
        )
        if response.data:
            return LearningSession(**response.data[0])
        return None

    def end_session(self, session_id: int, messages_count: int, words_learned: int) -> None:
        """Mark session as ended with statistics.

        Args:
            session_id: The session ID.
            messages_count: Total messages in the session.
            words_learned: Number of new words learned.
        """
        self._client.table("learning_sessions").update(
            {
                "ended_at": datetime.now(UTC).isoformat(),
                "messages_count": messages_count,
                "words_learned": words_learned,
            }
        ).eq("id", session_id).eq("user_id", self._user_id).execute()

    def get_all(self, limit: int = 50) -> list[LearningSession]:
        """Get all sessions ordered by start time.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of LearningSession entries.
        """
        response = (
            self._client.table("learning_sessions")
            .select("*")
            .eq("user_id", self._user_id)
            .order("started_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [LearningSession(**item) for item in response.data]

    def get_active(self) -> LearningSession | None:
        """Get the currently active (not ended) session.

        Returns:
            Active LearningSession if exists, None otherwise.
        """
        response = (
            self._client.table("learning_sessions")
            .select("*")
            .eq("user_id", self._user_id)
            .is_("ended_at", "null")
            .order("started_at", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            return LearningSession(**response.data[0])
        return None


class LessonProgressRepository:
    """Data access for lesson_progress table."""

    def __init__(self, user_id: str, client: SupabaseClient | None = None) -> None:
        """Initialize repository for a specific user.

        Args:
            user_id: Supabase auth user UUID or guest session UUID.
            client: Optional Supabase client. Defaults to anon client.
                    Pass admin client for guest (session-based) access.
        """
        self._user_id = user_id
        self._client = client or get_supabase()

    def get_by_lesson_id(self, lesson_id: str) -> LessonProgress | None:
        """Get lesson progress by ID.

        Args:
            lesson_id: The lesson identifier.

        Returns:
            LessonProgress if found, None otherwise.
        """
        response = (
            self._client.table("lesson_progress")
            .select("*")
            .eq("user_id", self._user_id)
            .eq("lesson_id", lesson_id)
            .execute()
        )
        if response.data:
            return LessonProgress(**response.data[0])
        return None

    def complete_lesson(self, lesson_id: str, score: int | None = None) -> LessonProgress:
        """Mark lesson as completed with optional score.

        Args:
            lesson_id: The lesson identifier.
            score: Optional score (0-100).

        Returns:
            The created or updated LessonProgress.
        """
        existing = self.get_by_lesson_id(lesson_id)
        completed_at = datetime.now(UTC).isoformat()

        if existing:
            response = (
                self._client.table("lesson_progress")
                .update(
                    {
                        "completed_at": completed_at,
                        "score": score,
                    }
                )
                .eq("user_id", self._user_id)
                .eq("lesson_id", lesson_id)
                .execute()
            )
        else:
            response = (
                self._client.table("lesson_progress")
                .insert(
                    {
                        "user_id": self._user_id,
                        "lesson_id": lesson_id,
                        "completed_at": completed_at,
                        "score": score,
                    }
                )
                .execute()
            )

        return LessonProgress(**response.data[0])

    def get_completed(self) -> list[LessonProgress]:
        """Get all completed lessons.

        Returns:
            List of completed LessonProgress entries.
        """
        response = (
            self._client.table("lesson_progress")
            .select("*")
            .eq("user_id", self._user_id)
            .not_.is_("completed_at", "null")
            .order("completed_at", desc=True)
            .execute()
        )
        return [LessonProgress(**item) for item in response.data]

    def get_all(self) -> list[LessonProgress]:
        """Get all lesson progress for the user.

        Returns:
            List of all LessonProgress entries.
        """
        response = (
            self._client.table("lesson_progress").select("*").eq("user_id", self._user_id).execute()
        )
        return [LessonProgress(**item) for item in response.data]
