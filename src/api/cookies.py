"""Centralized cookie utility with enforced security defaults and signing.

All cookie operations should go through this module to ensure consistent
security attributes across the application. The ``secure`` flag adapts to
the environment: enforced in production, relaxed in DEBUG mode so that
local development over plain HTTP continues to work.

Security properties enforced by default:
- secure: True in production (HTTPS only), False in DEBUG
- httponly: True (prevents JavaScript access / XSS)
- samesite: "lax" (CSRF protection with normal navigation)

Cookie signing (itsdangerous) is used for tamper-proof session cookies
(e.g. review sessions) so clients cannot forge word IDs, scores, or progress.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

from itsdangerous import BadSignature, URLSafeTimedSerializer

from src.api.config import get_settings

if TYPE_CHECKING:
    from fastapi import Response

logger = logging.getLogger(__name__)

SameSitePolicy = Literal["lax", "strict", "none"]


# ---------------------------------------------------------------------------
# Environment-aware cookie helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Cookie signing (itsdangerous)
# ---------------------------------------------------------------------------


def _get_serializer() -> URLSafeTimedSerializer:
    """Return a URLSafeTimedSerializer using the app SECRET_KEY."""
    settings = get_settings()
    return URLSafeTimedSerializer(settings.SECRET_KEY, salt="habla-cookie")


def sign_cookie_value(data: dict[str, Any]) -> str:
    """Serialize and sign a dictionary as a tamper-proof cookie value.

    Args:
        data: Dictionary to serialize. Must be JSON-serializable.

    Returns:
        Signed string safe for use as a cookie value.
    """
    serializer = _get_serializer()
    return serializer.dumps(data)  # type: ignore[no-any-return]


def sign_session_id(session_uuid: str) -> str:
    """Sign a guest session UUID for tamper-proof, time-limited storage.

    Embeds a timestamp so the server can enforce max_age server-side,
    independent of the browser's cookie expiry (Finding H5).

    Args:
        session_uuid: A UUID v4 string to embed in the signed token.

    Returns:
        Signed token safe for use as a ``session_id`` cookie value.
    """
    serializer = URLSafeTimedSerializer(get_settings().SECRET_KEY, salt="habla-session")
    return serializer.dumps({"id": session_uuid})  # type: ignore[no-any-return]


def unsign_session_id(
    raw_value: str | None,
    max_age_seconds: int = 7 * 24 * 3600,
) -> str | None:
    """Verify a signed session_id and return the embedded UUID, or None.

    Accepts both:
    - Signed tokens produced by :func:`sign_session_id` (new format).
    - Plain UUID v4 strings (old cookies set before signing was introduced,
      backward-compatibility requirement).

    Args:
        raw_value: Raw cookie string, or None if the cookie is absent.
        max_age_seconds: Maximum token age in seconds. Tokens older than
            this are rejected. Defaults to 7 days.

    Returns:
        The UUID string on success, None if missing / expired / invalid.
    """
    if not raw_value:
        return None

    # Try signed format first
    serializer = URLSafeTimedSerializer(get_settings().SECRET_KEY, salt="habla-session")
    try:
        data: Any = serializer.loads(raw_value, max_age=max_age_seconds)
        if isinstance(data, dict) and isinstance(data.get("id"), str):
            return str(data["id"])
        return None
    except BadSignature:
        pass  # Fall through to backward-compat check

    # Backward compat: accept plain UUID v4 (existing cookies)
    import uuid as _uuid  # noqa: PLC0415

    try:
        parsed = _uuid.UUID(raw_value, version=4)
        if str(parsed) == raw_value:
            return raw_value
    except (ValueError, AttributeError):
        pass

    logger.warning("Rejected session_id cookie: not a valid signed token or UUID v4")
    return None


def unsign_json_cookie(raw_value: str | None, max_age: int | None = None) -> dict[str, Any] | None:
    """Verify and deserialize a signed JSON cookie, or return None.

    Handles the common pattern where the raw cookie value may be None
    (cookie absent) or may have an invalid signature (tampered).

    Args:
        raw_value: Raw cookie string, or None if cookie was absent.
        max_age: Maximum signature age in seconds (None = no limit).

    Returns:
        Parsed dict on success, None on missing/invalid/tampered cookie.
    """
    if not raw_value:
        return None
    serializer = _get_serializer()
    try:
        data: Any = serializer.loads(raw_value, max_age=max_age)
    except BadSignature:
        logger.warning("Invalid cookie signature detected — treating as empty session")
        return None
    if not isinstance(data, dict):
        logger.warning("Signed cookie payload is not a dict — treating as empty session")
        return None
    return data  # type: ignore[no-any-return]
