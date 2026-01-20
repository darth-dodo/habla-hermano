# Phase 5: Supabase Authentication & Persistence Design Document

> Production-ready multi-user support with Supabase Auth, Postgres, and LangGraph PostgresSaver

---

## Overview

Phase 5 transforms Habla Hermano from an anonymous single-user application to a production-ready multi-user platform. This enables:

- **User Authentication**: Email/password signup and login via Supabase Auth
- **Data Persistence**: All user data stored in Supabase Postgres
- **Conversation Continuity**: LangGraph checkpointing via PostgresSaver
- **User Isolation**: Row Level Security ensures users only access their own data

**Learning Goal**: Master Supabase Auth integration with FastAPI and LangGraph PostgresSaver for production checkpointing.

**Related ADR**: [ADR-001: Supabase Integration](../adr/ADR-001-supabase-integration.md)

---

## Requirements

### Functional Requirements

| Requirement | Priority | Description |
|-------------|----------|-------------|
| Email/password auth | P0 | Users signup/login with email and password |
| Session management | P0 | JWT tokens in httponly cookies, 7-day expiry |
| Single conversation | P0 | One persistent conversation per user |
| Protected routes | P0 | Chat requires authentication |
| Logout | P0 | Clear session and redirect to login |
| New conversation | P1 | Reset conversation while keeping account |

### Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Auth latency | <200ms for login/signup |
| Database latency | <100ms for queries |
| Security | JWT validation, RLS, httponly cookies |
| Scalability | Support 1000+ concurrent users |

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (HTMX)                            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Cookie: sb-access-token (JWT)                              │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Auth Middleware                                            │ │
│  │  - Extract JWT from cookie                                  │ │
│  │  - Validate with Supabase JWT secret                        │ │
│  │  - Provide CurrentUserDep dependency                        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Protected Routes                                           │ │
│  │  GET  /           → Chat page (requires auth)               │ │
│  │  POST /chat       → Send message (requires auth)            │ │
│  │  POST /new        → Reset conversation (requires auth)      │ │
│  │  GET  /auth/login → Login page (public)                     │ │
│  │  POST /auth/login → Authenticate (public)                   │ │
│  │  GET  /auth/signup→ Signup page (public)                    │ │
│  │  POST /auth/signup→ Create account (public)                 │ │
│  │  POST /auth/logout→ Clear session (public)                  │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Supabase                                  │
│  ┌──────────────────┐  ┌──────────────────────────────────────┐ │
│  │  Supabase Auth   │  │  Supabase Postgres                   │ │
│  │  - Email/pass    │  │  - user_profiles (RLS)               │ │
│  │  - JWT tokens    │  │  - vocabulary (RLS)                  │ │
│  │  - User mgmt     │  │  - learning_sessions (RLS)           │ │
│  └──────────────────┘  │  - lesson_progress (RLS)             │ │
│                        │  - checkpoint tables (PostgresSaver)  │ │
│                        └──────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Authentication Flow

