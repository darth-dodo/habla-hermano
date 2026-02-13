# Phase 8: Guest Session Support Design Document

> Simplified guest model -- chat-only access without persistence, authentication required for all data features

---

## Overview

Phase 8 defines how Habla Hermano handles unauthenticated (guest) users. After evaluating a full guest-persistence model with data merge on signup, we chose a simpler approach: **guests get chat functionality only, and all data features require authentication**.

This means:

- **Chat works for everyone**: Guests can have conversations with Hermano immediately, with no signup required. Conversation state persists within a session via LangGraph checkpointing and a session cookie.
- **Data features require an account**: Vocabulary tracking, progress statistics, spaced repetition review, and lesson progress are available only to authenticated users.
- **No guest data in Supabase**: Guest interactions do not write to the database. There is no guest data to merge on signup.

**Why simplify?** The original design called for storing guest vocabulary, sessions, and lesson progress in Supabase using a service-role admin client to bypass RLS, followed by a merge service to transfer data on signup. This introduced significant complexity (dropped FK constraints, admin client usage, deduplication logic) for marginal benefit. Most users who engage enough to care about progress tracking are willing to create an account.

**Related Phases**:
- [Phase 5: Supabase Authentication](phase5-supabase-auth.md) -- Authentication foundation
- [Phase 7: Progress Tracking](phase7-progress-tracking.md) -- Dashboard and data capture

---

## Goals

### Primary Goals

| Goal | Description |
|------|-------------|
| Frictionless first experience | Allow guests to chat with Hermano immediately without signing up |
| Chat persistence for guests | Maintain conversation context within a session via LangGraph checkpointing |
| Clear authentication boundary | All data features (vocabulary, progress, review) require a signed-in user |
| Simple Supabase client model | All database operations use user-authenticated clients; no admin/service-role client needed |

### Non-Goals

| Non-Goal | Rationale |
|----------|-----------|
| Guest vocabulary tracking | Simplifies architecture; vocabulary requires account |
| Guest progress persistence | No guest data in Supabase; no merge service needed |
| Cross-device guest continuity | Session cookie is device-specific; cross-device requires authentication |
| Data merge on signup | No guest data exists to merge |

---

## Architecture

### System Overview

```
                        Simplified Guest Model

Browser                                              Supabase
+------------------------------------------+        +----------------------+
|                                          |        |                      |
|  Authenticated User:                     |        |  vocabulary          |
|    Cookie: sb-access-token=<JWT>         |        |  user_id (FK)  ──>  auth.users
|    -> Full features (chat, vocab,        |        |                      |
|       progress, review)                  |        |  learning_sessions   |
|                                          |        |  user_id (FK)  ──>  auth.users
|  Guest User:                             |        |                      |
|    Cookie: session_id=<UUID>             |        |  lesson_progress     |
|    -> Chat only (no DB writes)           |        |  user_id (FK)  ──>  auth.users
|                                          |        |                      |
+------------------------------------------+        +----------------------+
                    |                                          ^
                    v                                          |
+------------------------------------------+                  |
|           FastAPI Backend                 |                  |
|                                          |                  |
|  Chat routes (OptionalUserDep):          |                  |
|    Guest  -> LangGraph only, no DB       |                  |
|    Auth   -> LangGraph + vocab capture   |------------------+
|              via get_supabase_for_user()  |  (user JWT for RLS)
|                                          |
|  Progress routes (OptionalUserDep):      |
|    Guest  -> empty stats, signup prompt  |
|    Auth   -> real stats via user client  |
|                                          |
|  Review routes (CurrentUserDep):         |
|    Guest  -> 401 Unauthorized            |
|    Auth   -> spaced repetition sessions  |
|                                          |
+------------------------------------------+
```

### Guest Chat: Session Cookie and LangGraph Checkpointing

Guest chat sessions are identified by a UUID stored in a `session_id` cookie. This UUID serves as the LangGraph `thread_id`, allowing conversation context to persist across messages within a browser session.

**Cookie configuration**:

```python
# Set on first anonymous chat message
response.set_cookie(
    key="session_id",
    value=new_session_id,       # UUID generated server-side
    httponly=True,               # Not accessible via JavaScript
    samesite="lax",             # CSRF protection
    max_age=60 * 60 * 24 * 7,  # 7 days
)
```

**Cookie lifecycle**:

1. **Creation**: Generated when a guest sends their first chat message.
2. **Usage**: Sent with every request; used as `thread_id` for LangGraph checkpointing.
3. **Reset**: Deleted when the user starts a new conversation (POST /new).

The session cookie is used exclusively for LangGraph thread identification. It does not appear in any Supabase queries and does not function as a user identity for data operations.

### Identity Resolution in Chat

The `_resolve_chat_identity` helper in `chat.py` determines the thread ID and whether to track progress:

