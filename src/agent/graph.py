"""
LangGraph definition for HablaAI.

Phase 3: Graph with conditional routing for scaffolding.
Phase 4: Optional checkpointer support for conversation persistence.

- A0-A1 learners: respond -> scaffold -> analyze -> END
- A2-B1 learners: respond -> analyze -> END
"""

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.nodes.analyze import analyze_node
from src.agent.nodes.respond import respond_node
from src.agent.nodes.scaffold import scaffold_node
from src.agent.routing import needs_scaffolding
from src.agent.state import ConversationState


def build_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[Any]:
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

    Args:
        checkpointer: Optional checkpoint saver for conversation persistence.
            When provided, enables conversation history to be saved and resumed
            across sessions using thread_id in the config.

    Returns:
        Compiled LangGraph ready for invocation.

    Example usage:
        # Without persistence (stateless)
        graph = build_graph()
        result = await graph.ainvoke({
            "messages": [HumanMessage(content="Hola!")],
            "level": "A1",
            "language": "es"
        })

        # With persistence (Phase 4)
        async with get_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content="Hola!")], "level": "A1", "language": "es"},
                config={"configurable": {"thread_id": "user-session-123"}}
            )
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

    # Compile and return with optional checkpointer for persistence
    return graph.compile(checkpointer=checkpointer)


# Pre-built graph instance for convenience
# Can be imported directly: from src.agent.graph import compiled_graph
compiled_graph = build_graph()
