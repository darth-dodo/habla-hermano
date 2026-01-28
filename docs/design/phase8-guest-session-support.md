# Phase 8: Guest Session Support Design Document

> Progress tracking for unauthenticated users with seamless data migration on signup/login

---

## Overview

Phase 8 extends Habla Hermano to support progress tracking for unauthenticated (guest) users. This enables:

- **Guest Progress Tracking**: Vocabulary, learning sessions, and lesson progress stored without requiring signup
- **Seamless Migration**: All guest data automatically transfers to authenticated account on signup/login
- **Frictionless Onboarding**: Users can experience full app functionality before committing to an account
- **Data Continuity**: No learning progress is lost when transitioning from guest to authenticated user

**Business Value**: Reducing signup friction increases user engagement. Users who experience value before being asked to create an account have higher conversion rates and retention. Guest progress tracking removes the "cold start" problem where new authenticated users see empty dashboards.

**Learning Goal**: Master session-based identity patterns, admin client usage for RLS bypass, and data merge strategies for user conversion flows.

**Related Phases**:
- [Phase 5: Supabase Authentication](phase5-supabase-auth.md) - Authentication foundation
- [Phase 7: Progress Tracking](phase7-progress-tracking.md) - Dashboard and data capture

---

## Goals

### Primary Goals

| Goal | Description |
|------|-------------|
| Enable guest progress tracking | Store vocabulary, sessions, and lesson progress for unauthenticated users |
| Seamless data migration | Transfer all guest data to authenticated account on signup/login |
| Unified identity handling | Single code path for auth/guest in routes via `_resolve_identity()` helper |
| Minimal schema changes | Reuse existing tables with relaxed FK constraints |

### Non-Goals

| Non-Goal | Rationale |
|----------|-----------|
| Guest user profiles | No need for profile customization without authentication |
| Cross-device guest sync | Session ID is device-specific; cross-device requires authentication |
| Guest conversation history | LangGraph checkpointing already supports session-based threads |

---

## Requirements

### Functional Requirements

| Requirement | Priority | Description |
|-------------|----------|-------------|
| Session ID cookie | P0 | Generate and persist UUID for guest identity |
| Guest vocabulary capture | P0 | Store new vocabulary from chat conversations |
| Guest session tracking | P0 | Record learning sessions for guests |
| Guest lesson progress | P0 | Track lesson completion for guests |
| Guest dashboard access | P0 | Display progress stats for guests on /progress/ |
| Data merge on signup | P0 | Transfer all guest data when creating account |
| Data merge on login | P0 | Transfer all guest data when logging into existing account |
| Cookie cleanup post-merge | P1 | Clear session_id cookie after successful merge |

### Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Merge latency | <500ms for typical guest data volume |
| Cookie security | httponly, samesite=lax, secure in production |
| Cookie expiry | 7 days (matches auth token expiry) |
| Data integrity | ACID compliance on merge operations |
| Error resilience | Guest data capture fails silently (fire-and-forget) |

---

## Architecture

### System Overview

```
                        Guest Session Flow

Browser                                              Supabase
┌──────────────────────────────────────────┐        ┌──────────────────────┐
│                                          │        │                      │
│  Cookie: session_id=<UUID>               │        │  vocabulary          │
│         (httponly, samesite=lax)         │        │  ├─ user_id (UUID)   │
│         (7-day expiry)                   │        │  └─ (no FK to users) │
│                                          │        │                      │
└──────────────────────────────────────────┘        │  learning_sessions   │
                    │                               │  ├─ user_id (UUID)   │
                    ▼                               │  └─ (no FK to users) │
┌──────────────────────────────────────────┐        │                      │
│           FastAPI Backend                 │        │  lesson_progress     │
│                                          │        │  ├─ user_id (UUID)   │
│  ┌────────────────────────────────────┐  │        │  └─ (no FK to users) │
│  │  EffectiveUser Dependency          │  │        │                      │
│  │  ├─ Check JWT (authenticated)      │  │        └──────────────────────┘
│  │  └─ Fallback to session_id (guest) │  │                   ▲
│  └────────────────────────────────────┘  │                   │
│                    │                      │                   │
│                    ▼                      │                   │
│  ┌────────────────────────────────────┐  │                   │
│  │  get_client_for_user()             │  │                   │
│  │  ├─ Guest → get_supabase_admin()   │──┼───────────────────┘
│  │  └─ Auth  → get_supabase()         │  │    (admin bypasses RLS)
│  └────────────────────────────────────┘  │
│                                          │
└──────────────────────────────────────────┘
```

