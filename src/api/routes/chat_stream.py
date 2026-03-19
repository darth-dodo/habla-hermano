"""SSE streaming chat endpoint.

Extracted from chat.py to reduce module complexity.
Handles POST /chat/stream for real-time token delivery via Server-Sent Events.

Phase 15: Real-time token streaming for the chat interface.
Phase 23: Unified endpoint — when ``lesson_id`` is present, routes to the
lesson chat graph instead of the freeform graph.
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Form, Request
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from postgrest.exceptions import APIError
from sse_starlette.sse import EventSourceResponse

from src.agent.checkpointer import get_checkpointer
from src.agent.graph import build_graph
from src.agent.lesson_chat_graph import build_lesson_chat_graph
from src.api.auth import OptionalUserDep
from src.api.cookies import set_secure_cookie, sign_session_id
from src.api.dependencies import LessonServiceDep, TemplatesDep
from src.api.rate_limit import CHAT_RATE_LIMIT_CALLS, CHAT_RATE_LIMIT_PERIOD, rate_limited
from src.api.routes.chat import _resolve_chat_identity, _resolve_lesson_thread_id
from src.api.streaming import StreamResult, stream_chat_events
from src.api.supabase_client import get_supabase_for_user
from src.api.validation import MAX_MESSAGE_LENGTH, VALID_LANGUAGES, VALID_LEVELS
from src.services.lesson_completion import complete_lesson_and_persist
from src.services.progress import ProgressService
from src.services.thread_titling import generate_thread_title
from src.services.threads import ThreadService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


async def _stream_error(error_message: str) -> AsyncGenerator[dict[str, str], None]:
    """Yield a single error event for validation failures.

    Args:
        error_message: Human-readable error message.

    Yields:
        Error SSE event followed by done event.
    """
    yield {"event": "error", "data": json.dumps({"message": error_message})}
    yield {"event": "done", "data": "{}"}


@router.post("/chat/stream")
@rate_limited(calls=CHAT_RATE_LIMIT_CALLS, period=CHAT_RATE_LIMIT_PERIOD)
async def stream_message(  # noqa: PLR0911, PLR0912, PLR0915
    request: Request,  # noqa: ARG001 — kept for FastAPI DI consistency with other endpoints
    templates: TemplatesDep,
    user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    message: Annotated[str, Form()],
    level: Annotated[str, Form()] = "A1",
    language: Annotated[str, Form()] = "es",
    lesson_id: Annotated[str | None, Form()] = None,
    lesson_session: Annotated[str | None, Form()] = None,
    thread_id: Annotated[str | None, Form()] = None,
    session_id: Annotated[str | None, Cookie()] = None,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
    conversation_version: Annotated[str | None, Cookie()] = None,
) -> EventSourceResponse:
    """Stream a chat response as server-sent events.

    Phase 15: Real-time token streaming for the chat interface.
    Phase 23: Unified endpoint — when ``lesson_id`` is present, routes to the
    lesson chat graph instead of the freeform graph.

    Streams the AI response token-by-token as SSE events, then sends
    feedback sections (grammar, pronunciation, scaffolding) as rendered HTML.
    Uses the same LangGraph pipeline as POST /chat but with astream().

    SSE event flow (freeform):
        1. token events (AI response text, one per LLM token)
        2. response_complete (full accumulated response)
        3. scaffolding (rendered HTML, A0-A1 only)
        4. grammar (rendered HTML)
        5. pronunciation (rendered HTML)
        6. done (stream complete)

    Additional SSE events (lesson mode):
        - lesson_progress: progress bar / phase UI payload
        - exercise_result: exercise evaluation feedback
        - lesson_complete: lesson finished with score

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        user: Optional authenticated user (None for anonymous/guest).
        lesson_service: Lesson service for loading lesson data.
        message: User's message from form data.
        level: CEFR level (A0, A1, A2, B1). Defaults to A1.
        language: Target language (es, de, fr). Defaults to es.
        lesson_id: Optional lesson ID — when present, routes to lesson graph.
        session_id: Session cookie for anonymous users.
        sb_access_token: Supabase access token cookie.
        conversation_version: Conversation version cookie for new conversations.

    Returns:
        EventSourceResponse: SSE stream of chat events.
    """
    # --- Input validation (same as send_message) ---
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

    # --- Lesson mode: load lesson and derive level/language from metadata ---
    lesson = None
    if lesson_id:
        lesson = lesson_service.get_lesson(lesson_id)
        if not lesson:
            return EventSourceResponse(
                content=_stream_error(f"Lesson not found: {lesson_id}"),
                media_type="text/event-stream",
            )
        # Authoritative level/language from lesson metadata (not Form input)
        level = str(lesson.metadata.level)
        language = lesson.metadata.language

    # --- Validate level/language (freeform uses Form values, lesson uses metadata) ---
    if level not in VALID_LEVELS:
        return EventSourceResponse(
            content=_stream_error(
                f"Invalid level '{level}'. Must be one of: {', '.join(sorted(VALID_LEVELS))}."
            ),
            media_type="text/event-stream",
        )

    if language not in VALID_LANGUAGES:
        return EventSourceResponse(
            content=_stream_error(
                f"Invalid language '{language}'. Must be one of: {', '.join(sorted(VALID_LANGUAGES))}."
            ),
            media_type="text/event-stream",
        )

    # Save form param before it gets shadowed by the resolved thread_id
    thread_id_param = thread_id

    # Create user-scoped Supabase client for RLS-safe DB access in agent nodes.
    # Guard on `user` to avoid creating a client with a stale token when auth
    # failed gracefully (user=None but expired cookie still present).
    user_client = get_supabase_for_user(sb_access_token) if user and sb_access_token else None

    # --- Resolve identity ---
    auto_created_thread_id: str | None = None
    if lesson_id:
        effective_user_id = user.id if user else None
        thread_id, effective_user_id, new_session_id = _resolve_lesson_thread_id(
            effective_user_id, session_id, lesson_id, lesson_session
        )
    elif user and user_client:
        # Authenticated user — use explicit thread or auto-create
        effective_user_id = user.id
        new_session_id = None
        if thread_id_param:
            # Verify the thread belongs to this user before using it (C1)
            thread_svc = ThreadService(user_id=user.id, client=user_client)
            if not thread_svc.get_thread(thread_id_param):
                return EventSourceResponse(
                    content=_stream_error("Thread not found."),
                    media_type="text/event-stream",
                )
            thread_id = thread_id_param
        else:
            thread_svc = ThreadService(user_id=user.id, client=user_client)
            new_thread = thread_svc.create_thread(language=language, level=level)
            thread_id = new_thread.thread_id
            thread_id_param = thread_id  # so touch is called after stream
            auto_created_thread_id = thread_id
    else:
        # Guest fallback — use existing cookie-based identity
        thread_id, effective_user_id, new_session_id = _resolve_chat_identity(  # type: ignore[assignment]
            user, session_id, conversation_version
        )

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:  # noqa: PLR0912, PLR0915
        """Wrap streaming with checkpointer lifecycle and post-stream actions."""
        result = StreamResult()

        async with get_checkpointer() as checkpointer:
            # Notify client of auto-created thread so it can update URL and form
            if auto_created_thread_id:
                yield {
                    "event": "thread_created",
                    "data": json.dumps(
                        {"thread_id": auto_created_thread_id, "language": language, "level": level}
                    ),
                }

            graph_config: dict[str, Any] = {
                "configurable": {
                    "thread_id": thread_id,
                    "supabase_client": user_client,  # Runtime dep, not serialized
                }
            }

            if lesson_id and lesson:
                # --- Lesson mode ---
                graph = build_lesson_chat_graph(checkpointer=checkpointer)

                # Check for existing checkpoint — only send full init on first message
                existing = await graph.aget_state(
                    RunnableConfig(configurable={"thread_id": thread_id})
                )
                has_checkpoint = existing and existing.values.get("lesson_phase")

                if has_checkpoint:
                    inputs: dict[str, Any] = {
                        "messages": [HumanMessage(content=message)],
                        "user_id": effective_user_id,
                    }
                else:
                    inputs = {
                        "messages": [HumanMessage(content=message)],
                        "level": level,
                        "language": language,
                        "user_id": effective_user_id,
                        # Lesson-specific state — only on first invocation
                        "lesson_id": lesson_id,
                        "lesson_data": lesson.model_dump(),
                        "lesson_phase": "intro",
                        "step_index": 0,
                        "exercise_index": 0,
                        "exercise_results": [],
                        "lesson_score": 0,
                    }

                async for event in stream_chat_events(
                    graph=graph,  # type: ignore[arg-type]  # LangGraph astream signature is complex
                    inputs=inputs,
                    config=graph_config,
                    templates=templates,
                    level=level,
                    result=result,
                ):
                    yield event

                # Post-stream: emit lesson-specific SSE events from final state
                state = await graph.aget_state(
                    RunnableConfig(configurable={"thread_id": thread_id})
                )
                state_values = state.values if state else {}

                if state_values.get("lesson_completed"):
                    lesson_ui = state_values.get("lesson_ui", {})
                    score = lesson_ui.get("score", state_values.get("lesson_score", 0))
                    vocab_count = lesson_ui.get("vocab_count", 0)

                    yield {
                        "event": "lesson_complete",
                        "data": json.dumps(
                            {
                                "score": score,
                                "vocab_count": vocab_count,
                                "lesson_id": lesson_id,
                            }
                        ),
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

            else:
                # --- Freeform mode (existing behaviour) ---
                graph = build_graph(checkpointer=checkpointer)

                inputs = {
                    "messages": [HumanMessage(content=message)],
                    "level": level,
                    "language": language,
                    "user_id": effective_user_id,
                }

                async for event in stream_chat_events(
                    graph=graph,  # type: ignore[arg-type]  # LangGraph astream signature is complex
                    inputs=inputs,
                    config=graph_config,
                    templates=templates,
                    level=level,
                    result=result,
                ):
                    yield event

        # Post-stream: capture vocabulary for authenticated users (freeform only)
        if not lesson_id and result.new_vocabulary and effective_user_id and user and user_client:
            try:
                progress_service = ProgressService(effective_user_id, client=user_client)
                progress_service.record_chat_activity(
                    language=language,
                    level=level,
                    new_vocab=result.new_vocabulary,
                )
            except APIError:
                logger.exception("Failed to capture chat activity for user %s", effective_user_id)

        # Update thread timestamp
        if thread_id_param and effective_user_id and user_client:
            try:
                thread_service = ThreadService(user_id=effective_user_id, client=user_client)
                thread_service.touch(thread_id_param)
            except Exception:
                logger.exception("Failed to touch thread %s", thread_id_param)

        # Auto-title new threads after first exchange
        if (
            not lesson_id
            and thread_id_param
            and effective_user_id
            and user_client
            and result.full_response
        ):
            try:
                thread_service = ThreadService(user_id=effective_user_id, client=user_client)
                thread = thread_service.get_thread(thread_id_param)
                if thread and thread.title == "New conversation":
                    title = await generate_thread_title(message, result.full_response)
                    thread_service.update_title(thread_id_param, title)
                    # Emit SSE event so sidebar updates
                    yield {
                        "event": "thread_title",
                        "data": json.dumps({"thread_id": thread_id_param, "title": title}),
                    }
            except Exception:
                logger.exception("Failed to auto-title thread %s", thread_id_param)

    headers: dict[str, str] = {"Cache-Control": "no-cache"}
    response = EventSourceResponse(
        content=event_generator(),
        headers=headers,
        send_timeout=60,
    )

    # Set session cookie for first-time anonymous users.
    # Sign the value for server-side expiry enforcement (Finding H5).
    if new_session_id:
        set_secure_cookie(
            response,
            key="session_id",
            value=sign_session_id(new_session_id),
            max_age=60 * 60 * 24 * 7,  # 7 days
        )

    return response