```
                    SIGNUP FLOW
┌─────────┐    ┌─────────┐    ┌─────────────┐    ┌──────────┐
│ Browser │───►│ FastAPI │───►│ Supabase    │───►│ Postgres │
│         │    │         │    │ Auth        │    │          │
└─────────┘    └─────────┘    └─────────────┘    └──────────┘
     │              │               │                  │
     │  POST /auth/signup           │                  │
     │  {email, password}           │                  │
     │─────────────►│               │                  │
     │              │  supabase.auth.sign_up()         │
     │              │──────────────►│                  │
     │              │               │  INSERT user     │
     │              │               │─────────────────►│
     │              │               │                  │
     │              │  {access_token, user}            │
     │              │◄──────────────│                  │
     │              │               │                  │
     │  Set-Cookie: sb-access-token │                  │
     │  HX-Redirect: /              │                  │
     │◄─────────────│               │                  │


                    LOGIN FLOW
┌─────────┐    ┌─────────┐    ┌─────────────┐
│ Browser │───►│ FastAPI │───►│ Supabase    │
│         │    │         │    │ Auth        │
└─────────┘    └─────────┘    └─────────────┘
     │              │               │
     │  POST /auth/login            │
     │  {email, password}           │
     │─────────────►│               │
     │              │  supabase.auth.sign_in_with_password()
     │              │──────────────►│
     │              │               │
     │              │  {access_token, user}
     │              │◄──────────────│
     │              │               │
     │  Set-Cookie: sb-access-token │
     │  HX-Redirect: /              │
     │◄─────────────│               │


                    PROTECTED ROUTE FLOW
┌─────────┐    ┌─────────┐    ┌─────────────┐
│ Browser │───►│ FastAPI │───►│ Supabase    │
│         │    │         │    │ Postgres    │
└─────────┘    └─────────┘    └─────────────┘
     │              │               │
     │  POST /chat                  │
     │  Cookie: sb-access-token     │
     │─────────────►│               │
     │              │               │
     │              │  JWT decode + validate
     │              │  user_id = payload["sub"]
     │              │               │
     │              │  thread_id = f"user:{user_id}"
     │              │               │
     │              │  PostgresSaver.get(thread_id)
     │              │──────────────►│
     │              │               │
     │              │  LangGraph invoke with checkpointer
     │              │               │
     │              │  PostgresSaver.put(thread_id, state)
     │              │──────────────►│
     │              │               │
     │  HTML response               │
     │◄─────────────│               │
```

### Data Flow

1. **Signup**: User submits email/password → Supabase creates auth.user → Trigger creates user_profile → JWT returned in cookie
2. **Login**: User submits credentials → Supabase validates → JWT returned in cookie
3. **Chat**: JWT extracted → User ID derived → Thread ID = `user:{user_id}` → LangGraph uses PostgresSaver
4. **Logout**: Cookie cleared → Redirect to login

---

## Database Schema

### Tables

```sql
-- User profiles (auto-created via trigger on auth.users)
CREATE TABLE public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT,
    preferred_language TEXT DEFAULT 'es',
    current_level TEXT DEFAULT 'A1',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vocabulary tracking
CREATE TABLE public.vocabulary (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    word TEXT NOT NULL,
    translation TEXT NOT NULL,
    language TEXT NOT NULL,
    part_of_speech TEXT,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    times_seen INTEGER DEFAULT 1,
    times_correct INTEGER DEFAULT 0,
    UNIQUE(user_id, word, language)
);

-- Learning session tracking
CREATE TABLE public.learning_sessions (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    language TEXT NOT NULL,
    level TEXT NOT NULL,
    messages_count INTEGER DEFAULT 0,
    words_learned INTEGER DEFAULT 0
);

-- Lesson progress (for future micro-lessons feature)
CREATE TABLE public.lesson_progress (
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    lesson_id TEXT NOT NULL,
    completed_at TIMESTAMPTZ,
    score INTEGER,
    PRIMARY KEY (user_id, lesson_id)
);

-- Auto-create user profile trigger
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_profiles (id)
    VALUES (NEW.id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

### Row Level Security Policies

```sql
-- Enable RLS on all tables
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vocabulary ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.learning_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lesson_progress ENABLE ROW LEVEL SECURITY;

-- Users can only access their own data
CREATE POLICY "Users can view own profile"
    ON public.user_profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON public.user_profiles FOR UPDATE
    USING (auth.uid() = id);

CREATE POLICY "Users can manage own vocabulary"
    ON public.vocabulary FOR ALL
    USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own sessions"
    ON public.learning_sessions FOR ALL
    USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own progress"
    ON public.lesson_progress FOR ALL
    USING (auth.uid() = user_id);
```

---

## Implementation Plan

### Task 1: Dependencies and Configuration

**File**: `pyproject.toml`

```toml
dependencies = [
    # ... existing deps ...
    "supabase>=2.0.0",
    "PyJWT>=2.8.0",
    "langgraph-checkpoint-postgres>=2.0.0",
    "psycopg[binary,pool]>=3.1.0",
]
```

**File**: `src/api/config.py`

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_JWT_SECRET: str
    SUPABASE_DB_URL: str
```

**File**: `.env.example`

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key
SUPABASE_JWT_SECRET=your-jwt-secret
SUPABASE_DB_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres
```

### Task 2: Supabase Client

**File**: `src/api/supabase_client.py`

```python
"""Supabase client singleton for database and auth operations."""

