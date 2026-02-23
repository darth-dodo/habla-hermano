"""
Analyze node for the Habla Hermano conversation graph.

This node analyzes the user's message for grammar errors and vocabulary,
providing level-appropriate feedback without interrupting the conversation flow.

Phase 12: Adds tracking for review word usage in chat weaving.
"""

import json
import logging
from typing import Any, Literal, cast

from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.llm import get_llm
from src.agent.state import (
    ConversationState,
    GrammarFeedback,
    PronunciationTip,
    ReviewWordOffered,
    ReviewWordUsed,
    VocabWord,
)
from src.agent.utils import extract_json_from_response
from src.api.validation import get_language_name as _get_language_name

# Type alias for severity values
SeverityLevel = Literal["minor", "moderate", "significant"]

logger = logging.getLogger(__name__)

# Analysis prompt that asks Claude to return structured JSON
ANALYSIS_PROMPT = """You are a language learning assistant analyzing a student's message.

The student is learning {language} at CEFR level {level}.

Analyze their message for:
1. Grammar errors appropriate to flag at their level
2. New vocabulary words they used or should learn
3. Pronunciation tips for tricky words the AI used in its response

LEVEL GUIDELINES:
- A0: Only flag very basic errors (wrong greetings, completely wrong words). Be very encouraging.
- A1: Flag basic present tense errors, gender agreement, ser/estar confusion.
- A2: Include past tense errors, reflexive verbs, object pronouns.
- B1: Include subjunctive, conditionals, idiomatic expressions.

For vocabulary, identify:
- Words the student used correctly (to reinforce)
- Key words from the conversation they should remember

For pronunciation, identify:
- Words with sounds that don't exist in English
- Words with tricky stress patterns
- Common mispronunciations to avoid

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
    ],
    "pronunciation_tips": [
        {{
            "word": "word in target language",
            "phonetic": "simple phonetic like GRAH-see-ahs",
            "tip": "brief tip on how to say it",
            "audio_hint": "optional comparison to English sounds"
        }}
    ]
}}

If there are no errors, return an empty array for grammar_errors.
If there's no notable vocabulary, return an empty array for new_vocabulary.
If there are no tricky pronunciations, return an empty array for pronunciation_tips.
Keep explanations brief and encouraging. Maximum 3 grammar errors, 5 vocabulary words, and 2 pronunciation tips."""


def _parse_pronunciation_tips(data: dict[str, Any]) -> list[PronunciationTip]:
    """
    Parse pronunciation tips from the LLM response data.

    Args:
        data: Parsed JSON data from the LLM response.

    Returns:
        List of PronunciationTip objects.
    """
    pronunciation_tips: list[PronunciationTip] = []
    for tip in data.get("pronunciation_tips", []):
        # Skip non-dict entries (malformed data)
        if not isinstance(tip, dict):
            continue

        pronunciation_tip: PronunciationTip = {
            "word": str(tip.get("word", "")),
            "phonetic": str(tip.get("phonetic", "")),
            "tip": str(tip.get("tip", "")),
        }

        # Only include audio_hint if present and non-empty
        audio_hint = tip.get("audio_hint")
        if audio_hint and isinstance(audio_hint, str):
            pronunciation_tip["audio_hint"] = audio_hint

        pronunciation_tips.append(pronunciation_tip)

    return pronunciation_tips


def _parse_analysis_response(
    content: str,
) -> tuple[list[GrammarFeedback], list[VocabWord], list[PronunciationTip]]:
    """
    Parse the LLM's JSON response into typed structures.

    Args:
        content: Raw response content from the LLM.

    Returns:
        Tuple of (grammar_feedback list, vocabulary list, pronunciation_tips list).
        Returns empty lists on parse failure.
    """
    try:
        data = extract_json_from_response(content)

        grammar_feedback: list[GrammarFeedback] = []
        for error in data.get("grammar_errors", []):
            # Skip non-dict entries (malformed data)
            if not isinstance(error, dict):
                continue
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
            # Skip non-dict entries (malformed data)
            if not isinstance(vocab, dict):
                continue
            new_vocabulary.append(
                VocabWord(
                    word=str(vocab.get("word", "")),
                    translation=str(vocab.get("translation", "")),
                    part_of_speech=str(vocab.get("part_of_speech", "other")),
                )
            )

        pronunciation_tips = _parse_pronunciation_tips(data)

        return grammar_feedback, new_vocabulary, pronunciation_tips

    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
        logger.warning("Failed to parse analysis response: %s", e)
        return [], [], []


