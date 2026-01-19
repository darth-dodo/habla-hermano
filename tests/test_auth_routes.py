"""Tests for authentication routes.

Tests for signup, login, logout endpoints with mocked Supabase.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Response
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes.auth import (
    COOKIE_MAX_AGE,
    COOKIE_NAME,
    clear_auth_cookie,
    get_supabase_client,
    set_auth_cookie,
)


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the app."""
    return TestClient(app)


# =============================================================================
# Cookie Helper Tests
# =============================================================================


class TestSetAuthCookie:
    """Tests for set_auth_cookie helper."""

    def test_sets_cookie_with_correct_name(self) -> None:
        """Test cookie is set with correct name."""
        response = Response()
        set_auth_cookie(response, "test-token")

        # Check that set_cookie was called by checking headers
        assert "set-cookie" in response.headers
        assert COOKIE_NAME in response.headers["set-cookie"]

    def test_sets_cookie_with_httponly(self) -> None:
        """Test cookie is httponly."""
        response = Response()
        set_auth_cookie(response, "test-token")

        cookie_header = response.headers["set-cookie"]
        assert "httponly" in cookie_header.lower()

    def test_sets_cookie_with_secure(self) -> None:
        """Test cookie is secure."""
        response = Response()
        set_auth_cookie(response, "test-token")

        cookie_header = response.headers["set-cookie"]
        assert "secure" in cookie_header.lower()

    def test_sets_cookie_with_samesite_lax(self) -> None:
        """Test cookie has samesite=lax."""
        response = Response()
        set_auth_cookie(response, "test-token")

        cookie_header = response.headers["set-cookie"]
        assert "samesite=lax" in cookie_header.lower()


class TestClearAuthCookie:
    """Tests for clear_auth_cookie helper."""

    def test_clears_cookie(self) -> None:
        """Test cookie is cleared."""
        response = Response()
        clear_auth_cookie(response)

        # The response should have a set-cookie header that expires the cookie
        assert "set-cookie" in response.headers
        cookie_header = response.headers["set-cookie"]
        assert COOKIE_NAME in cookie_header


class TestCookieConstants:
    """Tests for cookie configuration constants."""

    def test_cookie_name(self) -> None:
        """Test cookie name is correct."""
        assert COOKIE_NAME == "sb-access-token"

    def test_cookie_max_age(self) -> None:
        """Test cookie max age is 7 days."""
        assert COOKIE_MAX_AGE == 60 * 60 * 24 * 7


# =============================================================================
# get_supabase_client Tests
# =============================================================================


class TestGetSupabaseClient:
    """Tests for get_supabase_client function."""

    def test_raises_when_not_configured(self) -> None:
        """Test raises HTTPException when Supabase not configured."""
        from fastapi import HTTPException

        with patch("src.api.routes.auth.get_settings") as mock_settings:
            mock_settings.return_value.supabase_configured = False

            with pytest.raises(HTTPException) as exc_info:
                get_supabase_client()

            assert exc_info.value.status_code == 503
            assert "not configured" in exc_info.value.detail

    def test_returns_client_when_configured(self) -> None:
        """Test returns Supabase client when configured."""
        with patch("src.api.routes.auth.get_settings") as mock_settings:
            mock_settings.return_value.supabase_configured = True
            mock_settings.return_value.SUPABASE_URL = "https://test.supabase.co"
            mock_settings.return_value.SUPABASE_ANON_KEY = "test-anon-key"

            with patch("src.api.routes.auth.create_client") as mock_create:
                mock_client = MagicMock()
                mock_create.return_value = mock_client

                result = get_supabase_client()

                assert result == mock_client
                mock_create.assert_called_once_with(
                    "https://test.supabase.co", "test-anon-key"
                )


# =============================================================================
# Login Page Tests
# =============================================================================


class TestLoginPage:
    """Tests for GET /auth/login endpoint."""

    def test_returns_login_page(self, client: TestClient) -> None:
        """Test login page is rendered."""
        response = client.get("/auth/login")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_login_page_contains_form(self, client: TestClient) -> None:
        """Test login page contains login form."""
        response = client.get("/auth/login")

        assert b"email" in response.content
        assert b"password" in response.content


# =============================================================================
# Signup Page Tests
# =============================================================================


class TestSignupPage:
    """Tests for GET /auth/signup endpoint."""

    def test_returns_signup_page(self, client: TestClient) -> None:
        """Test signup page is rendered."""
        response = client.get("/auth/signup")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_signup_page_contains_form(self, client: TestClient) -> None:
        """Test signup page contains signup form."""
        response = client.get("/auth/signup")

        assert b"email" in response.content
        assert b"password" in response.content
        assert b"confirm_password" in response.content or b"confirm" in response.content


# =============================================================================
# POST /auth/signup Tests
# =============================================================================


