"""Rate limiting configuration for API endpoints.

Uses the ratelimit library with a custom async-compatible decorator factory.
Protects against brute force login attempts and API budget abuse.

Note: The ratelimit library provides function-level (not per-IP) rate limiting.
For production deployments requiring per-IP limits, consider adding a reverse
proxy (e.g., nginx) or upgrading to a Redis-backed solution.
"""

import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import HTTPException
from ratelimit import RateLimitException
from ratelimit.decorators import RateLimitDecorator

logger = logging.getLogger(__name__)

# Rate limit constants (calls per period in seconds)
AUTH_RATE_LIMIT_CALLS = 5
AUTH_RATE_LIMIT_PERIOD = 60  # 1 minute

CHAT_RATE_LIMIT_CALLS = 20
CHAT_RATE_LIMIT_PERIOD = 60  # 1 minute

GENERAL_RATE_LIMIT_CALLS = 60
GENERAL_RATE_LIMIT_PERIOD = 60  # 1 minute

VOICE_RATE_LIMIT_CALLS = 10
VOICE_RATE_LIMIT_PERIOD = 60  # 1 minute

# Per-connection WebSocket message rate limits
VOICE_WS_MESSAGE_RATE = 60  # audio frames per minute (STT)
VOICE_WS_TTS_MESSAGE_RATE = 30  # text messages per minute (TTS)

F = TypeVar("F", bound=Callable[..., Any])

# Registry of active rate limit decorators for test reset support
_active_limiters: list[RateLimitDecorator] = []


def rate_limited(calls: int, period: int) -> Callable[[F], F]:
    """Create a rate limiting decorator for async FastAPI endpoints.

    Creates a tracking function decorated with @limits that is called before
    the wrapped endpoint executes. If the rate limit is exceeded, a 429
    HTTPException is raised.

    Args:
        calls: Maximum number of calls allowed within the period.
        period: Time window in seconds.

    Returns:
        A decorator that applies rate limiting to the wrapped function.
    """
    limiter_instance = RateLimitDecorator(calls=calls, period=period)
    _active_limiters.append(limiter_instance)

    @limiter_instance  # type: ignore[misc,untyped-decorator]  # ratelimit library lacks type stubs
    def _tracker() -> None:
        """Internal tracking function for rate limit counting."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                _tracker()
            except RateLimitException:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please try again later.",
                ) from None
            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]  # wrapper signature matches F at runtime

    return decorator


def reset_rate_limits() -> None:
    """Reset all active rate limiters to their initial state.

    Intended for use in tests to prevent rate limit state from leaking
    between test cases.
    """
    for limiter_instance in _active_limiters:
        limiter_instance.num_calls = 0
        limiter_instance.last_reset = limiter_instance.clock()


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
