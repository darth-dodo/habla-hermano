# Phase 7: Progress Tracking Design Document

> Real-time learning analytics with Supabase persistence and Chart.js visualizations

---

## Overview

Phase 7 introduces a **progress tracking system** to Habla Hermano, providing users with visibility into their learning journey through aggregated statistics and visual charts. This enables:

- **Learning Analytics**: Dashboard with vocabulary counts, session history, streak tracking, and accuracy metrics
- **Visual Progress**: Chart.js line charts showing vocabulary growth and accuracy trends over time
- **Data Capture**: Automatic persistence of vocabulary and session data during chat interactions
- **Guest Support**: Progress tracking works for both authenticated users and guest sessions

**Business Value**: Progress visibility is a key motivator for language learners. Seeing vocabulary growth, maintaining streaks, and tracking accuracy provides positive reinforcement that keeps users engaged and returning to practice.

**Learning Goal**: Master service layer aggregation patterns, Chart.js integration with HTMX, and fire-and-forget data persistence strategies.

---

## Goals

### Primary Goals

1. **Aggregate Learning Data**: Combine vocabulary, session, and lesson data into dashboard-ready statistics
2. **Visualize Progress**: Render vocabulary growth and accuracy trends using Chart.js
3. **Capture Activity Automatically**: Persist learning data during chat interactions without blocking responses
4. **Support All Users**: Work for both authenticated users (via RLS) and guests (via session cookies)

### Success Metrics

| Metric | Target |
|--------|--------|
| Dashboard load time | <300ms for stats rendering |
| Chart data endpoint | <200ms JSON response |
| Data capture latency | <50ms (fire-and-forget) |
| Test coverage | 30-40 unit tests for ProgressService |

---

## Requirements

### Functional Requirements

| Requirement | Priority | Description |
|-------------|----------|-------------|
| Dashboard page | P0 | Display aggregated statistics with real data from Supabase |
| Statistics cards | P0 | Show total words, sessions, lessons completed, and streak |
| Vocabulary list | P0 | Display learned words with delete capability |
| Chart visualization | P0 | Vocabulary growth and accuracy trend charts |
| Data capture hooks | P0 | Record vocabulary and sessions during chat |
| Guest progress | P1 | Support progress tracking for unauthenticated users |
| Language filtering | P1 | Filter vocabulary and stats by target language |

### Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Dashboard render time | <300ms for full page with stats |
| Chart data response | <200ms for JSON endpoint |
| Data capture impact | <50ms overhead on chat responses |
| Error tolerance | Data capture failures must not block chat |
| CDN dependency | Chart.js v4.4.1 via CDN (no build step) |

---

## Architecture

### System Overview

