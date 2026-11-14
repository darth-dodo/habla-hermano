# Phase 14: Learning Paths & Adaptive Recommendations

> Structured learning progression with intelligent daily recommendations combining path progress, vocabulary accuracy, and review schedules

---

## Overview

Phase 14 adds structured learning paths and adaptive daily recommendations to Habla Hermano. Previously, learners could browse 60 micro-lessons freely, but there was no guidance on which lesson to take next or how their overall progress mapped to a structured curriculum. This phase introduces:

1. **PathService** — Static path definitions mapping all 60 lessons into a structured progression (language → CEFR level units → ordered lessons by category)
2. **AdaptiveService** — Personalized daily recommendations combining path progress, vocabulary accuracy, and review schedules
3. **Learn page** — Full-page learning path overview with visual timeline and lazy-loaded recommendation card
4. **Lesson completion integration** — "Continue Path" button showing the next lesson after completing one

---

## Goals

- Provide learners with a clear, structured progression through the curriculum
- Help learners understand their position in the overall learning journey
- Generate personalized recommendations based on actual performance data
- Reduce decision fatigue ("which lesson should I do next?")
- Enable learners to see their overall progress at a glance
- Maintain continuity between lessons and review mode

---

## Design Decisions

### No New Database Tables

Paths are static configuration, not user-created content. Progress is derived entirely from the existing `lesson_progress` table. This avoids schema changes and keeps the data model simple.

### Static Path Config with Dynamic Progress Overlay

Rather than storing path state in the database, `PathService` builds static `LearningPath` objects from the lesson catalog at initialization, then overlays user completion data on each request. This follows the existing pattern of computing derived state from raw records and avoids sync issues.

### @lru_cache Singleton Pattern

Both `PathService` and `AdaptiveService` use the `@lru_cache` singleton pattern, matching the existing `LessonService` approach. Path definitions are built once per process and reused for all requests, providing efficient caching without explicit cache management.

### Category × Level Ordering

Lessons within each CEFR level unit are ordered by category: greetings → introductions → numbers → colors → family. This provides a natural pedagogical progression within each level, moving from social interaction through basic concepts to family relations.

### Lazy-Loaded Recommendations

The recommendation card on the Learn page is fetched asynchronously via HTMX, allowing the page to load quickly while the recommendation computation (which may involve database queries and logic) happens in the background.

---

## Data Model

### Path Models

```python
@dataclass(frozen=True)
class PathUnit:
    """Single CEFR level unit within a learning path."""
    level: str                      # "A0", "A1", "A2", "B1"
    title: str                      # "Absolute Beginner"
    description: str                # "Your first words and phrases"
    icon: str                       # Emoji icon (e.g., "🌱")
    lesson_ids: tuple[str, ...]     # Ordered lesson IDs


@dataclass(frozen=True)
class LearningPath:
    """Complete structured learning path for a language."""
    language: str                   # "es", "de", "fr"
    language_name: str              # "Spanish"
    units: tuple[PathUnit, ...]     # 4 units (A0→B1)


@dataclass(frozen=True)
class LessonInUnit:
    """Single lesson with completion status within a unit."""
    lesson: Lesson
    is_completed: bool
    score: int | None               # 0-100, None if not completed


@dataclass
class UnitProgress:
    """Progress tracking for a single unit."""
    unit: PathUnit
    lessons: list[LessonInUnit]
    completed_count: int
    total_count: int
    is_complete: bool


@dataclass
class PathProgress:
    """Complete path progress for a user."""
    path: LearningPath
    units: list[UnitProgress]
    overall_completed: int
    overall_total: int
    current_unit_index: int         # Index of unit currently working through
    next_lesson: Lesson | None      # First incomplete lesson in current unit
    completion_percentage: float     # 0.0 to 100.0
```

### Adaptive Recommendation Models

```python
@dataclass(frozen=True)
class CategoryStrength:
    """Analysis of learner performance in a vocabulary category."""
    category: str                   # "greetings", "introductions", etc.
    total_words: int                # Total words in category
    words_seen: int                 # Words user has encountered
    accuracy: float                 # 0.0 - 1.0, average accuracy in category
    is_weak: bool                   # True when accuracy < 0.7 and seen > 0


@dataclass(frozen=True)
class LevelReadiness:
    """Assessment of readiness to advance to next CEFR level."""
    current_level: str              # "A1"
    completed_in_level: int
    total_in_level: int
    readiness_pct: float            # 0.0 - 100.0
    is_ready: bool                  # True when all lessons complete
    next_level: str | None


@dataclass(frozen=True)
class DailyRecommendation:
    """Personalized recommendation for today's learning."""
    next_lesson: Lesson | None      # Next lesson to complete
    review_due_count: int           # Words due for spaced repetition review
    weak_categories: list[CategoryStrength]  # Categories needing practice
    level_readiness: LevelReadiness | None   # Readiness to advance
    suggestion_text: str            # Human-readable recommendation
```