def _check_review_word_usage(
    user_text: str,
    offered_words: list[ReviewWordOffered],
) -> list[ReviewWordUsed]:
    """
    Check if the user correctly used any offered review words.

    Performs case-insensitive matching of the user's text against
    the offered review words. If a word is found, it's considered
    "correctly used" and assigned a quality score of 4 (correct usage).

    Args:
        user_text: The user's message text.
        offered_words: List of review words that were offered for weaving.

    Returns:
        List of ReviewWordUsed dicts for words found in the user's message.
    """
    if not user_text or not offered_words:
        return []

    user_text_lower = user_text.lower()
    used_words: list[ReviewWordUsed] = []

    for word in offered_words:
        word_lower = word["word"].lower()

        # Check if the word appears in the user's message
        # Simple substring check - could be enhanced with word boundary detection
        if word_lower in user_text_lower:
            used_words.append(
                ReviewWordUsed(
                    vocab_id=word["vocab_id"],
                    word=word["word"],
                    quality=4,  # Correct usage in context
                )
            )

    return used_words


async def _update_sm2_for_used_words(
    user_id: str | None,
    used_words: list[ReviewWordUsed],
    supabase_client: Any = None,
) -> None:
    """
    Update SM-2 scheduling for review words that were used correctly.

    This enables "silent" review tracking during natural conversation -
    users get spaced repetition benefits without explicit review sessions.

    Args:
        user_id: User UUID for database access.
        used_words: List of words the user correctly used.
        supabase_client: User-scoped Supabase client for RLS-safe DB access.
    """
    if not user_id or not used_words:
        return

    try:
        # Import here to avoid circular imports
        from src.services.review import ReviewService

        # Use user-scoped client passed through state for RLS compliance
        review_service = ReviewService(user_id, client=supabase_client)

        for word in used_words:
            try:
                review_service.update_sm2(
                    vocab_id=word["vocab_id"],
                    quality=word["quality"],
                )
                logger.debug(
                    "Updated SM-2 for word '%s' with quality %s",
                    word["word"],
                    word["quality"],
                )
            except Exception as e:
                logger.warning("Failed to update SM-2 for word '%s': %s", word["word"], e)

    except Exception as e:
        logger.warning("Failed to update SM-2 for used words: %s", e)


async def analyze_node(state: ConversationState) -> dict[str, Any]:
    """
    Analyze the user's last message for grammar, vocabulary, and pronunciation.

    This node runs after the respond node to provide educational feedback
    without disrupting the conversation flow.

    The analysis is level-aware:
    - A0: Only flag very basic errors (spelling, basic conjugation)
    - A1: Add gender agreement, ser/estar confusion
    - A2: Add past tense errors, reflexive verb issues
    - B1: Add subjunctive, conditional, advanced constructions

    Phase 12: Also tracks usage of offered review words for spaced repetition.

    Args:
        state: Current conversation state containing messages, level, and language.

    Returns:
        Dictionary with grammar_feedback, new_vocabulary, pronunciation_tips,
        and review_words_used lists.
    """
    messages = state["messages"]

    # Initialize result with empty lists
    result: dict[str, Any] = {
        "grammar_feedback": [],
        "new_vocabulary": [],
        "pronunciation_tips": [],
    }

    # Need at least 2 messages (user message + AI response)
    # The user's message is at index -2 (before the AI response at -1)
    if len(messages) < 2:
        logger.debug("Not enough messages for analysis")
        return result

    # Get the user's last message (before AI response)
    user_message = messages[-2]

    # Verify it's actually a human message
    if not isinstance(user_message, HumanMessage):
        logger.debug("Second-to-last message is not a HumanMessage")
        return result

    user_text = user_message.content
    if not user_text or not isinstance(user_text, str):
        return result

    # Phase 12: Check for review word usage BEFORE grammar analysis
    # This enables "silent" spaced repetition during natural conversation
    offered_words = state.get("review_words_offered", [])
    used_words: list[ReviewWordUsed] = []

    if offered_words:
        used_words = _check_review_word_usage(user_text, offered_words)

        if used_words:
            # Update SM-2 scheduling for correctly used words
            user_id = state.get("user_id")
            await _update_sm2_for_used_words(
                user_id, used_words, supabase_client=state.get("supabase_client")
            )
            result["review_words_used"] = used_words

    # Build the analysis prompt
    language_name = _get_language_name(state["language"])
    prompt = ANALYSIS_PROMPT.format(
        language=language_name,
        level=state["level"],
    )

    # Call Claude for analysis
    llm = get_llm("analysis")
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
            grammar_feedback, new_vocabulary, pronunciation_tips = _parse_analysis_response(content)
        else:
            grammar_feedback, new_vocabulary, pronunciation_tips = [], [], []

    except Exception as e:
        logger.error("Analysis LLM call failed: %s", e)
        grammar_feedback, new_vocabulary, pronunciation_tips = [], [], []

    result["grammar_feedback"] = grammar_feedback
    result["new_vocabulary"] = new_vocabulary
    result["pronunciation_tips"] = pronunciation_tips

    return result
