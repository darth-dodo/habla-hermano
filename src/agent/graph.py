"""
LangGraph definition for HablaAI.

Phase 1: Minimal graph with a single respond node.
This is the simplest possible graph - just receives a message and responds.
"""

from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.nodes.respond import respond_node
from src.agent.state import ConversationState


def build_graph() -> CompiledStateGraph[Any]:
    """
    Build and compile the conversation graph.

    Phase 1 structure:
        START -> respond -> END

    Returns:
        Compiled LangGraph ready for invocation.

    Example usage:
        graph = build_graph()
        result = await graph.ainvoke({
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es"
        })
    """
    # Create the graph with our state type
    graph = StateGraph(ConversationState)

    # Add the respond node
    graph.add_node("respond", respond_node)

    # Set entry point - where execution starts
    graph.set_entry_point("respond")

    # Connect respond to END - completes the graph
    graph.add_edge("respond", END)

    # Compile and return
    return graph.compile()


# Pre-built graph instance for convenience
# Can be imported directly: from src.agent.graph import compiled_graph
compiled_graph = build_graph()
