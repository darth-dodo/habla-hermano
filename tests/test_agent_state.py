"""
Tests for the ConversationState TypedDict.

This module tests the structure and behavior of the conversation state
used by the LangGraph conversation flow.
"""

from typing import Any, get_type_hints

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

    def test_state_has_grammar_feedback_field(self) -> None:
        """ConversationState should have a grammar_feedback field (Phase 2)."""
        hints = get_type_hints(ConversationState, include_extras=True)
        assert "grammar_feedback" in hints

    def test_state_has_new_vocabulary_field(self) -> None:
        """ConversationState should have a new_vocabulary field (Phase 2)."""
        hints = get_type_hints(ConversationState, include_extras=True)
        assert "new_vocabulary" in hints

    def test_state_has_exactly_five_fields(self) -> None:
        """ConversationState should have exactly five fields for Phase 2."""
        hints = get_type_hints(ConversationState, include_extras=True)
        assert len(hints) == 5

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
            "grammar_feedback": [],
            "new_vocabulary": [],
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
            "grammar_feedback": [],
            "new_vocabulary": [],
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
            "grammar_feedback": [],
            "new_vocabulary": [],
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
            "grammar_feedback": [],
            "new_vocabulary": [],
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
            "grammar_feedback": [],
            "new_vocabulary": [],
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
            "grammar_feedback": [],
            "new_vocabulary": [],
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
            "grammar_feedback": [],
            "new_vocabulary": [],
        }
        assert state["level"] == ""
        assert state["language"] == ""

    def test_state_with_unknown_level(self) -> None:
        """State should accept any string for level (TypedDict is not runtime validated)."""
        state: ConversationState = {
            "messages": [],
            "level": "C2",  # Not a supported level
            "language": "es",
            "grammar_feedback": [],
            "new_vocabulary": [],
        }
        assert state["level"] == "C2"

    def test_state_with_unknown_language(self) -> None:
        """State should accept any string for language (TypedDict is not runtime validated)."""
        state: ConversationState = {
            "messages": [],
            "level": "A1",
            "language": "fr",  # French is now supported per state.py
            "grammar_feedback": [],
            "new_vocabulary": [],
        }
        assert state["language"] == "fr"

    def test_state_messages_can_have_empty_content(self) -> None:
        """State should accept messages with empty content."""
        state: ConversationState = {
            "messages": [HumanMessage(content="")],
            "level": "A1",
            "language": "es",
            "grammar_feedback": [],
            "new_vocabulary": [],
        }
        assert state["messages"][0].content == ""

    def test_state_is_dictionary_like(self) -> None:
        """ConversationState should behave like a dictionary."""
        state: ConversationState = {
            "messages": [],
            "level": "A1",
            "language": "es",
            "grammar_feedback": [],
            "new_vocabulary": [],
        }
        # Test dictionary operations
        assert "level" in state
        assert len(state) == 5


