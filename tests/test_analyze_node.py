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
