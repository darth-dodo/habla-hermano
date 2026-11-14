# Phase 24: Message Encryption & Data Privacy

**Date**: 2026-03-13
**Branch**: `feature/message-encryption`
**Status**: Complete

## Problem

User conversations with the AI tutor contain personal learning data (messages, vocabulary, exercise answers). While HTTPS protects data in transit, there is no protection for:
- Data at rest in Supabase (database breach exposure)
- Chat history stored in LangGraph checkpoint blobs (messages in plaintext)
- LLM provider data retention (Anthropic may store request/response pairs)
- Unbounded checkpoint growth (stale conversation state accumulates)
- No automatic conversation lifecycle management
- No row-level access control on checkpoint tables

## Goals

- Encrypt sensitive fields before storage (application-level encryption at rest)
- Encrypt LangGraph checkpoint blobs containing chat messages
- Request Anthropic zero-retention via API headers
- Auto-purge stale LangGraph checkpoints
- Provide configurable conversation data retention
- Add row-level security to checkpoint tables

## Constraints

True end-to-end encryption is not possible when the LLM is a conversation participant -- the server must read plaintext to generate responses. This design focuses on practical protections within that constraint.

## Architecture

### Layer 1: Encryption at Rest (Field-Level)

**Module**: `src/db/encryption.py`

```
User data (plaintext)
    |
encrypt_field()  ->  Fernet(PBKDF2(SECRET_KEY, ENCRYPTION_SALT))
    |
Base64 ciphertext  ->  Supabase text column
    |
decrypt_field()  ->  Plaintext (on read)
```

**Key derivation**: PBKDF2-HMAC-SHA256 with 480,000 iterations. The encryption key is derived deterministically from `SECRET_KEY` + `ENCRYPTION_SALT`, so no additional key management is required. Changing either value invalidates all previously encrypted data.

**Encrypted fields**:
| Table | Field | Reason |
|-------|-------|--------|
| `vocabulary` | `translation` | Contains user-facing translated content |
| `user_profiles` | `display_name` | Personally identifiable information |

**Plaintext fields** (intentionally not encrypted):
| Table | Field | Reason |
|-------|-------|--------|
| `vocabulary` | `word` | Needed for server-side `ilike` search |
| `vocabulary` | `part_of_speech` | Needed for filtering queries |

**Repository integration**: Encryption and decryption are wired into `src/db/repository.py` at the repository boundary. All vocabulary write methods encrypt `translation` before storage, and all read methods decrypt via the `_decrypt_vocabulary_fields()` helper. The `get_due_by_keywords()` method searches only the `word` column because `translation` is encrypted and cannot support `ilike` queries.

### Layer 2: Checkpoint Encryption

**Module**: `src/agent/checkpointer.py` (modified)

LangGraph checkpoint blobs contain the full conversation state, including all user and assistant messages. These are encrypted using LangGraph's built-in `EncryptedSerializer` with a custom `FernetCipher` class.

```
Checkpoint state (Python objects)
    |
msgpack.packb()  ->  Binary blob
    |
FernetCipher.encrypt()  ->  Fernet(PBKDF2(SECRET_KEY, ENCRYPTION_SALT))
    |
Encrypted blob  ->  checkpoint_blobs table
    |
Type field: "msgpack+fernet"
```

**FernetCipher** (defined in `src/db/encryption.py`) implements LangGraph's `CipherProtocol` interface with `encrypt()`/`decrypt()` methods. It uses the same PBKDF2-derived key as field-level encryption.

**Backward compatibility**: The type field changes from `msgpack` to `msgpack+fernet`. Unencrypted checkpoints from before this change remain readable.

**Scope**: Wired into both `init_checkpointer()` (primary PostgresSaver path) and the `get_postgres_checkpointer()` fallback. Affects all three checkpoint tables: `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`.

### Layer 3: Anthropic Zero-Retention

**Module**: `src/agent/llm.py` (modified)

When `ANTHROPIC_ZERO_RETENTION=True`, all `ChatAnthropic` instances include:
```
default_headers: {"x-no-store": "true"}
```

This requests Anthropic to not retain or log input/output for the API call. The header is added at the LLM factory level so all profiles (default, analysis, structured, creative, enhancement) inherit it.

### Layer 4: Checkpoint TTL Purging

**Module**: `src/agent/checkpoint_purge.py`

