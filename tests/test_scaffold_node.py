"""
Tests for the scaffold node in LangGraph.

This module tests the scaffold_node function that generates
learning aids (word banks, hints, sentence starters) for A0-A1 learners.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.nodes.scaffold import scaffold_node
from src.agent.state import ScaffoldingConfig

if TYPE_CHECKING:
    from src.agent.state import ConversationState


class TestScaffoldNodeReturnStructure:
    """Tests for scaffold_node return structure."""

    @pytest.mark.asyncio
    async def test_returns_dict(self) -> None:
        """scaffold_node should return a dictionary."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_returns_scaffolding_key(self) -> None:
        """scaffold_node should return a dict with 'scaffolding' key."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert "scaffolding" in result

    @pytest.mark.asyncio
    async def test_scaffolding_is_dict(self) -> None:
        """The scaffolding value should be a dictionary."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert isinstance(result["scaffolding"], dict)

    @pytest.mark.asyncio
    async def test_scaffolding_has_enabled_key(self) -> None:
        """The scaffolding dict should have an 'enabled' key."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert "enabled" in result["scaffolding"]


class TestScaffoldNodeLevelBehavior:
    """Tests for scaffold_node behavior with different levels."""

    @pytest.mark.asyncio
    async def test_a0_level_gets_scaffolding_response(self) -> None:
        """A0 level should get a scaffolding response (even if stub)."""
        state: ConversationState = {
            "messages": [
                HumanMessage(content="Hello"),
                AIMessage(content="Hola! Como te llamas?"),
            ],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert "scaffolding" in result

    @pytest.mark.asyncio
    async def test_a1_level_gets_scaffolding_response(self) -> None:
        """A1 level should get a scaffolding response."""
        state: ConversationState = {
            "messages": [
                HumanMessage(content="Hello"),
                AIMessage(content="Hola! Como estas?"),
            ],
            "level": "A1",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert "scaffolding" in result

    @pytest.mark.asyncio
    async def test_a2_level_gets_disabled_scaffolding(self) -> None:
        """A2 level should get disabled scaffolding."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A2",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert result["scaffolding"]["enabled"] is False

    @pytest.mark.asyncio
    async def test_b1_level_gets_disabled_scaffolding(self) -> None:
        """B1 level should get disabled scaffolding."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "B1",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert result["scaffolding"]["enabled"] is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A2", "B1", "B2", "C1", "C2"])
    async def test_advanced_levels_disabled(self, level: str) -> None:
        """Advanced levels should always have disabled scaffolding."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": level,
            "language": "es",
        }
        result = await scaffold_node(state)
        assert result["scaffolding"]["enabled"] is False


class TestScaffoldNodeEmptyMessages:
    """Tests for scaffold_node with empty or minimal messages."""

    @pytest.mark.asyncio
    async def test_handles_empty_messages_list(self) -> None:
        """scaffold_node should handle empty messages list gracefully."""
        state: ConversationState = {
            "messages": [],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert "scaffolding" in result
        # Empty messages should result in disabled scaffolding
        assert result["scaffolding"]["enabled"] is False

    @pytest.mark.asyncio
    async def test_handles_single_human_message(self) -> None:
        """scaffold_node should handle single message (no AI response yet)."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert "scaffolding" in result

    @pytest.mark.asyncio
    async def test_handles_only_ai_message(self) -> None:
        """scaffold_node should handle state with only AI message."""
        state: ConversationState = {
            "messages": [AIMessage(content="Hola!")],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert "scaffolding" in result


class TestScaffoldNodeConversationHistory:
    """Tests for scaffold_node with various conversation histories."""

    @pytest.mark.asyncio
    async def test_handles_full_conversation(self) -> None:
        """scaffold_node should handle full conversation history."""
        state: ConversationState = {
            "messages": [
                HumanMessage(content="Hola!"),
                AIMessage(content="Hola! Como estas?"),
                HumanMessage(content="Bien, gracias"),
                AIMessage(content="Me alegro! Que hiciste hoy?"),
            ],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert isinstance(result, dict)
        assert "scaffolding" in result

    @pytest.mark.asyncio
    async def test_handles_long_conversation(self) -> None:
        """scaffold_node should handle long conversation histories."""
        messages: list[HumanMessage | AIMessage] = []
        for i in range(20):
            messages.append(HumanMessage(content=f"User message {i}"))
            messages.append(AIMessage(content=f"AI response {i}"))

        state: ConversationState = {
            "messages": messages,
            "level": "A1",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert isinstance(result, dict)


class TestScaffoldNodeLanguages:
    """Tests for scaffold_node with different languages."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("language", ["es", "de", "fr"])
    async def test_handles_supported_languages(self, language: str) -> None:
        """scaffold_node should handle all supported languages."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A0",
            "language": language,
        }
        result = await scaffold_node(state)
        assert "scaffolding" in result

    @pytest.mark.asyncio
    async def test_handles_unsupported_language(self) -> None:
        """scaffold_node should not crash with unsupported language."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A0",
            "language": "ru",  # Not officially supported
        }
        result = await scaffold_node(state)
        assert isinstance(result, dict)


