"""Review endpoints for spaced repetition.

Phase 12: Implements spaced repetition review sessions using the SM-2 algorithm.
Requires authentication - spaced repetition is an authenticated-only feature.

Session state is stored in a signed cookie (itsdangerous) to prevent
clients from tampering with word IDs, scores, or progress.

Endpoints:
- GET /review/stats - Get review statistics (due count, next review time)
- POST /review/start - Start a review session
- POST /review/answer - Submit answer to current question
- POST /review/end - End session early
- DELETE /review/warmup-prompt - Dismiss warmup prompt
"""

import logging
import random
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Cookie, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from postgrest.exceptions import APIError

from src.api.auth import CurrentUserDep
from src.api.cookies import (
    delete_secure_cookie,
    set_secure_cookie,
    sign_cookie_value,
    unsign_json_cookie,
)
from src.api.dependencies import TemplatesDep
from src.api.supabase_client import get_supabase_for_user
from src.db.models import Vocabulary
from src.db.repository import VocabularyRepository
from src.services.review import ReviewService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/review", tags=["review"])

# Maximum age for review session cookie signatures (1 hour).
_REVIEW_SESSION_MAX_AGE = 60 * 60


# =============================================================================
# Helpers
# =============================================================================


def _get_review_session_cookie_name() -> str:
    """Get the cookie name for storing review session state."""
    return "review_session"


def _get_warmup_dismissed_cookie_name() -> str:
    """Get the cookie name for warmup dismissal tracking."""
    return "warmup_dismissed"


def _generate_question(
    vocab: Vocabulary, question_type: str | None = None
) -> dict[str, str | int | None]:
    """Generate a review question for a vocabulary word.

    Args:
        vocab: The vocabulary item to create a question for.
        question_type: Optional specific type. If None, randomly chosen.

    Returns:
        Dictionary with question details:
        - type: "translate" | "recognize" | "fill_blank"
        - prompt: The question text
        - word_id: The vocabulary ID
        - correct_answer: The expected answer
        - word: The target word
        - translation: The translation
    """
    if question_type is None:
        question_type = random.choice(["translate", "recognize"])

    if question_type == "translate":
        # Ask user to translate from English to target language
        prompt = f"How do you say '{vocab.translation}'?"
        correct_answer = vocab.word.lower()
    else:  # recognize
        # Ask user what the target word means
        prompt = f"What does '{vocab.word}' mean?"
        correct_answer = vocab.translation.lower()

    return {
        "type": question_type,
        "prompt": prompt,
        "word_id": vocab.id,
        "correct_answer": correct_answer,
        "word": vocab.word,
        "translation": vocab.translation,
    }


def _evaluate_answer(user_answer: str, correct_answer: str) -> tuple[bool, int]:
    """Evaluate user's answer and determine SM-2 quality score.

    Args:
        user_answer: The user's submitted answer.
        correct_answer: The expected correct answer.

    Returns:
        Tuple of (is_correct, quality_score) where quality is 0-5.
    """
    user_clean = user_answer.strip().lower()
    correct_clean = correct_answer.strip().lower()

    if user_clean == correct_clean:
        # Perfect match
        return True, 5
    elif user_clean and (
        user_clean in correct_clean
        or correct_clean in user_clean
        or _levenshtein_distance(user_clean, correct_clean) <= 2
    ):
        # Close match (minor typo)
        return True, 4
    else:
        # Incorrect
        return False, 2


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings.

    Simple edit distance for typo detection.
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