### Session ID Cookie Mechanism

The session ID cookie provides persistent identity for guest users across browser sessions.

**Cookie Configuration**:
```python
GUEST_SESSION_COOKIE = "session_id"
GUEST_SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

def set_guest_session_cookie(response: Response, session_id: str) -> None:
    """Set the guest session cookie on the response."""
    response.set_cookie(
        key=GUEST_SESSION_COOKIE,
        value=session_id,
        max_age=GUEST_SESSION_MAX_AGE,
        httponly=True,        # Not accessible via JavaScript
        secure=True,          # HTTPS only in production
        samesite="lax",       # CSRF protection while allowing navigation
    )
```

**Cookie Lifecycle**:
1. **Creation**: Generated on first guest interaction (chat message, lesson start)
2. **Persistence**: Sent with every request for 7 days
3. **Cleanup**: Deleted after successful merge on signup/login

### Guest Data Storage Strategy

Guest data is stored in the same tables as authenticated user data, using the session UUID in the `user_id` column.

**Key Insight**: The `user_id` column stores UUIDs, but for guests these UUIDs are not present in `auth.users`. This requires:

1. **Dropped FK constraints**: Guest UUIDs cannot reference `auth.users`
2. **Admin client for writes**: RLS policies check `auth.uid()`, which is NULL for guests
3. **Explicit user_id filtering**: Queries must include `.eq("user_id", effective_user.id)`

### Admin Client for Guest Operations

```python
def get_client_for_user(effective_user: EffectiveUser) -> SupabaseClient:
    """Return the appropriate Supabase client for the given user identity.

    Guests require the admin (service-role) client because they have no
    JWT and therefore cannot pass RLS policies with the anon client.
    Authenticated users use the standard anon client which respects RLS.
    """
    if effective_user.is_guest:
        return get_supabase_admin()
    return get_supabase()
```

**Why Admin Client?**

RLS policies use `auth.uid()` to check ownership:
```sql
CREATE POLICY "Users can manage own vocabulary"
    ON public.vocabulary FOR ALL
    USING (auth.uid() = user_id);
```

For guests, `auth.uid()` returns NULL (no JWT), so the policy denies all operations. The service-role client bypasses RLS entirely.

### _resolve_identity() Helper Pattern

The `EffectiveUser` dataclass and `get_effective_user()` dependency provide unified identity handling.

```python
@dataclass(frozen=True)
class EffectiveUser:
    """Represents either an authenticated user or an anonymous guest session."""
    id: str           # User UUID or session UUID
    is_guest: bool    # True for session-based identity
    email: str | None = None

async def get_effective_user(
    request: Request,
    user: OptionalUserDep,
) -> EffectiveUser | None:
    """Resolve the effective user identity.

    Priority:
    1. Authenticated JWT user (from sb-access-token cookie)
    2. Guest session (from session_id cookie)
    3. None (no identity established)
    """
    if user is not None:
        return EffectiveUser(id=user.id, is_guest=False, email=user.email)

    session_id = request.cookies.get("session_id")
    if session_id:
        return EffectiveUser(id=session_id, is_guest=True)

    return None
```

**Usage in Routes**:
```python
@router.post("/chat")
async def send_message(
    effective_user: EffectiveUserDep,
    ...
):
    if effective_user:
        client = get_client_for_user(effective_user)
        vocab_repo = VocabularyRepository(effective_user.id, client=client)
        # Works for both authenticated and guest users
```

---

