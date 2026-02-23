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

from fastapi import APIRouter, Cookie, Form, Request
from fastapi.responses import HTMLResponse, Response
from langchain_core.messages import HumanMessage
from sse_starlette.sse import EventSourceResponse

from src.agent.checkpointer import get_checkpointer, get_user_thread_id
from src.agent.graph import build_graph
from src.api.auth import AuthenticatedUser, OptionalUserDep
from src.api.dependencies import SettingsDep, TemplatesDep
from src.api.rate_limit import CHAT_RATE_LIMIT_CALLS, CHAT_RATE_LIMIT_PERIOD, rate_limited
from src.api.streaming import StreamResult, stream_chat_events
from src.api.supabase_client import get_supabase_for_user
from src.services.progress import ProgressService
from src.services.review import ReviewService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# --- Input validation constants ---
MAX_MESSAGE_LENGTH = 2000
VALID_LEVELS = {"A0", "A1", "A2", "B1"}
VALID_LANGUAGES = {"es", "de", "fr"}


def _make_error_html(error_message: str) -> HTMLResponse:
    """Return an HTMX-compatible HTML error fragment."""
    html = f'<div class="text-red-500 text-sm p-2">{error_message}</div>'
    return HTMLResponse(content=html, status_code=422)


@router.get("/", response_class=HTMLResponse, response_model=None)
async def chat_page(
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
    user: OptionalUserDep,
    mode: str | None = None,
    warmup_dismissed: Annotated[str | None, Cookie()] = None,
    language: str = "es",
) -> HTMLResponse:
    """Render the main chat interface.

    Supports both authenticated and guest users. Authenticated users
    get persistent conversation history and progress tracking; guests get
    session-based conversations via cookies but no progress tracking.

    Phase 12: Added review mode support. When mode=review, shows the
    review session start UI instead of normal chat.

    Phase 12: Added review mode support. When mode=review, shows the
    review session start UI instead of normal chat.

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        settings: Application settings.
        user: Optional authenticated user (None if guest).
        mode: Optional mode parameter ("review" for review mode).
        warmup_dismissed: Cookie tracking if warmup was dismissed.
        language: Target language for review stats.

    Returns:
        HTMLResponse: Rendered chat page for both authenticated and guest users.
    """
    # Default context
    context = {
        "app_name": settings.APP_NAME,
        "debug": settings.DEBUG,
        "user": user,
        "review_mode": False,
        "show_warmup": False,
        "review_stats": None,
        "current_language": language,
    }

    # Review features only for authenticated users
    if user:
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
        except Exception:
            logger.exception("Failed to get review stats for user %s", user.id)

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context=context,
    )


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


@router.post("/chat", response_class=HTMLResponse)
@rate_limited(calls=CHAT_RATE_LIMIT_CALLS, period=CHAT_RATE_LIMIT_PERIOD)
async def send_message(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    message: Annotated[str, Form()],
    level: Annotated[str, Form()] = "A1",
    language: Annotated[str, Form()] = "es",
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

    # Resolve identity for thread_id and effective user_id
    thread_id, effective_user_id, new_session_id = _resolve_chat_identity(
        user, session_id, conversation_version
    )

    # Create user-scoped Supabase client for RLS-safe DB access in agent nodes
    # Only available for authenticated users with a valid access token
    user_client = get_supabase_for_user(sb_access_token) if sb_access_token else None

    # Invoke LangGraph agent with checkpointing
    async with get_checkpointer() as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=message)],
                "level": level,
                "language": language,
                "user_id": effective_user_id,  # Phase 12: For review word weaving
                "supabase_client": user_client,  # User-scoped client for RLS
            },
            config={"configurable": {"thread_id": thread_id}},
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
        except Exception:
            logger.exception("Failed to capture chat activity for user %s", effective_user_id)

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
        },
    )

    # Set session cookie on the actual response being returned (not the injected one)
    if new_session_id:
        template_response.set_cookie(
            key="session_id",
            value=new_session_id,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 7,  # 7 days
        )

    return template_response


@router.post("/chat/stream")
@rate_limited(calls=CHAT_RATE_LIMIT_CALLS, period=CHAT_RATE_LIMIT_PERIOD)
async def stream_message(
    request: Request,  # noqa: ARG001 — kept for FastAPI DI consistency with other endpoints
    templates: TemplatesDep,
    user: OptionalUserDep,
    message: Annotated[str, Form()],
    level: Annotated[str, Form()] = "A1",
    language: Annotated[str, Form()] = "es",
    session_id: Annotated[str | None, Cookie()] = None,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
    conversation_version: Annotated[str | None, Cookie()] = None,
) -> EventSourceResponse:
    """Stream a chat response as server-sent events.

    Phase 15: Real-time token streaming for the chat interface.

    Streams the AI response token-by-token as SSE events, then sends
    feedback sections (grammar, pronunciation, scaffolding) as rendered HTML.
    Uses the same LangGraph pipeline as POST /chat but with astream().

    SSE event flow:
        1. token events (AI response text, one per LLM token)
        2. response_complete (full accumulated response)
        3. scaffolding (rendered HTML, A0-A1 only)
        4. grammar (rendered HTML)
        5. pronunciation (rendered HTML)
        6. done (stream complete)

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        user: Optional authenticated user (None for anonymous/guest).
        message: User's message from form data.
        level: CEFR level (A0, A1, A2, B1). Defaults to A1.
        language: Target language (es, de, fr). Defaults to es.
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

    # Resolve identity for thread_id and effective user_id
    thread_id, effective_user_id, new_session_id = _resolve_chat_identity(
        user, session_id, conversation_version
    )

    # Create user-scoped Supabase client for RLS-safe DB access in agent nodes
    user_client = get_supabase_for_user(sb_access_token) if sb_access_token else None

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        """Wrap streaming with checkpointer lifecycle and post-stream actions."""
        result = StreamResult()

        async with get_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)

            inputs: dict[str, Any] = {
                "messages": [HumanMessage(content=message)],
                "level": level,
                "language": language,
                "user_id": effective_user_id,
                "supabase_client": user_client,
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

        # Post-stream: capture vocabulary for authenticated users
        if result.new_vocabulary and effective_user_id and user and user_client:
            try:
                progress_service = ProgressService(effective_user_id, client=user_client)
                progress_service.record_chat_activity(
                    language=language,
                    level=level,
                    new_vocab=result.new_vocabulary,
                )
            except Exception:
                logger.exception("Failed to capture chat activity for user %s", effective_user_id)

    headers: dict[str, str] = {"Cache-Control": "no-cache"}
    response = EventSourceResponse(
        content=event_generator(),
        headers=headers,
        send_timeout=60,
    )

    # Set session cookie for first-time anonymous users
    if new_session_id:
        response.set_cookie(
            key="session_id",
            value=new_session_id,
            httponly=True,
            samesite="lax",
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
        response.set_cookie(
            key="conversation_version",
            value=str(uuid.uuid4()),
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 365,  # 1 year
        )
    else:
        # For anonymous users, delete the session cookie to start fresh
        response.delete_cookie(key="session_id")

    response.headers["HX-Redirect"] = "/"
    response.status_code = 200
    return response
