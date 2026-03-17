"""Authentication utilities for Supabase JWT validation.

Provides JWT token validation using Supabase's auth.get_user() for server-side
verification and a FastAPI dependency for extracting the current authenticated user.
Also provides EffectiveUser for unified authenticated/guest identity.

Security:
- Production: Tokens are verified server-side via Supabase auth.get_user()
- Local dev: Falls back to unverified JWT decode with a WARNING log
- Token refresh: Proactively refreshes tokens nearing expiry (within 5 minutes)
"""

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Annotated

import httpx
import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, Response, status
from supabase_auth.errors import AuthApiError

from src.api.config import get_settings
from src.api.supabase_client import SupabaseClient, get_supabase, get_supabase_admin

logger = logging.getLogger(__name__)

# Threshold in seconds before expiry to trigger a refresh attempt.
# If a token expires within this window, we try to refresh proactively.
TOKEN_REFRESH_THRESHOLD_SECONDS = 300  # 5 minutes


@dataclass(frozen=True)
class AuthenticatedUser:
    """Represents an authenticated user extracted from JWT.

    Attributes:
        id: User's unique identifier (UUID from Supabase Auth).
        email: User's email address.
    """

    id: str
    email: str


def _is_valid_session_id(value: str) -> bool:
    """Validate that a session_id is a well-formed UUID v4.

    Prevents injection attacks by rejecting arbitrary strings in the
    session_id cookie. Only accepts lowercase canonical UUID format.

    Args:
        value: The raw cookie value to validate.

    Returns:
        True if value is a valid UUID v4 string, False otherwise.
    """
    try:
        parsed = uuid.UUID(value, version=4)
    except (ValueError, AttributeError):
        return False
    return str(parsed) == value


def _get_token_from_request(request: Request) -> str | None:
    """Extract JWT token from request cookies or Authorization header.

    Checks cookies first (for browser sessions), then Authorization header
    (for API clients).

    Args:
        request: FastAPI request object.

    Returns:
        JWT token string if found, None otherwise.
    """
    # Check cookie first (browser sessions)
    token = request.cookies.get("sb-access-token")
    if token:
        return token

    # Check Authorization header (API clients)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]  # Remove "Bearer " prefix

    return None


def _get_refresh_token_from_request(request: Request) -> str | None:
    """Extract refresh token from request cookies.

    Args:
        request: FastAPI request object.

    Returns:
        Refresh token string if found, None otherwise.
    """
    return request.cookies.get("sb-refresh-token")


def _is_token_expiring_soon(token: str) -> bool:
    """Check if a JWT token is expiring within the refresh threshold.

    Decodes the token without signature verification to read the 'exp' claim.
    This is safe because we only use this to decide whether to attempt a
    refresh -- the actual authentication still goes through Supabase's
    server-side verification.

    Args:
        token: Raw JWT access token string.

    Returns:
        True if the token expires within TOKEN_REFRESH_THRESHOLD_SECONDS,
        or if expiry cannot be determined. False otherwise.
    """
    try:
        payload = pyjwt.decode(
            token,
            options={"verify_signature": False},
            algorithms=["HS256"],
        )
        exp = payload.get("exp")
        if exp is None:
            return False
        return bool(time.time() > (exp - TOKEN_REFRESH_THRESHOLD_SECONDS))
    except pyjwt.PyJWTError:
        # If we cannot decode the token at all, do not attempt refresh.
        # Let the normal verification path handle the error.
        return False


