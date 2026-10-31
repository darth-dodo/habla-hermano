"""Chat router for handling conversation interactions.

Phase 13: Simplified guest model - guests get chat only, no persistence.
Phase 12: Added review mode support for spaced repetition.
Phase 7: Added vocabulary and session data capture for authenticated users.
Phase 5: Added user authentication with Supabase.
Phase 4: Added conversation persistence with LangGraph checkpointing.

Provides endpoints for the main chat interface and non-streaming message handling.
The SSE streaming endpoint lives in chat_stream.py.
Uses HTMX for partial HTML responses.

Authentication:
- GET / supports both authenticated and guest users (OptionalUserDep)
- POST /chat supports both authenticated and guest users (OptionalUserDep)
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

import logging
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any, cast

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from langchain_core.messages import HumanMessage
from markupsafe import escape
from postgrest.exceptions import APIError

from src.agent.checkpointer import get_checkpointer, get_user_thread_id
from src.agent.graph import build_graph
from src.api.auth import AuthenticatedUser, OptionalUserDep
from src.api.cookies import (
    delete_secure_cookie,
    set_secure_cookie,
    sign_session_id,
    unsign_active_thread,
)
from src.api.dependencies import AccessTokenDep, LessonServiceDep, SettingsDep, TemplatesDep
from src.api.rate_limit import CHAT_RATE_LIMIT_CALLS, CHAT_RATE_LIMIT_PERIOD, rate_limited
from src.api.supabase_client import get_supabase_for_user
from src.api.validation import MAX_MESSAGE_LENGTH, VALID_LANGUAGES, VALID_LEVELS
from src.services.progress import ProgressService
from src.services.review import ReviewService
from src.services.thread_messages import get_thread_messages
from src.services.threads import ThreadService

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig
    from supabase import Client as SupabaseClient

    from src.api.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


# --- Cookie expiry ---
_CONVERSATION_VERSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
_SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

# --- Thread ID validation (Finding M1) ---
# Accepts: user:<uuid>:<any up to 100 chars>  or  lesson:<uuid>:<any up to 100 chars>
_THREAD_ID_RE = re.compile(r"^(user|lesson):[0-9a-f-]{36}:.{1,100}$")


def _is_valid_thread_id(value: str) -> bool:
    """Validate that a thread_id cookie matches the expected format.

    Rejects obviously invalid values (10KB strings, SQL injection attempts,
    unknown prefixes) before they reach the database layer.

    Args:
        value: Raw cookie value to validate.

    Returns:
        True if the value looks like a legitimate thread_id, False otherwise.
    """
    return bool(_THREAD_ID_RE.match(value))


def _make_error_html(error_message: str) -> HTMLResponse:
    """Return an HTMX-compatible HTML error fragment."""
    html = f'<div class="text-red-500 text-sm p-2">{escape(error_message)}</div>'
    return HTMLResponse(content=html, status_code=422)


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


# =============================================================================
# Shared chat turn helpers (used by POST /chat and POST /chat/stream)
# =============================================================================


@dataclass(frozen=True)
class ChatCookies:
    """Cookies read by the chat message endpoints."""

    session_id: str | None = None
    sb_access_token: str | None = None
    conversation_version: str | None = None


def get_chat_cookies(
    session_id: Annotated[str | None, Cookie()] = None,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
    conversation_version: Annotated[str | None, Cookie()] = None,
) -> ChatCookies:
    """FastAPI dependency that groups the chat endpoint cookies."""
    return ChatCookies(
        session_id=session_id,
        sb_access_token=sb_access_token,
        conversation_version=conversation_version,
    )


ChatCookiesDep = Annotated[ChatCookies, Depends(get_chat_cookies)]


@dataclass(frozen=True)
class ChatIdentity:
    """Resolved identity for a single chat turn.

    Attributes:
        thread_id: LangGraph checkpoint thread ID.
        user_id: Effective user ID for progress tracking (None for guests).
        new_session_id: Fresh guest session ID that must be set as a cookie.
        touch_thread_id: Thread to touch (and title) after the turn, if any.
        created_thread_id: Thread auto-created for this turn, if any.
    """

    thread_id: str
    user_id: str | None
    new_session_id: str | None = None
    touch_thread_id: str | None = None
    created_thread_id: str | None = None


def _message_error(message: str, too_long_hint: str = "") -> str | None:
    """Return a validation error for a (stripped) chat message, or None if valid."""
    if not message:
        return "Message cannot be empty."
    if len(message) > MAX_MESSAGE_LENGTH:
        return f"Message is too long (max {MAX_MESSAGE_LENGTH} characters).{too_long_hint}"
    return None


def _level_language_error(level: str, language: str) -> str | None:
    """Return a validation error for the CEFR level or language, or None if valid."""
    if level not in VALID_LEVELS:
        return f"Invalid level '{level}'. Must be one of: {', '.join(sorted(VALID_LEVELS))}."
    if language not in VALID_LANGUAGES:
        return (
            f"Invalid language '{language}'. Must be one of: {', '.join(sorted(VALID_LANGUAGES))}."
        )
    return None


def _resolve_freeform_identity(
    *,
    user: AuthenticatedUser | None,
    user_client: "SupabaseClient | None",
    requested_thread_id: str | None,
    cookies: ChatCookies,
    language: str,
    level: str,
    thread_service_factory: Callable[..., ThreadService] | None = None,
) -> ChatIdentity | None:
    """Resolve the thread and user for a freeform chat turn.

    Authenticated users (with a Supabase client) use their explicit thread,
    which must belong to them (C1), or get a new thread auto-created. Everyone
    else falls back to the cookie-based identity.

    ``thread_service_factory`` defaults to this module's ``ThreadService``
    (looked up at call time); other route modules pass their own reference.

    Returns:
        The resolved identity, or None when the requested thread is not owned
        by the user.
    """
    if not (user and user_client):
        thread_id, user_id, new_session_id = _resolve_chat_identity(
            user, cookies.session_id, cookies.conversation_version
        )
        return ChatIdentity(thread_id, user_id, new_session_id, requested_thread_id)

    thread_svc = (thread_service_factory or ThreadService)(user_id=user.id, client=user_client)
    if requested_thread_id:
        if not thread_svc.get_thread(requested_thread_id):
            return None
        return ChatIdentity(requested_thread_id, user.id, touch_thread_id=requested_thread_id)

    new_thread_id = thread_svc.create_thread(language=language, level=level).thread_id
    return ChatIdentity(
        new_thread_id, user.id, touch_thread_id=new_thread_id, created_thread_id=new_thread_id
    )


def _freeform_inputs(
    message: str, level: str, language: str, user_id: str | None
) -> dict[str, Any]:
    """Build the freeform graph input for one user message."""
    return {
        "messages": [HumanMessage(content=message)],
        "level": level,
        "language": language,
        "user_id": user_id,  # Phase 12: For review word weaving
    }


def _graph_config(thread_id: str, user_client: "SupabaseClient | None") -> dict[str, Any]:
    """Build the LangGraph run config for a chat turn."""
    return {
        "configurable": {
            "thread_id": thread_id,
            "supabase_client": user_client,  # Runtime dep, not serialized
        }
    }


def _persist_chat_turn(
    *,
    identity: ChatIdentity,
    user: AuthenticatedUser | None,
    user_client: "SupabaseClient | None",
    language: str,
    level: str,
    new_vocabulary: list[dict[str, str]],
    progress_service_factory: Callable[..., ProgressService] | None = None,
    thread_service_factory: Callable[..., ThreadService] | None = None,
) -> None:
    """Record vocabulary and touch the thread after a chat turn.

    Only authenticated users with a Supabase client get progress tracking.
    Failures are logged and never surface to the user. Service factories
    default to this module's classes (looked up at call time).
    """
    user_id = identity.user_id
    if new_vocabulary and user_id and user and user_client:
        try:
            progress_cls = progress_service_factory or ProgressService
            progress_service = progress_cls(user_id, client=user_client)
            progress_service.record_chat_activity(
                language=language,
                level=level,
                new_vocab=new_vocabulary,
            )
        except APIError:
            logger.exception("Failed to capture chat activity for user %s", user_id)

    if identity.touch_thread_id and user_id and user_client:
        try:
            thread_cls = thread_service_factory or ThreadService
            thread_service = thread_cls(user_id=user_id, client=user_client)
            thread_service.touch(identity.touch_thread_id)
        except Exception:
            logger.exception("Failed to touch thread %s", identity.touch_thread_id)


def _set_session_cookie(response: Response, new_session_id: str | None) -> None:
    """Set the signed guest session cookie for first-time anonymous users.

    The value is signed for server-side expiry enforcement (Finding H5).
    """
    if new_session_id:
        set_secure_cookie(
            response,
            key="session_id",
            value=sign_session_id(new_session_id),
            max_age=_SESSION_COOKIE_MAX_AGE,
        )


@router.get("/", response_class=HTMLResponse, response_model=None)
async def chat_page(  # noqa: PLR0912, PLR0915
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
    user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    sb_token: AccessTokenDep,
    mode: str | None = None,
    warmup_dismissed: Annotated[str | None, Cookie()] = None,
    session_id: Annotated[str | None, Cookie()] = None,
    active_thread: Annotated[str | None, Cookie()] = None,
    language: str = "es",
    lesson: Annotated[str | None, Query()] = None,
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
    if user and not lesson and sb_token:
        user_client = get_supabase_for_user(sb_token)

        # Unsign the active_thread cookie (signed since PII audit fix)
        thread_id = unsign_active_thread(active_thread)

        # Validate active_thread cookie format before use (Finding M1)
        if thread_id and not _is_valid_thread_id(thread_id):
            logger.warning(
                "Ignoring active_thread cookie with invalid format: %r",
                thread_id[:64],
            )
            thread_id = None

        # Load active thread from cookie
        if thread_id:
            try:
                thread_service = ThreadService(user_id=user.id, client=user_client)
                thread_data = thread_service.get_thread(thread_id)
                if thread_data:
                    context["active_thread_id"] = thread_id
                    messages = await get_thread_messages(thread_id)
                    context["messages"] = messages
                    context["current_language"] = thread_data.language
                    context["current_level"] = thread_data.level
            except Exception:
                logger.exception("Failed to load thread %s for user %s", thread_id, user.id)

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

    # Provide a signed WebSocket auth token for voice.
    # iOS Safari/Chrome (WebKit) may not send httponly cookies with WS upgrade
    # requests, so the JS passes this token as a query parameter instead.
    ws_token: str | None = None
    new_signed_session: str | None = None
    if settings.voice_enabled:
        if user:
            # Authenticated users: sign their user ID as a WS token
            ws_token = sign_session_id(user.id)
        elif session_id:
            # Returning guest: reuse the existing signed session cookie value
            ws_token = session_id
        else:
            # New guest: generate signed session now so both cookie and token match
            new_signed_session = sign_session_id(str(uuid.uuid4()))
            ws_token = new_signed_session
    context["ws_token"] = ws_token or ""

    response = templates.TemplateResponse(
        request=request,
        name="chat.html",
        context=context,
    )

    # Set session cookie on page load for guests so voice WebSocket auth works
    # before they send their first message. Sign the value so the server can
    # enforce expiry independently of the browser's cookie max_age (Finding H5).
    if not user and not session_id:
        set_secure_cookie(
            response,
            key="session_id",
            value=new_signed_session or sign_session_id(str(uuid.uuid4())),
            max_age=60 * 60 * 24 * 7,  # 7 days
        )

    return response


@router.get("/chat/thread-content", response_class=HTMLResponse, response_model=None)
async def thread_content_partial(
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
    user: OptionalUserDep,
    sb_token: AccessTokenDep,
    active_thread: Annotated[str | None, Cookie()] = None,
) -> Response:
    """Return the message area HTML for the active thread (SPA-style thread switching).

    Reads the active_thread cookie set by POST /threads/select and returns only
    the inner content of #chat-messages, avoiding a full page reload when switching
    threads. Thread language/level are passed back in X-Thread-* response headers
    so the client can update Alpine.js state without a round-trip.
    """
    empty = HTMLResponse("", headers={"X-Thread-Language": "es", "X-Thread-Level": "A1"})

    # Unsign the active_thread cookie
    thread_id = unsign_active_thread(active_thread)

    if not user or not thread_id:
        return empty

    # Validate active_thread cookie format before use (Finding M1)
    if not _is_valid_thread_id(thread_id):
        logger.warning(
            "Ignoring active_thread cookie with invalid format in thread_content_partial: %r",
            thread_id[:64],
        )
        return empty

    if not sb_token:
        return empty

    try:
        user_client = get_supabase_for_user(sb_token)
        thread_service = ThreadService(user_id=user.id, client=user_client)
        thread_data = thread_service.get_thread(thread_id)
        if not thread_data:
            return empty

        messages = await get_thread_messages(thread_id)
    except Exception:
        logger.exception("Failed to load thread content for %s", thread_id)
        return empty

    return templates.TemplateResponse(
        request=request,
        name="partials/thread_content.html",
        context={
            "messages": messages,
            "current_language": thread_data.language,
            "current_level": thread_data.level,
            "voice_enabled": settings.voice_enabled,
        },
        headers={
            "X-Thread-Language": thread_data.language,
            "X-Thread-Level": thread_data.level,
        },
    )


@router.post("/chat", response_class=HTMLResponse)
@rate_limited(calls=CHAT_RATE_LIMIT_CALLS, period=CHAT_RATE_LIMIT_PERIOD)
async def send_message(
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
    user: OptionalUserDep,
    cookies: ChatCookiesDep,
    message: Annotated[str, Form()],
    level: Annotated[str, Form()] = "A1",
    language: Annotated[str, Form()] = "es",
    thread_id: Annotated[str | None, Form()] = None,
) -> HTMLResponse:
    """Process a chat message and return the message pair partial HTML (HTMX).

    Authenticated users get an owned thread and progress tracking; guests use a cookie thread.
    """
    message = message.strip()
    error = _message_error(message, " Please shorten your message.")
    error = error or _level_language_error(level, language)
    if error:
        return _make_error_html(error)

    # RLS-safe client for agent nodes; ignore stale tokens when auth failed (user=None)
    token = cookies.sb_access_token
    user_client = get_supabase_for_user(token) if user and token else None

    identity = _resolve_freeform_identity(
        user=user,
        user_client=user_client,
        requested_thread_id=thread_id,
        cookies=cookies,
        language=language,
        level=level,
    )
    if identity is None:
        return _make_error_html("Thread not found.")

    try:
        inputs = _freeform_inputs(message, level, language, identity.user_id)
        result = await _invoke_freeform_graph(inputs, identity.thread_id, user_client)
    except Exception:
        logger.exception("Chat invocation failed")
        return _make_error_html("Sorry, something went wrong. Please try again.")

    context = _message_pair_context(result, message, level, language, settings)
    _persist_chat_turn(
        identity=identity,
        user=user,
        user_client=user_client,
        language=language,
        level=level,
        new_vocabulary=result.get("new_vocabulary", []),
    )

    template_response = templates.TemplateResponse(
        request=request,
        name="partials/message_pair.html",
        context=context,
    )
    _set_session_cookie(template_response, identity.new_session_id)
    return template_response


async def _invoke_freeform_graph(
    inputs: dict[str, Any], thread_id: str, user_client: "SupabaseClient | None"
) -> dict[str, Any]:
    """Run the freeform graph once with checkpointing and return its final state."""
    async with get_checkpointer() as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        config = cast("RunnableConfig", _graph_config(thread_id, user_client))
        result: dict[str, Any] = await graph.ainvoke(inputs, config=config)
        return result


def _message_pair_context(
    result: dict[str, Any], message: str, level: str, language: str, settings: "Settings"
) -> dict[str, Any]:
    """Build the message_pair.html context from the graph result.

    Grammar feedback, vocabulary and pronunciation come from the analyze node;
    scaffolding is only populated for A0-A1 learners.
    """
    return {
        "user_message": message,
        "ai_response": result["messages"][-1].content,
        "grammar_feedback": result.get("grammar_feedback", []),
        "new_vocabulary": result.get("new_vocabulary", []),
        "pronunciation_tips": result.get("pronunciation_tips", []),
        "scaffolding": result.get("scaffolding", {}),
        "level": level,
        "language": language,
        "voice_enabled": settings.voice_enabled,
    }


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
        # For anonymous users, delete the session cookie to start fresh.
        # Use delete_secure_cookie so samesite/secure/path match the original
        # set_secure_cookie call — otherwise browsers silently ignore the
        # deletion in production (Finding M2).
        delete_secure_cookie(response, key="session_id")

    response.headers["HX-Redirect"] = "/"
    response.status_code = 200
    return response
