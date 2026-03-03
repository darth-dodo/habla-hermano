"""Lesson chat routes for Phase 19 conversational lesson delivery.

Provides endpoints for the conversational lesson experience where Hermano
teaches YAML lesson content through the chat UI.

Endpoints:
- GET /chat/lesson/{lesson_id} — Render lesson chat page
- POST /chat/lesson/stream — Stream lesson chat as SSE events
"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from postgrest.exceptions import APIError
from sse_starlette.sse import EventSourceResponse

from src.agent.checkpointer import get_checkpointer
from src.agent.lesson_chat_graph import build_lesson_chat_graph
from src.api.auth import OptionalUserDep
from src.api.cookies import set_secure_cookie
from src.api.dependencies import LessonServiceDep, SettingsDep, TemplatesDep
from src.api.rate_limit import CHAT_RATE_LIMIT_CALLS, CHAT_RATE_LIMIT_PERIOD, rate_limited
from src.api.streaming import StreamResult, stream_chat_events
from src.api.supabase_client import get_supabase_for_user
from src.api.validation import MAX_MESSAGE_LENGTH
from src.services.lesson_completion import complete_lesson_and_persist

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat/lesson", tags=["lesson_chat"])


def _resolve_lesson_thread_id(
    user_id: str | None,
    session_id: str | None,
    lesson_id: str,
) -> tuple[str, str | None, str | None]:
    """Build a lesson-scoped thread ID.

    Format: lesson:{user_or_session_id}:{lesson_id}

    Returns:
        Tuple of (thread_id, effective_user_id, new_session_id).
    """
    if user_id:
        return f"lesson:{user_id}:{lesson_id}", user_id, None
    if session_id:
        return f"lesson:{session_id}:{lesson_id}", None, None
    new_id = str(uuid.uuid4())
    return f"lesson:{new_id}:{lesson_id}", None, new_id


@router.get("/{lesson_id}", response_class=HTMLResponse)
async def lesson_chat_page(
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
    user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    lesson_id: str,
    session_id: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """Render the chat interface in lesson mode.

    Loads the lesson metadata and renders chat.html with lesson-specific
    context so the frontend knows to auto-start and stream to the lesson
    endpoint.
    """
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson_id}")

    context: dict[str, Any] = {
        "app_name": settings.APP_NAME,
        "debug": settings.DEBUG,
        "user": user,
        "review_mode": False,
        "show_warmup": False,
        "review_stats": None,
        "current_language": lesson.metadata.language,
        "voice_enabled": settings.voice_enabled,
        # Lesson mode context
        "lesson_mode": True,
        "lesson_id": lesson_id,
        "lesson_title": lesson.metadata.title,
        "lesson_description": lesson.metadata.description,
        "lesson_level": str(lesson.metadata.level),
        "lesson_language": lesson.metadata.language,
    }

    response = templates.TemplateResponse(
        request=request,
        name="chat.html",
        context=context,
    )

    # Set session cookie for guests
    if not user and not session_id:
        set_secure_cookie(
            response,
            key="session_id",
            value=str(uuid.uuid4()),
            max_age=60 * 60 * 24 * 7,
        )

    return response


@router.post("/stream")
@rate_limited(calls=CHAT_RATE_LIMIT_CALLS, period=CHAT_RATE_LIMIT_PERIOD)
async def stream_lesson_message(
    request: Request,  # noqa: ARG001
    templates: TemplatesDep,
    user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    message: Annotated[str, Form()],
    lesson_id: Annotated[str, Form()],
    session_id: Annotated[str | None, Cookie()] = None,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
) -> EventSourceResponse:
    """Stream a lesson chat response as SSE events.

    Uses the lesson-specific LangGraph graph which includes the phase machine
    (intro -> teaching -> exercise_ask -> exercise_eval -> complete).

    Level and language are derived from the lesson metadata, not from client
    input, ensuring the correct difficulty and language are always used.
    """
    # Validate
    message = message.strip()
    if not message:
        return EventSourceResponse(
            content=_stream_error("Message cannot be empty."),
            media_type="text/event-stream",
        )

    if len(message) > MAX_MESSAGE_LENGTH:
        return EventSourceResponse(
            content=_stream_error(f"Message is too long (max {MAX_MESSAGE_LENGTH} characters)."),
            media_type="text/event-stream",
        )

    # Load lesson
    lesson = lesson_service.get_lesson(lesson_id)
    if not lesson:
        return EventSourceResponse(
            content=_stream_error(f"Lesson not found: {lesson_id}"),
            media_type="text/event-stream",
        )

    # Authoritative level/language from lesson metadata (not Form input)
    level = str(lesson.metadata.level)
    language = lesson.metadata.language

    # Resolve identity
    effective_user_id = user.id if user else None
    thread_id, effective_user_id, new_session_id = _resolve_lesson_thread_id(
        effective_user_id, session_id, lesson_id
    )

    user_client = get_supabase_for_user(sb_access_token) if sb_access_token else None

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        """Stream lesson chat events with post-stream lesson completion."""
        result = StreamResult()

        async with get_checkpointer() as checkpointer:
            graph = build_lesson_chat_graph(checkpointer=checkpointer)

            inputs: dict[str, Any] = {
                "messages": [HumanMessage(content=message)],
                "level": level,
                "language": language,
                "user_id": effective_user_id,
                "supabase_client": user_client,
                # Lesson-specific state
                "lesson_id": lesson_id,
                "lesson_data": lesson.model_dump(),
                "lesson_phase": "intro",
                "step_index": 0,
                "exercise_index": 0,
                "exercise_results": [],
                "lesson_score": 0,
            }
            graph_config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

            async for event in stream_chat_events(
                graph=graph,
                inputs=inputs,
                config=graph_config,
                templates=templates,
                level=level,
                result=result,
            ):
                yield event

            # Post-stream: check if lesson was completed and persist
            # Get final state from checkpoint
            state = await graph.aget_state(RunnableConfig(configurable={"thread_id": thread_id}))
            state_values = state.values if state else {}

            if state_values.get("lesson_completed"):
                lesson_ui = state_values.get("lesson_ui", {})
                score = lesson_ui.get("score", state_values.get("lesson_score", 0))
                vocab_count = lesson_ui.get("vocab_count", 0)

                # Emit lesson_complete SSE event
                yield {
                    "event": "lesson_complete",
                    "data": json.dumps({
                        "score": score,
                        "vocab_count": vocab_count,
                        "lesson_id": lesson_id,
                    }),
                }

                # Persist completion for authenticated users
                if effective_user_id and user:
                    try:
                        vocabulary = lesson_service.get_lesson_vocabulary(lesson_id)
                        complete_lesson_and_persist(
                            user=user,
                            session_id=session_id,
                            lesson_id=lesson_id,
                            score=score,
                            vocabulary=vocabulary,
                            language=language,
                        )
                    except APIError:
                        logger.exception(
                            "Failed to persist lesson completion for user %s",
                            effective_user_id,
                        )

            # Emit lesson_progress on every turn
            lesson_ui = state_values.get("lesson_ui", {})
            if lesson_ui:
                yield {
                    "event": "lesson_progress",
                    "data": json.dumps(lesson_ui),
                }

            # Emit exercise_result if present
            exercise_result = lesson_ui.get("exercise_result")
            if exercise_result:
                yield {
                    "event": "exercise_result",
                    "data": json.dumps(exercise_result),
                }

    headers: dict[str, str] = {"Cache-Control": "no-cache"}
    response = EventSourceResponse(
        content=event_generator(),
        headers=headers,
        send_timeout=60,
    )

    if new_session_id:
        set_secure_cookie(
            response,
            key="session_id",
            value=new_session_id,
            max_age=60 * 60 * 24 * 7,
        )

    return response


async def _stream_error(error_message: str) -> AsyncGenerator[dict[str, str], None]:
    """Yield a single error event for validation failures."""
    yield {"event": "error", "data": json.dumps({"message": error_message})}
    yield {"event": "done", "data": "{}"}
