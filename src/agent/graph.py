"""
LangGraph definition for HablaAI.

Phase 3: Graph with conditional routing for scaffolding.
- A0-A1 learners: respond -> scaffold -> analyze -> END
- A2-B1 learners: respond -> analyze -> END
"""

from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.nodes.analyze import analyze_node
from src.agent.nodes.respond import respond_node
from src.agent.nodes.scaffold import scaffold_node
from src.agent.routing import needs_scaffolding
from src.agent.state import ConversationState


def build_graph() -> CompiledStateGraph[Any]:
    """
    Build and compile the conversation graph.

    Phase 3 structure with conditional routing:
        START -> respond -> [scaffold | analyze] -> analyze -> END

    Routing logic:
        - A0-A1 learners: respond -> scaffold -> analyze -> END
        - A2-B1 learners: respond -> analyze -> END

    The respond node generates the AI response, then:
    - For A0-A1: scaffold node generates word banks, hints, sentence starters
    - For all levels: analyze node examines the user's message for grammar/vocab

    Returns:
        Compiled LangGraph ready for invocation.

    Example usage:
        graph = build_graph()
        result = await graph.ainvoke({
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es"
        })
        # result contains: messages, grammar_feedback, new_vocabulary, scaffolding
    """
    # Create the graph with our state type
    graph = StateGraph(ConversationState)

    # Add nodes
    graph.add_node("respond", respond_node)
    graph.add_node("scaffold", scaffold_node)
    graph.add_node("analyze", analyze_node)

    # Set entry point - where execution starts
    graph.set_entry_point("respond")

    # Conditional routing from respond based on learner level
    # A0-A1 -> scaffold, A2-B1 -> analyze
    graph.add_conditional_edges(
        "respond",
        needs_scaffolding,
        {"scaffold": "scaffold", "analyze": "analyze"},
    )

    # scaffold always goes to analyze
    graph.add_edge("scaffold", "analyze")

    # analyze always goes to END
    graph.add_edge("analyze", END)

    # Compile and return
    return graph.compile()


# Pre-built graph instance for convenience
# Can be imported directly: from src.agent.graph import compiled_graph
compiled_graph = build_graph()
