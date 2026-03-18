"""Tests for privacy & security endpoints (src/api/routes/privacy.py).

Validates the GET /privacy/ page, POST /privacy/delete-history, and
POST /privacy/delete-account endpoints with authentication, CSRF
compliance, Supabase mock interactions, and error handling.
"""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import (
    AuthenticatedUser,
    get_current_user,
    get_current_user_optional,
)
from tests.conftest import CSRF_HEADERS

# =============================================================================
# Helpers
# =============================================================================


def _make_mock_supabase() -> tuple[MagicMock, MagicMock]:
    """Build a mock Supabase client with chained PostgREST methods.

    Returns a (client, table) tuple so tests can inspect table-level calls.
    """
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_execute_result = MagicMock(data=[], count=0)

    for method in (
        "select",
        "insert",
        "update",
        "delete",
        "eq",
        "neq",
        "gt",
        "gte",
        "lt",
        "lte",
        "ilike",
        "like",
        "is_",
        "in_",
        "order",
        "limit",
        "range",
        "single",
    ):
        setattr(mock_table, method, MagicMock(return_value=mock_table))
    mock_table.execute = MagicMock(return_value=mock_execute_result)
    type(mock_table).not_ = PropertyMock(return_value=mock_table)
    mock_client.table = MagicMock(return_value=mock_table)
    return mock_client, mock_table


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_user() -> AuthenticatedUser:
    return AuthenticatedUser(id="test-user-123", email="test@example.com")


@pytest.fixture
def mock_supabase_user_client() -> tuple[MagicMock, MagicMock]:
    """Mock Supabase user client returned by get_supabase_for_user."""
    return _make_mock_supabase()


@pytest.fixture
def mock_supabase_admin_client() -> tuple[MagicMock, MagicMock]:
    """Mock Supabase admin client returned by get_supabase_admin."""
    client, table = _make_mock_supabase()
    # Admin client needs auth.admin.delete_user
    client.auth = MagicMock()
    client.auth.admin = MagicMock()
    client.auth.admin.delete_user = MagicMock()
    return client, table


@pytest.fixture
def authed_app(
    mock_user: AuthenticatedUser,
    mock_supabase_user_client: tuple[MagicMock, MagicMock],
    mock_supabase_admin_client: tuple[MagicMock, MagicMock],
) -> FastAPI:
    """Create a FastAPI app with authenticated user and mocked Supabase."""
    user_client, _ = mock_supabase_user_client
    admin_client, _ = mock_supabase_admin_client

    async def override_user():
        return mock_user

    async def override_user_optional():
        return mock_user

    with (
        patch(
            "src.api.routes.privacy.get_supabase_for_user",
            return_value=user_client,
        ),
        patch(
            "src.api.routes.privacy.get_supabase_admin",
            return_value=admin_client,
        ),
        patch(
            "src.api.routes.privacy.get_settings",
            return_value=MagicMock(SUPABASE_SERVICE_KEY="fake-service-key"),
        ),
    ):
        from src.api.main import create_app

        application = create_app()
        application.dependency_overrides[get_current_user] = override_user
        application.dependency_overrides[get_current_user_optional] = override_user_optional
        yield application
        application.dependency_overrides.pop(get_current_user, None)
        application.dependency_overrides.pop(get_current_user_optional, None)


@pytest.fixture
def authed_client(authed_app: FastAPI) -> TestClient:
    with TestClient(authed_app, headers=CSRF_HEADERS) as c:
        # Set the sb-access-token cookie so the endpoint sees it
        c.cookies.set("sb-access-token", "fake-access-token")
        yield c


@pytest.fixture
def guest_app() -> FastAPI:
    """Create a FastAPI app with no auth override (guest/unauthenticated)."""
    from src.api.main import create_app

    application = create_app()

    async def override_user_optional():
        return None

    application.dependency_overrides[get_current_user_optional] = override_user_optional
    yield application
    application.dependency_overrides.pop(get_current_user_optional, None)


