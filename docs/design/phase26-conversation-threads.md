# Phase 26: Conversation Threads

## Overview

Add a sidebar thread list so authenticated users can create, switch between, and manage multiple conversation threads. Each thread maintains its own LangGraph checkpoint history, language, and level context.

Guests keep the current single-conversation experience (no changes).

## Motivation

In a language tutor, conversation **context is pedagogically valuable**. The AI remembers vocabulary practiced, mistakes made, and topics discussed. The current single-conversation model forces users to lose that context when starting fresh. Threads let users:

- **Separate conversations by language** — Spanish thread, German thread, French thread
- **Topic-based practice** — "Restaurant ordering" vs "Job interview", each maintaining topical vocabulary
- **Resume where they left off** — return to a conversation from yesterday about travel vocabulary

## Approach

**Metadata table + existing checkpoints** (Approach A). A thin `conversation_threads` table in Supabase stores thread metadata (title, language, timestamps). Conversation data stays in LangGraph's checkpoint tables — no duplication. The `thread_id` column bridges the two systems.

## Data Model

### New table: `conversation_threads`

```sql
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

### Pydantic model

```python
class ConversationThread(BaseModel):
    id: str
    user_id: str
    thread_id: str
    title: str = "New conversation"
    language: str = "es"
    level: str = "A1"
    created_at: datetime
    updated_at: datetime
```

### Thread ID format

Existing format preserved: `user:{user_id}:{thread_uuid}`. The `conversation_version` cookie is replaced by an explicit `thread_id` parameter.

### Auto-titling

After the first AI response in a new thread, the system generates a short title (3-5 words) summarizing the conversation topic. This is done as a lightweight LLM call (Haiku) after the main response completes, so it doesn't block chat.

## API Design

### New endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/threads` | List user's threads (JSON, ordered by `updated_at` DESC) |
| POST | `/threads` | Create new thread, return thread metadata |
| PATCH | `/threads/{id}` | Rename thread |
| DELETE | `/threads/{id}` | Delete thread (soft: just removes metadata row) |

### Modified endpoints

| Endpoint | Change |
|----------|--------|
| `GET /` | Accept `?thread={id}` query param to load a specific thread |
| `POST /chat/stream` | Accept `thread_id` form field instead of relying on `conversation_version` cookie |
| `POST /new` | Replaced by `POST /threads` — creates a thread row and redirects |

### Thread list response

```json
[
  {
    "id": "uuid",
    "title": "Ordering at a restaurant",
    "language": "es",
    "level": "A1",
    "updated_at": "2026-03-15T14:30:00Z"
  }
]
```

## UI Design

### Sidebar (authenticated users only)

- **Desktop (≥768px)**: Fixed left sidebar, 280px wide. Chat area shifts right.
- **Mobile (<768px)**: Slide-out drawer from left edge, overlay on chat. Triggered by hamburger menu or swipe-right gesture.
- Sidebar contains:
  1. **"New Chat" button** at top (accent colored, prominent)
  2. **Thread list** grouped by recency: Today, Yesterday, Previous 7 Days, Older
  3. Each thread item shows: title (truncated), language flag emoji, relative timestamp
  4. Active thread highlighted with accent background
  5. Thread item has context menu (long-press on mobile, right-click on desktop): Rename, Delete
- **Collapse/expand**: Desktop sidebar can be collapsed to icon-only rail (40px) via toggle button

### Thread switching

- Clicking a thread navigates to `/?thread={id}`
- Chat messages area clears and loads the thread's checkpoint history
- Language/level selectors update to match the thread's settings
- No full page reload — HTMX partial swap of chat container

### Loading previous messages

When switching to an existing thread, the server extracts messages from the LangGraph checkpoint state and renders them as HTML partials. This is a new capability — currently the chat page always starts empty.

### Header changes

- Hamburger menu loses the "Free Chat" link (replaced by sidebar's "New Chat")
- On mobile, hamburger opens the thread sidebar instead of the current dropdown menu
- Theme selector, auth links move into a settings area at the bottom of the sidebar

## Backend Architecture

### Thread service (`src/services/threads.py`)

```python
class ThreadService:
    def __init__(self, user_id: str, client: Client):
        ...

    def list_threads(self) -> list[ConversationThread]:
        """List all threads for user, ordered by updated_at DESC."""

    def create_thread(self, language: str, level: str) -> ConversationThread:
        """Create a new thread with generated thread_id."""

    def get_thread(self, thread_id: str) -> ConversationThread | None:
        """Get a single thread by ID."""

    def update_title(self, thread_id: str, title: str) -> None:
        """Rename a thread."""

    def touch(self, thread_id: str) -> None:
        """Update updated_at timestamp (called on each message)."""

    def delete_thread(self, thread_id: str) -> None:
        """Delete thread metadata (checkpoints are orphaned, not deleted)."""
```

### Auto-title generation

After the first exchange in a new thread:
1. Extract the user's first message + AI's first response
2. Call Haiku with a simple prompt: "Generate a 3-5 word title for this conversation"
3. Update the thread row with the generated title
4. Push the title to the client via an SSE event (`thread_title` event)

### Message history loading

New utility to extract messages from a LangGraph checkpoint:

```python
async def get_thread_messages(thread_id: str) -> list[dict]:
    """Load message history from checkpoint for rendering."""
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
        ]
```

### Conversation version cookie removal

The `conversation_version` cookie mechanism is replaced entirely. Thread identity is now explicit via the `thread_id` parameter. Backward compatibility: existing `conversation_version` cookies are ignored; users start with an empty thread list and create new threads going forward.

## Migration Path

1. Deploy migration creating `conversation_threads` table
2. No data migration needed — existing conversations are not retroactively imported (clean start)
3. Remove `conversation_version` cookie logic from `_resolve_chat_identity()`
4. First visit after deploy: user sees empty sidebar with "New Chat" prompt

## Scope Boundaries

### In scope
- Thread CRUD (create, list, rename, delete)
- Sidebar UI (desktop fixed, mobile drawer)
- Thread switching with message history loading
- Auto-titling via LLM
- `updated_at` touch on each message

### Out of scope (future phases)
- Thread search/filter
- Thread export
- Pinned/starred threads
- Thread sharing between users
- Archiving threads
- Guest thread support

## Testing Strategy

- **Python unit tests**: ThreadService CRUD operations, thread_id generation, auto-titling
- **API tests**: Thread endpoints (list, create, rename, delete), auth enforcement
- **JS tests**: Sidebar rendering, thread switching, mobile drawer behavior
- **Integration**: End-to-end thread lifecycle (create → chat → switch → resume)