```
+---------------------------------------------------------------------+
|                        Browser (HTMX + Chart.js)                     |
|  +----------------------------------------------------------------+ |
|  |  /progress/           -> Dashboard page with stats cards        | |
|  |  /progress/stats      -> Stats partial (HTMX refresh)           | |
|  |  /progress/vocabulary -> Vocabulary list partial (HTMX)         | |
|  |  /progress/chart-data -> JSON data for Chart.js                 | |
|  +----------------------------------------------------------------+ |
+---------------------------------------------------------------------+
                                   |
                                   v
+---------------------------------------------------------------------+
|                        FastAPI Backend                               |
|  +----------------------------------------------------------------+ |
|  |  src/api/routes/progress.py                                     | |
|  |  - GET /progress/              (dashboard page)                 | |
|  |  - GET /progress/stats         (stats partial)                  | |
|  |  - GET /progress/vocabulary    (vocabulary partial)             | |
|  |  - GET /progress/chart-data    (JSON for charts)                | |
|  |  - DELETE /progress/vocabulary/{id} (remove word)               | |
|  +----------------------------------------------------------------+ |
|                                   |                                  |
|                                   v                                  |
|  +----------------------------------------------------------------+ |
|  |  src/services/progress.py (ProgressService)                     | |
|  |  - get_dashboard_stats()   -> DashboardStats                    | |
|  |  - get_chart_data()        -> ChartData                         | |
|  |  - record_chat_activity()  -> None (fire-and-forget)            | |
|  +----------------------------------------------------------------+ |
|                                   |                                  |
|                                   v                                  |
|  +----------------------------------------------------------------+ |
|  |  src/db/repository.py (Existing Repositories)                   | |
|  |  - VocabularyRepository                                         | |
|  |  - LearningSessionRepository                                    | |
|  |  - LessonProgressRepository                                     | |
|  +----------------------------------------------------------------+ |
+---------------------------------------------------------------------+
                                   |
                                   v
+---------------------------------------------------------------------+
|                        Supabase Postgres                             |
|  +----------------------------------------------------------------+ |
|  |  Tables:                                                        | |
|  |  - vocabulary (user words with times_seen/times_correct)        | |
|  |  - learning_sessions (chat sessions with message counts)        | |
|  |  - lesson_progress (completed lessons with scores)              | |
|  +----------------------------------------------------------------+ |
+---------------------------------------------------------------------+
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| `progress.py` (routes) | HTTP endpoints, template rendering, identity resolution |
| `ProgressService` | Data aggregation, metric computation, chart data generation |
| `VocabularyRepository` | CRUD for vocabulary table |
| `LearningSessionRepository` | CRUD for learning_sessions table |
| `LessonProgressRepository` | CRUD for lesson_progress table |
| Templates | Dashboard UI with Chart.js integration |

### Data Flow

1. **Dashboard Load**: User visits `/progress/` -> `ProgressService.get_dashboard_stats()` aggregates data -> Template renders with stats cards
2. **Chart Render**: Page loads -> JavaScript fetches `/progress/chart-data` -> Chart.js renders line charts
3. **Vocabulary View**: HTMX GET to `/progress/vocabulary` -> Repository fetches words -> Partial renders list
4. **Chat Activity**: User chats -> `chat.py` extracts vocabulary from graph result -> `ProgressService.record_chat_activity()` persists data (fire-and-forget)
5. **Lesson Completion**: User completes lesson -> `lessons.py` calls `LessonProgressRepository.complete_lesson()`

---

## Data Models

### DashboardStats Dataclass

Aggregated statistics for the user dashboard:

```python
@dataclass(frozen=True)
class DashboardStats:
    """Aggregated statistics for the user dashboard."""

    total_words: int           # Count of unique vocabulary entries
    total_sessions: int        # Count of learning sessions
    lessons_completed: int     # Count of completed lessons
    current_streak: int        # Consecutive days with activity
    accuracy_rate: float       # 0.0-100.0 percentage
    words_learned_today: int   # Words with first_seen_at == today
    messages_today: int        # Sum of messages_count for today's sessions
```

### ChartData Dataclass

Chart data for vocabulary growth and accuracy trends:

```python
@dataclass(frozen=True)
class VocabGrowthPoint:
    """A single point on the vocabulary growth chart."""
    date: str              # ISO date string YYYY-MM-DD
    cumulative_words: int  # Total words up to this date


@dataclass(frozen=True)
class AccuracyPoint:
    """A single point on the accuracy trend chart."""
    date: str         # ISO date string YYYY-MM-DD
    accuracy: float   # 0.0-100.0 percentage


@dataclass(frozen=True)
class ChartData:
    """Chart data for vocabulary growth and accuracy trends."""
    vocab_growth: list[VocabGrowthPoint]
    accuracy_trend: list[AccuracyPoint]

    def to_dict(self) -> dict:
        """Serialize chart data to a plain dictionary for JSON responses."""
        return {
            "vocab_growth": [asdict(p) for p in self.vocab_growth],
            "accuracy_trend": [asdict(p) for p in self.accuracy_trend],
        }
```

---

## Database Schema

### vocabulary Table

Stores vocabulary words learned by users:

```sql
CREATE TABLE vocabulary (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    word TEXT NOT NULL,
    translation TEXT NOT NULL,
    language VARCHAR(5) NOT NULL DEFAULT 'es',
    part_of_speech VARCHAR(50),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    times_seen INTEGER NOT NULL DEFAULT 1,
    times_correct INTEGER NOT NULL DEFAULT 0,

    -- Composite unique constraint for upsert logic
    UNIQUE(user_id, word, language)
);

