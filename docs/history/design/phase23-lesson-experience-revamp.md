# Phase 23: Lesson Experience Revamp

**Date**: 2026-03-11
**Branch**: `feature/lesson-experience-revamp`
**Status**: Approved

## Problem

The lesson system is fragmented and error-prone:
- Two parallel lesson systems (old step-by-step player + Phase 19 conversational chat)
- Lessons are bolted onto chat via `data-lesson-mode` flag — feels disconnected
- No resume UX despite checkpoints existing
- Exercise answer matching is broken (exact string match causes correct answers to show as wrong)
- No hints, skips, or retries

## Goals

- Unified chat experience — lessons happen inside the same `/chat` page
- Purge the old step-by-step player entirely
- Light progress indicators (not heavy UI chrome)
- Fix exercise answer matching
- Clean developer experience — one route, one stream endpoint

## Design Decisions

- **Approach B**: Keep separate graphs (freeform + lesson), unify the route layer
- **Direction B**: Unified chat with seamless lesson integration
- **Indicators B**: Light progress cues — thin bar, no phase badges

## Section 1: Unified Route & Entry Points

### Current State
- `GET /chat` — freeform chat page
- `POST /chat/stream` — freeform stream endpoint
- `GET /chat/lesson/{id}` — lesson chat page
- `POST /chat/lesson/stream` — lesson stream endpoint
- `GET /lessons/{id}/play` — old step-by-step player

### New Design

| Route | Purpose |
|-------|---------|
| `/chat` | Single chat page — freeform by default |
| `/chat/stream` | Single stream endpoint — routes to correct graph internally |
| `/lessons` | Lesson list page (kept, "Play" button removed) |

Deleted routes: `/lessons/{id}/play`, `/chat/lesson/{id}`, `/chat/lesson/stream`

### How It Works
- User picks a lesson from `/lessons` → navigates to `/chat?lesson=es_a1_greetings_01`
- `/chat` GET handler checks for `lesson` query param. If present, loads lesson metadata and renders chat with lesson context.
- `/chat/stream` POST receives optional `lesson_id` in form data. If present + no active checkpoint, invokes `build_lesson_chat_graph()`. If absent, invokes `build_graph()`.
- Exiting a lesson (completion or user choice) returns to plain `/chat` state — no page reload, HTMX swap of header area.

## Section 2: Chat UI in Lesson Mode

### Header Behavior
- **Freeform mode**: Shows language picker + level selector (as today)
- **Lesson mode**: Header area swaps to show lesson title, thin progress bar, and "Exit lesson" link. No phase badge. Transition via HTMX swap — no page reload.

### Progress Bar
- Thin bar (2-3px) at top of chat area
- Combined teaching steps + exercises as one linear scale
- Example: 5 teaching steps + 3 exercises = 8 units. After step 3, bar = 37.5%.
- Subtle theme accent color. No percentage text.

### Input Area
- Same textarea + send + mic in both modes
- During multiple-choice exercises: render clickable option buttons above textarea (user can still type). Options disappear after answering.

### Lesson Start
- Auto-sends "Start the lesson" on load when `?lesson=` present
- Auto-sent message is hidden from chat — first visible message is AI's intro

### Lesson Completion
- AI's final message includes score conversationally ("You got 5/6 — nice work!")
- Compact completion card below with score, vocab count, "Next Lesson" / "Free Chat" buttons
- No giant celebration banner

### Removed
- Phase badge UI element
- `visibility: hidden` hack for selectors
- `showLessonComplete()` celebration banner

## Section 3: Backend — Graph Routing & Exercise Fixes

### Graph Routing (unified `/chat/stream`)

```
POST /chat/stream
  ├─ Has lesson_id in form data?
  │   ├─ Yes → load lesson, check checkpoint
  │   │   ├─ No checkpoint → init LessonChatState, invoke lesson graph
  │   │   └─ Has checkpoint → resume lesson graph (no re-init)
  │   └─ No → invoke freeform graph (as today)
  └─ SSE event protocol stays identical
```

Lesson graph, state, nodes, and prompts stay as-is.

### Exercise Answer Matching Fix

Current: exact case-insensitive string match → correct answers marked wrong.

New approach:
- **Multiple choice**: Keep exact match (A/B/C/D) — works fine
- **Fill-in-the-blank**: Normalize whitespace + strip punctuation + case-insensitive. Accept list of valid answers from YAML (`answers: ["estoy bien", "estoy muy bien"]`)
- **Translation**: LLM evaluates correctness. Parse structured signal from LLM response (`[CORRECT]` / `[INCORRECT]` tag). Eliminates "LLM says correct but badge says wrong" disconnect.

### Resume Support
- If user navigates to `/chat?lesson=X` and checkpoint exists, load previous messages and show system message: "Resuming your lesson — pick up where you left off."
- No re-initialization of lesson state.

### Unchanged
- Lesson graph topology (respond → scaffold → analyze)
- Phase machine (intro → teaching → exercise_ask → exercise_eval → complete)
- CEFR teaching adjustments
- Lesson completion persistence & SM-2 vocabulary init

## Section 4: Cleanup & Deletions

### Files Deleted
| File | Reason |
|------|--------|
| `src/api/routes/lesson_chat.py` | Logic merges into `chat.py` |
| `src/templates/lesson_player.html` | Old step-by-step player |
| `src/templates/lesson_step.html` | Old step partial |
| `src/templates/lesson_exercise.html` | Old exercise partial |

### Routes Removed
| Route | File |
|-------|------|
| `GET /lessons/{id}/play` | `src/api/routes/lessons.py` |
| `GET /chat/lesson/{id}` | deleted with `lesson_chat.py` |
| `POST /chat/lesson/stream` | deleted with `lesson_chat.py` |

### JS Cleanup (`stream.js`)
- Remove `showLessonComplete()` celebration banner → compact completion card
- Remove `PHASE_LABELS` and phase badge updates
- Simplify `isLessonMode()` — check `?lesson=` param instead of `data-lesson-mode`

### Template Cleanup (`chat.html`)
- Remove `data-lesson-mode` / `data-lesson-id` attributes
- Remove `visibility: hidden` hack for selectors
- Replace hardcoded lesson header with swappable HTMX region

### Tests
- `tests/api/routes/test_lesson_chat.py` — rewrite to target unified `/chat/stream`
- Old player route tests — delete
- Exercise `check_answer()` tests — update for new matching logic

### Lessons Page (`/lessons`)
- Remove "Play" button
- "Learn with Hermano" links to `/chat?lesson={id}`
