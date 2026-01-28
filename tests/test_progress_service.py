"""Tests for progress tracking service module.

Comprehensive tests for dashboard aggregation, chart data generation,
streak calculation, and chat activity recording. All repository
dependencies are mocked -- no Supabase connection required.
"""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

import pytest

from src.db.models import LearningSession, LessonProgress, Vocabulary
from src.services.progress import (
    AccuracyPoint,
    ChartData,
    DashboardStats,
    ProgressService,
    VocabGrowthPoint,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_vocab_repo():
    """Create a mock VocabularyRepository."""
    with patch("src.services.progress.VocabularyRepository") as mock_class:
        yield mock_class.return_value


@pytest.fixture
def mock_session_repo():
    """Create a mock LearningSessionRepository."""
    with patch("src.services.progress.LearningSessionRepository") as mock_class:
        yield mock_class.return_value


@pytest.fixture
def mock_lesson_repo():
    """Create a mock LessonProgressRepository."""
    with patch("src.services.progress.LessonProgressRepository") as mock_class:
        yield mock_class.return_value


@pytest.fixture
def service(mock_vocab_repo, mock_session_repo, mock_lesson_repo):
    """Create a ProgressService with all repositories mocked."""
    return ProgressService("test-user-123")


def _make_vocab(
    word: str,
    translation: str = "trans",
    language: str = "es",
    times_seen: int = 1,
    times_correct: int = 0,
    first_seen_at: datetime | None = None,
) -> Vocabulary:
    """Helper to build a Vocabulary instance for tests."""
    return Vocabulary(
        id=1,
        user_id="test-user-123",
        word=word,
        translation=translation,
        language=language,
        times_seen=times_seen,
        times_correct=times_correct,
        first_seen_at=first_seen_at or datetime.now(UTC),
    )


def _make_session(
    started_at: datetime | None = None,
    messages_count: int = 0,
    words_learned: int = 0,
    language: str = "es",
    level: str = "A1",
    ended_at: datetime | None = None,
) -> LearningSession:
    """Helper to build a LearningSession instance for tests."""
    return LearningSession(
        id=1,
        user_id="test-user-123",
        started_at=started_at or datetime.now(UTC),
        ended_at=ended_at,
        language=language,
        level=level,
        messages_count=messages_count,
        words_learned=words_learned,
    )


def _make_lesson(lesson_id: str = "lesson-1", score: int | None = 80) -> LessonProgress:
    """Helper to build a LessonProgress instance for tests."""
    return LessonProgress(
        user_id="test-user-123",
        lesson_id=lesson_id,
        completed_at=datetime.now(UTC),
        score=score,
    )


# =============================================================================
# DashboardStats Dataclass Tests
# =============================================================================


class TestDashboardStatsDataclass:
    """Tests for the DashboardStats frozen dataclass."""

    def test_create_dashboard_stats(self) -> None:
        """Test creating DashboardStats with all fields."""
        stats = DashboardStats(
            total_words=50,
            total_sessions=10,
            lessons_completed=3,
            current_streak=5,
            accuracy_rate=72.5,
            words_learned_today=4,
            messages_today=12,
        )

        assert stats.total_words == 50
        assert stats.total_sessions == 10
        assert stats.lessons_completed == 3
        assert stats.current_streak == 5
        assert stats.accuracy_rate == 72.5
        assert stats.words_learned_today == 4
        assert stats.messages_today == 12

    def test_dashboard_stats_is_frozen(self) -> None:
        """Test DashboardStats is immutable."""
        stats = DashboardStats(
            total_words=0,
            total_sessions=0,
            lessons_completed=0,
            current_streak=0,
            accuracy_rate=0.0,
            words_learned_today=0,
            messages_today=0,
        )

        with pytest.raises(AttributeError):
            stats.total_words = 99  # type: ignore[misc]


# =============================================================================
# ChartData Dataclass and Serialization Tests
# =============================================================================


class TestChartDataToDict:
    """Tests for ChartData serialization."""

    def test_to_dict_empty(self) -> None:
        """Test to_dict with empty lists."""
        chart = ChartData(vocab_growth=[], accuracy_trend=[])
        result = chart.to_dict()

        assert result == {"vocab_growth": [], "accuracy_trend": []}

    def test_to_dict_with_points(self) -> None:
        """Test to_dict serializes points correctly."""
        chart = ChartData(
            vocab_growth=[VocabGrowthPoint(date="2026-01-01", cumulative_words=5)],
            accuracy_trend=[AccuracyPoint(date="2026-01-01", accuracy=80.0)],
        )
        result = chart.to_dict()

        assert len(result["vocab_growth"]) == 1
        assert result["vocab_growth"][0]["date"] == "2026-01-01"
        assert result["vocab_growth"][0]["cumulative_words"] == 5
        assert len(result["accuracy_trend"]) == 1
        assert result["accuracy_trend"][0]["date"] == "2026-01-01"
        assert result["accuracy_trend"][0]["accuracy"] == 80.0

    def test_to_dict_multiple_points(self) -> None:
        """Test to_dict with multiple data points preserves order."""
        chart = ChartData(
            vocab_growth=[
                VocabGrowthPoint(date="2026-01-01", cumulative_words=2),
                VocabGrowthPoint(date="2026-01-02", cumulative_words=5),
                VocabGrowthPoint(date="2026-01-03", cumulative_words=9),
            ],
            accuracy_trend=[
                AccuracyPoint(date="2026-01-01", accuracy=50.0),
                AccuracyPoint(date="2026-01-02", accuracy=65.0),
                AccuracyPoint(date="2026-01-03", accuracy=72.3),
            ],
        )
        result = chart.to_dict()

        assert len(result["vocab_growth"]) == 3
        assert result["vocab_growth"][2]["cumulative_words"] == 9
        assert len(result["accuracy_trend"]) == 3
        assert result["accuracy_trend"][2]["accuracy"] == 72.3

    def test_chart_data_is_frozen(self) -> None:
        """Test ChartData is immutable."""
        chart = ChartData(vocab_growth=[], accuracy_trend=[])

        with pytest.raises(AttributeError):
            chart.vocab_growth = []  # type: ignore[misc]

    def test_vocab_growth_point_is_frozen(self) -> None:
        """Test VocabGrowthPoint is immutable."""
        point = VocabGrowthPoint(date="2026-01-01", cumulative_words=10)

        with pytest.raises(AttributeError):
            point.cumulative_words = 20  # type: ignore[misc]

    def test_accuracy_point_is_frozen(self) -> None:
        """Test AccuracyPoint is immutable."""
        point = AccuracyPoint(date="2026-01-01", accuracy=50.0)

        with pytest.raises(AttributeError):
            point.accuracy = 99.0  # type: ignore[misc]


# =============================================================================
# get_dashboard_stats Tests
# =============================================================================


class TestDashboardStats:
    """Tests for ProgressService.get_dashboard_stats."""

    def test_zero_state(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test dashboard stats when user has no activity."""
        mock_vocab_repo.get_all.return_value = []
        mock_session_repo.get_all.return_value = []
        mock_lesson_repo.get_completed.return_value = []

        stats = service.get_dashboard_stats()

        assert stats.total_words == 0
        assert stats.total_sessions == 0
        assert stats.lessons_completed == 0
        assert stats.current_streak == 0
        assert stats.accuracy_rate == 0.0
        assert stats.words_learned_today == 0
        assert stats.messages_today == 0

    def test_populated_data(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test dashboard stats with existing user data."""
        today_dt = datetime.now(UTC)

        mock_vocab_repo.get_all.return_value = [
            _make_vocab("hola", times_seen=10, times_correct=8, first_seen_at=today_dt),
            _make_vocab("gracias", times_seen=5, times_correct=3, first_seen_at=today_dt),
        ]
        mock_session_repo.get_all.return_value = [
            _make_session(started_at=today_dt, messages_count=15),
        ]
        mock_lesson_repo.get_completed.return_value = [
            _make_lesson("lesson-1"),
            _make_lesson("lesson-2"),
        ]

        stats = service.get_dashboard_stats()

        assert stats.total_words == 2
        assert stats.total_sessions == 1
        assert stats.lessons_completed == 2
        assert stats.words_learned_today == 2
        assert stats.messages_today == 15

    def test_accuracy_calculation(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test accuracy rate is correctly computed from times_correct/times_seen."""
        mock_vocab_repo.get_all.return_value = [
            _make_vocab("hola", times_seen=10, times_correct=7),
            _make_vocab("gracias", times_seen=10, times_correct=9),
        ]
        mock_session_repo.get_all.return_value = []
        mock_lesson_repo.get_completed.return_value = []

        stats = service.get_dashboard_stats()

        # (7 + 9) / (10 + 10) * 100 = 80.0
        assert stats.accuracy_rate == 80.0

    def test_accuracy_zero_when_no_vocab(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test accuracy is 0.0 when there is no vocabulary data."""
        mock_vocab_repo.get_all.return_value = []
        mock_session_repo.get_all.return_value = []
        mock_lesson_repo.get_completed.return_value = []

        stats = service.get_dashboard_stats()

        assert stats.accuracy_rate == 0.0

    def test_accuracy_rounding(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test accuracy rate is rounded to one decimal place."""
        mock_vocab_repo.get_all.return_value = [
            _make_vocab("hola", times_seen=3, times_correct=1),
        ]
        mock_session_repo.get_all.return_value = []
        mock_lesson_repo.get_completed.return_value = []

        stats = service.get_dashboard_stats()

        # 1/3 * 100 = 33.333... -> 33.3
        assert stats.accuracy_rate == 33.3

    def test_language_filtering(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test get_dashboard_stats passes language filter to vocab repo."""
        mock_vocab_repo.get_all.return_value = []
        mock_session_repo.get_all.return_value = []
        mock_lesson_repo.get_completed.return_value = []

        service.get_dashboard_stats(language="de")

        mock_vocab_repo.get_all.assert_called_once_with(language="de")

    def test_words_learned_today_filters_by_date(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test only words with first_seen_at today are counted."""
        today_dt = datetime.now(UTC)
        yesterday_dt = today_dt - timedelta(days=1)

        mock_vocab_repo.get_all.return_value = [
            _make_vocab("hola", first_seen_at=today_dt),
            _make_vocab("ayer", first_seen_at=yesterday_dt),
            _make_vocab("nuevo", first_seen_at=today_dt),
        ]
        mock_session_repo.get_all.return_value = []
        mock_lesson_repo.get_completed.return_value = []

        stats = service.get_dashboard_stats()

        assert stats.words_learned_today == 2

    def test_messages_today_sums_todays_sessions(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test messages_today sums messages_count for sessions started today."""
        today_dt = datetime.now(UTC)
        yesterday_dt = today_dt - timedelta(days=1)

        mock_vocab_repo.get_all.return_value = []
        mock_session_repo.get_all.return_value = [
            _make_session(started_at=today_dt, messages_count=10),
            _make_session(started_at=today_dt, messages_count=5),
            _make_session(started_at=yesterday_dt, messages_count=20),
        ]
        mock_lesson_repo.get_completed.return_value = []

        stats = service.get_dashboard_stats()

        assert stats.messages_today == 15

    def test_default_language_is_es(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test default language parameter is 'es'."""
        mock_vocab_repo.get_all.return_value = []
        mock_session_repo.get_all.return_value = []
        mock_lesson_repo.get_completed.return_value = []

        service.get_dashboard_stats()

        mock_vocab_repo.get_all.assert_called_once_with(language="es")


# =============================================================================
# get_chart_data Tests
# =============================================================================


class TestChartData:
    """Tests for ProgressService.get_chart_data."""

    def test_empty_data_returns_zero_points(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test chart data with no vocabulary produces zero-value points."""
        mock_vocab_repo.get_all.return_value = []

        chart = service.get_chart_data(days=5)

        assert len(chart.vocab_growth) == 5
        assert len(chart.accuracy_trend) == 5
        assert all(p.cumulative_words == 0 for p in chart.vocab_growth)
        assert all(p.accuracy == 0.0 for p in chart.accuracy_trend)

    def test_correct_number_of_days(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test chart data returns exactly the requested number of days."""
        mock_vocab_repo.get_all.return_value = []

        chart_7 = service.get_chart_data(days=7)
        chart_30 = service.get_chart_data(days=30)

        assert len(chart_7.vocab_growth) == 7
        assert len(chart_30.vocab_growth) == 30

    def test_cumulative_growth(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test vocab growth is cumulative over time."""
        today = date.today()
        day_2_ago = datetime.combine(today - timedelta(days=2), datetime.min.time(), tzinfo=UTC)
        day_1_ago = datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        today_dt = datetime.combine(today, datetime.min.time(), tzinfo=UTC)

        mock_vocab_repo.get_all.return_value = [
            _make_vocab("hola", first_seen_at=day_2_ago),
            _make_vocab("gracias", first_seen_at=day_1_ago),
            _make_vocab("bueno", first_seen_at=today_dt),
        ]

        chart = service.get_chart_data(days=3)

        # Day 1 (2 days ago): 1 word
        assert chart.vocab_growth[0].cumulative_words == 1
        # Day 2 (1 day ago): 2 words
        assert chart.vocab_growth[1].cumulative_words == 2
        # Day 3 (today): 3 words
        assert chart.vocab_growth[2].cumulative_words == 3

    def test_date_format_is_iso(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test dates are formatted as ISO YYYY-MM-DD strings."""
        mock_vocab_repo.get_all.return_value = []

        chart = service.get_chart_data(days=1)

        today_str = date.today().isoformat()
        assert chart.vocab_growth[0].date == today_str
        assert chart.accuracy_trend[0].date == today_str

    def test_date_range_covers_correct_span(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test date range starts (days-1) days before today and ends today."""
        mock_vocab_repo.get_all.return_value = []

        chart = service.get_chart_data(days=5)

        today = date.today()
        start_date = today - timedelta(days=4)
        assert chart.vocab_growth[0].date == start_date.isoformat()
        assert chart.vocab_growth[-1].date == today.isoformat()

    def test_accuracy_trend_with_data(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test accuracy trend reflects cumulative vocab accuracy."""
        today = date.today()
        today_dt = datetime.combine(today, datetime.min.time(), tzinfo=UTC)

        mock_vocab_repo.get_all.return_value = [
            _make_vocab("hola", times_seen=10, times_correct=8, first_seen_at=today_dt),
        ]

        chart = service.get_chart_data(days=1)

        assert chart.accuracy_trend[0].accuracy == 80.0

    def test_language_passed_to_repo(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test language parameter is forwarded to vocabulary repository."""
        mock_vocab_repo.get_all.return_value = []

        service.get_chart_data(language="de", days=5)

        mock_vocab_repo.get_all.assert_called_once_with(language="de")

    def test_vocab_before_range_still_counted(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test vocab learned before the chart range counts as cumulative."""
        today = date.today()
        old_date = datetime.combine(today - timedelta(days=60), datetime.min.time(), tzinfo=UTC)

        mock_vocab_repo.get_all.return_value = [
            _make_vocab("antiguo", first_seen_at=old_date),
        ]

        chart = service.get_chart_data(days=3)

        # The word was learned 60 days ago, so all 3 days should show 1
        assert all(p.cumulative_words == 1 for p in chart.vocab_growth)


# =============================================================================
# _calculate_streak Tests
# =============================================================================


class TestStreak:
    """Tests for ProgressService._calculate_streak."""

    def test_zero_sessions(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test streak is 0 when there are no sessions."""
        assert service._calculate_streak([]) == 0

    def test_no_session_today_returns_zero(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test streak is 0 when there is no session today."""
        yesterday = datetime.now(UTC) - timedelta(days=1)
        sessions = [_make_session(started_at=yesterday)]

        assert service._calculate_streak(sessions) == 0

    def test_one_day_streak(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test streak of 1 when only today has a session."""
        today_dt = datetime.now(UTC)
        sessions = [_make_session(started_at=today_dt)]

        assert service._calculate_streak(sessions) == 1

    def test_multi_day_streak(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test multi-day consecutive streak."""
        today = datetime.now(UTC)
        sessions = [
            _make_session(started_at=today),
            _make_session(started_at=today - timedelta(days=1)),
            _make_session(started_at=today - timedelta(days=2)),
        ]

        assert service._calculate_streak(sessions) == 3

    def test_gap_breaks_streak(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test that a gap in days breaks the streak."""
        today = datetime.now(UTC)
        sessions = [
            _make_session(started_at=today),
            _make_session(started_at=today - timedelta(days=1)),
            # Gap: day -2 missing
            _make_session(started_at=today - timedelta(days=3)),
        ]

        assert service._calculate_streak(sessions) == 2

    def test_multiple_sessions_same_day(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test multiple sessions on the same day count as one streak day."""
        today = datetime.now(UTC)
        sessions = [
            _make_session(started_at=today),
            _make_session(started_at=today - timedelta(hours=2)),
            _make_session(started_at=today - timedelta(days=1)),
        ]

        assert service._calculate_streak(sessions) == 2

    def test_long_streak(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test a long consecutive streak."""
        today = datetime.now(UTC)
        sessions = [_make_session(started_at=today - timedelta(days=i)) for i in range(10)]

        assert service._calculate_streak(sessions) == 10

    def test_streak_via_dashboard_stats(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test that streak is correctly exposed through get_dashboard_stats."""
        today = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = []
        mock_session_repo.get_all.return_value = [
            _make_session(started_at=today),
            _make_session(started_at=today - timedelta(days=1)),
            _make_session(started_at=today - timedelta(days=2)),
        ]
        mock_lesson_repo.get_completed.return_value = []

        stats = service.get_dashboard_stats()

        assert stats.current_streak == 3


# =============================================================================
# record_chat_activity Tests
# =============================================================================


class TestRecordChatActivity:
    """Tests for ProgressService.record_chat_activity."""

    def test_upserts_each_vocab_word(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test each word in new_vocab triggers a repo upsert call."""
        mock_session_repo.get_active.return_value = _make_session()

        new_vocab = [
            {"word": "hola", "translation": "hello"},
            {"word": "gracias", "translation": "thanks", "part_of_speech": "noun"},
        ]

        service.record_chat_activity(language="es", level="A1", new_vocab=new_vocab)

        assert mock_vocab_repo.upsert.call_count == 2
        mock_vocab_repo.upsert.assert_any_call(
            word="hola", translation="hello", language="es", part_of_speech=None
        )
        mock_vocab_repo.upsert.assert_any_call(
            word="gracias", translation="thanks", language="es", part_of_speech="noun"
        )

    def test_creates_session_when_none_active(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test a new session is created when no active session exists."""
        mock_session_repo.get_active.return_value = None

        service.record_chat_activity(language="es", level="A1", new_vocab=[])

        mock_session_repo.create.assert_called_once_with(language="es", level="A1")

    def test_does_not_create_session_when_active(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test no new session is created when one is already active."""
        mock_session_repo.get_active.return_value = _make_session()

        service.record_chat_activity(language="es", level="A1", new_vocab=[])

        mock_session_repo.create.assert_not_called()

    def test_empty_vocab_list(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test calling with an empty vocab list does not call upsert."""
        mock_session_repo.get_active.return_value = _make_session()

        service.record_chat_activity(language="de", level="A0", new_vocab=[])

        mock_vocab_repo.upsert.assert_not_called()

    def test_error_is_logged_not_raised(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test exceptions are caught, logged, and not re-raised."""
        mock_vocab_repo.upsert.side_effect = RuntimeError("Supabase down")

        # Should not raise
        service.record_chat_activity(
            language="es",
            level="A1",
            new_vocab=[{"word": "fail", "translation": "fallo"}],
        )

    def test_error_logged_with_user_id(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test logged error includes the user_id for traceability."""
        mock_vocab_repo.upsert.side_effect = RuntimeError("Connection lost")

        with patch("src.services.progress.logger") as mock_logger:
            service.record_chat_activity(
                language="es",
                level="A1",
                new_vocab=[{"word": "fail", "translation": "fallo"}],
            )

            mock_logger.exception.assert_called_once()
            call_args = mock_logger.exception.call_args
            assert "test-user-123" in str(call_args)

    def test_session_check_after_vocab_upsert(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test session lookup happens even with vocab to upsert."""
        mock_session_repo.get_active.return_value = _make_session()

        service.record_chat_activity(
            language="es",
            level="A1",
            new_vocab=[{"word": "hola", "translation": "hello"}],
        )

        mock_session_repo.get_active.assert_called_once()

    def test_part_of_speech_optional(
        self, service, mock_vocab_repo, mock_session_repo, mock_lesson_repo
    ) -> None:
        """Test part_of_speech defaults to None when not provided."""
        mock_session_repo.get_active.return_value = _make_session()

        service.record_chat_activity(
            language="es",
            level="A1",
            new_vocab=[{"word": "hola", "translation": "hello"}],
        )

        mock_vocab_repo.upsert.assert_called_once_with(
            word="hola", translation="hello", language="es", part_of_speech=None
        )


# =============================================================================
# Service Initialization Tests
# =============================================================================


class TestServiceInit:
    """Tests for ProgressService initialization."""

    def test_init_creates_all_repositories(self) -> None:
        """Test service creates all three repositories with user_id."""
        with (
            patch("src.services.progress.VocabularyRepository") as mock_vocab,
            patch("src.services.progress.LearningSessionRepository") as mock_session,
            patch("src.services.progress.LessonProgressRepository") as mock_lesson,
        ):
            ProgressService("user-abc-789")

            mock_vocab.assert_called_once_with("user-abc-789", client=None)
            mock_session.assert_called_once_with("user-abc-789", client=None)
            mock_lesson.assert_called_once_with("user-abc-789", client=None)

    def test_stores_user_id(self) -> None:
        """Test service stores the user_id."""
        with (
            patch("src.services.progress.VocabularyRepository"),
            patch("src.services.progress.LearningSessionRepository"),
            patch("src.services.progress.LessonProgressRepository"),
        ):
            svc = ProgressService("user-xyz-456")

            assert svc._user_id == "user-xyz-456"