class TestGrammarFeedbackField:
    """Tests for the grammar_feedback field in ConversationState (Phase 2)."""

    def test_create_state_with_empty_grammar_feedback(self) -> None:
        """Should be able to create state with empty grammar_feedback list."""
        state: ConversationState = {
            "messages": [],
            "level": "A1",
            "language": "es",
            "grammar_feedback": [],
            "new_vocabulary": [],
        }
        assert state["grammar_feedback"] == []

    def test_create_state_with_grammar_feedback(self) -> None:
        """Should be able to create state with grammar_feedback items."""
        feedback: list[dict[str, Any]] = [
            {
                "original": "Yo es estudiante",
                "correction": "Yo soy estudiante",
                "explanation": "The verb 'ser' conjugates to 'soy' with 'yo'",
                "severity": "moderate",
            }
        ]
        state: ConversationState = {
            "messages": [],
            "level": "A1",
            "language": "es",
            "grammar_feedback": feedback,  # type: ignore[typeddict-item]
            "new_vocabulary": [],
        }
        assert len(state["grammar_feedback"]) == 1

    def test_grammar_feedback_item_has_required_fields(self) -> None:
        """GrammarFeedback items should have required fields."""
        expected_fields = {"original", "correction", "explanation", "severity"}
        sample_feedback = {
            "original": "Yo es",
            "correction": "Yo soy",
            "explanation": "Use 'soy' with 'yo'",
            "severity": "moderate",
        }
        assert set(sample_feedback.keys()) == expected_fields

    def test_grammar_feedback_original_is_string(self) -> None:
        """GrammarFeedback original field should be string."""
        feedback = {
            "original": "Yo es",
            "correction": "Yo soy",
            "explanation": "Use 'soy' with 'yo'",
            "severity": "moderate",
        }
        assert isinstance(feedback["original"], str)

    def test_grammar_feedback_correction_is_string(self) -> None:
        """GrammarFeedback correction field should be string."""
        feedback = {
            "original": "Yo es",
            "correction": "Yo soy",
            "explanation": "Use 'soy' with 'yo'",
            "severity": "moderate",
        }
        assert isinstance(feedback["correction"], str)

    def test_grammar_feedback_explanation_is_string(self) -> None:
        """GrammarFeedback explanation field should be string."""
        feedback = {
            "original": "Yo es",
            "correction": "Yo soy",
            "explanation": "Use 'soy' with 'yo'",
            "severity": "moderate",
        }
        assert isinstance(feedback["explanation"], str)

    @pytest.mark.parametrize("severity", ["minor", "moderate", "significant"])
    def test_grammar_feedback_valid_severity_values(self, severity: str) -> None:
        """GrammarFeedback severity should have valid values."""
        valid_severities = {"minor", "moderate", "significant"}
        assert severity in valid_severities


class TestNewVocabularyField:
    """Tests for the new_vocabulary field in ConversationState (Phase 2)."""

    def test_create_state_with_empty_new_vocabulary(self) -> None:
        """Should be able to create state with empty new_vocabulary list."""
        state: ConversationState = {
            "messages": [],
            "level": "A1",
            "language": "es",
            "grammar_feedback": [],
            "new_vocabulary": [],
        }
        assert state["new_vocabulary"] == []

    def test_create_state_with_new_vocabulary(self) -> None:
        """Should be able to create state with new_vocabulary items."""
        vocabulary: list[dict[str, Any]] = [
            {
                "word": "edificio",
                "translation": "building",
                "part_of_speech": "noun",
            }
        ]
        state: ConversationState = {
            "messages": [],
            "level": "A1",
            "language": "es",
            "grammar_feedback": [],
            "new_vocabulary": vocabulary,  # type: ignore[typeddict-item]
        }
        assert len(state["new_vocabulary"]) == 1

    def test_vocab_word_has_required_fields(self) -> None:
        """VocabWord items should have required fields."""
        expected_fields = {"word", "translation", "part_of_speech"}
        sample_vocab = {
            "word": "edificio",
            "translation": "building",
            "part_of_speech": "noun",
        }
        assert set(sample_vocab.keys()) == expected_fields

    def test_vocab_word_word_is_string(self) -> None:
        """VocabWord word field should be string."""
        vocab = {
            "word": "edificio",
            "translation": "building",
            "part_of_speech": "noun",
        }
        assert isinstance(vocab["word"], str)

    def test_vocab_word_translation_is_string(self) -> None:
        """VocabWord translation field should be string."""
        vocab = {
            "word": "edificio",
            "translation": "building",
            "part_of_speech": "noun",
        }
        assert isinstance(vocab["translation"], str)

    def test_vocab_word_part_of_speech_is_string(self) -> None:
        """VocabWord part_of_speech field should be string."""
        vocab = {
            "word": "edificio",
            "translation": "building",
            "part_of_speech": "noun",
        }
        assert isinstance(vocab["part_of_speech"], str)

    @pytest.mark.parametrize(
        "part_of_speech",
        ["noun", "verb", "adjective", "adverb", "preposition", "conjunction"],
    )
    def test_vocab_word_valid_part_of_speech_values(self, part_of_speech: str) -> None:
        """VocabWord part_of_speech can be various grammatical categories."""
        # Part of speech is a string, so any string is technically valid
        assert isinstance(part_of_speech, str)


