"""
Tests for routing functions in LangGraph conditional edges.

This module tests the needs_scaffolding routing function that determines
whether a conversation should flow through the scaffold node (for A0-A1)
or skip directly to analyze (for A2-B1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.routing import needs_scaffolding

if TYPE_CHECKING:
    from src.agent.state import ConversationState


class TestNeedsScaffoldingBasicRouting:
    """Tests for basic level-based routing."""

    def test_a0_routes_to_scaffold(self) -> None:
        """A0 level should route to scaffold node."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A0",
            "language": "es",
        }
        assert needs_scaffolding(state) == "scaffold"

    def test_a1_routes_to_scaffold(self) -> None:
        """A1 level should route to scaffold node."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A1",
            "language": "es",
        }
        assert needs_scaffolding(state) == "scaffold"

    def test_a2_routes_to_analyze(self) -> None:
        """A2 level should skip scaffold, go to analyze."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A2",
            "language": "es",
        }
        assert needs_scaffolding(state) == "analyze"

    def test_b1_routes_to_analyze(self) -> None:
        """B1 level should skip scaffold, go to analyze."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "B1",
            "language": "es",
        }
        assert needs_scaffolding(state) == "analyze"


class TestNeedsScaffoldingAllLevels:
    """Parametrized tests for all CEFR levels."""

    @pytest.mark.parametrize(
        "level,expected",
        [
            ("A0", "scaffold"),
            ("A1", "scaffold"),
            ("A2", "analyze"),
            ("B1", "analyze"),
            ("B2", "analyze"),
            ("C1", "analyze"),
            ("C2", "analyze"),
            ("", "analyze"),
        ],
    )
    def test_level_routing_parametrized(self, level: str, expected: str) -> None:
        """Parametrized test for all level routing."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": level,
            "language": "es",
        }
        assert needs_scaffolding(state) == expected


class TestNeedsScaffoldingCaseSensitivity:
    """Tests for case sensitivity in level matching."""

    def test_lowercase_a0_routes_to_analyze(self) -> None:
        """Lowercase 'a0' should NOT match 'A0', routes to analyze."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": "a0",
            "language": "es",
        }
        # Level matching is case-sensitive, lowercase not in ["A0", "A1"]
        assert needs_scaffolding(state) == "analyze"

    def test_lowercase_a1_routes_to_analyze(self) -> None:
        """Lowercase 'a1' should NOT match 'A1', routes to analyze."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": "a1",
            "language": "es",
        }
        assert needs_scaffolding(state) == "analyze"

    def test_mixed_case_routes_to_analyze(self) -> None:
        """Mixed case levels should NOT match, routes to analyze."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": "a0",  # Mixed/lowercase
            "language": "es",
        }
        assert needs_scaffolding(state) == "analyze"

    @pytest.mark.parametrize(
        "invalid_level",
        ["a0", "a1", "A 0", "A_0", "level-a0", "0", "1", "beginner"],
    )
    def test_invalid_level_formats_route_to_analyze(self, invalid_level: str) -> None:
        """Invalid level formats should route to analyze (fallback)."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": invalid_level,
            "language": "es",
        }
        assert needs_scaffolding(state) == "analyze"


class TestNeedsScaffoldingDifferentLanguages:
    """Tests for routing with different target languages."""

    def test_spanish_a0_routes_to_scaffold(self) -> None:
        """Spanish A0 should route to scaffold."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola")],
            "level": "A0",
            "language": "es",
        }
        assert needs_scaffolding(state) == "scaffold"

    def test_german_a0_routes_to_scaffold(self) -> None:
        """German A0 should also route to scaffold."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hallo")],
            "level": "A0",
            "language": "de",
        }
        assert needs_scaffolding(state) == "scaffold"

    def test_french_a1_routes_to_scaffold(self) -> None:
        """French A1 should route to scaffold."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Bonjour")],
            "level": "A1",
            "language": "fr",
        }
        assert needs_scaffolding(state) == "scaffold"

    def test_german_b1_routes_to_analyze(self) -> None:
        """German B1 should route to analyze."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Wie geht es Ihnen?")],
            "level": "B1",
            "language": "de",
        }
        assert needs_scaffolding(state) == "analyze"

    @pytest.mark.parametrize("language", ["es", "de", "fr", "it", "pt", "ru", "ja"])
    def test_a0_scaffolds_for_all_languages(self, language: str) -> None:
        """A0 level should route to scaffold regardless of language."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "A0",
            "language": language,
        }
        assert needs_scaffolding(state) == "scaffold"

    @pytest.mark.parametrize("language", ["es", "de", "fr", "it", "pt", "ru", "ja"])
    def test_b1_analyzes_for_all_languages(self, language: str) -> None:
        """B1 level should route to analyze regardless of language."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hello")],
            "level": "B1",
            "language": language,
        }
        assert needs_scaffolding(state) == "analyze"