-- Indexes for common queries
CREATE INDEX idx_vocabulary_user_language ON vocabulary(user_id, language);
CREATE INDEX idx_vocabulary_first_seen ON vocabulary(first_seen_at DESC);
```

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGSERIAL | Auto-generated primary key |
| `user_id` | UUID | Reference to auth.users or guest session ID |
| `word` | TEXT | The vocabulary word in target language |
| `translation` | TEXT | Translation to user's native language |
| `language` | VARCHAR(5) | Target language code (es, de) |
| `part_of_speech` | VARCHAR(50) | Optional grammatical category (noun, verb, etc.) |
| `first_seen_at` | TIMESTAMPTZ | When the word was first encountered |
| `times_seen` | INTEGER | Count of times word appeared in chat |
| `times_correct` | INTEGER | Count of correct uses (for accuracy calculation) |

### learning_sessions Table

Tracks individual chat sessions:

```sql
CREATE TABLE learning_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    language VARCHAR(5) NOT NULL DEFAULT 'es',
    level VARCHAR(5) NOT NULL DEFAULT 'A1',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    messages_count INTEGER NOT NULL DEFAULT 0,
    words_learned INTEGER NOT NULL DEFAULT 0
);

-- Indexes for session queries
CREATE INDEX idx_sessions_user_started ON learning_sessions(user_id, started_at DESC);
CREATE INDEX idx_sessions_active ON learning_sessions(user_id) WHERE ended_at IS NULL;
```

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGSERIAL | Auto-generated primary key |
| `user_id` | UUID | Reference to auth.users or guest session ID |
| `language` | VARCHAR(5) | Target language for this session |
| `level` | VARCHAR(5) | CEFR level (A0, A1, A2, B1) |
| `started_at` | TIMESTAMPTZ | Session start timestamp |
| `ended_at` | TIMESTAMPTZ | Session end timestamp (NULL if active) |
| `messages_count` | INTEGER | Total messages exchanged in session |
| `words_learned` | INTEGER | New vocabulary words introduced |

### lesson_progress Table

Tracks completed micro-lessons:

```sql
CREATE TABLE lesson_progress (
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    lesson_id TEXT NOT NULL,
    completed_at TIMESTAMPTZ,
    score INTEGER CHECK (score >= 0 AND score <= 100),

    PRIMARY KEY (user_id, lesson_id)
);

-- Index for completion queries
CREATE INDEX idx_lesson_progress_completed ON lesson_progress(user_id, completed_at DESC);
```

| Column | Type | Description |
|--------|------|-------------|
| `user_id` | UUID | Reference to auth.users or guest session ID |
| `lesson_id` | TEXT | Lesson identifier (e.g., "greetings-001") |
| `completed_at` | TIMESTAMPTZ | When lesson was completed (NULL if started but not finished) |
| `score` | INTEGER | Optional score 0-100 from exercises |

---

## ProgressService Class

### Class Overview

```python
class ProgressService:
    """Aggregates data from repositories into dashboard-ready structures.

    This service is read-heavy and designed for dashboard rendering.
    It pulls data from vocabulary, session, and lesson repositories,
    then computes derived metrics like streaks, accuracy, and trends.
    """

    def __init__(self, user_id: str, client: SupabaseClient | None = None) -> None:
        """Initialize progress service for a user.

        Args:
            user_id: Supabase auth user UUID or guest session UUID.
            client: Optional Supabase client to pass through to repositories.
                    When None each repository defaults to the anon client.
                    Pass the admin client for guest (session-based) access.
        """
```

### Method: get_dashboard_stats

```python
def get_dashboard_stats(self, language: str = "es") -> DashboardStats:
    """Get aggregated dashboard statistics.

    Computes total words, sessions, lessons completed, current streak,
    accuracy rate, and today's activity metrics.

    Args:
        language: Target language code to filter vocabulary by.

    Returns:
        DashboardStats with all computed metrics.

    Algorithm:
        1. Fetch all vocabulary for user/language
        2. Fetch all learning sessions
        3. Fetch completed lessons
        4. Calculate accuracy: sum(times_correct) / sum(times_seen) * 100
        5. Calculate streak via _calculate_streak()
        6. Count words/messages for today
    """
