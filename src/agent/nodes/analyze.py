"""Analyze node - extracts grammar errors and vocabulary.

This node analyzes the user's message for:
- Grammar mistakes appropriate to flag at their level
- New vocabulary words they've used or encountered

Phase 2 feature - currently a stub returning empty results.
"""

from src.agent.state import ConversationState


async def analyze_node(state: ConversationState) -> dict[str, list[object]]:
    """Analyze user's message for grammar errors and new vocabulary.

    Examines the user's last message and identifies:
    1. Grammar errors appropriate to their CEFR level
    2. Vocabulary words that are new or notable

    The analysis is level-aware:
    - A0: Only flag very basic errors (spelling, basic conjugation)
    - A1: Add gender agreement, ser/estar confusion
    - A2: Add past tense errors, reflexive verb issues
    - B1: Add subjunctive, conditional, advanced constructions

    Phase 2 Implementation:
        Will use structured output to extract analysis:
        ```
        analysis_prompt = f'''
        Analyze this {state["language"]} message from a {state["level"]} learner:
        "{user_message}"
        Return JSON with grammar_errors and new_vocabulary.
        '''
        result = await llm.ainvoke(analysis_prompt)
        ```

    Args:
        state: Current conversation state.

    Returns:
        Dict with grammar_feedback and new_vocabulary lists.
    """
    # Phase 1: Return empty results (stub implementation)
    _ = state  # Acknowledge state parameter for future use
    return {
        "grammar_feedback": [],
        "new_vocabulary": [],
    }
