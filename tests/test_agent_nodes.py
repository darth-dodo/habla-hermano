"""Comprehensive tests for agent nodes: respond, feedback, and scaffold.

This module tests the three agent node functions that form the core of the
HablaAI conversation flow.
"""

import inspect
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.nodes.feedback import feedback_node
from src.agent.nodes.respond import _get_llm, respond_node
from src.agent.nodes.scaffold import scaffold_node

if TYPE_CHECKING:
    from src.agent.state import ConversationState
    from src.api.config import Settings


# =============================================================================
# _get_llm() TESTS
# =============================================================================


class TestGetLlmFunction:
    """Tests for _get_llm helper function."""

    def test_get_llm_returns_chat_anthropic(self, mock_settings: "Settings") -> None:
        """_get_llm should return a ChatAnthropic instance."""
        with patch("src.agent.nodes.respond.get_settings", return_value=mock_settings):
            with patch("src.agent.nodes.respond.ChatAnthropic") as mock_chat:
                mock_chat.return_value = MagicMock()
                result = _get_llm()
                assert result is not None
                mock_chat.assert_called_once()

    def test_get_llm_uses_settings_api_key(self, mock_settings: "Settings") -> None:
        """_get_llm should use API key from settings."""
        with patch("src.agent.nodes.respond.get_settings", return_value=mock_settings):
            with patch("src.agent.nodes.respond.ChatAnthropic") as mock_chat:
                mock_chat.return_value = MagicMock()
                _get_llm()
                call_kwargs = mock_chat.call_args[1]
                assert call_kwargs["api_key"] == mock_settings.ANTHROPIC_API_KEY

    def test_get_llm_uses_settings_model(self, mock_settings: "Settings") -> None:
        """_get_llm should use model from settings."""
        with patch("src.agent.nodes.respond.get_settings", return_value=mock_settings):
            with patch("src.agent.nodes.respond.ChatAnthropic") as mock_chat:
                mock_chat.return_value = MagicMock()
                _get_llm()
                call_kwargs = mock_chat.call_args[1]
                assert call_kwargs["model"] == mock_settings.LLM_MODEL

    def test_get_llm_uses_settings_temperature(self, mock_settings: "Settings") -> None:
        """_get_llm should use temperature from settings."""
        with patch("src.agent.nodes.respond.get_settings", return_value=mock_settings):
            with patch("src.agent.nodes.respond.ChatAnthropic") as mock_chat:
                mock_chat.return_value = MagicMock()
                _get_llm()
                call_kwargs = mock_chat.call_args[1]
                assert call_kwargs["temperature"] == mock_settings.LLM_TEMPERATURE


# =============================================================================
# respond_node() TESTS
# =============================================================================


class TestRespondNodeBasic:
    """Basic tests for respond_node function."""

    def test_respond_node_is_async(self) -> None:
        """respond_node should be an async function."""
        assert inspect.iscoroutinefunction(respond_node)

    @pytest.mark.asyncio
    async def test_respond_node_returns_dict(self, mock_settings: "Settings") -> None:
        """respond_node should return a dictionary."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))

        with patch("src.agent.nodes.respond.get_settings", return_value=mock_settings):
            with patch("src.agent.nodes.respond._get_llm", return_value=mock_llm):
                state: ConversationState = {
                    "messages": [HumanMessage(content="Hola!")],
                    "level": "A1",
                    "language": "es",
                }
                result = await respond_node(state)
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_respond_node_returns_messages_key(self, mock_settings: "Settings") -> None:
        """respond_node should return dict with 'messages' key."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))

        with patch("src.agent.nodes.respond.get_settings", return_value=mock_settings):
            with patch("src.agent.nodes.respond._get_llm", return_value=mock_llm):
                state: ConversationState = {
                    "messages": [HumanMessage(content="Hola!")],
                    "level": "A1",
                    "language": "es",
                }
                result = await respond_node(state)
                assert "messages" in result

    @pytest.mark.asyncio
    async def test_respond_node_messages_is_list(self, mock_settings: "Settings") -> None:
        """respond_node messages should be a list."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))

        with patch("src.agent.nodes.respond.get_settings", return_value=mock_settings):
            with patch("src.agent.nodes.respond._get_llm", return_value=mock_llm):
                state: ConversationState = {
                    "messages": [HumanMessage(content="Hola!")],
                    "level": "A1",
                    "language": "es",
                }
                result = await respond_node(state)
                assert isinstance(result["messages"], list)

    @pytest.mark.asyncio
    async def test_respond_node_returns_ai_message(self, mock_settings: "Settings") -> None:
        """respond_node should return AIMessage in messages list."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Hola amigo!"))

        with patch("src.agent.nodes.respond.get_settings", return_value=mock_settings):
            with patch("src.agent.nodes.respond._get_llm", return_value=mock_llm):
                state: ConversationState = {
                    "messages": [HumanMessage(content="Hola!")],
                    "level": "A1",
                    "language": "es",
                }
                result = await respond_node(state)
                assert len(result["messages"]) == 1
                assert isinstance(result["messages"][0], AIMessage)