## GuestDataMergeService

### Overview

The merge service transfers all guest data to an authenticated account when a user signs up or logs in. It handles:

- **Vocabulary deduplication**: Merge counters for words that exist in both accounts
- **Session transfer**: Move all learning sessions to the authenticated user
- **Lesson progress deduplication**: Keep higher scores when same lesson completed by both

### Service Interface

```python
class GuestDataMergeService:
    """Merges guest session data into an authenticated user's account.

    All operations use the admin client (service role) to bypass RLS,
    since guest rows have session UUIDs that don't match auth.uid().
    """

    def __init__(self, guest_session_id: str, authenticated_user_id: str) -> None:
        """Initialize merge service.

        Args:
            guest_session_id: Guest's session UUID (from session_id cookie).
            authenticated_user_id: Authenticated user's UUID (from JWT).
        """
        self._guest_id = guest_session_id
        self._auth_id = authenticated_user_id
        self._client = get_supabase_admin()

    def merge_all(self) -> dict[str, int]:
        """Merge all guest data into the authenticated account.

        Returns:
            Dict with counts: {"vocabulary": N, "sessions": N, "lessons": N}
        """
        vocab_count = self._merge_vocabulary()
        session_count = self._merge_sessions()
        lesson_count = self._merge_lessons()
        return {
            "vocabulary": vocab_count,
            "sessions": session_count,
            "lessons": lesson_count,
        }
```

### _merge_vocabulary()

Transfers vocabulary entries from guest to authenticated user. For duplicate words (same word+language), merges counters:

```python
def _merge_vocabulary(self) -> int:
    """Transfer vocabulary entries from guest to authenticated user.

    Deduplication Strategy:
    - times_seen: sum both values
    - times_correct: sum both values
    - first_seen_at: keep the earliest timestamp

    Returns:
        Number of vocabulary entries transferred/merged.
    """
    guest_vocab = (
        self._client.table("vocabulary")
        .select("*")
        .eq("user_id", self._guest_id)
        .execute()
    )
    if not guest_vocab.data:
        return 0

    count = 0
    for entry in guest_vocab.data:
        existing = (
            self._client.table("vocabulary")
            .select("*")
            .eq("user_id", self._auth_id)
            .eq("word", entry["word"])
            .eq("language", entry["language"])
            .execute()
        )

        if existing.data:
            # Merge counters
            auth_entry = existing.data[0]
            self._client.table("vocabulary").update({
                "times_seen": auth_entry["times_seen"] + entry["times_seen"],
                "times_correct": auth_entry["times_correct"] + entry["times_correct"],
                "first_seen_at": min(auth_entry["first_seen_at"], entry["first_seen_at"]),
            }).eq("id", auth_entry["id"]).execute()
            # Delete guest entry
            self._client.table("vocabulary").delete().eq("id", entry["id"]).execute()
        else:
            # Transfer ownership
            self._client.table("vocabulary").update({
                "user_id": self._auth_id
            }).eq("id", entry["id"]).execute()

        count += 1

    return count
```

### _merge_sessions()

Transfers all learning sessions. No deduplication needed since each session is unique.

```python
def _merge_sessions(self) -> int:
    """Transfer all learning sessions from guest to authenticated user.

    Sessions are always transferred (no dedup needed -- each session is unique).

    Returns:
        Number of sessions transferred.
    """
    guest_sessions = (
        self._client.table("learning_sessions")
        .select("id")
        .eq("user_id", self._guest_id)
        .execute()
    )
    if not guest_sessions.data:
        return 0

    count = len(guest_sessions.data)
    # Bulk update all sessions
    self._client.table("learning_sessions").update({
        "user_id": self._auth_id
    }).eq("user_id", self._guest_id).execute()

    return count
```

### _merge_lessons()

Transfers lesson progress. For duplicate lessons (same lesson_id), keeps higher score.

