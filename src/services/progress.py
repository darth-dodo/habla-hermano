"""Progress tracking service for dashboard aggregation.

Aggregates data from vocabulary, session, and lesson repositories
into dashboard-ready statistics and chart data structures.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from src.db.repository import (
    LearningSessionRepository,
    LessonProgressRepository,
    VocabularyRepository,
)

if TYPE_CHECKING:
    from supabase import Client as SupabaseClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DashboardStats:
    """Aggregated statistics for the user dashboard."""

    total_words: int
    total_sessions: int
    lessons_completed: int
    current_streak: int  # Consecutive days with activity
    accuracy_rate: float  # 0.0-100.0
    words_learned_today: int
    messages_today: int


@dataclass(frozen=True)
class VocabGrowthPoint:
    """A single point on the vocabulary growth chart."""

    date: str  # ISO date string YYYY-MM-DD
    cumulative_words: int


@dataclass(frozen=True)
class AccuracyPoint:
    """A single point on the accuracy trend chart."""

    date: str  # ISO date string YYYY-MM-DD
    accuracy: float  # 0.0-100.0


@dataclass(frozen=True)
class ChartData:
    """Chart data for vocabulary growth and accuracy trends."""

    vocab_growth: list[VocabGrowthPoint]
    accuracy_trend: list[AccuracyPoint]

    def to_dict(self) -> dict:
        """Serialize chart data to a plain dictionary for JSON responses.

        Returns:
            Dictionary with vocab_growth and accuracy_trend lists.
        """
        return {
            "vocab_growth": [asdict(p) for p in self.vocab_growth],
            "accuracy_trend": [asdict(p) for p in self.accuracy_trend],
        }


class ProgressService:
    """Aggregates data from repositories into dashboard-ready structures.

    This service is read-heavy and designed for dashboard rendering.
    It pulls data from vocabulary, session, and lesson repositories,
    then computes derived metrics like streaks, accuracy, and trends.
    """

    def __init__(self, user_id: str, client: SupabaseClient | None = None) -> None:
        """Initialize progress service for a user.

        Args:
            user_id: Supabase auth user UUID or guest session UUID.
            client: Optional Supabase client to pass through to repositories.
                    When ``None`` each repository defaults to the anon client.
                    Pass the admin client for guest (session-based) access.
        """
        self._user_id = user_id
        self._vocab_repo = VocabularyRepository(user_id, client=client)
        self._session_repo = LearningSessionRepository(user_id, client=client)
        self._lesson_repo = LessonProgressRepository(user_id, client=client)

    def get_dashboard_stats(self, language: str = "es") -> DashboardStats:
        """Get aggregated dashboard statistics.

        Computes total words, sessions, lessons completed, current streak,
        accuracy rate, and today's activity metrics.

        Args:
            language: Target language code to filter vocabulary by.

        Returns:
            DashboardStats with all computed metrics.
        """
        vocab = self._vocab_repo.get_all(language=language)
        sessions = self._session_repo.get_all()
        completed_lessons = self._lesson_repo.get_completed()

        total_seen = sum(v.times_seen for v in vocab)
        total_correct = sum(v.times_correct for v in vocab)
        accuracy_rate = (total_correct / total_seen * 100.0) if total_seen > 0 else 0.0

        # Words learned today
        today = date.today()
        words_learned_today = sum(1 for v in vocab if v.first_seen_at.date() == today)

        # Messages today
        messages_today = sum(s.messages_count for s in sessions if s.started_at.date() == today)

        return DashboardStats(
            total_words=len(vocab),
            total_sessions=len(sessions),
            lessons_completed=len(completed_lessons),
            current_streak=self._calculate_streak(sessions),
            accuracy_rate=round(accuracy_rate, 1),
            words_learned_today=words_learned_today,
            messages_today=messages_today,
        )

    def get_chart_data(self, language: str = "es", days: int = 30) -> ChartData:
        """Get chart data for the last N days.

        Produces two series: cumulative vocabulary growth and accuracy trend
        over the specified date range.

        Args:
            language: Target language code to filter vocabulary by.
            days: Number of days to include in the chart.

        Returns:
            ChartData with vocab_growth and accuracy_trend point lists.
        """
        vocab = self._vocab_repo.get_all(language=language)
        today = date.today()
        start_date = today - timedelta(days=days - 1)

        vocab_growth: list[VocabGrowthPoint] = []
        accuracy_trend: list[AccuracyPoint] = []

        for day_offset in range(days):
            current_date = start_date + timedelta(days=day_offset)
            date_str = current_date.isoformat()

            # Cumulative words up to this date
            cumulative = sum(1 for v in vocab if v.first_seen_at.date() <= current_date)
            vocab_growth.append(VocabGrowthPoint(date=date_str, cumulative_words=cumulative))

            # Accuracy from vocab seen up to this date
            seen_up_to = [v for v in vocab if v.first_seen_at.date() <= current_date]
            total_seen = sum(v.times_seen for v in seen_up_to)
            total_correct = sum(v.times_correct for v in seen_up_to)
            accuracy = (total_correct / total_seen * 100.0) if total_seen > 0 else 0.0
            accuracy_trend.append(AccuracyPoint(date=date_str, accuracy=round(accuracy, 1)))

        return ChartData(vocab_growth=vocab_growth, accuracy_trend=accuracy_trend)

    def record_chat_activity(self, language: str, level: str, new_vocab: list[dict]) -> None:
        """Record vocabulary and session data after a chat interaction.

        Fire-and-forget: logs errors but does not raise, so callers
        are never blocked by persistence failures.

        Args:
            language: Target language code (es, de).
            level: CEFR level (A0, A1, A2, B1).
            new_vocab: List of dicts with keys: word, translation,
                       and optionally part_of_speech.
        """
        try:
            for word_entry in new_vocab:
                self._vocab_repo.upsert(
                    word=word_entry["word"],
                    translation=word_entry["translation"],
                    language=language,
                    part_of_speech=word_entry.get("part_of_speech"),
                )

            session = self._session_repo.get_active()
            if session is None:
                self._session_repo.create(language=language, level=level)
        except Exception:
            logger.exception("Failed to record chat activity for user %s", self._user_id)

    def _calculate_streak(self, sessions: list) -> int:
        """Calculate consecutive days with activity from today backwards.

        A streak counts the number of consecutive calendar days (ending today)
        that have at least one learning session. If there is no session today,
        the streak is 0.

        Args:
            sessions: List of LearningSession objects.

        Returns:
            Number of consecutive active days ending today.
        """
        if not sessions:
            return 0

        # Extract unique dates from sessions
        session_dates = {s.started_at.date() for s in sessions}

        today = date.today()
        if today not in session_dates:
            return 0

        streak = 0
        current_date = today
        while current_date in session_dates:
            streak += 1
            current_date -= timedelta(days=1)

        return streak
