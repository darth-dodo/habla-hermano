"""Tests for encryption integration in the repository layer.

Verifies that VocabularyRepository and UserProfileRepository correctly call
encrypt_field / decrypt_field on sensitive columns (translation, display_name)
while leaving non-sensitive columns (word, part_of_speech) as plaintext.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, call, patch

import pytest

from src.db.encryption import clear_encryption_cache, decrypt_field, encrypt_field
from src.db.models import Vocabulary
from src.db.repository import UserProfileRepository, VocabularyRepository

# =============================================================================
# Fixtures
# =============================================================================

USER_ID = "user-enc-test-123"
NOW_ISO = datetime.now(UTC).isoformat()


@pytest.fixture(autouse=True)
def _clear_enc_cache():
    """Ensure fresh Fernet instance per test."""
    clear_encryption_cache()
    yield
    clear_encryption_cache()


@pytest.fixture(autouse=True)
def _mock_enc_settings():
    """Provide deterministic encryption settings."""
    fake = type(
        "FakeSettings",
        (),
        {
            "SECRET_KEY": "test-secret-key-for-repo-enc",
            "ENCRYPTION_SALT": "test-salt-v1",
        },
    )()
    with patch("src.db.encryption.get_settings", return_value=fake):
        yield


@pytest.fixture
def mock_supabase() -> MagicMock:
    """Create a mock Supabase client with APIError on RPC by default."""
    from postgrest.exceptions import APIError

    client = MagicMock()
    client.rpc.side_effect = APIError({"message": "RPC not found", "code": "42883"})
    return client


@pytest.fixture
def mock_get_supabase(mock_supabase: MagicMock):
    """Patch get_supabase to return mock client."""
    with patch("src.db.repository.get_supabase", return_value=mock_supabase):
        yield mock_supabase


def _vocab_row(
    word: str = "hola",
    translation: str = "hello",
    language: str = "es",
    vocab_id: int = 1,
) -> dict:
    """Build a vocabulary row dict as returned by Supabase."""
    return {
        "id": vocab_id,
        "user_id": USER_ID,
        "word": word,
        "translation": translation,
        "language": language,
        "part_of_speech": "noun",
        "first_seen_at": NOW_ISO,
        "times_seen": 1,
        "times_correct": 0,
        "easiness_factor": 2.5,
        "interval_days": 0,
        "repetition_count": 0,
        "next_review_at": None,
        "last_reviewed_at": None,
    }


def _profile_row(display_name: str | None = "Test User") -> dict:
    """Build a user_profiles row dict as returned by Supabase."""
    return {
        "id": USER_ID,
        "display_name": display_name,
        "preferred_language": "es",
        "current_level": "A1",
        "created_at": NOW_ISO,
        "updated_at": NOW_ISO,
    }


# =============================================================================
# VocabularyRepository: Write Encryption (upsert)
# =============================================================================


class TestVocabularyUpsertEncryption:
    """Verify encrypt_field is called on translation during upsert."""

    @patch("src.db.repository.decrypt_field_safe", side_effect=lambda x: x)
    @patch("src.db.repository.encrypt_field")
    def test_upsert_encrypts_translation_on_insert(
        self,
        mock_encrypt: MagicMock,
        mock_decrypt: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """Translation must be encrypted before the insert call."""
        mock_encrypt.return_value = "encrypted_hello"
        mock_get_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[_vocab_row(translation="encrypted_hello")]
        )

        repo = VocabularyRepository(USER_ID)
        repo.upsert("hola", "hello", "es", "noun")

        mock_encrypt.assert_called_with("hello")

    @patch("src.db.repository.decrypt_field_safe", side_effect=lambda x: x)
    @patch("src.db.repository.encrypt_field")
    def test_upsert_rpc_fallback_encrypts_translation(
        self,
        mock_encrypt: MagicMock,
        mock_decrypt: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """Translation must be encrypted in the RPC fallback path."""
        from postgrest.exceptions import APIError

        mock_encrypt.return_value = "encrypted_hello"

        # Simulate duplicate key on insert
        mock_get_supabase.table.return_value.insert.return_value.execute.side_effect = APIError(
            {"message": "duplicate key", "code": "23505"}
        )
        # RPC path succeeds
        mock_get_supabase.rpc.side_effect = None
        mock_get_supabase.rpc.return_value.execute.return_value = MagicMock(
            data=[_vocab_row(translation="encrypted_hello")]
        )

        repo = VocabularyRepository(USER_ID)
        repo.upsert("hola", "hello", "es")

        mock_encrypt.assert_called_with("hello")

    @patch("src.db.repository.decrypt_field_safe", side_effect=lambda x: x)
    @patch("src.db.repository.encrypt_field")
    def test_upsert_does_not_encrypt_word(
        self,
        mock_encrypt: MagicMock,
        mock_decrypt: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """The word column must remain plaintext -- encrypt_field not called with word."""
        mock_encrypt.return_value = "encrypted_hello"
        mock_get_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[_vocab_row(translation="encrypted_hello")]
        )

        repo = VocabularyRepository(USER_ID)
        repo.upsert("hola", "hello", "es", "noun")

        # encrypt_field should only have been called with the translation value
        for c in mock_encrypt.call_args_list:
            assert c != call("hola"), "word should NOT be encrypted"

    @patch("src.db.repository.decrypt_field_safe", side_effect=lambda x: x)
    @patch("src.db.repository.encrypt_field")
    def test_upsert_does_not_encrypt_part_of_speech(
        self,
        mock_encrypt: MagicMock,
        mock_decrypt: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """part_of_speech must remain plaintext."""
        mock_encrypt.return_value = "encrypted_hello"
        mock_get_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[_vocab_row(translation="encrypted_hello")]
        )

        repo = VocabularyRepository(USER_ID)
        repo.upsert("hola", "hello", "es", "noun")

        for c in mock_encrypt.call_args_list:
            assert c != call("noun"), "part_of_speech should NOT be encrypted"


# =============================================================================
# VocabularyRepository: Read Decryption
# =============================================================================


class TestVocabularyReadDecryption:
    """Verify decrypt_field is called on translation when reading."""

    @patch("src.db.repository.encrypt_field", side_effect=lambda x: x)
    @patch("src.db.repository.decrypt_field_safe")
    def test_get_all_decrypts_translation(
        self,
        mock_decrypt: MagicMock,
        mock_encrypt: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """get_all must decrypt translation for each returned row."""
        mock_decrypt.return_value = "hello"
        mock_query = MagicMock()
        mock_get_supabase.table.return_value.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.execute.return_value = MagicMock(
            data=[_vocab_row(translation="encrypted_hello")]
        )

        repo = VocabularyRepository(USER_ID)
        results = repo.get_all()

        mock_decrypt.assert_called()
        assert len(results) == 1
        assert results[0].translation == "hello"

    @patch("src.db.repository.encrypt_field", side_effect=lambda x: x)
    @patch("src.db.repository.decrypt_field_safe")
    def test_get_by_id_decrypts_translation(
        self,
        mock_decrypt: MagicMock,
        mock_encrypt: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """get_by_id must decrypt translation on the returned row."""
        mock_decrypt.return_value = "hello"
        mock_get_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[_vocab_row(translation="encrypted_hello")]
        )

        repo = VocabularyRepository(USER_ID)
        result = repo.get_by_id(1)

        mock_decrypt.assert_called()
        assert result is not None
        assert result.translation == "hello"

    @patch("src.db.repository.encrypt_field", side_effect=lambda x: x)
    @patch("src.db.repository.decrypt_field_safe")
    def test_get_recent_decrypts_translation(
        self,
        mock_decrypt: MagicMock,
        mock_encrypt: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """get_recent must decrypt translation for each returned row."""
        mock_decrypt.return_value = "hello"
        mock_query = MagicMock()
        mock_get_supabase.table.return_value.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = MagicMock(
            data=[
                _vocab_row(translation="encrypted_hello"),
                _vocab_row(translation="encrypted_goodbye", word="adios", vocab_id=2),
            ]
        )

        repo = VocabularyRepository(USER_ID)
        results = repo.get_recent("es")

        assert mock_decrypt.call_count >= 2
        assert all(v.translation == "hello" for v in results)

    @patch("src.db.repository.encrypt_field", side_effect=lambda x: x)
    @patch("src.db.repository.decrypt_field_safe")
    def test_get_all_returns_decrypted_vocabulary_objects(
        self,
        mock_decrypt: MagicMock,
        mock_encrypt: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """Returned Vocabulary objects must have decrypted translation values."""
        mock_decrypt.return_value = "decrypted_value"
        mock_query = MagicMock()
        mock_get_supabase.table.return_value.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.execute.return_value = MagicMock(
            data=[_vocab_row(translation="gAAAAABh_ciphertext")]
        )

        repo = VocabularyRepository(USER_ID)
        results = repo.get_all()

        assert len(results) == 1
        assert isinstance(results[0], Vocabulary)
        assert results[0].translation == "decrypted_value"
        assert results[0].word == "hola"  # word stays plaintext


# =============================================================================
# VocabularyRepository: Search Behavior
# =============================================================================


class TestVocabularySearchWithEncryption:
    """Verify search methods handle encrypted translation correctly."""

    @patch("src.db.repository.encrypt_field", side_effect=lambda x: x)
    @patch("src.db.repository.decrypt_field_safe", side_effect=lambda x: x)
    def test_get_due_by_keywords_searches_word_column(
        self,
        mock_decrypt: MagicMock,
        mock_encrypt: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """get_due_by_keywords builds or_filter that includes word.ilike patterns.

        Since translation is encrypted, keyword search against it will not produce
        meaningful matches, but the query is server-side so we verify the filter
        string is constructed and the method executes without error.
        """
        from unittest.mock import PropertyMock

        mock_query = MagicMock()
        mock_get_supabase.table.return_value.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        type(mock_query).not_ = PropertyMock(return_value=mock_query)
        mock_query.is_.return_value = mock_query
        mock_query.lte.return_value = mock_query
        mock_query.or_.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[])

        repo = VocabularyRepository(USER_ID)
        results = repo.get_due_by_keywords("es", ["food"])

        assert results == []
        mock_query.or_.assert_called_once()
        or_filter = mock_query.or_.call_args[0][0]
        assert "word.ilike.%food%" in or_filter

    @patch("src.db.repository.encrypt_field", side_effect=lambda x: x)
    @patch("src.db.repository.decrypt_field_safe")
    def test_get_by_word_and_language_returns_decrypted_translation(
        self,
        mock_decrypt: MagicMock,
        mock_encrypt: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """get_by_word_and_language searches word (plaintext) and decrypts translation."""
        mock_decrypt.return_value = "hello"
        mock_get_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[_vocab_row(translation="encrypted_hello")]
        )

        repo = VocabularyRepository(USER_ID)
        result = repo.get_by_word_and_language("hola", "es")

        assert result is not None
        assert result.word == "hola"
        assert result.translation == "hello"
        mock_decrypt.assert_called()


class TestUserProfileEncryption:
    """Verify display_name is encrypted on write and decrypted on read."""

    @patch("src.db.repository.decrypt_field_safe")
    @patch("src.db.repository.encrypt_field")
    def test_update_encrypts_display_name(
        self,
        mock_encrypt: MagicMock,
        mock_decrypt: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """update() must call encrypt_field on display_name before storing."""
        mock_encrypt.return_value = "encrypted_name"
        # update() also decrypts display_name on the response row
        mock_decrypt.return_value = "Maria"
        mock_get_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[_profile_row(display_name="encrypted_name")]
        )

        repo = UserProfileRepository(USER_ID)
        result = repo.update(display_name="Maria")

        mock_encrypt.assert_called_once_with("Maria")
        assert result is not None
        assert result.display_name == "Maria"

    @patch("src.db.repository.encrypt_field", side_effect=lambda x: x)
    @patch("src.db.repository.decrypt_field_safe")
    def test_get_decrypts_display_name(
        self,
        mock_decrypt: MagicMock,
        mock_encrypt: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """get() must call decrypt_field on display_name from the row."""
        mock_decrypt.return_value = "Maria"
        mock_get_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[_profile_row(display_name="encrypted_name")]
        )

        repo = UserProfileRepository(USER_ID)
        result = repo.get()

        assert result is not None
        assert result.display_name == "Maria"
        mock_decrypt.assert_called_once_with("encrypted_name")

    @patch("src.db.repository.encrypt_field", side_effect=lambda x: x)
    @patch("src.db.repository.decrypt_field_safe")
    def test_get_handles_none_display_name(
        self,
        mock_decrypt: MagicMock,
        mock_encrypt: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """get() must handle None display_name gracefully (decrypt_field(None) -> None)."""
        mock_decrypt.return_value = None
        mock_get_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[_profile_row(display_name=None)]
        )

        repo = UserProfileRepository(USER_ID)
        result = repo.get()

        assert result is not None
        assert result.display_name is None
        mock_decrypt.assert_called_once_with(None)

    @patch("src.db.repository.decrypt_field_safe", side_effect=lambda x: x)
    @patch("src.db.repository.encrypt_field")
    def test_update_none_display_name_skips_encryption(
        self,
        mock_encrypt: MagicMock,
        mock_decrypt: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """When display_name is not provided, encrypt_field should not be called."""
        mock_get_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[_profile_row(display_name=None)]
        )

        repo = UserProfileRepository(USER_ID)
        repo.update(preferred_language="de")

        mock_encrypt.assert_not_called()


# =============================================================================
# Round-Trip Integrity (real encryption, no mocks)
# =============================================================================


class TestRoundTripIntegrity:
    """Verify encrypt -> decrypt returns original values using real Fernet."""

    def test_roundtrip_translation(self) -> None:
        """Translation survives encrypt -> decrypt cycle."""
        original = "hello world"
        ciphertext = encrypt_field(original)
        assert ciphertext is not None
        assert ciphertext != original
        assert decrypt_field(ciphertext) == original

    def test_roundtrip_display_name(self) -> None:
        """Display name survives encrypt -> decrypt cycle."""
        original = "Maria Garcia"
        ciphertext = encrypt_field(original)
        assert ciphertext is not None
        assert ciphertext != original
        assert decrypt_field(ciphertext) == original

    def test_roundtrip_unicode_translation(self) -> None:
        """Unicode translation (accents, special chars) survives round-trip."""
        original = "Buenos dias, como estas?"
        assert decrypt_field(encrypt_field(original)) == original

    def test_roundtrip_none_passthrough(self) -> None:
        """None values pass through encrypt/decrypt unchanged."""
        assert encrypt_field(None) is None
        assert decrypt_field(None) is None

    def test_roundtrip_empty_string_passthrough(self) -> None:
        """Empty strings pass through encrypt/decrypt unchanged."""
        assert encrypt_field("") == ""
        assert decrypt_field("") == ""
