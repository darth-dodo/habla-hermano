"""
Tests for the review LangGraph nodes.

This module tests the spaced repetition review nodes:
- _pick_question_type: Question type selection by CEFR level
- _strip_accents: Accent mark removal for comparison
- _levenshtein_distance: Edit distance calculation
- _infer_quality_score: SM-2 quality score inference
- generate_question_node: LLM-powered question generation
- evaluate_answer_node: Answer evaluation with LLM feedback
- update_sm2_node: SM-2 scheduling persistence
"""

from __future__ import annotations

import inspect
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from postgrest.exceptions import APIError

from src.agent.nodes.review import (
    _infer_quality_score,
    _levenshtein_distance,
    _pick_question_type,
    _strip_accents,
    evaluate_answer_node,
    generate_question_node,
    update_sm2_node,
)
from src.agent.review_state import ReviewState

# =============================================================================
# Helper: ReviewState factory
# =============================================================================


def _make_review_state(**overrides: Any) -> ReviewState:
    """Build a minimal ReviewState dict with sensible defaults.

    Any key can be overridden via keyword arguments.
    """
    base: dict[str, Any] = {
        "user_id": "test-user-abc",
        "language": "es",
        "level": "A1",
        "words_to_review": [
            {"id": 1, "word": "hola", "translation": "hello"},
            {"id": 2, "word": "gracias", "translation": "thank you"},
        ],
        "current_word_index": 0,
        "session_size": 2,
        "results": [],
    }
    base.update(overrides)
    return base  # type: ignore[return-value]


# =============================================================================
# _pick_question_type
# =============================================================================


class TestPickQuestionType:
    """Tests for _pick_question_type level-based selection."""

    VALID_TYPES: ClassVar[set[str]] = {"translate", "fill_blank", "recognize"}

    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    def test_returns_valid_type_for_all_levels(self, level: str) -> None:
        """_pick_question_type should always return a valid question type."""
        result = _pick_question_type(level)
        assert result in self.VALID_TYPES

    def test_a0_returns_valid_type(self) -> None:
        """A0 level should return one of the three valid question types."""
        # Run multiple times to exercise randomness
        results = {_pick_question_type("A0") for _ in range(200)}
        assert results.issubset(self.VALID_TYPES)

    def test_a0_favors_translate_and_recognize(self) -> None:
        """A0 should heavily favor translate and recognize over fill_blank.

        With weights {translate: 0.45, recognize: 0.45, fill_blank: 0.10},
        fill_blank should appear far less often than the other two.
        """
        counts: dict[str, int] = {"translate": 0, "recognize": 0, "fill_blank": 0}
        trials = 2000
        for _ in range(trials):
            counts[_pick_question_type("A0")] += 1

        # fill_blank has 10% weight, so it should be well under 20% of trials
        assert counts["fill_blank"] < trials * 0.20
        # translate + recognize have 90% weight combined
        assert counts["translate"] + counts["recognize"] > trials * 0.70

    def test_a1_same_weights_as_a0(self) -> None:
        """A1 uses the same beginner weights as A0."""
        counts: dict[str, int] = {"translate": 0, "recognize": 0, "fill_blank": 0}
        trials = 2000
        for _ in range(trials):
            counts[_pick_question_type("A1")] += 1

        assert counts["fill_blank"] < trials * 0.20

    def test_a2_includes_more_fill_blank(self) -> None:
        """A2 (higher level) should produce fill_blank more often than A0/A1.

        With weights {translate: 0.35, recognize: 0.30, fill_blank: 0.35},
        fill_blank should appear roughly 35% of the time.
        """
        counts: dict[str, int] = {"translate": 0, "recognize": 0, "fill_blank": 0}
        trials = 2000
        for _ in range(trials):
            counts[_pick_question_type("A2")] += 1

        # fill_blank has 35% weight, should be above 20%
        assert counts["fill_blank"] > trials * 0.20

    def test_b1_includes_more_fill_blank(self) -> None:
        """B1 should have similarly higher fill_blank weight as A2."""
        counts: dict[str, int] = {"translate": 0, "recognize": 0, "fill_blank": 0}
        trials = 2000
        for _ in range(trials):
            counts[_pick_question_type("B1")] += 1

        assert counts["fill_blank"] > trials * 0.20

    def test_unknown_level_uses_higher_weights(self) -> None:
        """Unknown levels should fall through to the else branch (higher weights)."""
        result = _pick_question_type("C2")
        assert result in self.VALID_TYPES

    @pytest.mark.parametrize("level", ["", "X9", "beginner", "advanced"])
    def test_arbitrary_level_strings(self, level: str) -> None:
        """Arbitrary non-standard level strings should not crash."""
        result = _pick_question_type(level)
        assert result in self.VALID_TYPES

    def test_deterministic_with_seeded_random(self) -> None:
        """With a seeded random, results should be reproducible."""
        import random

        random.seed(42)
        result1 = _pick_question_type("A1")
        random.seed(42)
        result2 = _pick_question_type("A1")
        assert result1 == result2