---

## Service Layer

### PathService

`src/services/paths.py` — Builds and caches learning path definitions from the lesson catalog.

```python
class PathService:
    """Service for managing learning path definitions and progress.

    Uses @lru_cache singleton pattern to build paths once and reuse.
    Progress is computed dynamically on each request by overlaying
    completion data onto static path definitions.
    """

    def __init__(self, lesson_service: LessonService):
        """Initialize service with lesson catalog."""
        self._lesson_service = lesson_service
        self._paths = self._build_paths()

    def _build_paths(self) -> dict[str, LearningPath]:
        """Build path definitions from lesson catalog.

        For each language, creates 4 units (A0-B1), each containing
        lessons ordered by category (greetings, introductions, numbers,
        colors, family). Verifies all lessons exist before including them.

        Returns path dict keyed by language code.
        """
        ...

    def get_path(self, language: str) -> LearningPath | None:
        """Get path definition for language."""
        ...

    def get_path_progress(
        self,
        language: str,
        completed_lessons: dict[str, LessonProgress]
    ) -> PathProgress | None:
        """Get path progress by overlaying completion data.

        Args:
            language: Language code (e.g., "es")
            completed_lessons: Dict mapping lesson_id → LessonProgress

        Returns:
            PathProgress with current unit, completion %, next lesson
        """
        ...

    def get_next_path_lesson(
        self,
        language: str,
        completed_lessons: dict[str, LessonProgress]
    ) -> Lesson | None:
        """Get next uncompleted lesson in path.

        Returns first incomplete lesson in current unit,
        or first incomplete in next unit if current unit complete.
        Returns None if entire path is complete.
        """
        ...
```

### AdaptiveService

`src/services/adaptive.py` — Generates personalized daily recommendations.

```python
class AdaptiveService:
    """Service for adaptive learning recommendations.

    Combines path progress, vocabulary accuracy, and review scheduling
    to generate personalized recommendations aligned with learner's
    current needs and abilities.
    """

    def __init__(
        self,
        path_service: PathService,
        lesson_service: LessonService
    ):
        """Initialize with path and lesson services."""
        self._path_service = path_service
        self._lesson_service = lesson_service

    def get_daily_recommendation(
        self,
        language: str,
        completed_lessons: dict[str, LessonProgress],
        vocabulary_data: list[VocabularyItem],
        review_due_count: int
    ) -> DailyRecommendation:
        """Generate personalized daily recommendation.

        Considers:
        - Next lesson in path
        - Words due for review
        - Categories with weak accuracy
        - Readiness to advance levels

        Returns recommendation with suggestion_text for UI display.
        """
        ...

    def get_category_strengths(
        self,
        language: str,
        vocabulary_data: list[VocabularyItem]
    ) -> list[CategoryStrength]:
        """Analyze performance by vocabulary category.

        Calculates accuracy for each category based on times_correct
        and times_seen. Identifies categories with accuracy < 0.7
        as weak and needing practice.
        """
        ...

    def _compute_level_readiness(
        self,
        language: str,
        completed_lessons: dict[str, LessonProgress]
    ) -> LevelReadiness | None:
        """Assess readiness to advance to next CEFR level.

        Compares completed lessons in current level to total lessons.
        Returns None if at maximum level or path not available.
        """
        ...

    def _build_suggestion(
        self,
        next_lesson: Lesson | None,
        review_due_count: int,
        weak_categories: list[CategoryStrength],
        level_readiness: LevelReadiness | None
    ) -> str:
        """Build human-readable recommendation text.

        Prioritizes: next lesson > review due > weak categories > ready to level up
        Returns natural language suggestion for UI display.

        Examples:
        - "Continue with Greetings in Level A1"
        - "You have 5 words due for review - want to practice?"
        - "Great progress! Ready to move to Level A2?"
        """
        ...
```

---

## Constants

```python
# src/services/paths.py

CATEGORY_ORDER = (
    "greetings",
    "introductions",
    "numbers",
    "colors",
    "family"
)

LEVEL_ORDER = ("A0", "A1", "A2", "B1")

LEVEL_METADATA = {
    "A0": ("🌱", "Absolute Beginner", "Your first words and phrases"),
    "A1": ("🌿", "Beginner", "Basic communication and everyday topics"),
    "A2": ("🌳", "Elementary", "Simple conversations about familiar matters"),
    "B1": ("🌲", "Intermediate", "Deal with most situations in the language"),
}

LANGUAGE_META = {
    "es": "Spanish",
    "de": "German",
    "fr": "French"
}
```

