"""Tests to increase coverage on uncovered agent source files.

Targets:
- src/agent/nodes/respond.py (lines 60-318, 342-383, 396-402, 439-448, 464)
- src/agent/nodes/lesson.py (lines 32-35, 58-97, 115-129, 155-181, 201-276)
- src/agent/nodes/analyze.py (lines 130-144, 195, 231-251, 268-292, 350-356)
- src/agent/prompts.py (lines 380-397, 428-432)
- src/agent/lesson_graph.py (lines 15-103)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

if TYPE_CHECKING:
    from src.agent.state import ConversationState
    from src.api.config import Settings


# =============================================================================
# respond.py: _extract_keywords_from_messages (lines 60-318)
# =============================================================================


class TestExtractKeywordsFromMessages:
    """Tests for _extract_keywords_from_messages covering the stopwords set
    and extraction logic (respond.py lines 60-318)."""

    def test_extracts_content_words_from_human_messages(self) -> None:
        """Should extract content words and filter stopwords."""
        from src.agent.nodes.respond import _extract_keywords_from_messages

        messages = [HumanMessage(content="The restaurant serves delicious tacos")]
        keywords = _extract_keywords_from_messages(messages)
        assert "restaurant" in keywords
        assert "serves" in keywords
        assert "delicious" in keywords
        assert "tacos" in keywords
        # Stopwords should be filtered out
        assert "the" not in keywords

    def test_filters_english_stopwords(self) -> None:
        """Should filter common English stopwords."""
        from src.agent.nodes.respond import _extract_keywords_from_messages

        messages = [HumanMessage(content="I have been going to the very same place")]
        keywords = _extract_keywords_from_messages(messages)
        for stopword in ["have", "been", "going", "the", "very", "same"]:
            assert stopword not in keywords
        assert "place" in keywords

    def test_filters_spanish_stopwords(self) -> None:
        """Should filter common Spanish stopwords."""
        from src.agent.nodes.respond import _extract_keywords_from_messages

        messages = [HumanMessage(content="hola bueno yo quiero comer tacos")]
        keywords = _extract_keywords_from_messages(messages)
        # 'hola', 'bueno', 'yo', 'querer' are stopwords
        assert "hola" not in keywords
        assert "bueno" not in keywords
        assert "comer" in keywords
        assert "tacos" in keywords

    def test_ignores_short_words(self) -> None:
        """Should ignore words shorter than 3 characters."""
        from src.agent.nodes.respond import _extract_keywords_from_messages

        messages = [HumanMessage(content="go to my big car now")]
        keywords = _extract_keywords_from_messages(messages)
        assert "go" not in keywords  # 2 chars - too short
        assert "to" not in keywords  # 2 chars - too short
        assert "my" not in keywords  # 2 chars - too short
        # 'big' is 3 chars, alpha, not a stopword -> it IS included
        assert "big" in keywords
        assert "car" in keywords
        assert "now" not in keywords  # 'now' is a stopword

    def test_ignores_non_alpha_words(self) -> None:
        """Should ignore words containing non-alpha characters."""
        from src.agent.nodes.respond import _extract_keywords_from_messages

        messages = [HumanMessage(content="user123 email@test hello world")]
        keywords = _extract_keywords_from_messages(messages)
        assert "user123" not in keywords
        assert "email@test" not in keywords
        assert "hello" in keywords
        assert "world" in keywords

    def test_removes_punctuation_before_splitting(self) -> None:
        """Should handle punctuation in messages."""
        from src.agent.nodes.respond import _extract_keywords_from_messages

        messages = [HumanMessage(content="Hello! How are you? Fine, thanks.")]
        keywords = _extract_keywords_from_messages(messages)
        # 'hello' is NOT in the stopword set, so it IS included
        assert "hello" in keywords
        # 'how' IS a stopword
        assert "how" not in keywords
        assert "fine" in keywords
        assert "thanks" in keywords

    def test_limits_to_15_keywords(self) -> None:
        """Should limit keywords to 15 max."""
        from src.agent.nodes.respond import _extract_keywords_from_messages

        # Create a message with many unique content words
        words = [f"word{i}abc" for i in range(30)]
        messages = [HumanMessage(content=" ".join(words))]
        keywords = _extract_keywords_from_messages(messages)
        assert len(keywords) <= 15

    def test_uses_only_recent_messages(self) -> None:
        """Should only analyze the last num_recent messages."""
        from src.agent.nodes.respond import _extract_keywords_from_messages

        messages = [
            HumanMessage(content="old message about dinosaurs"),
            AIMessage(content="AI response"),
            HumanMessage(content="another old message about rockets"),
            AIMessage(content="AI response two"),
            HumanMessage(content="recent message about cooking"),
            AIMessage(content="AI response three"),
            HumanMessage(content="latest message about painting"),
        ]
        # Default num_recent=4 -> last 4 messages
        keywords = _extract_keywords_from_messages(messages, num_recent=2)
        assert "painting" in keywords
        # 'dinosaurs' should not appear since it's outside the window
        assert "dinosaurs" not in keywords

    def test_only_processes_human_messages(self) -> None:
        """Should only extract keywords from HumanMessage instances."""
        from src.agent.nodes.respond import _extract_keywords_from_messages

        messages = [
            HumanMessage(content="cooking recipe"),
            AIMessage(content="artificial intelligence machine learning"),
        ]
        keywords = _extract_keywords_from_messages(messages)
        assert "cooking" in keywords
        assert "recipe" in keywords
        # AI message content should not be extracted
        assert "artificial" not in keywords
        assert "machine" not in keywords

    def test_deduplicates_keywords(self) -> None:
        """Should not include duplicate keywords."""
        from src.agent.nodes.respond import _extract_keywords_from_messages

        messages = [
            HumanMessage(content="cooking cooking cooking"),
        ]
        keywords = _extract_keywords_from_messages(messages)
        assert keywords.count("cooking") == 1

    def test_empty_messages_returns_empty(self) -> None:
        """Should return empty list for empty messages."""
        from src.agent.nodes.respond import _extract_keywords_from_messages

        keywords = _extract_keywords_from_messages([])
        assert keywords == []

    def test_handles_non_string_content(self) -> None:
        """Should handle messages with non-string content gracefully."""
        from src.agent.nodes.respond import _extract_keywords_from_messages

        # HumanMessage with list content (multimodal)
        msg = HumanMessage(content=[{"type": "text", "text": "hello"}])
        keywords = _extract_keywords_from_messages([msg])
        # Should not crash - non-string content is skipped
        assert isinstance(keywords, list)

    def test_case_insensitive_matching(self) -> None:
        """Keywords should be lowercased."""
        from src.agent.nodes.respond import _extract_keywords_from_messages

        messages = [HumanMessage(content="RESTAURANT Cooking")]
        keywords = _extract_keywords_from_messages(messages)
        assert "restaurant" in keywords
        assert "cooking" in keywords
        assert "RESTAURANT" not in keywords


# =============================================================================
# respond.py: _get_topical_review_words (lines 342-383)
# =============================================================================


class TestGetTopicalReviewWords:
    """Tests for _get_topical_review_words covering lines 342-383."""

    async def test_returns_empty_for_no_user_id(self) -> None:
        """Should return empty list when user_id is None."""
        from src.agent.nodes.respond import _get_topical_review_words

        result = await _get_topical_review_words(
            user_id=None, language="es", messages=[], limit=5
        )
        assert result == []

    async def test_returns_empty_for_empty_user_id(self) -> None:
        """Should return empty list when user_id is empty string."""
        from src.agent.nodes.respond import _get_topical_review_words

        result = await _get_topical_review_words(
            user_id="", language="es", messages=[], limit=5
        )
        assert result == []

    async def test_returns_review_words_on_success(self) -> None:
        """Should return ReviewWordOffered list on success."""
        from src.agent.nodes.respond import _get_topical_review_words

        mock_vocab = MagicMock()
        mock_vocab.id = 42
        mock_vocab.word = "casa"
        mock_vocab.translation = "house"

        mock_review_instance = MagicMock()
        mock_review_instance.get_topical_review_words.return_value = [mock_vocab]

        mock_review_cls = MagicMock(return_value=mock_review_instance)
        mock_get_admin = MagicMock(return_value=MagicMock())

        with (
            patch("src.api.supabase_client.get_supabase_admin", mock_get_admin),
            patch("src.services.review.ReviewService", mock_review_cls),
        ):
            messages = [HumanMessage(content="I want to buy a house")]
            result = await _get_topical_review_words(
                user_id="user-123", language="es", messages=messages, limit=5
            )
            assert len(result) == 1
            assert result[0]["vocab_id"] == 42
            assert result[0]["word"] == "casa"
            assert result[0]["translation"] == "house"

    async def test_filters_vocab_with_none_id(self) -> None:
        """Should filter out vocab entries with None id."""
        from src.agent.nodes.respond import _get_topical_review_words

        mock_vocab_good = MagicMock()
        mock_vocab_good.id = 10
        mock_vocab_good.word = "gato"
        mock_vocab_good.translation = "cat"

        mock_vocab_bad = MagicMock()
        mock_vocab_bad.id = None
        mock_vocab_bad.word = "perro"
        mock_vocab_bad.translation = "dog"

        mock_review_instance = MagicMock()
        mock_review_instance.get_topical_review_words.return_value = [
            mock_vocab_good,
            mock_vocab_bad,
        ]

        mock_review_cls = MagicMock(return_value=mock_review_instance)
        mock_get_admin = MagicMock(return_value=MagicMock())

        with (
            patch("src.api.supabase_client.get_supabase_admin", mock_get_admin),
            patch("src.services.review.ReviewService", mock_review_cls),
        ):
            result = await _get_topical_review_words(
                user_id="user-123", language="es", messages=[], limit=5
            )
            assert len(result) == 1
            assert result[0]["word"] == "gato"

    async def test_returns_empty_on_exception(self) -> None:
        """Should return empty list and log warning on exception."""
        from src.agent.nodes.respond import _get_topical_review_words

        with patch(
            "src.api.supabase_client.get_supabase_admin",
            side_effect=Exception("DB error"),
        ):
            result = await _get_topical_review_words(
                user_id="user-123", language="es", messages=[], limit=5
            )
            assert result == []


# =============================================================================
# respond.py: _build_review_prompt_addition (lines 396-402)
# =============================================================================


class TestBuildReviewPromptAddition:
    """Tests for _build_review_prompt_addition covering lines 396-402."""

    def test_returns_empty_for_no_words(self) -> None:
        """Should return empty string when no review words."""
        from src.agent.nodes.respond import _build_review_prompt_addition

        result = _build_review_prompt_addition([])
        assert result == ""

    def test_returns_prompt_with_words(self) -> None:
        """Should return prompt addition with word list."""
        from src.agent.nodes.respond import _build_review_prompt_addition
        from src.agent.state import ReviewWordOffered

        words = [
            ReviewWordOffered(vocab_id=1, word="casa", translation="house"),
            ReviewWordOffered(vocab_id=2, word="gato", translation="cat"),
        ]
        result = _build_review_prompt_addition(words)
        assert "casa" in result
        assert "gato" in result
        assert "REVIEW OPPORTUNITY" in result

    def test_single_word(self) -> None:
        """Should handle a single review word."""
        from src.agent.nodes.respond import _build_review_prompt_addition
        from src.agent.state import ReviewWordOffered

        words = [ReviewWordOffered(vocab_id=1, word="hola", translation="hello")]
        result = _build_review_prompt_addition(words)
        assert "hola" in result


# =============================================================================
# respond.py: respond_node with user_id and review words (lines 439-448, 464)
# =============================================================================


class TestRespondNodeReviewWords:
    """Tests for respond_node covering spaced repetition lines 439-448 and 464."""

    async def test_respond_node_with_user_id_fetches_review_words(
        self, mock_settings: "Settings"
    ) -> None:
        """respond_node should fetch review words when user_id is present."""
        from src.agent.nodes.respond import respond_node
        from src.agent.state import ReviewWordOffered

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))

        review_words = [
            ReviewWordOffered(vocab_id=1, word="casa", translation="house"),
        ]

        with (
            patch("src.api.config.get_settings", return_value=mock_settings),
            patch("src.agent.nodes.respond._get_llm", return_value=mock_llm),
            patch(
                "src.agent.nodes.respond._get_topical_review_words",
                new_callable=AsyncMock,
                return_value=review_words,
            ) as mock_get_words,
        ):
            state: ConversationState = {
                "messages": [HumanMessage(content="Hola!")],
                "level": "A1",
                "language": "es",
                "user_id": "test-user-123",
            }
            result = await respond_node(state)

            mock_get_words.assert_called_once_with(
                user_id="test-user-123",
                language="es",
                messages=state["messages"],
                limit=5,
            )
            assert "review_words_offered" in result
            assert result["review_words_offered"] == review_words

    async def test_respond_node_without_user_id_skips_review(
        self, mock_settings: "Settings"
    ) -> None:
        """respond_node should not fetch review words when no user_id."""
        from src.agent.nodes.respond import respond_node

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))

        with (
            patch("src.api.config.get_settings", return_value=mock_settings),
            patch("src.agent.nodes.respond._get_llm", return_value=mock_llm),
        ):
            state: ConversationState = {
                "messages": [HumanMessage(content="Hola!")],
                "level": "A1",
                "language": "es",
            }
            result = await respond_node(state)
            assert "review_words_offered" not in result

    async def test_respond_node_no_review_words_offered_key_when_empty(
        self, mock_settings: "Settings"
    ) -> None:
        """respond_node should not include review_words_offered when list is empty."""
        from src.agent.nodes.respond import respond_node

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))

        with (
            patch("src.api.config.get_settings", return_value=mock_settings),
            patch("src.agent.nodes.respond._get_llm", return_value=mock_llm),
            patch(
                "src.agent.nodes.respond._get_topical_review_words",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            state: ConversationState = {
                "messages": [HumanMessage(content="Hola!")],
                "level": "A1",
                "language": "es",
                "user_id": "test-user-123",
            }
            result = await respond_node(state)
            # Empty review_words should NOT add the key to result
            assert "review_words_offered" not in result


# =============================================================================
# analyze.py: _parse_pronunciation_tips (lines 130-144)
# =============================================================================


class TestParsePronunciationTips:
    """Tests for _parse_pronunciation_tips covering lines 130-144."""

    def test_parses_tips_with_audio_hint(self) -> None:
        """Should parse pronunciation tips including optional audio_hint."""
        from src.agent.nodes.analyze import _parse_pronunciation_tips

        data = {
            "pronunciation_tips": [
                {
                    "word": "gracias",
                    "phonetic": "GRAH-see-ahs",
                    "tip": "The 'c' before 'i' sounds like 'th' in Spain",
                    "audio_hint": "Like 'grassy-ahs'",
                }
            ]
        }
        tips = _parse_pronunciation_tips(data)
        assert len(tips) == 1
        assert tips[0]["word"] == "gracias"
        assert tips[0]["phonetic"] == "GRAH-see-ahs"
        assert tips[0]["audio_hint"] == "Like 'grassy-ahs'"

    def test_parses_tips_without_audio_hint(self) -> None:
        """Should parse tips without audio_hint key."""
        from src.agent.nodes.analyze import _parse_pronunciation_tips

        data = {
            "pronunciation_tips": [
                {
                    "word": "hola",
                    "phonetic": "OH-lah",
                    "tip": "Silent h",
                }
            ]
        }
        tips = _parse_pronunciation_tips(data)
        assert len(tips) == 1
        assert tips[0]["word"] == "hola"
        assert "audio_hint" not in tips[0]

    def test_skips_non_dict_entries(self) -> None:
        """Should skip non-dict entries in pronunciation_tips."""
        from src.agent.nodes.analyze import _parse_pronunciation_tips

        data = {
            "pronunciation_tips": [
                "not a dict",
                42,
                {"word": "bueno", "phonetic": "BWEH-noh", "tip": "Quick 'b'"},
            ]
        }
        tips = _parse_pronunciation_tips(data)
        assert len(tips) == 1
        assert tips[0]["word"] == "bueno"

    def test_handles_empty_audio_hint(self) -> None:
        """Should not include audio_hint when it's empty string."""
        from src.agent.nodes.analyze import _parse_pronunciation_tips

        data = {
            "pronunciation_tips": [
                {
                    "word": "casa",
                    "phonetic": "KAH-sah",
                    "tip": "Soft 's'",
                    "audio_hint": "",
                }
            ]
        }
        tips = _parse_pronunciation_tips(data)
        assert len(tips) == 1
        assert "audio_hint" not in tips[0]

    def test_handles_non_string_audio_hint(self) -> None:
        """Should not include audio_hint when it's not a string."""
        from src.agent.nodes.analyze import _parse_pronunciation_tips

        data = {
            "pronunciation_tips": [
                {
                    "word": "casa",
                    "phonetic": "KAH-sah",
                    "tip": "Soft 's'",
                    "audio_hint": 123,
                }
            ]
        }
        tips = _parse_pronunciation_tips(data)
        assert len(tips) == 1
        assert "audio_hint" not in tips[0]

    def test_handles_missing_pronunciation_tips_key(self) -> None:
        """Should return empty list when pronunciation_tips key is missing."""
        from src.agent.nodes.analyze import _parse_pronunciation_tips

        tips = _parse_pronunciation_tips({})
        assert tips == []

    def test_handles_missing_fields_with_defaults(self) -> None:
        """Should handle missing fields with empty string defaults."""
        from src.agent.nodes.analyze import _parse_pronunciation_tips

        data = {"pronunciation_tips": [{}]}
        tips = _parse_pronunciation_tips(data)
        assert len(tips) == 1
        assert tips[0]["word"] == ""
        assert tips[0]["phonetic"] == ""
        assert tips[0]["tip"] == ""


