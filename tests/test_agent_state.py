"""
Tests for the ConversationState TypedDict.

This module tests the structure and behavior of the conversation state
used by the LangGraph conversation flow.
"""

from typing import get_type_hints

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph.message import add_messages

from src.agent.state import ConversationState


class TestConversationStateStructure:
    """Tests for ConversationState TypedDict structure."""

    def test_state_has_messages_field(self) -> None:
        """ConversationState should have a messages field."""
        hints = get_type_hints(ConversationState, include_extras=True)
        assert "messages" in hints

    def test_state_has_level_field(self) -> None:
        """ConversationState should have a level field."""
        hints = get_type_hints(ConversationState, include_extras=True)
        assert "level" in hints

    def test_state_has_language_field(self) -> None:
        """ConversationState should have a language field."""
        hints = get_type_hints(ConversationState, include_extras=True)
        assert "language" in hints

    def test_state_has_exactly_three_fields(self) -> None:
        """ConversationState should have exactly three fields for Phase 1."""
        hints = get_type_hints(ConversationState, include_extras=True)
        assert len(hints) == 3

    def test_level_field_is_string(self) -> None:
        """Level field should be typed as str."""
        hints = get_type_hints(ConversationState, include_extras=False)
        assert hints["level"] is str

    def test_language_field_is_string(self) -> None:
        """Language field should be typed as str."""
        hints = get_type_hints(ConversationState, include_extras=False)
        assert hints["language"] is str


class TestConversationStateCreation:
    """Tests for creating ConversationState instances."""

    def test_create_empty_state(self) -> None:
        """Should be able to create a state with empty messages."""
        state: ConversationState = {
            "messages": [],
            "level": "A1",
            "language": "es",
        }
        assert state["messages"] == []
        assert state["level"] == "A1"
        assert state["language"] == "es"

    def test_create_state_with_human_message(self) -> None:
        """Should be able to create a state with a HumanMessage."""
        message = HumanMessage(content="Hola!")
        state: ConversationState = {
            "messages": [message],
            "level": "A1",
            "language": "es",
        }
        assert len(state["messages"]) == 1
        assert isinstance(state["messages"][0], HumanMessage)
        assert state["messages"][0].content == "Hola!"

    def test_create_state_with_ai_message(self) -> None:
        """Should be able to create a state with an AIMessage."""
        message = AIMessage(content="Buenos dias!")
        state: ConversationState = {
            "messages": [message],
            "level": "A1",
            "language": "es",
        }
        assert len(state["messages"]) == 1
        assert isinstance(state["messages"][0], AIMessage)

    def test_create_state_with_conversation_history(self) -> None:
        """Should be able to create a state with multiple messages."""
        messages: list[BaseMessage] = [
            HumanMessage(content="Hola!"),
            AIMessage(content="Hola! Como estas?"),
            HumanMessage(content="Muy bien, gracias"),
        ]
        state: ConversationState = {
            "messages": messages,
            "level": "A1",
            "language": "es",
        }
        assert len(state["messages"]) == 3

    @pytest.mark.parametrize(
        "level",
        ["A0", "A1", "A2", "B1"],
    )
    def test_create_state_with_valid_levels(self, level: str) -> None:
        """Should be able to create states with all valid CEFR levels."""
        state: ConversationState = {
            "messages": [],
            "level": level,
            "language": "es",
        }
        assert state["level"] == level

    @pytest.mark.parametrize(
        "language",
        ["es", "de"],
    )
    def test_create_state_with_valid_languages(self, language: str) -> None:
        """Should be able to create states with all supported languages."""
        state: ConversationState = {
            "messages": [],
            "level": "A1",
            "language": language,
        }
        assert state["language"] == language


class TestMessagesReducerBehavior:
    """Tests for the add_messages reducer behavior with ConversationState."""

    def test_add_messages_reducer_exists(self) -> None:
        """The messages field should use the add_messages reducer."""
        hints = get_type_hints(ConversationState, include_extras=True)
        messages_type = hints["messages"]
        # Check that it's an Annotated type with add_messages
        assert hasattr(messages_type, "__metadata__")
        assert add_messages in messages_type.__metadata__

    def test_add_messages_appends_new_message(self) -> None:
        """The add_messages reducer should append new messages to existing list."""
        existing: list[BaseMessage] = [HumanMessage(content="Hello")]
        new: list[BaseMessage] = [AIMessage(content="Hi there!")]

        # Simulate what the reducer does
        result = add_messages(existing, new)

        assert len(result) == 2
        assert isinstance(result[0], HumanMessage)
        assert isinstance(result[1], AIMessage)

    def test_add_messages_with_multiple_new_messages(self) -> None:
        """The add_messages reducer should append multiple new messages."""
        existing: list[BaseMessage] = [HumanMessage(content="Hello")]
        new: list[BaseMessage] = [
            AIMessage(content="Hi!"),
            HumanMessage(content="How are you?"),
        ]

        result = add_messages(existing, new)

        assert len(result) == 3

    def test_add_messages_to_empty_list(self) -> None:
        """The add_messages reducer should work with an empty existing list."""
        existing: list[BaseMessage] = []
        new: list[BaseMessage] = [HumanMessage(content="First message")]

        result = add_messages(existing, new)

        assert len(result) == 1
        assert result[0].content == "First message"

    def test_add_messages_preserves_message_order(self) -> None:
        """The add_messages reducer should preserve chronological order."""
        existing: list[BaseMessage] = [
            HumanMessage(content="1"),
            AIMessage(content="2"),
        ]
        new: list[BaseMessage] = [
            HumanMessage(content="3"),
            AIMessage(content="4"),
        ]

        result = add_messages(existing, new)

        contents = [m.content for m in result]
        assert contents == ["1", "2", "3", "4"]


class TestConversationStateEdgeCases:
    """Edge case tests for ConversationState."""

    def test_state_with_empty_strings(self) -> None:
        """State should accept empty strings (though not recommended)."""
        state: ConversationState = {
            "messages": [],
            "level": "",
            "language": "",
        }
        assert state["level"] == ""
        assert state["language"] == ""

    def test_state_with_unknown_level(self) -> None:
        """State should accept any string for level (TypedDict is not runtime validated)."""
        state: ConversationState = {
            "messages": [],
            "level": "C2",  # Not a supported level
            "language": "es",
        }
        assert state["level"] == "C2"

    def test_state_with_unknown_language(self) -> None:
        """State should accept any string for language (TypedDict is not runtime validated)."""
        state: ConversationState = {
            "messages": [],
            "level": "A1",
            "language": "fr",  # Not currently supported
        }
        assert state["language"] == "fr"

    def test_state_messages_can_have_empty_content(self) -> None:
        """State should accept messages with empty content."""
        state: ConversationState = {
            "messages": [HumanMessage(content="")],
            "level": "A1",
            "language": "es",
        }
        assert state["messages"][0].content == ""

    def test_state_is_dictionary_like(self) -> None:
        """ConversationState should behave like a dictionary."""
        state: ConversationState = {
            "messages": [],
            "level": "A1",
            "language": "es",
        }
        # Test dictionary operations
        assert "level" in state
        assert list(state.keys()) == ["messages", "level", "language"]
        assert len(state) == 3
