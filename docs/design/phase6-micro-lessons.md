# Phase 6: Micro-Lessons Design Document

> Structured 2-3 minute learning modules with vocabulary, examples, and interactive exercises

---

## Overview

Phase 6 introduces a **micro-lessons system** to Habla Hermano, providing structured learning content that complements the conversational AI tutor. This enables:

- **Structured Learning**: Bite-sized lessons with clear progression through vocabulary, examples, and practice
- **Interactive Exercises**: Multiple choice, fill-in-the-blank, and translation exercises with instant feedback
- **Guest Access**: Lessons accessible without authentication for onboarding new users
- **Chat Handoff**: Seamless transition from completed lessons to conversational practice with Hermano

**Business Value**: While free-form conversation is powerful, beginners often need structured content to build foundational vocabulary before they can engage meaningfully. Micro-lessons provide the scaffolding that makes the conversational experience accessible to true beginners.

**Learning Goal**: Master YAML-based content management, service layer patterns, and HTMX-driven interactive UI components.

---

## Requirements

### Functional Requirements

| Requirement | Priority | Description |
|-------------|----------|-------------|
| Lesson listing page | P0 | Browse available lessons grouped by difficulty level |
| Lesson player | P0 | Step-by-step interactive lesson experience |
| Step navigation | P0 | Next/previous navigation with progress tracking |
| Multiple exercise types | P0 | Support multiple_choice, fill_blank, translate exercises |
| Exercise validation | P0 | Check answers with instant feedback and explanations |
| Lesson completion | P0 | Celebration view with score and next steps |
| Chat handoff | P1 | Redirect to chat with lesson context after completion |
| Guest access | P0 | All lesson features work without authentication |

### Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Lesson load time | <200ms for YAML parsing and rendering |
| Step navigation | <100ms for HTMX partial updates |
| Content format | YAML files for easy content authoring |
| Accessibility | WCAG 2.1 AA compliant UI components |
| Mobile support | Touch-friendly navigation and exercises |

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Browser (HTMX)                               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  /lessons/           → Lesson list with grouping            │ │
│  │  /lessons/{id}/play  → Interactive lesson player            │ │
│  │  /lessons/{id}/step  → HTMX partial for step navigation     │ │
│  │  /lessons/{id}/exercise → Exercise rendering and submission │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  src/api/routes/lessons.py                                  │ │
│  │  - GET /lessons/              (lessons list page)           │ │
│  │  - GET /lessons/{id}/play     (lesson player)               │ │
│  │  - GET /lessons/{id}/step/{n} (step partial)                │ │
│  │  - POST /lessons/{id}/step/next|prev (navigation)           │ │
│  │  - GET /lessons/{id}/exercise/{id} (exercise partial)       │ │
│  │  - POST /lessons/{id}/exercise/{id}/submit (check answer)   │ │
│  │  - POST /lessons/{id}/complete (completion view)            │ │
│  │  - POST /lessons/{id}/handoff (redirect to chat)            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  src/lessons/service.py (LessonService)                     │ │
│  │  - Load lessons from YAML files                             │ │
│  │  - Filter by language, level, category                      │ │
│  │  - Extract vocabulary from steps                            │ │
│  │  - User progress integration (future)                       │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   YAML Lesson Files                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  data/lessons/es/A0/                                        │ │
│  │  ├── greetings-001.yaml                                     │ │
│  │  ├── introductions-001.yaml                                 │ │
│  │  ├── numbers-001.yaml                                       │ │
│  │  ├── colors-001.yaml                                        │ │
│  │  └── family-001.yaml                                        │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| `lessons.py` (routes) | HTTP endpoints, request validation, template rendering |
| `LessonService` | Content loading, filtering, vocabulary extraction |
| `models.py` | Data validation with Pydantic, exercise answer checking |
| YAML files | Content storage, easy authoring, version control friendly |
| Templates | HTMX-driven interactive UI components |

### Data Flow

1. **Lesson List**: User visits `/lessons/` -> Service loads metadata -> Grouped by beginner/intermediate -> Rendered with cards
2. **Start Lesson**: User clicks lesson -> Load full content -> Render player at step 0
3. **Navigate Steps**: HTMX POST to next/prev -> Return step partial -> Swap content, update progress bar
4. **Exercise**: Practice step loads exercise via HTMX GET -> User submits answer -> Validate and return feedback
5. **Complete**: User reaches end -> POST to complete -> Show celebration with score -> Option to practice with Hermano

