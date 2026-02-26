"""Micro-lesson endpoints for structured learning content.

Phase 12: Added review word initialization on lesson completion.
Phase 9: Added AI-enhanced endpoints using LangGraph subgraphs.
Phase 7: Added lesson completion persistence for authenticated users.
Phase 6: Full implementation of lesson API routes.
B7: Extracted business logic to src.services.lesson_completion (SRP refactor).

Provides lesson listing, content delivery, step navigation, exercises,
and progress tracking. Supports both authenticated users and guests.

AI-Enhanced endpoints (Phase 9):
- GET /{lesson_id}/step/{step_index}/enhanced - AI-enhanced step content
- POST /{lesson_id}/exercise/{exercise_id}/submit/enhanced - AI-enhanced feedback
"""

import contextlib
import logging
from typing import Annotated

from fastapi import APIRouter, Cookie, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from src.api.auth import OptionalUserDep
from src.api.cookies import set_secure_cookie
from src.api.dependencies import LessonServiceDep, TemplatesDep
from src.lessons.models import LessonLevel
from src.services.lesson_completion import (
    check_exercise_answer,
    complete_lesson_and_persist,
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
    """Render the lesson player page for interactive learning."""
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    steps = lesson.content.get_ordered_steps()

    return templates.TemplateResponse(
        request=request,
        name="lesson_player.html",
        context={
            "lesson": lesson,
            "step": steps[0] if steps else None,
            "current_step": 0,
            "total_steps": len(steps),
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
    """Get a specific lesson step as partial HTML."""
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    steps = lesson.content.get_ordered_steps()
    if step_index < 0 or step_index >= len(steps):
        raise HTTPException(
            status_code=404,
            detail=f"Step {step_index} not found. Lesson has {len(steps)} steps.",
        )

    return templates.TemplateResponse(
        request=request,
        name="partials/lesson_step.html",
        context={
            "step": steps[step_index],
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
    """Navigate to the next step in the lesson."""
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    steps = lesson.content.get_ordered_steps()
    next_index = min(current_step + 1, len(steps) - 1)

    return templates.TemplateResponse(
        request=request,
        name="partials/lesson_step.html",
        context={
            "step": steps[next_index],
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
    """Navigate to the previous step in the lesson."""
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    steps = lesson.content.get_ordered_steps()
    prev_index = max(current_step - 1, 0)

    return templates.TemplateResponse(
        request=request,
        name="partials/lesson_step.html",
        context={
            "step": steps[prev_index],
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
    """Get an exercise as partial HTML for interactive practice."""
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
    """Submit an answer for an exercise and return feedback HTML."""
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    exercise = lesson.content.get_exercise_by_id(exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=404,
            detail=f"Exercise not found: {exercise_id}",
        )

    feedback = check_exercise_answer(exercise, answer)
    return HTMLResponse(content=feedback.feedback_html)


# =============================================================================
# AI-Enhanced Endpoints (Phase 9)
# =============================================================================


@router.get("/{lesson_id}/step/{step_index}/enhanced", response_class=HTMLResponse)
async def get_enhanced_lesson_step(
    request: Request,
    templates: TemplatesDep,
    _user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    lesson_id: str,
    step_index: int,
    level: str = "A1",
    language: str = "es",
) -> HTMLResponse:
    """Get AI-enhanced lesson step content via the lesson subgraph."""
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    steps = lesson.content.get_ordered_steps()
    if step_index < 0 or step_index >= len(steps):
        raise HTTPException(
            status_code=404,
            detail=f"Step {step_index} not found. Lesson has {len(steps)} steps.",
        )

    from src.agent.lesson_graph import lesson_subgraph

    result = await lesson_subgraph.ainvoke(
        {
            "lesson_id": lesson_id,
            "step_index": step_index,
            "level": level,
            "language": language,
            "messages": [],
        }
    )

    return templates.TemplateResponse(
        request=request,
        name="partials/lesson_step_enhanced.html",
        context={
            "step_type": result.get("step_type", "instruction"),
            "step_content": result.get("step_content", ""),
            "step_vocabulary": result.get("step_vocabulary", []),
            "step_target_text": result.get("step_target_text"),
            "step_translation": result.get("step_translation"),
            "enhanced_content": result.get("enhanced_content", ""),
            "hermano_intro": result.get("hermano_intro", ""),
            "step_index": step_index,
            "lesson_id": lesson_id,
            "total_steps": len(steps),
            "level": level,
            "language": language,
        },
    )


@router.post("/{lesson_id}/exercise/{exercise_id}/submit/enhanced", response_class=HTMLResponse)
async def submit_exercise_enhanced(
    request: Request,
    templates: TemplatesDep,
    _user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    lesson_id: str,
    exercise_id: str,
    answer: str = Form(...),
    level: str = Form("A1"),
    language: str = Form("es"),
) -> HTMLResponse:
    """Submit exercise with AI-generated personalized feedback from Hermano."""
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    exercise = lesson.content.get_exercise_by_id(exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=404,
            detail=f"Exercise not found: {exercise_id}",
        )

    from src.agent.lesson_graph import exercise_validation_graph

    result = await exercise_validation_graph.ainvoke(
        {
            "lesson_id": lesson_id,
            "exercise_id": exercise_id,
            "user_answer": answer,
            "level": level,
            "language": language,
            "messages": [],
        }
    )

    return templates.TemplateResponse(
        request=request,
        name="partials/exercise_feedback_enhanced.html",
        context={
            "is_correct": result.get("is_correct", False),
            "feedback": result.get("exercise_feedback", ""),
            "lesson_id": lesson_id,
            "exercise_id": exercise_id,
            "level": level,
            "language": language,
        },
    )


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
    """Mark a lesson as completed and show completion view."""
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    vocabulary = lesson_service.get_lesson_vocabulary(lesson_id)

    result = complete_lesson_and_persist(
        user=user,
        session_id=session_id,
        lesson_id=lesson_id,
        score=score,
        vocabulary=vocabulary,
        language=lesson.metadata.language,
    )

    response = templates.TemplateResponse(
        request=request,
        name="partials/lesson_complete.html",
        context={
            "lesson_id": lesson_id,
            "lesson": lesson,
            "completed": True,
            "score": score,
            "vocab_count": result.vocab_count,
            "user": user,
            "next_path_lesson": result.next_path_lesson,
        },
    )

    # Set session cookie for first-time guests
    if result.new_session_id:
        set_secure_cookie(
            response,
            key="session_id",
            value=result.new_session_id,
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
    """Hand off from lesson to chat conversation via HX-Redirect."""
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    redirect_url = f"/chat?lesson={lesson_id}&topic={lesson.metadata.category or 'general'}"

    response = Response(status_code=200)
    response.headers["HX-Redirect"] = redirect_url
    return response
