"""Rate limiting configuration for API endpoints.

Uses the ratelimit library with a custom async-compatible decorator factory.
Protects against brute force login attempts and API budget abuse.

Note: The ratelimit library provides function-level (not per-IP) rate limiting.
For production deployments requiring per-IP limits, consider adding a reverse
proxy (e.g., nginx) or upgrading to a Redis-backed solution.
"""

import functools
import logging
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

    @limiter_instance  # type: ignore[misc,untyped-decorator]
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

        return wrapper  # type: ignore[return-value]

    return decorator


def reset_rate_limits() -> None:
    """Reset all active rate limiters to their initial state.

    Intended for use in tests to prevent rate limit state from leaking
    between test cases.
    """
    for limiter_instance in _active_limiters:
        limiter_instance.num_calls = 0
        limiter_instance.last_reset = limiter_instance.clock()