# =============================================================================
# _strip_accents
# =============================================================================


class TestStripAccents:
    """Tests for _strip_accents accent removal."""

    def test_removes_acute_accents_on_vowels(self) -> None:
        """Should replace accented vowels with plain equivalents."""
        assert _strip_accents("cafe") == "cafe"
        assert _strip_accents("cafe") == "cafe"

    @pytest.mark.parametrize(
        ("input_str", "expected"),
        [
            ("cafe", "cafe"),
            ("hola", "hola"),
            ("adios", "adios"),
            ("", ""),
        ],
    )
    def test_strings_without_accents_unchanged(self, input_str: str, expected: str) -> None:
        """Strings without accents should pass through unchanged."""
        assert _strip_accents(input_str) == expected

    def test_empty_string(self) -> None:
        """Empty string should return empty string."""
        assert _strip_accents("") == ""

    def test_removes_ene(self) -> None:
        """Should replace n-tilde with plain n."""
        assert _strip_accents("espanol") == "espanol"
        assert _strip_accents("nino") == "nino"

    def test_removes_ene_actual(self) -> None:
        """Should replace actual n-tilde character."""
        assert _strip_accents("\u00f1") == "n"
        assert _strip_accents("espa\u00f1ol") == "espanol"

    def test_removes_umlaut_u(self) -> None:
        """Should replace u-umlaut with plain u."""
        assert _strip_accents("\u00fc") == "u"
        assert _strip_accents("ping\u00fcino") == "pinguino"

    def test_removes_umlaut_a_and_o(self) -> None:
        """Should replace German umlauts a and o."""
        assert _strip_accents("\u00e4") == "a"
        assert _strip_accents("\u00f6") == "o"

    def test_all_spanish_accented_vowels(self) -> None:
        """Should handle all five Spanish accented vowels."""
        assert _strip_accents("\u00e1") == "a"
        assert _strip_accents("\u00e9") == "e"
        assert _strip_accents("\u00ed") == "i"
        assert _strip_accents("\u00f3") == "o"
        assert _strip_accents("\u00fa") == "u"

    def test_cafe_with_accent(self) -> None:
        """Classic test: 'cafe' with accent -> 'cafe'."""
        assert _strip_accents("caf\u00e9") == "cafe"

    def test_multiple_accents_in_one_word(self) -> None:
        """Should handle multiple accents in a single word."""
        # "accion" with accents on a and o
        assert _strip_accents("\u00e1cci\u00f3n") == "accion"

    def test_preserves_non_accent_characters(self) -> None:
        """Non-accent special characters should be preserved."""
        assert _strip_accents("hello!") == "hello!"
        assert _strip_accents("test 123") == "test 123"
        assert _strip_accents("a-b_c") == "a-b_c"


# =============================================================================
# _levenshtein_distance
# =============================================================================


class TestLevenshteinDistance:
    """Tests for _levenshtein_distance edit distance calculation."""

    def test_same_strings_zero_distance(self) -> None:
        """Identical strings should have distance 0."""
        assert _levenshtein_distance("hello", "hello") == 0

    def test_empty_vs_empty(self) -> None:
        """Two empty strings should have distance 0."""
        assert _levenshtein_distance("", "") == 0

    def test_empty_vs_nonempty(self) -> None:
        """Empty vs non-empty should equal length of non-empty string."""
        assert _levenshtein_distance("", "hello") == 5
        assert _levenshtein_distance("abc", "") == 3

    def test_single_char_difference(self) -> None:
        """One substitution should give distance 1."""
        assert _levenshtein_distance("cat", "bat") == 1

    def test_single_insertion(self) -> None:
        """One insertion should give distance 1."""
        assert _levenshtein_distance("cat", "cats") == 1

    def test_single_deletion(self) -> None:
        """One deletion should give distance 1."""
        assert _levenshtein_distance("cats", "cat") == 1

    def test_complete_mismatch_same_length(self) -> None:
        """Completely different strings of same length."""
        assert _levenshtein_distance("abc", "xyz") == 3

    def test_complete_mismatch_different_length(self) -> None:
        """Completely different strings of different lengths."""
        assert _levenshtein_distance("ab", "xyz") == 3

    def test_symmetry(self) -> None:
        """Distance should be symmetric: d(a,b) == d(b,a)."""
        assert _levenshtein_distance("kitten", "sitting") == _levenshtein_distance(
            "sitting", "kitten"
        )

    def test_classic_kitten_sitting(self) -> None:
        """Classic Levenshtein example: kitten -> sitting = 3."""
        assert _levenshtein_distance("kitten", "sitting") == 3

    def test_single_characters(self) -> None:
        """Single character strings."""
        assert _levenshtein_distance("a", "a") == 0
        assert _levenshtein_distance("a", "b") == 1

    @pytest.mark.parametrize(
        ("s1", "s2", "expected"),
        [
            ("hola", "hola", 0),
            ("hola", "hole", 1),
            ("hola", "holaa", 1),
            ("gracias", "gracia", 1),
            ("", "test", 4),
        ],
    )
    def test_parametrized_distances(self, s1: str, s2: str, expected: int) -> None:
        """Parametrized distance calculations."""
        assert _levenshtein_distance(s1, s2) == expected