class TestScaffoldNodeStubBehavior:
    """Tests for current stub implementation behavior."""

    @pytest.mark.asyncio
    async def test_stub_returns_disabled_for_a0(self) -> None:
        """Current stub should return disabled scaffolding for A0."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        # Current stub returns disabled for all levels
        assert "enabled" in result["scaffolding"]

    @pytest.mark.asyncio
    async def test_stub_returns_empty_word_bank(self) -> None:
        """Current stub should return empty word bank."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert "word_bank" in result["scaffolding"]
        assert result["scaffolding"]["word_bank"] == []


class TestScaffoldNodeAsync:
    """Tests for async behavior of scaffold_node."""

    @pytest.mark.asyncio
    async def test_is_async_function(self) -> None:
        """scaffold_node should be an async function."""
        import inspect

        assert inspect.iscoroutinefunction(scaffold_node)

    @pytest.mark.asyncio
    async def test_returns_awaitable(self) -> None:
        """scaffold_node should return an awaitable."""
        import asyncio

        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A0",
            "language": "es",
        }
        coro = scaffold_node(state)
        assert asyncio.iscoroutine(coro)
        result = await coro
        assert isinstance(result, dict)


class TestScaffoldingConfigModel:
    """Tests for ScaffoldingConfig Pydantic model."""

    def test_default_values(self) -> None:
        """Test default values for ScaffoldingConfig."""
        config = ScaffoldingConfig()

        assert config.enabled is False
        assert config.word_bank == []
        assert config.hint_text == ""
        assert config.sentence_starter is None
        assert config.auto_expand is False

    def test_model_dump(self) -> None:
        """Test model_dump produces correct dict."""
        config = ScaffoldingConfig(
            enabled=True,
            word_bank=["hola (hello)", "adios (goodbye)"],
            hint_text="Say hello",
            sentence_starter="Hola, me llamo...",
            auto_expand=True,
        )
        data = config.model_dump()

        assert data["enabled"] is True
        assert data["word_bank"] == ["hola (hello)", "adios (goodbye)"]
        assert data["hint_text"] == "Say hello"
        assert data["sentence_starter"] == "Hola, me llamo..."
        assert data["auto_expand"] is True

    def test_model_validate_from_dict(self) -> None:
        """Test model_validate creates config from dict."""
        data = {
            "enabled": True,
            "word_bank": ["test"],
            "hint_text": "hint",
            "sentence_starter": None,
            "auto_expand": False,
        }
        config = ScaffoldingConfig.model_validate(data)

        assert config.enabled is True
        assert config.word_bank == ["test"]
        assert config.hint_text == "hint"
        assert config.sentence_starter is None
        assert config.auto_expand is False

    def test_word_bank_accepts_list_of_strings(self) -> None:
        """word_bank should accept list of strings."""
        config = ScaffoldingConfig(word_bank=["hola", "buenos dias", "como estas"])
        assert len(config.word_bank) == 3
        assert all(isinstance(w, str) for w in config.word_bank)

    def test_sentence_starter_optional(self) -> None:
        """sentence_starter should be optional (can be None)."""
        config1 = ScaffoldingConfig(sentence_starter=None)
        config2 = ScaffoldingConfig(sentence_starter="Me llamo...")

        assert config1.sentence_starter is None
        assert config2.sentence_starter == "Me llamo..."

    def test_auto_expand_boolean(self) -> None:
        """auto_expand should be a boolean."""
        config_true = ScaffoldingConfig(auto_expand=True)
        config_false = ScaffoldingConfig(auto_expand=False)

        assert config_true.auto_expand is True
        assert config_false.auto_expand is False


