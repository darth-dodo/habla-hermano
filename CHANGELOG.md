# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0] - 2026-02-04

### Added
- Phase 12: Spaced repetition system with SM-2 algorithm
- ReviewService with SM-2 scheduling (easiness factor, intervals, repetition count)
- Intelligent chat weaving: due review words naturally woven into Hermano's conversations
- Dedicated review mode with conversational micro-quizzes (not flashcards)
- Review session API: /review/start, /review/next, /review/submit, /review/stats
- Review state tracking in LangGraph with review_words_offered and review_words_used
- Topical word matching: reviews words that fit current conversation context
- Quality score inference from answer correctness (no manual rating buttons)
- Silent review tracking: SM-2 updates when users naturally use review words in chat
- Review stats on progress page with due count and next review time
- Chat warmup prompt when words are due for review
- Session size options: Quick (5), Regular (10), All due words
- Design doc: docs/design/phase12-spaced-repetition.md

### Changed
- Vocabulary model extended with SM-2 fields: easiness_factor, interval_days, repetition_count, next_review_at, last_reviewed_at
- VocabularyRepository extended with get_due_for_review, get_due_by_keywords, update_review_schedule, get_review_stats
- Chat route now passes user_id to graph for review word weaving
- Respond node fetches topical review words and adds them to system prompt
- Analyze node tracks review word usage and updates SM-2 silently

## [0.8.0] - 2026-02-02

### Added
- Phase 11: Nordic Minimal design system with clean, modern aesthetic
- Pronunciation tips integrated into all CEFR level prompts (A0-B1)
- Language-specific pronunciation data: tricky_sounds, stress_rule, sound_tip
- PRONUNCIATION TIPS sections in prompts for natural pronunciation coaching
- Design doc: docs/design/phase11-nordic-design-pronunciation.md

### Changed
- Complete UI redesign with Nordic Minimal theme (cool grays, ice blue accents)
- Typography updated to Inter font family for cleaner readability
- Three theme variants: Light (Nordic Day), Dark (Nordic Night), Ocean
- Simplified chat header with icon-based branding
- Compact lesson cards with badge-style level indicators
- Minimal lesson player with thin progress bar

## [0.7.0] - 2026-02-01

### Added
- Phase 10: Lesson content expansion from 5 to 60 lessons
- German lessons: 20 lessons (A0-B1) with noun genders, umlauts, formal/informal distinction
- French lessons: 20 lessons (A0-B1) with accents, liaison rules, formal/informal distinction
- Spanish A1-B1 lessons: 15 new lessons building on existing A0 content
- Composite key system for LessonService (`lang/level/id` format)
- Level-appropriate exercise types: A0 (MC only) → B1 (MC + fill + translate)

### Changed
- LessonService now uses composite keys for unique lesson identification
- get_lesson() supports scoped lookups by language and level

## [0.6.0] - 2025-01-28

### Added
- Phase 8: Guest session support for unauthenticated users
- Session-based guest tracking via session_id cookie (httponly, 7-day expiry)
- Guest data stored in same Supabase tables using admin client to bypass RLS
- GuestDataMergeService for merging guest vocabulary and progress data on signup/login
- _resolve_identity() helper for unified auth/guest handling across routes
- Fire-and-forget pattern for data capture (failures don't block responses)

### Changed
- Chat and lesson routes now capture data for both authenticated users and guests
- Schema migration to drop FK constraints for guest UUIDs
- Progress tracking works identically for guests and authenticated users

## [0.5.0] - 2025-01-25

### Added
- Phase 7: Progress tracking dashboard with vocabulary and session analytics
- ProgressService for dashboard stats computation and chart data generation
- VocabularyRepository for storing and retrieving learned vocabulary items
- LearningSessionRepository for tracking learning session metadata
- LessonProgressRepository for micro-lesson completion tracking
- Progress dashboard page with vocabulary list, stats summary, and interactive charts
- Chart.js integration for visualizing learning progress over time
- Vocabulary and session data capture in chat and lesson routes
- HTMX partials: progress_vocab.html and stats_summary.html for dynamic updates

### Changed
- Navigation updated to include progress dashboard link
- User profile extended with progress statistics

## [0.4.0] - 2025-01-18

### Added
- Hermano personality: friendly big brother language tutor with consistent voice across all levels
- LANGUAGE_ADAPTER dictionary pattern for clean language switching in prompts
- Extensible language support structure (Spanish, German, French)

### Changed
- Project renamed from habla-ai to habla-hermano
- Renamed 38 files to reflect new branding
- System prompts rewritten with Hermano personality characteristics
- Language adaptation now uses dictionary-based format strings instead of string replacement
- All documentation updated to reflect Hermano personality

### Personality by Level
- A0: Supportive big brother for absolute beginners, heavy encouragement
- A1: Chill friend who spent a year abroad, relaxed guidance
- A2: Challenges learners while keeping it fun and conversational
- B1: Peer-to-peer natural conversation partner

## [0.3.0] - 2025-01-18

### Added
- Phase 3: Scaffold node with conditional routing
- Word bank generation for A0-A1 learners with contextual vocabulary
- Hint text to guide learner responses
- Sentence starters to help beginners formulate responses
- Click-to-insert functionality for word bank items
- Conditional graph routing: A0-A1 learners routed to scaffold node, A2-B1 skip to end
- Auto-expand scaffold for A0 level, collapsed for A1
- ScaffoldingConfig Pydantic model for type-safe scaffold data
- Comprehensive test coverage for scaffold node (16 tests)
- Routing logic tests (10 tests)
- E2E test documentation for scaffold scenarios

### Changed
- LangGraph now uses conditional edges for level-based routing
- Updated message_pair.html template to include scaffold partial
- Added Alpine.js interactions for collapsible scaffold UI

## [0.2.0] - 2025-01-15

### Added
- Phase 2: LangGraph analyze node with grammar feedback
- Grammar correction detection and gentle feedback generation
- Collapsible grammar feedback UI with expand/collapse animations
- Grammar tips displayed inline with conversation flow
- GrammarFeedback Pydantic model for structured feedback data
- Comprehensive test coverage for analyze node
- Desktop and mobile screenshot documentation

### Changed
- LangGraph StateGraph extended with analyze node after respond node
- Message pair template updated to include grammar feedback section
- UI styling enhanced for grammar tip visibility

## [0.1.0] - 2025-01-13

### Added
- Phase 1: LangGraph chat with HTMX UI
- Basic conversation flow with respond node
- HTMX-powered real-time chat interface
- Jinja2 templates with Tailwind CSS styling
- Three theme options: Dark, Light, Ocean
- Four proficiency levels: A0, A1, A2, B1
- Two target languages: Spanish and German
- FastAPI backend with WebSocket-style HTMX updates
- Session-based conversation state management
- Mobile-responsive design
- Initial test suite with pytest

### Changed
- Project structure established with src/ directory layout
- Development tooling configured (Ruff, MyPy, pre-commit)

## [0.0.1] - 2025-01-12

### Added
- Initial project setup
- Repository structure and configuration
- Development environment setup with uv
- Basic FastAPI application skeleton
- Makefile for common development commands
- GitHub Actions workflow for CI
- Pre-commit hooks configuration