```python
def _resolve_chat_identity(
    user: AuthenticatedUser | None,
    session_id: str | None,
) -> tuple[str, str | None, str | None]:
    """Resolve thread_id and user_id for chat.

    Returns:
        Tuple of (thread_id, user_id_for_progress, new_session_id).
        - thread_id: Used for LangGraph checkpointing (both auth and guest)
        - user_id_for_progress: Only set for authenticated users (None for guests)
        - new_session_id: Set only for first-time guests (triggers cookie creation)
    """
    if user:
        return get_user_thread_id(user.id), user.id, None
    if session_id:
        return session_id, None, None
    new_id = str(uuid.uuid4())
    return new_id, None, new_id
```

The key detail: `user_id_for_progress` is `None` for all guest paths. This means the vocabulary capture code block is never entered for guests, since it checks `if new_vocabulary and effective_user_id and user and sb_access_token`.

### User-Authenticated Supabase Client

All database operations use `get_supabase_for_user(sb_access_token)`, which creates a Supabase client authenticated with the user's own JWT:

```python
def get_supabase_for_user(access_token: str) -> SupabaseClient:
    """Get Supabase client authenticated with user's JWT.

    Creates a client that includes the user's access token,
    allowing RLS policies to use auth.uid() for row-level access control.
    """
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client
```

This pattern means:

- **RLS works naturally**: Supabase RLS policies using `auth.uid() = user_id` function correctly because the client carries the user's JWT.
- **No admin client needed for data operations**: The service-role client (`get_supabase_admin`) is not used for any guest or user data operations.
- **FK constraints preserved**: All `user_id` columns maintain their foreign key references to `auth.users`, since only real authenticated user IDs are written to the database.

---

## Authentication Boundaries

### What Guests Can Access

| Feature | Guest Access | How It Works |
|---------|-------------|--------------|
| Chat conversation | Full | LangGraph checkpointing with session cookie as thread_id |
| Grammar feedback | Full | Returned in chat response (no DB write) |
| Pronunciation tips | Full | Returned in chat response (no DB write) |
| Scaffolding (A0-A1) | Full | Returned in chat response (no DB write) |

### What Requires Authentication

| Feature | Auth Dependency | Behavior for Guests |
|---------|----------------|---------------------|
| Vocabulary tracking | `OptionalUserDep` + `sb_access_token` | Skipped silently; new vocabulary not persisted |
| Progress dashboard | `OptionalUserDep` | Returns empty stats with signup prompt |
| Vocabulary list | `OptionalUserDep` | Returns empty list |
| Chart data | `OptionalUserDep` | Returns empty arrays |
| Spaced repetition | `CurrentUserDep` | Returns 401 Unauthorized |
| Review sessions | `CurrentUserDep` | Returns 401 Unauthorized |

### Dependency Types

The application uses two FastAPI dependency patterns to enforce authentication boundaries:

- **`OptionalUserDep`** (`AuthenticatedUser | None`): Used by chat and progress endpoints. Returns `None` for guests, allowing the endpoint to handle both cases (serve chat content or show empty stats with signup prompt).
- **`CurrentUserDep`** (`AuthenticatedUser`): Used by review endpoints. Raises HTTP 401 for unauthenticated requests, enforcing that spaced repetition is an authenticated-only feature.

---

## Route Patterns

### Chat (supports guests)

```python
@router.post("/chat", response_class=HTMLResponse)
async def send_message(
    user: OptionalUserDep,          # None for guests
    session_id: Annotated[str | None, Cookie()] = None,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
    ...
):
    thread_id, effective_user_id, new_session_id = _resolve_chat_identity(user, session_id)

    # LangGraph invocation works for both auth and guest
    result = await graph.ainvoke(...)

    # Vocabulary capture: authenticated users ONLY
    if new_vocabulary and effective_user_id and user and sb_access_token:
        user_client = get_supabase_for_user(sb_access_token)
        progress_service = ProgressService(effective_user_id, client=user_client)
        progress_service.record_chat_activity(...)

    # Set session cookie for new guests
    if new_session_id:
        template_response.set_cookie(key="session_id", value=new_session_id, ...)
```

### Progress (returns empty state for guests)

```python
@router.get("/", response_class=HTMLResponse)
async def get_progress_page(
    user: OptionalUserDep,
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
    ...
):
    if not user or not sb_access_token:
        # Guest: show empty stats with signup prompt
        return templates.TemplateResponse(
            name="progress.html",
            context={"total_words": 0, ..., "user": None, "is_guest": True},
        )

    # Authenticated: fetch real stats
    user_client = get_supabase_for_user(sb_access_token)
    service = ProgressService(user.id, client=user_client)
    stats = service.get_dashboard_stats()
    ...
```

### Review (requires authentication)

```python
@router.post("/start", response_class=HTMLResponse)
async def start_review_session(
    user: CurrentUserDep,  # Raises 401 for guests
    sb_access_token: Annotated[str | None, Cookie(alias="sb-access-token")] = None,
    ...
):
    user_client = get_supabase_for_user(sb_access_token) if sb_access_token else None
    service = ReviewService(user.id, client=user_client)
    ...
```

