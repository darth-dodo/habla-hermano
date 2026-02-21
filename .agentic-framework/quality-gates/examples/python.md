# Quality Gate Examples - habla-hermano

Concrete examples using the actual project structure and commands.

## Project Layout

```
habla-hermano/
├── src/
│   ├── agent/          # LangGraph agent (nodes, state, tools)
│   ├── api/            # FastAPI app (routes, middleware, config)
│   ├── db/             # Database models and access
│   ├── lessons/        # Lesson content and logic
│   ├── services/       # Business services (paths, adaptive)
│   ├── templates/      # Jinja2 HTML templates
│   └── static/         # CSS, JS assets
├── tests/
│   ├── agent/          # Agent node tests
│   ├── api/            # API route tests
│   ├── db/             # Database tests
│   ├── lessons/        # Lesson tests
│   ├── services/       # Service tests
│   └── conftest.py     # Shared fixtures
├── pyproject.toml      # All tool configuration
└── Makefile            # Dev commands
```

## Daily Workflow

```bash
# Before starting work
make lint && make typecheck && make test

# While developing -- auto-fix as you go
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/

# Before committing
make check && make test
```

## Gate Examples

### Gate 2: Type Safety

mypy in strict mode catches issues like missing return types and untyped function signatures.

```python
# Bad -- mypy strict will reject this
def get_user_level(user_id):
    return db.query(user_id)

# Good -- fully typed
async def get_user_level(user_id: str) -> str:
    result: str = await db.query(user_id)
    return result
```

Suppressing third-party library issues (already configured in `pyproject.toml`):

```python
# If a third-party function lacks type stubs, the pyproject.toml overrides
# handle this globally. For one-off cases:
result = langchain_call()  # type: ignore[no-untyped-call]
```

### Gate 3: Lint

Ruff catches common issues specific to this project.

```python
# ARG001: unused function argument (caught by ruff)
async def handle_chat(request: Request, db: Database) -> Response:
    # 'db' is never used -- ruff will flag this
    return Response(content="ok")

# I001: import order (auto-fixed by ruff)
# ruff will sort stdlib, third-party, and first-party imports
from fastapi import Request       # third-party
import os                         # stdlib -- should be first
from src.api.config import settings  # first-party -- should be last
```

### Gate 5: Tests

Tests use pytest with async support (pytest-asyncio) and FastAPI's TestClient via httpx.

```python
# tests/api/test_chat.py
import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_chat_requires_auth():
    """Unauthenticated requests should be rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/chat", json={"message": "hola"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_validates_input(auth_headers):
    """Empty messages should be rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={"message": ""},
            headers=auth_headers,
        )
    assert response.status_code == 422
```

Running coverage against a specific module:

```bash
# See coverage for just the API routes
uv run pytest tests/api/ --cov=src.api --cov-report=term-missing
```

### Gate 4: Security Review

Key areas to check in this project:

```python
# JWT verification -- ensure tokens are validated server-side
# Check src/api/ middleware for Supabase JWT verification

# Input validation -- Pydantic models enforce structure
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)

# Environment variables -- never hardcode secrets
from src.api.config import settings
# settings.supabase_url, settings.supabase_key loaded from .env
```

## Pre-commit Hook

The project uses pre-commit (install with `make install-hooks`). The hook runs:

```bash
# What pre-commit runs on each commit
uv run ruff check --fix src/ tests/   # lint with auto-fix
uv run ruff format src/ tests/        # format
uv run mypy src/                      # type check
```

## Makefile Targets

| Target | Command | Purpose |
|--------|---------|---------|
| `make lint` | `uv run ruff check src/ tests/` | Lint check |
| `make lint-fix` | `uv run ruff check --fix src/ tests/` | Lint with auto-fix |
| `make format` | `uv run ruff format src/ tests/` | Format code |
| `make format-check` | `uv run ruff format --check src/ tests/` | Check formatting |
| `make typecheck` | `uv run mypy src/` | Type check |
| `make check` | lint + format-check + typecheck | All static checks |
| `make test` | `uv run pytest` | Run tests |
| `make test-cov` | `uv run pytest --cov=src --cov-report=html --cov-report=term-missing` | Tests + coverage |
| `make test-fast` | `uv run pytest -m "not slow"` | Skip slow tests |