# =============================================================================
# _infer_quality_score
# =============================================================================


class TestInferQualityScore:
    """Tests for _infer_quality_score SM-2 quality inference."""

    # --- Score 0: empty / skip ---

    @pytest.mark.parametrize("user_answer", ["", "  ", "skip", "?", "idk", "i don't know"])
    def test_empty_or_skip_returns_zero(self, user_answer: str) -> None:
        """Empty or skip answers should return quality 0."""
        assert _infer_quality_score(user_answer, "hola") == 0

    def test_whitespace_only_returns_zero(self) -> None:
        """Whitespace-only answers should return quality 0."""
        assert _infer_quality_score("   ", "hola") == 0

    # --- Score 5: exact match ---

    def test_exact_match_returns_five(self) -> None:
        """Exact match (case-insensitive) should return quality 5."""
        assert _infer_quality_score("hola", "hola") == 5

    def test_exact_match_case_insensitive(self) -> None:
        """Exact match should be case-insensitive."""
        assert _infer_quality_score("Hola", "hola") == 5
        assert _infer_quality_score("HOLA", "hola") == 5

    def test_exact_match_with_whitespace(self) -> None:
        """Leading/trailing whitespace should be stripped before comparison."""
        assert _infer_quality_score("  hola  ", "hola") == 5
        assert _infer_quality_score("hola", "  hola  ") == 5

    # --- Score 4: match without accents ---

    def test_accent_mismatch_returns_four(self) -> None:
        """Answer matching without accents should return quality 4."""
        assert _infer_quality_score("cafe", "caf\u00e9") == 4

    def test_missing_ene_returns_four(self) -> None:
        """Missing tilde on n should return quality 4."""
        assert _infer_quality_score("espanol", "espa\u00f1ol") == 4

    def test_missing_umlaut_returns_four(self) -> None:
        """Missing umlaut should return quality 4."""
        assert _infer_quality_score("uber", "\u00fcber") == 4

    # --- Score 4: close match for short words (distance <= 1, length <= 4) ---

    def test_short_word_one_char_off_returns_four(self) -> None:
        """Short word (<=4 chars) with 1 edit distance should return 4."""
        # "hola" vs "holx" -> distance 1, length 4
        assert _infer_quality_score("holx", "hola") == 4

    # --- Score 3: medium distance ---

    def test_medium_distance_returns_three(self) -> None:
        """Moderate edit distance should return quality 3.

        For words <=8 chars, distance <=2 should be 3.
        """
        # "gracias" (7 chars) vs "gracis" (6 chars) -> distance 1 after accent strip
        # Both have no accents so stripped versions are the same.
        # "gracis" vs "gracias" = distance 1 (one deletion).
        # word_length = 7, distance = 1 -> hits the (<=8 and <=2) branch -> quality 3
        assert _infer_quality_score("gracis", "gracias") == 3

    def test_longer_word_distance_three(self) -> None:
        """Longer word with distance 3 should return quality 3."""
        # "restaurante" (11 chars) with 3 edits
        assert _infer_quality_score("restarante", "restaurante") == 3

    # --- Score 2: contains match ---

    def test_contains_correct_answer_returns_two(self) -> None:
        """If user answer contains the correct answer, should return 2."""
        # "it means hola right" contains "hola"
        assert _infer_quality_score("it means hola right", "hola") == 2

    def test_correct_answer_contains_user_answer(self) -> None:
        """If correct answer contains the user answer, should return 2.

        This happens when user gives a partial answer.
        """
        # "buenos" is contained in "buenos dias"
        assert _infer_quality_score("buenos", "buenos dias") == 2

    # --- Score 1: no match ---

    def test_no_match_returns_one(self) -> None:
        """Completely wrong answer should return quality 1."""
        assert _infer_quality_score("perro", "gato") == 1

    def test_very_different_long_words_returns_one(self) -> None:
        """Very different long words with high distance should return 1."""
        assert _infer_quality_score("absolutely", "restaurante") == 1

    # --- Edge cases ---

    def test_both_empty_returns_zero(self) -> None:
        """Both empty should return 0 (user answer is empty -> skip)."""
        assert _infer_quality_score("", "") == 0

    def test_score_range_always_0_to_5(self) -> None:
        """Quality score should always be in range [0, 5]."""
        test_pairs = [
            ("", "anything"),
            ("skip", "word"),
            ("exact", "exact"),
            ("cafe", "caf\u00e9"),
            ("holx", "hola"),
            ("gracis", "gracias"),
            ("it means hola", "hola"),
            ("wrong", "right"),
        ]
        for user, correct in test_pairs:
            score = _infer_quality_score(user, correct)
            assert 0 <= score <= 5, f"Score {score} out of range for ({user!r}, {correct!r})"