class TestRespondNodeLevels:
    """Tests for respond_node with different levels."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    async def test_respond_node_handles_all_levels(
        self, level: str, mock_settings: "Settings"
    ) -> None:
        """respond_node should handle all valid CEFR levels."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))

        with patch("src.agent.nodes.respond.get_settings", return_value=mock_settings):
            with patch("src.agent.nodes.respond._get_llm", return_value=mock_llm):
                state: ConversationState = {
                    "messages": [HumanMessage(content="Hello")],
                    "level": level,
                    "language": "es",
                }
                result = await respond_node(state)
                assert isinstance(result, dict)
                assert "messages" in result

    @pytest.mark.asyncio
    async def test_respond_node_uses_level_for_prompt(self, mock_settings: "Settings") -> None:
        """respond_node should use the level to get appropriate prompt."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))

        with patch("src.agent.nodes.respond.get_settings", return_value=mock_settings):
            with patch("src.agent.nodes.respond._get_llm", return_value=mock_llm):
                with patch(
                    "src.agent.nodes.respond.get_prompt_for_level",
                    return_value="Test prompt",
                ) as mock_prompt:
                    state: ConversationState = {
                        "messages": [HumanMessage(content="Hello")],
                        "level": "A2",
                        "language": "es",
                    }
                    await respond_node(state)
                    mock_prompt.assert_called_once_with(language="es", level="A2")


class TestRespondNodeLanguages:
    """Tests for respond_node with different languages."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("language", ["es", "de"])
    async def test_respond_node_handles_supported_languages(
        self, language: str, mock_settings: "Settings"
    ) -> None:
        """respond_node should handle all supported languages."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))

        with patch("src.agent.nodes.respond.get_settings", return_value=mock_settings):
            with patch("src.agent.nodes.respond._get_llm", return_value=mock_llm):
                state: ConversationState = {
                    "messages": [HumanMessage(content="Hello")],
                    "level": "A1",
                    "language": language,
                }
                result = await respond_node(state)
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_respond_node_uses_language_for_prompt(self, mock_settings: "Settings") -> None:
        """respond_node should pass language to get_prompt_for_level."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))

        with patch("src.agent.nodes.respond.get_settings", return_value=mock_settings):
            with patch("src.agent.nodes.respond._get_llm", return_value=mock_llm):
                with patch(
                    "src.agent.nodes.respond.get_prompt_for_level",
                    return_value="German prompt",
                ) as mock_prompt:
                    state: ConversationState = {
                        "messages": [HumanMessage(content="Guten Tag")],
                        "level": "A1",
                        "language": "de",
                    }
                    await respond_node(state)
                    mock_prompt.assert_called_once_with(language="de", level="A1")


class TestRespondNodeConversationHistory:
    """Tests for respond_node with conversation history."""

    @pytest.mark.asyncio
    async def test_respond_node_handles_conversation_history(
        self, mock_settings: "Settings"
    ) -> None:
        """respond_node should handle full conversation history."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))

        with patch("src.agent.nodes.respond.get_settings", return_value=mock_settings):
            with patch("src.agent.nodes.respond._get_llm", return_value=mock_llm):
                state: ConversationState = {
                    "messages": [
                        HumanMessage(content="Hola!"),
                        AIMessage(content="Hola! Como estas?"),
                        HumanMessage(content="Bien, gracias"),
                    ],
                    "level": "A1",
                    "language": "es",
                }
                result = await respond_node(state)
                assert isinstance(result, dict)

                # Verify all messages are passed to LLM
                call_args = mock_llm.ainvoke.call_args[0][0]
                # Should have system message + 3 conversation messages
                assert len(call_args) == 4

    @pytest.mark.asyncio
    async def test_respond_node_preserves_message_order(self, mock_settings: "Settings") -> None:
        """respond_node should preserve message order in LLM call."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))

        msg1 = HumanMessage(content="First")
        msg2 = AIMessage(content="Second")
        msg3 = HumanMessage(content="Third")

        with patch("src.agent.nodes.respond.get_settings", return_value=mock_settings):
            with patch("src.agent.nodes.respond._get_llm", return_value=mock_llm):
                state: ConversationState = {
                    "messages": [msg1, msg2, msg3],
                    "level": "A1",
                    "language": "es",
                }
                await respond_node(state)

                call_args = mock_llm.ainvoke.call_args[0][0]
                # Messages should be in order after system message
                assert call_args[1] == msg1
                assert call_args[2] == msg2
                assert call_args[3] == msg3