```python
def _merge_lessons(self) -> int:
    """Transfer lesson progress from guest to authenticated user.

    Deduplication Strategy:
    - Keep the higher score if both completed same lesson
    - Always transfer if auth user hasn't completed the lesson

    Returns:
        Number of lesson entries transferred/merged.
    """
    guest_lessons = (
        self._client.table("lesson_progress")
        .select("*")
        .eq("user_id", self._guest_id)
        .execute()
    )
    if not guest_lessons.data:
        return 0

    count = 0
    for entry in guest_lessons.data:
        existing = (
            self._client.table("lesson_progress")
            .select("*")
            .eq("user_id", self._auth_id)
            .eq("lesson_id", entry["lesson_id"])
            .execute()
        )

        if existing.data:
            # Keep higher score
            auth_entry = existing.data[0]
            guest_score = entry.get("score") or 0
            auth_score = auth_entry.get("score") or 0
            if guest_score > auth_score:
                self._client.table("lesson_progress").update({
                    "score": guest_score
                }).eq("user_id", self._auth_id).eq("lesson_id", entry["lesson_id"]).execute()
            # Delete guest entry
            self._client.table("lesson_progress").delete().eq(
                "user_id", self._guest_id
            ).eq("lesson_id", entry["lesson_id"]).execute()
        else:
            # Transfer ownership
            self._client.table("lesson_progress").update({
                "user_id": self._auth_id
            }).eq("user_id", self._guest_id).eq("lesson_id", entry["lesson_id"]).execute()

        count += 1

    return count
```

---

## Schema Changes

### Overview

To support guest UUIDs in the `user_id` column, foreign key constraints must be dropped. Guest session UUIDs are not present in `auth.users`, so FK constraints would fail on insert.

### Migration SQL

```sql
-- Drop FK constraints to allow guest UUIDs
-- Guest session_id values are valid UUIDs but not in auth.users

ALTER TABLE public.vocabulary
    DROP CONSTRAINT IF EXISTS vocabulary_user_id_fkey;

ALTER TABLE public.learning_sessions
    DROP CONSTRAINT IF EXISTS learning_sessions_user_id_fkey;

ALTER TABLE public.lesson_progress
    DROP CONSTRAINT IF EXISTS lesson_progress_user_id_fkey;

-- Note: user_profiles retains its FK because guests don't have profiles
-- The trigger on auth.users handles profile creation for authenticated users only
```

### Affected Tables

| Table | Change | Reason |
|-------|--------|--------|
| `vocabulary` | Drop FK constraint | Guest UUIDs not in auth.users |
| `learning_sessions` | Drop FK constraint | Guest UUIDs not in auth.users |
| `lesson_progress` | Drop FK constraint | Guest UUIDs not in auth.users |
| `user_profiles` | No change | Guests don't have profiles |
| `checkpoint_*` | No change | LangGraph manages these tables |

### RLS Policy Updates

No RLS policy changes needed. The existing policies reference `auth.uid()`, which:
- Returns the user's UUID for authenticated requests (JWT present)
- Returns NULL for guest requests (no JWT)

Guest writes use the admin client, which bypasses RLS entirely. Guest reads are not supported via the anon client -- the admin client is required for all guest operations.

---

## Integration Points

### chat.py: Guest Vocabulary Capture

The chat route captures vocabulary for both authenticated and guest users.

```python
@router.post("/chat", response_class=HTMLResponse)
async def send_message(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    message: Annotated[str, Form()],
    level: Annotated[str, Form()] = "A1",
    language: Annotated[str, Form()] = "es",
    session_id: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    # ... graph invocation ...

    # Capture vocabulary for any user with identity (fire-and-forget)
    if new_vocabulary:
        effective_id: str | None = None

        if user:
            effective_id = user.id
            client = get_supabase()  # Authenticated: use anon client
        elif session_id or new_session_id:
            effective_id = session_id or new_session_id
            client = get_supabase_admin()  # Guest: use admin client

        if effective_id:
            try:
                progress_service = ProgressService(effective_id, client=client)
                progress_service.record_chat_activity(
                    language=language,
                    level=level,
                    new_vocabulary=new_vocabulary,
                )
            except Exception:
                logger.exception("Failed to capture chat activity")

    # Set session cookie for new guests
    template_response = templates.TemplateResponse(...)
    if new_session_id:
        set_guest_session_cookie(template_response, new_session_id)

    return template_response
```