def _get_hermano_feedback(quality: int, vocab: Vocabulary) -> str:
    """Generate Hermano-style feedback for a review answer.

    Args:
        quality: SM-2 quality score (0-5).
        vocab: The vocabulary item.

    Returns:
        Feedback string in Hermano's voice.
    """
    if quality >= 5:
        responses = [
            f"Nice! '{vocab.word}' - you've got it!",
            f"Perfect! '{vocab.word}' = '{vocab.translation}'",
            f"Nailed it! '{vocab.word}'",
        ]
    elif quality >= 4:
        responses = [
            f"Got it! Small typo but you knew it. '{vocab.word}' = '{vocab.translation}'",
            f"Close enough! '{vocab.word}' means '{vocab.translation}'",
        ]
    elif quality >= 3:
        responses = [
            f"There you go! '{vocab.word}' = '{vocab.translation}'",
        ]
    else:
        responses = [
            f"Not quite! '{vocab.word}' means '{vocab.translation}'. We'll practice this one more.",
            f"Ah, that one's tricky! '{vocab.word}' = '{vocab.translation}'",
            f"No worries! '{vocab.word}' means '{vocab.translation}'. We'll come back to it.",
        ]

    return random.choice(responses)


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/stats")
async def get_review_stats(
    user: CurrentUserDep,
    language: str = "es",
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> dict[str, int | str | None]:
    """Get review statistics for progress page and review prompts.

    Returns the number of words due for review, time until next review,
    and total words in the review rotation. Requires authentication.

    Args:
        user: Authenticated user (required).
        language: Target language to filter by. Defaults to "es".
        sb_access_token: User's Supabase access token from cookie.

    Returns:
        Dictionary with:
        - due_count: Number of words currently due
        - next_review_in: Human-readable time until next review
        - total_in_rotation: Total words scheduled for review
    """
    # Use user-authenticated client for RLS to work with auth.uid()
    user_client = get_supabase_for_user(sb_access_token) if sb_access_token else None
    service = ReviewService(user.id, client=user_client)
    stats = service.get_stats(language=language)

    return {
        "due_count": stats.due_count,
        "next_review_in": stats.next_review_in,
        "total_in_rotation": stats.total_in_rotation,
    }


@router.post("/start", response_class=HTMLResponse)
async def start_review_session(
    request: Request,
    templates: TemplatesDep,
    user: CurrentUserDep,
    count: int | Literal["all"] = 10,
    language: str = "es",
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> HTMLResponse:
    """Initialize a review session and return the first question.

    Creates a review session with the specified number of words and stores
    session state in a signed cookie. Returns the first question as an HTML
    partial. Requires authentication.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        user: Authenticated user (required).
        count: Number of words to review (5, 10, or "all").
        language: Target language. Defaults to "es".
        sb_access_token: User's Supabase access token from cookie.

    Returns:
        HTMLResponse: First review question as partial HTML.
    """
    # Use user-authenticated client for RLS to work with auth.uid()
    user_client = get_supabase_for_user(sb_access_token) if sb_access_token else None
    service = ReviewService(user.id, client=user_client)

    # Get due words
    limit = None if count == "all" else int(count)
    due_words = service.get_due_words(language=language, limit=limit)

    if not due_words:
        return templates.TemplateResponse(
            request=request,
            name="partials/review_empty.html",
            context={"message": "No words due for review! Come back later."},
        )

    # Build session state
    word_ids = [w.id for w in due_words]
    session_state = {
        "word_ids": word_ids,
        "current_index": 0,
        "results": [],
        "language": language,
    }

    # Generate first question
    first_word = due_words[0]
    question = _generate_question(first_word)

    # Create response with session cookie
    html_response = templates.TemplateResponse(
        request=request,
        name="partials/review_question.html",
        context={
            "question": question,
            "current": 1,
            "total": len(word_ids),
            "progress_percent": 0,
        },
    )

    # Store session state in a signed cookie
    set_secure_cookie(
        html_response,
        key=_get_review_session_cookie_name(),
        value=sign_cookie_value(session_state),
        max_age=_REVIEW_SESSION_MAX_AGE,
    )

    return html_response


@router.post("/answer", response_class=HTMLResponse)
async def submit_review_answer(
    request: Request,
    templates: TemplatesDep,
    user: CurrentUserDep,
    word_id: int = Form(...),
    user_answer: str = Form(...),
    review_session: Annotated[str | None, Cookie()] = None,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> HTMLResponse:
    """Submit an answer for the current review question.

    Validates the answer against the correct answer, updates SM-2 scheduling,
    and returns feedback along with the next question (or summary if complete).
    Requires authentication.

    The review_session cookie is signed; tampered values are rejected.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        user: Authenticated user (required).
        word_id: The vocabulary ID being answered.
        user_answer: User's submitted answer.
        review_session: Signed review session state cookie.
        sb_access_token: User's Supabase access token from cookie.

    Returns:
        HTMLResponse: Feedback partial with next question or session summary.

    Raises:
        HTTPException: 400 if no active review session or invalid signature.
    """
    if not review_session:
        raise HTTPException(status_code=400, detail="No active review session.")

    session_state = unsign_json_cookie(review_session, max_age=_REVIEW_SESSION_MAX_AGE)
    if session_state is None:
        raise HTTPException(status_code=400, detail="Invalid review session.")

    # Use user-authenticated client for RLS to work with auth.uid()
    user_client = get_supabase_for_user(sb_access_token) if sb_access_token else None
    service = ReviewService(user.id, client=user_client)

    # Get the vocabulary item
    due_words = service.get_due_words(language=session_state.get("language", "es"))
    vocab = next((w for w in due_words if w.id == word_id), None)

    # If word not in due list, try to get from all vocab
    if vocab is None:
        vocab_repo = VocabularyRepository(user.id, client=user_client)
        all_vocab = vocab_repo.get_all(language=session_state.get("language", "es"))
        vocab = next((w for w in all_vocab if w.id == word_id), None)

    if vocab is None:
        raise HTTPException(status_code=404, detail="Vocabulary not found.")

    # Determine correct answer based on question (we need to infer from session)
    # For simplicity, check both directions
    is_correct, quality = _evaluate_answer(user_answer, vocab.word)
    if not is_correct:
        is_correct, quality = _evaluate_answer(user_answer, vocab.translation)

    # Update SM-2 scheduling
    try:
        service.update_sm2(word_id, quality)
    except APIError:
        logger.exception("Failed to update SM-2 for word %d", word_id)

    # Record result
    session_state["results"].append(
        {
            "word_id": word_id,
            "word": vocab.word,
            "translation": vocab.translation,
            "is_correct": is_correct,
            "quality": quality,
        }
    )

    # Generate feedback
    feedback = _get_hermano_feedback(quality, vocab)

    # Move to next question
    session_state["current_index"] += 1
    current_index = session_state["current_index"]
    word_ids = session_state["word_ids"]
    total = len(word_ids)

    if current_index >= total:
        # Session complete - show summary
        results = session_state["results"]
        correct_count = sum(1 for r in results if r["is_correct"])

        html_response = templates.TemplateResponse(
            request=request,
            name="partials/review_summary.html",
            context={
                "feedback": feedback,
                "is_correct": is_correct,
                "total": total,
                "correct_count": correct_count,
                "results": results,
            },
        )

        # Clear session cookie
        delete_secure_cookie(html_response, key=_get_review_session_cookie_name())

        return html_response

    # Get next word
    next_word_id = word_ids[current_index]
    vocab_repo = VocabularyRepository(user.id, client=user_client)
    all_vocab = vocab_repo.get_all(language=session_state.get("language", "es"))
    next_vocab = next((w for w in all_vocab if w.id == next_word_id), None)

    if next_vocab is None:
        # Skip if word not found, move to next
        session_state["current_index"] += 1
        # Recursive call or show summary
        return await _handle_missing_word(
            request, templates, session_state, user.id, user_client, feedback, is_correct
        )

    next_question = _generate_question(next_vocab)
    progress_percent = int((current_index / total) * 100)

    html_response = templates.TemplateResponse(
        request=request,
        name="partials/review_feedback_question.html",
        context={
            "feedback": feedback,
            "is_correct": is_correct,
            "question": next_question,
            "current": current_index + 1,
            "total": total,
            "progress_percent": progress_percent,
        },
    )

    # Update session cookie (signed)
    set_secure_cookie(
        html_response,
        key=_get_review_session_cookie_name(),
        value=sign_cookie_value(session_state),
        max_age=_REVIEW_SESSION_MAX_AGE,
    )

    return html_response


async def _handle_missing_word(
    request: Request,
    templates: TemplatesDep,
    session_state: dict[str, Any],
    user_id: str,
    user_client: Any,
    feedback: str,
    is_correct: bool,
) -> HTMLResponse:
    """Handle case where a word in the session is missing.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        session_state: Current review session state.
        user_id: Authenticated user's ID.
        user_client: User-authenticated Supabase client.
        feedback: Feedback message from previous answer.
        is_correct: Whether the previous answer was correct.

    Returns:
        HTMLResponse: Next question or session summary.
    """
    word_ids = session_state["word_ids"]
    current_index = session_state["current_index"]
    total = len(word_ids)

    # Find next valid word
    vocab_repo = VocabularyRepository(user_id, client=user_client)
    all_vocab = vocab_repo.get_all(language=session_state.get("language", "es"))
    vocab_map = {v.id: v for v in all_vocab}

    while current_index < total:
        next_word_id = word_ids[current_index]
        if next_word_id in vocab_map:
            next_vocab = vocab_map[next_word_id]
            next_question = _generate_question(next_vocab)
            progress_percent = int((current_index / total) * 100)

            html_response = templates.TemplateResponse(
                request=request,
                name="partials/review_feedback_question.html",
                context={
                    "feedback": feedback,
                    "is_correct": is_correct,
                    "question": next_question,
                    "current": current_index + 1,
                    "total": total,
                    "progress_percent": progress_percent,
                },
            )

            session_state["current_index"] = current_index
            set_secure_cookie(
                html_response,
                key=_get_review_session_cookie_name(),
                value=sign_cookie_value(session_state),
                max_age=_REVIEW_SESSION_MAX_AGE,
            )

            return html_response

        current_index += 1
        session_state["current_index"] = current_index

    # All remaining words are missing - show summary
    results = session_state["results"]
    correct_count = sum(1 for r in results if r["is_correct"])

    html_response = templates.TemplateResponse(
        request=request,
        name="partials/review_summary.html",
        context={
            "feedback": feedback,
            "is_correct": is_correct,
            "total": len(results),
            "correct_count": correct_count,
            "results": results,
        },
    )

    delete_secure_cookie(html_response, key=_get_review_session_cookie_name())
    return html_response


@router.post("/end", response_class=HTMLResponse)
async def end_review_session(
    request: Request,
    templates: TemplatesDep,
    review_session: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """End the current review session early.

    Returns a summary of progress so far and clears the session cookie.
    This endpoint does not require authentication as it only reads
    the session cookie state.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        review_session: Signed review session state cookie.

    Returns:
        HTMLResponse: Session summary partial.
    """
    if not review_session:
        return templates.TemplateResponse(
            request=request,
            name="partials/review_empty.html",
            context={"message": "No active review session."},
        )

    session_state = unsign_json_cookie(review_session, max_age=_REVIEW_SESSION_MAX_AGE)
    if session_state is None:
        return templates.TemplateResponse(
            request=request,
            name="partials/review_empty.html",
            context={"message": "Invalid session state."},
        )

    results = session_state.get("results", [])
    correct_count = sum(1 for r in results if r.get("is_correct"))
    total_attempted = len(results)
    total_planned = len(session_state.get("word_ids", []))

    html_response = templates.TemplateResponse(
        request=request,
        name="partials/review_summary.html",
        context={
            "feedback": "Session ended early. Nice progress!",
            "is_correct": True,  # Neutral state for early end
            "total": total_attempted,
            "correct_count": correct_count,
            "results": results,
            "ended_early": True,
            "remaining": total_planned - total_attempted,
        },
    )

    # Clear session cookie
    delete_secure_cookie(html_response, key=_get_review_session_cookie_name())

    return html_response


@router.delete("/warmup-prompt", response_class=HTMLResponse)
async def dismiss_warmup() -> HTMLResponse:
    """Dismiss the warmup prompt for this browser session.

    Sets a cookie to prevent the warmup prompt from appearing again
    during the current browsing session. This endpoint does not require
    authentication as it only manages a UI preference cookie.

    Returns:
        HTMLResponse: Empty response with cookie set.
    """
    html_response = HTMLResponse(content="", status_code=200)

    # Set dismissal cookie (expires at end of browser session)
    set_secure_cookie(
        html_response,
        key=_get_warmup_dismissed_cookie_name(),
        value="1",
        # No max_age = session cookie, expires when browser closes
    )

    return html_response
