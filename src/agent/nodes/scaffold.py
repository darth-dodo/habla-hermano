"""Scaffold node - generates learning aids for beginners.

This node creates scaffolding to help A0-A1 learners respond:
- Word banks with relevant vocabulary
- Hints about what to say
- Sentence starters to reduce blank-page anxiety

Phase 3 feature - currently a stub returning disabled scaffolding.
"""

from typing import Any

from src.agent.state import ConversationState


async def scaffold_node(state: ConversationState) -> dict[str, dict[str, Any]]:
    """Generate scaffolding for A0-A1 learners.

    Creates contextual learning aids based on:
    1. The AI's last response (what they need to respond to)
    2. The user's proficiency level
    3. The current conversation topic

    Scaffolding types:
    - Word bank: 4-6 relevant words they might need
    - Hint: A simple suggestion about what to say
    - Sentence starter: Beginning of a response they can complete
    - Translation: English meaning of AI's message (A0 only)

    Phase 3 Implementation:
        Will use conditional routing to skip for A2-B1:
        ```
        if state["level"] not in ["A0", "A1"]:
            return {"scaffolding": {"enabled": False}}

        scaffolding_result = await llm.ainvoke(scaffolding_prompt)
        return {
            "scaffolding": {
                "enabled": True,
                "word_bank": [...],
                "hint_text": "...",
                "sentence_starter": "..."
            }
        }
        ```

    Args:
        state: Current conversation state.

    Returns:
        Dict with scaffolding configuration.
    """
    level = state.get("level", "A1")

    # Phase 1: Return disabled scaffolding (stub implementation)
    # A0-A1 will get scaffolding enabled in Phase 3
    if level in {"A0", "A1"}:
        return {
            "scaffolding": {
                "enabled": False,
                "show_word_bank": False,
                "word_bank": [],
                "show_hint": False,
                "hint_text": None,
                "sentence_starter": None,
            }
        }

    # A2-B1 never get scaffolding
    return {
        "scaffolding": {
            "enabled": False,
            "show_word_bank": False,
            "word_bank": [],
            "show_hint": False,
            "hint_text": None,
            "sentence_starter": None,
        }
    }
