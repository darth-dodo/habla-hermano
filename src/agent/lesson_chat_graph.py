"""
LangGraph definition for conversational lesson delivery.

Phase 19: Separate graph with identical topology to main chat,
using lesson_respond_node for phase-based lesson teaching.
"""

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.lesson_chat_state import LessonChatState
from src.agent.nodes.analyze import analyze_node
from src.agent.nodes.lesson_chat import lesson_respond_node
from src.agent.nodes.scaffold import scaffold_node
from src.agent.routing import needs_scaffolding

# Cache compiled graphs by checkpointer identity
_lesson_graph_cache: dict[int, CompiledStateGraph[Any]] = {}


def _build_lesson_state_graph() -> StateGraph[LessonChatState]:
    """Build the uncompiled lesson state graph (topology only)."""
    graph = StateGraph(LessonChatState)

    # Register as "respond" for SSE streaming compatibility
    graph.add_node("respond", lesson_respond_node)
    graph.add_node("scaffold", scaffold_node)
    graph.add_node("analyze", analyze_node)

    graph.set_entry_point("respond")

    graph.add_conditional_edges(
        "respond",
        needs_scaffolding,
        {"scaffold": "scaffold", "analyze": "analyze"},
    )

    graph.add_edge("scaffold", "analyze")
    graph.add_edge("analyze", END)

    return graph


def build_lesson_chat_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[Any]:
    """Build and compile the lesson chat graph, cached per checkpointer.

    Same topology as main chat graph but uses lesson_respond_node
    for phase-based lesson teaching (intro -> teaching -> exercises -> complete).

    Args:
        checkpointer: Optional checkpoint saver for lesson conversation persistence.
            Thread IDs use format: lesson:{user_id}:{lesson_id}

    Returns:
        Compiled LangGraph ready for lesson chat invocation.
    """
    cache_key = id(checkpointer) if checkpointer is not None else 0

    cached = _lesson_graph_cache.get(cache_key)
    if cached is not None:
        return cached

    compiled = _build_lesson_state_graph().compile(checkpointer=checkpointer)
    _lesson_graph_cache[cache_key] = compiled
    return compiled


def clear_lesson_graph_cache() -> None:
    """Clear the compiled lesson graph cache. Useful for testing."""
    _lesson_graph_cache.clear()