from functools import lru_cache

from supabase import Client, create_client

from src.api.config import get_settings


@lru_cache
def get_supabase() -> Client:
    """Get Supabase client singleton."""
    settings = get_settings()
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_ANON_KEY,
    )


def get_supabase_admin() -> Client:
    """Get Supabase client with service role for admin operations."""
    settings = get_settings()
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_KEY,
    )
```

### Task 3: Auth Module

**File**: `src/api/auth.py`

```python
"""Authentication module for JWT validation and user management."""

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status

from src.api.config import get_settings


@dataclass
class AuthenticatedUser:
    """Authenticated user data extracted from JWT."""

    id: str
    email: str


async def get_current_user(request: Request) -> AuthenticatedUser:
    """Extract and validate user from JWT cookie.

    Raises:
        HTTPException: If not authenticated or token invalid.
    """
    token = request.cookies.get("sb-access-token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"HX-Redirect": "/auth/login"},
        )

    try:
        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return AuthenticatedUser(
            id=payload["sub"],
            email=payload.get("email", ""),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"HX-Redirect": "/auth/login"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"HX-Redirect": "/auth/login"},
        )


# Type alias for dependency injection
CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]


def get_user_thread_id(user_id: str) -> str:
    """Convert user ID to LangGraph thread ID.

    Single conversation per user: user ID is the thread ID.
    """
    return f"user:{user_id}"
```

### Task 4: Auth Routes

**File**: `src/api/routes/auth.py`

```python
"""Authentication routes for login, signup, and logout."""

from typing import Annotated

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse

from src.api.config import get_settings
from src.api.dependencies import TemplatesDep
from src.api.supabase_client import get_supabase

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, templates: TemplatesDep):
    """Render login page."""
    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request},
    )


@router.post("/login")
async def login(
    response: Response,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    """Authenticate user and set JWT cookie."""
    supabase = get_supabase()

    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })
    except Exception as e:
        # Return error partial for HTMX
        return HTMLResponse(
            content=f'<div class="text-red-500">Invalid credentials</div>',
            status_code=400,
        )

    # Set JWT in httponly cookie
    settings = get_settings()
    response.set_cookie(
        key="sb-access-token",
        value=auth_response.session.access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )

    # HTMX redirect to chat
    response.headers["HX-Redirect"] = "/"
    return response


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request, templates: TemplatesDep):
    """Render signup page."""
    return templates.TemplateResponse(
        "auth/signup.html",
        {"request": request},
    )