# =============================================================================
# generate_question_node (async, mocked LLM)
# =============================================================================


class TestGenerateQuestionNode:
    """Tests for generate_question_node async function."""

    def test_is_async(self) -> None:
        """generate_question_node should be an async function."""
        assert inspect.iscoroutinefunction(generate_question_node)

    @pytest.mark.asyncio
    async def test_returns_dict_with_expected_keys(self) -> None:
        """Should return dict with current_word, question_type, question_text."""
        mock_response = MagicMock()
        mock_response.content = "How do you say 'hello' in Spanish?"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state()

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await generate_question_node(state)

        assert "current_word" in result
        assert "question_type" in result
        assert "question_text" in result

    @pytest.mark.asyncio
    async def test_current_word_from_index(self) -> None:
        """Should pick the word at the current_word_index."""
        mock_response = MagicMock()
        mock_response.content = "What does 'gracias' mean?"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        words = [
            {"id": 1, "word": "hola", "translation": "hello"},
            {"id": 2, "word": "gracias", "translation": "thank you"},
        ]
        state = _make_review_state(words_to_review=words, current_word_index=1)

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await generate_question_node(state)

        assert result["current_word"] == words[1]

    @pytest.mark.asyncio
    async def test_question_type_is_valid(self) -> None:
        """Should return a valid question type."""
        mock_response = MagicMock()
        mock_response.content = "Translate 'hello'."

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state()

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await generate_question_node(state)

        assert result["question_type"] in {"translate", "fill_blank", "recognize"}

    @pytest.mark.asyncio
    async def test_question_text_from_llm(self) -> None:
        """question_text should come from the LLM response content."""
        expected_text = "Quick one - how do you say 'hello' in Spanish?"
        mock_response = MagicMock()
        mock_response.content = expected_text

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state()

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await generate_question_node(state)

        assert result["question_text"] == expected_text

    @pytest.mark.asyncio
    async def test_index_beyond_words_returns_none(self) -> None:
        """When current_word_index >= len(words), should return None values."""
        state = _make_review_state(current_word_index=5)

        # No LLM call needed - should short-circuit
        result = await generate_question_node(state)

        assert result["current_word"] is None
        assert result["question_type"] is None
        assert result["question_text"] is None

    @pytest.mark.asyncio
    async def test_empty_words_list_returns_none(self) -> None:
        """Empty words_to_review with index 0 should return None values."""
        state = _make_review_state(words_to_review=[], current_word_index=0)

        result = await generate_question_node(state)

        assert result["current_word"] is None
        assert result["question_type"] is None
        assert result["question_text"] is None

    @pytest.mark.asyncio
    async def test_llm_invoked_with_messages(self) -> None:
        """Should call llm.ainvoke with SystemMessage and HumanMessage."""
        mock_response = MagicMock()
        mock_response.content = "Question text"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state()

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            await generate_question_node(state)

        mock_llm.ainvoke.assert_called_once()
        call_args = mock_llm.ainvoke.call_args[0][0]
        assert len(call_args) == 2
        # First message should be SystemMessage with the prompt
        assert call_args[0].__class__.__name__ == "SystemMessage"
        # Second message should be HumanMessage
        assert call_args[1].__class__.__name__ == "HumanMessage"

    @pytest.mark.asyncio
    async def test_uses_correct_language_name(self) -> None:
        """Should look up language name from LANGUAGE_ADAPTER."""
        mock_response = MagicMock()
        mock_response.content = "Question"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state(language="de")

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            await generate_question_node(state)

        # Verify the prompt contains the German language name
        call_args = mock_llm.ainvoke.call_args[0][0]
        system_content = call_args[0].content
        assert "German" in system_content

    @pytest.mark.asyncio
    async def test_handles_unknown_language_gracefully(self) -> None:
        """Unknown language code should fall back to Spanish."""
        mock_response = MagicMock()
        mock_response.content = "Question"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state(language="xx")

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            await generate_question_node(state)

        call_args = mock_llm.ainvoke.call_args[0][0]
        system_content = call_args[0].content
        assert "Spanish" in system_content

    @pytest.mark.asyncio
    async def test_llm_exception_propagates(self) -> None:
        """LLM exceptions should propagate (no try/except in generate_question_node)."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("API Error"))

        state = _make_review_state()

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            with pytest.raises(Exception, match="API Error"):
                await generate_question_node(state)

    @pytest.mark.asyncio
    async def test_llm_timeout_propagates(self) -> None:
        """Timeout errors should propagate from generate_question_node."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=TimeoutError("LLM timeout"))

        state = _make_review_state()

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            with pytest.raises(TimeoutError):
                await generate_question_node(state)