# =============================================================================
# FEEDBACK NODE TESTS
# =============================================================================


class TestFeedbackNodeStructure:
    """Tests for feedback_node function structure."""

    def test_feedback_node_is_async(self) -> None:
        """feedback_node should be an async function."""
        assert inspect.iscoroutinefunction(feedback_node)

    @pytest.mark.asyncio
    async def test_feedback_node_returns_dict(self) -> None:
        """feedback_node should return a dictionary."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es",
        }
        result = await feedback_node(state)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_feedback_node_returns_formatted_feedback_key(self) -> None:
        """feedback_node should return dict with 'formatted_feedback' key."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es",
        }
        result = await feedback_node(state)
        assert "formatted_feedback" in result

    @pytest.mark.asyncio
    async def test_feedback_node_formatted_feedback_is_list(self) -> None:
        """formatted_feedback should be a list."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es",
        }
        result = await feedback_node(state)
        assert isinstance(result["formatted_feedback"], list)


class TestFeedbackNodeStubBehavior:
    """Tests for feedback_node stub implementation (Phase 1)."""

    @pytest.mark.asyncio
    async def test_stub_returns_empty_list(self) -> None:
        """Current stub should return empty formatted_feedback list."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Yo es estudiante")],
            "level": "A1",
            "language": "es",
        }
        result = await feedback_node(state)
        assert result["formatted_feedback"] == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    async def test_stub_returns_empty_for_all_levels(self, level: str) -> None:
        """Stub should return empty list for all CEFR levels."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Test message")],
            "level": level,
            "language": "es",
        }
        result = await feedback_node(state)
        assert result["formatted_feedback"] == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("language", ["es", "de", "fr"])
    async def test_stub_returns_empty_for_all_languages(self, language: str) -> None:
        """Stub should return empty list for all languages."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Test message")],
            "level": "A1",
            "language": language,
        }
        result = await feedback_node(state)
        assert result["formatted_feedback"] == []

    @pytest.mark.asyncio
    async def test_stub_handles_state_with_grammar_feedback(self) -> None:
        """Stub should handle state that includes grammar_feedback."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": "A1",
            "language": "es",
            "grammar_feedback": [
                {
                    "original": "Yo es",
                    "correction": "Yo soy",
                    "explanation": "Use soy with yo",
                    "severity": "moderate",
                }
            ],
        }
        result = await feedback_node(state)
        # Stub ignores grammar_feedback for now
        assert result["formatted_feedback"] == []


class TestFeedbackNodeEdgeCases:
    """Edge case tests for feedback_node."""

    @pytest.mark.asyncio
    async def test_handles_empty_messages(self) -> None:
        """feedback_node should handle empty messages list."""
        state: ConversationState = {
            "messages": [],
            "level": "A1",
            "language": "es",
        }
        result = await feedback_node(state)
        assert result["formatted_feedback"] == []

    @pytest.mark.asyncio
    async def test_handles_only_ai_messages(self) -> None:
        """feedback_node should handle state with only AI messages."""
        state: ConversationState = {
            "messages": [AIMessage(content="Hola!")],
            "level": "A1",
            "language": "es",
        }
        result = await feedback_node(state)
        assert result["formatted_feedback"] == []

    @pytest.mark.asyncio
    async def test_handles_long_conversation(self) -> None:
        """feedback_node should handle long conversation histories."""
        messages = []
        for i in range(20):
            messages.append(HumanMessage(content=f"Message {i}"))
            messages.append(AIMessage(content=f"Response {i}"))

        state: ConversationState = {
            "messages": messages,
            "level": "A1",
            "language": "es",
        }
        result = await feedback_node(state)
        assert isinstance(result["formatted_feedback"], list)


# =============================================================================
# SCAFFOLD NODE TESTS
# =============================================================================


class TestScaffoldNodeStructure:
    """Tests for scaffold_node function structure."""

    def test_scaffold_node_is_async(self) -> None:
        """scaffold_node should be an async function."""
        assert inspect.iscoroutinefunction(scaffold_node)

    @pytest.mark.asyncio
    async def test_scaffold_node_returns_dict(self) -> None:
        """scaffold_node should return a dictionary."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_scaffold_node_returns_scaffolding_key(self) -> None:
        """scaffold_node should return dict with 'scaffolding' key."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert "scaffolding" in result

    @pytest.mark.asyncio
    async def test_scaffold_node_scaffolding_is_dict(self) -> None:
        """scaffolding should be a dictionary."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert isinstance(result["scaffolding"], dict)


