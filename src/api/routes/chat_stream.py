"""SSE streaming chat endpoint.

Extracted from chat.py to reduce module complexity.
Handles POST /chat/stream for real-time token delivery via Server-Sent Events.

Phase 15: Real-time token streaming for the chat interface.
Phase 23: Unified endpoint — when ``lesson_id`` is present, routes to the
lesson chat graph instead of the freeform graph.
"""

import json
import logging
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Form, Request
from langchain_core.runnables import RunnableConfig
from postgrest.exceptions import APIError
from sse_starlette.sse import EventSourceResponse

from src.agent.checkpointer import get_checkpointer
from src.agent.graph import build_graph
from src.agent.lesson_chat_graph import build_lesson_chat_graph
from src.api.auth import AuthenticatedUser, OptionalUserDep
from src.api.dependencies import LessonServiceDep, TemplatesDep
from src.api.rate_limit import CHAT_RATE_LIMIT_CALLS, CHAT_RATE_LIMIT_PERIOD, rate_limited
from src.api.routes.chat import (
    ChatCookies,
    ChatCookiesDep,
    ChatIdentity,
    _freeform_inputs,
    _graph_config,
    _level_language_error,
    _message_error,
    _persist_chat_turn,
    _resolve_freeform_identity,
    _resolve_lesson_thread_id,
    _set_session_cookie,
)
from src.api.streaming import StreamResult, stream_chat_events
from src.api.supabase_client import get_supabase_for_user
from src.services.lesson_completion import complete_lesson_and_persist
from src.services.progress import ProgressService
from src.services.thread_titling import generate_thread_title
from src.services.threads import ThreadService

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from supabase import Client as SupabaseClient

    from src.lessons.models import Lesson
    from src.lessons.service import LessonService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

SSEEvent = dict[str, str]


async def _stream_error(error_message: str) -> AsyncGenerator[SSEEvent, None]:
    """Yield a single error event for validation failures.

    Args:
        error_message: Human-readable error message.

    Yields:
        Error SSE event followed by done event.
    """
    yield {"event": "error", "data": json.dumps({"message": error_message})}
    yield {"event": "done", "data": "{}"}


def _error_response(error_message: str) -> EventSourceResponse:
    """Return an SSE response that only carries an error and done event."""
    return EventSourceResponse(content=_stream_error(error_message), media_type="text/event-stream")


@dataclass(frozen=True)
class _StreamTurn:
    """Everything the SSE generator needs for one validated chat turn."""

    message: str
    level: str
    language: str
    lesson_id: str | None
    lesson: "Lesson | None"
    user: AuthenticatedUser | None
    user_client: "SupabaseClient | None"
    session_id: str | None
    identity: ChatIdentity
    templates: "Jinja2Templates"
    lesson_service: "LessonService"


@router.post("/chat/stream")
@rate_limited(calls=CHAT_RATE_LIMIT_CALLS, period=CHAT_RATE_LIMIT_PERIOD)
async def stream_message(
    request: Request,  # noqa: ARG001 — kept for FastAPI DI consistency with other endpoints
    templates: TemplatesDep,
    user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    cookies: ChatCookiesDep,
    message: Annotated[str, Form()],
    level: Annotated[str, Form()] = "A1",
    language: Annotated[str, Form()] = "es",
    lesson_id: Annotated[str | None, Form()] = None,
    lesson_session: Annotated[str | None, Form()] = None,
    thread_id: Annotated[str | None, Form()] = None,
) -> EventSourceResponse:
    """Stream a chat response as server-sent events (Phase 15).

    Uses the same LangGraph pipeline as POST /chat but with astream(). When
    ``lesson_id`` is present the lesson chat graph is used instead (Phase 23).

    SSE event flow (freeform): token*, response_complete, scaffolding (A0-A1),
    grammar, pronunciation, done. Authenticated users may also receive
    thread_created and thread_title. Lesson mode adds lesson_progress,
    exercise_result and lesson_complete.
    """
    message = message.strip()
    error, lesson, level, language = _validate_stream_input(
        message, level, language, lesson_id, lesson_service
    )
    if error:
        return _error_response(error)

    # RLS-safe client for agent nodes; ignore stale tokens when auth failed (user=None)
    token = cookies.sb_access_token
    user_client = get_supabase_for_user(token) if user and token else None

    identity = _resolve_stream_identity(
        user, user_client, cookies, thread_id, lesson_id, lesson_session, language, level
    )
    if identity is None:
        return _error_response("Thread not found.")

    turn = _StreamTurn(
        message=message,
        level=level,
        language=language,
        lesson_id=lesson_id,
        lesson=lesson,
        user=user,
        user_client=user_client,
        session_id=cookies.session_id,
        identity=identity,
        templates=templates,
        lesson_service=lesson_service,
    )
    response = EventSourceResponse(
        content=_event_generator(turn), headers={"Cache-Control": "no-cache"}, send_timeout=60
    )
    _set_session_cookie(response, identity.new_session_id)
    return response