# =============================================================================
# evaluate_answer_node (async, mocked LLM)
# =============================================================================


class TestEvaluateAnswerNode:
    """Tests for evaluate_answer_node async function."""

    def test_is_async(self) -> None:
        """evaluate_answer_node should be an async function."""
        assert inspect.iscoroutinefunction(evaluate_answer_node)

    @pytest.mark.asyncio
    async def test_returns_dict_with_expected_keys(self) -> None:
        """Should return dict with quality_score, feedback_text, results."""
        mock_response = MagicMock()
        mock_response.content = "Great job!"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="hola",
            question_type="translate",
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await evaluate_answer_node(state)

        assert "quality_score" in result
        assert "feedback_text" in result
        assert "results" in result

    @pytest.mark.asyncio
    async def test_correct_answer_returns_high_quality(self) -> None:
        """Exact correct answer should yield quality_score >= 4."""
        mock_response = MagicMock()
        mock_response.content = "Perfect!"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="hola",
            question_type="translate",
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await evaluate_answer_node(state)

        assert result["quality_score"] == 5

    @pytest.mark.asyncio
    async def test_recognize_type_checks_translation(self) -> None:
        """For 'recognize' questions, correct answer should be the English translation."""
        mock_response = MagicMock()
        mock_response.content = "Correct!"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="hello",
            question_type="recognize",
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await evaluate_answer_node(state)

        assert result["quality_score"] == 5

    @pytest.mark.asyncio
    async def test_translate_type_checks_target_word(self) -> None:
        """For 'translate' questions, correct answer should be the target language word."""
        mock_response = MagicMock()
        mock_response.content = "Correct!"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="hola",
            question_type="translate",
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await evaluate_answer_node(state)

        assert result["quality_score"] == 5

    @pytest.mark.asyncio
    async def test_fill_blank_type_checks_target_word(self) -> None:
        """For 'fill_blank' questions, correct answer should be the target language word."""
        mock_response = MagicMock()
        mock_response.content = "Correct!"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="hola",
            question_type="fill_blank",
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await evaluate_answer_node(state)

        assert result["quality_score"] == 5

    @pytest.mark.asyncio
    async def test_wrong_answer_returns_low_quality(self) -> None:
        """Completely wrong answer should yield quality_score <= 1."""
        mock_response = MagicMock()
        mock_response.content = "Not quite."

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="perro",
            question_type="translate",
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await evaluate_answer_node(state)

        assert result["quality_score"] == 1

    @pytest.mark.asyncio
    async def test_empty_answer_returns_zero_quality(self) -> None:
        """Empty user_answer should yield quality_score 0."""
        mock_response = MagicMock()
        mock_response.content = "Let's try again."

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="",
            question_type="translate",
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await evaluate_answer_node(state)

        assert result["quality_score"] == 0

    @pytest.mark.asyncio
    async def test_no_current_word_returns_none(self) -> None:
        """When current_word is missing/None, should return None values."""
        state = _make_review_state(user_answer="hola")
        # We explicitly set it to None
        state_dict: dict[str, Any] = dict(state)
        state_dict["current_word"] = None
        state_typed: ReviewState = state_dict  # type: ignore[assignment]

        result = await evaluate_answer_node(state_typed)

        assert result["quality_score"] is None
        assert result["feedback_text"] is None

    @pytest.mark.asyncio
    async def test_results_list_appended(self) -> None:
        """Should append a new result to the existing results list."""
        mock_response = MagicMock()
        mock_response.content = "Good job!"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        existing_results = [{"word_id": 99, "quality": 5, "correct": True}]
        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="hola",
            question_type="translate",
            results=existing_results,
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await evaluate_answer_node(state)

        assert len(result["results"]) == 2
        assert result["results"][0] == existing_results[0]
        assert result["results"][1]["word_id"] == 1
        assert result["results"][1]["quality"] == 5
        assert result["results"][1]["correct"] is True

    @pytest.mark.asyncio
    async def test_results_correct_flag_for_quality_3_or_above(self) -> None:
        """Quality >= 3 should be marked as correct=True."""
        mock_response = MagicMock()
        mock_response.content = "Close enough!"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        # "gracis" vs "gracias" -> distance 1, length 7 (<=8) -> quality 3
        state = _make_review_state(
            current_word={"id": 1, "word": "gracias", "translation": "thank you"},
            user_answer="gracis",
            question_type="translate",
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await evaluate_answer_node(state)

        assert result["quality_score"] == 3
        assert result["results"][-1]["correct"] is True

    @pytest.mark.asyncio
    async def test_results_correct_flag_for_quality_below_3(self) -> None:
        """Quality < 3 should be marked as correct=False."""
        mock_response = MagicMock()
        mock_response.content = "Not this time."

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="perro",
            question_type="translate",
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await evaluate_answer_node(state)

        assert result["quality_score"] <= 2
        assert result["results"][-1]["correct"] is False

    @pytest.mark.asyncio
    async def test_feedback_type_correct_for_quality_4_or_above(self) -> None:
        """Quality >= 4 should use the 'correct' feedback prompt."""
        mock_response = MagicMock()
        mock_response.content = "Amazing!"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="hola",
            question_type="translate",
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            await evaluate_answer_node(state)

        call_args = mock_llm.ainvoke.call_args[0][0]
        system_content = call_args[0].content
        assert "celebrating" in system_content.lower() or "correct" in system_content.lower()

    @pytest.mark.asyncio
    async def test_feedback_type_almost_for_quality_2_3(self) -> None:
        """Quality 2-3 should use the 'almost' feedback prompt."""
        mock_response = MagicMock()
        mock_response.content = "Almost!"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        # "it means hola right" contains "hola" -> quality 2
        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="it means hola right",
            question_type="translate",
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            await evaluate_answer_node(state)

        call_args = mock_llm.ainvoke.call_args[0][0]
        system_content = call_args[0].content
        assert "gentle correction" in system_content.lower() or "close" in system_content.lower()

    @pytest.mark.asyncio
    async def test_feedback_type_incorrect_for_quality_below_2(self) -> None:
        """Quality 0-1 should use the 'incorrect' feedback prompt."""
        mock_response = MagicMock()
        mock_response.content = "No worries!"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="perro",
            question_type="translate",
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            await evaluate_answer_node(state)

        call_args = mock_llm.ainvoke.call_args[0][0]
        system_content = call_args[0].content
        assert "miss" in system_content.lower() or "helping after" in system_content.lower()

    @pytest.mark.asyncio
    async def test_feedback_text_from_llm(self) -> None:
        """feedback_text should come from the LLM response content."""
        expected_feedback = "Perfecto! You nailed it!"
        mock_response = MagicMock()
        mock_response.content = expected_feedback

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="hola",
            question_type="translate",
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await evaluate_answer_node(state)

        assert result["feedback_text"] == expected_feedback

    @pytest.mark.asyncio
    async def test_default_user_answer_empty_string(self) -> None:
        """Missing user_answer should default to empty string."""
        mock_response = MagicMock()
        mock_response.content = "Try again."

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            question_type="translate",
            # user_answer intentionally omitted
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await evaluate_answer_node(state)

        assert result["quality_score"] == 0

    @pytest.mark.asyncio
    async def test_default_question_type_translate(self) -> None:
        """Missing question_type should default to 'translate'."""
        mock_response = MagicMock()
        mock_response.content = "Feedback"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="hola",
            # question_type intentionally omitted
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await evaluate_answer_node(state)

        # Default question_type is "translate", so correct_answer = word ("hola")
        assert result["quality_score"] == 5

    @pytest.mark.asyncio
    async def test_llm_exception_propagates(self) -> None:
        """LLM exceptions should propagate from evaluate_answer_node."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM Error"))

        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="hola",
            question_type="translate",
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            with pytest.raises(Exception, match="LLM Error"):
                await evaluate_answer_node(state)

    @pytest.mark.asyncio
    async def test_llm_timeout_propagates(self) -> None:
        """Timeout errors should propagate from evaluate_answer_node."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=TimeoutError("Timeout"))

        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="hola",
            question_type="translate",
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            with pytest.raises(TimeoutError):
                await evaluate_answer_node(state)

    @pytest.mark.asyncio
    async def test_does_not_mutate_original_results(self) -> None:
        """Should not mutate the original results list from state."""
        mock_response = MagicMock()
        mock_response.content = "Feedback"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        original_results: list[dict[str, object]] = [{"word_id": 99, "quality": 5, "correct": True}]
        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            user_answer="hola",
            question_type="translate",
            results=original_results,
        )

        with patch("src.agent.nodes.review.get_llm", return_value=mock_llm):
            result = await evaluate_answer_node(state)

        # Original should not have been mutated
        assert len(original_results) == 1
        # New results should have 2 entries
        assert len(result["results"]) == 2


