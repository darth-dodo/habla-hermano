# Phase 24: Message Encryption & Data Privacy

**Date**: 2026-03-12
**Branch**: `feature/message-encryption`
**Status**: In Progress

## Problem

User conversations with the AI tutor contain personal learning data (messages, vocabulary, exercise answers). While HTTPS protects data in transit, there is no protection for:
- Data at rest in Supabase (database breach exposure)
- LLM provider data retention (Anthropic may store request/response pairs)
- Unbounded checkpoint growth (stale conversation state accumulates)
- No automatic conversation lifecycle management

## Goals

- Encrypt sensitive fields before storage (application-level encryption at rest)
- Request Anthropic zero-retention via API headers
- Auto-purge stale LangGraph checkpoints
- Provide configurable conversation data retention

## Constraints

True end-to-end encryption is not possible when the LLM is a conversation participant — the server must read plaintext to generate responses. This design focuses on practical protections within that constraint.

## Architecture

### Layer 1: Encryption at Rest

**Module**: `src/db/encryption.py`

```
User message (plaintext)
    ↓
encrypt_field()  →  Fernet(PBKDF2(SECRET_KEY, ENCRYPTION_SALT))
    ↓
Base64 ciphertext  →  Supabase text column
    ↓
decrypt_field()  →  Plaintext (on read)
```

**Key derivation**: PBKDF2-HMAC-SHA256 with 480,000 iterations. The encryption key is derived deterministically from `SECRET_KEY` + `ENCRYPTION_SALT`, so no additional key management is required. Changing either value invalidates all previously encrypted data.

**Scope**: Provides `encrypt_field()` / `decrypt_field()` utility functions. Not yet wired into repositories — field-level encryption should be applied selectively to sensitive columns (e.g., message content, vocabulary words) by modifying repository methods.

**Settings**:
| Setting | Default | Purpose |
|---------|---------|---------|
| `SECRET_KEY` | (existing) | Source key for PBKDF2 derivation |
| `ENCRYPTION_SALT` | `habla-hermano-encryption-v1` | Static salt for key derivation |

### Layer 2: Anthropic Zero-Retention

**Module**: `src/agent/llm.py` (modified)

When `ANTHROPIC_ZERO_RETENTION=True`, all `ChatAnthropic` instances include:
```
default_headers: {"x-no-store": "true"}
```

This requests Anthropic to not retain or log input/output for the API call. The header is added at the LLM factory level so all profiles (default, analysis, structured, creative, enhancement) inherit it.

**Settings**:
| Setting | Default | Purpose |
|---------|---------|---------|
| `ANTHROPIC_ZERO_RETENTION` | `False` | Add x-no-store header to all LLM calls |

### Layer 3: Checkpoint TTL Purging

**Module**: `src/agent/checkpoint_purge.py`

LangGraph stores conversation checkpoints in three Postgres tables (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`). Without cleanup, these grow unboundedly.

On application startup (after `init_checkpointer()`), old checkpoints are purged:
```sql
DELETE FROM {table} WHERE thread_ts < NOW() - INTERVAL '{N} days'
```

**Failure safety**: Purge errors are caught and logged — they never block app startup. When running in MemorySaver mode (dev), purge is a no-op.

**Settings**:
| Setting | Default | Purpose |
|---------|---------|---------|
| `CHECKPOINT_RETENTION_DAYS` | `30` | Days to keep checkpoints (0 = disabled) |

### Layer 4: Conversation Data Retention

**Module**: `src/services/data_retention.py`

Provides `purge_old_conversations()` for cleaning up old learning sessions and vocabulary items. Designed to be called from a scheduled task or admin endpoint.

Deletes:
- `learning_sessions` where `started_at < cutoff`
- `vocabulary` where both `last_reviewed_at` AND `next_review_at < cutoff`

**Settings**:
| Setting | Default | Purpose |
|---------|---------|---------|
| `CONVERSATION_RETENTION_DAYS` | `0` | Days to keep data (0 = disabled) |

## Security Model

| Threat | Mitigation | Protection Level |
|--------|-----------|-----------------|
| Network eavesdropping | HTTPS/TLS (existing) | Strong |
| Database breach | Fernet encryption at rest | Strong (if SECRET_KEY is secure) |
| LLM provider retains data | x-no-store header | Contractual (Anthropic policy) |
| Stale checkpoint accumulation | TTL purge on startup | Automated |
| Old conversation exposure | Configurable data retention | Opt-in |
| Server compromise | Not mitigated (server holds key) | N/A |
| Key rotation | Not yet implemented | Future work |

## Files Changed

### New Files
| File | Purpose |
|------|---------|
| `src/db/encryption.py` | Fernet encrypt/decrypt utilities |
| `src/agent/checkpoint_purge.py` | Checkpoint TTL purging |
| `src/services/data_retention.py` | Conversation data retention |
| `tests/db/test_encryption.py` | 17 encryption tests |
| `tests/agent/test_checkpoint_purge.py` | 13 checkpoint purge tests |
| `tests/agent/test_llm_zero_retention.py` | 4 zero-retention tests |
| `tests/services/test_data_retention.py` | 6 data retention tests |

### Modified Files
| File | Change |
|------|--------|
| `src/config.py` | Added 4 new settings |
| `src/agent/llm.py` | Conditional x-no-store header |
| `src/api/main.py` | Checkpoint purge on startup |
| `pyproject.toml` | Added `cryptography` dependency |

## Future Work

- **Repository integration**: Wire `encrypt_field()`/`decrypt_field()` into specific repository methods for message content, vocabulary words
- **Key rotation**: Support rotating SECRET_KEY with re-encryption migration
- **Scheduled retention**: Add a periodic task (cron/APScheduler) for `purge_old_conversations()`
- **Confidential computing**: Evaluate TEE (e.g., AWS Nitro Enclaves) for LLM processing isolation
- **User-controlled deletion**: UI for users to delete their own conversation history
- **Audit logging**: Log encryption/decryption operations for compliance

## Test Coverage

40 new tests across 4 test files:
- `test_encryption.py`: 17 tests (round-trip, edge cases, ciphertext properties, key derivation, invalid input)
- `test_checkpoint_purge.py`: 13 tests (MemorySaver no-op, disabled, SQL execution, error handling, settings)
- `test_llm_zero_retention.py`: 4 tests (header presence/absence, caching, profile isolation)
- `test_data_retention.py`: 6 tests (disabled, Supabase operations, error handling, None data)