### lessons.py: Guest Lesson Completion

The lessons route records completion for both authenticated and guest users.

```python
@router.post("/{lesson_id}/complete")
async def complete_lesson(
    lesson_id: str,
    effective_user: EffectiveUserDep,
    score: int = Form(0),
):
    if not effective_user:
        # No identity -- cannot record progress
        return {"status": "ok"}

    client = get_client_for_user(effective_user)
    lesson_repo = LessonProgressRepository(effective_user.id, client=client)
    lesson_repo.complete_lesson(lesson_id, score)

    return {"status": "ok"}
```

### progress.py: Guest Dashboard Access

The progress dashboard displays stats for both authenticated and guest users.

```python
@router.get("/", response_class=HTMLResponse)
async def progress_page(
    request: Request,
    templates: TemplatesDep,
    effective_user: EffectiveUserDep,
):
    if not effective_user:
        # Redirect to login or show empty state
        return templates.TemplateResponse(
            request=request,
            name="progress_guest_prompt.html",
        )

    client = get_client_for_user(effective_user)
    progress_service = ProgressService(effective_user.id, client=client)
    stats = progress_service.get_dashboard_stats()

    return templates.TemplateResponse(
        request=request,
        name="progress.html",
        context={
            "stats": stats,
            "is_guest": effective_user.is_guest,
        },
    )
```

### auth.py: Merge Trigger on Signup/Login

The auth routes trigger data merge when a guest signs up or logs in.

```python
@router.post("/signup")
async def signup(
    request: Request,
    templates: TemplatesDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
) -> Response:
    # ... signup logic ...

    # Set cookie and redirect
    response = Response(status_code=status.HTTP_200_OK)
    set_auth_cookie(response, auth_response.session.access_token)

    # Merge guest data if session_id cookie exists (fire-and-forget)
    guest_session_id = request.cookies.get("session_id")
    if guest_session_id and auth_response.user:
        try:
            merge_service = GuestDataMergeService(
                guest_session_id=guest_session_id,
                authenticated_user_id=auth_response.user.id,
            )
            result = merge_service.merge_all()
            logger.info("Merged guest data on signup: %s", result)
            # Clear guest session cookie after merge
            response.delete_cookie(key="session_id")
        except Exception:
            logger.exception("Failed to merge guest data on signup")

    response.headers["HX-Redirect"] = "/"
    return response


@router.post("/login")
async def login(
    request: Request,
    templates: TemplatesDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> Response:
    # ... login logic ...

    # Set cookie and redirect
    response = Response(status_code=status.HTTP_200_OK)
    set_auth_cookie(response, auth_response.session.access_token)

    # Merge guest data if session_id cookie exists (fire-and-forget)
    guest_session_id = request.cookies.get("session_id")
    if guest_session_id and auth_response.user:
        try:
            merge_service = GuestDataMergeService(
                guest_session_id=guest_session_id,
                authenticated_user_id=auth_response.user.id,
            )
            result = merge_service.merge_all()
            logger.info("Merged guest data on login: %s", result)
            # Clear guest session cookie after merge
            response.delete_cookie(key="session_id")
        except Exception:
            logger.exception("Failed to merge guest data on login")

    response.headers["HX-Redirect"] = "/"
    return response
```

---

## Data Flow Diagrams

### Guest Progress Capture Flow

```
Guest sends chat message
         │
         ▼
┌─────────────────────────────────────────┐
│ POST /chat                               │
│ Cookie: session_id=<UUID>                │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ get_effective_user()                     │
│ ├─ No JWT found                          │
│ └─ session_id cookie found → EffectiveUser(is_guest=True)
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ LangGraph invocation                     │
│ └─ Result contains new_vocabulary[]     │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ get_client_for_user(effective_user)      │
│ └─ is_guest=True → get_supabase_admin() │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ VocabularyRepository(session_id, admin) │
│ └─ INSERT INTO vocabulary               │
│    (user_id=session_id, word, ...)      │
└─────────────────────────────────────────┘
```