```

### Method: get_chart_data

```python
def get_chart_data(self, language: str = "es", days: int = 30) -> ChartData:
    """Get chart data for the last N days.

    Produces two series: cumulative vocabulary growth and accuracy trend
    over the specified date range.

    Args:
        language: Target language code to filter vocabulary by.
        days: Number of days to include in the chart.

    Returns:
        ChartData with vocab_growth and accuracy_trend point lists.

    Algorithm:
        1. Fetch all vocabulary for user/language
        2. For each day in range:
           a. Count words with first_seen_at <= date (cumulative)
           b. Calculate accuracy from vocab seen up to date
        3. Return ChartData with both series
    """
```

### Method: record_chat_activity

```python
def record_chat_activity(self, language: str, level: str, new_vocab: list[dict]) -> None:
    """Record vocabulary and session data after a chat interaction.

    Fire-and-forget: logs errors but does not raise, so callers
    are never blocked by persistence failures.

    Args:
        language: Target language code (es, de).
        level: CEFR level (A0, A1, A2, B1).
        new_vocab: List of dicts with keys: word, translation,
                   and optionally part_of_speech.

    Behavior:
        1. Upsert each vocabulary word (increments times_seen if exists)
        2. Get or create active learning session
        3. Log any errors but never raise
    """
```

### Method: _calculate_streak (Private)

```python
def _calculate_streak(self, sessions: list[LearningSession]) -> int:
    """Calculate consecutive days with activity from today backwards.

    A streak counts the number of consecutive calendar days (ending today)
    that have at least one learning session. If there is no session today,
    the streak is 0.

    Args:
        sessions: List of LearningSession objects.

    Returns:
        Number of consecutive active days ending today.

    Algorithm:
        1. Extract unique dates from sessions
        2. If today not in dates, return 0
        3. Walk backwards from today, counting consecutive days in set
    """