---

## What Was Removed (Compared to Original Design)

The original Phase 8 design included several patterns that were removed in favor of the simplified model:

| Removed Component | Original Purpose | Why Removed |
|-------------------|-----------------|-------------|
| `EffectiveUser` dataclass (for routing) | Unified identity for auth/guest in progress and review routes | No longer needed; chat uses its own `_resolve_chat_identity`, progress routes check `user` directly |
| `get_supabase_admin()` for data ops | Bypassed RLS for guest writes to Supabase | Guests no longer write to Supabase; all data ops use `get_supabase_for_user()` |
| `_resolve_identity()` in progress/review | Resolved effective user for data queries | Removed from `progress.py` and `review.py`; these routes check auth directly |
| `GuestDataMergeService` / `merge.py` | Transferred guest data to authenticated account on signup | No guest data exists to merge |
| `get_client_for_user(effective_user)` | Selected admin or anon client based on identity type | Single client pattern: `get_supabase_for_user(sb_access_token)` |
| Dropped FK constraints migration | Allowed guest UUIDs (not in `auth.users`) in `user_id` columns | FK constraints preserved; only real user IDs in the database |

**Note**: The `EffectiveUser` dataclass and related helpers (`get_effective_user`, `get_client_for_user`, `EffectiveUserDep`) still exist in `src/api/auth.py` as legacy code, but they are no longer used by any route. They can be removed in a future cleanup pass.

---

## Benefits of the Simplified Model

### Architectural simplicity

- **One client pattern**: All database operations go through `get_supabase_for_user(sb_access_token)`. No conditional logic to select between admin and anon clients.
- **RLS works naturally**: Row-level security policies (`auth.uid() = user_id`) function correctly because the client carries the user's JWT. No need to bypass RLS with the service-role key.
- **FK constraints intact**: The `user_id` columns maintain foreign key references to `auth.users`. No schema modifications required for guest support.
- **No service key dependency**: Data operations do not require the `SUPABASE_SERVICE_KEY` environment variable, reducing the attack surface.

### Reduced code and maintenance

- **No merge service**: Eliminated the `GuestDataMergeService` with its vocabulary deduplication, session transfer, and lesson score comparison logic.
- **No identity abstraction layer**: Routes directly check `user` (from `OptionalUserDep` or `CurrentUserDep`) instead of going through an `EffectiveUser` indirection.
- **Fewer failure modes**: No fire-and-forget merge operations, no race conditions on signup, no orphaned guest data requiring cleanup jobs.

### Clear product boundaries

- **Signup incentive**: Users who want to track vocabulary and progress have a clear reason to create an account.
- **No false promises**: Guests are not led to believe their data will persist if they do not sign up.
- **Simpler onboarding**: No merge operation means signup and login are purely authentication events with no hidden side effects.

---

## Testing Strategy

### Unit Tests

| Test | Description |
|------|-------------|
| `test_resolve_chat_identity_authenticated` | Returns user ID for thread and progress |
| `test_resolve_chat_identity_existing_guest` | Returns session_id for thread, None for progress |
| `test_resolve_chat_identity_new_guest` | Generates new UUID for thread, None for progress |
| `test_chat_no_vocab_capture_for_guest` | Vocabulary not persisted when user is None |
| `test_chat_vocab_capture_for_auth_user` | Vocabulary persisted via user-authenticated client |

### Integration Tests

| Test | Description |
|------|-------------|
| `test_guest_chat_works_without_auth` | POST /chat returns response for guest |
| `test_guest_chat_sets_session_cookie` | First guest message creates session_id cookie |
| `test_guest_progress_shows_empty_state` | GET /progress/ returns empty stats for guest |
| `test_guest_review_returns_401` | POST /review/start returns 401 for guest |
| `test_auth_user_chat_captures_vocab` | POST /chat stores vocabulary for auth user |
| `test_auth_user_progress_shows_stats` | GET /progress/ returns real stats for auth user |

### E2E Tests (Playwright)

| Test | Description |
|------|-------------|
| Guest chat journey | Chat as guest, verify responses, verify no progress data |
| Guest progress page | Visit /progress/ as guest, verify signup prompt |
| Auth user full journey | Sign up, chat, verify vocabulary appears on progress page |
| New conversation as guest | Start new conversation, verify session cookie reset |

---

## Success Criteria

### Functional

- [x] Guest users can chat with Hermano without signing up
- [x] Guest conversations persist within a session (LangGraph checkpointing)
- [x] Guest users see empty progress dashboard with signup prompt
- [x] Authenticated users get full vocabulary tracking from chat
- [x] Authenticated users see real progress statistics
- [x] Review endpoints require authentication (401 for guests)

### Technical

- [x] No service-role admin client used for data operations
- [x] All data operations use `get_supabase_for_user(sb_access_token)`
- [x] FK constraints on `user_id` columns preserved
- [x] RLS policies work without modification
- [x] No guest data written to Supabase tables
