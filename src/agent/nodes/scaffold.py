"""
Scaffold node for the HablaAI conversation graph.

This node generates scaffolding (word banks, hints, sentence starters) to help
A0-A1 learners formulate their responses to the AI tutor.
"""

import json
import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agent.state import ConversationState, ScaffoldingConfig
from src.api.config import get_settings

logger = logging.getLogger(__name__)

# Scaffold generation prompt
SCAFFOLD_PROMPT = """You are helping a {level} level {language} learner respond to a conversation.

The AI tutor just said: "{ai_response}"

Generate scaffolding to help the learner respond:

1. WORD BANK: 4-6 relevant words/phrases they might use in their response
2. HINT: A simple tip for how to respond (1 sentence in English)
3. SENTENCE STARTER: A partial sentence to get them started (optional)

Level-specific guidelines:
- A0: Very basic words, include English translations in parentheses, e.g. "hola (hello)"
- A1: Simple phrases, fewer translations needed

Return ONLY valid JSON:
{{
    "word_bank": ["word1 (translation)", "word2", ...],
    "hint": "Try telling them about...",
    "sentence_starter": "Me gusta..." or null
}}
"""


def _get_llm() -> ChatAnthropic:
    """
    Create and return a ChatAnthropic instance for scaffolding generation.

    Uses a lower temperature for more consistent JSON output.
    """
    settings = get_settings()
    return ChatAnthropic(
        model=settings.LLM_MODEL,  # type: ignore[call-arg]
        temperature=0.3,  # Lower temperature for structured output
        max_tokens=512,  # type: ignore[call-arg]
        api_key=settings.ANTHROPIC_API_KEY,  # type: ignore[arg-type]
    )


def _get_language_name(code: str) -> str:
    """Convert language code to full name."""
    names = {
        "es": "Spanish",
        "de": "German",
        "fr": "French",
    }
    return names.get(code, "Spanish")


def _parse_scaffold_response(content: str, level: str) -> ScaffoldingConfig:
    """
    Parse the LLM's JSON response into a ScaffoldingConfig.

    Args:
        content: Raw response content from the LLM.
        level: The learner's CEFR level (A0 or A1).

    Returns:
        ScaffoldingConfig with parsed data, or a default config on parse failure.
    """
    try:
        # Handle potential markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())

        # Validate word_bank is a list of strings
        word_bank = data.get("word_bank", [])
        if not isinstance(word_bank, list):
            word_bank = []
        word_bank = [str(w) for w in word_bank if w]  # Ensure strings, filter empties

        # Extract hint and sentence_starter
        hint_text = str(data.get("hint", "")) if data.get("hint") else ""
        sentence_starter = data.get("sentence_starter")
        if sentence_starter is not None:
            sentence_starter = str(sentence_starter)
            if not sentence_starter.strip():
                sentence_starter = None

        # A0 gets auto-expand, A1 starts collapsed
        auto_expand = level == "A0"

        return ScaffoldingConfig(
            enabled=True,
            word_bank=word_bank,
            hint_text=hint_text,
            sentence_starter=sentence_starter,
            auto_expand=auto_expand,
        )

    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
        logger.warning(f"Failed to parse scaffold response: {e}")
        # Return a minimal scaffolding config on failure
        return ScaffoldingConfig(
            enabled=True,
            word_bank=[],
            hint_text="Try responding to what the tutor said.",
            sentence_starter=None,
            auto_expand=level == "A0",
        )


def _get_ai_response(state: ConversationState) -> str | None:
    """
    Extract the AI's last response from the conversation state.

    Args:
        state: Current conversation state.

    Returns:
        The AI's last response text, or None if not found.
    """
    messages = state.get("messages", [])
    if not messages:
        return None

    # The last message should be the AI response
    last_message = messages[-1]
    if isinstance(last_message, AIMessage):
        content = last_message.content
        if isinstance(content, str):
            return content
    return None


async def scaffold_node(state: ConversationState) -> dict[str, Any]:
    """
    Generate scaffolding to help A0-A1 learners respond.

    This node runs after the respond node for A0-A1 learners, providing:
    - Word bank: Relevant vocabulary for their response
    - Hint: Brief guidance on how to respond
    - Sentence starter: Optional partial sentence to begin with

    Args:
        state: Current conversation state containing messages, level, and language.

    Returns:
        Dictionary with scaffolding config as a dict (from model_dump()).
    """
    # Debug logging
    logger.info(f"scaffold_node called with level={state.get('level')}")
    logger.info(f"scaffold_node messages count: {len(state.get('messages', []))}")
    for i, msg in enumerate(state.get("messages", [])):
        logger.info(f"  msg[{i}]: {type(msg).__name__} = {str(msg.content)[:50]}...")

    # Get the AI's last response
    ai_response = _get_ai_response(state)

    if not ai_response:
        logger.debug("No AI response found for scaffolding")
        return {
            "scaffolding": ScaffoldingConfig(enabled=False).model_dump(),
        }

    # Build the scaffold prompt
    language_name = _get_language_name(state["language"])
    level = state["level"]
    prompt = SCAFFOLD_PROMPT.format(
        level=level,
        language=language_name,
        ai_response=ai_response,
    )

    # Call Claude for scaffolding generation
    llm = _get_llm()
    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(content="Generate scaffolding for the learner."),
            ]
        )

        # Parse the response into ScaffoldingConfig
        content = response.content
        if isinstance(content, str):
            config = _parse_scaffold_response(content, level)
        else:
            config = ScaffoldingConfig(
                enabled=True,
                auto_expand=level == "A0",
            )

    except Exception as e:
        logger.error(f"Scaffold LLM call failed: {e}")
        config = ScaffoldingConfig(
            enabled=True,
            word_bank=[],
            hint_text="Try responding to what the tutor said.",
            sentence_starter=None,
            auto_expand=level == "A0",
        )

    return {"scaffolding": config.model_dump()}