```

---

## API Endpoints

### Route Summary

| Method | Path | Response | Description |
|--------|------|----------|-------------|
| GET | `/progress/` | HTML | Dashboard page with stats |
| GET | `/progress/stats` | HTML partial | Stats cards for HTMX refresh |
| GET | `/progress/vocabulary` | HTML partial | Vocabulary list with delete buttons |
| GET | `/progress/chart-data` | JSON | Chart.js data for rendering |
| DELETE | `/progress/vocabulary/{id}` | Empty HTML | Remove word (HTMX swap) |

### GET /progress/

Renders the main progress dashboard page.

**Query Parameters**: None

**Response**: Full HTML page with stats cards and chart containers

**Example Response Context**:
```python
{
    "total_words": 42,
    "sessions_count": 15,
    "current_streak": 3,
    "lessons_completed": 5,
    "vocabulary": [],  # Loaded via HTMX partial
    "user": AuthenticatedUser | None,
    "is_guest": True | False,
}
```

### GET /progress/stats

Returns stats summary as HTML partial for HTMX refresh.

**Query Parameters**: None

**Response**: HTML partial with stats cards

**Example Response Context**:
```python
{
    "total_words": 42,
    "total_sessions": 15,
    "lessons_completed": 5,
    "current_streak": 3,
    "accuracy_rate": 78.5,
    "words_learned_today": 5,
    "messages_today": 23,
}
```

### GET /progress/vocabulary

Returns vocabulary list as HTML partial.

**Query Parameters**:
- `language` (optional): Filter by language code. Default: `es`

**Response**: HTML partial with vocabulary items

**Example Request**:
```
GET /progress/vocabulary?language=es
```

### GET /progress/chart-data

Returns chart data as JSON for Chart.js.

**Query Parameters**:
- `language` (optional): Filter by language code. Default: `es`
- `days` (optional): Number of days of history. Default: `30`

**Response**: JSON with vocab_growth and accuracy_trend arrays

**Example Request**:
```
GET /progress/chart-data?language=es&days=30
```

**Example Response**:
```json
{
    "vocab_growth": [
        {"date": "2025-01-01", "cumulative_words": 10},
        {"date": "2025-01-02", "cumulative_words": 15},
        {"date": "2025-01-03", "cumulative_words": 18}
    ],
    "accuracy_trend": [
        {"date": "2025-01-01", "accuracy": 72.5},
        {"date": "2025-01-02", "accuracy": 75.0},
        {"date": "2025-01-03", "accuracy": 78.5}
    ]
}
```

### DELETE /progress/vocabulary/{word_id}

Removes a vocabulary word from the user's list.

**Path Parameters**:
- `word_id`: Database ID of the vocabulary entry

**Response**: Empty HTML (for HTMX swap removal)

**Example Request**:
```
DELETE /progress/vocabulary/123
```

---

## Data Flow Diagrams

### Dashboard Load Flow

```
User                    Browser                  FastAPI                  ProgressService           Supabase
  |                        |                        |                           |                      |
  |-- Visit /progress/ --->|                        |                           |                      |
  |                        |-- GET /progress/ ----->|                           |                      |
  |                        |                        |-- get_dashboard_stats() ->|                      |
  |                        |                        |                           |-- SELECT vocabulary ->|
  |                        |                        |                           |<-- vocab rows --------|
  |                        |                        |                           |-- SELECT sessions --->|
  |                        |                        |                           |<-- session rows ------|
  |                        |                        |                           |-- SELECT lessons ---->|
  |                        |                        |                           |<-- lesson rows -------|
  |                        |                        |<-- DashboardStats --------|                      |
  |                        |<-- HTML (stats cards) -|                           |                      |
  |<-- Render page --------|                        |                           |                      |
  |                        |                        |                           |                      |
  |                        |-- GET /chart-data ---->|                           |                      |
  |                        |                        |-- get_chart_data() ------>|                      |
  |                        |                        |                           |-- SELECT vocabulary ->|
  |                        |                        |                           |<-- vocab rows --------|
  |                        |                        |<-- ChartData -------------|                      |
  |                        |<-- JSON ---------------|                           |                      |
  |                        |-- Render Chart.js ---->|                           |                      |
  |<-- Charts visible -----|                        |                           |                      |
```

### Chat Activity Recording Flow

```
User                    Browser                  ChatRoute                ProgressService           Supabase
  |                        |                        |                           |                      |
  |-- Send message ------->|                        |                           |                      |
  |                        |-- POST /chat/send ---->|                           |                      |
  |                        |                        |-- Invoke LangGraph ------>|                      |
  |                        |                        |<-- Result (new_vocab) ----|                      |
  |                        |                        |                           |                      |
  |                        |                        |-- record_chat_activity() >|                      |
  |                        |                        |   (fire-and-forget)       |-- UPSERT vocabulary->|
  |                        |                        |                           |<-- OK ---------------|
  |                        |                        |                           |-- SELECT session --->|
  |                        |                        |                           |<-- session or NULL --|
  |                        |                        |                           |-- INSERT session --->| (if needed)
  |                        |                        |                           |<-- OK ---------------|
  |                        |<-- Response (no wait) -|                           |                      |
  |<-- AI response --------|                        |                           |                      |
```

### Guest User Identity Resolution

```
Request                 progress.py              _resolve_identity()         Supabase
  |                        |                           |                        |
  |-- Cookie: session_id ->|                           |                        |
  |                        |-- _resolve_identity() --->|                        |
  |                        |   (user=None, session_id) |                        |
  |                        |                           |-- get_supabase_admin()->|
  |                        |                           |<-- admin_client --------|
  |                        |<-- (session_id, client) --|                        |
  |                        |                           |                        |
  |                        |-- ProgressService(       |                        |
  |                        |     session_id,          |                        |
  |                        |     client=admin_client  |                        |
  |                        |   )                      |                        |
