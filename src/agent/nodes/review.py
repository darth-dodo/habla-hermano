"""
Review nodes for the spaced repetition review subgraph.

Phase 12: These nodes work together to:
1. Generate varied question types with Hermano's voice
2. Evaluate user answers and infer quality scores
3. Update SM-2 scheduling via ReviewService
"""

import random
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from postgrest.exceptions import APIError

from src.agent.llm import get_llm
from src.agent.prompts import LANGUAGE_ADAPTER
from src.agent.review_state import ReviewState

# Question generation prompts by type
QUESTION_PROMPTS = {
    "translate": """You are Hermano, a friendly language buddy helping someone review vocabulary.

Generate a single review question asking them to translate a word.

Word to review: {word}
Translation: {translation}
Language: {language_name}
Learner level: {level}

Write a casual, friendly question asking how to say the English word in {language_name}.
Keep it brief (1-2 sentences max). Use your warm, encouraging tone.

Example formats:
- "Quick one - how do you say '{translation}' in {language_name}?"
- "Alright, what's the {language_name} word for '{translation}'?"
- "Let's see... how would you say '{translation}'?"

Write ONLY the question, nothing else.""",
    "fill_blank": """You are Hermano, a friendly language buddy helping someone review vocabulary.

Generate a fill-in-the-blank question using this word.

Word to review: {word}
Translation: {translation}
Language: {language_name}
Learner level: {level}

Create a simple sentence in {language_name} with the word replaced by a blank (___).
The sentence should be appropriate for {level} level.
Include the English translation hint in parentheses.

Example format:
"Fill in the blank: '_____ la cuenta, por favor' (to ask for the bill)"

Write ONLY the question with the blank, nothing else.""",
    "recognize": """You are Hermano, a friendly language buddy helping someone review vocabulary.

Generate a recognition question asking what a {language_name} word means.

Word to review: {word}
Translation: {translation}
Language: {language_name}
Learner level: {level}

Write a casual question asking what the {language_name} word means in English.
Keep it brief (1-2 sentences max). Use your warm, encouraging tone.

Example formats:
- "What does '{word}' mean?"
- "Quick check - what's '{word}' in English?"
- "Do you remember what '{word}' means?"

Write ONLY the question, nothing else.""",
}


# Feedback prompts based on quality
FEEDBACK_PROMPTS = {
    "correct": """You are Hermano, a friendly language buddy celebrating a correct answer!

Word reviewed: {word}
Translation: {translation}
User's answer: {user_answer}
Language: {language_name}

Give brief, enthusiastic feedback (1-2 sentences).
- Celebrate their success genuinely
- Maybe add a quick tip or fun fact about the word (optional)
- Keep it casual and warm

Write ONLY the feedback, nothing else.""",
    "almost": """You are Hermano, a friendly language buddy giving gentle correction.

Word reviewed: {word}
Translation: {translation}
User's answer: {user_answer}
Language: {language_name}

Give supportive feedback (2-3 sentences) that:
- Acknowledges they were close
- Shows the correct answer naturally
- Encourages them

Keep it casual - like a friend saying "almost!"

Write ONLY the feedback, nothing else.""",
    "incorrect": """You are Hermano, a friendly language buddy helping after a miss.

Word reviewed: {word}
Translation: {translation}
User's answer: {user_answer}
Question type: {question_type}
Language: {language_name}

Give supportive feedback (2-3 sentences) that:
- Never makes them feel bad
- Shows the correct answer naturally
- Adds a brief memory tip if you can think of one
- Encourages them to keep going

Keep it casual - like a friend saying "no worries!"

Write ONLY the feedback, nothing else.""",
}


def _pick_question_type(level: str) -> str:
    """Pick a question type based on learner level.

    For beginners (A0-A1), favor recognition and translation.
    For higher levels, include fill_blank more often.

    Args:
        level: CEFR level (A0, A1, A2, B1).

    Returns:
        Question type: translate, fill_blank, or recognize.
    """
    # Weight probabilities by level
    if level in ("A0", "A1"):
        # Beginners: mostly translation and recognition
        weights = {"translate": 0.45, "recognize": 0.45, "fill_blank": 0.1}
    else:
        # Higher levels: more variety
        weights = {"translate": 0.35, "recognize": 0.30, "fill_blank": 0.35}

    # Pick based on weights
    r = random.random()
    cumulative = 0.0
    for qtype, weight in weights.items():
        cumulative += weight
        if r <= cumulative:
            return qtype

    return "translate"  # Fallback


