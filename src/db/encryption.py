"""Application-level encryption for sensitive data fields.

Provides symmetric encryption (Fernet) for data at rest. The encryption key
is derived from the application ``SECRET_KEY`` via PBKDF2, so no separate
encryption key is required.

Encrypted values are URL-safe base64-encoded strings, safe for storage in
standard text / varchar columns.
"""

import base64
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from src.config import get_settings


def _derive_key(secret: str, salt: str) -> bytes:
    """Derive a 32-byte Fernet key from *secret* and *salt* using PBKDF2.

    Args:
        secret: Application secret key.
        salt: Static salt string for key derivation.

    Returns:
        URL-safe base64-encoded 32-byte key suitable for Fernet.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt.encode("utf-8"),
        iterations=480_000,
    )
    raw_key = kdf.derive(secret.encode("utf-8"))
    return base64.urlsafe_b64encode(raw_key)


@lru_cache
def _get_fernet() -> Fernet:
    """Return a cached Fernet instance keyed from application settings.

    The key is derived deterministically from ``SECRET_KEY`` and
    ``ENCRYPTION_SALT`` so restarts with the same configuration can
    decrypt previously encrypted data.

    Returns:
        Configured Fernet instance.
    """
    settings = get_settings()
    key = _derive_key(settings.SECRET_KEY, settings.ENCRYPTION_SALT)
    return Fernet(key)


def encrypt_field(plaintext: str | None) -> str | None:
    """Encrypt a plaintext string for storage.

    Args:
        plaintext: The value to encrypt. ``None`` and empty strings are
            returned unchanged.

    Returns:
        URL-safe base64-encoded ciphertext, or the original value when
        *plaintext* is ``None`` or empty.
    """
    if plaintext is None or plaintext == "":
        return plaintext

    fernet = _get_fernet()
    token = fernet.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_field(ciphertext: str | None) -> str | None:
    """Decrypt a previously encrypted field value.

    Args:
        ciphertext: The encrypted value. ``None`` and empty strings are
            returned unchanged.

    Returns:
        Original plaintext string.

    Raises:
        cryptography.fernet.InvalidToken: If *ciphertext* is not a valid
            Fernet token (wrong key, corrupted data, or tampered).
    """
    if ciphertext is None or ciphertext == "":
        return ciphertext

    fernet = _get_fernet()
    return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def clear_encryption_cache() -> None:
    """Clear the cached Fernet instance.

    Useful for testing or when settings change.
    """
    _get_fernet.cache_clear()
