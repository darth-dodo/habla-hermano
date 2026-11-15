"""Tests to increase coverage on uncovered agent source files.

Targets:
- src/agent/nodes/respond.py (lines 60-318, 342-383, 396-402, 439-448, 464)
- src/agent/nodes/analyze.py (lines 130-144, 195, 231-251, 268-292, 350-356)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage
from postgrest.exceptions import APIError

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

        result = await _get_topical_review_words(user_id=None, language="es", messages=[], limit=5)
        assert result == []

    async def test_returns_empty_for_empty_user_id(self) -> None:
        """Should return empty list when user_id is empty string."""
        from src.agent.nodes.respond import _get_topical_review_words

        result = await _get_topical_review_words(user_id="", language="es", messages=[], limit=5)
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
        mock_client = MagicMock()

        with patch("src.services.review.ReviewService", mock_review_cls):
            messages = [HumanMessage(content="I want to buy a house")]
            result = await _get_topical_review_words(
                user_id="user-123",
                language="es",
                messages=messages,
                supabase_client=mock_client,
                limit=5,
            )
            assert len(result) == 1
            assert result[0]["vocab_id"] == 42
            assert result[0]["word"] == "casa"
            assert result[0]["translation"] == "house"
            mock_review_cls.assert_called_once_with("user-123", client=mock_client)

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

        with patch("src.services.review.ReviewService", mock_review_cls):
            result = await _get_topical_review_words(
                user_id="user-123", language="es", messages=[], limit=5
            )
            assert len(result) == 1
            assert result[0]["word"] == "gato"

    async def test_returns_empty_on_exception(self) -> None:
        """Should return empty list and log warning on exception."""
        from src.agent.nodes.respond import _get_topical_review_words

        with patch(
            "src.services.review.ReviewService",
            side_effect=APIError(
                {"code": "500", "message": "DB error", "hint": None, "details": None}
            ),
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
        self, mock_settings: Settings
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
            patch("src.config.get_settings", return_value=mock_settings),
            patch("src.agent.nodes.respond.get_llm", return_value=mock_llm),
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
            result = await respond_node(state, {"configurable": {"supabase_client": None}})

            mock_get_words.assert_called_once_with(
                user_id="test-user-123",
                language="es",
                messages=state["messages"],
                supabase_client=None,
                limit=5,
            )
            assert "review_words_offered" in result
            assert result["review_words_offered"] == review_words

    async def test_respond_node_without_user_id_skips_review(self, mock_settings: Settings) -> None:
        """respond_node should not fetch review words when no user_id."""
        from src.agent.nodes.respond import respond_node

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))

        with (
            patch("src.config.get_settings", return_value=mock_settings),
            patch("src.agent.nodes.respond.get_llm", return_value=mock_llm),
        ):
            state: ConversationState = {
                "messages": [HumanMessage(content="Hola!")],
                "level": "A1",
                "language": "es",
            }
            result = await respond_node(state, {"configurable": {"supabase_client": None}})
            assert "review_words_offered" not in result

    async def test_respond_node_no_review_words_offered_key_when_empty(
        self, mock_settings: Settings
    ) -> None:
        """respond_node should not include review_words_offered when list is empty."""
        from src.agent.nodes.respond import respond_node

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))

        with (
            patch("src.config.get_settings", return_value=mock_settings),
            patch("src.agent.nodes.respond.get_llm", return_value=mock_llm),
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
            result = await respond_node(state, {"configurable": {"supabase_client": None}})
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
        mock_client = MagicMock()

        with patch("src.services.review.ReviewService", mock_review_cls):
            words = [
                ReviewWordUsed(vocab_id=1, word="casa", quality=4),
                ReviewWordUsed(vocab_id=2, word="gato", quality=4),
            ]
            await _update_sm2_for_used_words("user-123", words, supabase_client=mock_client)

            mock_review_cls.assert_called_once_with("user-123", client=mock_client)
            assert mock_review_instance.update_sm2.call_count == 2
            mock_review_instance.update_sm2.assert_any_call(vocab_id=1, quality=4)
            mock_review_instance.update_sm2.assert_any_call(vocab_id=2, quality=4)

    async def test_handles_individual_word_exception(self) -> None:
        """Should continue processing when one word fails."""
        from src.agent.nodes.analyze import _update_sm2_for_used_words
        from src.agent.state import ReviewWordUsed

        mock_review_instance = MagicMock()
        mock_review_instance.update_sm2.side_effect = [
            APIError(
                {"code": "500", "message": "DB error", "hint": None, "details": None}
            ),  # First word fails
            None,  # Second word succeeds
        ]
        mock_review_cls = MagicMock(return_value=mock_review_instance)
        mock_client = MagicMock()

        with patch("src.services.review.ReviewService", mock_review_cls):
            words = [
                ReviewWordUsed(vocab_id=1, word="casa", quality=4),
                ReviewWordUsed(vocab_id=2, word="gato", quality=4),
            ]
            # Should not raise
            await _update_sm2_for_used_words("user-123", words, supabase_client=mock_client)
            assert mock_review_instance.update_sm2.call_count == 2

    async def test_handles_outer_exception(self) -> None:
        """Should handle exception during service initialization."""
        from src.agent.nodes.analyze import _update_sm2_for_used_words
        from src.agent.state import ReviewWordUsed

        with patch(
            "src.services.review.ReviewService",
            side_effect=APIError(
                {"code": "500", "message": "Service init error", "hint": None, "details": None}
            ),
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
            patch("src.agent.nodes.analyze.get_llm", return_value=mock_llm),
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
            result = await analyze_node(state, {"configurable": {"supabase_client": None}})

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

        with patch("src.agent.nodes.analyze.get_llm", return_value=mock_llm):
            state: ConversationState = {
                "messages": [
                    HumanMessage(content="Mi casa es grande"),
                    AIMessage(content="Muy bien!"),
                ],
                "level": "A1",
                "language": "es",
            }
            result = await analyze_node(state, {"configurable": {"supabase_client": None}})
            assert "review_words_used" not in result
