"""Review service for spaced repetition using SM-2 algorithm.

Provides scheduling and management for vocabulary review sessions,
including due word queries, SM-2 interval calculations, and
topical word matching for chat weaving.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

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

        Computes the number of words due for review, time until next review,
        and total words in the review rotation.

        Args:
            language: Target language code (es, de).

        Returns:
            ReviewStats with due count, next review time, and total in rotation.
        """
        vocab = self._vocab_repo.get_all(language=language)
        now = datetime.now(UTC)

        # Words with next_review_at set are "in rotation"
        in_rotation = [v for v in vocab if v.next_review_at is not None]
        total_in_rotation = len(in_rotation)

        # Words that are due (next_review_at <= now)
        due_words = [
            v for v in in_rotation if v.next_review_at is not None and v.next_review_at <= now
        ]
        due_count = len(due_words)

        # Calculate next review time for words not yet due
        next_review_in = self._calculate_next_review_in(in_rotation, now)

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

        Args:
            language: Target language code (es, de).
            limit: Maximum number of words to return. None returns all due words.

        Returns:
            List of Vocabulary entries due for review.
        """
        vocab = self._vocab_repo.get_all(language=language)
        now = datetime.now(UTC)

        # Filter to words in rotation that are due
        due_words = [v for v in vocab if v.next_review_at is not None and v.next_review_at <= now]

        # Sort by most overdue first (earliest next_review_at)
        due_words.sort(key=lambda v: v.next_review_at or now)

        if limit is not None:
            return due_words[:limit]
        return due_words

    def get_topical_review_words(
        self,
        language: str,
        topic_keywords: list[str],
        limit: int = 5,
    ) -> list[Vocabulary]:
        """Get due words matching conversation topic for chat weaving.

        Filters due words to those whose word or translation contains
        any of the provided topic keywords (case-insensitive).

        Args:
            language: Target language code (es, de).
            topic_keywords: Keywords from conversation to match against.
            limit: Maximum number of words to return.

        Returns:
            List of Vocabulary entries matching topic and due for review.
        """
        due_words = self.get_due_words(language=language)

        if not topic_keywords:
            return due_words[:limit]

        # Normalize keywords for case-insensitive matching
        keywords_lower = [kw.lower() for kw in topic_keywords]

        # Match words where the word or translation contains any keyword
        matching_words: list[Vocabulary] = []
        for vocab in due_words:
            word_lower = vocab.word.lower()
            translation_lower = vocab.translation.lower()

            for keyword in keywords_lower:
                if keyword in word_lower or keyword in translation_lower:
                    matching_words.append(vocab)
                    break  # Only add once per vocab

            if len(matching_words) >= limit:
                break

        return matching_words

    def update_sm2(self, vocab_id: int, quality: int) -> Vocabulary:
        """Apply SM-2 algorithm to a vocabulary item and persist.

        Updates the vocabulary's easiness factor, interval, repetition count,
        and schedules the next review based on the quality of recall.

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

        # Get current SM-2 values (with defaults for new entries)
        easiness_factor = getattr(vocab, "easiness_factor", 2.5) or 2.5
        interval_days = getattr(vocab, "interval_days", 0) or 0
        repetition_count = getattr(vocab, "repetition_count", 0) or 0
        times_seen = vocab.times_seen
        times_correct = vocab.times_correct

        # Apply SM-2 algorithm
        if quality >= 3:  # Successful recall
            if repetition_count == 0:
                interval_days = 1
            elif repetition_count == 1:
                interval_days = 6
            else:
                interval_days = round(interval_days * easiness_factor)

            repetition_count += 1
            times_correct += 1
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

        # Update times_seen
        times_seen += 1

        # Persist to database
        return self._update_vocab_sm2(
            vocab_id=vocab_id,
            easiness_factor=easiness_factor,
            interval_days=interval_days,
            repetition_count=repetition_count,
            next_review_at=next_review_at,
            last_reviewed_at=last_reviewed_at,
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
