"""Auto-generate conversation thread titles via LLM.

After the first exchange in a new thread, generates a short (3-5 word)
title summarizing the conversation topic.
"""

import logging

from langchain_anthropic import ChatAnthropic

from src.config import get_settings

logger = logging.getLogger(__name__)

TITLE_PROMPT = (
    "Generate a 3-5 word title for this language learning conversation. "
    "Return ONLY the title text, no quotes, no punctuation at the end.\n\n"
    "User: {human_message}\n"
    "Assistant: {ai_response}"
)


async def generate_thread_title(human_message: str, ai_response: str) -> str:
    """Generate a short conversation title via Haiku.

    Args:
        human_message: The user's first message (truncated to 200 chars).
        ai_response: The AI's first response (truncated to 200 chars).

    Returns:
        A 3-5 word title string, or "New conversation" on failure.
    """
    try:
        settings = get_settings()
        llm = ChatAnthropic(  # type: ignore[call-arg]  # langchain-anthropic lacks stubs
            model="claude-haiku-4-5-20251001",
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            max_tokens=30,
            temperature=0.3,
        )
        prompt = TITLE_PROMPT.format(
            human_message=human_message[:200],
            ai_response=ai_response[:200],
        )
        result = await llm.ainvoke(prompt)
        content = result.content if isinstance(result.content, str) else ""
        title = content.strip().strip('"').strip("'")[:50]
        return title if title else "New conversation"
    except Exception:
        logger.exception("Failed to generate thread title")
        return "New conversation"
