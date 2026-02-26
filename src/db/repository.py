"""Repository pattern for Supabase data access layer.

Provides typed data access classes for each table, handling CRUD operations
through the Supabase client. All repositories are user-scoped for RLS compliance.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from postgrest.exceptions import APIError

from src.db.client import get_supabase

if TYPE_CHECKING:
    from supabase import Client as SupabaseClient
from src.db.models import LearningSession, LessonProgress, UserProfile, Vocabulary

logger = logging.getLogger(__name__)


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

    def get_by_id(self, vocab_id: int) -> Vocabulary | None:
        """Get vocabulary entry by ID.

        Args:
            vocab_id: The vocabulary entry ID.

        Returns:
            Vocabulary if found, None otherwise.
        """
        response = (
            self._client.table("vocabulary")
            .select("*")
            .eq("id", vocab_id)
            .eq("user_id", self._user_id)
            .execute()
        )
        if response.data:
            return Vocabulary(**response.data[0])
        return None

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

        Uses an insert-first strategy to avoid the race condition inherent in
        read-then-write. If a concurrent insert wins the unique constraint
        (user_id, word, language), the duplicate key error (23505) is caught
        and the method falls back to an update on the existing row.

        Args:
            word: The vocabulary word.
            translation: Translation to user's native language.
            language: Target language code (es, de).
            part_of_speech: Optional grammatical category.

        Returns:
            The created or updated Vocabulary entry.
        """
        try:
            # Optimistic path: try inserting a new entry first
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
        except APIError as exc:
            if exc.code != "23505":
                raise

            # Duplicate key: word already exists, fall back to update
            logger.debug(
                "Vocabulary insert conflict for word=%s language=%s, updating instead",
                word,
                language,
            )

        # Row definitely exists now - read current state and update
        existing = self.get_by_word_and_language(word, language)
        if existing is None:
            # Should not happen, but guard against unexpected state
            msg = f"Vocabulary entry not found after conflict: word={word!r}, language={language!r}"
            raise RuntimeError(msg)

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

        Note: This uses a read-then-write pattern which is technically
        susceptible to lost updates under concurrent writes. In practice the
        risk is negligible because a single user rarely triggers concurrent
        correct-answer submissions for the same word. An atomic Postgres
        RPC (e.g. ``vocabulary_increment_correct(word_id)``) would eliminate
        the window entirely if higher concurrency is needed in the future.

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

    # ==================== Spaced Repetition Methods ====================

    def get_due_for_review(self, language: str, limit: int | None = None) -> list[Vocabulary]:
        """Get vocabulary due for review, ordered by most overdue first.

        Queries words where next_review_at is not None AND next_review_at <= NOW().

        Args:
            language: Language code (es, de).
            limit: Optional maximum number of entries to return.

        Returns:
            List of Vocabulary entries due for review, ordered by next_review_at ASC.
        """
        query = (
            self._client.table("vocabulary")
            .select("*")
            .eq("user_id", self._user_id)
            .eq("language", language)
            .not_.is_("next_review_at", "null")
            .lte("next_review_at", datetime.now(UTC).isoformat())
            .order("next_review_at", desc=False)
        )

        if limit is not None:
            query = query.limit(limit)

        response = query.execute()
        return [Vocabulary(**item) for item in response.data]

    def get_due_by_keywords(
        self, language: str, keywords: list[str], limit: int = 5
    ) -> list[Vocabulary]:
        """Get due words where the word or translation contains any of the keywords.

        Used for intelligent chat weaving - finding review words that match
        the current conversation topic. Keyword matching is performed server-side
        using Supabase's .or_() filter with ilike conditions.

        Args:
            language: Language code (es, de).
            keywords: List of keywords to match against word or translation.
            limit: Maximum number of entries to return.

        Returns:
            List of matching Vocabulary entries due for review.
        """
        if not keywords:
            return []

        # Build OR filter for keyword matching across word and translation columns
        or_conditions = []
        for kw in keywords:
            escaped = kw.replace("%", "\\%")
            or_conditions.append(f"word.ilike.%{escaped}%")
            or_conditions.append(f"translation.ilike.%{escaped}%")

        or_filter = ",".join(or_conditions)

        response = (
            self._client.table("vocabulary")
            .select("*")
            .eq("user_id", self._user_id)
            .eq("language", language)
            .not_.is_("next_review_at", "null")
            .lte("next_review_at", datetime.now(UTC).isoformat())
            .or_(or_filter)
            .order("next_review_at", desc=False)
            .limit(limit)
            .execute()
        )
        return [Vocabulary(**item) for item in response.data]

    def update_review_schedule(self, vocab_id: int, updates: dict[str, Any]) -> Vocabulary | None:
        """Update SM-2 spaced repetition fields for a vocabulary entry.

        Updates scheduling fields and optionally increments times_seen/times_correct.

        Args:
            vocab_id: The vocabulary entry ID.
            updates: Dictionary with any of:
                - easiness_factor (float): New easiness factor
                - interval_days (int): New interval
                - repetition_count (int): New repetition count
                - next_review_at (datetime|str|None): Next review datetime
                - last_reviewed_at (datetime|str|None): Last reviewed datetime
                - times_seen (int): Absolute times_seen value
                - times_correct (int): Absolute times_correct value
                - increment_seen (bool): If True, increment times_seen by 1
                - increment_correct (bool): If True, increment times_correct by 1

        Returns:
            Updated Vocabulary if successful, None otherwise.
        """
        update_data = self._build_review_update_data(updates)

        # Handle increment flags - need to fetch current values first
        if updates.get("increment_seen") or updates.get("increment_correct"):
            self._apply_increment_flags(vocab_id, updates, update_data)

        if not update_data:
            return None

        response = (
            self._client.table("vocabulary")
            .update(update_data)
            .eq("id", vocab_id)
            .eq("user_id", self._user_id)
            .execute()
        )

        if response.data:
            return Vocabulary(**response.data[0])
        return None

    def _build_review_update_data(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Build update data dict from SM-2 scheduling fields.

        Args:
            updates: Raw updates dictionary.

        Returns:
            Processed update data for Supabase.
        """
        update_data: dict[str, Any] = {}

        # Direct copy fields
        direct_fields = [
            "easiness_factor",
            "interval_days",
            "repetition_count",
            "times_seen",
            "times_correct",
        ]
        for field in direct_fields:
            if field in updates:
                update_data[field] = updates[field]

        # Datetime fields (convert to ISO string if datetime object)
        datetime_fields = ["next_review_at", "last_reviewed_at"]
        for field in datetime_fields:
            if field in updates:
                value = updates[field]
                update_data[field] = value.isoformat() if isinstance(value, datetime) else value

        return update_data

    def _apply_increment_flags(
        self, vocab_id: int, updates: dict[str, Any], update_data: dict[str, Any]
    ) -> None:
        """Apply increment_seen and increment_correct flags to update_data.

        Note: Uses a read-then-write pattern for the increment. See the
        concurrency note on :meth:`increment_correct` -- the same low-risk
        trade-off applies here.

        Args:
            vocab_id: The vocabulary entry ID.
            updates: Raw updates dictionary with increment flags.
            update_data: Update data dict to modify in place.
        """
        current_response = (
            self._client.table("vocabulary")
            .select("times_seen, times_correct")
            .eq("id", vocab_id)
            .eq("user_id", self._user_id)
            .execute()
        )
        if not current_response.data:
            return

        current = current_response.data[0]
        if updates.get("increment_seen"):
            update_data["times_seen"] = current.get("times_seen", 0) + 1
        if updates.get("increment_correct"):
            update_data["times_correct"] = current.get("times_correct", 0) + 1

    def get_review_stats(self, language: str) -> dict[str, Any]:
        """Get review statistics for the user's vocabulary.

        Returns stats for display in the progress page and review UI.

        Args:
            language: Language code (es, de).

        Returns:
            Dictionary with:
                - due_count: Number of words currently due for review
                - total_in_rotation: Total words with scheduled reviews
                - next_review_at: Datetime of next upcoming review (if any)
        """
        now = datetime.now(UTC).isoformat()

        # Count words due for review (next_review_at <= NOW)
        due_response = (
            self._client.table("vocabulary")
            .select("id", count="exact")
            .eq("user_id", self._user_id)
            .eq("language", language)
            .not_.is_("next_review_at", "null")
            .lte("next_review_at", now)
            .execute()
        )
        due_count = due_response.count if due_response.count is not None else 0

        # Count total words in rotation (next_review_at IS NOT NULL)
        in_rotation_response = (
            self._client.table("vocabulary")
            .select("id", count="exact")
            .eq("user_id", self._user_id)
            .eq("language", language)
            .not_.is_("next_review_at", "null")
            .execute()
        )
        total_in_rotation = (
            in_rotation_response.count if in_rotation_response.count is not None else 0
        )

        # Get the next upcoming review (next_review_at > NOW, ordered ASC)
        next_review_response = (
            self._client.table("vocabulary")
            .select("next_review_at")
            .eq("user_id", self._user_id)
            .eq("language", language)
            .not_.is_("next_review_at", "null")
            .gt("next_review_at", now)
            .order("next_review_at", desc=False)
            .limit(1)
            .execute()
        )

        next_review_at = None
        if next_review_response.data:
            next_review_at = next_review_response.data[0].get("next_review_at")

        return {
            "due_count": due_count,
            "total_in_rotation": total_in_rotation,
            "next_review_at": next_review_at,
        }


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

        Uses Supabase upsert with the primary key (user_id, lesson_id) to
        atomically insert or update in a single round-trip, eliminating the
        race condition from the previous read-then-write approach.

        Args:
            lesson_id: The lesson identifier.
            score: Optional score (0-100).

        Returns:
            The created or updated LessonProgress.
        """
        completed_at = datetime.now(UTC).isoformat()

        response = (
            self._client.table("lesson_progress")
            .upsert(
                {
                    "user_id": self._user_id,
                    "lesson_id": lesson_id,
                    "completed_at": completed_at,
                    "score": score,
                },
                on_conflict="user_id,lesson_id",
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