@pytest.fixture
def guest_client(guest_app: FastAPI) -> TestClient:
    with TestClient(guest_app, headers=CSRF_HEADERS) as c:
        yield c


# =============================================================================
# GET /privacy/ Tests
# =============================================================================


class TestGetPrivacyPage:
    """GET /privacy/ endpoint."""

    def test_guest_user_sees_privacy_page(self, guest_client: TestClient) -> None:
        """Guest user (no auth) can view the privacy page."""
        resp = guest_client.get("/privacy/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_authenticated_user_sees_privacy_page(self, authed_client: TestClient) -> None:
        """Authenticated user can view the privacy page."""
        resp = authed_client.get("/privacy/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


# =============================================================================
# POST /privacy/delete-history Tests
# =============================================================================


class TestDeleteHistory:
    """POST /privacy/delete-history endpoint."""

    def test_unauthenticated_redirects_to_login(self, guest_client: TestClient) -> None:
        """Unauthenticated user gets redirected to /auth/login."""
        resp = guest_client.post("/privacy/delete-history", follow_redirects=False)
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["location"]

    def test_deletes_conversation_threads(
        self,
        authed_client: TestClient,
        mock_supabase_user_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Deletes conversation_threads with eq('user_id', user.id)."""
        user_client, mock_table = mock_supabase_user_client
        resp = authed_client.post("/privacy/delete-history")
        assert resp.status_code == 200

        # Verify conversation_threads table was accessed
        user_client.table.assert_any_call("conversation_threads")
        # Verify .delete().eq("user_id", ...) chain was called
        mock_table.delete.assert_called()
        mock_table.eq.assert_any_call("user_id", "test-user-123")

    def test_deletes_all_three_checkpoint_tables(
        self,
        authed_client: TestClient,
        mock_supabase_user_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Deletes from checkpoint_writes, checkpoint_blobs, and checkpoints."""
        user_client, _mock_table = mock_supabase_user_client
        resp = authed_client.post("/privacy/delete-history")
        assert resp.status_code == 200

        table_calls = [call.args[0] for call in user_client.table.call_args_list]
        assert "checkpoint_writes" in table_calls
        assert "checkpoint_blobs" in table_calls
        assert "checkpoints" in table_calls

    def test_checkpoint_delete_uses_like_pattern(
        self,
        authed_client: TestClient,
        mock_supabase_user_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Checkpoint deletions use .like('thread_id', ...) for both user and lesson patterns."""
        _, mock_table = mock_supabase_user_client
        authed_client.post("/privacy/delete-history")

        like_calls = list(mock_table.like.call_args_list)
        # 3 checkpoint tables x 2 patterns (user + lesson) = 6 calls
        assert len(like_calls) == 6
        user_pattern = "user:test-user-123:%"
        lesson_pattern = "lesson:test-user-123:%"
        user_calls = [c for c in like_calls if c.args == ("thread_id", user_pattern)]
        lesson_calls = [c for c in like_calls if c.args == ("thread_id", lesson_pattern)]
        assert len(user_calls) == 3
        assert len(lesson_calls) == 3

    def test_response_has_hx_redirect_header(self, authed_client: TestClient) -> None:
        """Response includes HX-Redirect header pointing to '/'."""
        resp = authed_client.post("/privacy/delete-history")
        assert resp.status_code == 200
        assert resp.headers.get("hx-redirect") == "/"

    def test_active_thread_cookie_is_cleared(self, authed_client: TestClient) -> None:
        """The active_thread cookie is cleared after deletion."""
        resp = authed_client.post("/privacy/delete-history")
        assert resp.status_code == 200
        # Check that a Set-Cookie header clears the active_thread cookie
        set_cookie_headers = resp.headers.get_list("set-cookie")
        active_thread_cleared = any(
            "active_thread" in cookie
            and ('""' in cookie or "max-age=0" in cookie or "expires=" in cookie.lower())
            for cookie in set_cookie_headers
        )
        assert active_thread_cleared, (
            f"Expected active_thread cookie to be cleared. Set-Cookie headers: {set_cookie_headers}"
        )

    def test_handles_supabase_error_gracefully(
        self,
        authed_client: TestClient,
        mock_supabase_user_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """If Supabase raises an error, endpoint still returns redirect."""
        _, mock_table = mock_supabase_user_client
        mock_table.execute.side_effect = Exception("Supabase unavailable")
        resp = authed_client.post("/privacy/delete-history")
        # Should still return 200 with HX-Redirect (errors are logged, not raised)
        assert resp.status_code == 200
        assert resp.headers.get("hx-redirect") == "/"


# =============================================================================
# POST /privacy/delete-history — Lesson Checkpoint Tests
# =============================================================================


class TestDeleteHistoryLessonCheckpoints:
    """Ensure delete-history also removes lesson-prefixed checkpoint data."""

    def test_delete_history_also_deletes_lesson_checkpoints(
        self,
        authed_client: TestClient,
        mock_supabase_user_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Checkpoint deletions also cover the lesson:{user_id}:% pattern."""
        _, mock_table = mock_supabase_user_client
        authed_client.post("/privacy/delete-history")

        lesson_pattern = "lesson:test-user-123:%"
        like_calls = list(mock_table.like.call_args_list)
        lesson_calls = [c for c in like_calls if c.args == ("thread_id", lesson_pattern)]
        # One .like() call per checkpoint table for the lesson pattern
        assert len(lesson_calls) == 3, (
            f"Expected 3 like() calls with lesson pattern, got {len(lesson_calls)}. "
            f"All like calls: {like_calls}"
        )


# =============================================================================
# POST /privacy/delete-account Tests
# =============================================================================


class TestDeleteAccount:
    """POST /privacy/delete-account endpoint."""

    def test_unauthenticated_redirects_to_login(self, guest_client: TestClient) -> None:
        """Unauthenticated user gets redirected to /auth/login."""
        resp = guest_client.post(
            "/privacy/delete-account",
            data={"confirm": "DELETE"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["location"]

    def test_missing_confirm_returns_422(self, authed_client: TestClient) -> None:
        """Missing confirm value returns 422 error."""
        resp = authed_client.post("/privacy/delete-account", data={"confirm": ""})
        assert resp.status_code == 422
        assert "DELETE" in resp.text

    def test_wrong_confirm_returns_422(self, authed_client: TestClient) -> None:
        """Wrong confirm value (not 'DELETE') returns 422."""
        resp = authed_client.post("/privacy/delete-account", data={"confirm": "delete"})
        assert resp.status_code == 422
        assert "DELETE" in resp.text

    def test_successful_delete_calls_admin_delete_user(
        self,
        authed_client: TestClient,
        mock_supabase_admin_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Successful deletion calls admin.delete_user(user.id)."""
        admin_client, _ = mock_supabase_admin_client
        resp = authed_client.post(
            "/privacy/delete-account",
            data={"confirm": "DELETE"},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        assert resp.headers["HX-Redirect"] == "/"
        admin_client.auth.admin.delete_user.assert_called_once_with("test-user-123")

    def test_auth_cookies_cleared_on_success(self, authed_client: TestClient) -> None:
        """Auth cookies are cleared after successful account deletion."""
        resp = authed_client.post(
            "/privacy/delete-account",
            data={"confirm": "DELETE"},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        set_cookie_headers = resp.headers.get_list("set-cookie")
        # Check that sb-access-token cookie is cleared
        access_cleared = any("sb-access-token" in cookie for cookie in set_cookie_headers)
        assert access_cleared, (
            f"Expected sb-access-token to be cleared. Set-Cookie: {set_cookie_headers}"
        )

    def test_admin_error_returns_500(
        self,
        authed_client: TestClient,
        mock_supabase_admin_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Supabase admin error returns 500 with error message."""
        admin_client, _ = mock_supabase_admin_client
        admin_client.auth.admin.delete_user.side_effect = Exception("Admin API error")
        resp = authed_client.post(
            "/privacy/delete-account",
            data={"confirm": "DELETE"},
        )
        assert resp.status_code == 500
        assert "Failed to delete account" in resp.text
