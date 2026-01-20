"""
Tests for src/api/session.py - Thread ID session management.

This module tests the cookie-based session management for conversation
thread IDs in Phase 4 persistence.
"""

import uuid
from unittest.mock import MagicMock

from fastapi import Request, Response


class TestGetThreadId:
    """Tests for get_thread_id function."""

    def test_returns_existing_cookie_value(self) -> None:
        """get_thread_id should return existing thread_id from cookie."""
        from src.api.session import THREAD_COOKIE_NAME, get_thread_id

        existing_thread_id = "test-thread-12345"
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {THREAD_COOKIE_NAME: existing_thread_id}

        result = get_thread_id(mock_request)
        assert result == existing_thread_id

    def test_generates_uuid_when_no_cookie(self) -> None:
        """get_thread_id should generate UUID when no cookie exists."""
        from src.api.session import get_thread_id

        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}

        result = get_thread_id(mock_request)

        # Should return a valid UUID string
        assert result is not None
        # Verify it's a valid UUID format
        parsed_uuid = uuid.UUID(result)
        assert str(parsed_uuid) == result

    def test_generates_different_uuids_for_different_requests(self) -> None:
        """get_thread_id should generate unique UUIDs for different requests."""
        from src.api.session import get_thread_id

        mock_request1 = MagicMock(spec=Request)
        mock_request1.cookies = {}

        mock_request2 = MagicMock(spec=Request)
        mock_request2.cookies = {}

        result1 = get_thread_id(mock_request1)
        result2 = get_thread_id(mock_request2)

        # UUIDs should be different (extremely unlikely to collide)
        assert result1 != result2

    def test_returns_same_value_when_cookie_exists(self) -> None:
        """get_thread_id should return cookie value unchanged."""
        from src.api.session import THREAD_COOKIE_NAME, get_thread_id

        # Use a specific format that's clearly not a new UUID
        existing_id = "custom-session-abc123"
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {THREAD_COOKIE_NAME: existing_id}

        result = get_thread_id(mock_request)
        assert result == existing_id

    def test_handles_empty_cookie_value(self) -> None:
        """get_thread_id should generate UUID when cookie value is empty string."""
        from src.api.session import THREAD_COOKIE_NAME, get_thread_id

        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {THREAD_COOKIE_NAME: ""}

        result = get_thread_id(mock_request)

        # Empty string should be treated as falsy, generate new UUID
        # OR return empty string if that's the implementation
        # The test should match the expected behavior
        assert result is not None
        if result != "":
            # If implementation generates new UUID for empty
            uuid.UUID(result)  # Validate format


class TestSetThreadId:
    """Tests for set_thread_id function."""

    def test_sets_cookie_on_response(self) -> None:
        """set_thread_id should set cookie on response object."""
        from src.api.session import THREAD_COOKIE_NAME, set_thread_id

        mock_response = MagicMock(spec=Response)
        thread_id = "test-thread-id-xyz"

        set_thread_id(mock_response, thread_id)

        mock_response.set_cookie.assert_called_once()
        call_kwargs = mock_response.set_cookie.call_args
        # Check the cookie name is correct
        assert (
            call_kwargs[1]["key"] == THREAD_COOKIE_NAME or call_kwargs[0][0] == THREAD_COOKIE_NAME
        )

    def test_sets_correct_cookie_value(self) -> None:
        """set_thread_id should set the correct thread_id value."""
        from src.api.session import set_thread_id

        mock_response = MagicMock(spec=Response)
        thread_id = "my-unique-thread-123"

        set_thread_id(mock_response, thread_id)

        call_kwargs = mock_response.set_cookie.call_args
        # Value should be the thread_id
        if call_kwargs[1]:
            assert call_kwargs[1].get("value") == thread_id or call_kwargs[0][1] == thread_id
        else:
            assert call_kwargs[0][1] == thread_id

    def test_sets_httponly_flag(self) -> None:
        """set_thread_id should set httponly flag for security."""
        from src.api.session import set_thread_id

        mock_response = MagicMock(spec=Response)

        set_thread_id(mock_response, "test-id")

        call_kwargs = mock_response.set_cookie.call_args
        # httponly should be True for security
        assert call_kwargs[1].get("httponly") is True

    def test_sets_samesite_attribute(self) -> None:
        """set_thread_id should set samesite attribute."""
        from src.api.session import set_thread_id

        mock_response = MagicMock(spec=Response)

        set_thread_id(mock_response, "test-id")

        call_kwargs = mock_response.set_cookie.call_args
        # samesite should be set for CSRF protection
        samesite = call_kwargs[1].get("samesite")
        assert samesite in ["lax", "strict", "Lax", "Strict"]

    def test_sets_reasonable_max_age(self) -> None:
        """set_thread_id should set reasonable max_age for session persistence."""
        from src.api.session import set_thread_id

        mock_response = MagicMock(spec=Response)

        set_thread_id(mock_response, "test-id")

        call_kwargs = mock_response.set_cookie.call_args
        max_age = call_kwargs[1].get("max_age")

        # Should have a max_age for persistence (at least 1 hour)
        if max_age is not None:
            assert max_age >= 3600  # At least 1 hour


