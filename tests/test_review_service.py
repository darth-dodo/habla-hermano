"""Tests for spaced repetition review service module.

Comprehensive tests for the SM-2 algorithm, review scheduling, due word
queries, topical matching, and review statistics. All repository and
Supabase dependencies are mocked -- no database connection required.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.db.models import Vocabulary
from src.services.review import ReviewService, ReviewStats

# =============================================================================
# Constants
# =============================================================================

USER_ID = "test-user-123"

# =============================================================================
# Helpers
# =============================================================================


def _make_vocab(
    word: str = "hola",
    translation: str = "hello",
    language: str = "es",
    vocab_id: int = 1,
    times_seen: int = 1,
    times_correct: int = 0,
    easiness_factor: float = 2.5,
    interval_days: int = 0,
    repetition_count: int = 0,
    next_review_at: datetime | None = None,
    last_reviewed_at: datetime | None = None,
    first_seen_at: datetime | None = None,
) -> Vocabulary:
    """Helper to build a Vocabulary instance with SM-2 fields for tests."""
    return Vocabulary(
        id=vocab_id,
        user_id=USER_ID,
        word=word,
        translation=translation,
        language=language,
        times_seen=times_seen,
        times_correct=times_correct,
        easiness_factor=easiness_factor,
        interval_days=interval_days,
        repetition_count=repetition_count,
        next_review_at=next_review_at,
        last_reviewed_at=last_reviewed_at,
        first_seen_at=first_seen_at or datetime.now(UTC),
    )


def _make_mock_vocab_with_none_sm2(
    vocab_id: int = 1,
    times_seen: int = 1,
    times_correct: int = 0,
) -> MagicMock:
    """Create a MagicMock simulating a Vocabulary with None SM-2 fields.

    This exercises the `getattr(vocab, 'field', default) or default`
    fallback logic in update_sm2 for entries returned from Supabase
    where SM-2 columns may be NULL.
    """
    mock = MagicMock()
    mock.id = vocab_id
    mock.easiness_factor = None
    mock.interval_days = None
    mock.repetition_count = None
    mock.times_seen = times_seen
    mock.times_correct = times_correct
    return mock


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_vocab_repo():
    """Create a mock VocabularyRepository."""
    with patch("src.services.review.VocabularyRepository") as mock_class:
        yield mock_class.return_value


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client with chained table operations."""
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_table.update = MagicMock(return_value=mock_table)
    mock_table.eq = MagicMock(return_value=mock_table)
    mock_table.execute = MagicMock(return_value=MagicMock(data=[]))
    mock_client.table = MagicMock(return_value=mock_table)
    return mock_client


@pytest.fixture
def service(mock_vocab_repo, mock_supabase_client):
    """Create a ReviewService with mocked dependencies."""
    with patch("src.services.review.get_supabase", return_value=mock_supabase_client):
        svc = ReviewService(USER_ID, client=mock_supabase_client)
    return svc


# =============================================================================
# ReviewStats Dataclass Tests
# =============================================================================


class TestReviewStatsDataclass:
    """Tests for the ReviewStats frozen dataclass."""

    def test_create_review_stats(self) -> None:
        """Test creating ReviewStats with all fields."""
        stats = ReviewStats(
            due_count=5,
            next_review_in="2 hours",
            total_in_rotation=20,
        )

        assert stats.due_count == 5
        assert stats.next_review_in == "2 hours"
        assert stats.total_in_rotation == 20

    def test_review_stats_none_next_review(self) -> None:
        """Test ReviewStats with None next_review_in."""
        stats = ReviewStats(due_count=0, next_review_in=None, total_in_rotation=0)

        assert stats.next_review_in is None

    def test_review_stats_is_frozen(self) -> None:
        """Test ReviewStats is immutable."""
        stats = ReviewStats(due_count=0, next_review_in=None, total_in_rotation=0)

        with pytest.raises(AttributeError):
            stats.due_count = 99  # type: ignore[misc]


# =============================================================================
# SM-2 Algorithm Tests -- THE CRITICAL PATH
# =============================================================================


