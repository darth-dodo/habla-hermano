"""
Routing functions for conditional edges in LangGraph.

This module provides routing logic to determine which path messages
should take through the conversation graph based on the learner's level.
"""

from typing import Literal

from src.agent.state import ConversationState


def needs_scaffolding(state: ConversationState) -> Literal["scaffold", "analyze"]:
    """
    Route based on learner level: A0-A1 gets scaffolding, A2-B1 skips to analyze.

    Scaffolding provides word banks, hints, and sentence starters to help
    beginner learners (A0-A1) formulate their responses. More advanced
    learners (A2-B1) can respond independently without this assistance.

    Args:
        state: Current conversation state containing the learner's level.

    Returns:
        "scaffold" for A0-A1 learners who need assistance.
        "analyze" for A2-B1 learners who can respond independently.
    """
    if state["level"] in ["A0", "A1"]:
        return "scaffold"
    return "analyze"
