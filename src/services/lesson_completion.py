"""Lesson completion service for exercise validation and progress persistence.

Extracted from src/api/routes/lessons.py (B7: SRP refactor).
Handles business logic for:
- Exercise answer checking and feedback generation
- Lesson completion persistence (auth users + guests)
- Vocabulary initialization for spaced repetition review
- Next learning path lesson computation
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from markupsafe import escape
from postgrest.exceptions import APIError

from src.db.client import get_supabase_admin
from src.db.repository import LessonProgressRepository, VocabularyRepository
from src.lessons.models import (
    FillBlankExercise,
    MultipleChoiceExercise,
    TranslateExercise,
)
from src.services.review import ReviewService

if TYPE_CHECKING:
    from supabase import Client as SupabaseClient

    from src.api.auth import AuthenticatedUser
    from src.lessons.models import AnyExercise


def _bare_lesson_id(lesson_id: str) -> str:
    """Extract bare lesson ID from a full path ID.

    Handles both full IDs (``es/A1/greetings-001``) and bare IDs
    (``greetings-001``), returning the bare form in either case.
    """
    return lesson_id.rsplit("/", 1)[-1] if "/" in lesson_id else lesson_id


logger = logging.getLogger(__name__)


# =============================================================================
# Data Transfer Objects
# =============================================================================


@dataclass(frozen=True)
class ExerciseFeedback:
    """Result of checking an exercise answer.

    Attributes:
        is_correct: Whether the user's answer was correct.
        correct_answer: The expected correct answer text.
        explanation: Optional explanation from the exercise.
        feedback_html: Pre-rendered HTML feedback string.
    """

    is_correct: bool
    correct_answer: str
    explanation: str | None
    feedback_html: str


@dataclass
class CompletionResult:
    """Result of lesson completion persistence.

    Attributes:
        effective_id: The user or session ID used for persistence.
        new_session_id: New guest session ID if created, else None.
        next_path_lesson: Next recommended lesson, or None.
        vocab_count: Number of vocabulary words in the lesson.
    """

    effective_id: str | None
    new_session_id: str | None
    next_path_lesson: object | None  # LearningPathLesson or None
    vocab_count: int


# =============================================================================
# Exercise Validation
# =============================================================================


def check_exercise_answer(exercise: AnyExercise, answer: str) -> ExerciseFeedback:
    """Check a user's answer against an exercise and build feedback.

    Validates the answer based on exercise type (multiple choice, fill blank,
    translate) and generates HTML feedback with correct/incorrect indication.

    Args:
        exercise: The exercise model to check against.
        answer: The user's submitted answer string.

    Returns:
        ExerciseFeedback with correctness, correct answer, and HTML feedback.
    """
    is_correct = False
    correct_answer = ""

    if isinstance(exercise, MultipleChoiceExercise):
        try:
            selected_index = int(answer)
            is_correct = selected_index == exercise.correct_index
            correct_answer = exercise.options[exercise.correct_index]
        except (ValueError, IndexError):
            is_correct = False
            correct_answer = exercise.options[exercise.correct_index]

    elif isinstance(exercise, FillBlankExercise):
        is_correct = exercise.check_answer(answer)
        correct_answer = exercise.correct_answer

    elif isinstance(exercise, TranslateExercise):
        is_correct = exercise.check_answer(answer)
        correct_answer = exercise.correct_translation

    # Build feedback HTML (escape user-facing content to prevent XSS)
    css_class = "correct" if is_correct else "incorrect"
    result_text = "Correct!" if is_correct else "Incorrect - try again"
    answer_html = (
        f'<p class="correct-answer">Correct answer: {escape(correct_answer)}</p>'
        if not is_correct
        else ""
    )
    explanation_html = (
        f'<p class="explanation">{escape(exercise.explanation)}</p>' if exercise.explanation else ""
    )
    feedback_html = f"""
    <div class="exercise-feedback {css_class}">
        <p class="result">{result_text}</p>
        {answer_html}
        {explanation_html}
    </div>
    """

    return ExerciseFeedback(
        is_correct=is_correct,
        correct_answer=correct_answer,
        explanation=exercise.explanation,
        feedback_html=feedback_html,
    )


# =============================================================================
# Vocabulary Review Initialization
# =============================================================================


def initialize_lesson_vocabulary_for_review(
    effective_id: str,
    vocabulary: list[dict[str, str]],
    language: str,
    client: SupabaseClient | None = None,
) -> None:
    """Initialize vocabulary from a lesson for spaced repetition review.

    Upserts each vocabulary word and schedules it for review if not already
    scheduled. Called after lesson completion to ensure learned words enter
    the review rotation.

    Args:
        effective_id: User ID or guest session ID.
        vocabulary: List of vocabulary dicts with 'word' and 'translation' keys.
        language: Target language code (es, de, fr).
        client: Optional Supabase client for guest access.
    """
    if not vocabulary:
        return

    vocab_repo = VocabularyRepository(effective_id, client=client)
    review_service = ReviewService(effective_id, client=client)

    for word_entry in vocabulary:
        try:
            # Upsert the vocabulary word
            vocab = vocab_repo.upsert(
                word=word_entry.get("word", ""),
                translation=word_entry.get("translation", ""),
                language=language,
                part_of_speech=word_entry.get("part_of_speech"),
            )

            # Schedule for review if not already scheduled
            if vocab.id and vocab.next_review_at is None:
                review_service.initialize_word_for_review(vocab.id)
        except APIError:
            # Log but continue with other words
            logger.exception(
                "Failed to initialize word '%s' for review",
                word_entry.get("word", "unknown"),
            )


# =============================================================================
# Lesson Completion Orchestration
# =============================================================================


def complete_lesson_and_persist(
    *,
    user: AuthenticatedUser | None,
    session_id: str | None,
    lesson_id: str,
    score: int,
    vocabulary: list[dict[str, str]],
    language: str,
) -> CompletionResult:
    """Persist lesson completion and initialize vocabulary for review.

    Handles identity resolution (auth user, existing guest session, or new
    guest), persists completion to the DB, initializes vocabulary for spaced
    repetition, and computes the next learning path lesson.

    Args:
        user: Authenticated user, or None for guests.
        session_id: Existing guest session cookie value, or None.
        lesson_id: ID of the completed lesson.
        score: User's score on the lesson (0-100).
        vocabulary: Vocabulary items from the lesson.
        language: Target language code (es, de, fr).

    Returns:
        CompletionResult with persistence metadata and next lesson info.
    """
    # Resolve effective identity
    effective_id: str | None = None
    new_session_id: str | None = None

    if user:
        effective_id = user.id
    elif session_id:
        effective_id = session_id
    else:
        # First-time guest completing a lesson -- create session cookie
        new_session_id = str(uuid.uuid4())
        effective_id = new_session_id

    repo = None
    next_path_lesson = None

    if effective_id:
        try:
            client = None
            if not user:
                client = get_supabase_admin()
            repo = LessonProgressRepository(effective_id, client=client)
            repo.complete_lesson(_bare_lesson_id(lesson_id), score=score)

            # Initialize vocabulary for review (Phase 12)
            initialize_lesson_vocabulary_for_review(
                effective_id=effective_id,
                vocabulary=vocabulary,
                language=language,
                client=client,
            )
        except APIError:
            logger.exception("Failed to persist lesson completion for user %s", effective_id)

    # Phase 14: Compute next lesson in the learning path
    if repo:
        try:
            from src.services.paths import get_path_service  # noqa: PLC0415

            path_service = get_path_service()
            all_progress = repo.get_completed()
            next_path_lesson = path_service.get_next_path_lesson(language, all_progress)
        except (APIError, KeyError, ValueError):
            logger.exception("Failed to get next path lesson for user %s", effective_id)

    return CompletionResult(
        effective_id=effective_id,
        new_session_id=new_session_id,
        next_path_lesson=next_path_lesson,
        vocab_count=len(vocabulary),
    )