---

## Data Models

### Enums

```python
class LessonLevel(str, Enum):
    """CEFR proficiency levels for lessons."""
    A0 = "A0"  # Absolute beginner
    A1 = "A1"  # Beginner
    A2 = "A2"  # Elementary
    B1 = "B1"  # Intermediate


class LessonStepType(str, Enum):
    """Types of lesson steps."""
    INSTRUCTION = "instruction"  # Text explanation
    VOCABULARY = "vocabulary"    # Word list with translations
    EXAMPLE = "example"          # Example sentence/phrase
    TIP = "tip"                  # Cultural note or learning tip
    PRACTICE = "practice"        # Exercise reference


class ExerciseType(str, Enum):
    """Types of exercises."""
    MULTIPLE_CHOICE = "multiple_choice"
    FILL_BLANK = "fill_blank"
    TRANSLATE = "translate"
```

### LessonMetadata

Lightweight metadata for listing and filtering:

```python
class LessonMetadata(BaseModel):
    id: str                           # Unique slug (e.g., "greetings-001")
    title: str                        # Display title
    description: str                  # Brief description
    language: str                     # Target language (es, de, fr)
    level: LessonLevel               # CEFR level
    estimated_minutes: int = 2        # Expected duration
    category: str | None = None       # Grouping category
    tags: list[str] = []             # Searchable tags
    prerequisites: list[str] = []    # Required lesson IDs
    vocabulary_count: int = 0         # Word count for display
    icon: str = "📚"                  # Emoji icon
```

### LessonStep

Individual step within a lesson:

```python
class LessonStep(BaseModel):
    type: LessonStepType             # Step type
    content: str                      # Main text content
    order: int                        # Display order (1-based)
    target_text: str | None = None    # Text in target language
    translation: str | None = None    # English translation
    vocabulary: list[dict] = []       # Word/translation pairs
    exercise_id: str | None = None    # Reference to exercise
    audio_url: str | None = None      # Optional audio file
```

### Exercise Models

Three exercise types with answer validation:

```python
class MultipleChoiceExercise(Exercise):
    type: ExerciseType = ExerciseType.MULTIPLE_CHOICE
    question: str
    options: list[str]               # At least 2 options required
    correct_index: int               # 0-based index
    explanation: str | None = None


class FillBlankExercise(Exercise):
    type: ExerciseType = ExerciseType.FILL_BLANK
    sentence_template: str           # Contains _____ placeholder
    correct_answer: str
    hint: str | None = None
    accept_alternatives: list[str] = []

    def check_answer(self, answer: str) -> bool:
        """Case-insensitive match with alternatives."""


class TranslateExercise(Exercise):
    type: ExerciseType = ExerciseType.TRANSLATE
    source_text: str
    source_language: str
    target_language: str
    correct_translation: str
    accept_alternatives: list[str] = []

    def check_answer(self, answer: str) -> bool:
        """Case-insensitive match with alternatives."""
```

### Full Lesson

Combines metadata and content:

```python
class Lesson(BaseModel):
    metadata: LessonMetadata
    content: LessonContent           # Steps and exercises

    @property
    def step_count(self) -> int
    @property
    def exercise_count(self) -> int


class LessonContent(BaseModel):
    steps: list[LessonStep] = []
    exercises: list[AnyExercise] = []

    def get_ordered_steps(self) -> list[LessonStep]
    def get_exercise_by_id(self, id: str) -> AnyExercise | None
```

### UserLessonProgress (Future)

For tracking user completion:

```python
class UserLessonProgress(BaseModel):
    user_id: str
    lesson_id: str
    started_at: datetime
    completed_at: datetime | None = None
    current_step: int = 0
    completed_exercises: list[str] = []
    exercise_results: dict[str, bool] = {}

    @property
    def is_completed(self) -> bool
    @property
    def completion_percentage(self) -> float
    @property
    def score(self) -> int
```

---

## API Design