```

---

## Template Structure

### Page Templates

| Template | Purpose |
|----------|---------|
| `progress.html` | Main dashboard page with Chart.js integration |

### Partial Templates (HTMX)

| Template | Purpose |
|----------|---------|
| `partials/stats_summary.html` | Stats cards (words, sessions, streak, accuracy) |
| `partials/progress_vocab.html` | Vocabulary list with delete buttons |

### progress.html Structure

```html
{% extends "base.html" %}

{% block content %}
<div class="progress-dashboard">
    <!-- Stats Cards Section -->
    <div id="stats-container"
         hx-get="/progress/stats"
         hx-trigger="load, refresh-stats from:body"
         hx-swap="innerHTML">
        <!-- Initial stats rendered server-side -->
        {% include "partials/stats_summary.html" %}
    </div>

    <!-- Charts Section -->
    <div class="charts-container">
        <canvas id="vocab-growth-chart"></canvas>
        <canvas id="accuracy-trend-chart"></canvas>
    </div>

    <!-- Vocabulary List Section -->
    <div id="vocabulary-container"
         hx-get="/progress/vocabulary"
         hx-trigger="load"
         hx-swap="innerHTML">
        <!-- Loaded via HTMX -->
    </div>
</div>

<!-- Chart.js CDN -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script>
    // Fetch chart data and render
    fetch('/progress/chart-data')
        .then(r => r.json())
        .then(data => {
            renderVocabGrowthChart(data.vocab_growth);
            renderAccuracyTrendChart(data.accuracy_trend);
        });

    function renderVocabGrowthChart(data) {
        const ctx = document.getElementById('vocab-growth-chart');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(p => p.date),
                datasets: [{
                    label: 'Vocabulary',
                    data: data.map(p => p.cumulative_words),
                    borderColor: getComputedStyle(document.documentElement)
                        .getPropertyValue('--color-primary'),
                    fill: false
                }]
            }
        });
    }

    function renderAccuracyTrendChart(data) {
        const ctx = document.getElementById('accuracy-trend-chart');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(p => p.date),
                datasets: [{
                    label: 'Accuracy %',
                    data: data.map(p => p.accuracy),
                    borderColor: getComputedStyle(document.documentElement)
                        .getPropertyValue('--color-success'),
                    fill: false
                }]
            }
        });
    }
</script>
{% endblock %}
```

### partials/stats_summary.html Structure

```html
<div class="stats-grid">
    <div class="stat-card">
        <span class="stat-value">{{ total_words }}</span>
        <span class="stat-label">Words Learned</span>
    </div>
    <div class="stat-card">
        <span class="stat-value">{{ total_sessions }}</span>
        <span class="stat-label">Sessions</span>
    </div>
    <div class="stat-card">
        <span class="stat-value">{{ lessons_completed }}</span>
        <span class="stat-label">Lessons</span>
    </div>
    <div class="stat-card">
        <span class="stat-value">{{ current_streak }} days</span>
        <span class="stat-label">Current Streak</span>
    </div>
    <div class="stat-card">
        <span class="stat-value">{{ accuracy_rate }}%</span>
        <span class="stat-label">Accuracy</span>
    </div>
    <div class="stat-card">
        <span class="stat-value">{{ words_learned_today }}</span>
        <span class="stat-label">Words Today</span>
    </div>
</div>
```

### partials/progress_vocab.html Structure

```html
<div class="vocabulary-list">
    {% if vocabulary %}
        {% for word in vocabulary %}
        <div class="vocab-item" id="vocab-{{ word.id }}">
            <span class="word">{{ word.word }}</span>
            <span class="translation">{{ word.translation }}</span>
            <span class="stats">
                Seen: {{ word.times_seen }} | Correct: {{ word.times_correct }}
            </span>
            <button hx-delete="/progress/vocabulary/{{ word.id }}"
                    hx-target="#vocab-{{ word.id }}"
                    hx-swap="outerHTML"
                    class="delete-btn">
                Remove
            </button>
        </div>
        {% endfor %}
    {% else %}
        <p class="empty-state">No vocabulary yet. Start chatting to learn words!</p>
    {% endif %}
