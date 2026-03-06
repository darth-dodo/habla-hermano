# Phase 19: Conversational Lesson Delivery (Bridge 4)

> Hermano teaches lessons conversationally in the chat UI — YAML content becomes his teaching plan, exercises happen inline, and progress still persists for SM-2, learning paths, and the dashboard

---

## Overview

Habla Hermano currently has two disconnected learning experiences:

1. **Static lesson player** (`/lessons/{id}`): A step-by-step YAML-driven player with instruction cards, vocabulary lists, example sentences, tips, and exercises. Progress persists to Supabase. Works well but feels like a textbook — no personality, no adaptation, no conversation.

2. **Hermano chat** (`/chat`): A conversational AI tutor powered by LangGraph (respond → scaffold → analyze). Has the Hermano personality, level-appropriate language mixing, grammar feedback, pronunciation tips, and spaced repetition chat weaving. Engaging but unstructured — no curriculum, no exercises, no measurable progress.

The "Practice with Hermano" handoff button on the lesson completion screen redirects to `/chat?lesson={id}&topic={category}`, but the chat route doesn't read those params. It's a dead link — the two systems don't talk to each other.

**Phase 19 bridges this gap.** Hermano teaches lessons conversationally in the chat UI. The YAML lesson content becomes his teaching plan. Exercises happen inline as natural conversation. Progress persists identically to the static player — SM-2 vocabulary scheduling, learning path advancement, and dashboard stats all update.

The static lesson player remains available as an alternative. Users can choose their preferred learning style.

