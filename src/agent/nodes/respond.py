"""
Respond node for the Habla Hermano conversation graph.

This is the core node that generates AI responses appropriate
to the user's language level.

Phase 12: Adds intelligent chat weaving for spaced repetition review words.
"""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.llm import get_llm
from src.agent.prompts import get_prompt_for_level
from src.agent.state import ConversationState, ReviewWordOffered

logger = logging.getLogger(__name__)



def _extract_keywords_from_messages(
    messages: list[Any],
    num_recent: int = 4,
) -> list[str]:
    """
    Extract potential topic keywords from recent conversation messages.

    Focuses on content words (nouns, verbs, adjectives) by filtering out
    very short words and common stopwords. This is a simple heuristic
    approach - not perfect but good enough for topic matching.

    Args:
        messages: List of conversation messages.
        num_recent: Number of recent messages to analyze.

    Returns:
        List of potential topic keywords (lowercase).
    """
    # Common English and Spanish stopwords to filter out
    stopwords = {
        # English
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "dare",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "up",
        "about",
        "into",
        "over",
        "after",
        "and",
        "but",
        "or",
        "because",
        "as",
        "until",
        "while",
        "if",
        "then",
        "than",
        "so",
        "that",
        "this",
        "these",
        "those",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "where",
        "when",
        "why",
        "how",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "too",
        "very",
        "just",
        "also",
        "now",
        "here",
        "there",
        "i",
        "me",
        "my",
        "myself",
        "we",
        "our",
        "ours",
        "ourselves",
        "you",
        "your",
        "yours",
        "yourself",
        "yourselves",
        "he",
        "him",
        "his",
        "himself",
        "she",
        "her",
        "hers",
        "herself",
        "it",
        "its",
        "itself",
        "they",
        "them",
        "their",
        "theirs",
        "themselves",
        "went",
        "going",
        "got",
        "get",
        "say",
        "said",
        "like",
        "want",
        "wanted",
        "know",
        "think",
        # Spanish
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "y",
        "o",
        "pero",
        "que",
        "de",
        "en",
        "con",
        "por",
        "para",
        "sin",
        "sobre",
        "entre",
        "hacia",
        "hasta",
        "desde",
        "durante",
        "mediante",
        "según",
        "yo",
        "tú",
        "él",
        "ella",
        "usted",
        "nosotros",
        "vosotros",
        "ellos",
        "ellas",
        "ustedes",
        "te",
        "se",
        "nos",
        "os",
        "mi",
        "tu",
        "su",
        "nuestro",
        "vuestro",
        "este",
        "esta",
        "estos",
        "estas",
        "ese",
        "esa",
        "esos",
        "esas",
        "aquel",
        "aquella",
        "aquellos",
        "aquellas",
        "qué",
        "quién",
        "cuál",
        "dónde",
        "cuándo",
        "cómo",
        "por qué",
        "es",
        "son",
        "está",
        "están",
        "era",
        "eran",
        "fue",
        "fueron",
        "ser",
        "estar",
        "haber",
        "tener",
        "hacer",
        "ir",
        "venir",
        "ver",
        "dar",
        "saber",
        "poder",
        "querer",
        "deber",
        "hay",
        "sí",
        "muy",
        "más",
        "menos",
        "también",
        "ahora",
        "aquí",
        "allí",
        "hola",
        "bueno",
        "bien",
        "mal",
    }

    keywords: list[str] = []
    recent_messages = messages[-num_recent:] if len(messages) > num_recent else messages

    for msg in recent_messages:
        # Only process HumanMessage content for topic extraction
        if isinstance(msg, HumanMessage):
            content = msg.content
            if isinstance(content, str):
                # Simple tokenization: split by whitespace and punctuation
                words = (
                    content.lower()
                    .replace(",", " ")
                    .replace(".", " ")
                    .replace("?", " ")
                    .replace("!", " ")
                    .split()
                )
                for word in words:
                    # Filter: at least 3 chars, not a stopword, only letters, not already added
                    if (
                        len(word) >= 3
                        and word not in stopwords
                        and word.isalpha()
                        and word not in keywords
                    ):
                        keywords.append(word)

    return keywords[:15]  # Limit to avoid overly broad matching


