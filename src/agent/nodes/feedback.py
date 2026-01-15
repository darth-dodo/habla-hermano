"""Feedback node - formats corrections for display.

This node takes the grammar analysis results and formats them
into user-friendly feedback messages that are encouraging
rather than discouraging.

Phase 3 feature - currently a stub returning empty feedback.
"""

from typing import Any

from src.agent.state import ConversationState


async def feedback_node(state: ConversationState) -> dict[str, list[dict[str, Any]]]:
    """Format grammar corrections for user display.

    Takes raw grammar analysis and transforms it into:
    1. Friendly, encouraging correction messages
    2. Brief explanations appropriate to level
    3. Examples of correct usage

    The feedback style varies by level:
    - A0: Very gentle, focus on encouragement over correction
    - A1: Simple corrections with basic explanations
    - A2: More detailed explanations with grammar rule references
    - B1: Full explanations with nuanced usage notes

    Phase 3 Implementation:
        Will process grammar_feedback from analyze node:
        ```
        formatted = []
        for error in state.get("grammar_feedback", []):
            formatted.append({
                "original": error["original"],
                "correction": error["correction"],
                "message": format_friendly_message(error, state["level"]),
                "show_rule": state["level"] in ["A2", "B1"]
            })
        return {"formatted_feedback": formatted}
        ```

    Args:
        state: Current conversation state with grammar_feedback.

    Returns:
        Dict with formatted_feedback list ready for UI display.
    """
    # Phase 1: Return empty feedback (stub implementation)
    _ = state  # Acknowledge state parameter for future use
    return {"formatted_feedback": []}