class TestScaffoldNodeBeginnerLevels:
    """Tests for scaffold_node with A0 and A1 levels."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A0", "A1"])
    async def test_scaffold_returns_disabled_for_beginners_without_ai_response(
        self, level: str
    ) -> None:
        """Scaffold should return disabled=False for A0/A1 without AI response."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": level,
            "language": "es",
        }
        result = await scaffold_node(state)
        # Without AI response, scaffold returns disabled
        assert result["scaffolding"]["enabled"] is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A0", "A1"])
    async def test_scaffold_has_word_bank_field(self, level: str) -> None:
        """A0/A1 scaffold should have word_bank field."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": level,
            "language": "es",
        }
        result = await scaffold_node(state)
        assert "word_bank" in result["scaffolding"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A0", "A1"])
    async def test_scaffold_has_empty_word_bank_without_ai_response(self, level: str) -> None:
        """A0/A1 scaffold should have empty word_bank list without AI response."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": level,
            "language": "es",
        }
        result = await scaffold_node(state)
        assert result["scaffolding"]["word_bank"] == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A0", "A1"])
    async def test_scaffold_has_hint_text_field(self, level: str) -> None:
        """A0/A1 scaffold should have hint_text field."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": level,
            "language": "es",
        }
        result = await scaffold_node(state)
        assert "hint_text" in result["scaffolding"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A0", "A1"])
    async def test_scaffold_has_empty_hint_text_without_ai_response(self, level: str) -> None:
        """A0/A1 scaffold should have empty hint_text without AI response."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": level,
            "language": "es",
        }
        result = await scaffold_node(state)
        assert result["scaffolding"]["hint_text"] == ""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A0", "A1"])
    async def test_scaffold_has_no_sentence_starter(self, level: str) -> None:
        """A0/A1 scaffold should have sentence_starter as None without AI response."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": level,
            "language": "es",
        }
        result = await scaffold_node(state)
        assert result["scaffolding"]["sentence_starter"] is None


class TestScaffoldNodeIntermediateLevels:
    """Tests for scaffold_node with A2 and B1 levels."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A2", "B1"])
    async def test_scaffold_disabled_for_intermediate(self, level: str) -> None:
        """A2/B1 should never get scaffolding enabled."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": level,
            "language": "es",
        }
        result = await scaffold_node(state)
        assert result["scaffolding"]["enabled"] is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A2", "B1"])
    async def test_scaffold_empty_word_bank_for_intermediate(self, level: str) -> None:
        """A2/B1 should have empty word bank."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": level,
            "language": "es",
        }
        result = await scaffold_node(state)
        assert result["scaffolding"]["word_bank"] == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A2", "B1"])
    async def test_scaffold_empty_hints_for_intermediate(self, level: str) -> None:
        """A2/B1 should have empty hint_text."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": level,
            "language": "es",
        }
        result = await scaffold_node(state)
        assert result["scaffolding"]["hint_text"] == ""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A2", "B1"])
    async def test_scaffold_no_sentence_starter_for_intermediate(self, level: str) -> None:
        """A2/B1 should have no sentence starter."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola!")],
            "level": level,
            "language": "es",
        }
        result = await scaffold_node(state)
        assert result["scaffolding"]["sentence_starter"] is None