class TestNeedsScaffoldingWithConversationHistory:
    """Tests for routing with various conversation histories."""

    def test_routes_with_empty_messages(self) -> None:
        """Routing should work with empty messages list."""
        state: ConversationState = {
            "messages": [],
            "level": "A0",
            "language": "es",
        }
        assert needs_scaffolding(state) == "scaffold"

    def test_routes_with_single_message(self) -> None:
        """Routing should work with single message."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Hola")],
            "level": "A1",
            "language": "es",
        }
        assert needs_scaffolding(state) == "scaffold"

    def test_routes_with_full_conversation(self) -> None:
        """Routing should work with full conversation history."""
        state: ConversationState = {
            "messages": [
                HumanMessage(content="Hola"),
                AIMessage(content="Hola! Como estas?"),
                HumanMessage(content="Bien, gracias"),
                AIMessage(content="Me alegro!"),
            ],
            "level": "A0",
            "language": "es",
        }
        assert needs_scaffolding(state) == "scaffold"

    def test_routes_with_long_conversation(self) -> None:
        """Routing should work with long conversation history."""
        messages = []
        for i in range(20):
            messages.append(HumanMessage(content=f"User message {i}"))
            messages.append(AIMessage(content=f"AI response {i}"))

        state: ConversationState = {
            "messages": messages,
            "level": "A2",
            "language": "es",
        }
        assert needs_scaffolding(state) == "analyze"


class TestNeedsScaffoldingReturnType:
    """Tests for return type correctness."""

    def test_returns_string(self) -> None:
        """needs_scaffolding should return a string."""
        state: ConversationState = {
            "messages": [],
            "level": "A0",
            "language": "es",
        }
        result = needs_scaffolding(state)
        assert isinstance(result, str)

    def test_returns_literal_scaffold(self) -> None:
        """Should return exactly 'scaffold' for A0-A1."""
        state: ConversationState = {
            "messages": [],
            "level": "A0",
            "language": "es",
        }
        result = needs_scaffolding(state)
        assert result == "scaffold"

    def test_returns_literal_analyze(self) -> None:
        """Should return exactly 'analyze' for A2-B1."""
        state: ConversationState = {
            "messages": [],
            "level": "A2",
            "language": "es",
        }
        result = needs_scaffolding(state)
        assert result == "analyze"

    def test_only_two_possible_return_values(self) -> None:
        """Function should only return 'scaffold' or 'analyze'."""
        levels = ["A0", "A1", "A2", "B1", "B2", "C1", "C2", "", "invalid"]
        valid_returns = {"scaffold", "analyze"}

        for level in levels:
            state: ConversationState = {
                "messages": [],
                "level": level,
                "language": "es",
            }
            result = needs_scaffolding(state)
            assert result in valid_returns, f"Unexpected return value for level {level}: {result}"


class TestNeedsScaffoldingFunctionProperties:
    """Tests for function properties and behavior."""

    def test_is_pure_function(self) -> None:
        """needs_scaffolding should be a pure function (same input -> same output)."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": "A0",
            "language": "es",
        }

        result1 = needs_scaffolding(state)
        result2 = needs_scaffolding(state)
        result3 = needs_scaffolding(state)

        assert result1 == result2 == result3

    def test_does_not_modify_state(self) -> None:
        """needs_scaffolding should not modify the input state."""
        state: ConversationState = {
            "messages": [HumanMessage(content="Test")],
            "level": "A0",
            "language": "es",
        }
        original_level = state["level"]
        original_language = state["language"]
        original_messages_len = len(state["messages"])

        needs_scaffolding(state)

        assert state["level"] == original_level
        assert state["language"] == original_language
        assert len(state["messages"]) == original_messages_len

    def test_is_synchronous(self) -> None:
        """needs_scaffolding should be a synchronous function."""
        import asyncio
        import inspect

        assert not inspect.iscoroutinefunction(needs_scaffolding)
        assert not asyncio.iscoroutinefunction(needs_scaffolding)

    def test_callable(self) -> None:
        """needs_scaffolding should be callable."""
        assert callable(needs_scaffolding)


class TestNeedsScaffoldingEdgeCases:
    """Edge case tests for routing function."""

    def test_handles_extra_state_fields(self) -> None:
        """Routing should work with extra fields in state."""
        # ConversationState might have optional fields
        state: ConversationState = {
            "messages": [],
            "level": "A0",
            "language": "es",
            "grammar_feedback": [],
            "new_vocabulary": [],
        }
        assert needs_scaffolding(state) == "scaffold"

    def test_level_comparison_uses_list(self) -> None:
        """Verify level comparison uses list membership."""
        # Testing the implementation detail that ["A0", "A1"] is used
        state_a0: ConversationState = {
            "messages": [],
            "level": "A0",
            "language": "es",
        }
        state_a1: ConversationState = {
            "messages": [],
            "level": "A1",
            "language": "es",
        }
        state_a2: ConversationState = {
            "messages": [],
            "level": "A2",
            "language": "es",
        }

        assert needs_scaffolding(state_a0) == "scaffold"
        assert needs_scaffolding(state_a1) == "scaffold"
        assert needs_scaffolding(state_a2) == "analyze"


class TestNeedsScaffoldingDocumentation:
    """Tests for function documentation."""

    def test_has_docstring(self) -> None:
        """needs_scaffolding should have a docstring."""
        assert needs_scaffolding.__doc__ is not None
        assert len(needs_scaffolding.__doc__) > 0

    def test_docstring_mentions_levels(self) -> None:
        """Docstring should mention A0-A1 and A2-B1 levels."""
        doc = needs_scaffolding.__doc__
        assert doc is not None
        assert "A0" in doc or "A1" in doc
        assert "A2" in doc or "B1" in doc

    def test_docstring_mentions_scaffold(self) -> None:
        """Docstring should mention scaffolding."""
        doc = needs_scaffolding.__doc__
        assert doc is not None
        assert "scaffold" in doc.lower()


class TestNeedsScaffoldingImport:
    """Tests for module import and exports."""

    def test_needs_scaffolding_importable(self) -> None:
        """needs_scaffolding should be importable from routing module."""
        from src.agent.routing import needs_scaffolding as imported_func

        assert imported_func is not None
        assert callable(imported_func)

    def test_routing_module_exists(self) -> None:
        """Routing module should exist and be importable."""
        import src.agent.routing

        assert src.agent.routing is not None
