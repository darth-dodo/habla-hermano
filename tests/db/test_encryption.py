"""Tests for the application-level encryption module."""

from unittest.mock import patch

import pytest
from cryptography.fernet import InvalidToken

from src.db.encryption import (
    _derive_key,
    clear_encryption_cache,
    decrypt_field,
    encrypt_field,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure a fresh Fernet instance for every test."""
    clear_encryption_cache()
    yield
    clear_encryption_cache()


@pytest.fixture(autouse=True)
def _mock_settings():
    """Provide deterministic settings for all encryption tests."""
    mock_settings = type(
        "FakeSettings",
        (),
        {
            "SECRET_KEY": "test-secret-key-for-encryption",
            "ENCRYPTION_SALT": "test-salt-v1",
        },
    )()
    with patch("src.db.encryption.get_settings", return_value=mock_settings):
        yield


class TestEncryptDecryptRoundTrip:
    """Verify encrypt -> decrypt produces the original plaintext."""

    def test_simple_string(self):
        plaintext = "Hola, mundo!"
        ciphertext = encrypt_field(plaintext)
        assert decrypt_field(ciphertext) == plaintext

    def test_unicode_content(self):
        plaintext = "Les fraises sont rouges."
        ciphertext = encrypt_field(plaintext)
        assert decrypt_field(ciphertext) == plaintext

    def test_long_string(self):
        plaintext = "a" * 10_000
        ciphertext = encrypt_field(plaintext)
        assert decrypt_field(ciphertext) == plaintext

    def test_special_characters(self):
        plaintext = 'key=value&foo="bar"<script>alert(1)</script>'
        ciphertext = encrypt_field(plaintext)
        assert decrypt_field(ciphertext) == plaintext


class TestEdgeCases:
    """Edge-case handling for None and empty values."""

    def test_none_returns_none(self):
        assert encrypt_field(None) is None
        assert decrypt_field(None) is None

    def test_empty_string_returns_empty(self):
        assert encrypt_field("") == ""
        assert decrypt_field("") == ""


class TestCiphertextProperties:
    """Properties that the ciphertext must satisfy."""

    def test_ciphertext_differs_from_plaintext(self):
        plaintext = "secret message"
        ciphertext = encrypt_field(plaintext)
        assert ciphertext != plaintext

    def test_different_plaintexts_produce_different_ciphertexts(self):
        ct_a = encrypt_field("alpha")
        ct_b = encrypt_field("beta")
        assert ct_a != ct_b

    def test_same_plaintext_produces_different_tokens(self):
        """Fernet tokens include a timestamp and random IV, so two
        encryptions of the same value should differ."""
        ct_a = encrypt_field("same")
        ct_b = encrypt_field("same")
        assert ct_a != ct_b

    def test_ciphertext_is_ascii_safe(self):
        ciphertext = encrypt_field("some data")
        assert ciphertext is not None
        assert ciphertext.isascii()


class TestInvalidCiphertext:
    """Decryption of tampered or invalid data must raise."""

    def test_garbage_string_raises(self):
        with pytest.raises(InvalidToken):
            decrypt_field("not-a-valid-fernet-token")

    def test_truncated_token_raises(self):
        ciphertext = encrypt_field("hello")
        assert ciphertext is not None
        with pytest.raises(InvalidToken):
            decrypt_field(ciphertext[:10])

    def test_tampered_token_raises(self):
        ciphertext = encrypt_field("hello")
        assert ciphertext is not None
        tampered = ciphertext[:-4] + "XXXX"
        with pytest.raises(InvalidToken):
            decrypt_field(tampered)


class TestKeyDerivation:
    """Key derivation must be deterministic and salt-sensitive."""

    def test_deterministic(self):
        key_a = _derive_key("secret", "salt")
        key_b = _derive_key("secret", "salt")
        assert key_a == key_b

    def test_different_secret_different_key(self):
        key_a = _derive_key("secret-1", "salt")
        key_b = _derive_key("secret-2", "salt")
        assert key_a != key_b

    def test_different_salt_different_key(self):
        key_a = _derive_key("secret", "salt-1")
        key_b = _derive_key("secret", "salt-2")
        assert key_a != key_b

    def test_wrong_key_cannot_decrypt(self):
        """Data encrypted with one secret cannot be decrypted after
        the cached Fernet is rebuilt with a different secret."""
        ciphertext = encrypt_field("classified")

        # Rebuild with a different secret
        clear_encryption_cache()
        other_settings = type(
            "FakeSettings",
            (),
            {
                "SECRET_KEY": "completely-different-secret",
                "ENCRYPTION_SALT": "test-salt-v1",
            },
        )()
        with patch("src.db.encryption.get_settings", return_value=other_settings):
            with pytest.raises(InvalidToken):
                decrypt_field(ciphertext)