### Route Summary

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/lessons/` | Lessons list page | Optional |
| GET | `/lessons/{id}/play` | Lesson player page | Optional |
| GET | `/lessons/{id}/step/{n}` | Step partial (HTMX) | Optional |
| POST | `/lessons/{id}/step/next` | Next step navigation | Optional |
| POST | `/lessons/{id}/step/prev` | Previous step navigation | Optional |
| GET | `/lessons/{id}/exercise/{id}` | Exercise partial (HTMX) | Optional |
| POST | `/lessons/{id}/exercise/{id}/submit` | Submit answer | Optional |
| POST | `/lessons/{id}/complete` | Completion view | Optional |
| POST | `/lessons/{id}/handoff` | Redirect to chat | Optional |

### Endpoint Details

#### GET /lessons/

Renders lessons overview page with optional filters.

**Query Parameters**:
- `language` (optional): Filter by language code (es, de, fr)
- `level` (optional): Filter by CEFR level (A0, A1, A2, B1)

**Response**: HTML page with lessons grouped by difficulty (beginner/intermediate)

```python
@router.get("/", response_class=HTMLResponse)
async def get_lessons_page(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    lesson_service: LessonServiceDep,
    language: str | None = None,
    level: str | None = None,
) -> HTMLResponse
```

#### GET /lessons/{lesson_id}/play

Renders interactive lesson player starting at step 0.

**Response**: Full HTML page with lesson content and navigation

**Error**: 404 if lesson not found

#### POST /lessons/{lesson_id}/step/next

Navigate to next step (HTMX).

**Form Data**:
- `current_step`: Current step index (0-based)

**Response**: Partial HTML for next step with updated progress

**Behavior**: Clamps to last step if already at end

#### POST /lessons/{lesson_id}/exercise/{exercise_id}/submit

Validate exercise answer and return feedback.

**Form Data**:
- `answer`: User's submitted answer

**Response**: HTML feedback with correct/incorrect status and explanation

**Answer Checking**:
- Multiple choice: Compare index to correct_index
- Fill blank: Case-insensitive match with alternatives
- Translate: Case-insensitive match with alternatives

#### POST /lessons/{lesson_id}/handoff

Redirect to chat with lesson context.

**Response**: Empty body with `HX-Redirect: /chat?lesson={id}&topic={category}`

---

## Template Structure

### Page Templates

| Template | Purpose |
|----------|---------|
| `lessons.html` | Lessons overview with grouped cards |
| `lesson_player.html` | Full lesson player with progress bar and navigation |

### Partial Templates (HTMX)

| Template | Purpose |
|----------|---------|
| `partials/lesson_step.html` | Single step content (instruction, vocabulary, example, tip, practice) |
| `partials/lesson_exercise.html` | Exercise UI (multiple choice, fill blank, translate) |
| `partials/lesson_complete.html` | Completion celebration with score and actions |

### Step Type Rendering

The `lesson_step.html` partial renders different UI based on step type:

```html
{% if step.type.value == 'instruction' %}
    <!-- Text explanation with prose styling -->

{% elif step.type.value == 'vocabulary' %}
    <!-- Grid of word/translation cards -->

{% elif step.type.value == 'example' %}
    <!-- Target text with translation -->

{% elif step.type.value == 'tip' %}
    <!-- Yellow accent box with lightbulb icon -->

{% elif step.type.value == 'practice' %}
    <!-- Loads exercise via HTMX on render -->
{% endif %}
```

### Exercise Type Rendering

The `lesson_exercise.html` partial renders exercise-specific UI:

```html
{% if exercise.type.value == 'multiple_choice' %}
    <!-- Radio button options with form submission -->

{% elif exercise.type.value == 'fill_blank' %}
    <!-- Text input with hint and validation -->

{% elif exercise.type.value == 'translate' %}
    <!-- Source text display with translation input -->
{% endif %}
```

### HTMX Integration

Key HTMX patterns used:

1. **Step Navigation**: Button posts to `/step/next`, targets `#step-content`, swaps innerHTML
2. **Progress Updates**: JavaScript listens to `htmx:afterSwap` to update progress bar from data attributes
3. **Exercise Loading**: Practice steps use `hx-trigger="load"` to fetch exercise on render
4. **Answer Submission**: Form posts to submit endpoint, targets `.exercise` container for feedback
5. **Chat Handoff**: Button uses `hx-swap="none"` with server-side `HX-Redirect` header

---

## YAML Content Format

### Lesson File Structure

