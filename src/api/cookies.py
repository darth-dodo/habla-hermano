"""Cookie signing utilities for tamper-proof session cookies.

Uses itsdangerous URLSafeTimedSerializer to sign cookie values so that
clients cannot forge or modify session data (e.g. review scores, word IDs).

If the signature is invalid or the payload has been tampered with,
unsign() returns None so callers can treat it as "no session".
"""

import json
import logging
from typing import Any

from itsdangerous import BadSignature, URLSafeTimedSerializer

from src.api.config import get_settings

logger = logging.getLogger(__name__)


def _get_serializer() -> URLSafeTimedSerializer:
    """Return a URLSafeTimedSerializer using the app SECRET_KEY.

    Returns:
        Configured serializer instance.
    """
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


def unsign_cookie_value(signed_value: str, max_age: int | None = None) -> dict[str, Any] | None:
    """Verify the signature and deserialize a signed cookie value.

    Args:
        signed_value: The signed cookie string to verify.
        max_age: Maximum age in seconds. If the signature is older
                 than this, it is treated as invalid. None means no
                 expiry check on the signature itself.

    Returns:
        The original dictionary if the signature is valid, or None
        if the signature is invalid / expired / tampered with.
    """
    serializer = _get_serializer()
    try:
        data: Any = serializer.loads(signed_value, max_age=max_age)
    except BadSignature:
        logger.warning("Invalid cookie signature detected — treating as empty session")
        return None

    if not isinstance(data, dict):
        logger.warning("Signed cookie payload is not a dict — treating as empty session")
        return None

    return data  # type: ignore[no-any-return]


def sign_json_cookie(data: dict[str, Any]) -> str:
    """Sign a dict for use as a cookie value (convenience alias).

    This is equivalent to sign_cookie_value but named for clarity at call sites
    that previously used json.dumps().

    Args:
        data: Dictionary to sign.

    Returns:
        Signed cookie string.
    """
    return sign_cookie_value(data)


def unsign_json_cookie(
    raw_value: str | None, max_age: int | None = None
) -> dict[str, Any] | None:
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
    return unsign_cookie_value(raw_value, max_age=max_age)
