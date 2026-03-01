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

# Cache compiled graphs by checkpointer identity to avoid redundant compilation.
# The graph topology (nodes, edges, routing) is static; only the checkpointer varies.
_graph_cache: dict[int, CompiledStateGraph[Any]] = {}


def _build_state_graph() -> StateGraph[ConversationState]:
    """Build the uncompiled state graph (topology only).

    The graph structure is identical for every request; only the
    checkpointer binding differs at compile time.
    """
    graph = StateGraph(ConversationState)

    graph.add_node("respond", respond_node)
    graph.add_node("scaffold", scaffold_node)
    graph.add_node("analyze", analyze_node)

    graph.set_entry_point("respond")

    # Conditional routing from respond based on learner level
    # A0-A1 -> scaffold, A2-B1 -> analyze
    graph.add_conditional_edges(
        "respond",
        needs_scaffolding,
        {"scaffold": "scaffold", "analyze": "analyze"},
    )

    graph.add_edge("scaffold", "analyze")
    graph.add_edge("analyze", END)

    return graph


def build_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[Any]:
    """
    Build and compile the conversation graph, with caching per checkpointer.

    The graph topology is static. Only the checkpointer varies between calls.
    Compiled graphs are cached by checkpointer identity to avoid redundant
    compilation on every request.

    Phase 3 structure with conditional routing:
        START -> respond -> [scaffold | analyze] -> analyze -> END

    Routing logic:
        - A0-A1 learners: respond -> scaffold -> analyze -> END
        - A2-B1 learners: respond -> analyze -> END

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
    cache_key = id(checkpointer) if checkpointer is not None else 0

    cached = _graph_cache.get(cache_key)
    if cached is not None:
        return cached

    compiled = _build_state_graph().compile(checkpointer=checkpointer)
    _graph_cache[cache_key] = compiled
    return compiled


def clear_graph_cache() -> None:
    """Clear the compiled graph cache.

    Useful for testing or when graph structure changes at runtime.
    """
    _graph_cache.clear()


# Pre-built graph instance for convenience (stateless, no checkpointer)
# Can be imported directly: from src.agent.graph import compiled_graph
compiled_graph = build_graph()
