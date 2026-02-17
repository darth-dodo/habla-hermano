"""Tests for rate limiting on auth and chat endpoints."""

import asyncio
import inspect

import pytest

from src.api.rate_limit import (
    AUTH_RATE_LIMIT_CALLS,
    AUTH_RATE_LIMIT_PERIOD,
    CHAT_RATE_LIMIT_CALLS,
    CHAT_RATE_LIMIT_PERIOD,
    GENERAL_RATE_LIMIT_CALLS,
    GENERAL_RATE_LIMIT_PERIOD,
    rate_limited,
)


class TestRateLimitConstants:
    """Tests for rate limit configuration values."""

    def test_auth_rate_limit_calls(self) -> None:
        assert AUTH_RATE_LIMIT_CALLS == 5

    def test_auth_rate_limit_period(self) -> None:
        assert AUTH_RATE_LIMIT_PERIOD == 60

    def test_chat_rate_limit_calls(self) -> None:
        assert CHAT_RATE_LIMIT_CALLS == 20

    def test_chat_rate_limit_period(self) -> None:
        assert CHAT_RATE_LIMIT_PERIOD == 60

    def test_general_rate_limit_calls(self) -> None:
        assert GENERAL_RATE_LIMIT_CALLS == 60

    def test_general_rate_limit_period(self) -> None:
        assert GENERAL_RATE_LIMIT_PERIOD == 60

    def test_chat_has_higher_limit_than_auth(self) -> None:
        assert CHAT_RATE_LIMIT_CALLS > AUTH_RATE_LIMIT_CALLS


class TestRateLimitedDecorator:
    """Tests for the rate_limited decorator factory."""

    def test_decorator_preserves_function_name(self) -> None:
        @rate_limited(calls=5, period=60)
        async def my_endpoint() -> str:
            return "ok"

        assert my_endpoint.__name__ == "my_endpoint"

    def test_decorator_preserves_function_signature(self) -> None:
        @rate_limited(calls=5, period=60)
        async def my_endpoint(request: str, message: str = "hello") -> str:
            return f"{request}: {message}"

        sig = inspect.signature(my_endpoint)
        params = list(sig.parameters.keys())
        assert params == ["request", "message"]

    def test_decorator_preserves_docstring(self) -> None:
        @rate_limited(calls=5, period=60)
        async def my_endpoint() -> str:
            """My docstring."""
            return "ok"

        assert my_endpoint.__doc__ == "My docstring."

    def test_decorated_function_is_awaitable(self) -> None:
        @rate_limited(calls=5, period=60)
        async def my_endpoint() -> str:
            return "ok"

        assert asyncio.iscoroutinefunction(my_endpoint)

    @pytest.mark.asyncio
    async def test_rate_limit_allows_within_limit(self) -> None:
        @rate_limited(calls=3, period=60)
        async def my_endpoint() -> str:
            return "ok"

        # Should succeed within limit
        for _ in range(3):
            result = await my_endpoint()
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_rate_limit_raises_429_when_exceeded(self) -> None:
        from fastapi import HTTPException

        @rate_limited(calls=2, period=60)
        async def my_endpoint() -> str:
            return "ok"

        # Exhaust the limit
        await my_endpoint()
        await my_endpoint()

        # Next call should raise 429
        with pytest.raises(HTTPException) as exc_info:
            await my_endpoint()
        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in str(exc_info.value.detail)
