"""Tests for FernetCipher (LangGraph checkpoint encryption)."""

from unittest.mock import patch

import pytest

from src.db.encryption import FernetCipher, clear_encryption_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure a fresh Fernet instance for every test."""
    clear_encryption_cache()
    yield
    clear_encryption_cache()


@pytest.fixture(autouse=True)
def _mock_settings():
    """Provide deterministic settings for all cipher tests."""
    mock_settings = type(
        "FakeSettings",
        (),
        {"SECRET_KEY": "test-secret-key-for-cipher", "ENCRYPTION_SALT": "test-salt-cipher"},
    )()
    with patch("src.db.encryption.get_settings", return_value=mock_settings):
        yield


class TestFernetCipherEncryptDecrypt:
    """Core encrypt/decrypt round-trip for checkpoint blobs."""

    def test_round_trip_bytes(self) -> None:
        """Encrypted bytes should decrypt back to original."""
        cipher = FernetCipher()
        plaintext = b'{"messages": [{"role": "user", "content": "hola"}]}'
        name, ciphertext = cipher.encrypt(plaintext)
        assert cipher.decrypt(name, ciphertext) == plaintext

    def test_cipher_name_is_fernet(self) -> None:
        """Encrypt should return 'fernet' as the cipher name."""
        cipher = FernetCipher()
        name, _ = cipher.encrypt(b"test")
        assert name == "fernet"

    def test_ciphertext_differs_from_plaintext(self) -> None:
        """Ciphertext must not be the same as plaintext."""
        cipher = FernetCipher()
        plaintext = b"sensitive user message"
        _, ciphertext = cipher.encrypt(plaintext)
        assert ciphertext != plaintext

    def test_empty_bytes(self) -> None:
        """Empty byte string should round-trip."""
        cipher = FernetCipher()
        name, ciphertext = cipher.encrypt(b"")
        assert cipher.decrypt(name, ciphertext) == b""

    def test_large_payload(self) -> None:
        """Large checkpoint blobs should round-trip."""
        cipher = FernetCipher()
        plaintext = b"x" * 100_000
        name, ciphertext = cipher.encrypt(plaintext)
        assert cipher.decrypt(name, ciphertext) == plaintext


class TestFernetCipherErrors:
    """Error handling for invalid inputs."""

    def test_wrong_cipher_name_raises(self) -> None:
        """Decrypt with wrong cipher name should raise ValueError."""
        cipher = FernetCipher()
        _, ciphertext = cipher.encrypt(b"test")
        with pytest.raises(ValueError, match="Unknown cipher"):
            cipher.decrypt("aes-256", ciphertext)

    def test_tampered_ciphertext_raises(self) -> None:
        """Tampered ciphertext should raise InvalidToken."""
        from cryptography.fernet import InvalidToken

        cipher = FernetCipher()
        name, ciphertext = cipher.encrypt(b"test")
        tampered = ciphertext[:-1] + (b"X" if ciphertext[-1:] != b"X" else b"Y")
        with pytest.raises(InvalidToken):
            cipher.decrypt(name, tampered)


class TestEncryptedSerializerIntegration:
    """Integration with LangGraph's EncryptedSerializer."""

    def test_serde_round_trip(self) -> None:
        """EncryptedSerializer should encrypt and decrypt checkpoint state."""
        from langgraph.checkpoint.serde.encrypted import EncryptedSerializer

        serde = EncryptedSerializer(cipher=FernetCipher())
        state = {"messages": [{"role": "user", "content": "hola amigo"}]}
        typ, data = serde.dumps_typed(state)
        assert "+fernet" in typ
        assert serde.loads_typed((typ, data)) == state

    def test_serde_type_field_format(self) -> None:
        """Type field should be 'originaltype+fernet'."""
        from langgraph.checkpoint.serde.encrypted import EncryptedSerializer

        serde = EncryptedSerializer(cipher=FernetCipher())
        typ, _ = serde.dumps_typed({"key": "value"})
        parts = typ.split("+")
        assert len(parts) == 2
        assert parts[1] == "fernet"

    def test_backward_compat_unencrypted(self) -> None:
        """Unencrypted checkpoints (no +cipher suffix) should still deserialize."""
        from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

        plain_serde = JsonPlusSerializer()
        encrypted_serde = EncryptedSerializer(cipher=FernetCipher())

        state = {"messages": [{"role": "assistant", "content": "Buenos dias!"}]}
        typ, data = plain_serde.dumps_typed(state)
        assert "+" not in typ

        # Encrypted serde should read unencrypted data transparently
        result = encrypted_serde.loads_typed((typ, data))
        assert result == state