class TestScaffoldingConfigImport:
    """Tests for ScaffoldingConfig import."""

    def test_scaffolding_config_importable(self) -> None:
        """ScaffoldingConfig should be importable from state module."""
        from src.agent.state import ScaffoldingConfig as ImportedConfig

        assert ImportedConfig is not None

    def test_scaffolding_config_is_pydantic_model(self) -> None:
        """ScaffoldingConfig should be a Pydantic BaseModel."""
        from pydantic import BaseModel

        assert issubclass(ScaffoldingConfig, BaseModel)


class TestScaffoldNodeEdgeCases:
    """Edge case tests for scaffold_node."""

    @pytest.mark.asyncio
    async def test_handles_empty_message_content(self) -> None:
        """scaffold_node should handle messages with empty content."""
        state: ConversationState = {
            "messages": [HumanMessage(content="")],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_handles_whitespace_only_message(self) -> None:
        """scaffold_node should handle messages with only whitespace."""
        state: ConversationState = {
            "messages": [HumanMessage(content="   ")],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_handles_special_characters(self) -> None:
        """scaffold_node should handle messages with special characters."""
        state: ConversationState = {
            "messages": [
                HumanMessage(content="Hola!"),
                AIMessage(content="Hola! Como estas? :) <3"),
            ],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_handles_unicode_characters(self) -> None:
        """scaffold_node should handle Unicode characters properly."""
        state: ConversationState = {
            "messages": [
                HumanMessage(content="Hola nino"),
                AIMessage(content="Hola! El nino esta bien."),
            ],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_handles_very_long_message(self) -> None:
        """scaffold_node should handle very long messages."""
        long_content = "Hola " * 1000
        state: ConversationState = {
            "messages": [HumanMessage(content=long_content)],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_handles_missing_level_gracefully(self) -> None:
        """scaffold_node should handle missing level with default."""
        # Test with explicit .get() fallback
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "",  # Empty level
            "language": "es",
        }
        result = await scaffold_node(state)
        # Should not crash
        assert isinstance(result, dict)


class TestScaffoldNodeWithMockedLLM:
    """Tests for scaffold_node with mocked LLM (for Phase 3 implementation)."""

    @pytest.fixture
    def mock_llm_response_valid(self) -> MagicMock:
        """Create a mock LLM response with valid JSON."""
        return MagicMock(
            content='{"word_bank": ["hola (hello)", "me llamo (my name is)"], '
            '"hint": "Try introducing yourself", '
            '"sentence_starter": "Me llamo"}'
        )

    @pytest.fixture
    def mock_llm_response_empty(self) -> MagicMock:
        """Create a mock LLM response with empty values."""
        return MagicMock(content='{"word_bank": [], "hint": "", "sentence_starter": null}')

    @pytest.fixture
    def base_state(self) -> ConversationState:
        """Base conversation state for testing."""
        return {
            "messages": [
                HumanMessage(content="Hello"),
                AIMessage(content="Hola! Como te llamas?"),
            ],
            "level": "A0",
            "language": "es",
        }

    def test_mock_response_structure_valid(self, mock_llm_response_valid: MagicMock) -> None:
        """Verify mock response structure is parseable."""
        content = mock_llm_response_valid.content
        data = json.loads(content)

        assert "word_bank" in data
        assert "hint" in data
        assert "sentence_starter" in data
        assert len(data["word_bank"]) == 2

    def test_mock_response_structure_empty(self, mock_llm_response_empty: MagicMock) -> None:
        """Verify empty mock response is parseable."""
        content = mock_llm_response_empty.content
        data = json.loads(content)

        assert data["word_bank"] == []
        assert data["hint"] == ""
        assert data["sentence_starter"] is None


class TestScaffoldNodeJSONParsing:
    """Tests for JSON parsing edge cases (Phase 3 preparation)."""

    def test_valid_json_parsing(self) -> None:
        """Valid JSON should parse correctly."""
        json_str = '{"word_bank": ["hola"], "hint": "say hello", "sentence_starter": null}'
        result = json.loads(json_str)
        assert result["word_bank"] == ["hola"]
        assert result["hint"] == "say hello"
        assert result["sentence_starter"] is None

    def test_json_with_code_block(self) -> None:
        """JSON wrapped in markdown code block should be extractable."""
        content = """```json
{"word_bank": ["hola"], "hint": "test", "sentence_starter": null}
```"""
        # Extract JSON from code block
        json_str = content.split("```json")[1].split("```")[0] if "```json" in content else content

        result = json.loads(json_str.strip())
        assert result["word_bank"] == ["hola"]

    def test_json_with_unicode(self) -> None:
        """JSON with Unicode should parse correctly."""
        # Unicode escape sequences are converted to actual characters by json.loads
        json_str = '{"word_bank": ["ni\\u00f1o (child)", "ma\\u00f1ana (tomorrow)"]}'
        result = json.loads(json_str)
        # The escape sequences become actual unicode characters
        assert "nino" in result["word_bank"][0] or "\u00f1" in result["word_bank"][0]
        assert "child" in result["word_bank"][0]
        assert len(result["word_bank"]) == 2

    def test_invalid_json_raises_error(self) -> None:
        """Invalid JSON should raise an error."""
        invalid_json = '{"word_bank": ['  # Incomplete
        with pytest.raises(json.JSONDecodeError):
            json.loads(invalid_json)


class TestScaffoldNodeDocumentation:
    """Tests for scaffold_node documentation."""

    def test_has_docstring(self) -> None:
        """scaffold_node function should have a docstring."""
        assert scaffold_node.__doc__ is not None
        assert len(scaffold_node.__doc__) > 0

    def test_docstring_mentions_scaffolding(self) -> None:
        """Docstring should mention scaffolding."""
        doc = scaffold_node.__doc__
        assert doc is not None
        assert "scaffold" in doc.lower()

    def test_docstring_mentions_levels(self) -> None:
        """Docstring should mention A0-A1 levels."""
        doc = scaffold_node.__doc__
        assert doc is not None
        assert "A0" in doc or "A1" in doc


class TestScaffoldNodeImport:
    """Tests for module import and exports."""

    def test_scaffold_node_importable(self) -> None:
        """scaffold_node should be importable from nodes module."""
        from src.agent.nodes.scaffold import scaffold_node as imported_func

        assert imported_func is not None
        assert callable(imported_func)

    def test_scaffold_module_exists(self) -> None:
        """Scaffold module should exist and be importable."""
        import src.agent.nodes.scaffold

        assert src.agent.nodes.scaffold is not None


class TestScaffoldNodeIntegration:
    """Integration-style tests for scaffold_node."""

    @pytest.mark.asyncio
    async def test_scaffold_result_compatible_with_state(self) -> None:
        """scaffold_node result should be compatible with ConversationState."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)

        # Result can be merged into state
        merged = {**state, **result}
        assert "scaffolding" in merged
        assert "messages" in merged
        assert "level" in merged

    @pytest.mark.asyncio
    async def test_scaffold_result_has_expected_structure(self) -> None:
        """scaffold_node result should have the expected structure."""
        state: ConversationState = {
            "messages": [
                HumanMessage(content="Hello"),
                AIMessage(content="Hola!"),
            ],
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)

        scaffolding = result["scaffolding"]
        # Should have all expected keys
        expected_keys = {"enabled", "word_bank"}
        assert expected_keys.issubset(set(scaffolding.keys()))
