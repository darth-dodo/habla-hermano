"""
HablaAI Agent - LangGraph-based conversation engine.

This module provides the core conversation graph and state management
for the AI language tutor.

Phase 2 exports:
- ConversationState: TypedDict for graph state
- GrammarFeedback: TypedDict for grammar corrections
- VocabWord: TypedDict for vocabulary items
- build_graph: Function to create fresh graph instance
- compiled_graph: Pre-compiled graph ready for use
- respond_node: The response generation node
- analyze_node: The grammar/vocabulary analysis node
"""

from src.agent.graph import build_graph, compiled_graph
from src.agent.nodes import analyze_node, respond_node
from src.agent.state import ConversationState, GrammarFeedback, VocabWord

__all__ = [
    "ConversationState",
    "GrammarFeedback",
    "VocabWord",
    "analyze_node",
    "build_graph",
    "compiled_graph",
    "respond_node",
]