class TestSM2Algorithm:
    """Tests for ReviewService.update_sm2 -- the core SM-2 spaced repetition algorithm.

    The SM-2 algorithm is the foundation of the spaced repetition system. These
    tests verify correctness for every quality score (0-5), interval progression,
    easiness factor adjustment, and edge cases.
    """

    # -------------------------------------------------------------------------
    # Quality validation
    # -------------------------------------------------------------------------

    def test_quality_below_zero_raises(self, service, mock_vocab_repo) -> None:
        """Test quality < 0 raises ValueError."""
        with pytest.raises(ValueError, match="Quality must be 0-5"):
            service.update_sm2(vocab_id=1, quality=-1)

    def test_quality_above_five_raises(self, service, mock_vocab_repo) -> None:
        """Test quality > 5 raises ValueError."""
        with pytest.raises(ValueError, match="Quality must be 0-5"):
            service.update_sm2(vocab_id=1, quality=6)

    def test_quality_non_integer_boundary(self, service, mock_vocab_repo) -> None:
        """Test quality = 10 raises ValueError."""
        with pytest.raises(ValueError, match="Quality must be 0-5"):
            service.update_sm2(vocab_id=1, quality=10)

    def test_vocab_not_found_raises(self, service, mock_vocab_repo) -> None:
        """Test ValueError when vocab_id does not exist."""
        mock_vocab_repo.get_all.return_value = []

        with pytest.raises(ValueError, match="Vocabulary with id 999 not found"):
            service.update_sm2(vocab_id=999, quality=5)

    # -------------------------------------------------------------------------
    # Failed recall (quality 0, 1, 2) -- reset behavior
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("quality", [0, 1, 2])
    def test_failed_recall_resets_repetitions_to_zero(
        self, service, mock_vocab_repo, mock_supabase_client, quality
    ) -> None:
        """Test quality 0-2 resets repetition_count to 0."""
        vocab = _make_vocab(repetition_count=5, interval_days=30, easiness_factor=2.5)
        mock_vocab_repo.get_all.return_value = [vocab]

        # Mock the Supabase update to return vocab with updated values
        updated_data = vocab.model_dump()
        updated_data["repetition_count"] = 0
        updated_data["interval_days"] = 1
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=quality)

        # Verify the update was called with repetition_count=0
        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["repetition_count"] == 0

    @pytest.mark.parametrize("quality", [0, 1, 2])
    def test_failed_recall_resets_interval_to_one(
        self, service, mock_vocab_repo, mock_supabase_client, quality
    ) -> None:
        """Test quality 0-2 resets interval_days to 1."""
        vocab = _make_vocab(repetition_count=5, interval_days=30, easiness_factor=2.5)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        updated_data["repetition_count"] = 0
        updated_data["interval_days"] = 1
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=quality)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["interval_days"] == 1

    @pytest.mark.parametrize("quality", [0, 1, 2])
    def test_failed_recall_does_not_increment_times_correct(
        self, service, mock_vocab_repo, mock_supabase_client, quality
    ) -> None:
        """Test quality 0-2 does not increment times_correct."""
        vocab = _make_vocab(times_correct=5, times_seen=10)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=quality)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["times_correct"] == 5  # unchanged

    @pytest.mark.parametrize("quality", [0, 1, 2])
    def test_failed_recall_increments_times_seen(
        self, service, mock_vocab_repo, mock_supabase_client, quality
    ) -> None:
        """Test quality 0-2 still increments times_seen."""
        vocab = _make_vocab(times_seen=10)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=quality)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["times_seen"] == 11

    def test_quality_0_complete_blackout(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test quality 0 (complete blackout): resets and decreases easiness factor."""
        vocab = _make_vocab(
            repetition_count=3,
            interval_days=15,
            easiness_factor=2.5,
            times_correct=3,
        )
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=0)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["repetition_count"] == 0
        assert update_data["interval_days"] == 1
        assert update_data["times_correct"] == 3  # not incremented
        # EF = 2.5 + (0.1 - (5-0) * (0.08 + (5-0) * 0.02)) = 2.5 + (0.1 - 5*0.18) = 2.5 - 0.8 = 1.7
        expected_ef = max(1.3, 2.5 + (0.1 - (5 - 0) * (0.08 + (5 - 0) * 0.02)))
        assert update_data["easiness_factor"] == pytest.approx(expected_ef, abs=0.001)

    def test_quality_1_incorrect_unfamiliar(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test quality 1 (incorrect, answer seemed unfamiliar)."""
        vocab = _make_vocab(repetition_count=2, interval_days=6, easiness_factor=2.5)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=1)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["repetition_count"] == 0
        assert update_data["interval_days"] == 1
        # EF = 2.5 + (0.1 - 4*(0.08+4*0.02)) = 2.5 + (0.1 - 4*0.16) = 2.5 + (0.1 - 0.64) = 2.5 - 0.54 = 1.96
        expected_ef = max(1.3, 2.5 + (0.1 - (5 - 1) * (0.08 + (5 - 1) * 0.02)))
        assert update_data["easiness_factor"] == pytest.approx(expected_ef, abs=0.001)

    def test_quality_2_incorrect_recognized(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test quality 2 (incorrect, recognized correct answer)."""
        vocab = _make_vocab(repetition_count=2, interval_days=6, easiness_factor=2.5)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=2)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["repetition_count"] == 0
        assert update_data["interval_days"] == 1
        # EF = 2.5 + (0.1 - 3*(0.08+3*0.02)) = 2.5 + (0.1 - 3*0.14) = 2.5 + (0.1 - 0.42) = 2.5 - 0.32 = 2.18
        expected_ef = max(1.3, 2.5 + (0.1 - (5 - 2) * (0.08 + (5 - 2) * 0.02)))
        assert update_data["easiness_factor"] == pytest.approx(expected_ef, abs=0.001)

    # -------------------------------------------------------------------------
    # Successful recall (quality 3, 4, 5) -- progression behavior
    # -------------------------------------------------------------------------

    def test_quality_3_first_successful_review_interval_1(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test first successful review (quality 3): interval becomes 1 day."""
        vocab = _make_vocab(repetition_count=0, interval_days=0, easiness_factor=2.5)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=3)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["interval_days"] == 1
        assert update_data["repetition_count"] == 1

    def test_quality_4_first_successful_review_interval_1(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test first successful review (quality 4): interval becomes 1 day."""
        vocab = _make_vocab(repetition_count=0, interval_days=0, easiness_factor=2.5)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=4)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["interval_days"] == 1
        assert update_data["repetition_count"] == 1

    def test_quality_5_first_successful_review_interval_1(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test first successful review (quality 5): interval becomes 1 day."""
        vocab = _make_vocab(repetition_count=0, interval_days=0, easiness_factor=2.5)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=5)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["interval_days"] == 1
        assert update_data["repetition_count"] == 1

    def test_second_successful_review_interval_6(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test second successful review: interval becomes 6 days."""
        vocab = _make_vocab(repetition_count=1, interval_days=1, easiness_factor=2.5)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=5)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["interval_days"] == 6
        assert update_data["repetition_count"] == 2

    def test_third_successful_review_uses_ef_multiplier(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test third+ successful review: interval = prev_interval * easiness_factor."""
        vocab = _make_vocab(
            repetition_count=2,
            interval_days=6,
            easiness_factor=2.5,
        )
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=5)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        # interval = round(6 * 2.5) = 15
        assert update_data["interval_days"] == 15
        assert update_data["repetition_count"] == 3

    def test_fourth_successful_review_compounds_interval(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test interval compounds over repeated successful reviews."""
        # Simulate: rep=3, interval=15, EF=2.6
        vocab = _make_vocab(
            repetition_count=3,
            interval_days=15,
            easiness_factor=2.6,
        )
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=5)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        # interval = round(15 * 2.6) = 39
        assert update_data["interval_days"] == 39
        assert update_data["repetition_count"] == 4

    @pytest.mark.parametrize("quality", [3, 4, 5])
    def test_successful_recall_increments_times_correct(
        self, service, mock_vocab_repo, mock_supabase_client, quality
    ) -> None:
        """Test quality 3-5 increments times_correct."""
        vocab = _make_vocab(times_correct=3, times_seen=10)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=quality)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["times_correct"] == 4

    @pytest.mark.parametrize("quality", [3, 4, 5])
    def test_successful_recall_increments_times_seen(
        self, service, mock_vocab_repo, mock_supabase_client, quality
    ) -> None:
        """Test quality 3-5 increments times_seen."""
        vocab = _make_vocab(times_seen=10)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=quality)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["times_seen"] == 11

    # -------------------------------------------------------------------------
    # Easiness factor behavior
    # -------------------------------------------------------------------------

    def test_easiness_factor_never_below_1_3(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test easiness factor is clamped to minimum 1.3 after repeated failures."""
        # Start with EF already near the floor
        vocab = _make_vocab(easiness_factor=1.3, repetition_count=0, interval_days=1)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        # Quality 0 should try to decrease EF significantly
        service.update_sm2(vocab_id=1, quality=0)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["easiness_factor"] >= 1.3

    def test_easiness_factor_floor_with_quality_0(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test quality 0 with low EF still stays at 1.3 floor."""
        vocab = _make_vocab(easiness_factor=1.5)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=0)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        # EF = 1.5 + (0.1 - 5*0.18) = 1.5 - 0.8 = 0.7 -> clamped to 1.3
        assert update_data["easiness_factor"] == 1.3

    def test_easiness_factor_increases_with_quality_5(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test quality 5 (perfect) increases the easiness factor."""
        vocab = _make_vocab(easiness_factor=2.5)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=5)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        # EF = 2.5 + (0.1 - 0*(0.08+0*0.02)) = 2.5 + 0.1 = 2.6
        assert update_data["easiness_factor"] == pytest.approx(2.6, abs=0.001)

    def test_easiness_factor_decreases_with_quality_3(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test quality 3 (correct with difficulty) decreases EF slightly."""
        vocab = _make_vocab(easiness_factor=2.5)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=3)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        # EF = 2.5 + (0.1 - 2*(0.08+2*0.02)) = 2.5 + (0.1 - 2*0.12) = 2.5 + (0.1-0.24) = 2.5 - 0.14 = 2.36
        expected_ef = 2.5 + (0.1 - (5 - 3) * (0.08 + (5 - 3) * 0.02))
        assert update_data["easiness_factor"] == pytest.approx(expected_ef, abs=0.001)

    def test_easiness_factor_stable_with_quality_4(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test quality 4 keeps EF relatively stable."""
        vocab = _make_vocab(easiness_factor=2.5)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=4)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        # EF = 2.5 + (0.1 - 1*(0.08+1*0.02)) = 2.5 + (0.1 - 0.1) = 2.5
        expected_ef = 2.5 + (0.1 - (5 - 4) * (0.08 + (5 - 4) * 0.02))
        assert update_data["easiness_factor"] == pytest.approx(expected_ef, abs=0.001)

    @pytest.mark.parametrize(
        "quality,initial_ef,expected_ef",
        [
            (0, 2.5, 1.7),
            (1, 2.5, 1.96),
            (2, 2.5, 2.18),
            (3, 2.5, 2.36),
            (4, 2.5, 2.5),
            (5, 2.5, 2.6),
        ],
    )
    def test_easiness_factor_calculation_all_qualities(
        self,
        service,
        mock_vocab_repo,
        mock_supabase_client,
        quality,
        initial_ef,
        expected_ef,
    ) -> None:
        """Test the complete easiness factor adjustment formula for all quality scores."""
        vocab = _make_vocab(easiness_factor=initial_ef)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=quality)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["easiness_factor"] == pytest.approx(max(1.3, expected_ef), abs=0.01)

    # -------------------------------------------------------------------------
    # Consecutive failures
    # -------------------------------------------------------------------------

    def test_consecutive_failures_keep_resetting(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test multiple consecutive failures keep interval at 1 and rep at 0."""
        # Even after multiple failures, the state stays reset
        vocab = _make_vocab(repetition_count=0, interval_days=1, easiness_factor=1.5)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=0)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["repetition_count"] == 0
        assert update_data["interval_days"] == 1

    # -------------------------------------------------------------------------
    # Recovery after failure
    # -------------------------------------------------------------------------

    def test_recovery_after_failure_starts_from_interval_1(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test that after a failure reset, successful recall starts from interval=1."""
        # Simulates the state AFTER a failure reset: rep=0, interval=1
        vocab = _make_vocab(repetition_count=0, interval_days=1, easiness_factor=2.0)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=4)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["interval_days"] == 1  # first success = 1 day
        assert update_data["repetition_count"] == 1

    # -------------------------------------------------------------------------
    # next_review_at and last_reviewed_at scheduling
    # -------------------------------------------------------------------------

    def test_next_review_at_scheduled_correctly(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test next_review_at is set to now + interval_days."""
        vocab = _make_vocab(repetition_count=1, interval_days=1, easiness_factor=2.5)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        before = datetime.now(UTC)
        service.update_sm2(vocab_id=1, quality=5)
        after = datetime.now(UTC)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]

        # interval_days should be 6 (second success)
        assert update_data["interval_days"] == 6

        # next_review_at should be approximately now + 6 days
        next_review = datetime.fromisoformat(update_data["next_review_at"])
        expected_earliest = before + timedelta(days=6)
        expected_latest = after + timedelta(days=6)
        assert expected_earliest <= next_review <= expected_latest

    def test_last_reviewed_at_set_to_now(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test last_reviewed_at is set to the current time on update."""
        vocab = _make_vocab(repetition_count=0, interval_days=0, easiness_factor=2.5)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        before = datetime.now(UTC)
        service.update_sm2(vocab_id=1, quality=3)
        after = datetime.now(UTC)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        last_reviewed = datetime.fromisoformat(update_data["last_reviewed_at"])
        assert before <= last_reviewed <= after

    # -------------------------------------------------------------------------
    # Default value handling for new entries
    # -------------------------------------------------------------------------

    def test_new_entry_with_none_sm2_fields_uses_defaults(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test that None SM-2 fields default to sensible values.

        When Supabase returns NULL for SM-2 columns, update_sm2 uses
        `getattr(vocab, 'field', default) or default` to fall back to
        safe defaults (EF=2.5, interval=0, rep=0).
        """
        mock_vocab = _make_mock_vocab_with_none_sm2(vocab_id=1, times_seen=1, times_correct=0)
        mock_vocab_repo.get_all.return_value = [mock_vocab]

        # Provide valid return data for the Supabase update call
        return_data = {
            "id": 1,
            "user_id": USER_ID,
            "word": "hola",
            "translation": "hello",
            "language": "es",
            "times_seen": 2,
            "times_correct": 1,
            "easiness_factor": 2.6,
            "interval_days": 1,
            "repetition_count": 1,
            "next_review_at": datetime.now(UTC).isoformat(),
            "last_reviewed_at": datetime.now(UTC).isoformat(),
            "first_seen_at": datetime.now(UTC).isoformat(),
        }
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[return_data]
        )

        service.update_sm2(vocab_id=1, quality=5)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        # With defaults: EF=2.5, interval=0, rep=0 -> first success => interval=1, rep=1
        assert update_data["interval_days"] == 1
        assert update_data["repetition_count"] == 1

    # -------------------------------------------------------------------------
    # Database persistence
    # -------------------------------------------------------------------------

    def test_update_calls_supabase_with_correct_filters(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test that update uses correct table, vocab_id, and user_id filters."""
        vocab = _make_vocab(vocab_id=42)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=42, quality=4)

        mock_supabase_client.table.assert_called_with("vocabulary")

    def test_update_raises_on_empty_response(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test ValueError raised when Supabase returns empty data on update."""
        vocab = _make_vocab()
        mock_vocab_repo.get_all.return_value = [vocab]

        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        with pytest.raises(ValueError, match="Failed to update vocabulary"):
            service.update_sm2(vocab_id=1, quality=4)


# =============================================================================
# SM-2 Algorithm Integration / Multi-Step Scenario Tests
# =============================================================================


class TestSM2MultiStepScenarios:
    """End-to-end SM-2 scenarios that simulate realistic learning paths.

    These tests verify the correct EF and interval values across multiple
    simulated review steps by computing the expected values manually
    according to the algorithm, then checking the actual call.
    """

    def test_full_progression_quality_5_four_reviews(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Simulate 4 consecutive quality-5 reviews and verify interval progression.

        Step 1: rep=0 -> interval=1, rep=1, EF=2.6
        Step 2: rep=1 -> interval=6, rep=2, EF=2.7
        Step 3: rep=2 -> interval=round(6*2.7)=16, rep=3, EF=2.8
        Step 4: rep=3 -> interval=round(16*2.8)=45, rep=4, EF=2.9
        """
        # Step 1
        vocab_step1 = _make_vocab(repetition_count=0, interval_days=0, easiness_factor=2.5)
        mock_vocab_repo.get_all.return_value = [vocab_step1]
        updated_data = vocab_step1.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=5)
        call_args_1 = mock_supabase_client.table.return_value.update.call_args[0][0]
        assert call_args_1["interval_days"] == 1
        assert call_args_1["repetition_count"] == 1
        assert call_args_1["easiness_factor"] == pytest.approx(2.6, abs=0.01)

        # Step 2
        vocab_step2 = _make_vocab(repetition_count=1, interval_days=1, easiness_factor=2.6)
        mock_vocab_repo.get_all.return_value = [vocab_step2]

        service.update_sm2(vocab_id=1, quality=5)
        call_args_2 = mock_supabase_client.table.return_value.update.call_args[0][0]
        assert call_args_2["interval_days"] == 6
        assert call_args_2["repetition_count"] == 2
        assert call_args_2["easiness_factor"] == pytest.approx(2.7, abs=0.01)

        # Step 3
        vocab_step3 = _make_vocab(repetition_count=2, interval_days=6, easiness_factor=2.7)
        mock_vocab_repo.get_all.return_value = [vocab_step3]

        service.update_sm2(vocab_id=1, quality=5)
        call_args_3 = mock_supabase_client.table.return_value.update.call_args[0][0]
        assert call_args_3["interval_days"] == round(6 * 2.7)  # 16
        assert call_args_3["repetition_count"] == 3
        assert call_args_3["easiness_factor"] == pytest.approx(2.8, abs=0.01)

        # Step 4
        vocab_step4 = _make_vocab(
            repetition_count=3, interval_days=round(6 * 2.7), easiness_factor=2.8
        )
        mock_vocab_repo.get_all.return_value = [vocab_step4]

        service.update_sm2(vocab_id=1, quality=5)
        call_args_4 = mock_supabase_client.table.return_value.update.call_args[0][0]
        assert call_args_4["interval_days"] == round(round(6 * 2.7) * 2.8)  # 45
        assert call_args_4["repetition_count"] == 4

    def test_failure_in_middle_of_progression_resets(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test that a failure after multiple successes resets the progression.

        Step 1: quality=5, rep=0 -> interval=1, rep=1
        Step 2: quality=5, rep=1 -> interval=6, rep=2
        Step 3: quality=1 (fail), rep=2 -> interval=1, rep=0 (RESET)
        Step 4: quality=5, rep=0 -> interval=1, rep=1 (starts over)
        """
        # Step 1
        vocab = _make_vocab(repetition_count=0, interval_days=0, easiness_factor=2.5)
        mock_vocab_repo.get_all.return_value = [vocab]
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[vocab.model_dump()]
        )

        service.update_sm2(vocab_id=1, quality=5)
        data_1 = mock_supabase_client.table.return_value.update.call_args[0][0]
        assert data_1["interval_days"] == 1
        assert data_1["repetition_count"] == 1

        # Step 2
        vocab_s2 = _make_vocab(
            repetition_count=1, interval_days=1, easiness_factor=data_1["easiness_factor"]
        )
        mock_vocab_repo.get_all.return_value = [vocab_s2]
        service.update_sm2(vocab_id=1, quality=5)
        data_2 = mock_supabase_client.table.return_value.update.call_args[0][0]
        assert data_2["interval_days"] == 6
        assert data_2["repetition_count"] == 2

        # Step 3: FAILURE
        vocab_s3 = _make_vocab(
            repetition_count=2, interval_days=6, easiness_factor=data_2["easiness_factor"]
        )
        mock_vocab_repo.get_all.return_value = [vocab_s3]
        service.update_sm2(vocab_id=1, quality=1)
        data_3 = mock_supabase_client.table.return_value.update.call_args[0][0]
        assert data_3["interval_days"] == 1
        assert data_3["repetition_count"] == 0

        # Step 4: Recovery
        vocab_s4 = _make_vocab(
            repetition_count=0, interval_days=1, easiness_factor=data_3["easiness_factor"]
        )
        mock_vocab_repo.get_all.return_value = [vocab_s4]
        service.update_sm2(vocab_id=1, quality=5)
        data_4 = mock_supabase_client.table.return_value.update.call_args[0][0]
        assert data_4["interval_days"] == 1
        assert data_4["repetition_count"] == 1


# =============================================================================
# get_stats Tests
# =============================================================================


class TestGetStats:
    """Tests for ReviewService.get_stats."""

    def test_zero_state_no_vocab(self, service, mock_vocab_repo) -> None:
        """Test stats when user has no vocabulary."""
        mock_vocab_repo.get_all.return_value = []

        stats = service.get_stats(language="es")

        assert stats.due_count == 0
        assert stats.next_review_in is None
        assert stats.total_in_rotation == 0

    def test_words_not_in_rotation(self, service, mock_vocab_repo) -> None:
        """Test words with no next_review_at are not counted in rotation."""
        mock_vocab_repo.get_all.return_value = [
            _make_vocab("hola", next_review_at=None),
            _make_vocab("gracias", next_review_at=None),
        ]

        stats = service.get_stats(language="es")

        assert stats.total_in_rotation == 0
        assert stats.due_count == 0

    def test_words_in_rotation_counted(self, service, mock_vocab_repo) -> None:
        """Test words with next_review_at are counted in rotation."""
        now = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = [
            _make_vocab("hola", vocab_id=1, next_review_at=now - timedelta(hours=1)),
            _make_vocab("gracias", vocab_id=2, next_review_at=now + timedelta(hours=2)),
            _make_vocab("bueno", vocab_id=3, next_review_at=None),
        ]

        stats = service.get_stats(language="es")

        assert stats.total_in_rotation == 2

    def test_due_words_counted_correctly(self, service, mock_vocab_repo) -> None:
        """Test due words (next_review_at <= now) are counted."""
        now = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = [
            _make_vocab("hola", vocab_id=1, next_review_at=now - timedelta(hours=2)),
            _make_vocab("gracias", vocab_id=2, next_review_at=now - timedelta(minutes=5)),
            _make_vocab("bueno", vocab_id=3, next_review_at=now + timedelta(hours=1)),
        ]

        stats = service.get_stats(language="es")

        assert stats.due_count == 2
        assert stats.total_in_rotation == 3

    def test_next_review_in_calculated_for_future_words(self, service, mock_vocab_repo) -> None:
        """Test next_review_in shows time until soonest non-due word.

        Uses 3.5 hours offset to ensure the delta stays firmly in the
        '3 hours' bucket despite minor time drift between test setup
        and service execution.
        """
        now = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = [
            _make_vocab("hola", vocab_id=1, next_review_at=now - timedelta(hours=1)),
            _make_vocab(
                "gracias",
                vocab_id=2,
                next_review_at=now + timedelta(hours=3, minutes=30),
            ),
            _make_vocab("bueno", vocab_id=3, next_review_at=now + timedelta(days=2)),
        ]

        stats = service.get_stats(language="es")

        assert stats.next_review_in == "3 hours"

    def test_next_review_in_none_when_all_due(self, service, mock_vocab_repo) -> None:
        """Test next_review_in is None when all words are already due."""
        now = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = [
            _make_vocab("hola", vocab_id=1, next_review_at=now - timedelta(hours=1)),
            _make_vocab("gracias", vocab_id=2, next_review_at=now - timedelta(hours=2)),
        ]

        stats = service.get_stats(language="es")

        assert stats.next_review_in is None

    def test_default_language_is_es(self, service, mock_vocab_repo) -> None:
        """Test default language parameter is 'es'."""
        mock_vocab_repo.get_all.return_value = []

        service.get_stats()

        mock_vocab_repo.get_all.assert_called_once_with(language="es")

    def test_language_parameter_passed_through(self, service, mock_vocab_repo) -> None:
        """Test custom language parameter is forwarded to repository."""
        mock_vocab_repo.get_all.return_value = []

        service.get_stats(language="de")

        mock_vocab_repo.get_all.assert_called_once_with(language="de")


# =============================================================================
# get_due_words Tests
# =============================================================================


class TestGetDueWords:
    """Tests for ReviewService.get_due_words."""

    def test_returns_empty_list_when_no_vocab(self, service, mock_vocab_repo) -> None:
        """Test empty list returned when no vocabulary exists."""
        mock_vocab_repo.get_all.return_value = []

        result = service.get_due_words(language="es")

        assert result == []

    def test_filters_to_only_due_words(self, service, mock_vocab_repo) -> None:
        """Test only words with next_review_at <= now are returned."""
        now = datetime.now(UTC)
        due_word = _make_vocab("hola", vocab_id=1, next_review_at=now - timedelta(hours=1))
        future_word = _make_vocab("gracias", vocab_id=2, next_review_at=now + timedelta(hours=2))
        no_review_word = _make_vocab("bueno", vocab_id=3, next_review_at=None)

        mock_vocab_repo.get_all.return_value = [due_word, future_word, no_review_word]

        result = service.get_due_words(language="es")

        assert len(result) == 1
        assert result[0].word == "hola"

    def test_sorted_by_most_overdue_first(self, service, mock_vocab_repo) -> None:
        """Test due words are sorted by earliest next_review_at first."""
        now = datetime.now(UTC)
        word_a = _make_vocab("hola", vocab_id=1, next_review_at=now - timedelta(hours=1))
        word_b = _make_vocab("gracias", vocab_id=2, next_review_at=now - timedelta(hours=5))
        word_c = _make_vocab("bueno", vocab_id=3, next_review_at=now - timedelta(hours=3))

        mock_vocab_repo.get_all.return_value = [word_a, word_b, word_c]

        result = service.get_due_words(language="es")

        assert len(result) == 3
        # Most overdue first: gracias (5h ago), bueno (3h ago), hola (1h ago)
        assert result[0].word == "gracias"
        assert result[1].word == "bueno"
        assert result[2].word == "hola"

    def test_limit_restricts_results(self, service, mock_vocab_repo) -> None:
        """Test limit parameter caps the number of returned words."""
        now = datetime.now(UTC)
        words = [
            _make_vocab(f"word{i}", vocab_id=i, next_review_at=now - timedelta(hours=i))
            for i in range(1, 11)
        ]
        mock_vocab_repo.get_all.return_value = words

        result = service.get_due_words(language="es", limit=3)

        assert len(result) == 3

    def test_limit_none_returns_all(self, service, mock_vocab_repo) -> None:
        """Test limit=None returns all due words."""
        now = datetime.now(UTC)
        words = [
            _make_vocab(f"word{i}", vocab_id=i, next_review_at=now - timedelta(hours=i))
            for i in range(1, 6)
        ]
        mock_vocab_repo.get_all.return_value = words

        result = service.get_due_words(language="es", limit=None)

        assert len(result) == 5

    def test_limit_larger_than_available(self, service, mock_vocab_repo) -> None:
        """Test limit larger than available due words returns all available."""
        now = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = [
            _make_vocab("hola", vocab_id=1, next_review_at=now - timedelta(hours=1)),
        ]

        result = service.get_due_words(language="es", limit=100)

        assert len(result) == 1


# =============================================================================
# get_topical_review_words Tests
# =============================================================================


class TestGetTopicalReviewWords:
    """Tests for ReviewService.get_topical_review_words."""

    def test_empty_keywords_returns_first_n_due(self, service, mock_vocab_repo) -> None:
        """Test empty topic_keywords returns first due words up to limit."""
        now = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = [
            _make_vocab("hola", vocab_id=1, next_review_at=now - timedelta(hours=1)),
            _make_vocab("gracias", vocab_id=2, next_review_at=now - timedelta(hours=2)),
            _make_vocab("bueno", vocab_id=3, next_review_at=now - timedelta(hours=3)),
        ]

        result = service.get_topical_review_words(language="es", topic_keywords=[], limit=2)

        assert len(result) == 2

    def test_matches_on_word_case_insensitive(self, service, mock_vocab_repo) -> None:
        """Test matching works case-insensitively on the word field."""
        now = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = [
            _make_vocab("Hola", vocab_id=1, next_review_at=now - timedelta(hours=1)),
            _make_vocab("gracias", vocab_id=2, next_review_at=now - timedelta(hours=2)),
        ]

        result = service.get_topical_review_words(language="es", topic_keywords=["hola"], limit=5)

        assert len(result) == 1
        assert result[0].word == "Hola"

    def test_matches_on_translation_case_insensitive(self, service, mock_vocab_repo) -> None:
        """Test matching works case-insensitively on the translation field."""
        now = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = [
            _make_vocab(
                "hola",
                translation="Hello",
                vocab_id=1,
                next_review_at=now - timedelta(hours=1),
            ),
            _make_vocab(
                "gracias",
                translation="Thanks",
                vocab_id=2,
                next_review_at=now - timedelta(hours=2),
            ),
        ]

        result = service.get_topical_review_words(language="es", topic_keywords=["hello"], limit=5)

        assert len(result) == 1
        assert result[0].word == "hola"

    def test_partial_match_on_keyword(self, service, mock_vocab_repo) -> None:
        """Test keywords match as substrings (contains match)."""
        now = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = [
            _make_vocab(
                "buenos dias",
                translation="good morning",
                vocab_id=1,
                next_review_at=now - timedelta(hours=1),
            ),
        ]

        result = service.get_topical_review_words(language="es", topic_keywords=["buenos"], limit=5)

        assert len(result) == 1

    def test_respects_limit(self, service, mock_vocab_repo) -> None:
        """Test topical match respects the limit parameter."""
        now = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = [
            _make_vocab(
                f"food{i}",
                translation=f"comida{i}",
                vocab_id=i,
                next_review_at=now - timedelta(hours=i),
            )
            for i in range(1, 10)
        ]

        result = service.get_topical_review_words(language="es", topic_keywords=["food"], limit=3)

        assert len(result) == 3

    def test_no_matches_returns_empty(self, service, mock_vocab_repo) -> None:
        """Test returns empty list when no words match keywords."""
        now = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = [
            _make_vocab("hola", vocab_id=1, next_review_at=now - timedelta(hours=1)),
        ]

        result = service.get_topical_review_words(
            language="es", topic_keywords=["restaurant"], limit=5
        )

        assert result == []

    def test_only_due_words_considered(self, service, mock_vocab_repo) -> None:
        """Test topical matching only considers due words (not future or unscheduled)."""
        now = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = [
            _make_vocab(
                "hola",
                vocab_id=1,
                next_review_at=now + timedelta(hours=5),  # not due
            ),
            _make_vocab(
                "hola amigo",
                vocab_id=2,
                next_review_at=now - timedelta(hours=1),  # due
            ),
        ]

        result = service.get_topical_review_words(language="es", topic_keywords=["hola"], limit=5)

        assert len(result) == 1
        assert result[0].word == "hola amigo"

    def test_word_matched_only_once(self, service, mock_vocab_repo) -> None:
        """Test each vocabulary item is added at most once even if multiple keywords match."""
        now = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = [
            _make_vocab(
                "hola amigo",
                translation="hello friend",
                vocab_id=1,
                next_review_at=now - timedelta(hours=1),
            ),
        ]

        result = service.get_topical_review_words(
            language="es", topic_keywords=["hola", "hello"], limit=5
        )

        assert len(result) == 1

    def test_multiple_keywords_match_different_words(self, service, mock_vocab_repo) -> None:
        """Test multiple keywords can match different vocabulary items."""
        now = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = [
            _make_vocab(
                "hola",
                translation="hello",
                vocab_id=1,
                next_review_at=now - timedelta(hours=2),
            ),
            _make_vocab(
                "comer",
                translation="to eat",
                vocab_id=2,
                next_review_at=now - timedelta(hours=1),
            ),
            _make_vocab(
                "dormir",
                translation="to sleep",
                vocab_id=3,
                next_review_at=now - timedelta(hours=3),
            ),
        ]

        result = service.get_topical_review_words(
            language="es", topic_keywords=["hello", "eat"], limit=5
        )

        assert len(result) == 2
        matched_words = {v.word for v in result}
        assert matched_words == {"hola", "comer"}


# =============================================================================
# initialize_word_for_review Tests
# =============================================================================


class TestInitializeWordForReview:
    """Tests for ReviewService.initialize_word_for_review."""

    def test_vocab_not_found_raises(self, service, mock_vocab_repo, mock_supabase_client) -> None:
        """Test ValueError when vocab_id does not exist."""
        mock_vocab_repo.get_all.return_value = []

        with pytest.raises(ValueError, match="Vocabulary with id 999 not found"):
            service.initialize_word_for_review(vocab_id=999)

    def test_sets_default_sm2_values(self, service, mock_vocab_repo, mock_supabase_client) -> None:
        """Test initialize sets default SM-2 values (EF=2.5, interval=1, rep=0)."""
        vocab = _make_vocab(vocab_id=1, times_seen=3, times_correct=2)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.initialize_word_for_review(vocab_id=1)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["easiness_factor"] == 2.5
        assert update_data["interval_days"] == 1
        assert update_data["repetition_count"] == 0

    def test_schedules_next_review_for_tomorrow(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test next_review_at is set to approximately 1 day from now."""
        vocab = _make_vocab(vocab_id=1)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        before = datetime.now(UTC)
        service.initialize_word_for_review(vocab_id=1)
        after = datetime.now(UTC)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        next_review = datetime.fromisoformat(update_data["next_review_at"])

        expected_earliest = before + timedelta(days=1)
        expected_latest = after + timedelta(days=1)
        assert expected_earliest <= next_review <= expected_latest

    def test_does_not_set_last_reviewed_at(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test initialize does not set last_reviewed_at (it passes None)."""
        vocab = _make_vocab(vocab_id=1)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.initialize_word_for_review(vocab_id=1)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert "last_reviewed_at" not in update_data

    def test_preserves_times_seen_and_times_correct(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test initialize preserves existing times_seen and times_correct."""
        vocab = _make_vocab(vocab_id=1, times_seen=7, times_correct=4)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.initialize_word_for_review(vocab_id=1)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        assert update_data["times_seen"] == 7
        assert update_data["times_correct"] == 4


# =============================================================================
# _calculate_next_review_in Tests
# =============================================================================


class TestCalculateNextReviewIn:
    """Tests for ReviewService._calculate_next_review_in helper."""

    def test_returns_none_when_no_upcoming(self, service, mock_vocab_repo) -> None:
        """Test returns None when all words are due (none upcoming)."""
        now = datetime.now(UTC)
        in_rotation = [
            _make_vocab("hola", vocab_id=1, next_review_at=now - timedelta(hours=1)),
        ]

        result = service._calculate_next_review_in(in_rotation, now)

        assert result is None

    def test_returns_none_when_empty_list(self, service, mock_vocab_repo) -> None:
        """Test returns None when in_rotation is empty."""
        now = datetime.now(UTC)

        result = service._calculate_next_review_in([], now)

        assert result is None

    def test_picks_soonest_upcoming(self, service, mock_vocab_repo) -> None:
        """Test returns time for the soonest upcoming word."""
        now = datetime.now(UTC)
        in_rotation = [
            _make_vocab("hola", vocab_id=1, next_review_at=now + timedelta(hours=5)),
            _make_vocab("gracias", vocab_id=2, next_review_at=now + timedelta(hours=2)),
        ]

        result = service._calculate_next_review_in(in_rotation, now)

        assert result == "2 hours"

    def test_ignores_already_due_words(self, service, mock_vocab_repo) -> None:
        """Test already-due words are not considered as upcoming."""
        now = datetime.now(UTC)
        in_rotation = [
            _make_vocab("hola", vocab_id=1, next_review_at=now - timedelta(hours=1)),
            _make_vocab("gracias", vocab_id=2, next_review_at=now + timedelta(days=3)),
        ]

        result = service._calculate_next_review_in(in_rotation, now)

        assert result == "3 days"


# =============================================================================
# _format_timedelta Tests
# =============================================================================


class TestFormatTimedelta:
    """Tests for ReviewService._format_timedelta helper."""

    def test_negative_delta_returns_now(self, service, mock_vocab_repo) -> None:
        """Test negative timedelta returns 'now'."""
        result = service._format_timedelta(timedelta(seconds=-60))

        assert result == "now"

    def test_zero_delta_returns_1_minute(self, service, mock_vocab_repo) -> None:
        """Test zero or very small timedelta returns '1 minute'."""
        result = service._format_timedelta(timedelta(seconds=0))

        assert result == "1 minute"

    def test_one_minute(self, service, mock_vocab_repo) -> None:
        """Test 60 seconds returns '1 minute'."""
        result = service._format_timedelta(timedelta(seconds=60))

        assert result == "1 minute"

    def test_less_than_two_minutes(self, service, mock_vocab_repo) -> None:
        """Test 90 seconds returns '1 minute' (under 2 min threshold)."""
        result = service._format_timedelta(timedelta(seconds=90))

        assert result == "1 minute"

    def test_multiple_minutes(self, service, mock_vocab_repo) -> None:
        """Test 30 minutes returns '30 minutes'."""
        result = service._format_timedelta(timedelta(minutes=30))

        assert result == "30 minutes"

    def test_two_minutes(self, service, mock_vocab_repo) -> None:
        """Test 2 minutes returns '2 minutes'."""
        result = service._format_timedelta(timedelta(minutes=2))

        assert result == "2 minutes"

    def test_one_hour(self, service, mock_vocab_repo) -> None:
        """Test 1 hour returns '1 hour'."""
        result = service._format_timedelta(timedelta(hours=1))

        assert result == "1 hour"

    def test_multiple_hours(self, service, mock_vocab_repo) -> None:
        """Test 5 hours returns '5 hours'."""
        result = service._format_timedelta(timedelta(hours=5))

        assert result == "5 hours"

    def test_two_hours(self, service, mock_vocab_repo) -> None:
        """Test 2 hours returns '2 hours'."""
        result = service._format_timedelta(timedelta(hours=2))

        assert result == "2 hours"

    def test_tomorrow(self, service, mock_vocab_repo) -> None:
        """Test 1 day returns 'tomorrow'."""
        result = service._format_timedelta(timedelta(days=1))

        assert result == "tomorrow"

    def test_multiple_days(self, service, mock_vocab_repo) -> None:
        """Test 3 days returns '3 days'."""
        result = service._format_timedelta(timedelta(days=3))

        assert result == "3 days"

    def test_six_days(self, service, mock_vocab_repo) -> None:
        """Test 6 days returns '6 days'."""
        result = service._format_timedelta(timedelta(days=6))

        assert result == "6 days"

    def test_one_week(self, service, mock_vocab_repo) -> None:
        """Test 7 days returns '1 week'."""
        result = service._format_timedelta(timedelta(days=7))

        assert result == "1 week"

    def test_thirteen_days_still_one_week(self, service, mock_vocab_repo) -> None:
        """Test 13 days returns '1 week' (still under 14 days threshold)."""
        result = service._format_timedelta(timedelta(days=13))

        assert result == "1 week"

    def test_two_weeks(self, service, mock_vocab_repo) -> None:
        """Test 14 days returns '2 weeks'."""
        result = service._format_timedelta(timedelta(days=14))

        assert result == "2 weeks"

    def test_many_weeks(self, service, mock_vocab_repo) -> None:
        """Test 28 days returns '4 weeks'."""
        result = service._format_timedelta(timedelta(days=28))

        assert result == "4 weeks"

    @pytest.mark.parametrize(
        "delta,expected",
        [
            (timedelta(seconds=-1), "now"),
            (timedelta(seconds=30), "1 minute"),
            (timedelta(minutes=2), "2 minutes"),
            (timedelta(minutes=45), "45 minutes"),
            (timedelta(hours=1), "1 hour"),
            (timedelta(hours=2), "2 hours"),
            (timedelta(hours=23), "23 hours"),
            (timedelta(days=1), "tomorrow"),
            (timedelta(days=2), "2 days"),
            (timedelta(days=6), "6 days"),
            (timedelta(days=7), "1 week"),
            (timedelta(days=13), "1 week"),
            (timedelta(days=14), "2 weeks"),
            (timedelta(days=21), "3 weeks"),
        ],
    )
    def test_format_timedelta_parametrized(self, service, mock_vocab_repo, delta, expected) -> None:
        """Test _format_timedelta across a range of time deltas."""
        result = service._format_timedelta(delta)

        assert result == expected


# =============================================================================
# Service Initialization Tests
# =============================================================================


class TestServiceInit:
    """Tests for ReviewService initialization."""

    def test_init_creates_vocab_repository(self) -> None:
        """Test service creates VocabularyRepository with user_id."""
        with patch("src.services.review.VocabularyRepository") as mock_vocab:
            ReviewService("user-abc-789")

            mock_vocab.assert_called_once_with("user-abc-789", client=None)

    def test_init_with_client(self) -> None:
        """Test service passes client to VocabularyRepository."""
        mock_client = MagicMock()

        with patch("src.services.review.VocabularyRepository") as mock_vocab:
            ReviewService("user-abc-789", client=mock_client)

            mock_vocab.assert_called_once_with("user-abc-789", client=mock_client)

    def test_stores_user_id(self) -> None:
        """Test service stores the user_id."""
        with patch("src.services.review.VocabularyRepository"):
            svc = ReviewService("user-xyz-456")

            assert svc._user_id == "user-xyz-456"

    def test_stores_client(self) -> None:
        """Test service stores the client reference."""
        mock_client = MagicMock()

        with patch("src.services.review.VocabularyRepository"):
            svc = ReviewService("user-xyz-456", client=mock_client)

            assert svc._client is mock_client

    def test_client_defaults_to_none(self) -> None:
        """Test client defaults to None when not provided."""
        with patch("src.services.review.VocabularyRepository"):
            svc = ReviewService("user-xyz-456")

            assert svc._client is None


# =============================================================================
# Edge Case and Boundary Tests
# =============================================================================


class TestEdgeCases:
    """Boundary conditions and edge cases for the review service."""

    def test_quality_boundary_3_is_success(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test quality=3 is treated as successful recall (threshold boundary)."""
        vocab = _make_vocab(repetition_count=0, interval_days=0)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=3)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        # Quality 3 is successful: interval=1 (first), rep=1
        assert update_data["repetition_count"] == 1
        assert update_data["interval_days"] == 1

    def test_quality_boundary_2_is_failure(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test quality=2 is treated as failed recall (threshold boundary)."""
        vocab = _make_vocab(repetition_count=3, interval_days=15)
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=2)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        # Quality 2 is failure: reset
        assert update_data["repetition_count"] == 0
        assert update_data["interval_days"] == 1

    def test_very_large_interval_compounding(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test very large interval values compound correctly."""
        vocab = _make_vocab(
            repetition_count=10,
            interval_days=365,
            easiness_factor=2.5,
        )
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=5)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        # interval = round(365 * 2.5) = 912
        assert update_data["interval_days"] == round(365 * 2.5)

    def test_minimum_ef_with_quality_3_success(
        self, service, mock_vocab_repo, mock_supabase_client
    ) -> None:
        """Test quality 3 at minimum EF (1.3) still progresses intervals."""
        vocab = _make_vocab(
            repetition_count=2,
            interval_days=6,
            easiness_factor=1.3,
        )
        mock_vocab_repo.get_all.return_value = [vocab]

        updated_data = vocab.model_dump()
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        service.update_sm2(vocab_id=1, quality=3)

        call_args = mock_supabase_client.table.return_value.update.call_args
        update_data = call_args[0][0]
        # interval = round(6 * 1.3) = 8, slightly slower progression
        assert update_data["interval_days"] == round(6 * 1.3)
        assert update_data["repetition_count"] == 3

    def test_due_words_with_exactly_now_review_time(self, service, mock_vocab_repo) -> None:
        """Test words with next_review_at exactly now are considered due."""
        now = datetime.now(UTC)
        mock_vocab_repo.get_all.return_value = [
            _make_vocab("hola", vocab_id=1, next_review_at=now),
        ]

        result = service.get_due_words(language="es")

        assert len(result) == 1
