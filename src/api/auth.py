"""Authentication utilities for Supabase JWT validation.

Provides JWT token validation using Supabase's auth.get_user() for server-side
verification and a FastAPI dependency for extracting the current authenticated user.
Also provides EffectiveUser for unified authenticated/guest identity.

Security:
- Production: Tokens are verified server-side via Supabase auth.get_user()
- Local dev: Falls back to unverified JWT decode with a WARNING log
"""

import logging
import time
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status

from src.api.config import get_settings
from src.api.supabase_client import SupabaseClient, get_supabase, get_supabase_admin

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Represents an authenticated user extracted from JWT.

    Attributes:
        id: User's unique identifier (UUID from Supabase Auth).
        email: User's email address.
    """

    id: str
    email: str


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
    except Exception as e:
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
        payload = jwt.decode(
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

    except jwt.PyJWTError as e:
        logger.warning("JWT decode failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user(request: Request) -> AuthenticatedUser:
    """FastAPI dependency to get the current authenticated user.

    Extracts the JWT token from the request and verifies it:
    - If Supabase is configured: verifies server-side via auth.get_user()
    - If Supabase is NOT configured (local dev): falls back to unverified
      decode with a WARNING log.

    Args:
        request: FastAPI request object.

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
        # Production path: verify token server-side via Supabase
        return _verify_token_via_supabase(token)

    # Local dev fallback: unverified JWT decode
    logger.warning(
        "JWT signature verification is DISABLED (Supabase not configured). "
        "Do NOT use this in production."
    )
    return _decode_token_unverified(token)


async def get_current_user_optional(request: Request) -> AuthenticatedUser | None:
    """FastAPI dependency to optionally get the current user.

    Unlike get_current_user, this does not raise an exception if no user
    is authenticated. Useful for routes that work both with and without auth.

    Args:
        request: FastAPI request object.

    Returns:
        AuthenticatedUser if authenticated, None otherwise.
    """
    try:
        return await get_current_user(request)
    except HTTPException:
        return None


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

    session_id = request.cookies.get("session_id")
    if session_id:
        return EffectiveUser(id=session_id, is_guest=True)

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
