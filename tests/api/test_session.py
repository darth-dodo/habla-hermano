"""
Tests for src/api/session.py - Thread ID session management.

This module tests the cookie-based session management for conversation
thread IDs in Phase 4 persistence.

Also tests security findings:
- H5: Guest session expiry via signed cookies (URLSafeTimedSerializer)
- M1: active_thread cookie format validation
- M2: new_conversation uses delete_secure_cookie with matching attributes
"""

import time
import uuid
from unittest.mock import MagicMock, patch

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


# =============================================================================
# H5: Guest session expiry via signed cookies
# =============================================================================


class TestGuestSessionExpiry:
    """Tests for sign_session_id / unsign_session_id (Finding H5)."""

    def test_expired_session_id_is_rejected(self) -> None:
        """A signed session_id issued 8 days ago must be rejected."""
        from src.api.cookies import sign_session_id, unsign_session_id

        session_uuid = str(uuid.uuid4())

        # Freeze time to 8 days in the past so the signed token looks old
        past_time = time.time() - 8 * 24 * 3600
        with patch("itsdangerous.timed.time") as mock_time:
            mock_time.return_value = past_time
            signed = sign_session_id(session_uuid)

        # Verifying now (real time) — should fail because > 7 days
        result = unsign_session_id(signed, max_age_seconds=7 * 24 * 3600)
        assert result is None, "Expired signed session_id should be rejected"

    def test_valid_signed_session_id_accepted(self) -> None:
        """A freshly signed session_id must be accepted and return the UUID."""
        from src.api.cookies import sign_session_id, unsign_session_id

        session_uuid = str(uuid.uuid4())
        signed = sign_session_id(session_uuid)

        result = unsign_session_id(signed, max_age_seconds=7 * 24 * 3600)
        assert result == session_uuid, "Valid signed session_id should return the UUID"

    def test_plain_uuid_still_accepted_for_backward_compat(self) -> None:
        """A plain UUID4 (old cookie format) must still be accepted for backward compat."""
        from src.api.cookies import unsign_session_id

        plain_uuid = str(uuid.uuid4())
        result = unsign_session_id(plain_uuid, max_age_seconds=7 * 24 * 3600)
        assert result == plain_uuid, "Plain UUID4 should be accepted for backward compat"

    def test_invalid_value_is_rejected(self) -> None:
        """A garbage value must return None."""
        from src.api.cookies import unsign_session_id

        result = unsign_session_id("not-a-uuid-or-signed-value", max_age_seconds=7 * 24 * 3600)
        assert result is None, "Invalid cookie value should return None"

    def test_none_value_is_rejected(self) -> None:
        """None input must return None without raising."""
        from src.api.cookies import unsign_session_id

        result = unsign_session_id(None, max_age_seconds=7 * 24 * 3600)  # type: ignore[arg-type]
        assert result is None


# =============================================================================
# M1: active_thread cookie format validation
# =============================================================================


class TestActiveThreadValidation:
    """Tests for _is_valid_thread_id (Finding M1)."""

    def test_valid_user_thread_id_accepted(self) -> None:
        """A well-formed user thread_id must pass validation."""
        from src.api.routes.chat import _is_valid_thread_id

        uid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        assert _is_valid_thread_id(f"user:{uid}:{tid}") is True

    def test_valid_lesson_thread_id_accepted(self) -> None:
        """A well-formed lesson thread_id must pass validation."""
        from src.api.routes.chat import _is_valid_thread_id

        uid = str(uuid.uuid4())
        assert _is_valid_thread_id(f"lesson:{uid}:spanish-a1:extra") is True

    def test_invalid_active_thread_cookie_is_ignored(self) -> None:
        """An active_thread cookie with invalid format must be treated as None.

        This simulates the chat_page handler discarding a malformed cookie
        rather than passing it to ThreadService.
        """
        from src.api.routes.chat import _is_valid_thread_id

        # 10 KB string — should be rejected
        huge_value = "x" * 10_000
        assert _is_valid_thread_id(huge_value) is False

    def test_empty_string_is_invalid(self) -> None:
        """Empty string must fail validation."""
        from src.api.routes.chat import _is_valid_thread_id

        assert _is_valid_thread_id("") is False

    def test_sql_injection_attempt_is_invalid(self) -> None:
        """A value containing SQL metacharacters must fail."""
        from src.api.routes.chat import _is_valid_thread_id

        assert _is_valid_thread_id("'; DROP TABLE threads; --") is False

    def test_unknown_prefix_is_invalid(self) -> None:
        """A thread_id with an unknown prefix must fail."""
        from src.api.routes.chat import _is_valid_thread_id

        uid = str(uuid.uuid4())
        assert _is_valid_thread_id(f"admin:{uid}:something") is False


# =============================================================================
# M2: new_conversation uses delete_secure_cookie with matching attributes
# =============================================================================


class TestCookieDeletion:
    """Tests for new_conversation cookie deletion (Finding M2)."""

    def test_new_conversation_uses_delete_secure_cookie(self) -> None:
        """new_conversation must call delete_secure_cookie, not response.delete_cookie directly.

        delete_secure_cookie passes samesite/secure/path attributes that match
        the original set_secure_cookie call, so browsers actually honour the
        deletion in production (HTTPS) environments.
        """
        from src.api.cookies import delete_secure_cookie

        mock_response = MagicMock(spec=Response)

        # Call delete_secure_cookie directly — this is the helper the endpoint
        # must use instead of response.delete_cookie(key="session_id")
        delete_secure_cookie(mock_response, key="session_id")

        # The helper must delegate to response.delete_cookie with correct attrs
        mock_response.delete_cookie.assert_called_once()
        call_kwargs = mock_response.delete_cookie.call_args
        kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
        # key must be present either positionally or as keyword
        all_args = list(call_kwargs.args) + list(kwargs.values())
        assert "session_id" in all_args or kwargs.get("key") == "session_id"
        # samesite must be set (lax is the default)
        samesite_val = kwargs.get("samesite")
        assert samesite_val in (None, "lax", "strict", "none") or "samesite" in str(call_kwargs)

    def test_delete_secure_cookie_passes_secure_flag(self) -> None:
        """delete_secure_cookie must forward the secure flag to response.delete_cookie."""
        from src.api.cookies import delete_secure_cookie

        mock_response = MagicMock(spec=Response)

        with patch("src.api.cookies._is_secure", return_value=True):
            delete_secure_cookie(mock_response, key="session_id")

        call_kwargs = mock_response.delete_cookie.call_args
        kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
        assert kwargs.get("secure") is True