**Business Value**: Conversational lesson delivery combines the structure of curriculum (measurable progress, exercises, vocabulary tracking) with the engagement of conversation (Hermano's personality, adaptive responses, natural language interaction). This is the core differentiator — most language apps have either structured lessons OR conversation, not both unified.

---

## Design Decisions

### Separate LangGraph Graph, Same Topology

The lesson chat uses a **new graph** (`build_lesson_chat_graph`) rather than adding lesson awareness to the existing chat graph.

**Rationale**:
- **Separation of concerns**: The main chat graph handles free-form conversation. Adding lesson phase tracking, exercise validation, and step batching to `respond_node` would bloat a 239-line function into a 500+ line monster with mode branching everywhere.
- **Independent evolution**: Lesson chat can evolve its node structure (e.g., adding a dedicated exercise validation node) without risking regressions in regular chat.
- **Thread isolation**: Lesson conversations use separate thread IDs (`lesson:{user_id}:{lesson_id}`), preventing lesson context from polluting regular chat history and enabling lesson resumption via checkpoints.
- **Streaming compatibility**: By registering the lesson node as `"respond"` (same name as the main chat's respond node), the existing `stream_chat_events()` function handles token streaming without modification. The SSE infrastructure doesn't care which graph produced the tokens.

**Trade-off**: Some code duplication in graph construction (`StateGraph` → `add_node` → `add_conditional_edges` → `compile`). This is ~15 lines of boilerplate, acceptable for the isolation benefits.

**Rejected: Conditional mode in existing graph**: Adding an `if state.get("lesson_id"):` branch to `respond_node` was considered. This would avoid a new graph but couples two distinct behaviors. When the lesson chat needs changes (e.g., different scaffolding for exercise phases), it would require touching the main chat code path with no benefit.

**Rejected: Subgraph of existing graph**: Making lesson chat a subgraph invoked from the main respond node was considered. This creates a parent-child coupling where the main graph must be aware of lesson states and routing. The graphs are peers, not parent-child.

### Reuse Existing Nodes Unchanged

The lesson chat graph reuses `scaffold_node` and `analyze_node` directly — no modifications, no wrappers.

**Rationale**:
- **scaffold_node** generates word banks for A0-A1 learners based on the assistant's latest message. It reads from `state["messages"]` and writes to `state["scaffolding"]`. This works identically whether Hermano is teaching a lesson or having free conversation — the scaffolding is about the student's level, not the content source.
- **analyze_node** extracts grammar feedback, new vocabulary, and pronunciation tips from the conversation. Again, it reads messages and writes analysis fields. The lesson context doesn't change how analysis works.
- **`needs_scaffolding`** routing function checks `state["level"]` against A0/A1. Level is set identically in lesson chat state.

**Trade-off**: Lesson exercises produce short, formulaic student responses ("B", "mercado", "Hola, me llamo Ana"). The analyze node may not find much grammar to analyze in these. This is acceptable — analysis is more valuable during the teaching phases where Hermano writes rich responses and the student asks questions.

### Phase Machine Inside a Single Node

The `lesson_respond_node` uses an internal phase machine rather than multiple LangGraph nodes.

**Phases**: `intro` → `teaching` → `exercise_ask` → `exercise_eval` → `complete`

**Rationale**:
- **Atomic state transitions**: Each phase transition (e.g., teaching → exercise_ask) must update multiple state fields simultaneously (step_index, exercise_index, lesson_phase, lesson_ui). A single node function can do this atomically. Multiple nodes would require passing intermediate state and coordinating transitions.
- **LLM call consolidation**: Most phases make exactly one LLM call to generate Hermano's response. Splitting into separate LangGraph nodes (one per phase) would add routing overhead without reducing complexity — the routing logic IS the complexity.
- **Deterministic + LLM hybrid**: Exercise evaluation is deterministic first (call `check_answer()`), then generates LLM feedback. This mixed logic fits naturally in a single function with clear sections, not in separate nodes that would need to coordinate.
- **Simpler debugging**: One node function means one place to add logging, one place to set breakpoints, one call stack to trace.

**Trade-off**: The `lesson_respond_node` function will be ~300 lines, larger than the ~100-line `respond_node`. This is managed by extracting helper functions for each phase (`_handle_intro`, `_handle_teaching`, `_handle_exercise_ask`, `_handle_exercise_eval`, `_handle_complete`).

### Step Batching (2-3 per Turn)

Consecutive non-practice steps (instruction, vocabulary, example, tip) are grouped into batches of 2-3 and delivered in a single Hermano turn.

**Rationale**:
- **Pacing**: A typical lesson has 5-7 steps. Delivering one step per turn means 5-7 back-and-forth exchanges before exercises — too slow for chat, where users expect conversational flow.
- **Natural teaching style**: A real tutor doesn't pause after every sentence waiting for a response. They explain a concept, show an example, and then check understanding. Batching mimics this pattern.
- **Reduced LLM calls**: Fewer turns means fewer LLM invocations, reducing latency and cost.

**Batch boundary rules**:
1. A batch contains at most 3 steps (prevents overwhelming the student).
2. A `practice` step type always starts a new phase (exercise_ask), breaking the batch.
3. The final batch before exercises can be smaller (e.g., 1-2 steps if that's what remains).

**Example for a 7-step lesson**:
```
Turn 1 (intro):     Hermano introduces the lesson
Turn 2 (teaching):  Steps 0-2 (instruction + vocabulary + example)
Turn 3 (teaching):  Steps 3-4 (tip + example)
Turn 4 (exercise):  Exercise 0 asked
Turn 5 (exercise):  Exercise 0 evaluated, Exercise 1 asked
...
Turn N (complete):  Score, vocab count, next lesson
```

### Hybrid Exercise Validation

Exercises are validated deterministically first, then Hermano generates personalized feedback via LLM.

**Rationale**:
- **Correctness guarantee**: The existing `check_answer()` methods in `src/lessons/models.py` provide deterministic, tested validation. `MultipleChoiceExercise.check_answer()` compares against the correct option index. `FillBlankExercise.check_answer()` and `TranslateExercise.check_answer()` use normalized string comparison. These never produce false positives or false negatives.
- **Personality layer**: A deterministic "Correct!" or "Incorrect" is functional but bland. Hermano's personality is the product's differentiator. The LLM generates feedback like "Nice one! 'Mercado' is right — you'd hear that word every day if you were shopping in Mexico City" using the existing `get_exercise_feedback_prompt()`.
- **Separation of truth from presentation**: The `is_correct` boolean (deterministic) drives scoring, progress, and SM-2 updates. The feedback text (LLM-generated) is purely for UX. If the LLM is slow or fails, the score is still correct.

**Answer parsing for multiple choice** (in chat, users type answers instead of clicking buttons):
1. Single letter A-D → mapped to option index (case-insensitive)
2. Single digit 1-4 → mapped to option index
3. Full text match against option strings (fuzzy, normalized)
4. If ambiguous → Hermano asks for clarification ("Hmm, I wasn't sure which one you meant — try typing the letter (A, B, C, or D)")

### Thread Isolation with Lesson-Specific IDs

Thread ID format: `lesson:{user_or_session_id}:{lesson_id}`

**Rationale**:
- **Resumability**: If a user closes the browser mid-lesson and returns, the LangGraph checkpointer loads the previous state. The lesson resumes from where they left off (correct phase, step index, exercise index, partial results).
- **No cross-contamination**: Regular chat threads (`user:{id}` or session UUID) stay clean. A student won't see lesson exercise prompts in their free conversation history.
- **Idempotent restarts**: Starting the same lesson again uses the same thread ID, so the checkpoint is overwritten. No accumulation of stale lesson threads.

### Coexistence with Static Player

Both learning modes remain available. The lesson catalog shows two options per lesson: the existing "Start Lesson" (static player) and a new "Learn with Hermano" (conversational chat).

**Rationale**:
- **User preference**: Some learners prefer structured, self-paced progression (click through steps, read carefully). Others prefer conversational engagement. Both are valid learning styles.
- **Incremental rollout**: The static player is stable and tested. Conversational delivery is new. If bugs arise in the chat mode, the static player is always available as a fallback.
- **A/B comparison**: Having both modes enables future analysis of which approach leads to better retention (via SM-2 review performance).

---

## Architecture

### Graph Design

A new `build_lesson_chat_graph(checkpointer)` with identical topology to the main chat graph:

```
START → lesson_respond (registered as "respond") → [needs_scaffolding?]
                                                     ├─ A0/A1 → scaffold → analyze → END
                                                     └─ A2/B1 → analyze → END
```

Reuses existing `scaffold_node` and `analyze_node` unchanged. The node is registered as `"respond"` so `stream_chat_events()` handles token streaming without modification.

### State: LessonChatState

Extends ConversationState fields with lesson tracking:

```python
class LessonChatState(TypedDict):
    # === Same as ConversationState ===
    messages: Annotated[list[BaseMessage], add_messages]
    level: str
    language: str
    user_id: str
    supabase_client: Any
    grammar_feedback: list[GrammarFeedback]
    new_vocabulary: list[VocabWord]
    scaffolding: ScaffoldingConfig | None
    pronunciation_tips: list[PronunciationTip]
    review_words_offered: list[ReviewWordOffered]
    review_words_used: list[ReviewWordUsed]

    # === Lesson tracking ===
    lesson_id: str
    lesson_data: dict[str, Any]          # Lesson.model_dump() serialized YAML
    lesson_phase: str                     # "intro"|"teaching"|"exercise_ask"|"exercise_eval"|"complete"
    step_index: int                       # Current position in steps (0-based)
    exercise_index: int                   # Current position in exercises (0-based)
    exercise_results: list[dict]          # [{exercise_id, is_correct, user_answer}]
    lesson_score: int                     # Running score 0-100
    lesson_ui: NotRequired[dict]          # For SSE: progress bar, exercise feedback, completion
    lesson_completed: NotRequired[bool]   # Flag for post-stream persistence
```

### Phase Machine

```
intro → teaching (batch steps 0-2) → teaching (batch steps 3-4) → ...
    → exercise_ask (ex 0) → exercise_eval (ex 0)
    → exercise_ask (ex 1) → exercise_eval (ex 1) → ...
    → complete
```

**Phase transitions**:

| Current Phase | Trigger | Next Phase |
|---------------|---------|------------|
| `intro` | Any user message (or `/start`) | `teaching` |
| `teaching` | User responds, more steps remain | `teaching` (next batch) |
| `teaching` | User responds, all steps delivered | `exercise_ask` |
| `exercise_ask` | User submits answer | `exercise_eval` |
| `exercise_eval` | More exercises remain | `exercise_ask` (next exercise) |
| `exercise_eval` | All exercises done | `complete` |
| `complete` | (terminal) | — |

### Entry Points

1. **Lesson catalog**: "Learn with Hermano" button on each lesson card → `GET /chat/lesson/{lesson_id}`
2. **Post-completion**: Fixed handoff button → redirects to `/chat/lesson/{lesson_id}`
3. **Direct URL**: `GET /chat/lesson/{lesson_id}` (bookmarkable)

### Auto-Start

On page load, the JS client auto-sends a `/start` message after 500ms delay to trigger Hermano's introduction. The `lesson_respond_node` recognizes `/start` (or any first message when phase is `intro`) and generates the lesson introduction — a warm, Hermano-style preview of what the lesson covers.

### Exit

- **Mid-lesson**: "Exit Lesson" pill button in lesson header → redirects to `/lessons/`
- **Completion**: In-chat panel with score, vocabulary count, and navigation buttons (next lesson, back to lessons catalog)

### CEFR Teaching Adjustments

All prompt templates include a `{teaching_adjustments}` placeholder, and each phase handler passes `teaching_adjustments=get_teaching_adjustments(level)` to its format call. This ensures Hermano's pedagogy adapts to the learner's CEFR level.

`TEACHING_ADJUSTMENTS` is a `dict[str, str]` in `src/agent/prompts_lesson_chat.py` with 4 entries:

| Level | Key Pedagogical Instructions |
|-------|------------------------------|
| **A0** (Absolute Beginner) | ONE concept at a time; repeat key words 2-3 times; English for ALL explanations; yes/no or single-word questions only |
| **A1** (Beginner) | Group 2-3 related concepts; grammar through pattern recognition; 50/50 language mix; model correct form naturally |
| **A2** (Elementary) | Present in context (mini-dialogues); insider expressions; let small errors slide; 80% target language |
| **B1** (Intermediate) | Discuss nuance and regional variations; correct as a peer; 95%+ target language; ask for opinions and hypotheticals |

`get_teaching_adjustments(level)` returns the matching entry, falling back to A1 for unknown levels.

**Rationale**: A single system prompt cannot serve all levels well. An A0 learner needs slow, isolated vocabulary delivery with heavy English scaffolding. A B1 learner needs to be pushed toward full target-language production. Without explicit per-level instructions, the LLM tends to default to a generic intermediate style that overwhelms beginners and bores advanced students.

---

## Post-Implementation Bug Fixes

### Progress Bar Bug (stale checkpoint progress)

**Root cause**: `_build_lesson_ui()` originally read `step_index` from the input state (pre-advance), so the checkpoint always stored the step index *before* the handler advanced it. Additionally, each handler was passing the current phase to `_build_lesson_ui()` instead of the next phase.

**Fix**: `_build_lesson_ui()` now accepts a `step` override via `**extra` kwargs. Progress is computed comprehensively as `(completed_teaching_steps + completed_exercises) / (total_teaching_steps + total_exercises) * 100`, giving a smooth 0-100% bar that accounts for both teaching and exercise progress. Each handler passes the **post-advance** step index and the **next** phase to `_build_lesson_ui()`.

### Checkpoint Overwrite Bug (state reset on every request)

**Root cause**: The stream endpoint sent `lesson_phase: "intro"`, `step_index: 0`, etc. as input on every request. Because LangGraph merges inputs into state before invoking the node, this overwrote the checkpoint's tracked progression, resetting the lesson to the beginning every turn.

**Fix**: The route now checks for an existing checkpoint via `graph.aget_state()`. On the first invocation (no checkpoint), the full initialization payload is sent (lesson data, phase, indices, etc.). On subsequent turns, only the new message, `user_id`, and `supabase_client` are sent -- the checkpoint preserves all lesson progression state.

### Header Layout Centering Bug

**Root cause**: The language/level selectors in lesson mode were hidden with `display: none`, which removed them from the flex layout and caused the header content to shift off-center.

**Fix**: Changed to `visibility: hidden` so the elements remain in the flex layout flow (preserving centering) while being invisible. The selectors are derived from lesson metadata in lesson mode, so user interaction with them is not needed.

---

## SSE Event Flow

### Standard Events (unchanged)

```
token         → {"content": "H"}
token         → {"content": "ola"}
...
response_complete → {"content": "full response text"}
scaffolding   → {"html": "..."}     (A0-A1 only)
grammar       → {"html": "..."}
pronunciation → {"html": "..."}
```

### New Lesson Events (emitted after response_complete)

```
lesson_progress → {"step": 2, "total_steps": 7, "phase": "teaching", "progress": 28, "title": "Basic Greetings"}
exercise_result → {"is_correct": true, "exercise_id": "ex-mc-001"}       (exercise_eval only)
lesson_complete → {"score": 85, "vocab_count": 6, "lesson_id": "..."}    (complete only)
done            → {}
```

**Progress calculation**: `progress` is a server-computed 0-100 integer: `(completed_teaching_steps + completed_exercises) / (total_teaching_steps + total_exercises) * 100`. The client uses `data.progress` directly for the progress bar width, rather than computing `step/total_steps` locally.

**Backward compatible**: Regular chat never produces these events. The client's `switch`/`default` ignores unknown event types.

---

## Key Reuse Points

| Existing Code | Location | Reused For |
|---------------|----------|-----------|
| `scaffold_node` | `src/agent/nodes/scaffold.py` | Word banks for A0-A1 during lesson chat |
| `analyze_node` | `src/agent/nodes/analyze.py` | Grammar/vocab/pronunciation feedback on student responses |
| `needs_scaffolding` | `src/agent/routing.py` | Same conditional routing in lesson graph |
| `stream_chat_events` | `src/api/streaming.py` | Token streaming (node registered as "respond") |
| `check_answer()` methods | `src/lessons/models.py` | Deterministic exercise validation |
| `get_exercise_feedback_prompt` | `src/agent/prompts.py` | LLM feedback after exercise answers |
| `complete_lesson_and_persist` | `src/services/lesson_completion.py` | Post-stream lesson completion persistence |
| `LessonService.get_lesson()` | `src/lessons/service.py` | Load YAML lesson data |
| `get_checkpointer()` | `src/api/routes/chat.py` | Checkpoint lesson conversations |

---

## Files to Create

| # | File | ~Lines | Purpose |
|---|------|--------|---------|
| 1 | `src/agent/lesson_chat_state.py` | 70 | LessonChatState TypedDict, phase constants |
| 2 | `src/agent/prompts_lesson_chat.py` | 370 | System prompts for intro, teaching, exercise_ask, exercise_eval, complete + `TEACHING_ADJUSTMENTS` dict (4 CEFR levels) + `get_teaching_adjustments()` helper + step/exercise formatting helpers |
| 3 | `src/agent/nodes/lesson_chat.py` | 520 | `lesson_respond_node` with phase machine, exercise parsing, prompt building, `_build_lesson_ui()` with comprehensive progress calculation and `step` override |
| 4 | `src/agent/lesson_chat_graph.py` | 50 | `build_lesson_chat_graph(checkpointer)` |
| 5 | `src/api/routes/lesson_chat.py` | 300 | `GET /chat/lesson/{id}` page route, `POST /chat/lesson/stream` SSE endpoint (checkpoint-aware: first invocation sends full init state, subsequent turns send only new message) |
| 6 | `src/templates/partials/lesson_chat_header.html` | 40 | Progress bar, step counter, lesson title, exit button |
| 7 | `src/templates/partials/lesson_chat_complete.html` | 50 | In-chat completion panel (score, vocab, next lesson, back to catalog) |
| 8 | `tests/agent/nodes/test_lesson_chat.py` | 1000+ | 75 unit tests: all phases, exercise parsing, edge cases, 15 TEACHING_ADJUSTMENTS tests, 4 handler injection tests |

**Total new code**: ~2,000+ lines across 8 files

## Files to Modify

| # | File | Change | ~Lines |
|---|------|--------|--------|
| 1 | `src/api/main.py` | Register `lesson_chat.router` | 3 |
| 2 | `src/api/routes/lessons.py` | Fix `handoff_to_chat` → redirect to `/chat/lesson/{id}` | 3 |
| 3 | `src/api/streaming.py` | Emit `lesson_progress`, `exercise_result`, `lesson_complete` SSE events | 25 |
| 4 | `src/templates/chat.html` | Lesson mode conditional: lesson header partial, hidden input, `data-lesson-mode`, `visibility: hidden` for language/level selectors (preserves flex centering) | 30 |
| 5 | `src/static/js/modules/stream.js` | Handle 3 new SSE events, detect lesson mode, auto-start, switch stream URL, `updateLessonProgress()` uses server-computed `data.progress` | 45 |
| 6 | `src/templates/lessons.html` | Add "Learn with Hermano" button on lesson cards | 10 |
| 7 | `src/templates/partials/lesson_complete.html` | Update handoff button href | 3 |

**Total modified**: ~119 lines across 7 files

---

## Implementation Order

### Phase A: Backend Core (no existing code changes)

1. Create `src/agent/lesson_chat_state.py` — LessonChatState TypedDict, phase constants
2. Create `src/agent/prompts_lesson_chat.py` — system prompts per phase and step type
3. Create `src/agent/nodes/lesson_chat.py` — lesson_respond_node with phase machine
4. Create `src/agent/lesson_chat_graph.py` — build_lesson_chat_graph(checkpointer)
5. Create `tests/agent/nodes/test_lesson_chat.py` — unit tests for all phases

### Phase B: API Layer (new routes + small modifications)

6. Create `src/api/routes/lesson_chat.py` — page + stream endpoints
7. Modify `src/api/main.py` — register router
8. Modify `src/api/streaming.py` — emit lesson SSE events
9. Modify `src/api/routes/lessons.py` — fix handoff redirect
10. Create `tests/api/routes/test_lesson_chat.py` — API tests

### Phase C: Frontend (UI additions)

11. Create `src/templates/partials/lesson_chat_header.html`
12. Create `src/templates/partials/lesson_chat_complete.html`
13. Modify `src/templates/chat.html` — lesson mode conditional
14. Modify `src/static/js/modules/stream.js` — lesson events + auto-start
15. Modify `src/templates/lessons.html` — "Learn with Hermano" button
16. Modify `src/templates/partials/lesson_complete.html` — fix handoff URL

---

## Verification

1. **Unit tests**: `uv run python -m pytest tests/agent/nodes/test_lesson_chat.py -v` (75 tests)
   - All 5 phases produce correct state transitions
   - Exercise parsing handles letter, number, text, and ambiguous input
   - Step batching groups correctly (2-3 per batch, practice breaks batch)
   - Score calculation accurate (correct / total * 100)
   - 15 tests for `TEACHING_ADJUSTMENTS` (4 levels present, unique content, key phrases per level, fallback behavior)
   - 4 tests verifying each handler (intro, teaching, exercise_ask, exercise_eval) injects level-specific content into the system prompt

2. **API tests**: `uv run python -m pytest tests/api/routes/test_lesson_chat.py -v`
   - `GET /chat/lesson/{id}` renders lesson mode chat page
   - `POST /chat/lesson/stream` produces SSE events in correct order
   - Invalid `lesson_id` returns 404
   - Auth and guest session flows work

3. **Existing tests unbroken**: `uv run python -m pytest -q --tb=line` (all 2157+ pass)

4. **JS tests**: `npm test` (all 186 pass, no regressions)

5. **Manual E2E**: Navigate to `/lessons/`, click "Learn with Hermano" on a Spanish A0 lesson, verify Hermano teaches the content conversationally, answer exercises inline, see completion panel with score.

6. **Lint/type check**: `uv run ruff check src/ tests/ && uv run mypy src/`

---

## Future Work (Bridges 1-3)

This phase focuses exclusively on Bridge 4 (conversational lesson delivery). Three additional bridges are planned as follow-up work:

- **Bridge 1: Lesson Context Injection** (~30 lines) — Inject recently completed lesson context into regular chat's system prompt, so Hermano can reference what the student learned.
- **Bridge 2: Practice Scenario Generation** (~100 lines) — After completing a lesson, generate conversational practice scenarios that use the lesson's vocabulary and grammar patterns.
- **Bridge 3: Hermano Recommends Lessons** (~50 lines) — During free chat, when Hermano notices the student struggling with a concept, he suggests a relevant lesson from the catalog.
