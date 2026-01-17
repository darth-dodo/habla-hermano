"""
Analyze node for the HablaAI conversation graph.

This node analyzes the user's message for grammar errors and vocabulary,
providing level-appropriate feedback without interrupting the conversation flow.
"""

import json
import logging
from typing import Any, Literal, cast

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.state import ConversationState, GrammarFeedback, VocabWord
from src.api.config import get_settings

# Type alias for severity values
SeverityLevel = Literal["minor", "moderate", "significant"]

logger = logging.getLogger(__name__)

# Analysis prompt that asks Claude to return structured JSON
ANALYSIS_PROMPT = """You are a language learning assistant analyzing a student's message.

The student is learning {language} at CEFR level {level}.

Analyze their message for:
1. Grammar errors appropriate to flag at their level
2. New vocabulary words they used or should learn

LEVEL GUIDELINES:
- A0: Only flag very basic errors (wrong greetings, completely wrong words). Be very encouraging.
- A1: Flag basic present tense errors, gender agreement, ser/estar confusion.
- A2: Include past tense errors, reflexive verbs, object pronouns.
- B1: Include subjunctive, conditionals, idiomatic expressions.

For vocabulary, identify:
- Words the student used correctly (to reinforce)
- Key words from the conversation they should remember

Return ONLY valid JSON in this exact format:
{{
    "grammar_errors": [
        {{
            "original": "the incorrect phrase",
            "correction": "the correct phrase",
            "explanation": "brief friendly explanation",
            "severity": "minor|moderate|significant"
        }}
    ],
    "new_vocabulary": [
        {{
            "word": "word in target language",
            "translation": "English translation",
            "part_of_speech": "noun|verb|adjective|adverb|phrase|other"
        }}
    ]
}}

If there are no errors, return an empty array for grammar_errors.
If there's no notable vocabulary, return an empty array for new_vocabulary.
Keep explanations brief and encouraging. Maximum 3 grammar errors and 5 vocabulary words."""


def _get_llm() -> ChatAnthropic:
    """
    Create and return a ChatAnthropic instance for analysis.

    Uses a lower temperature for more consistent JSON output.
    """
    settings = get_settings()
    return ChatAnthropic(
        model=settings.LLM_MODEL,  # type: ignore[call-arg]
        temperature=0.3,  # Lower temperature for structured output
        max_tokens=1024,  # type: ignore[call-arg]
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


def _parse_analysis_response(content: str) -> tuple[list[GrammarFeedback], list[VocabWord]]:
    """
    Parse the LLM's JSON response into typed structures.

    Args:
        content: Raw response content from the LLM.

    Returns:
        Tuple of (grammar_feedback list, vocabulary list).
        Returns empty lists on parse failure.
    """
    try:
        # Handle potential markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())

        grammar_feedback: list[GrammarFeedback] = []
        for error in data.get("grammar_errors", []):
            # Validate and normalize severity value
            raw_severity = error.get("severity", "minor")
            if raw_severity not in ("minor", "moderate", "significant"):
                raw_severity = "minor"
            severity = cast("SeverityLevel", raw_severity)

            grammar_feedback.append(
                GrammarFeedback(
                    original=str(error.get("original", "")),
                    correction=str(error.get("correction", "")),
                    explanation=str(error.get("explanation", "")),
                    severity=severity,
                )
            )

        new_vocabulary: list[VocabWord] = []
        for vocab in data.get("new_vocabulary", []):
            new_vocabulary.append(
                VocabWord(
                    word=str(vocab.get("word", "")),
                    translation=str(vocab.get("translation", "")),
                    part_of_speech=str(vocab.get("part_of_speech", "other")),
                )
            )

        return grammar_feedback, new_vocabulary

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"Failed to parse analysis response: {e}")
        return [], []


async def analyze_node(state: ConversationState) -> dict[str, Any]:
    """
    Analyze the user's last message for grammar and vocabulary.

    This node runs after the respond node to provide educational feedback
    without disrupting the conversation flow.

    The analysis is level-aware:
    - A0: Only flag very basic errors (spelling, basic conjugation)
    - A1: Add gender agreement, ser/estar confusion
    - A2: Add past tense errors, reflexive verb issues
    - B1: Add subjunctive, conditional, advanced constructions

    Args:
        state: Current conversation state containing messages, level, and language.

    Returns:
        Dictionary with grammar_feedback and new_vocabulary lists.
    """
    messages = state["messages"]

    # Need at least 2 messages (user message + AI response)
    # The user's message is at index -2 (before the AI response at -1)
    if len(messages) < 2:
        logger.debug("Not enough messages for analysis")
        return {
            "grammar_feedback": [],
            "new_vocabulary": [],
        }

    # Get the user's last message (before AI response)
    user_message = messages[-2]

    # Verify it's actually a human message
    if not isinstance(user_message, HumanMessage):
        logger.debug("Second-to-last message is not a HumanMessage")
        return {
            "grammar_feedback": [],
            "new_vocabulary": [],
        }

    user_text = user_message.content
    if not user_text or not isinstance(user_text, str):
        return {
            "grammar_feedback": [],
            "new_vocabulary": [],
        }

    # Build the analysis prompt
    language_name = _get_language_name(state["language"])
    prompt = ANALYSIS_PROMPT.format(
        language=language_name,
        level=state["level"],
    )

    # Call Claude for analysis
    llm = _get_llm()
    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(content=f"Student's message: {user_text}"),
            ]
        )

        # Parse the response
        content = response.content
        if isinstance(content, str):
            grammar_feedback, new_vocabulary = _parse_analysis_response(content)
        else:
            grammar_feedback, new_vocabulary = [], []

    except Exception as e:
        logger.error(f"Analysis LLM call failed: {e}")
        grammar_feedback, new_vocabulary = [], []

    return {
        "grammar_feedback": grammar_feedback,
        "new_vocabulary": new_vocabulary,
    }
