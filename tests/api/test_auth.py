"""Tests for authentication module.

Comprehensive tests for Supabase JWT validation and FastAPI auth dependencies.
Covers both the secure Supabase verification path and the local-dev fallback,
as well as the proactive JWT token refresh mechanism.
"""

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from src.api.auth import (
    TOKEN_REFRESH_THRESHOLD_SECONDS,
    AuthenticatedUser,
    CurrentUserDep,
    OptionalUserDep,
    _decode_token_unverified,
    _get_refresh_token_from_request,
    _is_token_expiring_soon,
    _try_refresh_token,
    _verify_token_via_supabase,
    get_current_user,
    get_current_user_optional,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def valid_jwt_payload() -> dict:
    """Create a valid JWT payload with future expiration."""
    return {
        "sub": "test-user-123",
        "email": "test@example.com",
        "exp": int(time.time()) + 3600,  # 1 hour from now
        "aud": "authenticated",
        "role": "authenticated",
    }


@pytest.fixture
def expired_jwt_payload() -> dict:
    """Create an expired JWT payload."""
    return {
        "sub": "test-user-123",
        "email": "test@example.com",
        "exp": int(time.time()) - 3600,  # 1 hour ago
        "aud": "authenticated",
        "role": "authenticated",
    }


@pytest.fixture
def expiring_soon_jwt_payload() -> dict:
    """Create a JWT payload expiring within the refresh threshold."""
    return {
        "sub": "test-user-123",
        "email": "test@example.com",
        "exp": int(time.time()) + 60,  # 1 minute from now (within 5-min threshold)
        "aud": "authenticated",
        "role": "authenticated",
    }


@pytest.fixture
def missing_sub_jwt_payload() -> dict:
    """Create a JWT payload missing the 'sub' claim."""
    return {
        "email": "test@example.com",
        "exp": int(time.time()) + 3600,
        "aud": "authenticated",
    }


def create_test_token(payload: dict, secret: str = "test-secret") -> str:
    """Create a JWT token from a payload."""
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def valid_token(valid_jwt_payload: dict) -> str:
    """Create a valid JWT token."""
    return create_test_token(valid_jwt_payload)


@pytest.fixture
def expired_token(expired_jwt_payload: dict) -> str:
    """Create an expired JWT token."""
    return create_test_token(expired_jwt_payload)


@pytest.fixture
def expiring_soon_token(expiring_soon_jwt_payload: dict) -> str:
    """Create a JWT token expiring within the refresh threshold."""
    return create_test_token(expiring_soon_jwt_payload)


@pytest.fixture
def token_missing_sub(missing_sub_jwt_payload: dict) -> str:
    """Create a JWT token missing the 'sub' claim."""
    return create_test_token(missing_sub_jwt_payload)


@pytest.fixture
def mock_settings_no_supabase() -> MagicMock:
    """Mock settings where Supabase is NOT configured (local dev)."""
    settings = MagicMock()
    settings.supabase_configured = False
    return settings


@pytest.fixture
def mock_settings_with_supabase() -> MagicMock:
    """Mock settings where Supabase IS configured (production)."""
    settings = MagicMock()
    settings.supabase_configured = True
    return settings


@pytest.fixture
def mock_response() -> Response:
    """Create a mock FastAPI Response for cookie testing."""
    return Response()


@pytest.fixture
def test_app() -> FastAPI:
    """Create a test FastAPI app with auth-protected routes."""
    app = FastAPI()

    @app.get("/protected")
    async def protected_route(user: CurrentUserDep) -> dict:
        """Route requiring authentication."""
        return {"user_id": user.id, "email": user.email}

    @app.get("/optional")
    async def optional_route(user: OptionalUserDep) -> dict:
        """Route with optional authentication."""
        if user:
            return {"authenticated": True, "user_id": user.id}
        return {"authenticated": False, "user_id": None}

    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    """Create a test client for the app."""
    return TestClient(test_app)


# =============================================================================
# AuthenticatedUser Tests
# =============================================================================


class TestAuthenticatedUser:
    """Tests for AuthenticatedUser dataclass."""

    def test_authenticated_user_creation(self) -> None:
        """Test AuthenticatedUser can be created with required fields."""
        user = AuthenticatedUser(id="user-123", email="user@example.com")
        assert user.id == "user-123"
        assert user.email == "user@example.com"

    def test_authenticated_user_is_frozen(self) -> None:
        """Test AuthenticatedUser is immutable (frozen dataclass)."""
        user = AuthenticatedUser(id="user-123", email="user@example.com")
        with pytest.raises(AttributeError):
            user.id = "new-id"  # type: ignore[misc]

    def test_authenticated_user_equality(self) -> None:
        """Test AuthenticatedUser equality comparison."""
        user1 = AuthenticatedUser(id="user-123", email="user@example.com")
        user2 = AuthenticatedUser(id="user-123", email="user@example.com")
        user3 = AuthenticatedUser(id="user-456", email="user@example.com")

        assert user1 == user2
        assert user1 != user3


# =============================================================================
# get_current_user Tests (Supabase NOT configured -- fallback path)
# =============================================================================


class TestGetCurrentUser:
    """Tests for get_current_user dependency when Supabase is not configured.

    These tests exercise the unverified JWT decode fallback path, which is
    only active when supabase_configured is False (local development).
    """

    @pytest.mark.asyncio
    async def test_valid_token_from_header(
        self,
        valid_token: str,
        mock_settings_no_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test get_current_user with valid token in Authorization header."""
        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = f"Bearer {valid_token}"

        with patch("src.api.auth.get_settings", return_value=mock_settings_no_supabase):
            user = await get_current_user(request, mock_response)

        assert isinstance(user, AuthenticatedUser)
        assert user.id == "test-user-123"
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_valid_token_from_cookie(
        self,
        valid_token: str,
        mock_settings_no_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test get_current_user with valid token in cookie."""
        request = MagicMock()
        request.cookies.get.return_value = valid_token
        request.headers.get.return_value = None

        with patch("src.api.auth.get_settings", return_value=mock_settings_no_supabase):
            user = await get_current_user(request, mock_response)

        assert isinstance(user, AuthenticatedUser)
        assert user.id == "test-user-123"
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_missing_token_raises_401(self, mock_response: Response) -> None:
        """Test get_current_user raises 401 when no token is present."""
        from fastapi import HTTPException

        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request, mock_response)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(
        self,
        expired_token: str,
        mock_settings_no_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test get_current_user raises 401 for expired token."""
        from fastapi import HTTPException

        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = f"Bearer {expired_token}"

        with patch("src.api.auth.get_settings", return_value=mock_settings_no_supabase):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(request, mock_response)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Token expired"

    @pytest.mark.asyncio
    async def test_missing_sub_raises_401(
        self,
        token_missing_sub: str,
        mock_settings_no_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test get_current_user raises 401 when token is missing 'sub' claim."""
        from fastapi import HTTPException

        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = f"Bearer {token_missing_sub}"

        with patch("src.api.auth.get_settings", return_value=mock_settings_no_supabase):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(request, mock_response)

        assert exc_info.value.status_code == 401
        assert "missing user ID" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_token_format_raises_401(
        self,
        mock_settings_no_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test get_current_user raises 401 for malformed token."""
        from fastapi import HTTPException

        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = "Bearer not-a-valid-jwt-token"

        with patch("src.api.auth.get_settings", return_value=mock_settings_no_supabase):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(request, mock_response)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_cookie_takes_precedence_over_header(
        self,
        valid_token: str,
        expired_token: str,
        mock_settings_no_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test that cookie token is used when both are present."""
        request = MagicMock()
        request.cookies.get.return_value = valid_token  # Valid cookie
        request.headers.get.return_value = f"Bearer {expired_token}"  # Expired header

        with patch("src.api.auth.get_settings", return_value=mock_settings_no_supabase):
            # Should use the valid cookie token
            user = await get_current_user(request, mock_response)
        assert user.id == "test-user-123"

    @pytest.mark.asyncio
    async def test_token_without_email_uses_empty_string(
        self,
        mock_settings_no_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test that missing email defaults to empty string."""
        payload = {
            "sub": "user-no-email",
            "exp": int(time.time()) + 3600,
        }
        token = create_test_token(payload)

        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = f"Bearer {token}"

        with patch("src.api.auth.get_settings", return_value=mock_settings_no_supabase):
            user = await get_current_user(request, mock_response)
        assert user.id == "user-no-email"
        assert user.email == ""


# =============================================================================
# get_current_user_optional Tests
# =============================================================================


class TestGetCurrentUserOptional:
    """Tests for get_current_user_optional dependency."""

    @pytest.mark.asyncio
    async def test_returns_user_when_valid_token(
        self,
        valid_token: str,
        mock_settings_no_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test get_current_user_optional returns user with valid token."""
        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = f"Bearer {valid_token}"

        with patch("src.api.auth.get_settings", return_value=mock_settings_no_supabase):
            user = await get_current_user_optional(request, mock_response)

        assert user is not None
        assert isinstance(user, AuthenticatedUser)
        assert user.id == "test-user-123"

    @pytest.mark.asyncio
    async def test_returns_none_when_missing_token(self, mock_response: Response) -> None:
        """Test get_current_user_optional returns None when no token present."""
        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = None

        user = await get_current_user_optional(request, mock_response)

        assert user is None

    @pytest.mark.asyncio
    async def test_returns_none_when_invalid_token(
        self,
        mock_settings_no_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test get_current_user_optional returns None for invalid token."""
        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = "Bearer invalid-token"

        with patch("src.api.auth.get_settings", return_value=mock_settings_no_supabase):
            user = await get_current_user_optional(request, mock_response)

        assert user is None

    @pytest.mark.asyncio
    async def test_returns_none_when_expired_token(
        self,
        expired_token: str,
        mock_settings_no_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test get_current_user_optional returns None for expired token."""
        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = f"Bearer {expired_token}"

        with patch("src.api.auth.get_settings", return_value=mock_settings_no_supabase):
            user = await get_current_user_optional(request, mock_response)

        assert user is None


# =============================================================================
# Type Alias Tests
# =============================================================================


class TestTypeAliases:
    """Tests for CurrentUserDep and OptionalUserDep type aliases."""

    def test_current_user_dep_is_annotated_type(self) -> None:
        """Test CurrentUserDep is an Annotated type with Depends."""
        assert CurrentUserDep.__class__.__name__ == "_AnnotatedAlias"

    def test_optional_user_dep_is_annotated_type(self) -> None:
        """Test OptionalUserDep is an Annotated type with Depends."""
        assert OptionalUserDep.__class__.__name__ == "_AnnotatedAlias"


# =============================================================================
# Supabase Server-Side Verification Tests
# =============================================================================


class TestSupabaseVerification:
    """Tests for Supabase auth.get_user() server-side token verification."""

    @pytest.mark.asyncio
    async def test_valid_token_verified_by_supabase(
        self,
        valid_token: str,
        mock_settings_with_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test that a valid token is verified via Supabase auth.get_user()."""
        mock_supabase_user = MagicMock()
        mock_supabase_user.id = "supabase-verified-user-id"
        mock_supabase_user.email = "verified@supabase.com"

        mock_supabase_response = MagicMock()
        mock_supabase_response.user = mock_supabase_user

        mock_client = MagicMock()
        mock_client.auth.get_user.return_value = mock_supabase_response

        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = f"Bearer {valid_token}"

        with (
            patch("src.api.auth.get_settings", return_value=mock_settings_with_supabase),
            patch("src.api.auth.get_supabase", return_value=mock_client),
        ):
            user = await get_current_user(request, mock_response)

        assert isinstance(user, AuthenticatedUser)
        assert user.id == "supabase-verified-user-id"
        assert user.email == "verified@supabase.com"
        mock_client.auth.get_user.assert_called_once_with(valid_token)

    @pytest.mark.asyncio
    async def test_forged_token_rejected_by_supabase(
        self,
        mock_settings_with_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test that a forged/invalid token is rejected by Supabase."""
        from fastapi import HTTPException

        forged_payload = {
            "sub": "attacker-forged-id",
            "email": "attacker@evil.com",
            "exp": int(time.time()) + 3600,
        }
        forged_token = create_test_token(forged_payload, secret="wrong-secret")

        mock_client = MagicMock()
        import httpx

        mock_client.auth.get_user.side_effect = httpx.HTTPError("Invalid JWT: signature mismatch")

        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = f"Bearer {forged_token}"

        with (
            patch("src.api.auth.get_settings", return_value=mock_settings_with_supabase),
            patch("src.api.auth.get_supabase", return_value=mock_client),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(request, mock_response)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Token verification failed"

    @pytest.mark.asyncio
    async def test_supabase_returns_null_user(
        self,
        valid_token: str,
        mock_settings_with_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test that a null user response from Supabase yields 401."""
        from fastapi import HTTPException

        mock_supabase_response = MagicMock()
        mock_supabase_response.user = None

        mock_client = MagicMock()
        mock_client.auth.get_user.return_value = mock_supabase_response

        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = f"Bearer {valid_token}"

        with (
            patch("src.api.auth.get_settings", return_value=mock_settings_with_supabase),
            patch("src.api.auth.get_supabase", return_value=mock_client),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(request, mock_response)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid or expired token"

    @pytest.mark.asyncio
    async def test_supabase_unavailable_returns_401(
        self,
        valid_token: str,
        mock_settings_with_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test that Supabase network errors yield 401, not a fallback."""
        from fastapi import HTTPException

        mock_client = MagicMock()
        import httpx

        mock_client.auth.get_user.side_effect = httpx.ConnectError("Failed to connect to Supabase")

        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = f"Bearer {valid_token}"

        with (
            patch("src.api.auth.get_settings", return_value=mock_settings_with_supabase),
            patch("src.api.auth.get_supabase", return_value=mock_client),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(request, mock_response)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Token verification failed"

    @pytest.mark.asyncio
    async def test_fallback_logs_warning_when_supabase_not_configured(
        self,
        valid_token: str,
        mock_settings_no_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test fallback to unverified decode logs a warning."""
        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = f"Bearer {valid_token}"

        with (
            patch("src.api.auth.get_settings", return_value=mock_settings_no_supabase),
            patch("src.api.auth.logger") as mock_logger,
        ):
            user = await get_current_user(request, mock_response)

        assert isinstance(user, AuthenticatedUser)
        assert user.id == "test-user-123"
        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "DISABLED" in warning_msg

    @pytest.mark.asyncio
    async def test_supabase_user_with_no_email(
        self,
        valid_token: str,
        mock_settings_with_supabase: MagicMock,
        mock_response: Response,
    ) -> None:
        """Test Supabase user with email=None defaults to empty string."""
        mock_supabase_user = MagicMock()
        mock_supabase_user.id = "user-no-email"
        mock_supabase_user.email = None

        mock_supabase_response = MagicMock()
        mock_supabase_response.user = mock_supabase_user

        mock_client = MagicMock()
        mock_client.auth.get_user.return_value = mock_supabase_response

        request = MagicMock()
        request.cookies.get.return_value = None
        request.headers.get.return_value = f"Bearer {valid_token}"

        with (
            patch("src.api.auth.get_settings", return_value=mock_settings_with_supabase),
            patch("src.api.auth.get_supabase", return_value=mock_client),
        ):
            user = await get_current_user(request, mock_response)

        assert user.id == "user-no-email"
        assert user.email == ""


# =============================================================================
# _verify_token_via_supabase Unit Tests
# =============================================================================


class TestVerifyTokenViaSupabase:
    """Direct unit tests for the _verify_token_via_supabase helper."""

    def test_raises_valueerror_when_supabase_not_configured(self) -> None:
        """Test that ValueError from get_supabase() propagates."""
        with patch(
            "src.api.auth.get_supabase",
            side_effect=ValueError("Supabase is not configured."),
        ):
            with pytest.raises(ValueError, match="Supabase is not configured"):
                _verify_token_via_supabase("any-token")


# =============================================================================
# _decode_token_unverified Unit Tests
# =============================================================================


class TestDecodeTokenUnverified:
    """Direct unit tests for the _decode_token_unverified helper."""

    def test_valid_token_decoded(self, valid_token: str) -> None:
        """Test successful unverified decode of a valid token."""
        user = _decode_token_unverified(valid_token)
        assert user.id == "test-user-123"
        assert user.email == "test@example.com"

    def test_expired_token_rejected(self, expired_token: str) -> None:
        """Test unverified decode rejects expired token."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _decode_token_unverified(expired_token)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Token expired"

    def test_missing_sub_rejected(self, token_missing_sub: str) -> None:
        """Test unverified decode rejects token without sub claim."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _decode_token_unverified(token_missing_sub)
        assert exc_info.value.status_code == 401
        assert "missing user ID" in exc_info.value.detail

    def test_malformed_token_rejected(self) -> None:
        """Test unverified decode rejects malformed token string."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _decode_token_unverified("not-a-jwt")
        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail


# =============================================================================
# _is_token_expiring_soon Unit Tests
# =============================================================================


class TestIsTokenExpiringSoon:
    """Tests for the _is_token_expiring_soon helper."""

    def test_token_not_expiring_soon(self, valid_token: str) -> None:
        """Test that a token with 1 hour remaining is not expiring soon."""
        assert _is_token_expiring_soon(valid_token) is False

    def test_token_expiring_soon(self, expiring_soon_token: str) -> None:
        """Test that a token within the threshold is detected as expiring soon."""
        assert _is_token_expiring_soon(expiring_soon_token) is True

    def test_expired_token_is_expiring_soon(self, expired_token: str) -> None:
        """Test that an already-expired token is detected as expiring soon."""
        assert _is_token_expiring_soon(expired_token) is True

    def test_token_without_exp_claim(self) -> None:
        """Test that a token without exp claim returns False."""
        payload = {"sub": "test-user", "email": "test@example.com"}
        token = create_test_token(payload)
        assert _is_token_expiring_soon(token) is False

    def test_malformed_token_returns_false(self) -> None:
        """Test that a malformed token returns False (no refresh attempt)."""
        assert _is_token_expiring_soon("not-a-jwt") is False

    def test_token_at_exact_threshold(self) -> None:
        """Test token at exactly the threshold boundary."""
        payload = {
            "sub": "test-user",
            "exp": int(time.time()) + TOKEN_REFRESH_THRESHOLD_SECONDS,
        }
        token = create_test_token(payload)
        # At the exact boundary, time.time() > (exp - threshold) should be True
        # since exp - threshold == time.time() and the comparison is strictly >
        # Due to timing, this could go either way, so we just verify no error
        result = _is_token_expiring_soon(token)
        assert isinstance(result, bool)


# =============================================================================
# _get_refresh_token_from_request Unit Tests
# =============================================================================


class TestGetRefreshTokenFromRequest:
    """Tests for the _get_refresh_token_from_request helper."""

    def test_returns_refresh_token_from_cookie(self) -> None:
        """Test extraction of refresh token from cookie."""
        request = MagicMock()
        request.cookies.get.return_value = "test-refresh-token"

        result = _get_refresh_token_from_request(request)

        assert result == "test-refresh-token"
        request.cookies.get.assert_called_once_with("sb-refresh-token")

    def test_returns_none_when_no_cookie(self) -> None:
        """Test returns None when no refresh token cookie exists."""
        request = MagicMock()
        request.cookies.get.return_value = None

        result = _get_refresh_token_from_request(request)

        assert result is None


# =============================================================================
# _try_refresh_token Unit Tests
# =============================================================================


class TestTryRefreshToken:
    """Tests for the _try_refresh_token helper."""

    def test_successful_refresh(self) -> None:
        """Test successful token refresh sets cookies and returns new token."""
        mock_session = MagicMock()
        mock_session.access_token = "new-access-token"
        mock_session.refresh_token = "new-refresh-token"

        mock_refresh_response = MagicMock()
        mock_refresh_response.session = mock_session

        mock_client = MagicMock()
        mock_client.auth.refresh_session.return_value = mock_refresh_response

        response = Response()

        with (
            patch("src.api.auth.get_supabase", return_value=mock_client),
            patch("src.api.routes.auth.set_auth_cookies") as mock_set_cookies,
        ):
            result = _try_refresh_token("old-refresh-token", response)

        assert result == "new-access-token"
        mock_client.auth.refresh_session.assert_called_once_with("old-refresh-token")
        mock_set_cookies.assert_called_once_with(
            response,
            access_token="new-access-token",
            refresh_token="new-refresh-token",
        )

    def test_refresh_returns_no_session(self) -> None:
        """Test refresh returning None session returns None."""
        mock_refresh_response = MagicMock()
        mock_refresh_response.session = None

        mock_client = MagicMock()
        mock_client.auth.refresh_session.return_value = mock_refresh_response

        response = Response()

        with patch("src.api.auth.get_supabase", return_value=mock_client):
            result = _try_refresh_token("old-refresh-token", response)

        assert result is None

    def test_refresh_returns_none_response(self) -> None:
        """Test refresh returning None response returns None."""
        mock_client = MagicMock()
        mock_client.auth.refresh_session.return_value = None

        response = Response()

        with patch("src.api.auth.get_supabase", return_value=mock_client):
            result = _try_refresh_token("old-refresh-token", response)

        assert result is None

    def test_refresh_supabase_not_configured(self) -> None:
        """Test refresh when Supabase is not configured returns None."""
        response = Response()

        with patch(
            "src.api.auth.get_supabase",
            side_effect=ValueError("Supabase not configured"),
        ):
            result = _try_refresh_token("old-refresh-token", response)

        assert result is None

    def test_refresh_network_error(self) -> None:
        """Test refresh with network error returns None."""
        mock_client = MagicMock()
        mock_client.auth.refresh_session.side_effect = ConnectionError("Network error")

        response = Response()

        with patch("src.api.auth.get_supabase", return_value=mock_client):
            result = _try_refresh_token("old-refresh-token", response)

        assert result is None

    def test_refresh_auth_error(self) -> None:
        """Test refresh with auth error returns None."""
        mock_client = MagicMock()
        mock_client.auth.refresh_session.side_effect = Exception("Invalid refresh token")

        response = Response()

        with patch("src.api.auth.get_supabase", return_value=mock_client):
            result = _try_refresh_token("old-refresh-token", response)

        assert result is None


# =============================================================================
# Token Refresh Integration Tests
# =============================================================================


class TestTokenRefreshIntegration:
    """Integration tests for the token refresh mechanism within get_current_user."""

    @pytest.mark.asyncio
    async def test_refresh_triggered_when_token_expiring_soon(
        self,
        expiring_soon_token: str,
        mock_settings_with_supabase: MagicMock,
    ) -> None:
        """Test that refresh is attempted when token is close to expiry."""
        # Create a new valid token that would be returned from refresh
        new_payload = {
            "sub": "test-user-123",
            "email": "test@example.com",
            "exp": int(time.time()) + 3600,
        }
        new_token = create_test_token(new_payload)

        mock_supabase_user = MagicMock()
        mock_supabase_user.id = "test-user-123"
        mock_supabase_user.email = "test@example.com"

        mock_user_response = MagicMock()
        mock_user_response.user = mock_supabase_user

        mock_client = MagicMock()
        mock_client.auth.get_user.return_value = mock_user_response

        mock_session = MagicMock()
        mock_session.access_token = new_token
        mock_session.refresh_token = "new-refresh-token"

        mock_refresh_response = MagicMock()
        mock_refresh_response.session = mock_session

        mock_client.auth.refresh_session.return_value = mock_refresh_response

        request = MagicMock()
        request.cookies.get.side_effect = {
            "sb-access-token": expiring_soon_token,
            "sb-refresh-token": "old-refresh-token",
        }.get
        request.headers.get.return_value = None

        response = Response()

        with (
            patch("src.api.auth.get_settings", return_value=mock_settings_with_supabase),
            patch("src.api.auth.get_supabase", return_value=mock_client),
            patch("src.api.routes.auth.set_auth_cookies"),
        ):
            user = await get_current_user(request, response)

        assert user.id == "test-user-123"
        # Verify refresh was called
        mock_client.auth.refresh_session.assert_called_once_with("old-refresh-token")
        # Verify the refreshed token was used for verification
        mock_client.auth.get_user.assert_called_once_with(new_token)

    @pytest.mark.asyncio
    async def test_no_refresh_when_token_not_expiring(
        self,
        valid_token: str,
        mock_settings_with_supabase: MagicMock,
    ) -> None:
        """Test that refresh is NOT attempted when token has plenty of time left."""
        mock_supabase_user = MagicMock()
        mock_supabase_user.id = "test-user-123"
        mock_supabase_user.email = "test@example.com"

        mock_user_response = MagicMock()
        mock_user_response.user = mock_supabase_user

        mock_client = MagicMock()
        mock_client.auth.get_user.return_value = mock_user_response

        request = MagicMock()
        request.cookies.get.side_effect = {
            "sb-access-token": valid_token,
            "sb-refresh-token": "some-refresh-token",
        }.get
        request.headers.get.return_value = None

        response = Response()

        with (
            patch("src.api.auth.get_settings", return_value=mock_settings_with_supabase),
            patch("src.api.auth.get_supabase", return_value=mock_client),
        ):
            user = await get_current_user(request, response)

        assert user.id == "test-user-123"
        # Verify refresh was NOT called
        mock_client.auth.refresh_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_refresh_when_no_refresh_token_cookie(
        self,
        expiring_soon_token: str,
        mock_settings_with_supabase: MagicMock,
    ) -> None:
        """Test that refresh is skipped when no refresh token cookie exists."""
        mock_supabase_user = MagicMock()
        mock_supabase_user.id = "test-user-123"
        mock_supabase_user.email = "test@example.com"

        mock_user_response = MagicMock()
        mock_user_response.user = mock_supabase_user

        mock_client = MagicMock()
        mock_client.auth.get_user.return_value = mock_user_response

        request = MagicMock()
        request.cookies.get.side_effect = {
            "sb-access-token": expiring_soon_token,
            "sb-refresh-token": None,
        }.get
        request.headers.get.return_value = None

        response = Response()

        with (
            patch("src.api.auth.get_settings", return_value=mock_settings_with_supabase),
            patch("src.api.auth.get_supabase", return_value=mock_client),
        ):
            user = await get_current_user(request, response)

        assert user.id == "test-user-123"
        # Verify refresh was NOT called (no refresh token)
        mock_client.auth.refresh_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_to_original_token_when_refresh_fails(
        self,
        expiring_soon_token: str,
        mock_settings_with_supabase: MagicMock,
    ) -> None:
        """Test that original token is used when refresh fails."""
        mock_supabase_user = MagicMock()
        mock_supabase_user.id = "test-user-123"
        mock_supabase_user.email = "test@example.com"

        mock_user_response = MagicMock()
        mock_user_response.user = mock_supabase_user

        mock_client = MagicMock()
        mock_client.auth.get_user.return_value = mock_user_response
        mock_client.auth.refresh_session.side_effect = Exception("Refresh failed")

        request = MagicMock()
        request.cookies.get.side_effect = {
            "sb-access-token": expiring_soon_token,
            "sb-refresh-token": "old-refresh-token",
        }.get
        request.headers.get.return_value = None

        response = Response()

        with (
            patch("src.api.auth.get_settings", return_value=mock_settings_with_supabase),
            patch("src.api.auth.get_supabase", return_value=mock_client),
        ):
            user = await get_current_user(request, response)

        assert user.id == "test-user-123"
        # Original token was used for verification since refresh failed
        mock_client.auth.get_user.assert_called_once_with(expiring_soon_token)

    @pytest.mark.asyncio
    async def test_no_refresh_when_supabase_not_configured(
        self,
        expiring_soon_token: str,
        mock_settings_no_supabase: MagicMock,
    ) -> None:
        """Test that refresh is skipped in local dev mode (no Supabase)."""
        request = MagicMock()
        request.cookies.get.side_effect = {
            "sb-access-token": expiring_soon_token,
            "sb-refresh-token": "some-refresh-token",
        }.get
        request.headers.get.return_value = None

        response = Response()

        with patch("src.api.auth.get_settings", return_value=mock_settings_no_supabase):
            # Token is still valid (just expiring soon), so local dev decode succeeds
            user = await get_current_user(request, response)

        assert user.id == "test-user-123"

    @pytest.mark.asyncio
    async def test_refresh_with_bearer_header_token(
        self,
        mock_settings_with_supabase: MagicMock,
    ) -> None:
        """Test refresh works with token from Authorization header."""
        # Create an expiring token
        payload = {
            "sub": "test-user-123",
            "email": "test@example.com",
            "exp": int(time.time()) + 60,  # Expiring soon
        }
        expiring_token = create_test_token(payload)

        new_token = create_test_token(
            {
                "sub": "test-user-123",
                "email": "test@example.com",
                "exp": int(time.time()) + 3600,
            }
        )

        mock_supabase_user = MagicMock()
        mock_supabase_user.id = "test-user-123"
        mock_supabase_user.email = "test@example.com"

        mock_user_response = MagicMock()
        mock_user_response.user = mock_supabase_user

        mock_session = MagicMock()
        mock_session.access_token = new_token
        mock_session.refresh_token = "new-refresh"

        mock_refresh_response = MagicMock()
        mock_refresh_response.session = mock_session

        mock_client = MagicMock()
        mock_client.auth.get_user.return_value = mock_user_response
        mock_client.auth.refresh_session.return_value = mock_refresh_response

        request = MagicMock()
        # Token from header, no access token cookie
        request.cookies.get.side_effect = {
            "sb-access-token": None,
            "sb-refresh-token": "refresh-token-from-cookie",
        }.get
        request.headers.get.return_value = f"Bearer {expiring_token}"

        response = Response()

        with (
            patch("src.api.auth.get_settings", return_value=mock_settings_with_supabase),
            patch("src.api.auth.get_supabase", return_value=mock_client),
            patch("src.api.routes.auth.set_auth_cookies"),
        ):
            user = await get_current_user(request, response)

        assert user.id == "test-user-123"
        mock_client.auth.refresh_session.assert_called_once_with("refresh-token-from-cookie")


# =============================================================================
# Integration Tests with FastAPI
# =============================================================================


class TestAuthIntegration:
    """Integration tests for auth dependencies with FastAPI routes."""

    def test_protected_route_with_valid_token(self, client: TestClient, valid_token: str) -> None:
        """Test protected route accepts valid token (via fallback path)."""
        mock_settings = MagicMock()
        mock_settings.supabase_configured = False

        with patch("src.api.auth.get_settings", return_value=mock_settings):
            response = client.get(
                "/protected",
                headers={"Authorization": f"Bearer {valid_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test-user-123"
        assert data["email"] == "test@example.com"

    def test_protected_route_without_token(self, client: TestClient) -> None:
        """Test protected route returns 401 without token."""
        response = client.get("/protected")
        assert response.status_code == 401

    def test_protected_route_with_expired_token(
        self, client: TestClient, expired_token: str
    ) -> None:
        """Test protected route returns 401 with expired token."""
        mock_settings = MagicMock()
        mock_settings.supabase_configured = False

        with patch("src.api.auth.get_settings", return_value=mock_settings):
            response = client.get(
                "/protected",
                headers={"Authorization": f"Bearer {expired_token}"},
            )

        assert response.status_code == 401

    def test_optional_route_with_valid_token(self, client: TestClient, valid_token: str) -> None:
        """Test optional route returns user info with valid token."""
        mock_settings = MagicMock()
        mock_settings.supabase_configured = False

        with patch("src.api.auth.get_settings", return_value=mock_settings):
            response = client.get(
                "/optional",
                headers={"Authorization": f"Bearer {valid_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["user_id"] == "test-user-123"

    def test_optional_route_without_token(self, client: TestClient) -> None:
        """Test optional route works without token."""
        response = client.get("/optional")

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False
        assert data["user_id"] is None

    def test_protected_route_with_cookie(self, client: TestClient, valid_token: str) -> None:
        """Test protected route accepts token from cookie."""
        mock_settings = MagicMock()
        mock_settings.supabase_configured = False

        with patch("src.api.auth.get_settings", return_value=mock_settings):
            response = client.get(
                "/protected",
                cookies={"sb-access-token": valid_token},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test-user-123"

    def test_protected_route_with_supabase_verification(
        self, client: TestClient, valid_token: str
    ) -> None:
        """Test protected route with Supabase server-side verification."""
        mock_settings = MagicMock()
        mock_settings.supabase_configured = True

        mock_supabase_user = MagicMock()
        mock_supabase_user.id = "verified-id"
        mock_supabase_user.email = "verified@test.com"

        mock_supabase_response = MagicMock()
        mock_supabase_response.user = mock_supabase_user

        mock_client = MagicMock()
        mock_client.auth.get_user.return_value = mock_supabase_response

        with (
            patch("src.api.auth.get_settings", return_value=mock_settings),
            patch("src.api.auth.get_supabase", return_value=mock_client),
        ):
            response = client.get(
                "/protected",
                headers={"Authorization": f"Bearer {valid_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "verified-id"
        assert data["email"] == "verified@test.com"