### Guest to Authenticated Migration Flow

```
Guest clicks "Sign Up"
         │
         ▼
┌─────────────────────────────────────────┐
│ POST /auth/signup                        │
│ Cookies: session_id=<guest_uuid>         │
│ Form: email, password                    │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ Supabase Auth: sign_up()                 │
│ └─ Creates auth.user(id=<auth_uuid>)    │
│ └─ Returns JWT access_token              │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ GuestDataMergeService(guest_id, auth_id)│
│ ├─ _merge_vocabulary()                   │
│ │   └─ UPDATE vocabulary SET user_id=auth_id WHERE user_id=guest_id
│ ├─ _merge_sessions()                     │
│ │   └─ UPDATE learning_sessions SET user_id=auth_id WHERE user_id=guest_id
│ └─ _merge_lessons()                      │
│     └─ UPDATE lesson_progress SET user_id=auth_id WHERE user_id=guest_id
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ Set-Cookie: sb-access-token=<JWT>        │
│ Delete-Cookie: session_id                │
│ HX-Redirect: /                           │
└─────────────────────────────────────────┘
```

### Dashboard Data Flow (Guest vs Authenticated)

```
                    GET /progress/
                          │
                          ▼
              ┌───────────────────────┐
              │ get_effective_user()   │
              └───────────────────────┘
                    │           │
          ┌─────────┘           └─────────┐
          │                               │
          ▼                               ▼
┌──────────────────┐            ┌──────────────────┐
│ Authenticated    │            │ Guest            │
│ EffectiveUser    │            │ EffectiveUser    │
│ is_guest=False   │            │ is_guest=True    │
└──────────────────┘            └──────────────────┘
          │                               │
          ▼                               ▼
┌──────────────────┐            ┌──────────────────┐
│ get_supabase()   │            │ get_supabase_    │
│ (anon client)    │            │ admin()          │
└──────────────────┘            └──────────────────┘
          │                               │
          │      ┌───────────────┐        │
          └──────► ProgressService ◄──────┘
                 │ (same API)    │
                 └───────────────┘
                          │
                          ▼
                 ┌───────────────┐
                 │ progress.html │
                 │ is_guest=?    │
                 │ (signup prompt│
                 │  if guest)    │
                 └───────────────┘
```

---

## Testing Strategy

### Unit Tests

**File**: `tests/test_merge_service.py`

| Test | Description |
|------|-------------|
| `test_merge_vocabulary_new_words` | Guest words transfer to auth user |
| `test_merge_vocabulary_duplicates` | Counters merge for existing words |
| `test_merge_vocabulary_keeps_earliest_date` | first_seen_at uses minimum |
| `test_merge_sessions_all_transfer` | All guest sessions move to auth user |
| `test_merge_lessons_new_lessons` | Guest lessons transfer to auth user |
| `test_merge_lessons_keeps_higher_score` | Higher score retained on duplicate |
| `test_merge_all_empty_guest` | No errors when guest has no data |
| `test_merge_all_returns_counts` | Returns accurate merge counts |

**File**: `tests/test_guest_progress.py`

| Test | Description |
|------|-------------|
| `test_guest_vocabulary_capture` | Vocabulary stored with session_id |
| `test_guest_session_tracking` | Learning sessions created for guests |
| `test_guest_lesson_completion` | Lesson progress recorded for guests |
| `test_guest_dashboard_access` | Progress page renders for guests |
| `test_effective_user_authenticated` | JWT user returns correct identity |
| `test_effective_user_guest` | Session cookie returns guest identity |
| `test_effective_user_none` | No identity when no cookies |
| `test_get_client_for_guest` | Admin client returned for guests |
| `test_get_client_for_auth` | Anon client returned for auth users |

### Integration Tests

