# Conversation Threads Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a sidebar thread list so authenticated users can create, switch between, and manage multiple conversation threads, each with its own LangGraph checkpoint history.

**Architecture:** New `conversation_threads` Supabase table stores thread metadata (title, language, level, timestamps). Existing LangGraph checkpoint tables store conversation data — no duplication. A `ThreadService` handles CRUD, new API endpoints serve the sidebar, and a slide-out sidebar UI (HTMX + Alpine.js) provides thread management. Auto-titling via Haiku generates thread titles after the first exchange.

**Tech Stack:** FastAPI, Supabase (Postgres + RLS), LangGraph checkpoints, HTMX, Alpine.js, Tailwind CSS, Jinja2 templates, Vitest (JS tests), pytest (Python tests)

**Design doc:** `docs/design/phase26-conversation-threads.md`

---

## Task 1: Database Migration & Pydantic Model

**Files:**
- Create: `migrations/005_conversation_threads.sql`
- Modify: `src/db/models.py`

**Step 1: Write the migration**

```sql
-- migrations/005_conversation_threads.sql
-- Phase 26: Conversation threads metadata table

CREATE TABLE conversation_threads (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    thread_id   TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL DEFAULT 'New conversation',
    language    TEXT NOT NULL DEFAULT 'es',
    level       TEXT NOT NULL DEFAULT 'A1',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE conversation_threads ENABLE ROW LEVEL SECURITY;

CREATE POLICY threads_user_policy ON conversation_threads
  FOR ALL USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

CREATE POLICY threads_service_policy ON conversation_threads
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE INDEX idx_threads_user_updated ON conversation_threads(user_id, updated_at DESC);
```

**Step 2: Add Pydantic model to `src/db/models.py`**

```python
class ConversationThread(BaseModel):
    """Conversation thread metadata for the sidebar thread list."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    thread_id: str
    title: str = "New conversation"
    language: str = "es"
    level: str = "A1"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

**Step 3: Commit**

```bash
git add migrations/005_conversation_threads.sql src/db/models.py
git commit -m "feat(db): add conversation_threads table and model"
```

---

## Task 2: Thread Service (CRUD)

**Files:**
- Create: `src/services/threads.py`
- Create: `tests/services/test_threads.py`

**Step 1: Write failing tests for ThreadService**

Test file: `tests/services/test_threads.py`

Test cases needed:
- `test_create_thread` — creates a thread, returns ConversationThread with correct user_id, language, level, generated thread_id
- `test_list_threads_empty` — returns empty list for new user
- `test_list_threads_ordered_by_updated` — most recently updated first
- `test_get_thread` — retrieves by thread ID
- `test_get_thread_not_found` — returns None for missing thread
- `test_update_title` — renames a thread
- `test_touch_updates_timestamp` — touch() updates updated_at
- `test_delete_thread` — removes the row
- `test_delete_nonexistent_thread` — no error on missing thread

Mock the Supabase client following existing test patterns (see `tests/conftest.py` for mock setup patterns — PostgREST chain mocking).

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/services/test_threads.py -v
```

Expected: FAIL (module not found)

**Step 3: Implement ThreadService**

Create `src/services/threads.py`:

```python
class ThreadService:
    """CRUD operations for conversation thread metadata."""

    TABLE = "conversation_threads"

    def __init__(self, user_id: str, client: SupabaseClient) -> None:
        self._user_id = user_id
        self._client = client

    def create_thread(self, language: str = "es", level: str = "A1") -> ConversationThread:
        """Create a new thread with a generated thread_id."""

    def list_threads(self) -> list[ConversationThread]:
        """List all threads for user, ordered by updated_at DESC."""

    def get_thread(self, thread_id: str) -> ConversationThread | None:
        """Get a single thread by its LangGraph thread_id."""

    def update_title(self, thread_id: str, title: str) -> None:
        """Rename a thread."""

    def touch(self, thread_id: str) -> None:
        """Update updated_at to now (called on each message)."""

    def delete_thread(self, thread_id: str) -> None:
        """Delete thread metadata row."""
```