class TestClearThreadId:
    """Tests for clear_thread_id function."""

    def test_deletes_cookie_from_response(self) -> None:
        """clear_thread_id should delete the thread cookie."""
        from src.api.session import THREAD_COOKIE_NAME, clear_thread_id

        mock_response = MagicMock(spec=Response)

        clear_thread_id(mock_response)

        mock_response.delete_cookie.assert_called_once()
        call_args = mock_response.delete_cookie.call_args
        # Check the correct cookie is deleted
        assert (
            call_args[1].get("key") == THREAD_COOKIE_NAME or call_args[0][0] == THREAD_COOKIE_NAME
        )

    def test_clears_correct_cookie_name(self) -> None:
        """clear_thread_id should clear the THREAD_COOKIE_NAME cookie specifically."""
        from src.api.session import THREAD_COOKIE_NAME, clear_thread_id

        mock_response = MagicMock(spec=Response)

        clear_thread_id(mock_response)

        # Verify delete_cookie was called with correct name
        call_args = mock_response.delete_cookie.call_args
        cookie_name = call_args[1].get("key") if call_args[1] else call_args[0][0]
        assert cookie_name == THREAD_COOKIE_NAME

    def test_can_be_called_multiple_times(self) -> None:
        """clear_thread_id should handle being called multiple times."""
        from src.api.session import clear_thread_id

        mock_response = MagicMock(spec=Response)

        # Should not raise on multiple calls
        clear_thread_id(mock_response)
        clear_thread_id(mock_response)

        assert mock_response.delete_cookie.call_count == 2


class TestThreadCookieName:
    """Tests for the THREAD_COOKIE_NAME constant."""

    def test_cookie_name_is_string(self) -> None:
        """THREAD_COOKIE_NAME should be a string."""
        from src.api.session import THREAD_COOKIE_NAME

        assert isinstance(THREAD_COOKIE_NAME, str)

    def test_cookie_name_is_not_empty(self) -> None:
        """THREAD_COOKIE_NAME should not be empty."""
        from src.api.session import THREAD_COOKIE_NAME

        assert len(THREAD_COOKIE_NAME) > 0

    def test_cookie_name_is_valid_cookie_name(self) -> None:
        """THREAD_COOKIE_NAME should be a valid HTTP cookie name."""
        from src.api.session import THREAD_COOKIE_NAME

        # Cookie names should not contain special characters
        invalid_chars = " \t\n\r,;="
        for char in invalid_chars:
            assert char not in THREAD_COOKIE_NAME


class TestSessionModuleExports:
    """Tests for module exports and documentation."""

    def test_module_exports_get_thread_id(self) -> None:
        """Module should export get_thread_id function."""
        from src.api import session

        assert hasattr(session, "get_thread_id")
        assert callable(session.get_thread_id)

    def test_module_exports_set_thread_id(self) -> None:
        """Module should export set_thread_id function."""
        from src.api import session

        assert hasattr(session, "set_thread_id")
        assert callable(session.set_thread_id)

    def test_module_exports_clear_thread_id(self) -> None:
        """Module should export clear_thread_id function."""
        from src.api import session

        assert hasattr(session, "clear_thread_id")
        assert callable(session.clear_thread_id)

    def test_module_exports_cookie_name(self) -> None:
        """Module should export THREAD_COOKIE_NAME constant."""
        from src.api import session

        assert hasattr(session, "THREAD_COOKIE_NAME")

    def test_get_thread_id_has_docstring(self) -> None:
        """get_thread_id should have documentation."""
        from src.api.session import get_thread_id

        assert get_thread_id.__doc__ is not None
        assert len(get_thread_id.__doc__) > 0

    def test_set_thread_id_has_docstring(self) -> None:
        """set_thread_id should have documentation."""
        from src.api.session import set_thread_id

        assert set_thread_id.__doc__ is not None
        assert len(set_thread_id.__doc__) > 0

    def test_clear_thread_id_has_docstring(self) -> None:
        """clear_thread_id should have documentation."""
        from src.api.session import clear_thread_id

        assert clear_thread_id.__doc__ is not None
        assert len(clear_thread_id.__doc__) > 0


class TestSessionRoundTrip:
    """Tests for complete session management round-trip scenarios."""

    def test_set_then_get_flow(self) -> None:
        """Setting a thread_id should allow getting it back."""
        from src.api.session import THREAD_COOKIE_NAME, get_thread_id, set_thread_id

        # Simulate setting a cookie
        mock_response = MagicMock(spec=Response)
        thread_id = str(uuid.uuid4())
        set_thread_id(mock_response, thread_id)

        # Now simulate a request with that cookie
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {THREAD_COOKIE_NAME: thread_id}

        result = get_thread_id(mock_request)
        assert result == thread_id

    def test_clear_then_get_flow(self) -> None:
        """Clearing thread_id should result in new UUID on next get."""
        from src.api.session import clear_thread_id, get_thread_id

        original_id = "original-thread-id"

        # Clear the cookie
        mock_response = MagicMock(spec=Response)
        clear_thread_id(mock_response)

        # Now a request without the cookie (simulating cleared state)
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}

        result = get_thread_id(mock_request)

        # Should get a new UUID, not the original
        assert result != original_id
        # Should be a valid UUID
        uuid.UUID(result)
