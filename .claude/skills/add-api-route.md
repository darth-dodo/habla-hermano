# Add API Route

Add a new FastAPI route to the Habla Hermano backend.

## When to Use
- Adding a new API endpoint (REST or HTMX)
- Creating a new page route with Jinja2 template rendering
- Adding authenticated or guest-accessible endpoints

## Steps

1. **Understand existing route patterns**
   - Read `src/api/routes/chat.py` for HTMX + auth pattern
   - Read `src/api/routes/progress.py` for authenticated data routes
   - Read `src/api/routes/lessons.py` for resource browsing pattern
   - Read `src/api/auth.py` for `CurrentUserDep` and `OptionalUserDep`
   - Read `src/api/dependencies.py` for shared dependencies

2. **Create or extend the route file** at `src/api/routes/{name}.py`
   ```python
   from fastapi import APIRouter, Depends, Request
   from fastapi.responses import HTMLResponse
   from jinja2 import Environment as Jinja2Templates

   from src.api.auth import AuthenticatedUser, CurrentUserDep, OptionalUserDep
   from src.api.dependencies import get_cached_templates

   router = APIRouter(prefix="/{name}", tags=["{name}"])
   ```

3. **Choose the auth pattern**
   - **Public (guest ok)**: `user: OptionalUserDep` - returns `None` for guests
   - **Authenticated only**: `user: CurrentUserDep` - returns 401 for unauthenticated
   - **No auth needed**: Don't include user dependency (health check, static pages)

4. **For data routes using Supabase**
   - Import `get_supabase_for_user` from `src.api.supabase_client`
   - Create user-scoped client: `client = get_supabase_for_user(request.cookies.get("sb-access-token", ""))`
   - Pass client to repository/service: `repo = SomeRepository(user.id, client=client)`
   - This ensures Row Level Security (RLS) works correctly

5. **For HTMX template responses**
   ```python
   @router.get("/", response_class=HTMLResponse)
   async def page_view(
       request: Request,
       user: OptionalUserDep,
       templates: Jinja2Templates = Depends(get_cached_templates),
   ) -> HTMLResponse:
       context = {"request": request, "user": user}
       return templates.TemplateResponse("{template}.html", context)
   ```

6. **Register the router** in `src/api/main.py`
   ```python
   from src.api.routes.{name} import router as {name}_router
   app.include_router({name}_router)
   ```

7. **Add input validation** (if accepting user input)
   - Use Pydantic models for request bodies
   - Validate string lengths, allowed values
   - See `src/api/routes/chat.py` for message length validation pattern

8. **Add rate limiting** (for write endpoints)
   - Import from `src.api.rate_limit`
   - Apply `@rate_limit` decorator or check in handler

9. **Write tests** in `tests/api/test_{name}.py`
   - Use `test_client` fixture for sync tests
   - Use `async_client` fixture for async tests
   - Test both authenticated and unauthenticated access
   - Mock Supabase calls using `mock_supabase_client` fixture
   - Override auth deps: `app.dependency_overrides[get_current_user] = mock_fn`

10. **Run quality checks**
    ```bash
    uv run pytest tests/api/ -v
    uv run ruff check src/api/ tests/api/
    uv run mypy src/api/
    ```

## Key Dependencies
- `get_cached_templates` - Jinja2 template engine (cached)
- `get_settings` - App configuration (cached)
- `get_graph` / `get_checkpointer` - LangGraph agent access
- `get_supabase_for_user` - User-scoped Supabase client (RLS-compliant)

## Template Location
- HTML templates go in `src/templates/`
- Use HTMX attributes for dynamic content: `hx-post`, `hx-swap`, `hx-target`
- Alpine.js for client-side interactivity
- Tailwind CSS for styling (compile with `make dev-css`)
