# ADR-007: Static Learning Paths with Dynamic Progress Overlay

**Date**: 2025-01-18
**Status**: Accepted
**Context**: Phase 14 — Learning Paths & Adaptive Recommendations
**Decider(s)**: Project Owner

---

## Summary

Build learning paths as static configuration derived from the lesson catalog, with user progress overlaid dynamically on each request. No new database tables — paths are computed from existing `lesson_progress` records. Combined with an AdaptiveService that produces personalized daily recommendations by synthesizing path progress, vocabulary accuracy, and spaced repetition review schedule.

---

## Problem Statement

### The Challenge

With 60 lessons across 3 languages and 4 CEFR levels, users need guidance on what to learn next:

1. **Structured progression**: Organize lessons into a logical path per language
2. **Progress visualization**: Show completion state across the entire curriculum
3. **Next lesson recommendation**: Suggest what to learn next based on progress
4. **Adaptive recommendations**: Factor in vocabulary accuracy, review due count, and level readiness
5. **No schema changes**: Avoid database migrations — reuse existing `lesson_progress` table

### Why This Matters

Without a guided path, users face a wall of 60 lessons with no clear direction. Learning paths provide structure, and adaptive recommendations provide personalization — both proven to improve learner retention and completion rates.

### Success Criteria

- [x] Static paths built from lesson catalog (5 categories x 4 levels per language)
- [x] Dynamic progress overlay from existing lesson_progress records
- [x] Adaptive daily recommendation combining 4 signals
- [x] Learn page with visual timeline and lazy-loaded recommendation
- [x] Continue Path button in post-lesson flow
- [x] No new database tables or schema changes

---

## Options Considered

### Option A: Static Paths with Dynamic Overlay (Selected)

**Description**: PathService builds static LearningPath objects from the lesson catalog on first request. Progress is computed per request by overlaying `lesson_progress` records onto the static structure. AdaptiveService combines path progress, vocabulary accuracy, and review schedule.

**Pros**:

- No schema changes — reuses existing lesson_progress table
- Clean separation of structure (static) from progress (dynamic)
- Simple data model — all paths are deterministic from lesson catalog
- Easy to extend with new categories or levels

**Cons**:

- Paths not customizable per user
- Recomputed on each request (acceptable for 60 lessons)
- Constants (CATEGORY_ORDER, LEVEL_ORDER) are hardcoded

**Estimated Effort**: 3-4 days

---

### Option B: Database-Stored Paths

**Description**: User-specific path records in Supabase with assigned lessons and progress state.

**Pros**:

- Customizable paths per user
- Persistent path state

**Cons**:

- Schema changes (new tables, migrations, RLS policies)
- Sync issues if lesson catalog changes
- Over-engineering for fixed 60-lesson curriculum

**Estimated Effort**: 5-6 days

---

### Option C: Prerequisite Graph

**Description**: Each lesson declares prerequisites; path computed from DAG traversal.

**Pros**:

- Flexible non-linear progression
- Natural modeling of skill dependencies

**Cons**:

- Complex graph traversal for 60 lessons
- Hard to visualize for users
- Overkill for a linear category x level structure

**Estimated Effort**: 4-5 days

---

## Decision

### Chosen Option

**Selected**: Option A: Static Paths with Dynamic Overlay

**Rationale**: The curriculum is fixed (5 categories x 4 levels x 3 languages). Paths don't need per-user customization. Reusing existing `lesson_progress` records avoids schema changes. The deterministic structure-from-catalog approach is simple, testable, and maintainable.

**Key Factors**:

- No database migrations required
- Deterministic paths from lesson catalog
- Progress overlay is a pure function (completed_lessons -> PathProgress)
- Matches existing patterns (LessonService singleton, dataclass models)

**Trade-offs Accepted**:

- No per-user path customization (acceptable for guided curriculum)
- Recomputation per request (negligible for 60 lessons)

---

## Consequences

### Data Models

**Path Structure** (static, `@dataclass(frozen=True)`):

| Model | Fields | Purpose |
|-------|--------|---------|
| `PathUnit` | level, title, description, icon, lesson_ids | Single CEFR level unit |
| `LearningPath` | language, language_name, units | Complete curriculum for one language |

