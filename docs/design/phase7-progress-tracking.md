# Phase 7: Progress Tracking

## Overview

Progress dashboard with real Supabase persistence and Chart.js visualizations for the Habla Hermano language learning app.

## Architecture

### New Components

- **ProgressService** (`src/services/progress.py`): Aggregates data from existing repositories (VocabularyRepository, LearningSessionRepository, LessonProgressRepository) into dashboard-ready structures.
- **Dashboard Templates**: `progress.html` with Chart.js, `stats_summary.html` and `progress_vocab.html` partials.
- **Data Capture Hooks**: Chat and lesson routes persist learning data for authenticated users.

### Data Flow

1. User chats with Hermano -> `chat.py` extracts `new_vocabulary` from graph result -> `ProgressService.record_chat_activity()` upserts vocab and creates/updates learning session
2. User completes lesson -> `lessons.py` calls `LessonProgressRepository.complete_lesson()`
3. User visits `/progress/` -> `ProgressService.get_dashboard_stats()` aggregates data -> Template renders with Chart.js via `/progress/chart-data` JSON endpoint

### Key Decisions

1. **Existing repository layer reused** -- No new DB client code needed
2. **Sync repos in async routes** -- supabase-py is synchronous, acceptable for indexed queries
3. **Chart.js via CDN** -- No build step needed (v4.4.1)
4. **CSS variables for chart colors** -- getComputedStyle() reads theme vars at render time
5. **Fire-and-forget data capture** -- Errors logged but don't fail chat responses
6. **Auth-gated progress** -- Guest users don't get progress tracking

### Endpoints

| Method | Path | Response | Description |
|--------|------|----------|-------------|
| GET | /progress/ | HTML | Dashboard page |
| GET | /progress/stats | HTML partial | Stats cards |
| GET | /progress/vocabulary | HTML partial | Vocabulary list |
| GET | /progress/chart-data | JSON | Chart.js data |
| DELETE | /progress/vocabulary/{id} | Empty HTML | Remove word |

### Models

- **DashboardStats**: total_words, total_sessions, lessons_completed, current_streak, accuracy_rate, words_learned_today, messages_today
- **ChartData**: vocab_growth (VocabGrowthPoint[]), accuracy_trend (AccuracyPoint[])

## Testing Strategy

- ~30-40 unit tests for ProgressService with mocked repositories
- ~15-20 integration tests for data capture in chat/lesson routes
- All existing 918+ tests continue to pass
