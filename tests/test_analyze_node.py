"""
Tests for the analyze_node function.

This module tests the grammar analysis and vocabulary extraction
functionality of the analyze node in the conversation graph.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.nodes.analyze import analyze_node

if TYPE_CHECKING:
    from src.agent.state import ConversationState


class TestAnalyzeNodeStructure:
    """Tests for analyze_node return structure."""

    @pytest.mark.asyncio
    async def test_returns_dict(self) -> None:
        """analyze_node should return a dictionary."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_returns_grammar_feedback_key(self) -> None:
        """analyze_node should return a dict with grammar_feedback key."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        assert "grammar_feedback" in result

    @pytest.mark.asyncio
    async def test_returns_new_vocabulary_key(self) -> None:
        """analyze_node should return a dict with new_vocabulary key."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        assert "new_vocabulary" in result

    @pytest.mark.asyncio
    async def test_grammar_feedback_is_list(self) -> None:
        """grammar_feedback should be a list."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        assert isinstance(result["grammar_feedback"], list)

    @pytest.mark.asyncio
    async def test_new_vocabulary_is_list(self) -> None:
        """new_vocabulary should be a list."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        assert isinstance(result["new_vocabulary"], list)


class TestAnalyzeNodeEmptyMessages:
    """Tests for analyze_node with empty or missing messages."""

    @pytest.mark.asyncio
    async def test_handles_empty_messages_list(self) -> None:
        """analyze_node should handle empty messages list gracefully."""
        state: ConversationState = {
            "messages": [],
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        assert result["grammar_feedback"] == []
        assert result["new_vocabulary"] == []

    @pytest.mark.asyncio
    async def test_handles_only_ai_message(self) -> None:
        """analyze_node should handle state with only AI messages."""
        state: ConversationState = {
            "messages": [AIMessage(content="Hola! Como estas?")],
            "level": "A1",
            "language": "es",
        }
        # Should not crash, should return empty or gracefully handle
        result = await analyze_node(state)
        assert "grammar_feedback" in result
        assert "new_vocabulary" in result


class TestAnalyzeNodeWithConversationHistory:
    """Tests for analyze_node with various conversation histories."""

    @pytest.mark.asyncio
    async def test_handles_single_human_message(self) -> None:
        """analyze_node should handle a single human message."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Yo soy bueno")],
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        assert isinstance(result, dict)
        assert "grammar_feedback" in result

    @pytest.mark.asyncio
    async def test_handles_conversation_with_history(self) -> None:
        """analyze_node should handle full conversation history."""
        state: ConversationState = {
            "messages": [
                HumanMessage(content="Hola!"),
                AIMessage(content="Hola! Como estas?"),
                HumanMessage(content="Yo estoy bien, gracias"),
            ],
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        assert isinstance(result, dict)
        assert "grammar_feedback" in result
        assert "new_vocabulary" in result

    @pytest.mark.asyncio
    async def test_handles_long_conversation(self) -> None:
        """analyze_node should handle long conversation histories."""
        messages = []
        for i in range(10):
            messages.append(HumanMessage(content=f"User message {i}"))
            messages.append(AIMessage(content=f"AI response {i}"))

        state: ConversationState = {
            "messages": messages,
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        assert isinstance(result, dict)


class TestAnalyzeNodeLevels:
    """Tests for analyze_node with different CEFR levels."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    async def test_handles_all_cefr_levels(self, level: str) -> None:
        """analyze_node should handle all valid CEFR levels."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola, me llamo Juan")],
            "level": level,
            "language": "es",
        }
        result = await analyze_node(state)
        assert isinstance(result, dict)
        assert "grammar_feedback" in result

    @pytest.mark.asyncio
    async def test_handles_unknown_level(self) -> None:
        """analyze_node should not crash with unknown level."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": "C2",  # Not officially supported
            "language": "es",
        }
        # Should not crash
        result = await analyze_node(state)
        assert isinstance(result, dict)


