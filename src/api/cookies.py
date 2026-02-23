"""Centralized cookie utility with enforced security defaults.

All cookie operations should go through this module to ensure consistent
security attributes across the application. The ``secure`` flag adapts to
the environment: enforced in production, relaxed in DEBUG mode so that
local development over plain HTTP continues to work.

Security properties enforced by default:
- secure: True in production (HTTPS only), False in DEBUG
- httponly: True (prevents JavaScript access / XSS)
- samesite: "lax" (CSRF protection with normal navigation)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from src.api.config import get_settings

if TYPE_CHECKING:
    from fastapi import Response

SameSitePolicy = Literal["lax", "strict", "none"]


def _is_secure() -> bool:
    """Determine whether cookies should require HTTPS.

    Returns True in production (DEBUG=False) so cookies are only
    transmitted over secure connections. Returns False in DEBUG mode
    to allow local development over plain HTTP.
    """
    return not get_settings().DEBUG


def set_secure_cookie(
    response: Response,
    key: str,
    value: str,
    *,
    max_age: int | None = None,
    httponly: bool = True,
    samesite: SameSitePolicy = "lax",
    path: str = "/",
) -> None:
    """Set a cookie with enforced security defaults.

    Wraps ``response.set_cookie`` and automatically applies the ``secure``
    flag based on the current environment.

    Args:
        response: FastAPI/Starlette response object.
        key: Cookie name.
        value: Cookie value.
        max_age: Max age in seconds. None creates a session cookie.
        httponly: If True the cookie is inaccessible to JavaScript.
        samesite: SameSite attribute ("lax", "strict", or "none").
        path: URL path scope for the cookie.
    """
    response.set_cookie(
        key=key,
        value=value,
        max_age=max_age,
        httponly=httponly,
        secure=_is_secure(),
        samesite=samesite,
        path=path,
    )


def delete_secure_cookie(
    response: Response,
    key: str,
    *,
    path: str = "/",
    samesite: SameSitePolicy = "lax",
) -> None:
    """Delete a cookie with matching path/samesite attributes.

    Args:
        response: FastAPI/Starlette response object.
        key: Cookie name to delete.
        path: Must match the path used when the cookie was set.
        samesite: Must match the samesite used when the cookie was set.
    """
    response.delete_cookie(
        key=key,
        path=path,
        samesite=samesite,
        secure=_is_secure(),
    )
