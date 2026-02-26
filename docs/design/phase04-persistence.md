# Phase 4: Persistence Design Document

> LangGraph checkpointing for conversation memory and session continuity

---

## Overview

Phase 4 adds persistence to Habla Hermano using LangGraph's checkpointing system. This enables:
- **Conversation continuity**: Resume conversations across browser sessions
- **Message history**: View and continue previous conversations
- **Thread isolation**: Multiple independent conversation threads

**Learning Goal**: Master LangGraph's SqliteSaver checkpointer and thread_id configuration.

---

## Requirements

### Functional Requirements

| Requirement | Priority | Description |
|-------------|----------|-------------|
| Conversation persistence | P0 | Conversations saved to SQLite, resume on return |
| Thread ID management | P0 | Unique thread per conversation, stored in session |
| New conversation | P0 | User can start fresh conversation anytime |
| Conversation history | P1 | List previous conversations, click to resume |

### Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Latency overhead | <50ms for checkpoint operations |
| Storage | SQLite file in `data/` directory |
| Async support | Full async with AsyncSqliteSaver |

---

## Architecture

### LangGraph Checkpointing

LangGraph checkpointing saves graph state after each node execution. Key concepts:

1. **Checkpointer**: Storage backend (AsyncSqliteSaver for async support)
2. **Thread ID**: Unique identifier for conversation isolation
3. **Config**: Passed to `ainvoke()` with `configurable.thread_id`

### Component Design

```
┌─────────────────────────────────────────────────────────────┐
│                      Browser Session                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Cookie: thread_id = "uuid-xxx"                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Routes                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  GET /              → Chat page (get/create thread)  │   │
│  │  POST /chat         → Send message (with thread_id)  │   │
│  │  POST /new          → Start new conversation         │   │
│  │  GET /history       → List previous threads          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph + Checkpointer                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  graph.ainvoke(                                       │   │
│  │      {"messages": [...], "level": "A1", ...},        │   │
│  │      config={"configurable": {"thread_id": "xxx"}}   │   │
│  │  )                                                    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    AsyncSqliteSaver                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  data/checkpoints.db                                  │   │
│  │  - checkpoint table (state snapshots)                 │   │
│  │  - checkpoint_writes table (pending writes)           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **First visit**: Generate UUID thread_id, store in session cookie
2. **Send message**: Include thread_id in graph config
3. **Graph execution**: Checkpointer saves state after each node
4. **Return visit**: Read thread_id from cookie, resume conversation
5. **New conversation**: Generate new thread_id, clear old cookie

---

## Implementation Plan

### Task 1: Checkpointer Setup

**File**: `src/agent/checkpointer.py`

```python
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from contextlib import asynccontextmanager

# Connection string for SQLite database
CHECKPOINT_DB = "data/checkpoints.db"

@asynccontextmanager
async def get_checkpointer():
    """Get async SQLite checkpointer for LangGraph persistence."""
    async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB) as saver:
        yield saver
```

### Task 2: Update Graph Builder

**File**: `src/agent/graph.py`

```python
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

def build_graph(checkpointer: AsyncSqliteSaver | None = None) -> CompiledStateGraph:
    """Build graph with optional checkpointer for persistence."""
    graph = StateGraph(ConversationState)
    # ... nodes and edges ...
    return graph.compile(checkpointer=checkpointer)
```

### Task 3: Thread ID Management

**File**: `src/api/session.py`

```python
import uuid
from fastapi import Request, Response

THREAD_COOKIE = "habla_thread_id"

def get_thread_id(request: Request) -> str:
    """Get thread_id from cookie or generate new one."""
    return request.cookies.get(THREAD_COOKIE) or str(uuid.uuid4())

def set_thread_id(response: Response, thread_id: str) -> None:
    """Set thread_id cookie."""
    response.set_cookie(
        key=THREAD_COOKIE,
        value=thread_id,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,  # 30 days
    )

def clear_thread_id(response: Response) -> None:
    """Clear thread_id cookie for new conversation."""
    response.delete_cookie(key=THREAD_COOKIE)
```

### Task 4: Update Chat Routes

**File**: `src/api/routes/chat.py`

```python
@router.post("/chat")
async def send_message(
    request: Request,
    response: Response,
    message: str = Form(...),
    level: str = Form("A1"),
    language: str = Form("es"),
):
    thread_id = get_thread_id(request)
    set_thread_id(response, thread_id)

    async with get_checkpointer() as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=message)], "level": level, "language": language},
            config={"configurable": {"thread_id": thread_id}}
        )
    # ... render response
```

### Task 5: New Conversation Endpoint

**File**: `src/api/routes/chat.py`

```python
@router.post("/new")
async def new_conversation(response: Response):
    """Start a new conversation by clearing thread_id."""
    clear_thread_id(response)
    response.headers["HX-Redirect"] = "/"
    return Response(status_code=200)
```

### Task 6: Conversation History (P1)

**File**: `src/api/routes/chat.py`

```python
@router.get("/history")
async def list_conversations(request: Request, templates: TemplatesDep):
    """List previous conversation threads."""
    # Query checkpointer for thread summaries
    # Return partial HTML for HTMX
```

---

## Testing Strategy

### Unit Tests

| Test | Description |
|------|-------------|
| `test_checkpointer_saves_state` | Verify state persisted after graph invoke |
| `test_thread_isolation` | Different threads have independent state |
| `test_resume_conversation` | Same thread_id resumes message history |
| `test_new_conversation_clears_thread` | New conversation starts fresh |

### Integration Tests

| Test | Description |
|------|-------------|
| `test_chat_persists_across_requests` | Multiple POST /chat with same thread |
| `test_new_conversation_endpoint` | POST /new clears and redirects |
| `test_session_cookie_management` | Cookie set/read correctly |

### E2E Tests

| Test | Description |
|------|-------------|
| Conversation continuity | Send messages, refresh, send more |
| New conversation button | Click new, verify fresh start |
| History navigation | List threads, click to resume |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| SQLite file corruption | Use WAL mode, regular backups |
| Large checkpoint files | Periodic cleanup of old threads |
| Async context management | Proper `async with` patterns |
| Cookie security | httponly, samesite flags |

---

## Dependencies

- `langgraph-checkpoint` - Already in pyproject.toml
- `aiosqlite` - Already in pyproject.toml (for async SQLite)

No new dependencies required.

---

## Success Criteria

- [ ] Conversations persist across browser refreshes
- [ ] Multiple conversations can exist independently
- [ ] "New Conversation" starts fresh thread
- [ ] All existing tests still pass
- [ ] <50ms latency overhead from checkpointing