LangGraph stores conversation checkpoints in three Postgres tables (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`). Without cleanup, these grow unboundedly.

On application startup (after `init_checkpointer()`), old checkpoints are purged:
```sql
DELETE FROM {table} WHERE thread_ts < NOW() - INTERVAL '{N} days'
```

**SQL safety**: Uses `psycopg.sql.SQL` with `Identifier` for table names -- no string interpolation, no SQL injection risk.

**Failure safety**: Purge errors are caught and logged -- they never block app startup. When running in MemorySaver mode (dev), purge is a no-op.

### Layer 5: Conversation Data Retention

**Module**: `src/services/data_retention.py`

Provides `purge_old_conversations()` for cleaning up old learning sessions and vocabulary items. Designed to be called from a scheduled task or admin endpoint.

Deletes:
- `learning_sessions` where `started_at < cutoff`
- `vocabulary` where both `last_reviewed_at` AND `next_review_at < cutoff`

### Layer 6: Checkpoint Table RLS

**Migration**: `migrations/004_checkpoint_rls.sql`

Adds row-level security to all four LangGraph checkpoint tables as defense-in-depth. This protects against scenarios where a compromised client connection attempts to read another user's checkpoints.

**Implementation**:
- `checkpoint_owner()` SQL function extracts the user UUID from the `thread_id` column
- User policy: `checkpoint_owner(thread_id) = auth.uid()`
- Service role gets unrestricted access (needed for guest sessions and admin operations)

**Note**: The application connects as the `postgres` superuser, which bypasses RLS. This layer is defense-in-depth for any future scenario where direct Supabase client connections are used.

## Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `SECRET_KEY` | (existing) | Source key for PBKDF2 derivation |
| `ENCRYPTION_SALT` | `habla-hermano-encryption-v1` | Static salt for key derivation |
| `ANTHROPIC_ZERO_RETENTION` | `False` | Add x-no-store header to all LLM calls |
| `CONVERSATION_RETENTION_DAYS` | `0` | Days to keep data (0 = disabled) |
| `CHECKPOINT_RETENTION_DAYS` | `30` | Days to keep checkpoints (0 = disabled) |

## Security Model

| Threat | Mitigation | Protection Level |
|--------|-----------|-----------------|
| Network eavesdropping | HTTPS/TLS (existing) | Strong |
| Database breach (fields) | Fernet encryption on `translation`, `display_name` | Strong |
| Database breach (messages) | Fernet-encrypted checkpoint blobs | Strong |
| Database breach (access) | RLS on all tables including checkpoints | Defense-in-depth |
| LLM provider retains data | x-no-store header | Contractual (Anthropic policy) |
| Stale checkpoint accumulation | TTL purge on startup | Automated |
| Old conversation exposure | Configurable data retention | Opt-in |
| Server compromise | Not mitigated (server holds key) | N/A |
| Key rotation | Not yet implemented | Future work |

## Files Changed

### New Files
| File | Purpose |
|------|---------|
| `src/db/encryption.py` | Fernet encrypt/decrypt + FernetCipher for checkpoints |
| `src/agent/checkpoint_purge.py` | Checkpoint TTL purging |
| `src/services/data_retention.py` | Conversation data retention |
| `migrations/004_checkpoint_rls.sql` | RLS for LangGraph checkpoint tables |
| `tests/db/test_encryption.py` | 17 encryption tests |
| `tests/db/test_fernet_cipher.py` | 10 FernetCipher + EncryptedSerializer tests |
| `tests/db/test_repository_encryption.py` | 19 repository encryption integration tests |
| `tests/agent/test_checkpoint_purge.py` | 13 checkpoint purge tests |
| `tests/agent/test_llm_zero_retention.py` | 4 zero-retention tests |
| `tests/services/test_data_retention.py` | 6 data retention tests |

### Modified Files
| File | Change |
|------|--------|
| `src/config.py` | Added 4 new settings |
| `src/db/repository.py` | Encrypt/decrypt at repository boundary |
| `src/agent/llm.py` | Conditional x-no-store header |
| `src/agent/checkpointer.py` | EncryptedSerializer with FernetCipher |
| `src/api/main.py` | Checkpoint purge on startup |
| `pyproject.toml` | Added `cryptography` dependency |
| `.env.example` | Privacy & Data Retention section |

## Test Coverage

69 new tests across 6 test files:
- `test_encryption.py`: 17 tests (round-trip, edge cases, ciphertext properties, key derivation, invalid input)
- `test_fernet_cipher.py`: 10 tests (FernetCipher protocol compliance, EncryptedSerializer integration, round-trip with msgpack)
- `test_repository_encryption.py`: 19 tests (encrypt on write, decrypt on read, keyword search on plaintext fields, vocabulary CRUD)
- `test_checkpoint_purge.py`: 13 tests (MemorySaver no-op, disabled, SQL execution, error handling, settings)
- `test_llm_zero_retention.py`: 4 tests (header presence/absence, caching, profile isolation)
- `test_data_retention.py`: 6 tests (disabled, Supabase operations, error handling, None data)

## Future Work

- **Key rotation**: Support rotating SECRET_KEY with re-encryption migration
- **Scheduled retention**: Add a periodic task (cron/APScheduler) for `purge_old_conversations()`
- **User-controlled deletion**: UI for users to delete their own conversation history
- **Audit logging**: Log encryption/decryption operations for compliance
- **Confidential computing**: Evaluate TEE (e.g., AWS Nitro Enclaves) for LLM processing isolation
