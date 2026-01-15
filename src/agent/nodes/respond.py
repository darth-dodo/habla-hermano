"""Respond node - generates AI tutor responses.

This node is the core of the conversation flow. It takes the current
conversation state, constructs an appropriate prompt based on the
user's level, and generates a response.

Phase 1: Returns a placeholder response (no LLM integration yet)
Future: Will integrate with Claude API via langchain-anthropic
"""

from langchain_core.messages import AIMessage

from src.agent.prompts import get_prompt_for_level
from src.agent.state import ConversationState


async def respond_node(state: ConversationState) -> dict[str, list[AIMessage]]:
    """Generate an AI response appropriate to the user's level.

    This node reads the conversation history and user's proficiency level,
    then generates a contextually appropriate response.

    Phase 1 Implementation:
        Returns a placeholder response demonstrating the state flow.
        The response includes level-aware greeting to verify routing works.

    Future Implementation:
        Will use langchain-anthropic to generate responses:
        ```
        llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            *state["messages"]
        ])
        return {"messages": [response]}
        ```

    Args:
        state: Current conversation state containing messages, level, and language.

    Returns:
        Dict with "messages" key containing the AI response.
        Uses the add_messages reducer pattern for automatic accumulation.
    """
    level = state.get("level", "A1")
    language = state.get("language", "es")

    # Get the appropriate prompt (validates level and language)
    _prompt = get_prompt_for_level(language, level)

    # Phase 1: Placeholder response
    # This demonstrates the state flow without requiring LLM integration
    level_greetings = {
        "A0": "Hola! Hello! I'm your Spanish tutor. Let's start with basics!",
        "A1": "Hola! Como estas? I'm here to help you practice Spanish.",
        "A2": "Hola! Que tal? Vamos a practicar espanol juntos.",
        "B1": "Hola! Que gusto verte. Estoy listo para nuestra conversacion.",
    }

    greeting = level_greetings.get(level, level_greetings["A1"])
    response = AIMessage(content=greeting)

    return {"messages": [response]}
