"""
Lesson delivery subgraph for AI-enhanced lessons.

Phase 9: LangGraph subgraph pattern for reusable lesson content delivery.

This subgraph can be:
1. Invoked standalone for lesson step enhancement
2. Added as a node in the main conversation graph (future)

Provides two compiled graphs:
- lesson_subgraph: Loads and enhances lesson steps with Hermano's teaching
- exercise_validation_graph: Validates answers with personalized feedback
"""

from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.lesson_state import LessonState
from src.agent.nodes.lesson import (
    enhance_step_node,
    load_step_node,
    validate_exercise_node,
)


def build_lesson_subgraph() -> CompiledStateGraph[Any]:
    """Build the lesson delivery subgraph.

    Flow:
        START -> load_step -> enhance_step -> END

    This graph:
    1. Loads step data from the YAML lesson
    2. Enhances it with Hermano's personalized content

    Returns:
        Compiled LangGraph ready for invocation.

    Example usage:
        result = await lesson_subgraph.ainvoke({
            "lesson_id": "es-greetings-basics",
            "step_index": 0,
            "level": "A1",
            "language": "es",
            "messages": [],
        })
        # result contains: step_type, step_content, enhanced_content, hermano_intro
    """
    graph = StateGraph(LessonState)

    # Add nodes
    graph.add_node("load_step", load_step_node)
    graph.add_node("enhance_step", enhance_step_node)

    # Define flow: load_step -> enhance_step -> END
    graph.set_entry_point("load_step")
    graph.add_edge("load_step", "enhance_step")
    graph.add_edge("enhance_step", END)

    return graph.compile()


def build_exercise_validation_graph() -> CompiledStateGraph[Any]:
    """Build exercise validation subgraph.

    Flow:
        START -> validate_exercise -> END

    Separate graph for validating exercise answers with AI-generated
    personalized feedback from Hermano.

    Returns:
        Compiled LangGraph ready for invocation.

    Example usage:
        result = await exercise_validation_graph.ainvoke({
            "lesson_id": "es-greetings-basics",
            "exercise_id": "greet-choice-1",
            "user_answer": "0",
            "level": "A1",
            "language": "es",
            "messages": [],
        })
        # result contains: is_correct, exercise_feedback
    """
    graph = StateGraph(LessonState)

    # Single node for exercise validation
    graph.add_node("validate_exercise", validate_exercise_node)

    # Flow: validate_exercise -> END
    graph.set_entry_point("validate_exercise")
    graph.add_edge("validate_exercise", END)

    return graph.compile()


# Pre-compiled instances for direct import
# Usage: from src.agent.lesson_graph import lesson_subgraph, exercise_validation_graph
lesson_subgraph = build_lesson_subgraph()
exercise_validation_graph = build_exercise_validation_graph()