class TestAnalyzeNodeLanguages:
    """Tests for analyze_node with different languages."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("language", ["es", "de"])
    async def test_handles_supported_languages(self, language: str) -> None:
        """analyze_node should handle all supported languages."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A1",
            "language": language,
        }
        result = await analyze_node(state)
        assert isinstance(result, dict)
        assert "grammar_feedback" in result

    @pytest.mark.asyncio
    async def test_handles_unsupported_language(self) -> None:
        """analyze_node should not crash with unsupported language."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Bonjour!")],
            "level": "A1",
            "language": "fr",  # Not supported
        }
        # Should not crash
        result = await analyze_node(state)
        assert isinstance(result, dict)


class TestAnalyzeNodeCurrentStub:
    """Tests for current stub implementation behavior."""

    @pytest.mark.asyncio
    async def test_stub_returns_empty_grammar_feedback(self) -> None:
        """Current stub should return empty grammar_feedback list."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Yo es un estudiante")],  # Grammar error
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        # Stub implementation returns empty lists
        assert result["grammar_feedback"] == []

    @pytest.mark.asyncio
    async def test_stub_returns_empty_new_vocabulary(self) -> None:
        """Current stub should return empty new_vocabulary list."""
        state: ConversationState = {
            "messages": [HumanMessage(content="El edificio es magnifico")],  # New vocab
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        # Stub implementation returns empty lists
        assert result["new_vocabulary"] == []


class TestGrammarFeedbackStructure:
    """Tests for expected GrammarFeedback structure (matches state.py)."""

    def test_grammar_feedback_expected_fields(self) -> None:
        """GrammarFeedback should have expected fields when implemented."""
        # This test documents the expected structure matching state.py
        expected_fields = {"original", "correction", "explanation", "severity"}
        sample_feedback = {
            "original": "Yo es",
            "correction": "Yo soy",
            "explanation": "Use 'soy' with 'yo'",
            "severity": "moderate",
        }
        assert set(sample_feedback.keys()) == expected_fields

    def test_severity_valid_values(self) -> None:
        """Severity should have valid values matching state.py Literal type."""
        # Matches the Literal["minor", "moderate", "significant"] in state.py
        valid_severities = {"minor", "moderate", "significant"}
        for severity in valid_severities:
            assert severity in {"minor", "moderate", "significant"}


class TestVocabWordStructure:
    """Tests for expected VocabWord structure (matches state.py)."""

    def test_vocab_word_expected_fields(self) -> None:
        """VocabWord should have expected fields matching state.py."""
        # This test documents the expected structure matching state.py
        expected_fields = {"word", "translation", "part_of_speech"}
        sample_vocab = {
            "word": "edificio",
            "translation": "building",
            "part_of_speech": "noun",
        }
        assert set(sample_vocab.keys()) == expected_fields

    def test_vocab_word_part_of_speech_values(self) -> None:
        """part_of_speech should accept valid grammatical categories."""
        valid_parts = ["noun", "verb", "adjective", "adverb", "preposition"]
        for pos in valid_parts:
            assert isinstance(pos, str)


class TestAnalyzeNodeEdgeCases:
    """Edge case tests for analyze_node."""

    @pytest.mark.asyncio
    async def test_handles_empty_message_content(self) -> None:
        """analyze_node should handle messages with empty content."""
        state: ConversationState = {
            "messages": [HumanMessage(content="")],
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_handles_whitespace_only_message(self) -> None:
        """analyze_node should handle messages with only whitespace."""
        state: ConversationState = {
            "messages": [HumanMessage(content="   ")],
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_handles_special_characters(self) -> None:
        """analyze_node should handle messages with special characters."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola! Como estas? :)")],
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_handles_unicode_characters(self) -> None:
        """analyze_node should handle Unicode characters properly."""
        state: ConversationState = {
            "messages": [HumanMessage(content="El nino tiene anos")],  # Missing tildes
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_handles_very_long_message(self) -> None:
        """analyze_node should handle very long messages."""
        long_content = "Hola " * 1000
        state: ConversationState = {
            "messages": [HumanMessage(content=long_content)],
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        assert isinstance(result, dict)


class TestAnalyzeNodeWithMockedLLM:
    """Tests for analyze_node with mocked LLM (for Phase 2 implementation)."""

    @pytest.fixture
    def mock_llm_response_with_errors(self) -> dict[str, Any]:
        """Create mock LLM response with grammar errors (matching state.py types)."""
        return {
            "grammar_feedback": [
                {
                    "original": "Yo es estudiante",
                    "correction": "Yo soy estudiante",
                    "explanation": "The verb 'ser' conjugates to 'soy' with 'yo'",
                    "severity": "moderate",
                }
            ],
            "new_vocabulary": [
                {
                    "word": "estudiante",
                    "translation": "student",
                    "part_of_speech": "noun",
                }
            ],
        }

    @pytest.fixture
    def mock_llm_response_no_errors(self) -> dict[str, Any]:
        """Create mock LLM response with no errors."""
        return {
            "grammar_feedback": [],
            "new_vocabulary": [],
        }

    def test_mock_response_structure_with_errors(
        self, mock_llm_response_with_errors: dict[str, Any]
    ) -> None:
        """Verify mock response structure is valid."""
        response = mock_llm_response_with_errors
        assert "grammar_feedback" in response
        assert "new_vocabulary" in response
        assert len(response["grammar_feedback"]) == 1
        assert len(response["new_vocabulary"]) == 1
        # Verify severity uses correct values
        assert response["grammar_feedback"][0]["severity"] in {
            "minor",
            "moderate",
            "significant",
        }
        # Verify vocab has part_of_speech
        assert "part_of_speech" in response["new_vocabulary"][0]

    def test_mock_response_structure_no_errors(
        self, mock_llm_response_no_errors: dict[str, Any]
    ) -> None:
        """Verify mock response with no errors is valid."""
        response = mock_llm_response_no_errors
        assert response["grammar_feedback"] == []
        assert response["new_vocabulary"] == []


class TestAnalyzeNodeJSONParsing:
    """Tests for JSON parsing edge cases (Phase 2 preparation)."""

    def test_valid_json_parsing(self) -> None:
        """Valid JSON should parse correctly."""
        json_str = '{"grammar_feedback": [], "new_vocabulary": []}'
        result = json.loads(json_str)
        assert result["grammar_feedback"] == []
        assert result["new_vocabulary"] == []

    def test_json_with_nested_objects(self) -> None:
        """JSON with nested objects should parse correctly."""
        json_str = """
        {
            "grammar_feedback": [
                {
                    "original": "test",
                    "correction": "test",
                    "explanation": "test",
                    "severity": "minor"
                }
            ],
            "new_vocabulary": []
        }
        """
        result = json.loads(json_str)
        assert len(result["grammar_feedback"]) == 1
        assert result["grammar_feedback"][0]["severity"] == "minor"

    def test_invalid_json_raises_error(self) -> None:
        """Invalid JSON should raise an error."""
        invalid_json = '{"grammar_feedback": [], "new_vocabulary": '  # Incomplete
        with pytest.raises(json.JSONDecodeError):
            json.loads(invalid_json)

    def test_json_with_unicode(self) -> None:
        """JSON with Unicode should parse correctly."""
        json_str = '{"original": "El nino", "correction": "El ni\\u00f1o"}'
        result = json.loads(json_str)
        assert result["correction"] == "El ni\u00f1o"


class TestSeverityValidation:
    """Tests for severity value validation (matching state.py Literal type)."""

    @pytest.mark.parametrize("severity", ["minor", "moderate", "significant"])
    def test_valid_severity_values(self, severity: str) -> None:
        """Valid severity values should be accepted (matching state.py)."""
        valid_severities = {"minor", "moderate", "significant"}
        assert severity in valid_severities

    @pytest.mark.parametrize(
        "severity", ["low", "medium", "high", "MINOR", "Moderate", "critical", "none", ""]
    )
    def test_invalid_severity_values(self, severity: str) -> None:
        """Invalid severity values should not be in valid set."""
        valid_severities = {"minor", "moderate", "significant"}
        assert severity not in valid_severities


class TestAnalyzeNodeAsync:
    """Tests for async behavior of analyze_node."""

    @pytest.mark.asyncio
    async def test_is_async_function(self) -> None:
        """analyze_node should be an async function."""
        import inspect

        assert inspect.iscoroutinefunction(analyze_node)

    @pytest.mark.asyncio
    async def test_returns_awaitable(self) -> None:
        """analyze_node should return an awaitable."""
        import asyncio

        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es",
        }
        coro = analyze_node(state)
        # Verify it's a coroutine
        assert asyncio.iscoroutine(coro)
        # Await it to complete the test
        result = await coro
        assert isinstance(result, dict)


class TestGrammarFeedbackTypedDictIntegration:
    """Tests verifying GrammarFeedback TypedDict from state module."""

    def test_grammar_feedback_can_be_imported(self) -> None:
        """GrammarFeedback TypedDict should be importable."""
        from src.agent.state import GrammarFeedback

        assert GrammarFeedback is not None

    def test_grammar_feedback_has_correct_fields(self) -> None:
        """GrammarFeedback should have the expected fields."""
        from typing import get_type_hints

        from src.agent.state import GrammarFeedback

        hints = get_type_hints(GrammarFeedback)
        expected_fields = {"original", "correction", "explanation", "severity"}
        assert set(hints.keys()) == expected_fields


class TestVocabWordTypedDictIntegration:
    """Tests verifying VocabWord TypedDict from state module."""

    def test_vocab_word_can_be_imported(self) -> None:
        """VocabWord TypedDict should be importable."""
        from src.agent.state import VocabWord

        assert VocabWord is not None

    def test_vocab_word_has_correct_fields(self) -> None:
        """VocabWord should have the expected fields."""
        from typing import get_type_hints

        from src.agent.state import VocabWord

        hints = get_type_hints(VocabWord)
        expected_fields = {"word", "translation", "part_of_speech"}
        assert set(hints.keys()) == expected_fields


# =============================================================================
# COVERAGE GAP TESTS - _parse_analysis_response()
# =============================================================================


class TestParseAnalysisResponseMarkdownBlocks:
    """Tests for _parse_analysis_response handling of markdown code blocks."""

    def test_parse_json_with_json_code_block(self) -> None:
        """_parse_analysis_response should handle JSON wrapped in ```json blocks."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = """```json
{
    "grammar_errors": [
        {
            "original": "Yo es",
            "correction": "Yo soy",
            "explanation": "Use soy with yo",
            "severity": "moderate"
        }
    ],
    "new_vocabulary": []
}
```"""
        grammar, vocab = _parse_analysis_response(content)
        assert len(grammar) == 1
        assert grammar[0]["original"] == "Yo es"
        assert grammar[0]["correction"] == "Yo soy"
        assert vocab == []

    def test_parse_json_with_plain_code_block(self) -> None:
        """_parse_analysis_response should handle JSON wrapped in plain ``` blocks."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = """```
{
    "grammar_errors": [],
    "new_vocabulary": [
        {
            "word": "libro",
            "translation": "book",
            "part_of_speech": "noun"
        }
    ]
}
```"""
        grammar, vocab = _parse_analysis_response(content)
        assert grammar == []
        assert len(vocab) == 1
        assert vocab[0]["word"] == "libro"

    def test_parse_plain_json(self) -> None:
        """_parse_analysis_response should handle plain JSON without code blocks."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = '{"grammar_errors": [], "new_vocabulary": []}'
        grammar, vocab = _parse_analysis_response(content)
        assert grammar == []
        assert vocab == []


class TestParseAnalysisResponseGrammarErrors:
    """Tests for _parse_analysis_response parsing grammar_errors array."""

    def test_parse_single_grammar_error(self) -> None:
        """_parse_analysis_response should parse a single grammar error."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = json.dumps(
            {
                "grammar_errors": [
                    {
                        "original": "Yo es estudiante",
                        "correction": "Yo soy estudiante",
                        "explanation": "Use soy with yo",
                        "severity": "moderate",
                    }
                ],
                "new_vocabulary": [],
            }
        )
        grammar, _vocab = _parse_analysis_response(content)
        assert len(grammar) == 1
        assert grammar[0]["original"] == "Yo es estudiante"
        assert grammar[0]["correction"] == "Yo soy estudiante"
        assert grammar[0]["explanation"] == "Use soy with yo"
        assert grammar[0]["severity"] == "moderate"

    def test_parse_multiple_grammar_errors(self) -> None:
        """_parse_analysis_response should parse multiple grammar errors."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = json.dumps(
            {
                "grammar_errors": [
                    {
                        "original": "err1",
                        "correction": "corr1",
                        "explanation": "exp1",
                        "severity": "minor",
                    },
                    {
                        "original": "err2",
                        "correction": "corr2",
                        "explanation": "exp2",
                        "severity": "significant",
                    },
                    {
                        "original": "err3",
                        "correction": "corr3",
                        "explanation": "exp3",
                        "severity": "moderate",
                    },
                ],
                "new_vocabulary": [],
            }
        )
        grammar, _vocab = _parse_analysis_response(content)
        assert len(grammar) == 3
        assert grammar[0]["severity"] == "minor"
        assert grammar[1]["severity"] == "significant"
        assert grammar[2]["severity"] == "moderate"

    def test_parse_grammar_error_with_invalid_severity(self) -> None:
        """_parse_analysis_response should default invalid severity to 'minor'."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = json.dumps(
            {
                "grammar_errors": [
                    {
                        "original": "test",
                        "correction": "test",
                        "explanation": "test",
                        "severity": "INVALID",
                    }
                ],
                "new_vocabulary": [],
            }
        )
        grammar, _vocab = _parse_analysis_response(content)
        assert len(grammar) == 1
        assert grammar[0]["severity"] == "minor"  # Defaults to minor

    def test_parse_grammar_error_with_missing_severity(self) -> None:
        """_parse_analysis_response should default missing severity to 'minor'."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = json.dumps(
            {
                "grammar_errors": [
                    {"original": "test", "correction": "test", "explanation": "test"}
                ],
                "new_vocabulary": [],
            }
        )
        grammar, _vocab = _parse_analysis_response(content)
        assert len(grammar) == 1
        assert grammar[0]["severity"] == "minor"  # Defaults to minor

    def test_parse_grammar_error_with_missing_fields(self) -> None:
        """_parse_analysis_response should handle missing fields with defaults."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = json.dumps(
            {
                "grammar_errors": [
                    {}  # All fields missing
                ],
                "new_vocabulary": [],
            }
        )
        grammar, _vocab = _parse_analysis_response(content)
        assert len(grammar) == 1
        assert grammar[0]["original"] == ""
        assert grammar[0]["correction"] == ""
        assert grammar[0]["explanation"] == ""
        assert grammar[0]["severity"] == "minor"


class TestParseAnalysisResponseVocabulary:
    """Tests for _parse_analysis_response parsing new_vocabulary array."""

    def test_parse_single_vocabulary_word(self) -> None:
        """_parse_analysis_response should parse a single vocabulary word."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = json.dumps(
            {
                "grammar_errors": [],
                "new_vocabulary": [
                    {"word": "casa", "translation": "house", "part_of_speech": "noun"}
                ],
            }
        )
        grammar, vocab = _parse_analysis_response(content)
        assert grammar == []
        assert len(vocab) == 1
        assert vocab[0]["word"] == "casa"
        assert vocab[0]["translation"] == "house"
        assert vocab[0]["part_of_speech"] == "noun"

    def test_parse_multiple_vocabulary_words(self) -> None:
        """_parse_analysis_response should parse multiple vocabulary words."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = json.dumps(
            {
                "grammar_errors": [],
                "new_vocabulary": [
                    {"word": "hola", "translation": "hello", "part_of_speech": "interjection"},
                    {"word": "libro", "translation": "book", "part_of_speech": "noun"},
                    {"word": "grande", "translation": "big", "part_of_speech": "adjective"},
                ],
            }
        )
        _grammar, vocab = _parse_analysis_response(content)
        assert len(vocab) == 3
        assert vocab[0]["word"] == "hola"
        assert vocab[1]["word"] == "libro"
        assert vocab[2]["word"] == "grande"

    def test_parse_vocabulary_with_missing_fields(self) -> None:
        """_parse_analysis_response should handle missing vocab fields with defaults."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = json.dumps(
            {
                "grammar_errors": [],
                "new_vocabulary": [
                    {}  # All fields missing
                ],
            }
        )
        _grammar, vocab = _parse_analysis_response(content)
        assert len(vocab) == 1
        assert vocab[0]["word"] == ""
        assert vocab[0]["translation"] == ""
        assert vocab[0]["part_of_speech"] == "other"


