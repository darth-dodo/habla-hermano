"""
LangGraph definition for HablaAI.

Phase 2: Graph with respond and analyze nodes.
The analyze node provides grammar feedback and vocabulary extraction.
"""

from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.nodes.analyze import analyze_node
from src.agent.nodes.respond import respond_node
from src.agent.state import ConversationState


def build_graph() -> CompiledStateGraph[Any]:
    """
    Build and compile the conversation graph.

    Phase 2 structure:
        START -> respond -> analyze -> END

    The respond node generates the AI response, then the analyze node
    examines the user's message for grammar errors and vocabulary.

    Returns:
        Compiled LangGraph ready for invocation.

    Example usage:
        graph = build_graph()
        result = await graph.ainvoke({
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es"
        })
        # result contains: messages, grammar_feedback, new_vocabulary
    """
    # Create the graph with our state type
    graph = StateGraph(ConversationState)

    # Add nodes
    graph.add_node("respond", respond_node)
    graph.add_node("analyze", analyze_node)

    # Set entry point - where execution starts
    graph.set_entry_point("respond")

    # Connect respond -> analyze -> END
    graph.add_edge("respond", "analyze")
    graph.add_edge("analyze", END)

    # Compile and return
    return graph.compile()


# Pre-built graph instance for convenience
# Can be imported directly: from src.agent.graph import compiled_graph
compiled_graph = build_graph()
