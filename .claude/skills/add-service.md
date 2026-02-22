# Add Service

Create a new service layer component for business logic.

## When to Use
- Adding business logic that sits between API routes and database repositories
- Composing multiple repository operations into a single workflow
- Implementing algorithms (like SM-2 spaced repetition) that operate on domain models

## Steps

1. **Review existing service patterns**
   - Read `src/services/progress.py` - aggregates stats from 3 repositories
   - Read `src/services/review.py` - SM-2 algorithm + scheduling logic
   - Read `src/services/vocabulary.py` - vocabulary CRUD with business rules
   - Read `src/services/paths.py` - learning path structure
   - Read `src/services/adaptive.py` - daily recommendation engine

2. **Create the service** at `src/services/{name}.py`
   ```python
   from typing import Any

   from src.db.repository import SomeRepository


   class {Name}Service:
       """Service description."""

       def __init__(self, user_id: str, client: Any = None) -> None:
           self.user_id = user_id
           self.repo = SomeRepository(user_id, client=client)

       def some_method(self) -> dict[str, Any]:
           """Method description."""
           data = self.repo.get_data()
           # Business logic here
           return result
   ```

3. **Key design patterns**
   - **Constructor injection**: Accept `user_id` and optional `client` (Supabase)
   - **Repository composition**: Create repos in `__init__`, compose in methods
   - **User-scoped client**: Always pass `client=client` to repos for RLS compliance
   - **Factory pattern**: For services needing lazy imports (see `paths.py`, `adaptive.py`)

4. **If the service needs a repository**, check or create in `src/db/repository.py`
   - Repositories handle raw Supabase table operations
   - Services handle business logic on top of repositories
   - Never call Supabase directly from services - always go through a repository

5. **Wire into API routes**
   ```python
   from src.services.{name} import {Name}Service

   client = get_supabase_for_user(request.cookies.get("sb-access-token", ""))
   service = {Name}Service(user.id, client=client)
   result = service.some_method()
   ```

6. **Write tests** in `tests/services/test_{name}.py`
   - Mock the repository layer, not Supabase directly
   - Test business logic in isolation
   - Test edge cases (empty data, missing fields, boundary values)
   ```python
   from unittest.mock import MagicMock, patch

   def test_service_method():
       mock_client = MagicMock()
       service = SomeService("user-123", client=mock_client)
       # Mock repo methods on the service instance
       service.repo.get_data = MagicMock(return_value=[...])
       result = service.some_method()
       assert result == expected
   ```

7. **Run quality checks**
   ```bash
   uv run pytest tests/services/ -v
   uv run ruff check src/services/ tests/services/
   ```

## Architecture Notes
- Services sit between routes and repositories: Route -> Service -> Repository -> Supabase
- Services are stateless (no instance caching) except for `user_id` and `client`
- The `client` parameter enables RLS - always use user-scoped client from cookies
- MyPy has `ignore_errors = true` for `src.services.*` (historical, aim to fix)