```yaml
# Metadata
id: greetings-001
title: Basic Greetings
description: Learn to say hello and goodbye in Spanish
language: es
level: A0
estimated_minutes: 3
category: greetings
tags: [greeting, basics, hello, goodbye]
vocabulary_count: 6
icon: "👋"

# Content Steps
steps:
  - type: instruction
    content: "Welcome message and introduction..."
    order: 1

  - type: vocabulary
    content: "Key vocabulary for this lesson:"
    vocabulary:
      - word: hola
        translation: hello
      - word: adios
        translation: goodbye
    order: 2

  - type: example
    content: "Hola, como estas?"
    translation: "Hello, how are you?"
    order: 3

  - type: tip
    content: "Cultural tip about usage..."
    order: 4

  - type: practice
    content: "Test your knowledge!"
    exercise_id: "ex-mc-greet-001"
    order: 5

# Exercises
exercises:
  - id: ex-mc-greet-001
    type: multiple_choice
    question: "How do you say 'hello' in Spanish?"
    options: [Hola, Adios, Gracias, Por favor]
    correct_index: 0
    explanation: "Hola means 'hello' in Spanish."
```

### Initial Content

Phase 6 includes 5 Spanish A0 lessons:

| Lesson ID | Title | Category | Vocabulary |
|-----------|-------|----------|------------|
| `greetings-001` | Basic Greetings | greetings | 6 words |
| `introductions-001` | Introducing Yourself | introductions | 8 words |
| `numbers-001` | Numbers 1-10 | numbers | 10 words |
| `colors-001` | Colors | colors | 8 words |
| `family-001` | Family Members | family | 8 words |

---

## Testing Strategy

### Test Coverage

Phase 6 added **95 new tests** with comprehensive coverage:

| Test File | Tests | Coverage Area |
|-----------|-------|---------------|
| `test_lesson_models.py` | ~150 | Pydantic models, validation, exercise checking |
| `test_lesson_service.py` | ~100 | YAML loading, filtering, vocabulary extraction |
| `test_lesson_routes.py` | ~150 | API endpoints, HTMX responses, error handling |
| `test_lessons_progress_routes.py` | ~200 | Progress tracking, user integration |

### Unit Tests

**Model Tests** (`test_lesson_models.py`):
- Enum value validation
- LessonMetadata field validation (language support, level enum)
- LessonStep type handling and optional fields
- Exercise validation (minimum options, correct_index bounds)
- Answer checking methods (case insensitivity, alternatives)
- UserLessonProgress calculations (completion %, score)

**Service Tests** (`test_lesson_service.py`):
- YAML file loading from directory
- Lesson filtering by language, level, category
- Vocabulary extraction from steps
- Metadata-only retrieval for listing
- Progress integration helpers
- Error handling for malformed files

### Integration Tests

**Route Tests** (`test_lesson_routes.py`):
- GET /lessons/ returns grouped lessons HTML
- GET /lessons/{id}/play returns player with step content
- Step navigation returns correct partials
- Exercise submission validates answers
- 404 handling for missing lessons/steps/exercises
- Filter query parameters work correctly

### E2E Tests (Playwright)

Browser-level tests for user flows:
- Browse lessons page and filter by level
- Start lesson and navigate through all steps
- Complete multiple choice exercise correctly
- Complete fill-blank exercise with hint
- Reach completion screen and see score
- Handoff to chat with lesson context

---

## Implementation Plan

### File Summary

| File | Action | Description |
|------|--------|-------------|
| `src/lessons/models.py` | Create | Pydantic models for lessons, steps, exercises |
| `src/lessons/service.py` | Create | LessonService for loading and filtering |
| `src/api/routes/lessons.py` | Create | FastAPI routes for lesson endpoints |
| `src/api/dependencies.py` | Modify | Add LessonServiceDep |
| `src/templates/lessons.html` | Create | Lessons list page |
| `src/templates/lesson_player.html` | Create | Interactive lesson player |
| `src/templates/partials/lesson_step.html` | Create | Step content partial |
| `src/templates/partials/lesson_exercise.html` | Create | Exercise partial |
| `src/templates/partials/lesson_complete.html` | Create | Completion partial |
| `data/lessons/es/A0/*.yaml` | Create | 5 Spanish A0 lessons |
| `tests/test_lesson_*.py` | Create | 4 comprehensive test files |