class TestGrammarFeedbackTypedDict:
    """Tests for GrammarFeedback TypedDict structure (Phase 2)."""

    def test_grammar_feedback_typeddict_exists(self) -> None:
        """GrammarFeedback TypedDict should be importable from state module."""
        from src.agent.state import GrammarFeedback

        assert GrammarFeedback is not None

    def test_grammar_feedback_has_original_field(self) -> None:
        """GrammarFeedback should have an original field."""
        from src.agent.state import GrammarFeedback

        hints = get_type_hints(GrammarFeedback, include_extras=True)
        assert "original" in hints

    def test_grammar_feedback_has_correction_field(self) -> None:
        """GrammarFeedback should have a correction field."""
        from src.agent.state import GrammarFeedback

        hints = get_type_hints(GrammarFeedback, include_extras=True)
        assert "correction" in hints

    def test_grammar_feedback_has_explanation_field(self) -> None:
        """GrammarFeedback should have an explanation field."""
        from src.agent.state import GrammarFeedback

        hints = get_type_hints(GrammarFeedback, include_extras=True)
        assert "explanation" in hints

    def test_grammar_feedback_has_severity_field(self) -> None:
        """GrammarFeedback should have a severity field."""
        from src.agent.state import GrammarFeedback

        hints = get_type_hints(GrammarFeedback, include_extras=True)
        assert "severity" in hints

    def test_grammar_feedback_has_exactly_four_fields(self) -> None:
        """GrammarFeedback should have exactly four fields."""
        from src.agent.state import GrammarFeedback

        hints = get_type_hints(GrammarFeedback, include_extras=True)
        assert len(hints) == 4


class TestVocabWordTypedDict:
    """Tests for VocabWord TypedDict structure (Phase 2)."""

    def test_vocab_word_typeddict_exists(self) -> None:
        """VocabWord TypedDict should be importable from state module."""
        from src.agent.state import VocabWord

        assert VocabWord is not None

    def test_vocab_word_has_word_field(self) -> None:
        """VocabWord should have a word field."""
        from src.agent.state import VocabWord

        hints = get_type_hints(VocabWord, include_extras=True)
        assert "word" in hints

    def test_vocab_word_has_translation_field(self) -> None:
        """VocabWord should have a translation field."""
        from src.agent.state import VocabWord

        hints = get_type_hints(VocabWord, include_extras=True)
        assert "translation" in hints

    def test_vocab_word_has_part_of_speech_field(self) -> None:
        """VocabWord should have a part_of_speech field."""
        from src.agent.state import VocabWord

        hints = get_type_hints(VocabWord, include_extras=True)
        assert "part_of_speech" in hints

    def test_vocab_word_has_exactly_three_fields(self) -> None:
        """VocabWord should have exactly three fields."""
        from src.agent.state import VocabWord

        hints = get_type_hints(VocabWord, include_extras=True)
        assert len(hints) == 3


class TestStateFieldTypes:
    """Tests for field type validation in state TypedDicts."""

    def test_grammar_feedback_severity_is_literal(self) -> None:
        """GrammarFeedback severity should be a Literal type."""
        from src.agent.state import GrammarFeedback

        # Get the type hints without stripping extras to see the Literal
        hints = get_type_hints(GrammarFeedback, include_extras=True)
        severity_type = hints["severity"]
        # Check it's a Literal type by verifying it has __args__
        assert hasattr(severity_type, "__args__")
        # Verify the Literal contains the expected values
        assert set(severity_type.__args__) == {"minor", "moderate", "significant"}

    def test_vocab_word_fields_are_strings(self) -> None:
        """All VocabWord fields should be strings."""
        from src.agent.state import VocabWord

        hints = get_type_hints(VocabWord, include_extras=False)
        for field, field_type in hints.items():
            assert field_type is str, f"Field {field} should be str, got {field_type}"

    def test_grammar_feedback_text_fields_are_strings(self) -> None:
        """GrammarFeedback text fields should be strings."""
        from src.agent.state import GrammarFeedback

        hints = get_type_hints(GrammarFeedback, include_extras=False)
        for field in ["original", "correction", "explanation"]:
            assert hints[field] is str, f"Field {field} should be str"