def _strip_accents(s: str) -> str:
    """Remove common accent marks from a string for comparison.

    Args:
        s: String to process.

    Returns:
        String with accent marks replaced by plain characters.
    """
    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ñ": "n",
        "ü": "u",
        "ä": "a",
        "ö": "o",
    }
    for acc, plain in replacements.items():
        s = s.replace(acc, plain)
    return s


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein edit distance between two strings.

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Minimum number of single-character edits to transform s1 into s2.
    """
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def _infer_quality_score(
    user_answer: str,
    correct_answer: str,
) -> int:
    """Infer SM-2 quality score from user's answer.

    Quality scores (per SM-2):
        5 - Perfect response, no hesitation
        4 - Correct with minor typo/accent issue
        3 - Correct with difficulty
        2 - Incorrect, but close
        1 - Incorrect, answer seemed unfamiliar
        0 - Complete blank / skip

    Args:
        user_answer: The user's submitted answer.
        correct_answer: The expected correct answer.

    Returns:
        Quality score 0-5.
    """
    # Normalize for comparison
    user_normalized = user_answer.strip().lower()
    correct_normalized = correct_answer.strip().lower()

    # Empty or skip -> 0
    if not user_normalized or user_normalized in ("skip", "?", "idk", "i don't know"):
        return 0

    # Exact match -> 5
    if user_normalized == correct_normalized:
        return 5

    # Compare with accents stripped
    user_stripped = _strip_accents(user_normalized)
    correct_stripped = _strip_accents(correct_normalized)

    # Match without accents -> 4
    if user_stripped == correct_stripped:
        return 4

    # Calculate edit distance for fuzzy matching
    distance = _levenshtein_distance(user_stripped, correct_stripped)
    word_length = len(correct_stripped)
    contains_match = correct_stripped in user_stripped or user_stripped in correct_stripped

    # Determine quality based on distance relative to word length
    quality = 1  # Default: incorrect but not blank
    if word_length <= 4 and distance <= 1:
        quality = 4
    elif (word_length <= 8 and distance <= 2) or distance <= 3:
        quality = 3
    elif contains_match:
        quality = 2

    return quality


async def generate_question_node(state: ReviewState) -> dict[str, Any]:
    """Generate a review question for the current word.

    Picks a question type (translate/fill_blank/recognize) and generates
    a question using Hermano's voice.

    Args:
        state: Current review state with words_to_review and current_word_index.

    Returns:
        Dictionary with current_word, question_type, and question_text.
    """
    words = state["words_to_review"]
    index = state["current_word_index"]

    if index >= len(words):
        # No more words - session complete
        return {
            "current_word": None,
            "question_type": None,
            "question_text": None,
        }

    word = words[index]
    level = state["level"]
    language = state["language"]

    # Pick question type
    question_type = _pick_question_type(level)

    # Get language name
    lang_data = LANGUAGE_ADAPTER.get(language, LANGUAGE_ADAPTER["es"])
    language_name = lang_data["language_name"]

    # Generate question with LLM
    llm = get_llm("creative")
    prompt = QUESTION_PROMPTS[question_type].format(
        word=word.get("word", ""),
        translation=word.get("translation", ""),
        language_name=language_name,
        level=level,
    )

    response = await llm.ainvoke(
        [
            SystemMessage(content=prompt),
            HumanMessage(content="Generate the review question."),
        ]
    )

    return {
        "current_word": word,
        "question_type": question_type,
        "question_text": str(response.content),
    }


async def evaluate_answer_node(state: ReviewState) -> dict[str, Any]:
    """Evaluate user's answer and generate feedback.

    Compares the user's answer to the correct answer, infers a quality score,
    and generates Hermano-style feedback.

    Args:
        state: Current review state with current_word and user_answer.

    Returns:
        Dictionary with quality_score, feedback_text, and updated results.
    """
    word = state.get("current_word")
    user_answer = state.get("user_answer", "")
    question_type = state.get("question_type", "translate")
    language = state["language"]

    if not word:
        return {
            "quality_score": None,
            "feedback_text": None,
        }

    # Determine correct answer based on question type
    if question_type == "recognize":
        # User should give English translation
        correct_answer = str(word.get("translation", ""))
    else:
        # User should give target language word
        correct_answer = str(word.get("word", ""))

    # Infer quality score
    quality_score = _infer_quality_score(user_answer, correct_answer)
    is_correct = quality_score >= 3

    # Get language name for feedback
    lang_data = LANGUAGE_ADAPTER.get(language, LANGUAGE_ADAPTER["es"])
    language_name = lang_data["language_name"]

    # Determine feedback type
    if quality_score >= 4:
        feedback_type = "correct"
    elif quality_score >= 2:
        feedback_type = "almost"
    else:
        feedback_type = "incorrect"

    # Generate feedback with LLM
    llm = get_llm("creative")
    prompt = FEEDBACK_PROMPTS[feedback_type].format(
        word=word.get("word", ""),
        translation=word.get("translation", ""),
        user_answer=user_answer,
        question_type=question_type,
        language_name=language_name,
    )

    response = await llm.ainvoke(
        [
            SystemMessage(content=prompt),
            HumanMessage(content="Generate the feedback."),
        ]
    )

    # Update results list
    results = list(state.get("results", []))
    results.append(
        {
            "word_id": word.get("id"),
            "quality": quality_score,
            "correct": is_correct,
        }
    )

    return {
        "quality_score": quality_score,
        "feedback_text": str(response.content),
        "results": results,
    }


async def update_sm2_node(state: ReviewState, config: RunnableConfig) -> dict[str, Any]:
    """Update SM-2 scheduling for the reviewed word.

    Calls ReviewService.update_sm2() to persist the new interval
    and easiness factor based on the quality score.

    Args:
        state: Current review state with current_word and quality_score.
        config: LangGraph config; supabase_client passed via config["configurable"].

    Returns:
        Dictionary with current_word_index incremented.
    """
    configurable = config.get("configurable", {})
    supabase_client = configurable.get("supabase_client")

    word = state.get("current_word")
    quality_score = state.get("quality_score")
    user_id = state["user_id"]

    word_id_raw = word.get("id") if word else None
    # Convert to int safely - word_id comes from Vocabulary.id which is int | None
    word_id: int | None = None
    if word_id_raw is not None:
        word_id = int(str(word_id_raw))
    if word and quality_score is not None and word_id is not None:
        try:
            # Import lazily to avoid circular imports
            from src.services.review import ReviewService

            # Use user-scoped client passed through config for RLS compliance
            service = ReviewService(user_id, client=supabase_client)
            service.update_sm2(vocab_id=word_id, quality=quality_score)
        except APIError as e:
            # Log but don't fail the session
            import logging

            logger = logging.getLogger(__name__)
            logger.warning("Failed to update SM-2 for word %s: %s", word_id, e)

    # Increment index to move to next word
    return {
        "current_word_index": state["current_word_index"] + 1,
    }
