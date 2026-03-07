"""Review service for spaced repetition using SM-2 algorithm.

Provides scheduling and management for vocabulary review sessions,
including due word queries, SM-2 interval calculations, and
topical word matching for chat weaving.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from src.db.repository import VocabularyRepository

if TYPE_CHECKING:
    from supabase import Client as SupabaseClient

    from src.db.models import Vocabulary

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReviewStats:
    """Statistics for review UI display.

    Attributes:
        due_count: Number of words currently due for review.
        next_review_in: Human-readable time until next review (e.g., "2 hours", "tomorrow").
        total_in_rotation: Total words scheduled for review (have next_review_at set).
    """

    due_count: int
    next_review_in: str | None
    total_in_rotation: int


class ReviewService:
    """Service for spaced repetition review operations.

    Handles SM-2 algorithm calculations, due word queries, and
    review session management. Works with both authenticated users
    and guest sessions.
    """

    def __init__(self, user_id: str, client: SupabaseClient | None = None) -> None:
        """Initialize review service for a user.

        Args:
            user_id: Supabase auth user UUID or guest session UUID.
            client: Optional Supabase client. Defaults to anon client.
                    Pass admin client for guest (session-based) access.
        """
        self._user_id = user_id
        self._vocab_repo = VocabularyRepository(user_id, client=client)

    def get_stats(self, language: str = "es") -> ReviewStats:
        """Get review statistics for UI display.

        Uses server-side queries to count due words and in-rotation totals
        instead of fetching all vocabulary and filtering in Python.

        Args:
            language: Target language code (es, de).

        Returns:
            ReviewStats with due count, next review time, and total in rotation.
        """
        repo_stats = self._vocab_repo.get_review_stats(language=language)

        due_count: int = repo_stats["due_count"]
        total_in_rotation: int = repo_stats["total_in_rotation"]

        # Calculate next review time from the repo's next_review_at
        next_review_in: str | None = None
        next_review_at_raw = repo_stats.get("next_review_at")
        if isinstance(next_review_at_raw, str):
            next_review_at = datetime.fromisoformat(next_review_at_raw)
            now = datetime.now(UTC)
            if next_review_at > now:
                next_review_in = self._format_timedelta(next_review_at - now)
        elif isinstance(next_review_at_raw, datetime):
            now = datetime.now(UTC)
            if next_review_at_raw > now:
                next_review_in = self._format_timedelta(next_review_at_raw - now)

        return ReviewStats(
            due_count=due_count,
            next_review_in=next_review_in,
            total_in_rotation=total_in_rotation,
        )

    def get_due_words(
        self,
        language: str,
        limit: int | None = None,
    ) -> list[Vocabulary]:
        """Get words due for review, ordered by most overdue first.

        Uses a server-side query with WHERE next_review_at <= NOW()
        instead of fetching all vocabulary and filtering in Python.

        Args:
            language: Target language code (es, de).
            limit: Maximum number of words to return. None returns all due words.

        Returns:
            List of Vocabulary entries due for review.
        """
        return self._vocab_repo.get_due_for_review(language=language, limit=limit)

    def get_topical_review_words(
        self,
        language: str,
        topic_keywords: list[str],
        limit: int = 5,
    ) -> list[Vocabulary]:
        """Get due words matching conversation topic for chat weaving.

        Uses server-side ilike queries to match keywords against word
        and translation columns instead of fetching all due words and
        filtering in Python.

        Args:
            language: Target language code (es, de).
            topic_keywords: Keywords from conversation to match against.
            limit: Maximum number of words to return.

        Returns:
            List of Vocabulary entries matching topic and due for review.
        """
        if not topic_keywords:
            return self._vocab_repo.get_due_for_review(language=language, limit=limit)

        return self._vocab_repo.get_due_by_keywords(
            language=language, keywords=topic_keywords, limit=limit
        )

    def update_sm2(self, vocab_id: int, quality: int) -> Vocabulary:
        """Apply SM-2 algorithm to a vocabulary item and persist.

        Uses an atomic Postgres RPC with optimistic concurrency control.
        The RPC ``vocabulary_update_sm2`` updates SM-2 scheduling fields
        and atomically increments ``times_seen`` / ``times_correct`` using
        ``SET col = col + 1``, guarded by a ``WHERE repetition_count =
        :expected`` clause.  If a concurrent request modified the row between
        the read and the write, the update affects 0 rows and the method
        re-reads the vocabulary and retries once.

        If the RPC is not deployed, falls back to the previous non-atomic
        path.

        Quality scores:
            5 - Perfect response, no hesitation
            4 - Correct with minor hesitation
            3 - Correct with difficulty (hint helped)
            2 - Incorrect, recognized correct answer
            1 - Incorrect, answer seemed unfamiliar
            0 - Complete blank / skip

        Args:
            vocab_id: The vocabulary entry ID.
            quality: Recall quality score (0-5).

        Returns:
            Updated Vocabulary entry with new SM-2 values.

        Raises:
            ValueError: If quality is not in range 0-5.
            ValueError: If vocabulary not found.
        """
        if not 0 <= quality <= 5:
            raise ValueError(f"Quality must be 0-5, got {quality}")

        # Fetch current vocabulary by ID (B3: eliminates full-table scan)
        vocab = self._vocab_repo.get_by_id(vocab_id)

        if vocab is None:
            raise ValueError(f"Vocabulary with id {vocab_id} not found")

        # Try atomic path (with one retry on optimistic lock failure)
        for attempt in range(2):
            if attempt > 0:
                # Re-read on retry after optimistic lock failure
                vocab = self._vocab_repo.get_by_id(vocab_id)
                if vocab is None:
                    raise ValueError(f"Vocabulary with id {vocab_id} not found")
                logger.info(
                    "SM-2 optimistic lock retry attempt=%d for vocab_id=%s",
                    attempt,
                    vocab_id,
                )

            sm2_values = self._compute_sm2(vocab, quality)

            # Attempt atomic update via RPC
            result = self._vocab_repo.update_sm2_atomic(
                vocab_id=vocab_id,
                easiness_factor=sm2_values["easiness_factor"],
                interval_days=sm2_values["interval_days"],
                repetition_count=sm2_values["repetition_count"],
                next_review_at=sm2_values["next_review_at"],
                last_reviewed_at=sm2_values["last_reviewed_at"],
                expected_repetition_count=sm2_values["expected_repetition_count"],
                quality=quality,
            )

            if result is not None:
                return result

            # result is None: either RPC unavailable or optimistic lock failed.
            # On first attempt with lock failure, retry.  If RPC is entirely
            # unavailable, the second attempt will also return None and we
            # fall through to the non-atomic path below.

        # Fallback: non-atomic path (RPC not deployed)
        logger.warning(
            "Atomic SM-2 update unavailable for vocab_id=%s, using non-atomic "
            "fallback. Deploy migration 003_atomic_counter_operations.sql to fix.",
            vocab_id,
        )
        return self._update_vocab_sm2_legacy(vocab_id, quality)

    def _compute_sm2(self, vocab: Vocabulary, quality: int) -> dict[str, Any]:
        """Compute new SM-2 values from current vocabulary state.

        Pure computation with no side effects. Returns a dictionary of
        all fields needed for the update, including the expected
        repetition_count for optimistic locking.

        Args:
            vocab: Current vocabulary state.
            quality: Recall quality score (0-5).

        Returns:
            Dictionary with keys: easiness_factor, interval_days,
            repetition_count, next_review_at, last_reviewed_at,
            expected_repetition_count.
        """
        easiness_factor = getattr(vocab, "easiness_factor", 2.5) or 2.5
        interval_days = getattr(vocab, "interval_days", 0) or 0
        repetition_count = getattr(vocab, "repetition_count", 0) or 0
        expected_repetition_count = repetition_count

        # Apply SM-2 algorithm
        if quality >= 3:  # Successful recall
            if repetition_count == 0:
                interval_days = 1
            elif repetition_count == 1:
                interval_days = 6
            else:
                interval_days = round(interval_days * easiness_factor)

            repetition_count += 1
        else:  # Failed recall - reset
            repetition_count = 0
            interval_days = 1

        # Update easiness factor (never below 1.3)
        easiness_factor = max(
            1.3,
            easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)),
        )

        # Schedule next review
        now = datetime.now(UTC)
        next_review_at = now + timedelta(days=interval_days)
        last_reviewed_at = now

        return {
            "easiness_factor": easiness_factor,
            "interval_days": interval_days,
            "repetition_count": repetition_count,
            "next_review_at": next_review_at,
            "last_reviewed_at": last_reviewed_at,
            "expected_repetition_count": expected_repetition_count,
        }

    def _update_vocab_sm2_legacy(self, vocab_id: int, quality: int) -> Vocabulary:
        """Non-atomic SM-2 update fallback (read-then-write).

        Used when the ``vocabulary_update_sm2`` RPC is not deployed.
        Susceptible to lost updates under concurrent access.

        Args:
            vocab_id: The vocabulary entry ID.
            quality: Recall quality score (0-5).

        Returns:
            Updated Vocabulary entry.

        Raises:
            ValueError: If vocabulary not found.
        """
        vocab = self._vocab_repo.get_by_id(vocab_id)
        if vocab is None:
            raise ValueError(f"Vocabulary with id {vocab_id} not found")

        sm2 = self._compute_sm2(vocab, quality)

        # In the legacy path, compute absolute counter values
        times_seen = vocab.times_seen + 1
        times_correct = vocab.times_correct + (1 if quality >= 3 else 0)

        return self._update_vocab_sm2(
            vocab_id=vocab_id,
            easiness_factor=sm2["easiness_factor"],
            interval_days=sm2["interval_days"],
            repetition_count=sm2["repetition_count"],
            next_review_at=sm2["next_review_at"],
            last_reviewed_at=sm2["last_reviewed_at"],
            times_seen=times_seen,
            times_correct=times_correct,
        )

    def initialize_word_for_review(self, vocab_id: int) -> Vocabulary:
        """Set initial next_review_at for a newly learned word.

        Schedules the word for review starting tomorrow with default SM-2 values.
        Called when a word is first learned in a lesson or conversation.

        Args:
            vocab_id: The vocabulary entry ID.

        Returns:
            Updated Vocabulary entry with review scheduling initialized.

        Raises:
            ValueError: If vocabulary not found.
        """
        # Fetch current vocabulary by ID (B3: eliminates full-table scan)
        vocab = self._vocab_repo.get_by_id(vocab_id)

        if vocab is None:
            raise ValueError(f"Vocabulary with id {vocab_id} not found")

        # Schedule for tomorrow with default SM-2 values
        now = datetime.now(UTC)
        next_review_at = now + timedelta(days=1)

        return self._update_vocab_sm2(
            vocab_id=vocab_id,
            easiness_factor=2.5,
            interval_days=1,
            repetition_count=0,
            next_review_at=next_review_at,
            last_reviewed_at=None,
            times_seen=vocab.times_seen,
            times_correct=vocab.times_correct,
        )

    def _update_vocab_sm2(
        self,
        vocab_id: int,
        easiness_factor: float,
        interval_days: int,
        repetition_count: int,
        next_review_at: datetime,
        last_reviewed_at: datetime | None,
        times_seen: int,
        times_correct: int,
    ) -> Vocabulary:
        """Persist SM-2 updates via the repository layer (B6).

        Args:
            vocab_id: The vocabulary entry ID.
            easiness_factor: Updated easiness factor (1.3-2.5+).
            interval_days: Current review interval in days.
            repetition_count: Consecutive successful reviews.
            next_review_at: When the word is next due for review.
            last_reviewed_at: When the word was last reviewed.
            times_seen: Total times the word has been seen.
            times_correct: Total times the word was correctly recalled.

        Returns:
            Updated Vocabulary entry.
        """
        updates = {
            "easiness_factor": easiness_factor,
            "interval_days": interval_days,
            "repetition_count": repetition_count,
            "next_review_at": next_review_at,
            "times_seen": times_seen,
            "times_correct": times_correct,
        }

        if last_reviewed_at is not None:
            updates["last_reviewed_at"] = last_reviewed_at

        result = self._vocab_repo.update_review_schedule(vocab_id, updates)

        if result is None:
            raise ValueError(f"Failed to update vocabulary {vocab_id}")

        return result

    def _calculate_next_review_in(
        self,
        in_rotation: list[Vocabulary],
        now: datetime,
    ) -> str | None:
        """Calculate human-readable time until next review.

        Args:
            in_rotation: Words with next_review_at set.
            now: Current datetime for comparison.

        Returns:
            Human-readable string like "2 hours", "tomorrow", or None if no upcoming.
        """
        # Find the next upcoming review (not yet due)
        upcoming = [
            v for v in in_rotation if v.next_review_at is not None and v.next_review_at > now
        ]

        if not upcoming:
            return None

        # Get the soonest upcoming review
        next_review = min(upcoming, key=lambda v: v.next_review_at or now)
        next_review_at = next_review.next_review_at
        if next_review_at is None:
            return None
        delta = next_review_at - now

        return self._format_timedelta(delta)

    def _format_timedelta(self, delta: timedelta) -> str:
        """Format a timedelta as a human-readable string.

        Args:
            delta: Time difference to format.

        Returns:
            Human-readable string like "2 hours", "tomorrow", "3 days".
        """
        total_seconds = int(delta.total_seconds())

        if total_seconds < 0:
            return "now"

        minutes = total_seconds // 60
        hours = minutes // 60
        days = hours // 24

        # Determine the appropriate time unit and value
        if days >= 14:
            result = f"{days // 7} weeks"
        elif days >= 7:
            result = "1 week"
        elif days >= 2:
            result = f"{days} days"
        elif days == 1:
            result = "tomorrow"
        elif hours >= 2:
            result = f"{hours} hours"
        elif hours == 1:
            result = "1 hour"
        elif minutes >= 2:
            result = f"{minutes} minutes"
        else:
            result = "1 minute"

        return result