class TestSignupEndpoint:
    """Tests for POST /auth/signup endpoint."""

    def test_passwords_mismatch_returns_error(self, client: TestClient) -> None:
        """Test signup fails when passwords don't match."""
        response = client.post(
            "/auth/signup",
            data={
                "email": "test@example.com",
                "password": "password123",
                "confirm_password": "different123",
            },
        )

        assert response.status_code == 400
        assert b"do not match" in response.content

    def test_short_password_returns_error(self, client: TestClient) -> None:
        """Test signup fails when password is too short."""
        response = client.post(
            "/auth/signup",
            data={
                "email": "test@example.com",
                "password": "short",
                "confirm_password": "short",
            },
        )

        assert response.status_code == 400
        assert b"at least 8 characters" in response.content

    def test_successful_signup_with_session(self, client: TestClient) -> None:
        """Test successful signup sets cookie and redirects."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock successful signup with session
            mock_session = MagicMock()
            mock_session.access_token = "test-access-token"
            mock_response = MagicMock()
            mock_response.user = MagicMock()
            mock_response.session = mock_session
            mock_client.auth.sign_up.return_value = mock_response

            response = client.post(
                "/auth/signup",
                data={
                    "email": "test@example.com",
                    "password": "password123",
                    "confirm_password": "password123",
                },
            )

            assert response.status_code == 200
            assert "HX-Redirect" in response.headers

    def test_signup_email_confirmation_required(self, client: TestClient) -> None:
        """Test signup shows message when email confirmation required."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock signup requiring email confirmation
            mock_response = MagicMock()
            mock_response.user = MagicMock()
            mock_response.session = None  # No session = email confirmation required
            mock_client.auth.sign_up.return_value = mock_response

            response = client.post(
                "/auth/signup",
                data={
                    "email": "test@example.com",
                    "password": "password123",
                    "confirm_password": "password123",
                },
            )

            assert response.status_code == 200
            assert b"check your email" in response.content.lower()

    def test_signup_user_creation_failed(self, client: TestClient) -> None:
        """Test signup handles user creation failure."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock failed signup
            mock_response = MagicMock()
            mock_response.user = None
            mock_client.auth.sign_up.return_value = mock_response

            response = client.post(
                "/auth/signup",
                data={
                    "email": "test@example.com",
                    "password": "password123",
                    "confirm_password": "password123",
                },
            )

            assert response.status_code == 400
            assert b"failed" in response.content.lower()

    def test_signup_already_registered_error(self, client: TestClient) -> None:
        """Test signup handles already registered error."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock already registered error
            mock_client.auth.sign_up.side_effect = Exception(
                "User already registered"
            )

            response = client.post(
                "/auth/signup",
                data={
                    "email": "test@example.com",
                    "password": "password123",
                    "confirm_password": "password123",
                },
            )

            assert response.status_code == 400
            assert b"already exists" in response.content.lower()

    def test_signup_invalid_email_error(self, client: TestClient) -> None:
        """Test signup handles invalid email error."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock invalid email error
            mock_client.auth.sign_up.side_effect = Exception("Invalid email address")

            response = client.post(
                "/auth/signup",
                data={
                    "email": "invalid-email",
                    "password": "password123",
                    "confirm_password": "password123",
                },
            )

            assert response.status_code == 400
            assert b"valid email" in response.content.lower()


# =============================================================================
# POST /auth/login Tests
# =============================================================================


class TestLoginEndpoint:
    """Tests for POST /auth/login endpoint."""

    def test_successful_login(self, client: TestClient) -> None:
        """Test successful login sets cookie and redirects."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock successful login
            mock_session = MagicMock()
            mock_session.access_token = "test-access-token"
            mock_response = MagicMock()
            mock_response.session = mock_session
            mock_client.auth.sign_in_with_password.return_value = mock_response

            response = client.post(
                "/auth/login",
                data={
                    "email": "test@example.com",
                    "password": "password123",
                },
            )

            assert response.status_code == 200
            assert "HX-Redirect" in response.headers
            assert response.headers["HX-Redirect"] == "/"

    def test_login_no_session(self, client: TestClient) -> None:
        """Test login fails when no session returned."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock failed login (no session)
            mock_response = MagicMock()
            mock_response.session = None
            mock_client.auth.sign_in_with_password.return_value = mock_response

            response = client.post(
                "/auth/login",
                data={
                    "email": "test@example.com",
                    "password": "wrongpassword",
                },
            )

            assert response.status_code == 401
            assert b"invalid" in response.content.lower()

    def test_login_invalid_credentials_error(self, client: TestClient) -> None:
        """Test login handles invalid credentials error."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock invalid credentials error
            mock_client.auth.sign_in_with_password.side_effect = Exception(
                "Invalid login credentials"
            )

            response = client.post(
                "/auth/login",
                data={
                    "email": "test@example.com",
                    "password": "wrongpassword",
                },
            )

            assert response.status_code == 401
            assert b"invalid" in response.content.lower()

    def test_login_email_not_confirmed_error(self, client: TestClient) -> None:
        """Test login handles email not confirmed error."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock email not confirmed error
            mock_client.auth.sign_in_with_password.side_effect = Exception(
                "Email not confirmed"
            )

            response = client.post(
                "/auth/login",
                data={
                    "email": "test@example.com",
                    "password": "password123",
                },
            )

            assert response.status_code == 401
            assert b"confirm" in response.content.lower()


# =============================================================================
# Logout Tests
# =============================================================================


class TestLogoutEndpoints:
    """Tests for logout endpoints."""

    def test_post_logout_clears_cookie(self, client: TestClient) -> None:
        """Test POST /auth/logout clears auth cookie."""
        response = client.post("/auth/logout")

        assert response.status_code == 200
        assert "HX-Redirect" in response.headers
        assert response.headers["HX-Redirect"] == "/auth/login"

    def test_get_logout_redirects(self, client: TestClient) -> None:
        """Test GET /auth/logout redirects to login."""
        response = client.get("/auth/logout", follow_redirects=False)

        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]
