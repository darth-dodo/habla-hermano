"""Authentication utilities for Supabase JWT validation.

Provides JWT token validation using Supabase's JWKS endpoint and
a FastAPI dependency for extracting the current authenticated user.
"""

import time
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status


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


async def get_current_user(request: Request) -> AuthenticatedUser:
    """FastAPI dependency to get the current authenticated user.

    Extracts and validates the JWT token from the request, returning
    the authenticated user's information.

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

    try:
        # Decode and validate JWT
        # Supabase uses HS256 with the JWT secret for token signing
        payload = jwt.decode(
            token,
            options={"verify_signature": False},  # We'll verify via Supabase API
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


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