async def _get_topical_review_words(
    user_id: str | None,
    language: str,
    messages: list[Any],
    supabase_client: Any = None,
    limit: int = 5,
) -> list[ReviewWordOffered]:
    """
    Get due review words that match the current conversation topic.

    Queries the ReviewService for words due for review, filtered by
    keywords extracted from recent messages.

    Args:
        user_id: User UUID for database access (None if not available).
        language: Target language code (es, de).
        messages: Recent conversation messages for keyword extraction.
        supabase_client: User-scoped Supabase client for RLS-safe DB access.
        limit: Maximum number of words to return.

    Returns:
        List of ReviewWordOffered dicts with vocab_id, word, and translation.
    """
    if not user_id:
        return []

    try:
        # Import here to avoid circular imports
        from src.services.review import ReviewService

        # Extract topic keywords from recent messages
        keywords = _extract_keywords_from_messages(messages)

        if not keywords:
            # No keywords extracted - return a few due words anyway
            # (they might still fit naturally)
            keywords = []

        # Use user-scoped client passed through state for RLS compliance
        review_service = ReviewService(user_id, client=supabase_client)

        # Get topical review words
        due_words = review_service.get_topical_review_words(
            language=language,
            topic_keywords=keywords,
            limit=limit,
        )

        # Convert to ReviewWordOffered format
        return [
            ReviewWordOffered(
                vocab_id=vocab.id,  # type: ignore[typeddict-item]
                word=vocab.word,
                translation=vocab.translation,
            )
            for vocab in due_words
            if vocab.id is not None
        ]

    except Exception as e:
        logger.warning("Failed to get topical review words: %s", e)
        return []


def _build_review_prompt_addition(review_words: list[ReviewWordOffered]) -> str:
    """
    Build the prompt addition for review word weaving.

    Args:
        review_words: List of review words to weave into conversation.

    Returns:
        Prompt addition string (empty if no words).
    """
    if not review_words:
        return ""

    words_list = [w["word"] for w in review_words]
    words_str = ", ".join(words_list)

    return f"""

REVIEW OPPORTUNITY (use naturally if relevant, ignore if not):
These words are due for review: [{words_str}]
If conversation allows, use them or prompt the user to use them.
Do NOT force them awkwardly - conversation flow comes first."""


async def respond_node(state: ConversationState) -> dict[str, Any]:
    """
    Generate an AI response appropriate to the user's level.

    This node:
    1. Gets the appropriate system prompt for the user's level
    2. Checks for due review words that match conversation topic (Phase 12)
    3. Calls Claude with the conversation history
    4. Returns the response and offered review words to be added to state

    Args:
        state: Current conversation state containing messages, level, and language

    Returns:
        Dictionary with "messages" key containing the AI response,
        and "review_words_offered" for spaced repetition tracking.
        The add_messages reducer will append messages to existing list.
    """
    # Get level-appropriate system prompt
    prompt = get_prompt_for_level(
        language=state["language"],
        level=state["level"],
    )

    # Phase 12: Get topical review words for chat weaving
    user_id = state.get("user_id")
    review_words: list[ReviewWordOffered] = []

    if user_id:
        review_words = await _get_topical_review_words(
            user_id=user_id,
            language=state["language"],
            messages=state["messages"],
            supabase_client=state.get("supabase_client"),
            limit=5,
        )

        # Add review opportunity to prompt if we have words
        if review_words:
            prompt += _build_review_prompt_addition(review_words)

    # Build message list with system prompt first
    messages = [
        SystemMessage(content=prompt),
        *state["messages"],
    ]

    # Call Claude
    llm = get_llm("conversational")
    response = await llm.ainvoke(messages)

    # Return response and review words offered
    result: dict[str, Any] = {"messages": [response]}

    if review_words:
        result["review_words_offered"] = review_words

    return result