### Dependency Injection

Added `LessonServiceDep` to `dependencies.py`:

```python
from src.lessons.service import LessonService, get_lesson_service

LessonServiceDep = Annotated[LessonService, Depends(get_lesson_service)]
```

The `get_lesson_service()` function uses `@lru_cache` for singleton behavior, loading YAML files once at startup.

### Authentication Pattern

All lesson routes use `OptionalUserDep` for guest access:

```python
from src.api.auth import OptionalUserDep

@router.get("/{lesson_id}/play")
async def get_lesson_player(
    user: OptionalUserDep,  # None for guests, AuthenticatedUser if logged in
    ...
)
```

This allows:
- Guests to try lessons without signup (onboarding)
- Authenticated users to get progress tracking (future)

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| YAML parsing errors | Medium | Low | Graceful error handling, continue loading other files |
| Large lesson files | Low | Medium | Lazy loading, pagination for very long lessons |
| Exercise answer edge cases | Medium | Low | Case-insensitive matching, alternatives list |
| Progress loss for guests | Medium | Medium | LocalStorage backup, encourage signup |
| Accessibility issues | Medium | High | WCAG compliance, keyboard navigation, screen reader testing |

---

## Future Considerations

### Phase 6.1: Progress Persistence

- Store UserLessonProgress in Supabase
- Show completion badges on lesson cards
- Track exercise accuracy over time
- Resume lessons from last step

### Phase 6.2: Content Expansion

- Add more languages (German, French)
- Create A1-B1 level content
- Add audio pronunciation files
- Support image-based exercises

### Phase 6.3: Adaptive Learning

- Recommend lessons based on conversation performance
- Surface vocabulary from lessons in chat scaffolding
- Spaced repetition for vocabulary review
- Progress-based level suggestions

### Phase 6.4: Content Authoring

- Admin interface for lesson creation
- Preview mode for authors
- Lesson analytics (completion rate, exercise accuracy)
- A/B testing for exercise types

---

## Success Criteria

### Functional

- [x] Users can browse lessons grouped by difficulty
- [x] Users can complete a full lesson with all step types
- [x] Exercises validate answers with feedback
- [x] Completion view shows score and vocabulary count
- [x] Handoff to chat works with lesson context
- [x] All features work for unauthenticated guests

### Technical

- [x] YAML lessons load correctly at startup
- [x] Service layer provides clean API for routes
- [x] HTMX navigation updates progress without full page reload
- [x] All existing tests pass (maintained 98% coverage)
- [x] 95 new tests added with comprehensive coverage

### Performance

- [x] Lesson list renders in <200ms
- [x] Step navigation feels instant (<100ms HTMX swap)
- [x] No blocking operations in request handlers

---

## Appendix: LessonService API Reference

```python
class LessonService:
    """Service for loading and managing lessons."""

    def __init__(self, lessons_dir: Path | None = None) -> None
        """Initialize with optional custom directory."""

    def get_lesson(self, lesson_id: str) -> Lesson | None
        """Get a single lesson by ID."""

    def get_all_lessons(self) -> list[Lesson]
        """Get all loaded lessons."""

    def get_lessons(
        self,
        language: str | None = None,
        level: LessonLevel | None = None,
        category: str | None = None,
    ) -> list[Lesson]
        """Get lessons with optional filters."""

    def get_lessons_metadata(
        self,
        language: str | None = None,
        level: LessonLevel | None = None,
    ) -> list[LessonMetadata]
        """Get only metadata for listing."""

    def get_categories(self, language: str | None = None) -> list[str]
        """Get unique categories."""

    def get_lesson_vocabulary(self, lesson_id: str) -> list[dict[str, str]]
        """Extract vocabulary from lesson steps."""

    def get_lessons_with_progress(
        self,
        user_id: str,
        progress_data: list[UserLessonProgress],
        language: str | None = None,
        level: LessonLevel | None = None,
    ) -> list[LessonWithProgress]
        """Merge lessons with user progress."""

    def get_next_recommended(
        self,
        user_id: str,
        progress_data: list[UserLessonProgress],
        language: str,
        level: LessonLevel,
    ) -> Lesson | None
        """Get next uncompleted lesson for a user."""
```