def _validate_stream_input(
    message: str,
    level: str,
    language: str,
    lesson_id: str | None,
    lesson_service: "LessonService",
) -> tuple[str | None, "Lesson | None", str, str]:
    """Validate a stream request and load its lesson, if any.

    In lesson mode the lesson metadata is authoritative for level and language
    (Form input is ignored).

    Returns:
        Tuple of (error message or None, lesson or None, level, language).
    """
    error = _message_error(message)
    lesson = None
    if not error and lesson_id:
        lesson = lesson_service.get_lesson(lesson_id)
        if lesson:
            level, language = str(lesson.metadata.level), lesson.metadata.language
        else:
            error = f"Lesson not found: {lesson_id}"
    return error or _level_language_error(level, language), lesson, level, language


def _resolve_stream_identity(
    user: AuthenticatedUser | None,
    user_client: "SupabaseClient | None",
    cookies: ChatCookies,
    thread_id: str | None,
    lesson_id: str | None,
    lesson_session: str | None,
    language: str,
    level: str,
) -> ChatIdentity | None:
    """Resolve the thread for a lesson turn or delegate to the freeform resolver.

    Returns None when an authenticated user requests a thread they do not own.
    """
    if lesson_id:
        lesson_thread_id, user_id, new_session_id = _resolve_lesson_thread_id(
            user.id if user else None, cookies.session_id, lesson_id, lesson_session
        )
        return ChatIdentity(lesson_thread_id, user_id, new_session_id, thread_id)
    return _resolve_freeform_identity(
        user=user,
        user_client=user_client,
        requested_thread_id=thread_id,
        cookies=cookies,
        language=language,
        level=level,
        thread_service_factory=ThreadService,
    )


async def _event_generator(turn: _StreamTurn) -> AsyncGenerator[SSEEvent, None]:
    """Wrap streaming with checkpointer lifecycle and post-stream actions."""
    result = StreamResult()
    identity = turn.identity

    async with get_checkpointer() as checkpointer:
        # Notify client of auto-created thread so it can update URL and form
        if identity.created_thread_id:
            payload = {
                "thread_id": identity.created_thread_id,
                "language": turn.language,
                "level": turn.level,
            }
            yield {"event": "thread_created", "data": json.dumps(payload)}

        if turn.lesson is not None:
            async for event in _stream_lesson_turn(turn, turn.lesson, checkpointer, result):
                yield event
        else:
            graph = build_graph(checkpointer=checkpointer)
            inputs = _freeform_inputs(turn.message, turn.level, turn.language, identity.user_id)
            async for event in _stream_graph(turn, graph, inputs, result):
                yield event

    # Vocabulary capture is freeform only; thread touch applies to both modes
    _persist_chat_turn(
        identity=identity,
        user=turn.user,
        user_client=turn.user_client,
        language=turn.language,
        level=turn.level,
        new_vocabulary=[] if turn.lesson_id else result.new_vocabulary,
        progress_service_factory=ProgressService,
        thread_service_factory=ThreadService,
    )

    if not turn.lesson_id:
        async for event in _auto_title_thread(turn, result.full_response):
            yield event


def _stream_graph(
    turn: _StreamTurn, graph: Any, inputs: dict[str, Any], result: StreamResult
) -> AsyncIterator[SSEEvent]:
    """Stream token and feedback events for one graph run."""
    return stream_chat_events(
        graph=graph,
        inputs=inputs,
        config=_graph_config(turn.identity.thread_id, turn.user_client),
        templates=turn.templates,
        level=turn.level,
        result=result,
    )