@router.post("/signup")
async def signup(
    response: Response,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    """Create new user account."""
    supabase = get_supabase()

    try:
        auth_response = supabase.auth.sign_up({
            "email": email,
            "password": password,
        })
    except Exception as e:
        return HTMLResponse(
            content=f'<div class="text-red-500">Signup failed: {str(e)}</div>',
            status_code=400,
        )

    # Set JWT in httponly cookie
    settings = get_settings()
    response.set_cookie(
        key="sb-access-token",
        value=auth_response.session.access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )

    response.headers["HX-Redirect"] = "/"
    return response


@router.post("/logout")
async def logout(response: Response):
    """Clear session and redirect to login."""
    response.delete_cookie("sb-access-token")
    response.headers["HX-Redirect"] = "/auth/login"
    return response
```

### Task 5: PostgresSaver Checkpointer

**File**: `src/agent/checkpointer.py`

```python
"""LangGraph checkpointer using Supabase Postgres for persistence."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.api.config import get_settings


@asynccontextmanager
async def get_checkpointer() -> AsyncGenerator[AsyncPostgresSaver, None]:
    """Get PostgresSaver checkpointer for LangGraph persistence.

    Uses Supabase Postgres for durable conversation storage.
    Conversations persist across server restarts.

    Yields:
        AsyncPostgresSaver: Configured checkpointer for graph compilation.

    Example:
        async with get_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            result = await graph.ainvoke(
                state,
                config={"configurable": {"thread_id": f"user:{user_id}"}}
            )
    """
    settings = get_settings()
    async with AsyncPostgresSaver.from_conn_string(
        settings.SUPABASE_DB_URL
    ) as checkpointer:
        # Setup creates checkpoint tables if they don't exist
        await checkpointer.setup()
        yield checkpointer


def get_user_thread_id(user_id: str) -> str:
    """Convert user ID to LangGraph thread ID.

    Args:
        user_id: Supabase auth user UUID.

    Returns:
        Thread ID for LangGraph in format "user:{uuid}".
    """
    return f"user:{user_id}"
```

### Task 6: Protected Chat Routes

**File**: `src/api/routes/chat.py` (updated)

```python
@router.post("/chat")
async def send_message(
    request: Request,
    response: Response,
    user: CurrentUserDep,  # NEW: Require authentication
    message: Annotated[str, Form()],
    level: Annotated[str, Form()] = "A1",
    language: Annotated[str, Form()] = "es",
    templates: TemplatesDep = Depends(),
):
    """Send a message and get AI response (requires authentication)."""
    # Use user ID as thread ID (single conversation per user)
    thread_id = get_user_thread_id(user.id)

    async with get_checkpointer() as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=message)],
                "level": level,
                "language": language,
            },
            config={"configurable": {"thread_id": thread_id}},
        )

    # ... rest of response handling


@router.post("/new")
async def new_conversation(
    user: CurrentUserDep,  # NEW: Require authentication
):
    """Start a new conversation (clears LangGraph state for user)."""
    # TODO: Clear checkpointer state for this thread_id
    # For now, just redirect - conversation continues
    return Response(
        status_code=200,
        headers={"HX-Redirect": "/"},
    )
```

### Task 7: Auth Templates

**File**: `src/templates/auth/login.html`

```html
{% extends "base.html" %}

{% block content %}
<div class="min-h-screen flex items-center justify-center bg-gray-900 px-4">
    <div class="max-w-md w-full space-y-8">
        <div class="text-center">
            <h1 class="text-4xl font-bold text-white">Habla Hermano</h1>
            <p class="mt-2 text-gray-400">Sign in to continue learning</p>
        </div>

        <form
            hx-post="/auth/login"
            hx-target="#error-message"
            hx-swap="innerHTML"
            class="mt-8 space-y-6 bg-gray-800 p-8 rounded-xl"
        >
            <div id="error-message"></div>

            <div>
                <label for="email" class="block text-sm font-medium text-gray-300">
                    Email
                </label>
                <input
                    type="email"
                    name="email"
                    id="email"
                    required
                    class="mt-1 block w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="you@example.com"
                />
            </div>

            <div>
                <label for="password" class="block text-sm font-medium text-gray-300">
                    Password
                </label>
                <input
                    type="password"
                    name="password"
                    id="password"
                    required
                    class="mt-1 block w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="••••••••"
                />
            </div>

            <button
                type="submit"
                class="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
                Sign in
            </button>
        </form>

        <p class="text-center text-gray-400">
            Don't have an account?
            <a href="/auth/signup" class="text-blue-400 hover:text-blue-300">
                Sign up
            </a>
        </p>
    </div>
</div>
{% endblock %}
```

**File**: `src/templates/auth/signup.html`

```html
{% extends "base.html" %}

{% block content %}
<div class="min-h-screen flex items-center justify-center bg-gray-900 px-4">
    <div class="max-w-md w-full space-y-8">
        <div class="text-center">
            <h1 class="text-4xl font-bold text-white">Join Habla Hermano</h1>
            <p class="mt-2 text-gray-400">Start your language learning journey</p>
        </div>

        <form
            hx-post="/auth/signup"
            hx-target="#error-message"
            hx-swap="innerHTML"
            class="mt-8 space-y-6 bg-gray-800 p-8 rounded-xl"
        >
            <div id="error-message"></div>

            <div>
                <label for="email" class="block text-sm font-medium text-gray-300">
                    Email
                </label>
                <input
                    type="email"
                    name="email"
                    id="email"
                    required
                    class="mt-1 block w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="you@example.com"
                />
            </div>

            <div>
                <label for="password" class="block text-sm font-medium text-gray-300">
                    Password
                </label>
                <input
                    type="password"
                    name="password"
                    id="password"
                    required
                    minlength="8"
                    class="mt-1 block w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="••••••••"
                />
                <p class="mt-1 text-sm text-gray-500">At least 8 characters</p>
            </div>

            <button
                type="submit"
                class="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
            >
                Create account
            </button>
        </form>

        <p class="text-center text-gray-400">
            Already have an account?
            <a href="/auth/login" class="text-blue-400 hover:text-blue-300">
                Sign in
            </a>
        </p>
    </div>
</div>
{% endblock %}
```

---

## Testing Strategy

### Unit Tests

| Test | Description |
|------|-------------|
| `test_get_current_user_valid_token` | Valid JWT returns AuthenticatedUser |
| `test_get_current_user_no_token` | Missing token raises 401 |
| `test_get_current_user_expired_token` | Expired JWT raises 401 |
| `test_get_user_thread_id` | User ID correctly converted to thread ID |
| `test_supabase_client_singleton` | Client is cached |

### Integration Tests

| Test | Description |
|------|-------------|
| `test_signup_creates_user` | POST /auth/signup creates account |
| `test_login_returns_token` | POST /auth/login sets cookie |
| `test_logout_clears_cookie` | POST /auth/logout removes cookie |
| `test_protected_route_requires_auth` | /chat returns 401 without token |
| `test_protected_route_with_auth` | /chat works with valid token |

### E2E Tests

| Test | Description |
|------|-------------|
| Signup flow | Navigate to signup, create account, redirect to chat |
| Login flow | Navigate to login, enter credentials, redirect to chat |
| Chat persistence | Send message, refresh, conversation continues |
| User isolation | User A cannot see User B's conversations |
| Logout flow | Click logout, redirect to login |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| RLS misconfiguration | Comprehensive policy testing before launch |
| JWT secret exposure | Store in environment variables only |
| PostgresSaver compatibility | Test with exact LangGraph version |
| Supabase outage | Graceful error handling, status page |
| Cookie theft | Secure flag, short expiry, HTTPS only |

---

## Dependencies

### New Dependencies

```toml
supabase = ">=2.0.0"
PyJWT = ">=2.8.0"
langgraph-checkpoint-postgres = ">=2.0.0"
psycopg = {extras = ["binary", "pool"], version = ">=3.1.0"}
```

### Removable Dependencies

- `aiosqlite` - No longer needed (was for AsyncSqliteSaver)
- `langgraph-checkpoint-sqlite` - No longer needed

---

## Success Criteria

- [ ] Users can sign up with email/password
- [ ] Users can log in and receive JWT cookie
- [ ] Chat is protected (401 without auth)
- [ ] Conversations persist across server restarts
- [ ] Users only see their own conversations (RLS)
- [ ] All existing tests pass
- [ ] New auth tests achieve 95%+ coverage

---

## File Summary

| File | Action | Phase |
|------|--------|-------|
| `pyproject.toml` | Modify | 1 |
| `src/api/config.py` | Modify | 1 |
| `.env.example` | Modify | 1 |
| `src/api/supabase_client.py` | Create | 1 |
| `src/api/auth.py` | Create | 3 |
| `src/api/routes/auth.py` | Create | 3 |
| `src/templates/auth/login.html` | Create | 3 |
| `src/templates/auth/signup.html` | Create | 3 |
| `src/api/main.py` | Modify | 3 |
| `src/agent/checkpointer.py` | Modify | 4 |
| `src/api/routes/chat.py` | Modify | 5 |
| `src/api/session.py` | Modify | 5 |
| `tests/conftest.py` | Modify | 7 |
| `tests/test_auth.py` | Create | 7 |

---

## Verification Checklist

1. **Signup flow**: Navigate to `/auth/signup`, create account, verify redirect to `/`
2. **Login flow**: Logout, login with credentials, verify session persists
3. **Chat persistence**: Send message, refresh page, send another - AI remembers context
4. **Logout**: Click logout, verify redirect to login, verify `/chat` returns 401
5. **User isolation**: Create second account, verify no access to first user's data
6. **Server restart**: Stop server, restart, verify conversation resumes
7. **Run tests**: `make test` - all tests should pass
