"""
Respond node for the HablaAI conversation graph.

This is the core node that generates AI responses appropriate
to the user's language level.
"""

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage

from src.agent.prompts import get_prompt_for_level
from src.agent.state import ConversationState
from src.api.config import get_settings


def _get_llm() -> ChatAnthropic:
    """
    Create and return a ChatAnthropic instance.

    Uses claude-sonnet-4-20250514 for good balance of quality and speed.
    API key is read from application settings.
    """
    settings = get_settings()
    return ChatAnthropic(
        model=settings.LLM_MODEL,  # type: ignore[call-arg]
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=1024,  # type: ignore[call-arg]
        api_key=settings.ANTHROPIC_API_KEY,  # type: ignore[arg-type]
    )


async def respond_node(state: ConversationState) -> dict[str, Any]:
    """
    Generate an AI response appropriate to the user's level.

    This node:
    1. Gets the appropriate system prompt for the user's level
    2. Calls Claude with the conversation history
    3. Returns the response to be added to messages

    Args:
        state: Current conversation state containing messages, level, and language

    Returns:
        Dictionary with "messages" key containing the AI response.
        The add_messages reducer will append this to existing messages.
    """
    # Get level-appropriate system prompt
    prompt = get_prompt_for_level(
        language=state["language"],
        level=state["level"],
    )

    # Build message list with system prompt first
    messages = [
        SystemMessage(content=prompt),
        *state["messages"],
    ]

    # Call Claude
    llm = _get_llm()
    response = await llm.ainvoke(messages)

    # Return response - add_messages reducer will append it
    return {"messages": [response]}
