# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
