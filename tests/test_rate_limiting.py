"""Tests for rate limiting on auth and chat endpoints."""

import pytest

from src.api.rate_limit import AUTH_RATE_LIMIT, CHAT_RATE_LIMIT, GENERAL_RATE_LIMIT, limiter


class TestRateLimitConstants:
    """Tests for rate limit configuration values."""

    def test_auth_rate_limit(self) -> None:
        assert AUTH_RATE_LIMIT == "5/minute"

    def test_chat_rate_limit(self) -> None:
        assert CHAT_RATE_LIMIT == "20/minute"

    def test_general_rate_limit(self) -> None:
        assert GENERAL_RATE_LIMIT == "60/minute"

    def test_limiter_uses_remote_address(self) -> None:
        from slowapi.util import get_remote_address

        assert limiter._key_func is get_remote_address


class TestRateLimitMiddleware:
    """Tests for rate limiting middleware integration."""

    @pytest.fixture
    def client(self):
        limiter.reset()
        from fastapi.testclient import TestClient

        from src.api.main import app

        return TestClient(app)

    def test_app_has_limiter_state(self, client) -> None:
        assert hasattr(client.app, "state")
        assert hasattr(client.app.state, "limiter")
        assert client.app.state.limiter is limiter


class TestChatRateLimiting:
    """Tests for chat rate limit configuration."""

    def test_chat_has_higher_limit_than_auth(self) -> None:
        chat_limit = int(CHAT_RATE_LIMIT.split("/")[0])
        auth_limit = int(AUTH_RATE_LIMIT.split("/")[0])
        assert chat_limit > auth_limit
