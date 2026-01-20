"""Session management for Habla Hermano.

Phase 4: Thread ID management for conversation persistence.
Handles cookie-based session tracking for LangGraph checkpointing.
"""

import uuid

from fastapi import Request, Response

# Cookie configuration
THREAD_COOKIE_NAME = "habla_thread_id"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days in seconds


def get_thread_id(request: Request) -> str:
    """
    Get thread_id from cookie or generate a new one.

    If the request contains a habla_thread_id cookie, returns its value.
    Otherwise, generates a new UUID for a fresh conversation thread.

    Args:
        request: FastAPI request object containing cookies.

    Returns:
        str: Existing thread_id from cookie or newly generated UUID.

    Example:
        thread_id = get_thread_id(request)
        # Use thread_id in graph config: {"configurable": {"thread_id": thread_id}}
    """
    existing_thread_id = request.cookies.get(THREAD_COOKIE_NAME)
    if existing_thread_id:
        return existing_thread_id
    return str(uuid.uuid4())


def set_thread_id(response: Response, thread_id: str) -> None:
    """
    Set thread_id cookie on the response.

    Configures the cookie with security best practices:
    - httponly: Prevents JavaScript access (XSS protection)
    - samesite=lax: CSRF protection while allowing normal navigation
    - 30-day expiration: Long enough for conversation continuity

    Args:
        response: FastAPI response object to set cookie on.
        thread_id: UUID string to store in the cookie.

    Example:
        thread_id = get_thread_id(request)
        set_thread_id(response, thread_id)
    """
    response.set_cookie(
        key=THREAD_COOKIE_NAME,
        value=thread_id,
        httponly=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
    )


def clear_thread_id(response: Response) -> None:
    """
    Clear thread_id cookie to start a new conversation.

    Deletes the habla_thread_id cookie, causing the next request
    to generate a fresh thread_id for a new conversation.

    Args:
        response: FastAPI response object to delete cookie from.

    Example:
        # In /new endpoint:
        clear_thread_id(response)
        # Next request will get a fresh thread_id
    """
    response.delete_cookie(key=THREAD_COOKIE_NAME)


def is_new_session(request: Request) -> bool:
    """
    Check if this is a new session (no existing thread_id cookie).

    Useful for determining if we need to show welcome messages
    or initialize conversation state.

    Args:
        request: FastAPI request object containing cookies.

    Returns:
        bool: True if no thread_id cookie exists, False otherwise.
    """
    return THREAD_COOKIE_NAME not in request.cookies