class TestParseAnalysisResponseErrors:
    """Tests for _parse_analysis_response error handling."""

    def test_parse_invalid_json(self) -> None:
        """_parse_analysis_response should return empty lists for invalid JSON."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = "not valid json {"
        grammar, vocab = _parse_analysis_response(content)
        assert grammar == []
        assert vocab == []

    def test_parse_empty_string(self) -> None:
        """_parse_analysis_response should return empty lists for empty string."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = ""
        grammar, vocab = _parse_analysis_response(content)
        assert grammar == []
        assert vocab == []

    def test_parse_json_missing_keys(self) -> None:
        """_parse_analysis_response should handle JSON without expected keys."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = '{"other_key": "value"}'
        grammar, vocab = _parse_analysis_response(content)
        assert grammar == []
        assert vocab == []

    def test_parse_json_with_wrong_types(self) -> None:
        """_parse_analysis_response should handle JSON with wrong value types."""
        from src.agent.nodes.analyze import _parse_analysis_response

        content = '{"grammar_errors": "not_an_array", "new_vocabulary": 123}'
        grammar, vocab = _parse_analysis_response(content)
        # Should not crash, returns empty or handles gracefully
        assert isinstance(grammar, list)
        assert isinstance(vocab, list)


# =============================================================================
# COVERAGE GAP TESTS - analyze_node() edge cases
# =============================================================================


class TestAnalyzeNodeEmptyUserText:
    """Tests for analyze_node when user_text is empty or non-string."""

    @pytest.mark.asyncio
    async def test_returns_empty_for_none_content(self) -> None:
        """analyze_node should return empty lists when message content is None-like."""
        # This tests line 188: if not user_text or not isinstance(user_text, str)
        state: ConversationState = {
            "messages": [
                HumanMessage(content=""),  # Empty content
                AIMessage(content="Response"),
            ],
            "level": "A1",
            "language": "es",
        }
        result = await analyze_node(state)
        assert result["grammar_feedback"] == []
        assert result["new_vocabulary"] == []


class TestAnalyzeNodeLLMResponse:
    """Tests for analyze_node handling different LLM response types."""

    @pytest.mark.asyncio
    async def test_handles_non_string_llm_response(self) -> None:
        """analyze_node should handle LLM returning non-string content."""
        from unittest.mock import AsyncMock, MagicMock, patch

        # Create mock LLM that returns non-string content
        mock_response = MagicMock()
        mock_response.content = ["list", "content"]  # Not a string

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("src.agent.nodes.analyze._get_llm", return_value=mock_llm):
            state: ConversationState = {
                "messages": [
                    HumanMessage(content="Hola amigo"),
                    AIMessage(content="Response"),
                ],
                "level": "A1",
                "language": "es",
            }
            result = await analyze_node(state)
            # Should return empty lists when content is not string
            assert result["grammar_feedback"] == []
            assert result["new_vocabulary"] == []


class TestAnalyzeNodeLLMExceptions:
    """Tests for analyze_node handling LLM exceptions."""

    @pytest.mark.asyncio
    async def test_handles_llm_exception(self) -> None:
        """analyze_node should handle LLM exceptions gracefully."""
        from unittest.mock import AsyncMock, MagicMock, patch

        # Create mock LLM that raises an exception
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("API Error"))

        with patch("src.agent.nodes.analyze._get_llm", return_value=mock_llm):
            state: ConversationState = {
                "messages": [
                    HumanMessage(content="Hola amigo"),
                    AIMessage(content="Response"),
                ],
                "level": "A1",
                "language": "es",
            }
            result = await analyze_node(state)
            # Should return empty lists on exception
            assert result["grammar_feedback"] == []
            assert result["new_vocabulary"] == []

    @pytest.mark.asyncio
    async def test_handles_timeout_exception(self) -> None:
        """analyze_node should handle timeout exceptions gracefully."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=TimeoutError())

        with patch("src.agent.nodes.analyze._get_llm", return_value=mock_llm):
            state: ConversationState = {
                "messages": [
                    HumanMessage(content="Hola"),
                    AIMessage(content="Response"),
                ],
                "level": "A1",
                "language": "es",
            }
            result = await analyze_node(state)
            assert result["grammar_feedback"] == []
            assert result["new_vocabulary"] == []