# =============================================================================
# update_sm2_node (async, mocked ReviewService)
# =============================================================================


class TestUpdateSm2Node:
    """Tests for update_sm2_node async function.

    Note: update_sm2_node uses state.get("supabase_client") to get the
    user-scoped Supabase client, and does a lazy import of ReviewService.
    We pass the mock client through state and patch ReviewService.
    """

    def test_is_async(self) -> None:
        """update_sm2_node should be an async function."""
        assert inspect.iscoroutinefunction(update_sm2_node)

    @pytest.mark.asyncio
    async def test_increments_current_word_index(self) -> None:
        """Should always increment current_word_index by 1."""
        mock_client = MagicMock()
        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            quality_score=5,
            current_word_index=0,
            supabase_client=mock_client,
        )

        with patch("src.services.review.ReviewService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service_cls.return_value = mock_service

            result = await update_sm2_node(state)

        assert result["current_word_index"] == 1

    @pytest.mark.asyncio
    async def test_increments_from_nonzero_index(self) -> None:
        """Should increment from whatever the current index is."""
        mock_client = MagicMock()
        state = _make_review_state(
            current_word={"id": 2, "word": "gracias", "translation": "thank you"},
            quality_score=4,
            current_word_index=3,
            supabase_client=mock_client,
        )

        with patch("src.services.review.ReviewService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service_cls.return_value = mock_service

            result = await update_sm2_node(state)

        assert result["current_word_index"] == 4

    @pytest.mark.asyncio
    async def test_calls_review_service_update_sm2(self) -> None:
        """Should call ReviewService.update_sm2 with correct args."""
        mock_client = MagicMock()
        state = _make_review_state(
            current_word={"id": 42, "word": "hola", "translation": "hello"},
            quality_score=5,
            supabase_client=mock_client,
        )

        with patch("src.services.review.ReviewService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service_cls.return_value = mock_service

            await update_sm2_node(state)

        mock_service.update_sm2.assert_called_once_with(vocab_id=42, quality=5)

    @pytest.mark.asyncio
    async def test_creates_service_with_user_id_and_user_client(self) -> None:
        """Should create ReviewService with the user_id and user-scoped client."""
        mock_user_client = MagicMock()
        state = _make_review_state(
            user_id="user-xyz-789",
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            quality_score=5,
            supabase_client=mock_user_client,
        )

        with patch("src.services.review.ReviewService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service_cls.return_value = mock_service

            await update_sm2_node(state)

        mock_service_cls.assert_called_once_with("user-xyz-789", client=mock_user_client)

    @pytest.mark.asyncio
    async def test_handles_missing_current_word(self) -> None:
        """When current_word is None, should skip update and still increment index."""
        state = _make_review_state(quality_score=5, current_word_index=2)
        # Ensure current_word is not set
        state_dict: dict[str, Any] = dict(state)
        state_dict.pop("current_word", None)
        state_typed: ReviewState = state_dict  # type: ignore[assignment]

        result = await update_sm2_node(state_typed)

        assert result["current_word_index"] == 3

    @pytest.mark.asyncio
    async def test_handles_missing_quality_score(self) -> None:
        """When quality_score is None, should skip update and still increment index."""
        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            current_word_index=1,
        )
        # quality_score not set

        result = await update_sm2_node(state)

        assert result["current_word_index"] == 2

    @pytest.mark.asyncio
    async def test_handles_missing_word_id(self) -> None:
        """When current_word has no 'id', should skip update and still increment."""
        state = _make_review_state(
            current_word={"word": "hola", "translation": "hello"},
            quality_score=5,
            current_word_index=0,
        )

        result = await update_sm2_node(state)

        assert result["current_word_index"] == 1

    @pytest.mark.asyncio
    async def test_service_exception_does_not_crash(self) -> None:
        """If ReviewService.update_sm2 raises, should log warning and continue."""
        mock_client = MagicMock()
        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            quality_score=5,
            current_word_index=0,
            supabase_client=mock_client,
        )

        with patch("src.services.review.ReviewService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.update_sm2.side_effect = APIError(
                {"code": "500", "message": "Database error", "hint": None, "details": None}
            )
            mock_service_cls.return_value = mock_service

            # Should not raise
            result = await update_sm2_node(state)

        # Index should still be incremented despite the error
        assert result["current_word_index"] == 1

    @pytest.mark.asyncio
    async def test_none_supabase_client_still_works(self) -> None:
        """If supabase_client is None, ReviewService should be created with None client."""
        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            quality_score=5,
            current_word_index=0,
            # No supabase_client - defaults to None
        )

        with patch("src.services.review.ReviewService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service_cls.return_value = mock_service

            result = await update_sm2_node(state)

        # Service should be created with None client
        mock_service_cls.assert_called_once_with("test-user-abc", client=None)
        assert result["current_word_index"] == 1

    @pytest.mark.asyncio
    async def test_word_id_converted_to_int(self) -> None:
        """word_id should be converted to int even if stored as string."""
        mock_client = MagicMock()
        state = _make_review_state(
            current_word={"id": "42", "word": "hola", "translation": "hello"},
            quality_score=5,
            supabase_client=mock_client,
        )

        with patch("src.services.review.ReviewService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service_cls.return_value = mock_service

            await update_sm2_node(state)

        mock_service.update_sm2.assert_called_once_with(vocab_id=42, quality=5)

    @pytest.mark.asyncio
    async def test_only_returns_current_word_index(self) -> None:
        """Return dict should only contain current_word_index."""
        mock_client = MagicMock()
        state = _make_review_state(
            current_word={"id": 1, "word": "hola", "translation": "hello"},
            quality_score=5,
            current_word_index=0,
            supabase_client=mock_client,
        )

        with patch("src.services.review.ReviewService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service_cls.return_value = mock_service

            result = await update_sm2_node(state)

        assert list(result.keys()) == ["current_word_index"]


# =============================================================================
# get_llm helper (creative profile)
# =============================================================================


class TestGetLlm:
    """Tests for get_llm with creative profile."""

    def test_creates_chat_anthropic(self) -> None:
        """get_llm('creative') should create a ChatAnthropic instance with correct params."""
        from src.api.config import Settings

        mock_settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-review-key",  # pragma: allowlist secret
            LLM_MODEL="claude-test-model",
            LLM_TEMPERATURE=0.5,
        )

        with patch("src.config.get_settings", return_value=mock_settings):
            with patch("src.agent.llm.ChatAnthropic") as mock_chat:
                mock_chat.return_value = MagicMock()
                from src.agent.llm import get_llm

                get_llm("creative")

                mock_chat.assert_called_once()
                call_kwargs = mock_chat.call_args[1]
                assert call_kwargs["model"] == "claude-test-model"
                assert call_kwargs["temperature"] == 0.7
                assert call_kwargs["max_tokens"] == 512


# =============================================================================
# ReviewState TypedDict integration
# =============================================================================


class TestReviewStateTypedDict:
    """Tests verifying ReviewState TypedDict fields."""

    def test_review_state_importable(self) -> None:
        """ReviewState should be importable."""
        from src.agent.review_state import ReviewState as RS

        assert RS is not None

    def test_review_state_required_fields(self) -> None:
        """ReviewState should have the expected required fields."""
        from typing import get_type_hints

        hints = get_type_hints(ReviewState, include_extras=True)
        required_fields = {
            "user_id",
            "language",
            "level",
            "words_to_review",
            "current_word_index",
            "session_size",
            "results",
        }
        for field in required_fields:
            assert field in hints, f"Missing required field: {field}"

    def test_review_state_optional_fields(self) -> None:
        """ReviewState should have NotRequired optional fields."""
        from typing import get_type_hints

        hints = get_type_hints(ReviewState, include_extras=True)
        optional_fields = {
            "current_word",
            "question_type",
            "question_text",
            "user_answer",
            "quality_score",
            "feedback_text",
        }
        for field in optional_fields:
            assert field in hints, f"Missing optional field: {field}"


# =============================================================================
# Integration-style tests (combining multiple functions)
# =============================================================================


class TestQualityScoreIntegration:
    """Integration tests combining _strip_accents, _levenshtein_distance,
    and _infer_quality_score to verify the full scoring pipeline."""

    @pytest.mark.parametrize(
        ("user_answer", "correct_answer", "min_score", "max_score"),
        [
            # Exact match
            ("hola", "hola", 5, 5),
            # Case difference only
            ("HOLA", "hola", 5, 5),
            # Accent difference
            ("cafe", "caf\u00e9", 4, 4),
            ("espanol", "espa\u00f1ol", 4, 4),
            # Skip
            ("skip", "hola", 0, 0),
            ("?", "anything", 0, 0),
            # Wrong
            ("xyz", "hola", 1, 1),
        ],
    )
    def test_scoring_pipeline(
        self,
        user_answer: str,
        correct_answer: str,
        min_score: int,
        max_score: int,
    ) -> None:
        """Verify quality scores fall in expected ranges for various inputs."""
        score = _infer_quality_score(user_answer, correct_answer)
        assert min_score <= score <= max_score, (
            f"Score {score} not in [{min_score}, {max_score}] "
            f"for ({user_answer!r}, {correct_answer!r})"
        )

    def test_strip_accents_feeds_into_quality_score(self) -> None:
        """Verify that accent stripping is used internally by _infer_quality_score."""
        # These should match after accent stripping -> quality 4
        score = _infer_quality_score("adios", "adi\u00f3s")
        assert score == 4

    def test_levenshtein_feeds_into_quality_score(self) -> None:
        """Verify that edit distance is used for fuzzy matching.

        "gracis" vs "gracias": distance is 1 (one 'a' insertion), word_length is 7.
        With word_length <= 8 and distance <= 2, this triggers quality 3.
        """
        distance = _levenshtein_distance("gracis", "gracias")
        assert distance == 1

        score = _infer_quality_score("gracis", "gracias")
        assert score == 3
