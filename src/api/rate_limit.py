"""Rate limiting configuration for API endpoints.

REST endpoints are limited per client IP with an in-process sliding window,
so one client cannot lock everyone else out (for example of login). Protects
against brute force login attempts and API budget abuse.
"""

import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# Rate limit constants (calls per period in seconds)
AUTH_RATE_LIMIT_CALLS = 5
AUTH_RATE_LIMIT_PERIOD = 60  # 1 minute

CHAT_RATE_LIMIT_CALLS = 20
CHAT_RATE_LIMIT_PERIOD = 60  # 1 minute

VOICE_RATE_LIMIT_CALLS = 10
VOICE_RATE_LIMIT_PERIOD = 60  # 1 minute

# Per-connection WebSocket message rate limit for TTS.
# STT audio frames are not rate-limited per-message because AudioWorklet
# fires process() at 128-sample intervals (~375/sec at 48kHz). The
# authenticated WebSocket connection itself is the throttle for STT.
VOICE_WS_TTS_MESSAGE_RATE = 30  # text messages per minute (TTS)

F = TypeVar("F", bound=Callable[..., Any])

# Registry of per-client limiters, so tests can reset them.
_active_limiters: list[dict[str, "WebSocketMessageRateLimiter"]] = []

# shortcut: limits are per process and forgotten past this many clients;
# move to Redis if the app ever runs more than one worker or instance.
_MAX_TRACKED_CLIENTS = 10_000


def client_key(request: Request | None) -> str:
    """Identify the caller for rate limiting.

    Render's proxy appends the real client IP as the last X-Forwarded-For
    entry; earlier entries come from the client and can be forged, so they
    are ignored. Without the header (local dev) the socket peer is used.
    """
    if request is None:
        return "-"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.rsplit(",", 1)[-1].strip()
    return request.client.host if request.client else "-"


def rate_limited(calls: int, period: int) -> Callable[[F], F]:
    """Create a per-client rate limiting decorator for async FastAPI endpoints.

    The endpoint should declare a ``request: Request`` parameter; without
    one, every caller shares a single budget.

    Args:
        calls: Maximum number of calls allowed per client within the period.
        period: Time window in seconds.

    Returns:
        A decorator that raises a 429 HTTPException once a client exceeds the limit.
    """
    clients: dict[str, WebSocketMessageRateLimiter] = {}
    _active_limiters.append(clients)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = kwargs.get("request")
            key = client_key(request if isinstance(request, Request) else None)
            if key not in clients and len(clients) >= _MAX_TRACKED_CLIENTS:
                clients.clear()
            limiter = clients.setdefault(key, WebSocketMessageRateLimiter(calls, period))
            if not limiter.check():
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please try again later.",
                )
            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]  # wrapper signature matches F at runtime

    return decorator


def reset_rate_limits() -> None:
    """Reset all REST rate limiters (for tests, so state does not leak)."""
    for clients in _active_limiters:
        clients.clear()


class WebSocketMessageRateLimiter:
    """Per-connection sliding window rate limiter for WebSocket messages.

    Tracks message timestamps within a rolling window and rejects messages
    that would exceed the configured rate. Each WebSocket connection should
    create its own instance.

    Args:
        max_messages: Maximum messages allowed within the window.
        window_seconds: Sliding window duration in seconds.
    """

    def __init__(self, max_messages: int, window_seconds: int) -> None:
        self._max_messages = max_messages
        self._window_seconds = window_seconds
        self._timestamps: list[float] = []

    def check(self) -> bool:
        """Check if a message is allowed under the rate limit.

        Removes expired timestamps and checks if the new message would
        exceed the limit.

        Returns:
            True if the message is allowed, False if rate limited.
        """
        now = time.monotonic()
        cutoff = now - self._window_seconds
        # Prune expired timestamps
        self._timestamps = [t for t in self._timestamps if t > cutoff]
        if len(self._timestamps) >= self._max_messages:
            return False
        self._timestamps.append(now)
        return True