Each language has 4 units (one per CEFR level) × 5 lessons (one per category) = 20 lessons per language × 3 languages = 60 total lessons.

---

## Routes

### GET /learn/

Full learning path overview page. Renders `learn.html` with the complete path structure and progress visualization.

**Authentication**: Optional (`OptionalUserDep`). Guests see the path structure with no progress overlay. Authenticated users see their completion status and current position.

**Query Parameters**:
- `language` (string, default: `es`) — Language to display path for

**Response**: HTML page with:
- Path header with language name and completion percentage
- Visual timeline of units and lessons with status indicators
- Completion progress bar
- Lazy-loaded recommendation card via HTMX

### GET /learn/recommendation

HTMX partial endpoint returning adaptive recommendation card. Designed for lazy loading — main page loads first, then this card is fetched asynchronously.

**Authentication**: Optional. Returns empty/generic recommendation for unauthenticated users.

**Query Parameters**:
- `language` (string, default: `es`) — Language for recommendation

**Response**: HTML partial with recommendation card content

---

## Templates

### learn.html

Full-page layout with:
- Page header: "Learning Path — Spanish" with completion indicator
- Completion progress bar (e.g., "12 of 60 lessons completed")
- Unit cards (rendered via `learn_unit.html` partial for each unit)
- Recommendation card placeholder with `hx-get="/learn/recommendation"` and `hx-trigger="load delay:500ms"`

Structure:
```html
<div class="learn-page">
  <header>
    <h1>{{ language_name }} Learning Path</h1>
    <div class="progress-bar" style="width: {{ completion_percentage }}%"></div>
    <p>{{ overall_completed }} of {{ overall_total }} lessons completed</p>
  </header>

  <div class="units-timeline">
    {% for unit_progress in units %}
      {% include "partials/learn_unit.html" %}
    {% endfor %}
  </div>

  <div id="recommendation"
       hx-get="/learn/recommendation?language={{ language }}"
       hx-trigger="load delay:500ms">
    <p>Loading your recommendation...</p>
  </div>
</div>
```

### partials/learn_unit.html

Single unit card showing:
- Unit level badge (e.g., "A0")
- Unit title and description
- Progress indicator (e.g., "3 of 5 lessons completed")
- List of lessons with completion checkmarks, scores, and links
- Visual emphasis for current unit (learner is working through)

```html
<div class="unit-card {% if unit.is_current %}current{% endif %}">
  <div class="unit-header">
    <span class="level-badge">{{ unit.level }}</span>
    <h3>{{ unit.title }}</h3>
    <p class="unit-description">{{ unit.description }}</p>
  </div>

  <div class="unit-progress">
    {{ unit.completed_count }} of {{ unit.total_count }} completed
  </div>

  <div class="lessons-list">
    {% for lesson in unit.lessons %}
      <div class="lesson-item">
        {% if lesson.is_completed %}
          <span class="checkmark">✓</span>
          <span class="score">{{ lesson.score }}%</span>
        {% else %}
          <span class="status">Not started</span>
        {% endif %}

        <a href="/lesson/{{ lesson.lesson.id }}" class="lesson-link">
          {{ lesson.lesson.title }}
        </a>
      </div>
    {% endfor %}
  </div>
</div>
```

### partials/learn_recommendation.html

Adaptive recommendation card showing:
- Next lesson suggestion with link (primary action)
- Review due count with link to review mode
- Weak categories needing practice (if any)
- Level readiness indicator
- Human-readable suggestion text

```html
<div class="recommendation-card">
  <h3>Today's Recommendation</h3>

  {% if next_lesson %}
  <div class="recommendation-primary">
    <p class="suggestion">{{ suggestion_text }}</p>
    <a href="/lesson/{{ next_lesson.id }}" class="btn btn-primary">
      Continue Learning →
    </a>
  </div>
  {% endif %}

  {% if review_due_count > 0 %}
  <div class="recommendation-review">
    <p>{{ review_due_count }} words due for review</p>
    <a href="/chat?mode=review" class="btn btn-secondary">
      Review Now
    </a>
  </div>
  {% endif %}

  {% if weak_categories %}
  <div class="recommendation-weak">
    <p class="label">Categories to strengthen:</p>
    <ul>
      {% for category in weak_categories %}
      <li>{{ category.category }} ({{ category.accuracy * 100 }}% accuracy)</li>
      {% endfor %}
    </ul>
  </div>
  {% endif %}

  {% if level_readiness and level_readiness.is_ready %}
  <div class="recommendation-advance">
    <p>🎉 Ready to advance to {{ level_readiness.next_level }}!</p>
    <a href="/learn?level={{ level_readiness.next_level }}" class="btn btn-accent">
      Next Level
    </a>
  </div>
  {% endif %}
</div>
```