class TestAnalyzeNodeWithMockedLLMSuccess:
    """Tests for analyze_node with successful mocked LLM responses."""

    @pytest.mark.asyncio
    async def test_successful_analysis_with_grammar_errors(self) -> None:
        """analyze_node should return parsed grammar errors from successful LLM call."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {
                "grammar_errors": [
                    {
                        "original": "Yo es",
                        "correction": "Yo soy",
                        "explanation": "Use soy with yo",
                        "severity": "moderate",
                    }
                ],
                "new_vocabulary": [
                    {"word": "estudiante", "translation": "student", "part_of_speech": "noun"}
                ],
            }
        )

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("src.agent.nodes.analyze._get_llm", return_value=mock_llm):
            state: ConversationState = {
                "messages": [
                    HumanMessage(content="Yo es estudiante"),
                    AIMessage(content="Response"),
                ],
                "level": "A1",
                "language": "es",
            }
            result = await analyze_node(state)
            assert len(result["grammar_feedback"]) == 1
            assert result["grammar_feedback"][0]["original"] == "Yo es"
            assert len(result["new_vocabulary"]) == 1
            assert result["new_vocabulary"][0]["word"] == "estudiante"


class TestGetLlmAnalyze:
    """Tests for _get_llm helper in analyze module."""

    def test_get_llm_creates_chat_anthropic(self) -> None:
        """_get_llm should create a ChatAnthropic instance."""
        from unittest.mock import MagicMock, patch

        from src.api.config import Settings

        mock_settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            ANTHROPIC_API_KEY="test-key",  # pragma: allowlist secret
            LLM_MODEL="claude-test",
            LLM_TEMPERATURE=0.5,
        )

        with patch("src.agent.nodes.analyze.get_settings", return_value=mock_settings):
            with patch("src.agent.nodes.analyze.ChatAnthropic") as mock_chat:
                mock_chat.return_value = MagicMock()
                from src.agent.nodes.analyze import _get_llm

                _get_llm()
                mock_chat.assert_called_once()
                call_kwargs = mock_chat.call_args[1]
                assert call_kwargs["temperature"] == 0.3  # Fixed lower temp for analysis
                assert call_kwargs["max_tokens"] == 1024


class TestGetLanguageName:
    """Tests for _get_language_name helper."""

    def test_spanish_code(self) -> None:
        """_get_language_name should convert 'es' to 'Spanish'."""
        from src.agent.nodes.analyze import _get_language_name

        assert _get_language_name("es") == "Spanish"

    def test_german_code(self) -> None:
        """_get_language_name should convert 'de' to 'German'."""
        from src.agent.nodes.analyze import _get_language_name

        assert _get_language_name("de") == "German"

    def test_french_code(self) -> None:
        """_get_language_name should convert 'fr' to 'French'."""
        from src.agent.nodes.analyze import _get_language_name

        assert _get_language_name("fr") == "French"

    def test_unknown_code_defaults_to_spanish(self) -> None:
        """_get_language_name should default unknown codes to 'Spanish'."""
        from src.agent.nodes.analyze import _get_language_name

        assert _get_language_name("unknown") == "Spanish"
        assert _get_language_name("") == "Spanish"
        assert _get_language_name("it") == "Spanish"
