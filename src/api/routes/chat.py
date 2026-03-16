"""Chat router for handling conversation interactions.

Phase 15: Added SSE streaming endpoint for real-time token delivery.
Phase 13: Simplified guest model - guests get chat only, no persistence.
Phase 12: Added review mode support for spaced repetition.
Phase 7: Added vocabulary and session data capture for authenticated users.
Phase 5: Added user authentication with Supabase.
Phase 4: Added conversation persistence with LangGraph checkpointing.

Provides endpoints for the main chat interface and message handling.
Uses HTMX for partial HTML responses, plus SSE streaming for real-time chat.

Authentication:
- GET / supports both authenticated and guest users (OptionalUserDep)
- POST /chat supports both authenticated and guest users (OptionalUserDep)
- POST /chat/stream supports both authenticated and guest users (OptionalUserDep)
- POST /new supports both authenticated and guest users (OptionalUserDep)

Thread IDs are user-scoped for authenticated users (persistent across sessions),
and session-based for anonymous users (cookie-based).

Guest users get:
- Full chat functionality (conversation persists via LangGraph checkpointing)
- Grammar feedback and pronunciation tips (returned in response)
- NO vocabulary tracking (requires account)
- NO progress page data (requires account)
- NO spaced repetition (requires account)
"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from markupsafe import escape
from postgrest.exceptions import APIError
from sse_starlette.sse import EventSourceResponse

from src.agent.checkpointer import get_checkpointer, get_user_thread_id
from src.agent.graph import build_graph
from src.agent.lesson_chat_graph import build_lesson_chat_graph
from src.api.auth import AuthenticatedUser, OptionalUserDep
from src.api.cookies import set_secure_cookie
from src.api.dependencies import LessonServiceDep, SettingsDep, TemplatesDep
from src.api.rate_limit import CHAT_RATE_LIMIT_CALLS, CHAT_RATE_LIMIT_PERIOD, rate_limited
from src.api.streaming import StreamResult, stream_chat_events
from src.api.supabase_client import get_supabase_for_user
from src.api.validation import MAX_MESSAGE_LENGTH, VALID_LANGUAGES, VALID_LEVELS
from src.services.lesson_completion import complete_lesson_and_persist
from src.services.progress import ProgressService
from src.services.review import ReviewService
from src.services.thread_messages import get_thread_messages
from src.services.thread_titling import generate_thread_title
from src.services.threads import ThreadService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


# --- Cookie expiry ---
_CONVERSATION_VERSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def _make_error_html(error_message: str) -> HTMLResponse:
    """Return an HTMX-compatible HTML error fragment."""
    html = f'<div class="text-red-500 text-sm p-2">{escape(error_message)}</div>'
    return HTMLResponse(content=html, status_code=422)


@router.get("/", response_class=HTMLResponse, response_model=None)
async def chat_page(  # noqa: PLR0912
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
    user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    mode: str | None = None,
    warmup_dismissed: Annotated[str | None, Cookie()] = None,
    session_id: Annotated[str | None, Cookie()] = None,
    language: str = "es",
    lesson: Annotated[str | None, Query()] = None,
    thread: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    """Render the main chat interface.

    Supports both authenticated and guest users. Authenticated users
    get persistent conversation history and progress tracking; guests get
    session-based conversations via cookies but no progress tracking.

    Phase 12: Added review mode support. When mode=review, shows the
    review session start UI instead of normal chat.

    When the ``lesson`` query param is provided, renders the chat page in
    lesson mode with lesson-specific context so the frontend auto-starts
    the lesson conversation flow.

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        settings: Application settings.
        user: Optional authenticated user (None if guest).
        lesson_service: Lesson service for loading lesson data.
        mode: Optional mode parameter ("review" for review mode).
        warmup_dismissed: Cookie tracking if warmup was dismissed.
        language: Target language for review stats.
        lesson: Optional lesson ID to render in lesson mode.

    Returns:
        HTMLResponse: Rendered chat page for both authenticated and guest users.
    """
    # Default context
    context: dict[str, Any] = {
        "app_name": settings.APP_NAME,
        "debug": settings.DEBUG,
        "user": user,
        "review_mode": False,
        "show_warmup": False,
        "review_stats": None,
        "current_language": language,
        "voice_enabled": settings.voice_enabled,
        "active_thread_id": None,
        "threads": [],
        "messages": [],
    }

    # Lesson mode: load lesson and add context for the template
    if lesson:
        lesson_data = lesson_service.get_lesson(lesson)
        if not lesson_data:
            raise HTTPException(status_code=404, detail=f"Lesson not found: {lesson}")
        context["lesson_mode"] = True
        context["lesson_id"] = lesson
        context["lesson_title"] = lesson_data.metadata.title
        context["lesson_description"] = lesson_data.metadata.description
        context["lesson_level"] = str(lesson_data.metadata.level)
        context["lesson_language"] = lesson_data.metadata.language
        context["current_language"] = lesson_data.metadata.language
        # Fresh session UUID so each page load starts a clean checkpoint
        context["lesson_session"] = str(uuid.uuid4())

    # Thread loading and sidebar for authenticated users (skip in lesson mode)
    if user and not lesson:
        sb_token = request.cookies.get("sb-access-token")
        if sb_token:
            user_client = get_supabase_for_user(sb_token)

            # Load active thread if requested
            if thread:
                try:
                    thread_service = ThreadService(user_id=user.id, client=user_client)
                    active_thread = thread_service.get_thread(thread)
                    if active_thread:
                        context["active_thread_id"] = thread
                        messages = await get_thread_messages(thread)
                        context["messages"] = messages
                        context["current_language"] = active_thread.language
                        context["current_level"] = active_thread.level
                except Exception:
                    logger.exception("Failed to load thread %s for user %s", thread, user.id)

            # Load thread list for sidebar
            try:
                thread_service = ThreadService(user_id=user.id, client=user_client)
                threads = thread_service.list_threads()
                context["threads"] = [
                    {
                        "id": t.id,
                        "thread_id": t.thread_id,
                        "title": t.title,
                        "language": t.language,
                        "level": t.level,
                        "updated_at": t.updated_at.isoformat(),
                    }
                    for t in threads
                ]
            except Exception:
                logger.exception("Failed to load thread list for user %s", user.id)

    # Review features only for authenticated users (skip in lesson mode)
    if user and not lesson:
        try:
            review_service = ReviewService(user.id)
            review_stats = review_service.get_stats(language=language)
            context["review_stats"] = review_stats

            if mode == "review":
                # Review mode - show review start UI
                context["review_mode"] = True
            elif review_stats.due_count > 0 and not warmup_dismissed:
                # Show warmup prompt if words are due and not dismissed
                context["show_warmup"] = True
        except APIError:
            logger.exception("Failed to get review stats for user %s", user.id)

    response = templates.TemplateResponse(
        request=request,
        name="chat.html",
        context=context,
    )

    # Set session cookie on page load for guests so voice WebSocket auth works
    # before they send their first message
    if not user and not session_id:
        set_secure_cookie(
            response,
            key="session_id",
            value=str(uuid.uuid4()),
            max_age=60 * 60 * 24 * 7,  # 7 days
        )

    return response


def _resolve_chat_identity(
    user: AuthenticatedUser | None,
    session_id: str | None,
    conversation_version: str | None = None,
) -> tuple[str, str | None, str | None]:
    """Resolve thread_id and user_id for chat.

    For authenticated users, returns their user ID for both thread and user tracking.
    If a conversation_version cookie is present, it is incorporated into the thread_id
    so that starting a new conversation effectively abandons old checkpoints.
    For guests, returns session_id for thread (checkpointing) but None for user_id
    (no progress tracking).

    Returns:
        Tuple of (thread_id, user_id_for_progress, new_session_id).
        - thread_id: Used for LangGraph checkpointing (works for both auth and guest)
        - user_id_for_progress: Only set for authenticated users (None for guests)
        - new_session_id: Set only for first-time anonymous users (for cookie)
    """
    if user:
        base_thread_id = get_user_thread_id(user.id)
        if conversation_version:
            thread_id = f"{base_thread_id}:{conversation_version}"
        else:
            thread_id = base_thread_id
        return thread_id, user.id, None
    if session_id:
        # Guest with existing session - thread_id for chat, but NO user_id for progress
        return session_id, None, None
    # First-time anonymous user - generate session for checkpointing only
    new_id = str(uuid.uuid4())
    return new_id, None, new_id


def _resolve_lesson_thread_id(
    user_id: str | None,
    session_id: str | None,
    lesson_id: str,
    lesson_session: str | None = None,
) -> tuple[str, str | None, str | None]:
    """Build a lesson-scoped thread ID.

    Format: lesson:{user_or_session_id}:{lesson_id}:{lesson_session}

    Each page load generates a fresh ``lesson_session`` UUID so that every
    lesson attempt gets a clean checkpoint (no stale conversation history).

    Returns:
        Tuple of (thread_id, effective_user_id, new_session_id).
    """
    suffix = lesson_session or str(uuid.uuid4())
    if user_id:
        return f"lesson:{user_id}:{lesson_id}:{suffix}", user_id, None
    if session_id:
        return f"lesson:{session_id}:{lesson_id}:{suffix}", None, None
    new_id = str(uuid.uuid4())
    return f"lesson:{new_id}:{lesson_id}:{suffix}", None, new_id


@router.post("/chat", response_class=HTMLResponse)
@rate_limited(calls=CHAT_RATE_LIMIT_CALLS, period=CHAT_RATE_LIMIT_PERIOD)
async def send_message(  # noqa: PLR0912
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
    user: OptionalUserDep,
    message: Annotated[str, Form()],
    level: Annotated[str, Form()] = "A1",
    language: Annotated[str, Form()] = "es",
    thread_id: Annotated[str | None, Form()] = None,
    session_id: Annotated[str | None, Cookie()] = None,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
    conversation_version: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """Process a chat message and return the response as partial HTML.

    This endpoint is designed for HTMX requests. It receives a message,
    invokes the LangGraph agent, and returns a partial HTML fragment
    that HTMX swaps into the chat container.

    Supports both authenticated and anonymous users:
    - Authenticated: Thread ID derived from user ID (persistent across sessions)
    - Anonymous: Thread ID from session cookie (session-based)

    Phase 4: Uses checkpointing for conversation persistence.

    Args:
        request: FastAPI request object.
        response: FastAPI response object (for setting cookies).
        templates: Jinja2 templates instance.
        user: Optional authenticated user (None for anonymous/guest).
        message: User's message from form data.
        level: CEFR level (A0, A1, A2, B1). Defaults to A1.
        language: Target language (es, de). Defaults to es (Spanish).
        thread_id: Optional explicit thread ID for authenticated users.
        session_id: Session cookie for anonymous users.

    Returns:
        HTMLResponse: Partial HTML with user message and AI response.
    """
    # --- Input validation ---
    message = message.strip()

    if not message:
        return _make_error_html("Message cannot be empty.")

    if len(message) > MAX_MESSAGE_LENGTH:
        return _make_error_html(
            f"Message is too long (max {MAX_MESSAGE_LENGTH} characters). "
            "Please shorten your message."
        )

    if level not in VALID_LEVELS:
        return _make_error_html(
            f"Invalid level '{level}'. Must be one of: {', '.join(sorted(VALID_LEVELS))}."
        )

    if language not in VALID_LANGUAGES:
        return _make_error_html(
            f"Invalid language '{language}'. Must be one of: {', '.join(sorted(VALID_LANGUAGES))}."
        )

    # Save the form param before it gets shadowed by the resolved thread_id
    thread_id_param = thread_id

    # Create user-scoped Supabase client for RLS-safe DB access in agent nodes
    # Only available for authenticated users with a valid access token
    user_client = get_supabase_for_user(sb_access_token) if sb_access_token else None

    # Resolve identity for thread_id and effective user_id
    if user and user_client:
        effective_user_id = user.id
        new_session_id = None
        if thread_id_param:
            # Authenticated user with explicit thread — use directly
            thread_id = thread_id_param
        else:
            # Authenticated user without thread — auto-create one
            thread_svc = ThreadService(user_id=user.id, client=user_client)
            new_thread = thread_svc.create_thread(language=language, level=level)
            thread_id = new_thread.thread_id
            thread_id_param = thread_id  # so touch is called after stream
    else:
        # Guest fallback — use existing cookie-based identity
        thread_id, effective_user_id, new_session_id = _resolve_chat_identity(
            user, session_id, conversation_version
        )

    # Invoke LangGraph agent with checkpointing
    async with get_checkpointer() as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=message)],
                "level": level,
                "language": language,
                "user_id": effective_user_id,  # Phase 12: For review word weaving
            },
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "supabase_client": user_client,  # Runtime dep, not serialized
                }
            },
        )

    # Extract AI response from graph result
    ai_response = result["messages"][-1].content

    # Extract grammar feedback and vocabulary from analyze node (if present)
    # These fields are populated by the analyze node in Phase 2
    grammar_feedback = result.get("grammar_feedback", [])
    new_vocabulary = result.get("new_vocabulary", [])
    pronunciation_tips = result.get("pronunciation_tips", [])

    # Extract scaffolding from scaffold node (Phase 3)
    # Only populated for A0-A1 learners via conditional routing
    scaffolding = result.get("scaffolding", {})

    # Capture vocabulary and session data for authenticated users only
    # Guests get chat but no progress tracking (simplifies architecture, no service key needed)
    if new_vocabulary and effective_user_id and user and user_client:
        try:
            # Reuse the user-scoped client created above for RLS compliance
            progress_service = ProgressService(effective_user_id, client=user_client)
            progress_service.record_chat_activity(
                language=language,
                level=level,
                new_vocab=new_vocabulary,
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

    # Create template response
    template_response = templates.TemplateResponse(
        request=request,
        name="partials/message_pair.html",
        context={
            "user_message": message,
            "ai_response": ai_response,
            "grammar_feedback": grammar_feedback,
            "new_vocabulary": new_vocabulary,
            "pronunciation_tips": pronunciation_tips,
            "scaffolding": scaffolding,
            "level": level,
            "language": language,
            "voice_enabled": settings.voice_enabled,
        },
    )

    # Set session cookie on the actual response being returned (not the injected one)
    if new_session_id:
        set_secure_cookie(
            template_response,
            key="session_id",
            value=new_session_id,
            max_age=60 * 60 * 24 * 7,  # 7 days
        )

    return template_response


@router.post("/chat/stream")
@rate_limited(calls=CHAT_RATE_LIMIT_CALLS, period=CHAT_RATE_LIMIT_PERIOD)
async def stream_message(  # noqa: PLR0915
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

    # Create user-scoped Supabase client for RLS-safe DB access in agent nodes
    user_client = get_supabase_for_user(sb_access_token) if sb_access_token else None

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
            thread_id = thread_id_param
        else:
            thread_svc = ThreadService(user_id=user.id, client=user_client)
            new_thread = thread_svc.create_thread(language=language, level=level)
            thread_id = new_thread.thread_id
            thread_id_param = thread_id  # so touch is called after stream
            auto_created_thread_id = thread_id
    else:
        # Guest fallback — use existing cookie-based identity
        thread_id, effective_user_id, new_session_id = _resolve_chat_identity(
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
                    "data": json.dumps({"thread_id": auto_created_thread_id, "language": language, "level": level}),
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
                # Each page load uses a fresh lesson_session UUID, so the first
                # message always creates a new thread.  Subsequent messages within
                # the same page session reuse the same thread_id and skip re-init.
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
                    graph=graph,
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
                    graph=graph,
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

    # Set session cookie for first-time anonymous users
    if new_session_id:
        set_secure_cookie(
            response,
            key="session_id",
            value=new_session_id,
            max_age=60 * 60 * 24 * 7,  # 7 days
        )

    return response


async def _stream_error(error_message: str) -> AsyncGenerator[dict[str, str], None]:
    """Yield a single error event for validation failures.

    Args:
        error_message: Human-readable error message.

    Yields:
        Error SSE event followed by done event.
    """
    yield {"event": "error", "data": json.dumps({"message": error_message})}
    yield {"event": "done", "data": "{}"}


@router.post("/new", response_class=HTMLResponse)
async def new_conversation(
    response: Response,
    user: OptionalUserDep,
) -> Response:
    """Start a new conversation by clearing conversation history.

    Supports both authenticated and anonymous users:
    - Authenticated: Sets a new conversation_version cookie so the next message
      uses a fresh thread_id, effectively abandoning old checkpoints.
    - Anonymous: Clears the session cookie, generating a new thread on next message.

    Args:
        response: FastAPI response object.
        user: Optional authenticated user (None for anonymous/guest).

    Returns:
        Response: Empty response with HX-Redirect header to reload page.
    """
    if user:
        # Rotate to a new conversation by setting a version cookie.
        # The thread_id will become "user:{id}:{version}", abandoning old checkpoints.
        set_secure_cookie(
            response,
            key="conversation_version",
            value=str(uuid.uuid4()),
            max_age=60 * 60 * 24 * 30,  # 30 days (A24: reduced from 1 year)
        )
    else:
        # For anonymous users, delete the session cookie to start fresh
        response.delete_cookie(key="session_id")

    response.headers["HX-Redirect"] = "/"
    response.status_code = 200
    return response