Thread ID generation: `f"user:{user_id}:{uuid4()}"` — same format as existing `conversation_version` approach but explicitly managed.

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/services/test_threads.py -v
```

**Step 5: Commit**

```bash
git add src/services/threads.py tests/services/test_threads.py
git commit -m "feat(services): add ThreadService for conversation thread CRUD"
```

---

## Task 3: Thread API Endpoints

**Files:**
- Create: `src/api/routes/threads.py`
- Modify: `src/api/main.py` (register router)
- Create: `tests/api/test_threads.py`

**Step 1: Write failing tests for thread endpoints**

Test file: `tests/api/test_threads.py`

Test cases:
- `test_list_threads_unauthenticated` — returns 401
- `test_list_threads_empty` — returns empty JSON array
- `test_create_thread` — POST returns new thread JSON
- `test_create_thread_with_language` — respects language param
- `test_rename_thread` — PATCH updates title
- `test_rename_thread_not_found` — 404
- `test_delete_thread` — DELETE returns 204
- `test_delete_thread_not_found` — 204 (idempotent)

Use the test client from `tests/conftest.py`. All POST/PATCH/DELETE need `CSRF_HEADERS`.

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/api/test_threads.py -v
```

**Step 3: Implement thread router**

Create `src/api/routes/threads.py`:

```python
router = APIRouter(prefix="/threads", tags=["threads"])

@router.get("/")
async def list_threads(user: CurrentUserDep, ...) -> list[dict]:
    """List user's conversation threads."""

@router.post("/", status_code=201)
async def create_thread(user: CurrentUserDep, ...) -> dict:
    """Create a new conversation thread."""

@router.patch("/{thread_id}")
async def rename_thread(thread_id: str, user: CurrentUserDep, ...) -> dict:
    """Rename a thread."""

@router.delete("/{thread_id}", status_code=204)
async def delete_thread(thread_id: str, user: CurrentUserDep, ...) -> Response:
    """Delete a thread."""
```

**Step 4: Register router in `src/api/main.py`**

Add: `from src.api.routes import threads` and `app.include_router(threads.router)`.

**Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/api/test_threads.py -v
```

**Step 6: Commit**

```bash
git add src/api/routes/threads.py src/api/main.py tests/api/test_threads.py
git commit -m "feat(api): add thread CRUD endpoints"
```

---

## Task 4: Integrate Threads into Chat Flow

**Files:**
- Modify: `src/api/routes/chat.py`
- Modify: `tests/api/test_chat.py` (update affected tests)

**Step 1: Modify `_resolve_chat_identity()` to accept explicit thread_id**

When an authenticated user sends a `thread_id` form field:
1. Validate the thread exists and belongs to the user (via ThreadService)
2. Use that thread_id directly instead of the cookie-based `conversation_version` approach
3. Call `thread_service.touch(thread_id)` to update `updated_at`

When no `thread_id` is provided (first message / new user):
1. Auto-create a thread via ThreadService
2. Return the new thread_id

**Step 2: Add `thread_id` form field to `stream_message()`**

Add `thread_id: Annotated[str | None, Form()] = None` parameter.

**Step 3: Remove `conversation_version` cookie dependency**

Remove the `conversation_version` cookie parameter from `stream_message()` and `send_message()`. Keep backward compat: if `conversation_version` cookie is present but no `thread_id` form field, ignore the cookie (users will start fresh with threads).

**Step 4: Update `POST /new` to create a thread**

Modify `new_conversation()` to create a thread row and redirect to `/?thread={thread_id}` instead of setting a cookie.

**Step 5: Update tests**

Update existing chat tests that rely on `conversation_version` cookie.

**Step 6: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short
```

**Step 7: Commit**

```bash
git add src/api/routes/chat.py tests/api/test_chat.py
git commit -m "feat(chat): integrate thread_id into chat flow, replace conversation_version cookie"
```

---

## Task 5: Message History Loading

**Files:**
- Create: `src/services/thread_messages.py`
- Create: `tests/services/test_thread_messages.py`
- Create: `src/templates/partials/thread_history.html`

**Step 1: Write failing tests for message history extraction**

Test cases:
- `test_get_messages_empty_thread` — returns empty list
- `test_get_messages_with_history` — returns list of {role, content} dicts
- `test_get_messages_filters_system_messages` — excludes system messages

**Step 2: Implement `get_thread_messages()`**

```python
async def get_thread_messages(thread_id: str) -> list[dict[str, str]]:
    """Extract message history from a LangGraph checkpoint."""
    async with get_checkpointer() as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        state = await graph.aget_state(
            RunnableConfig(configurable={"thread_id": thread_id})
        )
        if not state or not state.values.get("messages"):
            return []
        return [
            {"role": "human" if isinstance(m, HumanMessage) else "ai",
             "content": m.content}
            for m in state.values["messages"]
            if isinstance(m, (HumanMessage, AIMessage))
        ]
```

**Step 3: Create `thread_history.html` partial**

Renders message history as chat bubbles (same styling as streaming bubbles from `stream.js`). This partial is returned when loading an existing thread.

**Step 4: Run tests**

```bash
python -m pytest tests/services/test_thread_messages.py -v
```

**Step 5: Commit**