</div>
```

---

## Key Design Decisions

### 1. Existing Repository Layer Reused

**Decision**: Aggregate data from existing repositories rather than create new database queries.

**Rationale**: The VocabularyRepository, LearningSessionRepository, and LessonProgressRepository already provide the necessary data access. Reusing them ensures consistency and reduces maintenance burden.

### 2. Sync Repositories in Async Routes

**Decision**: Use synchronous Supabase client calls within async FastAPI routes.

**Rationale**: The supabase-py client is synchronous. For indexed queries returning small result sets, the blocking time is minimal (<50ms). Running these in async routes is acceptable for our use case.

### 3. Chart.js via CDN

**Decision**: Load Chart.js v4.4.1 from jsDelivr CDN rather than bundling.

**Rationale**: No build step required. CDN provides caching benefits. Chart.js is loaded only on the progress page, not globally.

### 4. CSS Variables for Chart Colors

**Decision**: Read theme colors via `getComputedStyle()` at render time.

**Rationale**: Enables consistent theming. Charts automatically adapt if the user switches between light/dark modes or custom themes.

### 5. Fire-and-Forget Data Capture

**Decision**: `record_chat_activity()` catches all exceptions and logs rather than raising.

**Rationale**: User experience during chat should never be blocked by persistence failures. Data capture is valuable but not critical to the core interaction.

### 6. Auth-Gated Progress

**Decision**: Progress tracking requires authentication or a guest session cookie.

**Rationale**: Progress data is user-specific. Without identity, there's nothing to track. Guest users get a session_id cookie that enables temporary progress tracking.

---

## Testing Strategy

### Test Coverage Summary

Phase 7 adds **30-40 unit tests** for ProgressService with comprehensive coverage:

| Test File | Tests | Coverage Area |
|-----------|-------|---------------|
| `tests/test_progress_service.py` | ~30-40 | ProgressService aggregation, chart data, streaks |
| `tests/test_data_capture.py` | ~15-20 | Chat activity recording, vocabulary persistence |
| `tests/test_guest_progress.py` | ~15-20 | Guest user identity resolution, admin client usage |

### Unit Tests (test_progress_service.py)

**DashboardStats Tests**:
- Empty data returns zero values
- Single vocabulary entry counted correctly
- Multiple entries with different languages filtered properly
- Accuracy calculation: times_correct / times_seen
- Words learned today: filter by first_seen_at date
- Messages today: sum messages_count for today's sessions

**ChartData Tests**:
- Empty data returns empty arrays
- Single day returns one point
- 30-day range returns 30 points
- Cumulative words increases monotonically
- Accuracy reflects vocabulary up to each date

**Streak Calculation Tests**:
- No sessions returns streak = 0
- Session today only returns streak = 1
- Consecutive days counted correctly
- Gap in days resets streak
- Multiple sessions same day counted once

**Record Activity Tests**:
- New vocabulary upserted correctly
- Existing vocabulary increments times_seen
- Session created if none active
- Errors logged but not raised

### Integration Tests (test_data_capture.py)

**Chat Route Integration**:
- POST /chat/send persists vocabulary from graph result
- Vocabulary appears in /progress/vocabulary after chat
- Session created on first chat message
- Multiple messages don't create multiple sessions

### Guest Progress Tests (test_guest_progress.py)

**Identity Resolution**:
- Authenticated user uses user.id
- Guest with session_id uses session_id
- Guest without session_id returns empty state
- Admin client failure gracefully degraded

**End-to-End Guest Flow**:
- Guest chats, vocabulary persisted to session_id
- Guest visits /progress/, sees their words
- Guest deletes word, removed from list

### Test Fixtures

```python
@pytest.fixture
def mock_vocab_repo():
    """Create a mock VocabularyRepository."""
    with patch("src.services.progress.VocabularyRepository") as mock_class:
        yield mock_class.return_value


@pytest.fixture
def mock_session_repo():
    """Create a mock LearningSessionRepository."""
    with patch("src.services.progress.LearningSessionRepository") as mock_class:
        yield mock_class.return_value


@pytest.fixture
def mock_lesson_repo():
    """Create a mock LessonProgressRepository."""
    with patch("src.services.progress.LessonProgressRepository") as mock_class:
        yield mock_class.return_value