def _thread_config(thread_id: str) -> RunnableConfig:
    """Build the config used to read checkpointed graph state."""
    return RunnableConfig(configurable={"thread_id": thread_id})


async def _stream_lesson_turn(
    turn: _StreamTurn,
    lesson: "Lesson",
    checkpointer: "BaseCheckpointSaver[Any]",
    result: StreamResult,
) -> AsyncGenerator[SSEEvent, None]:
    """Stream a lesson-mode turn, then emit lesson events from the final state."""
    graph = build_lesson_chat_graph(checkpointer=checkpointer)
    thread_id = turn.identity.thread_id

    # Check for existing checkpoint; only send full lesson init on first message
    existing = await graph.aget_state(_thread_config(thread_id))
    has_checkpoint = bool(existing and existing.values.get("lesson_phase"))

    inputs = _lesson_inputs(turn, lesson, has_checkpoint)
    async for event in _stream_graph(turn, graph, inputs, result):
        yield event

    state = await graph.aget_state(_thread_config(thread_id))
    async for event in _lesson_state_events(turn, state.values if state else {}):
        yield event


def _lesson_inputs(turn: _StreamTurn, lesson: "Lesson", has_checkpoint: bool) -> dict[str, Any]:
    """Build lesson graph input; lesson state is only sent on the first turn."""
    inputs = _freeform_inputs(turn.message, turn.level, turn.language, turn.identity.user_id)
    if has_checkpoint:
        return {"messages": inputs["messages"], "user_id": inputs["user_id"]}
    return {
        **inputs,
        "lesson_id": turn.lesson_id,
        "lesson_data": lesson.model_dump(),
        "lesson_phase": "intro",
        "step_index": 0,
        "exercise_index": 0,
        "exercise_results": [],
        "lesson_score": 0,
    }


async def _lesson_state_events(
    turn: _StreamTurn, state_values: dict[str, Any]
) -> AsyncGenerator[SSEEvent, None]:
    """Emit lesson_complete, lesson_progress and exercise_result events."""
    lesson_ui = state_values.get("lesson_ui", {})

    if state_values.get("lesson_completed"):
        score = lesson_ui.get("score", state_values.get("lesson_score", 0))
        payload = {
            "score": score,
            "vocab_count": lesson_ui.get("vocab_count", 0),
            "lesson_id": turn.lesson_id,
        }
        yield {"event": "lesson_complete", "data": json.dumps(payload)}
        _persist_lesson_completion(turn, score)

    # Emit lesson_progress on every turn
    if lesson_ui:
        yield {"event": "lesson_progress", "data": json.dumps(lesson_ui)}

    exercise_result = lesson_ui.get("exercise_result")
    if exercise_result:
        yield {"event": "exercise_result", "data": json.dumps(exercise_result)}


def _persist_lesson_completion(turn: _StreamTurn, score: Any) -> None:
    """Persist lesson completion for authenticated users; log DB failures."""
    if not (turn.identity.user_id and turn.user and turn.lesson_id):
        return
    try:
        vocabulary = turn.lesson_service.get_lesson_vocabulary(turn.lesson_id)
        complete_lesson_and_persist(
            user=turn.user,
            session_id=turn.session_id,
            lesson_id=turn.lesson_id,
            score=score,
            vocabulary=vocabulary,
            language=turn.language,
        )
    except APIError:
        logger.exception("Failed to persist lesson completion for user %s", turn.identity.user_id)


async def _auto_title_thread(
    turn: _StreamTurn, full_response: str
) -> AsyncGenerator[SSEEvent, None]:
    """Auto-title a new thread after its first exchange and notify the sidebar."""
    thread_id = turn.identity.touch_thread_id
    user_id = turn.identity.user_id
    if not (thread_id and user_id and turn.user_client and full_response):
        return
    try:
        thread_service = ThreadService(user_id=user_id, client=turn.user_client)
        thread = thread_service.get_thread(thread_id)
        if thread and thread.title == "New conversation":
            title = await generate_thread_title(turn.message, full_response)
            thread_service.update_title(thread_id, title)
            yield {
                "event": "thread_title",
                "data": json.dumps({"thread_id": thread_id, "title": title}),
            }
    except Exception:
        logger.exception("Failed to auto-title thread %s", thread_id)