```bash
git add src/services/thread_messages.py tests/services/test_thread_messages.py src/templates/partials/thread_history.html
git commit -m "feat: add message history loading for thread switching"
```

---

## Task 6: Chat Page Thread Loading

**Files:**
- Modify: `src/api/routes/chat.py` (GET /)
- Modify: `src/templates/chat.html`

**Step 1: Accept `thread` query param in GET /**

When `/?thread={thread_id}` is requested:
1. Validate thread belongs to user
2. Load message history via `get_thread_messages()`
3. Pass `messages`, `active_thread_id`, and thread metadata to template

**Step 2: Update `chat.html` to render preloaded messages**

If `messages` context is present, render them in `#chat-messages` instead of the welcome message. Pass `active_thread_id` as a hidden form field so subsequent messages use the correct thread.

**Step 3: Pass thread list to template**

Load `thread_service.list_threads()` and pass as `threads` context variable for sidebar rendering.

**Step 4: Test manually and update existing tests**

```bash
python -m pytest tests/api/test_chat.py -v
```

**Step 5: Commit**

```bash
git add src/api/routes/chat.py src/templates/chat.html
git commit -m "feat(chat): load thread history and thread list on page load"
```

---

## Task 7: Sidebar Template (Desktop + Mobile)

**Files:**
- Create: `src/templates/partials/thread_sidebar.html`
- Modify: `src/templates/chat.html` (include sidebar)
- Modify: `src/templates/partials/app_header.html` (hamburger triggers sidebar on mobile)

**Step 1: Create sidebar partial**

`src/templates/partials/thread_sidebar.html`:

Structure:
- Only rendered when `user` is present (authenticated)
- Alpine.js `x-data` for sidebar state (open/collapsed)
- "New Chat" button at top (POST /threads via HTMX, redirect on response)
- Thread list grouped by recency (Today / Yesterday / Previous 7 Days / Older)
- Each thread item: title (truncated), language flag, relative time
- Active thread highlighted (`active_thread_id` comparison)
- Context menu on each thread: Rename (inline edit), Delete (with confirm)
- Desktop: fixed left panel, 280px wide, collapsible to 40px icon rail
- Mobile: slide-out overlay drawer, swipe-to-close

**Step 2: Include sidebar in `chat.html`**

Add `{% include "partials/thread_sidebar.html" %}` in the layout. Adjust chat container to flex alongside sidebar.

Layout change:
```html
<div class="flex h-screen">
  {% if user %}{% include "partials/thread_sidebar.html" %}{% endif %}
  <div class="flex-1 flex flex-col">
    <!-- existing header + chat + input -->
  </div>
</div>
```

**Step 3: Update hamburger menu for mobile**

On mobile, hamburger button toggles the sidebar drawer instead of the current dropdown menu. Move theme/auth links to bottom of sidebar.

**Step 4: Commit**

```bash
git add src/templates/partials/thread_sidebar.html src/templates/chat.html src/templates/partials/app_header.html
git commit -m "feat(ui): add conversation thread sidebar for desktop and mobile"
```

---

## Task 8: Thread Switching (Client-Side JS)

**Files:**
- Modify: `src/static/js/modules/stream.js`
- Modify: `src/static/js/modules/dom.js`
- Modify: `src/static/js/modules/shortcuts.js`
- Create: `tests/js/threads.test.js`

**Step 1: Write JS tests for thread switching behavior**

Test cases:
- Thread click navigates to `/?thread={id}`
- New Chat button creates thread and navigates
- Active thread is highlighted
- Thread rename submits PATCH and updates DOM
- Thread delete submits DELETE and removes from list

**Step 2: Update `stream.js`**

- Read `thread_id` from hidden form field and include in FormData for `/chat/stream`
- Handle `thread_title` SSE event (update sidebar thread title)

**Step 3: Update `dom.js`**

- Add `clearChatMessages()` utility for thread switching
- Add `updateActiveThread(threadId)` to highlight active thread in sidebar

**Step 4: Update `shortcuts.js`**

- Cmd/Ctrl+Shift+N creates new thread (POST /threads) instead of POST /new
- Cmd/Ctrl+Shift+S toggles sidebar visibility

**Step 5: Run JS tests**

```bash
npx vitest run tests/js/threads.test.js
```

**Step 6: Commit**

```bash
git add src/static/js/modules/stream.js src/static/js/modules/dom.js src/static/js/modules/shortcuts.js tests/js/threads.test.js
git commit -m "feat(js): add thread switching, renaming, and keyboard shortcuts"
```

---

## Task 9: Auto-Titling

**Files:**
- Create: `src/services/thread_titling.py`
- Create: `tests/services/test_thread_titling.py`
- Modify: `src/api/routes/chat.py` (trigger after first exchange)
- Modify: `src/api/streaming.py` (emit `thread_title` SSE event)

**Step 1: Write failing tests for title generation**

Test cases:
- `test_generate_title_returns_short_string` — 3-5 words
- `test_generate_title_from_messages` — uses first human + AI message
- `test_generate_title_updates_thread` — calls `thread_service.update_title()`

Mock the LLM call.

**Step 2: Implement auto-titling**

```python
async def generate_thread_title(
    human_message: str, ai_response: str
) -> str:
    """Generate a 3-5 word conversation title via Haiku."""
    from src.agent.llm import get_llm  # reuse existing LLM factory

    llm = get_llm(model="claude-haiku-4-5-20251001")
    result = await llm.ainvoke(
        f"Generate a 3-5 word title for this conversation. "
        f"Return ONLY the title, no quotes or punctuation.\n\n"
        f"User: {human_message[:200]}\n"
        f"Assistant: {ai_response[:200]}"
    )
    return result.content.strip()[:50]
```

**Step 3: Trigger after first exchange in `stream_message()`**

After the first message in a new thread (thread has default title "New conversation"):
1. Call `generate_thread_title()` with the user message and AI response
2. Update the thread row
3. Emit a `thread_title` SSE event with `{thread_id, title}`

**Step 4: Run tests**

```bash
python -m pytest tests/services/test_thread_titling.py -v
```

**Step 5: Commit**

```bash
git add src/services/thread_titling.py tests/services/test_thread_titling.py src/api/routes/chat.py src/api/streaming.py
git commit -m "feat: auto-generate thread titles via Haiku after first exchange"
```

---

## Task 10: Polish & Integration Testing

**Files:**
- Modify: `src/templates/partials/conversation_header.html` (remove old new-conversation button)
- Modify: `src/api/routes/chat.py` (clean up old conversation_version references)
- Create: `tests/integration/test_thread_lifecycle.py`

**Step 1: Remove old conversation_version cookie logic**

- Remove `conversation_version` cookie params from `send_message()` and `stream_message()`
- Remove `_CONVERSATION_VERSION_MAX_AGE` constant
- Update `POST /new` to redirect to thread creation (or remove entirely if sidebar replaces it)
- Clean up `conversation_header.html` (the "Thread active" indicator can show actual thread title now)

**Step 2: Write integration test for full thread lifecycle**

```python
async def test_thread_lifecycle():
    """Create thread → send message → switch thread → resume."""
    # 1. Create thread
    # 2. Send message to thread
    # 3. Verify thread.updated_at changed
    # 4. Create second thread
    # 5. List threads — both present, ordered by updated_at
    # 6. Load first thread — message history present
```

**Step 3: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short
make check  # lint + format + typecheck
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: conversation threads polish and integration tests"
```

---

## Parallelization Map

These tasks can be worked on in parallel by independent subagents:

```
Task 1 (DB migration + model) ──────┐
                                     ├──→ Task 4 (chat flow integration)
Task 2 (ThreadService CRUD) ────────┤
                                     ├──→ Task 5 (message history loading)
Task 3 (API endpoints) ─────────────┘
                                          ↓
Task 7 (sidebar template) ──────────→ Task 8 (client-side JS)
                                          ↓
Task 6 (chat page loading) ─────────→ Task 9 (auto-titling)
                                          ↓
                                     Task 10 (polish + integration)
```

**Parallel group 1** (no dependencies): Tasks 1, 2, 3 — all foundational, can be built simultaneously
**Parallel group 2** (depends on group 1): Tasks 4, 5, 7 — integration, history, UI
**Parallel group 3** (depends on group 2): Tasks 6, 8, 9 — page loading, JS, auto-titling
**Sequential finale**: Task 10 — integration testing after everything is merged

---

## Key Implementation Notes

- **Existing test patterns**: See `tests/conftest.py` for `CSRF_HEADERS`, Supabase mock setup (PostgREST chain pattern), and fixture conventions
- **Auth dependency**: Thread endpoints use `CurrentUserDep` (not `OptionalUserDep`) — threads are auth-only
- **Supabase client**: Use `get_supabase_for_user(sb_access_token)` for RLS-compliant queries
- **CSRF**: All POST/PATCH/DELETE need `HX-Request: true` or `X-Requested-With: XMLHttpRequest` header
- **Thread ID format**: `user:{user_id}:{uuid4}` — consistent with existing checkpoint_owner() RLS function
- **Encryption**: Thread title is plain text (not PII), no encryption needed. Thread_id links to encrypted checkpoints.
