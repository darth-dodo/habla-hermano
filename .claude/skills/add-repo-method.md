# Add Repository Method

Add a new database operation to the Supabase repository layer.

## When to Use
- Adding CRUD operations for existing tables (vocabulary, learning_sessions, lesson_progress, user_profiles)
- Adding query patterns (filtering, aggregation, date ranges)
- Implementing upsert or batch operations

## Steps

1. **Review existing repository patterns**
   - Read `src/db/repository.py` for all repository classes
   - Read `src/db/models.py` for Pydantic models matching each table
   - Understand the RLS pattern: all queries automatically scoped to `auth.uid()`

2. **Identify the target repository class**
   - `VocabularyRepository` - word tracking, SM-2 fields, review scheduling
   - `LearningSessionRepository` - session start/end, message counts
   - `LessonProgressRepository` - lesson completion tracking
   - `UserProfileRepository` - display name, preferences

3. **Add the method** to the appropriate class in `src/db/repository.py`
   ```python
   def new_method(self, param: str) -> list[dict[str, Any]]:
       """Description of what this query does."""
       result = (
           self.client.table("table_name")
           .select("*")
           .eq("user_id", self.user_id)
           .eq("column", param)
           .execute()
       )
       return result.data or []
   ```

4. **Supabase query patterns**
   ```python
   # Select with filters
   .select("*").eq("col", val).gte("date", start).execute()

   # Insert
   .insert({"user_id": self.user_id, "col": val}).execute()

   # Upsert (prefer over insert+update for race condition safety)
   .upsert({"user_id": self.user_id, ...}, on_conflict="user_id,unique_col").execute()

   # Update
   .update({"col": new_val}).eq("user_id", self.user_id).eq("id", id).execute()

   # Delete
   .delete().eq("user_id", self.user_id).eq("id", id).execute()

   # Ordering and limits
   .select("*").eq("user_id", self.user_id).order("created_at", desc=True).limit(10).execute()

   # Date filtering (SM-2 review scheduling)
   .select("*").eq("user_id", self.user_id).lte("next_review_at", datetime.now().isoformat()).execute()
   ```

5. **Repository constructor pattern**
   ```python
   class SomeRepository:
       def __init__(self, user_id: str, client: Any = None) -> None:
           self.user_id = user_id
           self.client = client or get_supabase_admin()  # Prefer user client for RLS
   ```
   **Important**: Always prefer user-scoped client. Admin client bypasses RLS.

6. **Write tests** in `tests/db/test_repository.py`
   ```python
   def test_new_method():
       mock_client = MagicMock()
       mock_table = MagicMock()
       mock_client.table.return_value = mock_table
       mock_table.select.return_value = mock_table
       mock_table.eq.return_value = mock_table
       mock_table.execute.return_value = MagicMock(data=[{"id": "1"}])

       repo = SomeRepository("user-123", client=mock_client)
       result = repo.new_method("param")

       assert len(result) == 1
       mock_client.table.assert_called_with("table_name")
   ```

7. **Run quality checks**
   ```bash
   uv run pytest tests/db/ -v
   uv run ruff check src/db/ tests/db/
   ```

## Database Schema Reference
| Table | Key Columns | Notes |
|-------|------------|-------|
| vocabulary | word, translation, language, times_seen, times_correct, easiness_factor, interval_days, repetition_count, next_review_at | SM-2 fields |
| learning_sessions | started_at, ended_at, language, level, message_count | Session tracking |
| lesson_progress | user_id, lesson_id, completed_at, score | Upsert on re-completion |
| user_profiles | display_name, preferred_language, current_level | User preferences |

## RLS Notes
- All tables have Row Level Security enabled
- Policies use `auth.uid()` to restrict access
- User-scoped Supabase client automatically includes the JWT in requests
- Admin client (`SUPABASE_SERVICE_KEY`) bypasses RLS - avoid in production code paths