---

## Integration

### Lesson Completion Flow

After completing a lesson, the completion view (`partials/lesson_complete.html`) now shows a "Continue Path" button. The `complete_lesson` route in `src/api/routes/lessons.py` computes the next lesson using `PathService.get_next_path_lesson()`.

```html
<!-- partials/lesson_complete.html -->
<div class="lesson-complete">
  <h2>Great work!</h2>

  {% if next_lesson %}
  <a href="/lesson/{{ next_lesson.id }}" class="btn btn-primary">
    Continue Path →
  </a>
  {% endif %}

  <a href="/learn" class="btn btn-secondary">
    View Learning Path
  </a>
</div>
```

### Router Mount

The learn router is mounted at `/learn` prefix in `src/api/main.py`:

```python
from src.api.routes import learn
app.include_router(learn.router, prefix="/learn")
```

---

## Testing

### Test Coverage (99 new tests)

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/test_paths_service.py` | 27 | Path building, progress computation, next lesson logic |
| `tests/test_adaptive_service.py` | 49 | Category strengths, level readiness, recommendations, suggestion text |
| `tests/test_learn_routes.py` | 23 | Pages, partials, error handling, guest vs authenticated access |

### Key Test Scenarios

**PathService tests:**
- Path builds correctly with 4 units × 5 lessons per language
- Missing lessons are excluded gracefully (path still builds)
- Progress overlay correctly maps flat completion records to hierarchical path structure
- Next lesson computation skips completed lessons in current unit
- Next lesson advances to next unit when current unit complete
- Returns None when entire path complete
- Completion percentage calculated and rounded correctly
- Language not found returns None

**AdaptiveService tests:**
- Category strengths computed from vocabulary accuracy data
- Weak categories detected (accuracy < 0.7 and words_seen > 0)
- Level readiness correctly identifies when all lessons in level complete
- Level readiness returns None at maximum level
- Recommendation includes next lesson (primary)
- Recommendation includes review due count
- Recommendation includes weak categories
- Recommendation includes level readiness when applicable
- Suggestion text generated for all combinations:
  - Only next lesson
  - Next lesson + review due
  - Next lesson + weak categories
  - Ready to advance to next level
  - All of the above prioritized correctly

**Learn routes tests:**
- `/learn/` renders correctly for authenticated users
- `/learn/` renders correctly for guests (no progress overlay)
- `/learn/?language=de` shows German path
- `/learn/?language=invalid` handles gracefully (404 or default)
- `/learn/recommendation` renders correctly for authenticated users
- `/learn/recommendation` renders generic card for guests
- HTMX lazy-load works correctly
- Page loads quickly without blocking on recommendation

---

## Files

### Created

- `src/services/paths.py` — PathService implementation (~340 lines)
- `src/services/adaptive.py` — AdaptiveService implementation (~310 lines)
- `src/api/routes/learn.py` — Learn page and recommendation routes (~215 lines)
- `src/templates/learn.html` — Learning path overview page (~98 lines)
- `src/templates/partials/learn_unit.html` — Unit card partial (~188 lines)
- `src/templates/partials/learn_recommendation.html` — Recommendation card partial (~68 lines)
- `tests/test_paths_service.py` — PathService tests (27 tests)
- `tests/test_adaptive_service.py` — AdaptiveService tests (49 tests)
- `tests/test_learn_routes.py` — Learn routes tests (23 tests)

### Modified

- `src/api/main.py` — Mount learn router at `/learn` prefix (+2 lines)
- `src/api/routes/lessons.py` — Add next_path_lesson to complete_lesson response (+15 lines)
- `src/templates/partials/lesson_complete.html` — Add "Continue Path" button (+12 lines)

---

## Success Criteria

- All 99 tests passing with >95% code coverage on new code
- Learn page loads in <200ms for authenticated users
- Recommendation partial loads within 500ms
- Path correctly reflects all 60 lessons across 3 languages and 4 levels
- Lesson completion surfaces next lesson via "Continue Path" button
- Adaptive recommendations prioritize correctly and suggest contextual actions
- Lazy loading of recommendation card doesn't block page load

---

## Future Enhancements (Out of Scope)

- Custom learning paths based on learner goals
- Path difficulty adjustments based on performance
- Recommended daily schedules
- Learning streaks and milestone celebrations
- Path analytics (average completion time, success rates by unit)
- Collaborative paths or peer learning integration

---

## Dependencies

- Existing LessonService and lesson catalog
- Existing LessonProgress tracking
- Existing Vocabulary model and accuracy tracking
- Existing authentication and OptionalUserDep
- Existing lesson completion endpoints
- HTMX for lazy-loading recommendations