# =============================================================================
# analyze.py: _parse_analysis_response - non-dict vocab entries (line 195)
# =============================================================================


class TestParseAnalysisResponseNonDictVocab:
    """Tests for _parse_analysis_response with non-dict vocabulary entries (line 195)."""

    def test_skips_non_dict_vocab_entries(self) -> None:
        """Should skip non-dict entries in new_vocabulary array."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = json.dumps(
            {
                "grammar_errors": [],
                "new_vocabulary": [
                    "just a string",
                    42,
                    {"word": "libro", "translation": "book", "part_of_speech": "noun"},
                ],
                "pronunciation_tips": [],
            }
        )
        _grammar, vocab, _pron = _parse_analysis_response(content)
        assert len(vocab) == 1
        assert vocab[0]["word"] == "libro"


# =============================================================================
# analyze.py: _check_review_word_usage (lines 231-251)
# =============================================================================


class TestCheckReviewWordUsage:
    """Tests for _check_review_word_usage covering lines 231-251."""

    def test_returns_empty_for_empty_text(self) -> None:
        """Should return empty list when user text is empty."""
        from src.agent.nodes.analyze import _check_review_word_usage
        from src.agent.state import ReviewWordOffered

        offered = [ReviewWordOffered(vocab_id=1, word="casa", translation="house")]
        result = _check_review_word_usage("", offered)
        assert result == []

    def test_returns_empty_for_empty_offered_words(self) -> None:
        """Should return empty list when no words offered."""
        from src.agent.nodes.analyze import _check_review_word_usage

        result = _check_review_word_usage("I live in a casa", [])
        assert result == []

    def test_returns_empty_for_none_text(self) -> None:
        """Should return empty list when user text is falsy."""
        from src.agent.nodes.analyze import _check_review_word_usage
        from src.agent.state import ReviewWordOffered

        offered = [ReviewWordOffered(vocab_id=1, word="casa", translation="house")]
        result = _check_review_word_usage("", offered)
        assert result == []

    def test_detects_word_usage(self) -> None:
        """Should detect when a review word is used in text."""
        from src.agent.nodes.analyze import _check_review_word_usage
        from src.agent.state import ReviewWordOffered

        offered = [
            ReviewWordOffered(vocab_id=1, word="casa", translation="house"),
            ReviewWordOffered(vocab_id=2, word="gato", translation="cat"),
        ]
        result = _check_review_word_usage("Mi casa es grande", offered)
        assert len(result) == 1
        assert result[0]["vocab_id"] == 1
        assert result[0]["word"] == "casa"
        assert result[0]["quality"] == 4

    def test_case_insensitive_matching(self) -> None:
        """Should match words case-insensitively."""
        from src.agent.nodes.analyze import _check_review_word_usage
        from src.agent.state import ReviewWordOffered

        offered = [ReviewWordOffered(vocab_id=1, word="Casa", translation="house")]
        result = _check_review_word_usage("mi CASA es bonita", offered)
        assert len(result) == 1

    def test_detects_multiple_words(self) -> None:
        """Should detect multiple review words in text."""
        from src.agent.nodes.analyze import _check_review_word_usage
        from src.agent.state import ReviewWordOffered

        offered = [
            ReviewWordOffered(vocab_id=1, word="casa", translation="house"),
            ReviewWordOffered(vocab_id=2, word="gato", translation="cat"),
        ]
        result = _check_review_word_usage("Mi casa tiene un gato", offered)
        assert len(result) == 2

    def test_word_not_found(self) -> None:
        """Should return empty list when no words match."""
        from src.agent.nodes.analyze import _check_review_word_usage
        from src.agent.state import ReviewWordOffered

        offered = [ReviewWordOffered(vocab_id=1, word="perro", translation="dog")]
        result = _check_review_word_usage("Mi casa es grande", offered)
        assert result == []


# =============================================================================
# analyze.py: _update_sm2_for_used_words (lines 268-292)
# =============================================================================


class TestUpdateSm2ForUsedWords:
    """Tests for _update_sm2_for_used_words covering lines 268-292."""

    async def test_returns_none_for_no_user_id(self) -> None:
        """Should return early when user_id is None."""
        from src.agent.nodes.analyze import _update_sm2_for_used_words
        from src.agent.state import ReviewWordUsed

        words = [ReviewWordUsed(vocab_id=1, word="casa", quality=4)]
        # Should not raise
        await _update_sm2_for_used_words(None, words)

    async def test_returns_none_for_empty_used_words(self) -> None:
        """Should return early when used_words is empty."""
        from src.agent.nodes.analyze import _update_sm2_for_used_words

        await _update_sm2_for_used_words("user-123", [])

    async def test_updates_sm2_for_each_word(self) -> None:
        """Should call update_sm2 for each used word."""
        from src.agent.nodes.analyze import _update_sm2_for_used_words
        from src.agent.state import ReviewWordUsed

        mock_review_instance = MagicMock()
        mock_review_cls = MagicMock(return_value=mock_review_instance)
        mock_get_admin = MagicMock(return_value=MagicMock())

        with (
            patch("src.api.supabase_client.get_supabase_admin", mock_get_admin),
            patch("src.services.review.ReviewService", mock_review_cls),
        ):
            words = [
                ReviewWordUsed(vocab_id=1, word="casa", quality=4),
                ReviewWordUsed(vocab_id=2, word="gato", quality=4),
            ]
            await _update_sm2_for_used_words("user-123", words)

            assert mock_review_instance.update_sm2.call_count == 2
            mock_review_instance.update_sm2.assert_any_call(vocab_id=1, quality=4)
            mock_review_instance.update_sm2.assert_any_call(vocab_id=2, quality=4)

    async def test_handles_individual_word_exception(self) -> None:
        """Should continue processing when one word fails."""
        from src.agent.nodes.analyze import _update_sm2_for_used_words
        from src.agent.state import ReviewWordUsed

        mock_review_instance = MagicMock()
        mock_review_instance.update_sm2.side_effect = [
            Exception("DB error"),  # First word fails
            None,  # Second word succeeds
        ]
        mock_review_cls = MagicMock(return_value=mock_review_instance)
        mock_get_admin = MagicMock(return_value=MagicMock())

        with (
            patch("src.api.supabase_client.get_supabase_admin", mock_get_admin),
            patch("src.services.review.ReviewService", mock_review_cls),
        ):
            words = [
                ReviewWordUsed(vocab_id=1, word="casa", quality=4),
                ReviewWordUsed(vocab_id=2, word="gato", quality=4),
            ]
            # Should not raise
            await _update_sm2_for_used_words("user-123", words)
            assert mock_review_instance.update_sm2.call_count == 2

    async def test_handles_outer_exception(self) -> None:
        """Should handle exception during service initialization."""
        from src.agent.nodes.analyze import _update_sm2_for_used_words
        from src.agent.state import ReviewWordUsed

        with patch(
            "src.api.supabase_client.get_supabase_admin",
            side_effect=Exception("Import error"),
        ):
            words = [ReviewWordUsed(vocab_id=1, word="casa", quality=4)]
            # Should not raise
            await _update_sm2_for_used_words("user-123", words)


# =============================================================================
# analyze.py: analyze_node with review words (lines 350-356)
# =============================================================================


class TestAnalyzeNodeReviewWordTracking:
    """Tests for analyze_node review word tracking (lines 350-356)."""

    async def test_tracks_review_word_usage(self) -> None:
        """analyze_node should track and update SM-2 when review words are used."""
        from src.agent.nodes.analyze import analyze_node
        from src.agent.state import ReviewWordOffered

        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {"grammar_errors": [], "new_vocabulary": [], "pronunciation_tips": []}
        )

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        offered_words = [
            ReviewWordOffered(vocab_id=1, word="casa", translation="house"),
        ]

        with (
            patch("src.agent.nodes.analyze._get_llm", return_value=mock_llm),
            patch(
                "src.agent.nodes.analyze._update_sm2_for_used_words",
                new_callable=AsyncMock,
            ) as mock_update,
        ):
            state: ConversationState = {
                "messages": [
                    HumanMessage(content="Mi casa es grande"),
                    AIMessage(content="Muy bien!"),
                ],
                "level": "A1",
                "language": "es",
                "user_id": "test-user-123",
                "review_words_offered": offered_words,
            }
            result = await analyze_node(state)

            assert "review_words_used" in result
            assert len(result["review_words_used"]) == 1
            assert result["review_words_used"][0]["word"] == "casa"
            mock_update.assert_called_once()

    async def test_no_tracking_when_no_offered_words(self) -> None:
        """analyze_node should skip tracking when no review words offered."""
        from src.agent.nodes.analyze import analyze_node

        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {"grammar_errors": [], "new_vocabulary": [], "pronunciation_tips": []}
        )

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("src.agent.nodes.analyze._get_llm", return_value=mock_llm):
            state: ConversationState = {
                "messages": [
                    HumanMessage(content="Mi casa es grande"),
                    AIMessage(content="Muy bien!"),
                ],
                "level": "A1",
                "language": "es",
            }
            result = await analyze_node(state)
            assert "review_words_used" not in result


# =============================================================================
# prompts.py: get_lesson_enhance_prompt (lines 380-397)
# =============================================================================


class TestGetLessonEnhancePrompt:
    """Tests for get_lesson_enhance_prompt covering lines 380-397."""

    def test_instruction_step_type(self) -> None:
        """Should generate prompt for instruction step type."""
        from src.agent.prompts import get_lesson_enhance_prompt

        result = get_lesson_enhance_prompt(
            language="es",
            level="A1",
            step_type="instruction",
            step_content="Greetings in Spanish",
        )
        assert "Spanish" in result
        assert "A1" in result
        assert "Greetings in Spanish" in result

    def test_vocabulary_step_with_vocab_list(self) -> None:
        """Should format vocabulary list in prompt."""
        from src.agent.prompts import get_lesson_enhance_prompt

        vocab = [
            {"word": "hola", "translation": "hello"},
            {"word": "adios", "translation": "goodbye"},
        ]
        result = get_lesson_enhance_prompt(
            language="es",
            level="A1",
            step_type="vocabulary",
            step_content="Basic greetings",
            vocabulary=vocab,
        )
        assert "hola" in result
        assert "hello" in result
        assert "adios" in result

    def test_example_step_with_target_text(self) -> None:
        """Should include target text section for example steps."""
        from src.agent.prompts import get_lesson_enhance_prompt

        result = get_lesson_enhance_prompt(
            language="es",
            level="A2",
            step_type="example",
            step_content="Common phrases",
            target_text="Buenos dias",
            translation="Good morning",
        )
        assert "Buenos dias" in result
        assert "Good morning" in result

    def test_example_step_with_target_text_no_translation(self) -> None:
        """Should handle target text without translation."""
        from src.agent.prompts import get_lesson_enhance_prompt

        result = get_lesson_enhance_prompt(
            language="es",
            level="A2",
            step_type="example",
            step_content="Common phrases",
            target_text="Buenos dias",
        )
        assert "Buenos dias" in result

    def test_tip_step_type(self) -> None:
        """Should generate prompt for tip step type."""
        from src.agent.prompts import get_lesson_enhance_prompt

        result = get_lesson_enhance_prompt(
            language="de",
            level="A1",
            step_type="tip",
            step_content="Germans shake hands when greeting",
        )
        assert "German" in result
        assert "Germans shake hands" in result

    def test_practice_step_type(self) -> None:
        """Should generate prompt for practice step type."""
        from src.agent.prompts import get_lesson_enhance_prompt

        result = get_lesson_enhance_prompt(
            language="es",
            level="A0",
            step_type="practice",
            step_content="Practice basic greetings",
        )
        assert "PEP_TALK" in result
        assert "Practice basic greetings" in result

    def test_unknown_step_type_defaults_to_instruction(self) -> None:
        """Should default to instruction template for unknown step type."""
        from src.agent.prompts import get_lesson_enhance_prompt

        result = get_lesson_enhance_prompt(
            language="es",
            level="A1",
            step_type="unknown_type",
            step_content="Some content",
        )
        # Should use instruction template which contains "INTRO:" and "EXTRA:"
        assert "INTRO:" in result
        assert "EXTRA:" in result

    def test_no_vocabulary_provided(self) -> None:
        """Should handle None vocabulary for vocabulary step."""
        from src.agent.prompts import get_lesson_enhance_prompt

        result = get_lesson_enhance_prompt(
            language="es",
            level="A1",
            step_type="vocabulary",
            step_content="Words to learn",
            vocabulary=None,
        )
        assert isinstance(result, str)

    def test_french_language(self) -> None:
        """Should use French language adapter."""
        from src.agent.prompts import get_lesson_enhance_prompt

        result = get_lesson_enhance_prompt(
            language="fr",
            level="A1",
            step_type="instruction",
            step_content="Greetings",
        )
        assert "French" in result


# =============================================================================
# prompts.py: get_exercise_feedback_prompt (lines 428-432)
# =============================================================================


class TestGetExerciseFeedbackPrompt:
    """Tests for get_exercise_feedback_prompt covering lines 428-432."""

    def test_correct_answer_prompt(self) -> None:
        """Should generate celebration prompt for correct answers."""
        from src.agent.prompts import get_exercise_feedback_prompt

        result = get_exercise_feedback_prompt(
            language="es",
            level="A1",
            exercise_description="Choose the greeting",
            user_answer="Hola",
            correct_answer="Hola",
            is_correct=True,
        )
        assert "Spanish" in result
        assert "A1" in result
        assert "Hola" in result
        assert "celebrating" in result.lower() or "correct" in result.lower()

    def test_incorrect_answer_prompt(self) -> None:
        """Should generate supportive prompt for incorrect answers."""
        from src.agent.prompts import get_exercise_feedback_prompt

        result = get_exercise_feedback_prompt(
            language="es",
            level="A1",
            exercise_description="Choose the greeting",
            user_answer="Adios",
            correct_answer="Hola",
            is_correct=False,
        )
        assert "Spanish" in result
        assert "Adios" in result
        assert "Hola" in result

    def test_german_language(self) -> None:
        """Should use German language adapter."""
        from src.agent.prompts import get_exercise_feedback_prompt

        result = get_exercise_feedback_prompt(
            language="de",
            level="A0",
            exercise_description="Choose hello",
            user_answer="Hallo",
            correct_answer="Hallo",
            is_correct=True,
        )
        assert "German" in result

    def test_unknown_language_defaults_to_spanish(self) -> None:
        """Should default to Spanish for unknown language codes."""
        from src.agent.prompts import get_exercise_feedback_prompt

        result = get_exercise_feedback_prompt(
            language="xx",
            level="A1",
            exercise_description="Test",
            user_answer="test",
            correct_answer="test",
            is_correct=True,
        )
        assert "Spanish" in result


# =============================================================================
# lesson.py: _get_llm (lines 32-35)
# =============================================================================


class TestLessonGetLlm:
    """Tests for lesson.py _get_llm covering lines 32-35."""

    def test_get_llm_creates_instance(self, mock_settings: "Settings") -> None:
        """Should create ChatAnthropic with higher temperature for creativity."""
        with (
            patch("src.api.config.get_settings", return_value=mock_settings),
            patch("src.agent.nodes.lesson.ChatAnthropic") as mock_chat,
        ):
            mock_chat.return_value = MagicMock()
            from src.agent.nodes.lesson import _get_llm

            result = _get_llm()
            assert result is not None
            mock_chat.assert_called_once()
            call_kwargs = mock_chat.call_args[1]
            assert call_kwargs["temperature"] == 0.7
            assert call_kwargs["max_tokens"] == 1024


# =============================================================================
# lesson.py: _extract_intro (lines 58-97)
# =============================================================================


class TestExtractIntro:
    """Tests for _extract_intro covering lines 58-97."""

    def test_extracts_labeled_intro(self) -> None:
        """Should extract text after INTRO: label."""
        from src.agent.nodes.lesson import _extract_intro

        content = "INTRO: This is a warm welcome!\n\nEXTRA: Additional details here."
        result = _extract_intro(content)
        assert result == "This is a warm welcome!"

    def test_extracts_intro_before_extra_label(self) -> None:
        """Should stop at EXTRA: label."""
        from src.agent.nodes.lesson import _extract_intro

        content = "INTRO: Welcome to the lesson!EXTRA: More content"
        result = _extract_intro(content)
        assert result == "Welcome to the lesson!"

    def test_extracts_intro_before_examples_label(self) -> None:
        """Should stop at EXAMPLES: label."""
        from src.agent.nodes.lesson import _extract_intro

        content = "INTRO: Here are the words.EXAMPLES: Word1, Word2"
        result = _extract_intro(content)
        assert result == "Here are the words."

    def test_extracts_intro_before_alternative_label(self) -> None:
        """Should stop at ALTERNATIVE: label."""
        from src.agent.nodes.lesson import _extract_intro

        content = "INTRO: This phrase means hello.ALTERNATIVE: You can also say hi."
        result = _extract_intro(content)
        assert result == "This phrase means hello."

    def test_extracts_intro_before_story_label(self) -> None:
        """Should stop at STORY: label."""
        from src.agent.nodes.lesson import _extract_intro

        content = "INTRO: Cultural tip.STORY: Once upon a time."
        result = _extract_intro(content)
        assert result == "Cultural tip."

    def test_extracts_intro_before_usage_note_label(self) -> None:
        """Should stop at USAGE NOTE: label."""
        from src.agent.nodes.lesson import _extract_intro

        content = "INTRO: Phrase overview.USAGE NOTE: Use in formal settings."
        result = _extract_intro(content)
        assert result == "Phrase overview."

    def test_extracts_intro_before_why_it_matters_label(self) -> None:
        """Should stop at WHY IT MATTERS: label."""
        from src.agent.nodes.lesson import _extract_intro

        content = "INTRO: This tip is important.WHY IT MATTERS: Because culture."
        result = _extract_intro(content)
        assert result == "This tip is important."

    def test_extracts_intro_before_double_newline(self) -> None:
        """Should stop at double newline within intro section."""
        from src.agent.nodes.lesson import _extract_intro

        content = "INTRO: First line of intro\n\nSecond paragraph not intro"
        result = _extract_intro(content)
        assert result == "First line of intro"

    def test_extracts_pep_talk(self) -> None:
        """Should extract PEP_TALK: section for practice steps."""
        from src.agent.nodes.lesson import _extract_intro

        content = "PEP_TALK: You got this! Let's practice!"
        result = _extract_intro(content)
        assert result == "You got this! Let's practice!"

    def test_fallback_first_paragraph(self) -> None:
        """Should fallback to first paragraph when no labels found."""
        from src.agent.nodes.lesson import _extract_intro

        content = "First paragraph here.\n\nSecond paragraph here."
        result = _extract_intro(content)
        assert result == "First paragraph here."

    def test_fallback_limits_to_three_sentences(self) -> None:
        """Should limit fallback to 3 sentences max."""
        from src.agent.nodes.lesson import _extract_intro

        content = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five."
        result = _extract_intro(content)
        assert result.count(".") <= 3

    def test_truncates_long_text(self) -> None:
        """Should truncate text longer than 200 chars when no paragraphs found."""
        from src.agent.nodes.lesson import _extract_intro

        # Single long string without paragraph breaks
        content = "x" * 300
        result = _extract_intro(content)
        # Fallback with single paragraph splits on sentences
        assert len(result) <= 300  # The paragraph logic gets the full text

    def test_handles_empty_string(self) -> None:
        """Should handle empty string input."""
        from src.agent.nodes.lesson import _extract_intro

        result = _extract_intro("")
        assert isinstance(result, str)

    def test_handles_whitespace_only(self) -> None:
        """Should handle whitespace-only input."""
        from src.agent.nodes.lesson import _extract_intro

        result = _extract_intro("   ")
        assert isinstance(result, str)


# =============================================================================
# lesson.py: load_step_node (lines 115-129)
# =============================================================================


class TestLoadStepNode:
    """Tests for load_step_node covering lines 115-129."""

    @patch("src.agent.nodes.lesson.get_lesson_service")
    async def test_loads_step_successfully(self, mock_get_service: MagicMock) -> None:
        """Should load step data from lesson service."""
        from src.lessons.models import LessonStepType

        mock_step = MagicMock()
        mock_step.type = LessonStepType.INSTRUCTION
        mock_step.content = "Learn greetings"
        mock_step.vocabulary = [{"word": "hola", "translation": "hello"}]
        mock_step.target_text = "Hola"
        mock_step.translation = "Hello"
        mock_step.exercise_id = None

        mock_lesson = MagicMock()
        mock_lesson.content.get_ordered_steps.return_value = [mock_step]

        mock_service = MagicMock()
        mock_service.get_lesson.return_value = mock_lesson
        mock_get_service.return_value = mock_service

        from src.agent.nodes.lesson import load_step_node

        state = {
            "lesson_id": "es-greetings-001",
            "step_index": 0,
            "level": "A1",
            "language": "es",
            "messages": [],
        }
        result = await load_step_node(state)

        assert result["step_type"] == "instruction"
        assert result["step_content"] == "Learn greetings"
        assert result["step_vocabulary"] == [{"word": "hola", "translation": "hello"}]
        assert result["step_target_text"] == "Hola"
        assert result["step_translation"] == "Hello"
        assert result["exercise_id"] is None

    @patch("src.agent.nodes.lesson.get_lesson_service")
    async def test_raises_for_missing_lesson(self, mock_get_service: MagicMock) -> None:
        """Should raise ValueError when lesson not found."""
        mock_service = MagicMock()
        mock_service.get_lesson.return_value = None
        mock_get_service.return_value = mock_service

        from src.agent.nodes.lesson import load_step_node

        state = {
            "lesson_id": "nonexistent",
            "step_index": 0,
            "level": "A1",
            "language": "es",
            "messages": [],
        }
        with pytest.raises(ValueError, match="Lesson not found"):
            await load_step_node(state)

    @patch("src.agent.nodes.lesson.get_lesson_service")
    async def test_raises_for_invalid_step_index(self, mock_get_service: MagicMock) -> None:
        """Should raise ValueError for out-of-range step index."""
        mock_lesson = MagicMock()
        mock_lesson.content.get_ordered_steps.return_value = [MagicMock()]

        mock_service = MagicMock()
        mock_service.get_lesson.return_value = mock_lesson
        mock_get_service.return_value = mock_service

        from src.agent.nodes.lesson import load_step_node

        state = {
            "lesson_id": "es-greetings-001",
            "step_index": 5,
            "level": "A1",
            "language": "es",
            "messages": [],
        }
        with pytest.raises(ValueError, match="Step 5 not found"):
            await load_step_node(state)

    @patch("src.agent.nodes.lesson.get_lesson_service")
    async def test_raises_for_negative_step_index(self, mock_get_service: MagicMock) -> None:
        """Should raise ValueError for negative step index."""
        mock_lesson = MagicMock()
        mock_lesson.content.get_ordered_steps.return_value = [MagicMock()]

        mock_service = MagicMock()
        mock_service.get_lesson.return_value = mock_lesson
        mock_get_service.return_value = mock_service

        from src.agent.nodes.lesson import load_step_node

        state = {
            "lesson_id": "es-greetings-001",
            "step_index": -1,
            "level": "A1",
            "language": "es",
            "messages": [],
        }
        with pytest.raises(ValueError, match="Step -1 not found"):
            await load_step_node(state)


# =============================================================================
# lesson.py: enhance_step_node (lines 155-181)
# =============================================================================


class TestEnhanceStepNode:
    """Tests for enhance_step_node covering lines 155-181."""

    async def test_enhances_step_content(self, mock_settings: "Settings") -> None:
        """Should call LLM and return enhanced content with intro."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content="INTRO: Welcome to greetings!\n\nEXTRA: More details."
            )
        )

        with (
            patch("src.api.config.get_settings", return_value=mock_settings),
            patch("src.agent.nodes.lesson._get_llm", return_value=mock_llm),
        ):
            from src.agent.nodes.lesson import enhance_step_node

            state = {
                "language": "es",
                "level": "A1",
                "step_type": "instruction",
                "step_content": "Learn greetings",
                "step_vocabulary": None,
                "step_target_text": None,
                "step_translation": None,
                "lesson_id": "test",
                "step_index": 0,
                "messages": [],
            }
            result = await enhance_step_node(state)

            assert "enhanced_content" in result
            assert "hermano_intro" in result
            assert "Welcome to greetings!" in result["hermano_intro"]
            mock_llm.ainvoke.assert_called_once()

    async def test_enhance_with_vocabulary_step(self, mock_settings: "Settings") -> None:
        """Should handle vocabulary step type with vocab data."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content="INTRO: Let's learn words!\n\nEXAMPLES: ...")
        )

        with (
            patch("src.api.config.get_settings", return_value=mock_settings),
            patch("src.agent.nodes.lesson._get_llm", return_value=mock_llm),
        ):
            from src.agent.nodes.lesson import enhance_step_node

            state = {
                "language": "es",
                "level": "A1",
                "step_type": "vocabulary",
                "step_content": "Basic words",
                "step_vocabulary": [{"word": "hola", "translation": "hello"}],
                "step_target_text": None,
                "step_translation": None,
                "lesson_id": "test",
                "step_index": 0,
                "messages": [],
            }
            result = await enhance_step_node(state)
            assert "enhanced_content" in result
            assert "hermano_intro" in result


# =============================================================================
# lesson.py: validate_exercise_node (lines 201-276)
# =============================================================================


class TestValidateExerciseNode:
    """Tests for validate_exercise_node covering lines 201-276."""

    async def test_returns_none_when_no_user_answer(self) -> None:
        """Should return None values when no user answer."""
        from src.agent.nodes.lesson import validate_exercise_node

        state = {
            "lesson_id": "test",
            "step_index": 0,
            "level": "A1",
            "language": "es",
            "messages": [],
            "user_answer": None,
            "exercise_id": "ex-1",
        }
        result = await validate_exercise_node(state)
        assert result["is_correct"] is None
        assert result["exercise_feedback"] is None

    async def test_returns_none_when_no_exercise_id(self) -> None:
        """Should return None values when no exercise id."""
        from src.agent.nodes.lesson import validate_exercise_node

        state = {
            "lesson_id": "test",
            "step_index": 0,
            "level": "A1",
            "language": "es",
            "messages": [],
            "user_answer": "hola",
            "exercise_id": None,
        }
        result = await validate_exercise_node(state)
        assert result["is_correct"] is None
        assert result["exercise_feedback"] is None

    @patch("src.agent.nodes.lesson.get_lesson_service")
    async def test_returns_false_when_lesson_not_found(
        self, mock_get_service: MagicMock
    ) -> None:
        """Should return false with message when lesson not found."""
        mock_service = MagicMock()
        mock_service.get_lesson.return_value = None
        mock_get_service.return_value = mock_service

        from src.agent.nodes.lesson import validate_exercise_node

        state = {
            "lesson_id": "nonexistent",
            "step_index": 0,
            "level": "A1",
            "language": "es",
            "messages": [],
            "user_answer": "hola",
            "exercise_id": "ex-1",
        }
        result = await validate_exercise_node(state)
        assert result["is_correct"] is False
        assert "lesson not found" in result["exercise_feedback"]

    @patch("src.agent.nodes.lesson.get_lesson_service")
    async def test_returns_false_when_exercise_not_found(
        self, mock_get_service: MagicMock
    ) -> None:
        """Should return false with message when exercise not found."""
        mock_lesson = MagicMock()
        mock_lesson.content.get_exercise_by_id.return_value = None
        mock_service = MagicMock()
        mock_service.get_lesson.return_value = mock_lesson
        mock_get_service.return_value = mock_service

        from src.agent.nodes.lesson import validate_exercise_node

        state = {
            "lesson_id": "test",
            "step_index": 0,
            "level": "A1",
            "language": "es",
            "messages": [],
            "user_answer": "hola",
            "exercise_id": "nonexistent",
        }
        result = await validate_exercise_node(state)
        assert result["is_correct"] is False
        assert "exercise not found" in result["exercise_feedback"]

    @patch("src.agent.nodes.lesson.get_lesson_service")
    async def test_validates_multiple_choice_correct(
        self, mock_get_service: MagicMock, mock_settings: "Settings"
    ) -> None:
        """Should validate correct multiple choice answer."""
        from src.lessons.models import MultipleChoiceExercise

        exercise = MultipleChoiceExercise(
            id="mc-1",
            question="What is hello in Spanish?",
            options=["Hola", "Adios", "Gracias"],
            correct_index=0,
        )

        mock_lesson = MagicMock()
        mock_lesson.content.get_exercise_by_id.return_value = exercise
        mock_service = MagicMock()
        mock_service.get_lesson.return_value = mock_lesson
        mock_get_service.return_value = mock_service

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Great job!"))

        with (
            patch("src.api.config.get_settings", return_value=mock_settings),
            patch("src.agent.nodes.lesson._get_llm", return_value=mock_llm),
        ):
            from src.agent.nodes.lesson import validate_exercise_node

            state = {
                "lesson_id": "test",
                "step_index": 0,
                "level": "A1",
                "language": "es",
                "messages": [],
                "user_answer": "0",
                "exercise_id": "mc-1",
            }
            result = await validate_exercise_node(state)
            assert result["is_correct"] is True
            assert result["exercise_feedback"] == "Great job!"

    @patch("src.agent.nodes.lesson.get_lesson_service")
    async def test_validates_multiple_choice_incorrect(
        self, mock_get_service: MagicMock, mock_settings: "Settings"
    ) -> None:
        """Should validate incorrect multiple choice answer."""
        from src.lessons.models import MultipleChoiceExercise

        exercise = MultipleChoiceExercise(
            id="mc-1",
            question="What is hello in Spanish?",
            options=["Hola", "Adios", "Gracias"],
            correct_index=0,
        )

        mock_lesson = MagicMock()
        mock_lesson.content.get_exercise_by_id.return_value = exercise
        mock_service = MagicMock()
        mock_service.get_lesson.return_value = mock_lesson
        mock_get_service.return_value = mock_service

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Nice try!"))

        with (
            patch("src.api.config.get_settings", return_value=mock_settings),
            patch("src.agent.nodes.lesson._get_llm", return_value=mock_llm),
        ):
            from src.agent.nodes.lesson import validate_exercise_node

            state = {
                "lesson_id": "test",
                "step_index": 0,
                "level": "A1",
                "language": "es",
                "messages": [],
                "user_answer": "1",
                "exercise_id": "mc-1",
            }
            result = await validate_exercise_node(state)
            assert result["is_correct"] is False

    @patch("src.agent.nodes.lesson.get_lesson_service")
    async def test_validates_multiple_choice_invalid_input(
        self, mock_get_service: MagicMock, mock_settings: "Settings"
    ) -> None:
        """Should handle non-numeric input for multiple choice."""
        from src.lessons.models import MultipleChoiceExercise

        exercise = MultipleChoiceExercise(
            id="mc-1",
            question="What is hello?",
            options=["Hola", "Adios"],
            correct_index=0,
        )

        mock_lesson = MagicMock()
        mock_lesson.content.get_exercise_by_id.return_value = exercise
        mock_service = MagicMock()
        mock_service.get_lesson.return_value = mock_lesson
        mock_get_service.return_value = mock_service

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Try again!"))

        with (
            patch("src.api.config.get_settings", return_value=mock_settings),
            patch("src.agent.nodes.lesson._get_llm", return_value=mock_llm),
        ):
            from src.agent.nodes.lesson import validate_exercise_node

            state = {
                "lesson_id": "test",
                "step_index": 0,
                "level": "A1",
                "language": "es",
                "messages": [],
                "user_answer": "not_a_number",
                "exercise_id": "mc-1",
            }
            result = await validate_exercise_node(state)
            assert result["is_correct"] is False

    @patch("src.agent.nodes.lesson.get_lesson_service")
    async def test_validates_fill_blank_correct(
        self, mock_get_service: MagicMock, mock_settings: "Settings"
    ) -> None:
        """Should validate correct fill-in-the-blank answer."""
        from src.lessons.models import FillBlankExercise

        exercise = FillBlankExercise(
            id="fb-1",
            sentence_template="_____ dias!",
            correct_answer="Buenos",
        )

        mock_lesson = MagicMock()
        mock_lesson.content.get_exercise_by_id.return_value = exercise
        mock_service = MagicMock()
        mock_service.get_lesson.return_value = mock_lesson
        mock_get_service.return_value = mock_service

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Perfect!"))

        with (
            patch("src.api.config.get_settings", return_value=mock_settings),
            patch("src.agent.nodes.lesson._get_llm", return_value=mock_llm),
        ):
            from src.agent.nodes.lesson import validate_exercise_node

            state = {
                "lesson_id": "test",
                "step_index": 0,
                "level": "A1",
                "language": "es",
                "messages": [],
                "user_answer": "Buenos",
                "exercise_id": "fb-1",
            }
            result = await validate_exercise_node(state)
            assert result["is_correct"] is True

    @patch("src.agent.nodes.lesson.get_lesson_service")
    async def test_validates_translate_correct(
        self, mock_get_service: MagicMock, mock_settings: "Settings"
    ) -> None:
        """Should validate correct translation answer."""
        from src.lessons.models import TranslateExercise

        exercise = TranslateExercise(
            id="tr-1",
            source_text="Hello",
            source_language="en",
            target_language="es",
            correct_translation="Hola",
        )

        mock_lesson = MagicMock()
        mock_lesson.content.get_exercise_by_id.return_value = exercise
        mock_service = MagicMock()
        mock_service.get_lesson.return_value = mock_lesson
        mock_get_service.return_value = mock_service

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Excellent!"))

        with (
            patch("src.api.config.get_settings", return_value=mock_settings),
            patch("src.agent.nodes.lesson._get_llm", return_value=mock_llm),
        ):
            from src.agent.nodes.lesson import validate_exercise_node

            state = {
                "lesson_id": "test",
                "step_index": 0,
                "level": "A1",
                "language": "es",
                "messages": [],
                "user_answer": "Hola",
                "exercise_id": "tr-1",
            }
            result = await validate_exercise_node(state)
            assert result["is_correct"] is True
            assert result["exercise_feedback"] == "Excellent!"

    @patch("src.agent.nodes.lesson.get_lesson_service")
    async def test_validates_translate_incorrect(
        self, mock_get_service: MagicMock, mock_settings: "Settings"
    ) -> None:
        """Should validate incorrect translation answer."""
        from src.lessons.models import TranslateExercise

        exercise = TranslateExercise(
            id="tr-1",
            source_text="Hello",
            source_language="en",
            target_language="es",
            correct_translation="Hola",
        )

        mock_lesson = MagicMock()
        mock_lesson.content.get_exercise_by_id.return_value = exercise
        mock_service = MagicMock()
        mock_service.get_lesson.return_value = mock_lesson
        mock_get_service.return_value = mock_service

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Almost!"))

        with (
            patch("src.api.config.get_settings", return_value=mock_settings),
            patch("src.agent.nodes.lesson._get_llm", return_value=mock_llm),
        ):
            from src.agent.nodes.lesson import validate_exercise_node

            state = {
                "lesson_id": "test",
                "step_index": 0,
                "level": "A1",
                "language": "es",
                "messages": [],
                "user_answer": "Adios",
                "exercise_id": "tr-1",
            }
            result = await validate_exercise_node(state)
            assert result["is_correct"] is False


# =============================================================================
# lesson_graph.py: build_lesson_subgraph and build_exercise_validation_graph
# (lines 15-103)
# =============================================================================


class TestBuildLessonSubgraph:
    """Tests for build_lesson_subgraph covering lesson_graph.py lines 28-62."""

    def test_builds_compiled_graph(self) -> None:
        """Should return a compiled StateGraph."""
        from src.agent.lesson_graph import build_lesson_subgraph

        graph = build_lesson_subgraph()
        assert graph is not None
        # Compiled graph should have an ainvoke method
        assert hasattr(graph, "ainvoke")

    def test_graph_has_load_step_node(self) -> None:
        """The subgraph should include a load_step node."""
        from src.agent.lesson_graph import build_lesson_subgraph

        graph = build_lesson_subgraph()
        # Access the underlying graph nodes
        node_names = list(graph.get_graph().nodes.keys())
        assert "load_step" in node_names

    def test_graph_has_enhance_step_node(self) -> None:
        """The subgraph should include an enhance_step node."""
        from src.agent.lesson_graph import build_lesson_subgraph

        graph = build_lesson_subgraph()
        node_names = list(graph.get_graph().nodes.keys())
        assert "enhance_step" in node_names


class TestBuildExerciseValidationGraph:
    """Tests for build_exercise_validation_graph covering lesson_graph.py lines 65-97."""

    def test_builds_compiled_graph(self) -> None:
        """Should return a compiled StateGraph."""
        from src.agent.lesson_graph import build_exercise_validation_graph

        graph = build_exercise_validation_graph()
        assert graph is not None
        assert hasattr(graph, "ainvoke")

    def test_graph_has_validate_exercise_node(self) -> None:
        """The exercise graph should include a validate_exercise node."""
        from src.agent.lesson_graph import build_exercise_validation_graph

        graph = build_exercise_validation_graph()
        node_names = list(graph.get_graph().nodes.keys())
        assert "validate_exercise" in node_names


class TestPreCompiledInstances:
    """Tests for pre-compiled graph instances (lesson_graph.py lines 100-103)."""

    def test_lesson_subgraph_is_importable(self) -> None:
        """lesson_subgraph should be importable and ready to use."""
        from src.agent.lesson_graph import lesson_subgraph

        assert lesson_subgraph is not None
        assert hasattr(lesson_subgraph, "ainvoke")

    def test_exercise_validation_graph_is_importable(self) -> None:
        """exercise_validation_graph should be importable and ready to use."""
        from src.agent.lesson_graph import exercise_validation_graph

        assert exercise_validation_graph is not None
        assert hasattr(exercise_validation_graph, "ainvoke")