@pytest.fixture
def service(mock_vocab_repo, mock_session_repo, mock_lesson_repo):
    """Create a ProgressService with all repositories mocked."""
    return ProgressService("test-user-123")
```

### Test Helpers

```python
def _make_vocab(
    word: str,
    translation: str = "trans",
    language: str = "es",
    times_seen: int = 1,
    times_correct: int = 0,
    first_seen_at: datetime | None = None,
) -> Vocabulary:
    """Helper to build a Vocabulary instance for tests."""


def _make_session(
    started_at: datetime | None = None,
    messages_count: int = 0,
    words_learned: int = 0,
) -> LearningSession:
    """Helper to build a LearningSession instance for tests."""


def _make_lesson(lesson_id: str = "lesson-1", score: int | None = 80) -> LessonProgress:
    """Helper to build a LessonProgress instance for tests."""
```

---

## Implementation Files

### File Summary

| File | Action | Description |
|------|--------|-------------|
| `src/services/progress.py` | Create | ProgressService with aggregation logic |
| `src/api/routes/progress.py` | Create | FastAPI routes for progress endpoints |
| `src/templates/progress.html` | Create | Dashboard page with Chart.js |
| `src/templates/partials/stats_summary.html` | Create | Stats cards partial |
| `src/templates/partials/progress_vocab.html` | Create | Vocabulary list partial |
| `src/api/routes/chat.py` | Modify | Add data capture hook after graph execution |
| `tests/test_progress_service.py` | Create | Unit tests for ProgressService |
| `tests/test_data_capture.py` | Create | Integration tests for activity recording |
| `tests/test_guest_progress.py` | Create | Guest user progress tests |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Supabase query latency | Medium | Medium | Use indexed queries, accept sync client blocking |
| Data capture blocking chat | Low | High | Fire-and-forget pattern, error logging only |
| Chart.js CDN unavailable | Low | Low | Graceful degradation, charts optional |
| Guest session expiry | Medium | Low | Local storage backup (future), encourage signup |
| Accuracy calculation edge cases | Medium | Low | Handle division by zero, default to 0% |

---

## Future Considerations

### Phase 7.1: Enhanced Analytics

- Weekly/monthly summary emails
- Progress sharing (social features)
- Leaderboards (opt-in)
- Achievement badges

### Phase 7.2: Spaced Repetition

- Track word strength based on accuracy over time
- Surface weak vocabulary for review
- Integrate with micro-lessons for targeted practice

### Phase 7.3: Learning Insights

- Identify difficult grammar patterns
- Suggest focused practice areas
- Time-of-day learning effectiveness

---

## Success Criteria

### Functional

- [x] Users see real statistics on dashboard
- [x] Charts render vocabulary growth and accuracy
- [x] Vocabulary list shows learned words with delete
- [x] Chat activity persisted automatically
- [x] Guest users can track progress via session cookie

### Technical

- [x] ProgressService aggregates from repositories correctly
- [x] Chart data endpoint returns valid JSON for Chart.js
- [x] Data capture never blocks chat responses
- [x] All existing tests continue to pass
- [x] 30-40 new tests added with comprehensive coverage

### Performance

- [x] Dashboard loads in <300ms
- [x] Chart data returns in <200ms
- [x] Data capture adds <50ms to chat response

---

## Appendix: ProgressService API Reference

```python
class ProgressService:
    """Aggregates data from repositories into dashboard-ready structures."""

    def __init__(self, user_id: str, client: SupabaseClient | None = None) -> None
        """Initialize progress service for a user."""

    def get_dashboard_stats(self, language: str = "es") -> DashboardStats
        """Get aggregated dashboard statistics."""

    def get_chart_data(self, language: str = "es", days: int = 30) -> ChartData
        """Get chart data for the last N days."""

    def record_chat_activity(
        self,
        language: str,
        level: str,
        new_vocab: list[dict]
    ) -> None
        """Record vocabulary and session data after a chat interaction."""

    def _calculate_streak(self, sessions: list[LearningSession]) -> int
        """Calculate consecutive days with activity from today backwards."""
```