**File**: `tests/test_data_capture.py`

| Test | Description |
|------|-------------|
| `test_chat_captures_guest_vocabulary` | POST /chat stores vocab for guest |
| `test_lesson_completion_records_guest_progress` | Lesson completion for guest |
| `test_signup_merges_guest_data` | Signup triggers data merge |
| `test_login_merges_guest_data` | Login triggers data merge |
| `test_session_cookie_deleted_after_merge` | Cookie cleanup post-merge |
| `test_merge_failure_does_not_fail_auth` | Auth succeeds if merge fails |

### E2E Tests (Playwright)

| Test | Description |
|------|-------------|
| Guest vocabulary journey | Chat as guest, check vocabulary captured |
| Guest lesson journey | Complete lesson as guest, check progress |
| Guest to signup merge | Chat as guest, signup, verify merged data |
| Guest to login merge | Chat as guest, login, verify merged data |
| Dashboard shows guest data | View progress page as guest |
| Dashboard shows signup prompt | Guest dashboard includes signup CTA |

---

## Implementation Plan

### File Summary

| File | Action | Description |
|------|--------|-------------|
| `src/api/auth.py` | Modify | Add EffectiveUser, get_effective_user, get_client_for_user |
| `src/services/merge.py` | Create | GuestDataMergeService with merge methods |
| `src/api/routes/auth.py` | Modify | Add merge trigger on signup/login |
| `src/api/routes/chat.py` | Modify | Use EffectiveUser for vocab capture |
| `src/api/routes/lessons.py` | Modify | Use EffectiveUser for lesson completion |
| `src/api/routes/progress.py` | Modify | Use EffectiveUser for dashboard |
| `src/db/repository.py` | Modify | Accept optional client parameter |
| `supabase/migrations/*` | Create | Drop FK constraints migration |
| `tests/test_merge_service.py` | Create | Unit tests for merge service |
| `tests/test_guest_progress.py` | Create | Unit tests for guest progress |
| `tests/test_data_capture.py` | Modify | Integration tests for data capture |

### Dependency Changes

No new dependencies required. Uses existing:
- `supabase` - Database client
- `PyJWT` - Token handling (existing)

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Orphaned guest data | Medium | Low | Periodic cleanup job for sessions >30 days |
| Merge race conditions | Low | Medium | Fire-and-forget pattern; user can retry |
| Admin client misuse | Low | High | Clear documentation, limited scope |
| Cookie theft | Low | Medium | httponly, secure flags, 7-day expiry |
| Large merge volume | Low | Medium | Batch operations, timeout handling |

---

## Success Criteria

### Functional

- [ ] Guest users can track vocabulary from chat
- [ ] Guest users can complete lessons with progress recorded
- [ ] Guest users can view progress dashboard
- [ ] Data merges correctly on signup
- [ ] Data merges correctly on login
- [ ] Session cookie deleted after merge
- [ ] Duplicate handling works (vocabulary counters, lesson scores)

### Technical

- [ ] All existing tests pass
- [ ] New tests achieve 90%+ coverage
- [ ] Merge completes in <500ms for typical data volumes
- [ ] Fire-and-forget pattern prevents auth failures from merge errors

### Performance

- [ ] Guest dashboard loads in <200ms
- [ ] Vocabulary capture adds <50ms to chat response
- [ ] Merge operation completes within request timeout

---

## Appendix: Repository Client Parameter Pattern

Repositories accept an optional client parameter to support both authenticated and guest access:

```python
class VocabularyRepository:
    """Data access for vocabulary table."""

    def __init__(self, user_id: str, client: SupabaseClient | None = None) -> None:
        """Initialize repository for a specific user.

        Args:
            user_id: Supabase auth user UUID or guest session UUID.
            client: Optional Supabase client. Defaults to anon client.
                    Pass admin client for guest (session-based) access.
        """
        self._user_id = user_id
        self._client = client or get_supabase()
```

This pattern allows the same repository code to work for both user types, with the calling code responsible for selecting the appropriate client based on identity type.
