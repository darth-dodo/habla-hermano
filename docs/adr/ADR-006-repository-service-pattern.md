# ADR-006: Repository + Service Layer Architecture

**Date**: 2025-01-15
**Status**: Accepted
**Context**: Phase 7 (Progress Tracking), extended through Phase 14
**Decider(s)**: Project Owner

---

## Summary

Adopt a layered architecture with Repository classes for Supabase data access and Service classes for business logic, using `@lru_cache` singletons for stateless services. Repositories take a user-authenticated Supabase client to ensure Row Level Security (RLS) applies naturally. Services compose repositories and implement domain logic.

---

## Problem Statement

### The Challenge

As Habla Hermano grows from a simple chat app to a full learning platform, data access patterns become increasingly complex:

1. **Multiple data domains**: Vocabulary, lesson progress, learning sessions, review scheduling
2. **Business logic**: Dashboard aggregation, streak calculation, SM-2 scheduling, path progress, adaptive recommendations
3. **Auth-scoped access**: Authenticated users see their data via RLS; guests see empty state
4. **Testability**: Business logic must be testable without real database connections
5. **Composability**: Services build on each other (AdaptiveService uses PathService and ReviewService data)

### Success Criteria

- [x] Clean separation of data access from business logic
- [x] User-scoped data access via authenticated Supabase client
- [x] Services testable with mock repositories
- [x] Services composable (AdaptiveService depends on PathService)
- [x] Consistent patterns across all data domains

---

## Options Considered

### Option A: Repository + Service Pattern (Selected)

**Description**: Repository classes encapsulate Supabase table operations. Service classes compose repositories and implement business logic. Services are `@lru_cache` singletons.

**Architecture**:
```
Routes (FastAPI dependency injection)
  |
Services (business logic, @lru_cache singletons)
  |
Repositories (Supabase SDK calls)
  |
Supabase (PostgreSQL + RLS)
```

**Pros**:

- Clear separation of concerns
- Repositories are thin, testable wrappers
- Services encapsulate all business logic
- User-scoped clients make RLS transparent
- Singleton pattern avoids repeated initialization

**Cons**:

- More files and indirection
- Potential for over-abstraction
- Repository constructor requires user_id and client on each request

**Estimated Effort**: 2-3 days

---

### Option B: Direct Supabase Calls in Routes

**Description**: Route handlers call `supabase.table("vocabulary").select()` directly.

**Pros**:

- Simple, fewer files
- No abstraction overhead

**Cons**:

- Untestable without real database
- Duplicated queries across routes
- No business logic layer
- Mixing concerns in route handlers

---

### Option C: ORM (SQLAlchemy)

**Description**: Full ORM with models, sessions, and migrations.

**Pros**:

- Familiar patterns, migration support, query builder

**Cons**:

- Supabase already manages schema and migrations
- ORM adds complexity without benefit
- Doesn't work well with RLS (auth.uid() in policies)
- Extra dependency

---

## Decision

### Chosen Option

**Selected**: Option A: Repository + Service Pattern

**Rationale**: Supabase handles the database layer, so an ORM is unnecessary overhead. Repositories provide clean abstractions over Supabase SDK calls, while services implement business logic that composes multiple repositories. The `@lru_cache` singleton pattern matches the existing LessonService pattern.

**Key Factors**:

- RLS works naturally with user-authenticated clients
- Business logic belongs in services, not route handlers
- Repositories are thin — just Supabase SDK calls
- Singletons avoid repeated service construction

---

## Consequences

### Repository Layer (`src/db/repository.py`)

- `VocabularyRepository(user_id, client)`: get_all, upsert, get_due_for_review
- `LessonProgressRepository(user_id, client)`: get_completed, mark_complete
- `LearningSessionRepository(user_id, client)`: create, get_recent

**Pattern**: Constructor takes `user_id` and optional `client`. If client not provided, falls back to admin client. User-scoped client ensures RLS applies naturally.

### Service Layer

| Service | File | Responsibility | Composes |
|---------|------|----------------|----------|
| `ProgressService` | `src/services/progress.py` | Dashboard stats, chart data, streaks | 3 repositories |
| `ReviewService` | `src/services/review.py` | SM-2 scheduling, due words, stats | VocabularyRepository |
| `PathService` | `src/services/paths.py` | Static path building, progress overlay | LessonService |
| `AdaptiveService` | `src/services/adaptive.py` | Daily recommendations | PathService, LessonService |
| `LessonService` | `src/lessons/service.py` | YAML loading, lesson lookups | Filesystem (YAML) |

### Singleton Pattern

All services use `@lru_cache` on factory functions:
- Lazy initialization on first request
- Services are stateless (state comes from user-scoped repositories)
- Avoids circular imports via lazy imports in factory functions

### User-Scoped Clients

Routes create authenticated clients and pass to repositories:
```python
client = get_supabase_for_user(sb_access_token)
repo = VocabularyRepository(user.id, client=client)
```
This ensures RLS policies apply without admin bypass.

---

## Key Files

- `src/db/repository.py` — Repository classes (Vocabulary, LessonProgress, LearningSession)
- `src/db/models.py` — Data models (Vocabulary, LessonProgress, LearningSession dataclasses)
- `src/services/progress.py` — ProgressService (dashboard, charts, streaks)
- `src/services/review.py` — ReviewService (SM-2, due words, stats)
- `src/services/paths.py` — PathService (learning paths, progress overlay)
- `src/services/adaptive.py` — AdaptiveService (daily recommendations)
- `src/lessons/service.py` — LessonService (YAML loading, lesson lookups)
- `src/api/supabase_client.py` — `get_supabase_for_user()`, `get_supabase_admin()`

---

## Related Decisions

**Depends On**: ADR-001 (Supabase as data layer with RLS)

**Related To**:
- ADR-004 (LessonService follows this pattern for YAML content)
- ADR-005 (ReviewService implements SM-2 using this pattern)
- ADR-007 (PathService and AdaptiveService use this pattern)

---

## Metadata

**ADR Number**: 006
**Created**: 2025-01-15
**Last Updated**: 2025-01-18
**Version**: 1.0
**Tags**: architecture, repository, service, singleton, rls, data-access

---

**Status**: ACCEPTED