def _try_refresh_token(refresh_token: str, response: Response) -> str | None:
    """Attempt to refresh a Supabase session using the refresh token.

    On success, sets new access and refresh token cookies on the response
    and returns the new access token. On failure, returns None so the
    caller can fall through to normal verification with the existing token.

    Args:
        refresh_token: The Supabase refresh token from the cookie.
        response: FastAPI response object to set new cookies on.

    Returns:
        New access token string if refresh succeeded, None otherwise.
    """
    try:
        from src.api.routes.auth import set_auth_cookies  # noqa: PLC0415

        client = get_supabase()
        refresh_response = client.auth.refresh_session(refresh_token)

        if refresh_response is None or refresh_response.session is None:
            logger.debug("Token refresh returned no session")
            return None

        new_session = refresh_response.session
        new_access_token = new_session.access_token
        new_refresh_token = new_session.refresh_token

        # Set updated cookies on the response
        set_auth_cookies(
            response,
            access_token=new_access_token,
            refresh_token=new_refresh_token,
        )

        logger.debug("Successfully refreshed JWT token")
        return new_access_token

    except ValueError:
        # Supabase not configured -- should not happen since we check before
        # calling this, but handle gracefully.
        logger.debug("Token refresh skipped: Supabase not configured")
        return None
    except Exception:
        # Any refresh failure is non-fatal. The user continues with
        # their current token (which may still be valid, or will fail
        # at the normal verification step).
        logger.debug("Token refresh failed", exc_info=True)
        return None


def _verify_token_via_supabase(token: str) -> AuthenticatedUser:
    """Verify a JWT token server-side via Supabase auth.get_user().

    This is the secure verification path used in production. The token
    signature is validated by Supabase's auth service, and user data
    is returned from Supabase (the source of truth).

    Args:
        token: Raw JWT access token string.

    Returns:
        AuthenticatedUser with verified id and email from Supabase.

    Raises:
        HTTPException: 401 if token is invalid, expired, or Supabase
            returns a null user.
        ValueError: If Supabase is not configured (propagated from get_supabase).
    """
    try:
        client = get_supabase()
        response = client.auth.get_user(token)
    except ValueError:
        raise
    except (httpx.HTTPError, AuthApiError) as e:
        logger.warning("Supabase token verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    if response is None or response.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(
        id=response.user.id,
        email=response.user.email or "",
    )


def _decode_token_unverified(token: str) -> AuthenticatedUser:
    """Decode a JWT token WITHOUT signature verification.

    WARNING: This path is for local development only. It does NOT verify
    the token signature, meaning forged tokens will be accepted.

    Args:
        token: Raw JWT access token string.

    Returns:
        AuthenticatedUser with claims extracted from unverified JWT.

    Raises:
        HTTPException: 401 if token is malformed, expired, or missing 'sub'.
    """
    try:
        payload = pyjwt.decode(
            token,
            options={"verify_signature": False},
            algorithms=["HS256"],
        )

        user_id = payload.get("sub")
        email = payload.get("email", "")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check expiration
        exp = payload.get("exp")
        if exp and time.time() > exp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return AuthenticatedUser(id=user_id, email=email)

    except pyjwt.PyJWTError as e:
        logger.warning("JWT decode failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user(request: Request, response: Response) -> AuthenticatedUser:
    """FastAPI dependency to get the current authenticated user.

    Extracts the JWT token from the request and verifies it:
    - If Supabase is configured: verifies server-side via auth.get_user()
    - If Supabase is NOT configured (local dev): falls back to unverified
      decode with a WARNING log.

    Token refresh: When Supabase is configured and the access token is
    within 5 minutes of expiry, attempts to refresh using the refresh
    token cookie. If refresh succeeds, the new tokens are set as cookies
    on the response. If refresh fails, the original token is used.

    Args:
        request: FastAPI request object.
        response: FastAPI response object (for setting refreshed cookies).

    Returns:
        AuthenticatedUser with id and email.

    Raises:
        HTTPException: 401 if token is missing, invalid, or expired.
    """
    token = _get_token_from_request(request)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()

    if settings.supabase_configured:
        # Attempt proactive token refresh if close to expiry
        if _is_token_expiring_soon(token):
            refresh_token = _get_refresh_token_from_request(request)
            if refresh_token:
                new_token = _try_refresh_token(refresh_token, response)
                if new_token:
                    token = new_token

        # Production path: verify token server-side via Supabase
        return _verify_token_via_supabase(token)

    # Unverified JWT decode — only allowed when explicitly opted in
    if not settings.ALLOW_UNVERIFIED_JWT:
        logger.error(
            "Supabase is not configured and ALLOW_UNVERIFIED_JWT is not enabled. "
            "Set ALLOW_UNVERIFIED_JWT=true for local dev or configure Supabase."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication service is not configured",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.warning(
        "SECURITY WARNING: JWT signature verification is DISABLED "
        "(ALLOW_UNVERIFIED_JWT=true). Do NOT use this in production."
    )
    return _decode_token_unverified(token)


async def get_current_user_optional(
    request: Request, response: Response
) -> AuthenticatedUser | None:
    """FastAPI dependency to optionally get the current user.

    Returns None only when no token is present (true guest). If a token IS
    present but invalid/expired, attempts a refresh via the refresh token
    cookie before giving up with a 401.

    Args:
        request: FastAPI request object.
        response: FastAPI response object (for setting refreshed cookies).

    Returns:
        AuthenticatedUser if authenticated, None if no token present.

    Raises:
        HTTPException: 401 if token is invalid and refresh fails.
    """
    token = _get_token_from_request(request)
    if not token:
        return None
    try:
        return await get_current_user(request, response)
    except HTTPException:
        # Token is invalid/expired — attempt refresh before giving up
        refresh_token = _get_refresh_token_from_request(request)
        if refresh_token:
            new_token = _try_refresh_token(refresh_token, response)
            if new_token:
                # Retry with the refreshed token
                try:
                    return _verify_token_via_supabase(new_token)
                except (HTTPException, AuthApiError):
                    pass
        raise


# Type aliases for FastAPI dependency injection
CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]
OptionalUserDep = Annotated[AuthenticatedUser | None, Depends(get_current_user_optional)]


