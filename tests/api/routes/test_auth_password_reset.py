"""Tests for password reset authentication routes.

Tests for forgot-password and reset-password endpoints with mocked Supabase.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from supabase import AuthApiError

from src.api.main import app
from tests.conftest import CSRF_HEADERS


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the app with CSRF headers."""
    return TestClient(app, headers=CSRF_HEADERS)


# =============================================================================
# Forgot Password Page Tests
# =============================================================================


class TestForgotPasswordPage:
    """Tests for GET /auth/forgot-password endpoint."""

    def test_returns_forgot_password_page(self, client: TestClient) -> None:
        """Test forgot password page is rendered."""
        response = client.get("/auth/forgot-password")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_page_contains_email_form(self, client: TestClient) -> None:
        """Test forgot password page contains email form field."""
        response = client.get("/auth/forgot-password")

        assert b"email" in response.content
        assert b"forgot-password" in response.content


# =============================================================================
# POST /auth/forgot-password Tests
# =============================================================================


class TestForgotPasswordEndpoint:
    """Tests for POST /auth/forgot-password endpoint."""

    def test_shows_success_message(self, client: TestClient) -> None:
        """Test forgot password shows success message on valid request."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            response = client.post(
                "/auth/forgot-password",
                data={"email": "test@example.com"},
            )

            assert response.status_code == 200
            assert b"reset link" in response.content

    def test_shows_success_even_for_nonexistent_email(
        self, client: TestClient
    ) -> None:
        """Test forgot password shows success even when email doesn't exist."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock AuthApiError for nonexistent email
            mock_client.auth.reset_password_for_email.side_effect = AuthApiError(
                "User not found", 404, None
            )

            response = client.post(
                "/auth/forgot-password",
                data={"email": "nonexistent@example.com"},
            )

            # Should still show success to prevent email enumeration
            assert response.status_code == 200
            assert b"reset link" in response.content

    def test_calls_reset_password_for_email(self, client: TestClient) -> None:
        """Test forgot password calls Supabase reset_password_for_email."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            client.post(
                "/auth/forgot-password",
                data={"email": "test@example.com"},
            )

            mock_client.auth.reset_password_for_email.assert_called_once()
            call_args = mock_client.auth.reset_password_for_email.call_args
            assert call_args[0][0] == "test@example.com"
            assert "redirect_to" in call_args[1]["options"]


# =============================================================================
# Reset Password Page Tests
# =============================================================================


class TestResetPasswordPage:
    """Tests for GET /auth/reset-password endpoint."""

    def test_returns_reset_password_page(self, client: TestClient) -> None:
        """Test reset password page is rendered."""
        response = client.get("/auth/reset-password")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_page_contains_password_form(self, client: TestClient) -> None:
        """Test reset password page contains password form fields."""
        response = client.get("/auth/reset-password")

        assert b"password" in response.content
        assert b"confirm_password" in response.content

    def test_page_contains_hidden_token_field(self, client: TestClient) -> None:
        """Test reset password page contains hidden access_token field."""
        response = client.get("/auth/reset-password")

        assert b"access_token" in response.content
        assert b'type="hidden"' in response.content


# =============================================================================
# POST /auth/reset-password Tests
# =============================================================================


class TestResetPasswordEndpoint:
    """Tests for POST /auth/reset-password endpoint."""

    def test_passwords_mismatch_returns_error(self, client: TestClient) -> None:
        """Test reset password fails when passwords don't match."""
        response = client.post(
            "/auth/reset-password",
            data={
                "password": "newpassword123",
                "confirm_password": "different123",
                "access_token": "test-token",
            },
        )

        assert response.status_code == 200
        assert b"do not match" in response.content

    def test_short_password_returns_error(self, client: TestClient) -> None:
        """Test reset password fails when password is too short."""
        response = client.post(
            "/auth/reset-password",
            data={
                "password": "short",
                "confirm_password": "short",
                "access_token": "test-token",
            },
        )

        assert response.status_code == 200
        assert b"at least 8 characters" in response.content

    def test_missing_access_token_returns_error(self, client: TestClient) -> None:
        """Test reset password fails when access token is missing."""
        response = client.post(
            "/auth/reset-password",
            data={
                "password": "newpassword123",
                "confirm_password": "newpassword123",
                "access_token": "",
            },
        )

        assert response.status_code == 200
        assert b"expired reset link" in response.content.lower()

    def test_successful_password_reset(self, client: TestClient) -> None:
        """Test successful password reset redirects to login."""
        with patch(
            "src.db.client.get_supabase_for_user"
        ) as mock_get_user_client:
            mock_client = MagicMock()
            mock_get_user_client.return_value = mock_client

            response = client.post(
                "/auth/reset-password",
                data={
                    "password": "newpassword123",
                    "confirm_password": "newpassword123",
                    "access_token": "test-recovery-token",
                },
            )

            assert response.status_code == 200
            assert "HX-Redirect" in response.headers
            assert response.headers["HX-Redirect"] == "/auth/login"
            mock_client.auth.update_user.assert_called_once_with(
                {"password": "newpassword123"}
            )

    def test_auth_error_shows_message(self, client: TestClient) -> None:
        """Test reset password shows error when Supabase returns AuthApiError."""
        with patch(
            "src.db.client.get_supabase_for_user"
        ) as mock_get_user_client:
            mock_client = MagicMock()
            mock_get_user_client.return_value = mock_client

            mock_client.auth.update_user.side_effect = AuthApiError(
                "Token expired", 401, None
            )

            response = client.post(
                "/auth/reset-password",
                data={
                    "password": "newpassword123",
                    "confirm_password": "newpassword123",
                    "access_token": "expired-token",
                },
            )

            assert response.status_code == 200
            assert b"failed to reset password" in response.content.lower()