class TestScaffoldNodeAllLevels:
    """Tests for scaffold_node across all levels."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    async def test_scaffold_structure_consistent(self, level: str) -> None:
        """All levels should return consistent scaffolding structure."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": level,
            "language": "es",
        }
        result = await scaffold_node(state)

        scaffolding = result["scaffolding"]
        # All levels should have these keys (Phase 3 Pydantic model fields)
        assert "enabled" in scaffolding
        assert "word_bank" in scaffolding
        assert "hint_text" in scaffolding
        assert "sentence_starter" in scaffolding
        assert "auto_expand" in scaffolding

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    async def test_scaffold_returns_correct_types(self, level: str) -> None:
        """Scaffolding fields should have correct types."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": level,
            "language": "es",
        }
        result = await scaffold_node(state)

        scaffolding = result["scaffolding"]
        assert isinstance(scaffolding["enabled"], bool)
        assert isinstance(scaffolding["word_bank"], list)
        assert isinstance(scaffolding["hint_text"], str)
        assert isinstance(scaffolding["auto_expand"], bool)
        # sentence_starter can be None or str
        assert scaffolding["sentence_starter"] is None or isinstance(
            scaffolding["sentence_starter"], str
        )


class TestScaffoldNodeEdgeCases:
    """Edge case tests for scaffold_node."""

    @pytest.mark.asyncio
    async def test_handles_empty_messages(self) -> None:
        """scaffold_node should handle empty messages list."""
        state: ConversationState = {
            "messages": [],
            "level": "A1",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert "scaffolding" in result

    @pytest.mark.asyncio
    async def test_handles_unknown_level(self) -> None:
        """scaffold_node should handle unknown level (goes to A2/B1 branch)."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": "C2",  # Unknown level
            "language": "es",
        }
        result = await scaffold_node(state)
        # Unknown level should return disabled scaffolding (A2/B1 path)
        assert result["scaffolding"]["enabled"] is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize("language", ["es", "de", "fr"])
    async def test_handles_all_languages(self, language: str) -> None:
        """scaffold_node should handle all languages."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": "A1",
            "language": language,
        }
        result = await scaffold_node(state)
        assert "scaffolding" in result

    @pytest.mark.asyncio
    async def test_handles_long_conversation_history(self) -> None:
        """scaffold_node should handle long conversation histories."""
        messages = []
        for i in range(50):
            messages.append(HumanMessage(content=f"User {i}"))
            messages.append(AIMessage(content=f"AI {i}"))

        state: ConversationState = {
            "messages": messages,
            "level": "A0",
            "language": "es",
        }
        result = await scaffold_node(state)
        assert "scaffolding" in result


class TestScaffoldNodePhaseDocumentation:
    """Tests verifying Phase 3 stub documentation."""

    @pytest.mark.asyncio
    async def test_a0_a1_path_executed(self) -> None:
        """Verify A0/A1 conditional path is executed."""
        state_a0: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": "A0",
            "language": "es",
        }
        state_a1: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": "A1",
            "language": "es",
        }

        result_a0 = await scaffold_node(state_a0)
        result_a1 = await scaffold_node(state_a1)

        # Both should return same structure (stub)
        assert result_a0["scaffolding"] == result_a1["scaffolding"]

    @pytest.mark.asyncio
    async def test_a2_b1_path_executed(self) -> None:
        """Verify A2/B1 conditional path is executed."""
        state_a2: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": "A2",
            "language": "es",
        }
        state_b1: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": "B1",
            "language": "es",
        }

        result_a2 = await scaffold_node(state_a2)
        result_b1 = await scaffold_node(state_b1)

        # Both should return same structure
        assert result_a2["scaffolding"] == result_b1["scaffolding"]

    @pytest.mark.asyncio
    async def test_both_paths_return_same_structure_in_stub(self) -> None:
        """In stub, both A0/A1 and A2/B1 paths return identical disabled scaffolding."""
        state_a0: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": "A0",
            "language": "es",
        }
        state_b1: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": "B1",
            "language": "es",
        }

        result_a0 = await scaffold_node(state_a0)
        result_b1 = await scaffold_node(state_b1)

        # Stub returns same disabled scaffolding for all levels
        assert result_a0["scaffolding"] == result_b1["scaffolding"]


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestNodeIntegration:
    """Integration tests for node module imports and relationships."""

    def test_respond_node_importable(self) -> None:
        """respond_node should be importable from module."""
        from src.agent.nodes.respond import respond_node

        assert respond_node is not None
        assert callable(respond_node)

    def test_feedback_node_importable(self) -> None:
        """feedback_node should be importable from module."""
        from src.agent.nodes.feedback import feedback_node

        assert feedback_node is not None
        assert callable(feedback_node)

    def test_scaffold_node_importable(self) -> None:
        """scaffold_node should be importable from module."""
        from src.agent.nodes.scaffold import scaffold_node

        assert scaffold_node is not None
        assert callable(scaffold_node)

    def test_get_llm_helper_importable(self) -> None:
        """_get_llm helper should be importable from respond module."""
        from src.agent.nodes.respond import _get_llm

        assert _get_llm is not None
        assert callable(_get_llm)

    def test_all_nodes_are_async(self) -> None:
        """All node functions should be async."""
        from src.agent.nodes.feedback import feedback_node
        from src.agent.nodes.respond import respond_node
        from src.agent.nodes.scaffold import scaffold_node

        assert inspect.iscoroutinefunction(respond_node)
        assert inspect.iscoroutinefunction(feedback_node)
        assert inspect.iscoroutinefunction(scaffold_node)
