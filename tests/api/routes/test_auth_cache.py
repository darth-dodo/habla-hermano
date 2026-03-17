"""Tests for Cache-Control: no-store on auth HTML responses.

Security finding M9: Auth pages must be marked with Cache-Control: no-store
so browsers and proxies do not cache sensitive authentication pages.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from tests.conftest import CSRF_HEADERS


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the app with CSRF headers."""
    return TestClient(app, headers=CSRF_HEADERS)


# =============================================================================
# Cache-Control: no-store on HTML auth responses
# =============================================================================


class TestAuthPagesCacheControl:
    """Auth HTML pages must include Cache-Control: no-store (security M9)."""

    def test_login_page_has_no_store(self, client: TestClient) -> None:
        """GET /auth/login must respond with Cache-Control: no-store."""
        response = client.get("/auth/login")

        assert response.status_code == 200
        cache_control = response.headers.get("cache-control", "")
        assert "no-store" in cache_control, (
            f"GET /auth/login missing Cache-Control: no-store. Got: {cache_control!r}"
        )

    def test_signup_page_has_no_store(self, client: TestClient) -> None:
        """GET /auth/signup must respond with Cache-Control: no-store."""
        response = client.get("/auth/signup")

        assert response.status_code == 200
        cache_control = response.headers.get("cache-control", "")
        assert "no-store" in cache_control, (
            f"GET /auth/signup missing Cache-Control: no-store. Got: {cache_control!r}"
        )

    def test_logout_get_has_no_store(self, client: TestClient) -> None:
        """GET /auth/logout redirect must include Cache-Control: no-store."""
        response = client.get("/auth/logout", follow_redirects=False)

        # Expect 302 redirect; the redirect response itself must carry no-store
        assert response.status_code == 302
        cache_control = response.headers.get("cache-control", "")
        assert "no-store" in cache_control, (
            f"GET /auth/logout missing Cache-Control: no-store. Got: {cache_control!r}"
        )

    def test_signup_post_validation_error_has_no_store(self, client: TestClient) -> None:
        """POST /auth/signup that returns an HTML error page must include no-store."""
        response = client.post(
            "/auth/signup",
            data={
                "email": "test@example.com",
                "password": "short",
                "confirm_password": "short",
            },
        )

        assert response.status_code == 200
        cache_control = response.headers.get("cache-control", "")
        assert "no-store" in cache_control, (
            f"POST /auth/signup error page missing Cache-Control: no-store. Got: {cache_control!r}"
        )

    def test_login_post_error_has_no_store(self, client: TestClient) -> None:
        """POST /auth/login that returns an HTML error page must include no-store."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            from supabase import AuthApiError

            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.auth.sign_in_with_password.side_effect = AuthApiError(
                "Invalid login credentials", 400, {}
            )

            response = client.post(
                "/auth/login",
                data={
                    "email": "bad@example.com",
                    "password": "wrongpassword",
                },
            )

        assert response.status_code == 200
        cache_control = response.headers.get("cache-control", "")
        assert "no-store" in cache_control, (
            f"POST /auth/login error page missing Cache-Control: no-store. Got: {cache_control!r}"
        )

    def test_signup_post_passwords_mismatch_has_no_store(self, client: TestClient) -> None:
        """POST /auth/signup with mismatched passwords HTML response must include no-store."""
        response = client.post(
            "/auth/signup",
            data={
                "email": "test@example.com",
                "password": "password123",
                "confirm_password": "different123",
            },
        )

        assert response.status_code == 200
        cache_control = response.headers.get("cache-control", "")
        assert "no-store" in cache_control, (
            f"POST /auth/signup mismatch page missing Cache-Control: no-store. Got: {cache_control!r}"
        )

    def test_signup_post_email_confirmation_has_no_store(self, client: TestClient) -> None:
        """POST /auth/signup email-confirmation HTML response must include no-store."""
        with patch("src.api.routes.auth.get_supabase_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            mock_auth_response = MagicMock()
            mock_auth_response.user = MagicMock()
            mock_auth_response.session = None  # email confirmation required
            mock_client.auth.sign_up.return_value = mock_auth_response

            response = client.post(
                "/auth/signup",
                data={
                    "email": "new@example.com",
                    "password": "password123",
                    "confirm_password": "password123",
                },
            )

        assert response.status_code == 200
        cache_control = response.headers.get("cache-control", "")
        assert "no-store" in cache_control, (
            f"POST /auth/signup confirmation page missing Cache-Control: no-store. Got: {cache_control!r}"
        )