**Progress Overlay** (dynamic, per request):

| Model | Fields | Purpose |
|-------|--------|---------|
| `LessonInUnit` | lesson, is_completed, score | Lesson with completion status |
| `UnitProgress` | unit, lessons, completed_count, total_count, is_complete | Unit with aggregated progress |
| `PathProgress` | path, units, overall_completed, overall_total, current_unit_index, next_lesson, completion_percentage | Full progress view |

**Recommendation Models** (`@dataclass(frozen=True)`):

| Model | Fields | Purpose |
|-------|--------|---------|
| `CategoryStrength` | category, total_words, words_seen, accuracy, is_weak | Per-category vocab accuracy |
| `LevelReadiness` | current_level, completed_in_level, total_in_level, readiness_pct, is_ready, next_level | Level advancement readiness |
| `DailyRecommendation` | next_lesson, review_due_count, weak_categories, level_readiness, suggestion_text | Combined recommendation |

### PathService (`src/services/paths.py`)

**Constants**:
- `CATEGORY_ORDER = ("greetings", "introductions", "numbers", "colors", "family")`
- `LEVEL_ORDER = ("A0", "A1", "A2", "B1")`
- `LANGUAGE_META = {"es": "Spanish", "de": "German", "fr": "French"}`

**Methods**:
- `_build_paths()`: On init, builds all paths from lesson catalog
- `get_path(language)`: Static path for language
- `get_path_progress(language, completed_lessons)`: Overlays progress
- `get_next_path_lesson(language, completed_lessons)`: Next uncompleted lesson

### AdaptiveService (`src/services/adaptive.py`)

**Methods**:
- `get_daily_recommendation()`: Returns DailyRecommendation combining 4 signals
- `get_category_strengths()`: Accuracy by vocabulary category
- `_compute_level_readiness()`: Level advancement assessment
- `_build_suggestion()`: Human-readable recommendation text

**Recommendation Priority**:
1. Review due words ("You have 5 words ready for review.")
2. Weak categories ("Your Greetings and Numbers could use some practice.")
3. Level advancement ("You've completed A0 -- ready for A1!")
4. Next lesson ("Continue with 'Basic Greetings' to keep your streak going.")
5. Default ("Great job! Keep exploring to discover new vocabulary.")

### Routes (`src/api/routes/learn.py`)

- `GET /learn/`: Full path page with progress overlay and recommendation
- `GET /learn/recommendation`: HTMX lazy-loaded partial (`hx-trigger="load delay:500ms"`)
- Both support authenticated users (full progress) and guests (empty progress)

### Testing

99 new tests across 3 test files:
- `test_paths_service.py` (27 tests): Path building, progress overlay, next lesson, edge cases
- `test_adaptive_service.py` (49 tests): Recommendations, category strengths, level readiness
- `test_learn_routes.py` (23 tests): Page rendering, HTMX partial, guest/auth, error handling

---

## Key Files

- `src/services/paths.py` — PathService with path building and progress overlay
- `src/services/adaptive.py` — AdaptiveService with daily recommendations
- `src/api/routes/learn.py` — Learn page and recommendation routes
- `src/templates/learn.html` — Learning path page template
- `src/templates/partials/learn_recommendation.html` — Recommendation card partial
- `tests/test_paths_service.py` — PathService tests (27)
- `tests/test_adaptive_service.py` — AdaptiveService tests (49)
- `tests/test_learn_routes.py` — Learn routes tests (23)

---

## Related Decisions

**Depends On**:
- ADR-001 (Supabase stores lesson_progress records)
- ADR-004 (YAML lessons feed PathService via LessonService)
- ADR-005 (ReviewService provides review_due_count for AdaptiveService)
- ADR-006 (Follows repository + service layer pattern)

**Related To**:
- ADR-003 (HTMX — learn page uses lazy loading for recommendation partial)

---

## Metadata

**ADR Number**: 007
**Created**: 2025-01-18
**Last Updated**: 2025-01-18
**Version**: 1.0
**Tags**: learning-paths, adaptive, recommendations, static-config, progress, phase14

---

**Status**: ACCEPTED