@dataclass(frozen=True)
class EffectiveUser:
    """Represents either an authenticated user or an anonymous guest session.

    Provides a unified identity for both logged-in users (identified by
    Supabase Auth UUID) and guests (identified by a client-generated
    session UUID stored in a cookie).

    Attributes:
        id: User UUID (from Supabase Auth) or session UUID (from cookie).
        is_guest: True if the identity comes from a session cookie, not a JWT.
        email: User's email address if authenticated, None for guests.
    """

    id: str
    is_guest: bool
    email: str | None = None


async def get_effective_user(
    request: Request,
    user: OptionalUserDep,
) -> EffectiveUser | None:
    """FastAPI dependency to resolve the effective user identity.

    Checks for an authenticated JWT user first. If none is found, falls back
    to a guest session identified by the ``session_id`` cookie.

    Args:
        request: FastAPI request object.
        user: Optionally resolved authenticated user (injected by FastAPI).

    Returns:
        EffectiveUser if an identity can be determined, None otherwise.
    """
    if user is not None:
        return EffectiveUser(id=user.id, is_guest=False, email=user.email)

    session_id_raw = request.cookies.get("session_id")
    if session_id_raw:
        from src.api.cookies import unsign_session_id  # noqa: PLC0415

        session_uuid = unsign_session_id(session_id_raw)
        if session_uuid:
            return EffectiveUser(id=session_uuid, is_guest=True)
        logger.warning(
            "Rejected expired or invalid session_id cookie: %r",
            session_id_raw[:64],  # Truncate to prevent log injection
        )

    return None


def get_client_for_user(effective_user: EffectiveUser) -> SupabaseClient:
    """Return the appropriate Supabase client for the given user identity.

    Guests require the admin (service-role) client because they have no
    JWT and therefore cannot pass RLS policies with the anon client.
    Authenticated users use the standard anon client which respects RLS.

    Args:
        effective_user: The resolved effective user identity.

    Returns:
        Supabase client instance appropriate for the user type.
    """
    if effective_user.is_guest:
        return get_supabase_admin()
    return get_supabase()


EffectiveUserDep = Annotated[EffectiveUser | None, Depends(get_effective_user)]
