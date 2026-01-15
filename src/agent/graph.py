"""LangGraph definition for HablaAI conversation flow.

This module defines the conversation graph that orchestrates the AI tutor.
The graph is built incrementally following the learning progression:

Phase 1 (Current): Minimal graph with single respond node
Phase 2: Add analyze node for grammar/vocab extraction
Phase 3: Conditional routing for scaffolding (A0-A1)
Phase 4: Checkpointing for conversation persistence
"""

from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.nodes.respond import respond_node
from src.agent.state import ConversationState

# Type alias for compiled graph (langgraph types are not fully typed)
CompiledGraph = CompiledStateGraph[Any]

# Module-level compiled graph instance (lazy initialization)
_compiled_graph: CompiledGraph | None = None


def build_graph() -> StateGraph[ConversationState]:
    """Build the LangGraph for conversation flow.

    Creates a StateGraph with the current phase's nodes and edges.
    This function returns an uncompiled graph for testing and inspection.

    Phase 1 Implementation:
        START -> respond -> END

    Returns:
        Uncompiled StateGraph ready for compilation or inspection.
    """
    graph: StateGraph[ConversationState] = StateGraph(ConversationState)

    # Add nodes
    graph.add_node("respond", respond_node)

    # Set entry point
    graph.set_entry_point("respond")

    # Add edges (Phase 1: simple linear flow)
    graph.add_edge("respond", END)

    return graph


def get_compiled_graph() -> CompiledGraph:
    """Get or create the compiled conversation graph.

    This function implements lazy initialization of the compiled graph.
    The graph is compiled once and reused for all subsequent calls.

    Future phases will add checkpointing here:
        checkpointer = SqliteSaver.from_conn_string("data/habla.db")
        return graph.compile(checkpointer=checkpointer)

    Returns:
        Compiled StateGraph ready for invocation.
    """
    global _compiled_graph  # noqa: PLW0603

    if _compiled_graph is None:
        graph = build_graph()
        _compiled_graph = graph.compile()

    return _compiled_graph
