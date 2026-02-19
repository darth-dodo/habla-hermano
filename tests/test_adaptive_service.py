"""Tests for adaptive daily recommendation service.

Comprehensive tests for category strength computation, level readiness
detection, daily recommendation assembly, and suggestion text generation.
Uses real LessonService and PathService backed by YAML fixtures in a temp
directory -- no mocking of service internals required.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from src.db.models import LessonProgress, Vocabulary
from src.lessons.service import LessonService
from src.services.adaptive import (
    AdaptiveService,
    CategoryStrength,
    DailyRecommendation,
    LevelReadiness,
)
from src.services.paths import PathService

# =============================================================================
# Constants
# =============================================================================

CATEGORIES = ("greetings", "introductions", "numbers", "colors", "family")
LEVELS = ("A0", "A1", "A2", "B1")

# Two words per category per level -- enough to test aggregation without bloat.
CATEGORY_WORDS: dict[str, list[dict[str, str]]] = {
    "greetings": [
        {"word": "hola", "translation": "hello"},
        {"word": "adios", "translation": "goodbye"},
    ],
    "introductions": [
        {"word": "me llamo", "translation": "my name is"},
        {"word": "mucho gusto", "translation": "nice to meet you"},
    ],
    "numbers": [
        {"word": "uno", "translation": "one"},
        {"word": "dos", "translation": "two"},
    ],
    "colors": [
        {"word": "rojo", "translation": "red"},
        {"word": "azul", "translation": "blue"},
    ],
    "family": [
        {"word": "madre", "translation": "mother"},
        {"word": "padre", "translation": "father"},
    ],
}

CATEGORY_TITLES: dict[str, str] = {
    "greetings": "Basic Greetings",
    "introductions": "Introducing Yourself",
    "numbers": "Counting Basics",
    "colors": "Color Vocabulary",
    "family": "Family Members",
}

CATEGORY_ICONS: dict[str, str] = {
    "greetings": "wave",
    "introductions": "hand",
    "numbers": "123",
    "colors": "art",
    "family": "people",
}


# =============================================================================
# Helpers
# =============================================================================


def _make_vocab(
    word: str,
    translation: str = "trans",
    language: str = "es",
    times_seen: int = 1,
    times_correct: int = 0,
) -> Vocabulary:
    """Build a Vocabulary instance for tests."""
    return Vocabulary(
        id=1,
        user_id="test-user",
        word=word,
        translation=translation,
        language=language,
        times_seen=times_seen,
        times_correct=times_correct,
        first_seen_at=datetime.now(UTC),
    )


def _make_lesson_progress(lesson_id: str, completed: bool = True) -> LessonProgress:
    """Build a LessonProgress instance for tests."""
    return LessonProgress(
        user_id="test-user",
        lesson_id=lesson_id,
        completed_at=datetime.now(UTC) if completed else None,
        score=80 if completed else None,
    )


def _build_lesson_yaml(
    lesson_id: str,
    title: str,
    category: str,
    language: str,
    level: str,
    words: list[dict[str, str]],
) -> str:
    """Build a lesson YAML string with a vocabulary step."""
    data = {
        "id": lesson_id,
        "title": title,
        "description": f"Learn {category}",
        "language": language,
        "level": level,
        "category": category,
        "icon": CATEGORY_ICONS.get(category, "book"),
        "steps": [
            {
                "type": "vocabulary",
                "content": "Key vocabulary",
                "vocabulary": words,
                "order": 1,
            },
        ],
        "exercises": [],
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def lessons_dir(tmp_path: Path) -> Path:
    """Create a full lesson tree: es / 4 levels x 5 categories = 20 lessons.

    Each lesson has a vocabulary step with two words from CATEGORY_WORDS.
    """
    base = tmp_path / "lessons"
    for level in LEVELS:
        level_dir = base / "es" / level
        level_dir.mkdir(parents=True)
        for cat in CATEGORIES:
            lid = f"{cat}-001"
            content = _build_lesson_yaml(
                lesson_id=lid,
                title=CATEGORY_TITLES[cat],
                category=cat,
                language="es",
                level=level,
                words=CATEGORY_WORDS[cat],
            )
            (level_dir / f"{lid}.yaml").write_text(content)
    return base


@pytest.fixture
def lesson_service(lessons_dir: Path) -> LessonService:
    """Create a LessonService backed by the temp lesson directory."""
    return LessonService(lessons_dir=lessons_dir)


@pytest.fixture
def path_service(lesson_service: LessonService) -> PathService:
    """Create a PathService backed by the temp lesson directory."""
    return PathService(lesson_service)


@pytest.fixture
def service(path_service: PathService, lesson_service: LessonService) -> AdaptiveService:
    """Create an AdaptiveService with real path and lesson services."""
    return AdaptiveService(path_service, lesson_service)


# =============================================================================
# CategoryStrength Dataclass Tests
# =============================================================================


class TestCategoryStrengthDataclass:
    """Tests for the CategoryStrength frozen dataclass."""

    def test_create_category_strength(self) -> None:
        """CategoryStrength should accept all fields."""
        cs = CategoryStrength(
            category="greetings",
            total_words=10,
            words_seen=5,
            accuracy=0.75,
            is_weak=False,
        )
        assert cs.category == "greetings"
        assert cs.total_words == 10
        assert cs.words_seen == 5
        assert cs.accuracy == 0.75
        assert cs.is_weak is False

    def test_category_strength_is_frozen(self) -> None:
        """CategoryStrength should be immutable."""
        cs = CategoryStrength(
            category="greetings", total_words=0, words_seen=0, accuracy=0.0, is_weak=False,
        )
        with pytest.raises(AttributeError):
            cs.accuracy = 1.0  # type: ignore[misc]


# =============================================================================
# LevelReadiness Dataclass Tests
# =============================================================================


class TestLevelReadinessDataclass:
    """Tests for the LevelReadiness frozen dataclass."""

    def test_create_level_readiness(self) -> None:
        """LevelReadiness should accept all fields."""
        lr = LevelReadiness(
            current_level="A0",
            completed_in_level=3,
            total_in_level=5,
            readiness_pct=60.0,
            is_ready=False,
            next_level="A1",
        )
        assert lr.current_level == "A0"
        assert lr.completed_in_level == 3
        assert lr.total_in_level == 5
        assert lr.readiness_pct == 60.0
        assert lr.is_ready is False
        assert lr.next_level == "A1"

    def test_level_readiness_is_frozen(self) -> None:
        """LevelReadiness should be immutable."""
        lr = LevelReadiness(
            current_level="A0",
            completed_in_level=0,
            total_in_level=5,
            readiness_pct=0.0,
            is_ready=False,
            next_level="A1",
        )
        with pytest.raises(AttributeError):
            lr.is_ready = True  # type: ignore[misc]


# =============================================================================
# DailyRecommendation Dataclass Tests
# =============================================================================


class TestDailyRecommendationDataclass:
    """Tests for the DailyRecommendation frozen dataclass."""

    def test_create_daily_recommendation(self) -> None:
        """DailyRecommendation should accept all fields including None."""
        rec = DailyRecommendation(
            next_lesson=None,
            review_due_count=0,
            weak_categories=[],
            level_readiness=None,
            suggestion_text="Keep going!",
        )
        assert rec.next_lesson is None
        assert rec.review_due_count == 0
        assert rec.weak_categories == []
        assert rec.level_readiness is None
        assert rec.suggestion_text == "Keep going!"

    def test_daily_recommendation_is_frozen(self) -> None:
        """DailyRecommendation should be immutable."""
        rec = DailyRecommendation(
            next_lesson=None,
            review_due_count=0,
            weak_categories=[],
            level_readiness=None,
            suggestion_text="",
        )
        with pytest.raises(AttributeError):
            rec.review_due_count = 5  # type: ignore[misc]


# =============================================================================
# get_category_strengths Tests
# =============================================================================


class TestCategoryStrengths:
    """Tests for AdaptiveService.get_category_strengths."""

    def test_empty_vocab_returns_categories_with_zero_words(
        self, service: AdaptiveService,
    ) -> None:
        """When no vocab data exists, each category should show 0 totals."""
        strengths = service.get_category_strengths("es", [])

        assert len(strengths) > 0
        for cs in strengths:
            assert cs.total_words == 0
            assert cs.words_seen == 0
            assert cs.accuracy == 0.0
            assert cs.is_weak is False

    def test_maps_words_to_correct_categories(
        self, service: AdaptiveService,
    ) -> None:
        """Words should be grouped into the category defined by their lesson."""
        vocab = [
            _make_vocab("hola", "hello"),
            _make_vocab("adios", "goodbye"),
            _make_vocab("rojo", "red"),
        ]
        strengths = service.get_category_strengths("es", vocab)

        strength_map = {cs.category: cs for cs in strengths}

        assert strength_map["greetings"].total_words == 2
        assert strength_map["colors"].total_words == 1

    def test_calculates_accuracy_correctly(
        self, service: AdaptiveService,
    ) -> None:
        """Accuracy should be sum(times_correct) / sum(times_seen)."""
        vocab = [
            _make_vocab("hola", "hello", times_seen=10, times_correct=8),
            _make_vocab("adios", "goodbye", times_seen=10, times_correct=6),
        ]
        strengths = service.get_category_strengths("es", vocab)

        strength_map = {cs.category: cs for cs in strengths}
        greetings = strength_map["greetings"]

        # (8 + 6) / (10 + 10) = 0.7
        assert greetings.accuracy == 0.7
        assert greetings.words_seen == 2

    def test_is_weak_true_when_accuracy_below_threshold(
        self, service: AdaptiveService,
    ) -> None:
        """is_weak should be True when accuracy < 0.7 and seen > 0."""
        vocab = [
            _make_vocab("hola", "hello", times_seen=10, times_correct=5),
        ]
        strengths = service.get_category_strengths("es", vocab)

        strength_map = {cs.category: cs for cs in strengths}
        greetings = strength_map["greetings"]

        assert greetings.accuracy == 0.5
        assert greetings.is_weak is True

    def test_is_weak_false_when_accuracy_at_threshold(
        self, service: AdaptiveService,
    ) -> None:
        """is_weak should be False when accuracy >= 0.7."""
        vocab = [
            _make_vocab("hola", "hello", times_seen=10, times_correct=7),
        ]
        strengths = service.get_category_strengths("es", vocab)

        strength_map = {cs.category: cs for cs in strengths}
        greetings = strength_map["greetings"]

        assert greetings.accuracy == 0.7
        assert greetings.is_weak is False

    def test_is_weak_false_when_no_words_seen(
        self, service: AdaptiveService,
    ) -> None:
        """is_weak should be False when no words have been seen even with 0 accuracy."""
        # Provide vocab for a different language so category has 0 seen words
        vocab = [
            _make_vocab("hola", "hello", language="de", times_seen=0, times_correct=0),
        ]
        strengths = service.get_category_strengths("es", vocab)

        for cs in strengths:
            assert cs.is_weak is False

    def test_filters_vocab_by_language(
        self, service: AdaptiveService,
    ) -> None:
        """Only vocab matching the requested language should be included."""
        vocab = [
            _make_vocab("hola", "hello", language="es", times_seen=5, times_correct=3),
            _make_vocab("hola", "hello", language="de", times_seen=10, times_correct=1),
        ]
        strengths = service.get_category_strengths("es", vocab)

        strength_map = {cs.category: cs for cs in strengths}
        greetings = strength_map["greetings"]

        # Only the es vocab should be counted
        assert greetings.total_words == 1
        assert greetings.accuracy == 0.6

    def test_case_insensitive_word_matching(
        self, service: AdaptiveService,
    ) -> None:
        """Word matching should be case-insensitive."""
        vocab = [
            _make_vocab("Hola", "hello", times_seen=4, times_correct=4),
        ]
        strengths = service.get_category_strengths("es", vocab)

        strength_map = {cs.category: cs for cs in strengths}
        assert strength_map["greetings"].total_words == 1

    def test_accuracy_rounded_to_two_decimals(
        self, service: AdaptiveService,
    ) -> None:
        """Accuracy should be rounded to 2 decimal places."""
        vocab = [
            _make_vocab("hola", "hello", times_seen=3, times_correct=1),
        ]
        strengths = service.get_category_strengths("es", vocab)

        strength_map = {cs.category: cs for cs in strengths}
        greetings = strength_map["greetings"]

        # 1/3 = 0.3333... -> 0.33
        assert greetings.accuracy == 0.33

    def test_returns_all_language_categories(
        self, service: AdaptiveService,
    ) -> None:
        """Should return a CategoryStrength for every category in the language."""
        strengths = service.get_category_strengths("es", [])
        categories = {cs.category for cs in strengths}

        for cat in CATEGORIES:
            assert cat in categories


# =============================================================================
# _compute_level_readiness Tests
# =============================================================================


class TestLevelReadiness:
    """Tests for AdaptiveService._compute_level_readiness."""

    def test_returns_none_for_unsupported_language(
        self, service: AdaptiveService,
    ) -> None:
        """Should return None when language has no path (e.g. 'jp')."""
        result = service._compute_level_readiness("jp", [])
        assert result is None

    def test_no_completions_first_level(
        self, service: AdaptiveService,
    ) -> None:
        """With no completions, should report first level at 0% readiness."""
        result = service._compute_level_readiness("es", [])

        assert result is not None
        assert result.current_level == "A0"
        assert result.completed_in_level == 0
        assert result.total_in_level == 5  # 5 categories
        assert result.readiness_pct == 0.0
        assert result.is_ready is False
        assert result.next_level == "A1"

    def test_partial_completion(
        self, service: AdaptiveService,
    ) -> None:
        """Partial completion should show correct counts and percentage."""
        completed = [
            _make_lesson_progress("greetings-001"),
            _make_lesson_progress("introductions-001"),
        ]
        result = service._compute_level_readiness("es", completed)

        assert result is not None
        assert result.current_level == "A0"
        assert result.completed_in_level == 2
        assert result.total_in_level == 5
        assert result.readiness_pct == 40.0
        assert result.is_ready is False

    def test_full_level_complete_all_shared_ids(
        self, service: AdaptiveService,
    ) -> None:
        """When all category IDs are completed (shared across levels), all units complete.

        Because all levels reference the same base lesson IDs (greetings-001, etc.),
        completing those 5 IDs marks every level as complete. The PathService then
        reports the last unit (B1) as the current unit.
        """
        completed = [_make_lesson_progress(f"{cat}-001") for cat in CATEGORIES]
        result = service._compute_level_readiness("es", completed)

        assert result is not None
        # All units are complete, so current_unit_index is len(units)-1 = B1
        assert result.current_level == "B1"
        assert result.completed_in_level == 5
        assert result.total_in_level == 5
        assert result.is_ready is True
        assert result.next_level is None  # B1 is the last level

    def test_all_levels_complete_is_ready(
        self, service: AdaptiveService,
    ) -> None:
        """When all levels are complete, is_ready should be True."""
        completed = [_make_lesson_progress(f"{cat}-001") for cat in CATEGORIES]

        result = service._compute_level_readiness("es", completed)

        assert result is not None
        assert result.is_ready is True

    def test_last_level_has_no_next(
        self, service: AdaptiveService,
    ) -> None:
        """When on the last level (B1), next_level should be None."""
        completed = [_make_lesson_progress(f"{cat}-001") for cat in CATEGORIES]

        result = service._compute_level_readiness("es", completed)

        assert result is not None
        assert result.next_level is None


# =============================================================================
# get_daily_recommendation Tests
# =============================================================================


class TestDailyRecommendation:
    """Tests for AdaptiveService.get_daily_recommendation."""

    def test_recommendation_with_empty_data(
        self, service: AdaptiveService,
    ) -> None:
        """Should return a valid recommendation even with no user data."""
        rec = service.get_daily_recommendation("es", [], [], 0)

        assert isinstance(rec, DailyRecommendation)
        assert rec.next_lesson is not None  # First lesson in path
        assert rec.review_due_count == 0
        assert rec.weak_categories == []
        assert rec.level_readiness is not None
        assert len(rec.suggestion_text) > 0

    def test_includes_review_count(
        self, service: AdaptiveService,
    ) -> None:
        """Recommendation should carry through the review_due_count."""
        rec = service.get_daily_recommendation("es", [], [], 5)

        assert rec.review_due_count == 5

    def test_includes_weak_categories(
        self, service: AdaptiveService,
    ) -> None:
        """Recommendation should include categories with is_weak=True."""
        vocab = [
            _make_vocab("hola", "hello", times_seen=10, times_correct=3),
            _make_vocab("adios", "goodbye", times_seen=10, times_correct=2),
        ]
        rec = service.get_daily_recommendation("es", [], vocab, 0)

        weak_cats = [wc.category for wc in rec.weak_categories]
        assert "greetings" in weak_cats

    def test_excludes_strong_categories(
        self, service: AdaptiveService,
    ) -> None:
        """Recommendation should not include categories with is_weak=False."""
        vocab = [
            _make_vocab("hola", "hello", times_seen=10, times_correct=9),
        ]
        rec = service.get_daily_recommendation("es", [], vocab, 0)

        weak_cats = [wc.category for wc in rec.weak_categories]
        assert "greetings" not in weak_cats

    def test_includes_next_lesson(
        self, service: AdaptiveService,
    ) -> None:
        """Recommendation should include the next lesson from the path."""
        rec = service.get_daily_recommendation("es", [], [], 0)

        assert rec.next_lesson is not None
        assert rec.next_lesson.metadata.language == "es"

    def test_next_lesson_none_when_all_complete(
        self, service: AdaptiveService,
    ) -> None:
        """When all lessons are complete, next_lesson should be None."""
        completed = [_make_lesson_progress(f"{cat}-001") for cat in CATEGORIES]
        rec = service.get_daily_recommendation("es", completed, [], 0)

        assert rec.next_lesson is None

    def test_includes_level_readiness(
        self, service: AdaptiveService,
    ) -> None:
        """Recommendation should include level readiness information."""
        rec = service.get_daily_recommendation("es", [], [], 0)

        assert rec.level_readiness is not None
        assert isinstance(rec.level_readiness, LevelReadiness)

    def test_suggestion_text_mentions_review(
        self, service: AdaptiveService,
    ) -> None:
        """suggestion_text should mention review when review_due_count > 0."""
        rec = service.get_daily_recommendation("es", [], [], 3)

        assert "3 words ready for review" in rec.suggestion_text

    def test_suggestion_text_singular_word_review(
        self, service: AdaptiveService,
    ) -> None:
        """suggestion_text should use 'word' (singular) when review_due_count == 1."""
        rec = service.get_daily_recommendation("es", [], [], 1)

        assert "1 word ready for review" in rec.suggestion_text

    def test_suggestion_text_mentions_weak_categories(
        self, service: AdaptiveService,
    ) -> None:
        """suggestion_text should mention weak categories by display name."""
        vocab = [
            _make_vocab("hola", "hello", times_seen=10, times_correct=3),
        ]
        rec = service.get_daily_recommendation("es", [], vocab, 0)

        assert "Greetings" in rec.suggestion_text
        assert "could use some practice" in rec.suggestion_text

    def test_suggestion_text_ready_for_next_level(
        self, service: AdaptiveService,
    ) -> None:
        """suggestion_text should mention level readiness when level complete.

        NOTE: In this test fixture all levels share the same lesson IDs, so
        completing all IDs completes all levels. The last level (B1) has no
        next_level, so the 'ready for' branch does not fire. This test verifies
        the suggestion text is still non-empty in that scenario.
        """
        completed = [_make_lesson_progress(f"{cat}-001") for cat in CATEGORIES]
        rec = service.get_daily_recommendation("es", completed, [], 0)

        assert len(rec.suggestion_text) > 0

    def test_suggestion_text_continue_with_lesson(
        self, service: AdaptiveService,
    ) -> None:
        """suggestion_text should mention the next lesson title."""
        rec = service.get_daily_recommendation("es", [], [], 0)

        assert "Continue with" in rec.suggestion_text
        assert "to keep your streak going" in rec.suggestion_text

    def test_suggestion_text_default_when_nothing_applies(
        self, service: AdaptiveService,
    ) -> None:
        """suggestion_text should show default when no signals are available."""
        # Complete everything, no reviews, no weak categories
        completed = [_make_lesson_progress(f"{cat}-001") for cat in CATEGORIES]
        rec = service.get_daily_recommendation("es", completed, [], 0)

        # All levels done (B1 is last, next_level=None), no reviews, no weak cats.
        # Falls through to default message.
        assert "Great job" in rec.suggestion_text

    def test_unsupported_language_returns_recommendation(
        self, service: AdaptiveService,
    ) -> None:
        """Should handle unsupported language gracefully."""
        rec = service.get_daily_recommendation("jp", [], [], 0)

        assert isinstance(rec, DailyRecommendation)
        assert rec.next_lesson is None
        assert rec.level_readiness is None


# =============================================================================
# _build_suggestion Tests
# =============================================================================


class TestBuildSuggestion:
    """Tests for AdaptiveService._build_suggestion static method."""

    def test_empty_inputs_returns_default(self) -> None:
        """With no signals, should return default encouragement."""
        result = AdaptiveService._build_suggestion(
            next_lesson=None,
            review_due_count=0,
            weak_categories=[],
            level_readiness=None,
        )
        assert result == "Great job! Keep exploring to discover new vocabulary."

    def test_only_review_due(self) -> None:
        """Should mention review count when reviews are due."""
        result = AdaptiveService._build_suggestion(
            next_lesson=None,
            review_due_count=5,
            weak_categories=[],
            level_readiness=None,
        )
        assert "5 words ready for review" in result

    def test_singular_word_review(self) -> None:
        """Should use 'word' (singular) for review_due_count == 1."""
        result = AdaptiveService._build_suggestion(
            next_lesson=None,
            review_due_count=1,
            weak_categories=[],
            level_readiness=None,
        )
        assert "1 word ready for review" in result
        assert "words" not in result

    def test_only_weak_categories(self) -> None:
        """Should mention weak category names for practice."""
        weak = [
            CategoryStrength(
                category="greetings", total_words=5, words_seen=3, accuracy=0.4, is_weak=True,
            ),
        ]
        result = AdaptiveService._build_suggestion(
            next_lesson=None,
            review_due_count=0,
            weak_categories=weak,
            level_readiness=None,
        )
        assert "Greetings" in result
        assert "could use some practice" in result

    def test_two_weak_categories_joined_with_and(self) -> None:
        """Should join two weak category display names with 'and'."""
        weak = [
            CategoryStrength(
                category="greetings", total_words=5, words_seen=3, accuracy=0.4, is_weak=True,
            ),
            CategoryStrength(
                category="numbers", total_words=5, words_seen=3, accuracy=0.3, is_weak=True,
            ),
        ]
        result = AdaptiveService._build_suggestion(
            next_lesson=None,
            review_due_count=0,
            weak_categories=weak,
            level_readiness=None,
        )
        assert "Greetings and Numbers" in result

    def test_max_two_weak_categories_shown(self) -> None:
        """Should show at most 2 weak categories even if more exist."""
        weak = [
            CategoryStrength(
                category="greetings", total_words=5, words_seen=3, accuracy=0.4, is_weak=True,
            ),
            CategoryStrength(
                category="numbers", total_words=5, words_seen=3, accuracy=0.3, is_weak=True,
            ),
            CategoryStrength(
                category="colors", total_words=5, words_seen=3, accuracy=0.2, is_weak=True,
            ),
        ]
        result = AdaptiveService._build_suggestion(
            next_lesson=None,
            review_due_count=0,
            weak_categories=weak,
            level_readiness=None,
        )
        # Colors (3rd category) should not appear
        assert "Colors" not in result

    def test_level_ready_with_next_level(self) -> None:
        """Should mention level completion and next level when ready."""
        readiness = LevelReadiness(
            current_level="A0",
            completed_in_level=5,
            total_in_level=5,
            readiness_pct=100.0,
            is_ready=True,
            next_level="A1",
        )
        result = AdaptiveService._build_suggestion(
            next_lesson=None,
            review_due_count=0,
            weak_categories=[],
            level_readiness=readiness,
        )
        assert "completed A0" in result
        assert "ready for A1" in result

    def test_level_ready_without_next_level(self, lesson_service: LessonService) -> None:
        """When level is ready but no next level, should not mention readiness."""
        readiness = LevelReadiness(
            current_level="B1",
            completed_in_level=5,
            total_in_level=5,
            readiness_pct=100.0,
            is_ready=True,
            next_level=None,
        )
        # Provide a next_lesson so the elif branch fires
        lesson = lesson_service.get_lesson("greetings-001")
        result = AdaptiveService._build_suggestion(
            next_lesson=lesson,
            review_due_count=0,
            weak_categories=[],
            level_readiness=readiness,
        )
        assert "ready for" not in result
        assert "Continue with" in result

    def test_next_lesson_when_not_level_ready(self, lesson_service: LessonService) -> None:
        """Should mention lesson title when a next lesson exists."""
        lesson = lesson_service.get_lesson("greetings-001")
        assert lesson is not None

        result = AdaptiveService._build_suggestion(
            next_lesson=lesson,
            review_due_count=0,
            weak_categories=[],
            level_readiness=None,
        )
        assert f'Continue with "{lesson.metadata.title}"' in result
        assert "to keep your streak going" in result

    def test_level_ready_takes_priority_over_next_lesson(
        self, lesson_service: LessonService,
    ) -> None:
        """Level readiness message should appear instead of next lesson."""
        readiness = LevelReadiness(
            current_level="A0",
            completed_in_level=5,
            total_in_level=5,
            readiness_pct=100.0,
            is_ready=True,
            next_level="A1",
        )
        lesson = lesson_service.get_lesson("greetings-001")
        result = AdaptiveService._build_suggestion(
            next_lesson=lesson,
            review_due_count=0,
            weak_categories=[],
            level_readiness=readiness,
        )
        assert "ready for A1" in result
        assert "Continue with" not in result

    def test_combined_review_and_weak_and_lesson(
        self, lesson_service: LessonService,
    ) -> None:
        """All parts should appear together when multiple signals present."""
        weak = [
            CategoryStrength(
                category="greetings", total_words=5, words_seen=3, accuracy=0.4, is_weak=True,
            ),
        ]
        lesson = lesson_service.get_lesson("greetings-001")
        result = AdaptiveService._build_suggestion(
            next_lesson=lesson,
            review_due_count=3,
            weak_categories=weak,
            level_readiness=None,
        )
        assert "3 words ready for review" in result
        assert "Greetings" in result
        assert "could use some practice" in result
        assert "Continue with" in result

    def test_unknown_category_uses_slug_as_display(self) -> None:
        """Categories not in CATEGORY_DISPLAY should fall back to slug."""
        weak = [
            CategoryStrength(
                category="unknown_cat", total_words=5, words_seen=3, accuracy=0.4, is_weak=True,
            ),
        ]
        result = AdaptiveService._build_suggestion(
            next_lesson=None,
            review_due_count=0,
            weak_categories=weak,
            level_readiness=None,
        )
        assert "unknown_cat" in result

    def test_not_ready_level_does_not_trigger_message(self) -> None:
        """Level readiness with is_ready=False should not produce readiness text."""
        readiness = LevelReadiness(
            current_level="A0",
            completed_in_level=2,
            total_in_level=5,
            readiness_pct=40.0,
            is_ready=False,
            next_level="A1",
        )
        result = AdaptiveService._build_suggestion(
            next_lesson=None,
            review_due_count=0,
            weak_categories=[],
            level_readiness=readiness,
        )
        assert "ready for" not in result
        # Falls through to default
        assert "Great job" in result
