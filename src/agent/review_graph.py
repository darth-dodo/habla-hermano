"""
Review session subgraph for spaced repetition vocabulary review.

Phase 12: LangGraph subgraph pattern for conversational vocabulary review.

This subgraph can be:
1. Invoked standalone for dedicated review mode
2. Added as a node in the main conversation graph (future)

Provides two compiled graphs:
- review_subgraph: Generates questions for review sessions
- answer_evaluation_graph: Evaluates answers and updates SM-2
"""

from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.nodes.review import (
    evaluate_answer_node,
    generate_question_node,
    update_sm2_node,
)
from src.agent.review_state import ReviewState


def build_review_subgraph() -> CompiledStateGraph[Any]:
    """Build the review session subgraph for generating questions.

    Flow:
        START -> generate_question -> END

    This graph:
    1. Picks a question type based on word and learner level
    2. Generates a question with Hermano's voice
    3. Returns the question (waits for user input externally)

    Returns:
        Compiled LangGraph ready for invocation.

    Example usage:
        result = await review_subgraph.ainvoke({
            "user_id": "uuid...",
            "language": "es",
            "level": "A1",
            "words_to_review": [{"id": 1, "word": "hola", "translation": "hello"}, ...],
            "current_word_index": 0,
            "session_size": 10,
            "results": [],
        })
        # result contains: current_word, question_type, question_text
    """
    graph = StateGraph(ReviewState)

    # Add node for question generation
    graph.add_node("generate_question", generate_question_node)

    # Flow: generate_question -> END (wait for user input)
    graph.set_entry_point("generate_question")
    graph.add_edge("generate_question", END)

    return graph.compile()


def build_answer_evaluation_graph() -> CompiledStateGraph[Any]:
    """Build answer evaluation subgraph.

    Flow:
        START -> evaluate_answer -> update_sm2 -> END

    Separate graph for evaluating user answers after they respond.
    Updates SM-2 scheduling and provides personalized feedback.

    Returns:
        Compiled LangGraph ready for invocation.

    Example usage:
        result = await answer_evaluation_graph.ainvoke({
            "user_id": "uuid...",
            "language": "es",
            "level": "A1",
            "words_to_review": [...],
            "current_word_index": 0,
            "session_size": 10,
            "results": [],
            "current_word": {"id": 1, "word": "hola", "translation": "hello"},
            "question_type": "translate",
            "user_answer": "hola",
        })
        # result contains: quality_score, feedback_text, results (updated)
    """
    graph = StateGraph(ReviewState)

    # Add nodes for evaluation and SM-2 update
    graph.add_node("evaluate_answer", evaluate_answer_node)
    graph.add_node("update_sm2", update_sm2_node)

    # Flow: evaluate_answer -> update_sm2 -> END
    graph.set_entry_point("evaluate_answer")
    graph.add_edge("evaluate_answer", "update_sm2")
    graph.add_edge("update_sm2", END)

    return graph.compile()


# Pre-compiled instances for direct import
# Usage: from src.agent.review_graph import review_subgraph, answer_evaluation_graph
review_subgraph = build_review_subgraph()
answer_evaluation_graph = build_answer_evaluation_graph()
