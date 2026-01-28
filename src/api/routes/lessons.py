"""Micro-lesson endpoints for structured learning content.

Phase 7: Added lesson completion persistence for authenticated users.
Phase 6: Full implementation of lesson API routes.

Provides lesson listing, content delivery, step navigation, exercises,
and progress tracking. Supports both authenticated users and guests.
"""

import contextlib
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from src.api.auth import OptionalUserDep
from src.api.dependencies import LessonServiceDep, TemplatesDep
from src.api.supabase_client import get_supabase_admin
from src.db.repository import LessonProgressRepository
from src.lessons.models import (
    FillBlankExercise,
    LessonLevel,
    MultipleChoiceExercise,
    TranslateExercise,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Lesson List
# =============================================================================


@router.get("/", response_class=HTMLResponse)
async def get_lessons_page(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    language: str | None = None,
    level: str | None = None,
) -> HTMLResponse:
    """Render the lessons overview page with available micro-lessons.

    Supports filtering by language and CEFR level. Lesson completion
    status is scoped to the current user.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        user: User if authenticated, None for guests.
        lesson_service: Lesson service for fetching lessons.
        language: Optional language filter (es, de, fr).
        level: Optional CEFR level filter (A0, A1, A2, B1).

    Returns:
        HTMLResponse: Rendered lessons page with lesson cards.

    Raises:
    """
    # Parse level filter if provided
    level_enum = None
    if level:
        with contextlib.suppress(ValueError):
            level_enum = LessonLevel(level)

    # Get lesson metadata for listing
    lessons_metadata = lesson_service.get_lessons_metadata(
        language=language,
        level=level_enum,
    )

    beginner_levels = {LessonLevel.A0, LessonLevel.A1}
    intermediate_levels = {LessonLevel.A2, LessonLevel.B1}

    lessons_grouped = {
        "beginner": [lesson for lesson in lessons_metadata if lesson.level in beginner_levels],
        "intermediate": [
            lesson for lesson in lessons_metadata if lesson.level in intermediate_levels
        ],
    }

    return templates.TemplateResponse(
        request=request,
        name="lessons.html",
        context={
            "lessons": lessons_grouped,
            "language": language or "es",
            "level": level or "A1",
            "user": user,
        },
    )


# =============================================================================
# Lesson Player
# =============================================================================


@router.get("/{lesson_id}/play", response_class=HTMLResponse)
async def get_lesson_player(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    lesson_id: str,
) -> HTMLResponse:
    """Render the lesson player page for interactive learning.

    Displays the lesson content with step navigation and progress tracking.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        user: User if authenticated, None for guests.
        lesson_service: Lesson service for fetching lesson content.
        lesson_id: Unique identifier for the lesson.

    Returns:
        HTMLResponse: Rendered lesson player page.

    Raises:
                HTTPException: 404 if lesson not found.
    """
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    # Get ordered steps
    steps = lesson.content.get_ordered_steps()
    current_step = 0
    total_steps = len(steps)

    return templates.TemplateResponse(
        request=request,
        name="lesson_player.html",
        context={
            "lesson": lesson,
            "step": steps[current_step] if steps else None,
            "current_step": current_step,
            "total_steps": total_steps,
            "user": user,
        },
    )


# =============================================================================
# Step Navigation
# =============================================================================


@router.get("/{lesson_id}/step/{step_index}", response_class=HTMLResponse)
async def get_lesson_step(
    request: Request,
    templates: TemplatesDep,
    _user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    lesson_id: str,
    step_index: int,
) -> HTMLResponse:
    """Get a specific lesson step as partial HTML.

    Returns the step content for HTMX-based navigation without full page reload.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        _user: User if authenticated, None for guests.
        lesson_service: Lesson service for fetching lesson content.
        lesson_id: Unique identifier for the lesson.
        step_index: Zero-based index of the step.

    Returns:
        HTMLResponse: Partial HTML for the step content.

    Raises:
                HTTPException: 404 if lesson or step not found.
    """
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    steps = lesson.content.get_ordered_steps()
    if step_index < 0 or step_index >= len(steps):
        raise HTTPException(
            status_code=404,
            detail=f"Step {step_index} not found. Lesson has {len(steps)} steps.",
        )

    step = steps[step_index]

    return templates.TemplateResponse(
        request=request,
        name="partials/lesson_step.html",
        context={
            "step": step,
            "step_index": step_index,
            "lesson_id": lesson_id,
            "total_steps": len(steps),
        },
    )


@router.post("/{lesson_id}/step/next", response_class=HTMLResponse)
async def next_lesson_step(
    request: Request,
    templates: TemplatesDep,
    _user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    lesson_id: str,
    current_step: int = Form(...),
) -> HTMLResponse:
    """Navigate to the next step in the lesson.

    Increments the step index and returns the next step content.
    If at the last step, returns the same step (boundary handling).

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        _user: User if authenticated, None for guests.
        lesson_service: Lesson service for fetching lesson content.
        lesson_id: Unique identifier for the lesson.
        current_step: Current step index from form data.

    Returns:
        HTMLResponse: Partial HTML for the next step content.

    Raises:
                HTTPException: 404 if lesson not found.
    """
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    steps = lesson.content.get_ordered_steps()
    next_index = min(current_step + 1, len(steps) - 1)
    step = steps[next_index]

    return templates.TemplateResponse(
        request=request,
        name="partials/lesson_step.html",
        context={
            "step": step,
            "step_index": next_index,
            "lesson_id": lesson_id,
            "total_steps": len(steps),
        },
    )


@router.post("/{lesson_id}/step/prev", response_class=HTMLResponse)
async def previous_lesson_step(
    request: Request,
    templates: TemplatesDep,
    _user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    lesson_id: str,
    current_step: int = Form(...),
) -> HTMLResponse:
    """Navigate to the previous step in the lesson.

    Decrements the step index and returns the previous step content.
    If at the first step, returns the same step (boundary handling).

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        _user: User if authenticated, None for guests.
        lesson_service: Lesson service for fetching lesson content.
        lesson_id: Unique identifier for the lesson.
        current_step: Current step index from form data.

    Returns:
        HTMLResponse: Partial HTML for the previous step content.

    Raises:
                HTTPException: 404 if lesson not found.
    """
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    steps = lesson.content.get_ordered_steps()
    prev_index = max(current_step - 1, 0)
    step = steps[prev_index]

    return templates.TemplateResponse(
        request=request,
        name="partials/lesson_step.html",
        context={
            "step": step,
            "step_index": prev_index,
            "lesson_id": lesson_id,
            "total_steps": len(steps),
        },
    )


# =============================================================================
# Exercises
# =============================================================================


@router.get("/{lesson_id}/exercise/{exercise_id}", response_class=HTMLResponse)
async def get_exercise(
    request: Request,
    templates: TemplatesDep,
    _user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    lesson_id: str,
    exercise_id: str,
) -> HTMLResponse:
    """Get an exercise as partial HTML for interactive practice.

    Renders the appropriate exercise template based on exercise type
    (multiple choice, fill blank, translate).

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        _user: User if authenticated, None for guests.
        lesson_service: Lesson service for fetching lesson content.
        lesson_id: Unique identifier for the lesson.
        exercise_id: Unique identifier for the exercise.

    Returns:
        HTMLResponse: Partial HTML for the exercise.

    Raises:
                HTTPException: 404 if lesson or exercise not found.
    """
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    exercise = lesson.content.get_exercise_by_id(exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=404,
            detail=f"Exercise not found: {exercise_id}",
        )

    return templates.TemplateResponse(
        request=request,
        name="partials/lesson_exercise.html",
        context={
            "exercise": exercise,
            "lesson_id": lesson_id,
        },
    )


@router.post("/{lesson_id}/exercise/{exercise_id}/submit", response_class=HTMLResponse)
async def submit_exercise(
    _user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    lesson_id: str,
    exercise_id: str,
    answer: str = Form(...),
) -> HTMLResponse:
    """Submit an answer for an exercise.

    Validates the answer against the exercise's correct answer and returns
    feedback HTML indicating whether the answer was correct or incorrect.

    Args:
        _user: User if authenticated, None for guests.
        lesson_service: Lesson service for fetching lesson content.
        lesson_id: Unique identifier for the lesson.
        exercise_id: Unique identifier for the exercise.
        answer: User's submitted answer.

    Returns:
        HTMLResponse: Feedback HTML with result and explanation.

    Raises:
                HTTPException: 404 if lesson or exercise not found.
    """
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    exercise = lesson.content.get_exercise_by_id(exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=404,
            detail=f"Exercise not found: {exercise_id}",
        )

    # Check answer based on exercise type
    is_correct = False
    correct_answer = ""

    if isinstance(exercise, MultipleChoiceExercise):
        # For multiple choice, answer is the index
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

    # Build feedback response
    feedback_html = f"""
    <div class="exercise-feedback {"correct" if is_correct else "incorrect"}">
        <p class="result">{"Correct!" if is_correct else "Incorrect - try again"}</p>
        {f'<p class="correct-answer">Correct answer: {correct_answer}</p>' if not is_correct else ""}
        {f'<p class="explanation">{exercise.explanation}</p>' if exercise.explanation else ""}
    </div>
    """

    return HTMLResponse(content=feedback_html)


# =============================================================================
# Lesson Completion
# =============================================================================


@router.post("/{lesson_id}/complete", response_class=HTMLResponse)
async def complete_lesson(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    lesson_id: str,
    score: int = Form(default=100),
    session_id: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """Mark a lesson as completed and show completion view.

    Records the lesson completion for the current user and displays
    a celebration view with score and next steps.

    Args:
        request: FastAPI request for template context.
        templates: Jinja2 template engine.
        user: User if authenticated, None for guests.
        lesson_service: Lesson service for fetching lesson content.
        lesson_id: Unique identifier for the completed lesson.
        score: User's score on the lesson (0-100).

    Returns:
        HTMLResponse: Completion celebration view with score and links.

    Raises:
                HTTPException: 404 if lesson not found.
    """
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    # Get vocabulary count from lesson
    vocabulary = lesson_service.get_lesson_vocabulary(lesson_id)
    vocab_count = len(vocabulary)

    # Persist lesson completion for any user with identity
    effective_id: str | None = None
    new_session_id: str | None = None

    if user:
        effective_id = user.id
    elif session_id:
        effective_id = session_id
    else:
        # First-time guest completing a lesson — create session cookie
        new_session_id = str(uuid.uuid4())
        effective_id = new_session_id

    if effective_id:
        try:
            client = None
            if not user:
                client = get_supabase_admin()
            repo = LessonProgressRepository(effective_id, client=client)
            repo.complete_lesson(lesson_id, score=score)
        except Exception:
            logger.exception("Failed to persist lesson completion for user %s", effective_id)

    response = templates.TemplateResponse(
        request=request,
        name="partials/lesson_complete.html",
        context={
            "lesson_id": lesson_id,
            "lesson": lesson,
            "completed": True,
            "score": score,
            "vocab_count": vocab_count,
            "user": user,
        },
    )

    # Set session cookie for first-time guests
    if new_session_id:
        response.set_cookie(
            key="session_id",
            value=new_session_id,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 7,  # 7 days
        )

    return response


# =============================================================================
# Lesson Handoff to Chat
# =============================================================================


@router.post("/{lesson_id}/handoff")
async def handoff_to_chat(
    _user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    lesson_id: str,
) -> Response:
    """Hand off from lesson to chat conversation.

    Prepares context from the completed lesson (vocabulary, topics) and
    redirects to the chat page where the user can practice with Hermano.

    Uses HX-Redirect header for HTMX-based navigation.

    Args:
        _user: User if authenticated, None for guests.
        lesson_service: Lesson service for fetching lesson content.
        lesson_id: Unique identifier for the lesson.

    Returns:
        Response: Empty response with HX-Redirect header to /chat.

    Raises:
                HTTPException: 404 if lesson not found.
    """
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    # Build redirect URL with lesson context
    # The chat page can use query params to initialize conversation context
    redirect_url = f"/chat?lesson={lesson_id}&topic={lesson.metadata.category or 'general'}"

    # Return response with HX-Redirect header for HTMX
    response = Response(status_code=200)
    response.headers["HX-Redirect"] = redirect_url

    return response
