# Phase 23: Lesson Experience Revamp — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify the lesson experience into the main chat page, purge the old step-by-step player, and fix exercise answer matching.

**Architecture:** Keep separate LangGraph graphs (freeform + lesson) but unify the route layer. One `/chat` page, one `/chat/stream` endpoint that routes internally based on `lesson_id` presence. Old player templates and routes deleted entirely.

**Tech Stack:** FastAPI, LangGraph, Jinja2/HTMX, Tailwind CSS, SSE, Vitest, pytest

---

### Task 1: Purge Old Lesson Player Templates

Delete the old step-by-step player templates that are being replaced by the conversational approach.

**Files:**
- Delete: `src/templates/lesson_player.html`
- Delete: `src/templates/partials/lesson_step.html`
- Delete: `src/templates/partials/lesson_exercise.html`

**Step 1: Delete the three template files**

```bash
rm src/templates/lesson_player.html
rm src/templates/partials/lesson_step.html
rm src/templates/partials/lesson_exercise.html
```

**Step 2: Run tests to check for breakage**

Run: `make test`
Expected: Some tests may reference deleted templates — note which ones fail.

**Step 3: Commit**

```bash
git add -u
git commit -m "chore: delete old lesson player templates (lesson_player, lesson_step, lesson_exercise)"
```

---

### Task 2: Remove Old Player Routes from `lessons.py`

Remove the `/lessons/{id}/play` route and related step/exercise HTMX routes. Keep the lesson list route.

**Files:**
- Modify: `src/api/routes/lessons.py` — remove `get_lesson_player` (lines 96-121), step navigation routes, exercise routes, `complete_lesson` route, and `handoff_to_chat` route
- Delete: tests for old player routes

**Step 1: Identify all old player routes in lessons.py**

The following routes serve the old player and must be removed:
- `GET /lessons/{lesson_id}/play` (get_lesson_player, ~line 96)
- `POST /lessons/{lesson_id}/step/next` and `/step/prev` (step navigation)
- `POST /lessons/{lesson_id}/exercise/{exercise_id}/submit` (exercise submission)
- `POST /lessons/{lesson_id}/complete` (complete_lesson, ~line 398)
- `POST /lessons/{lesson_id}/handoff` (handoff_to_chat, ~line 455)

Keep only:
- `GET /` (get_lessons_page) — the lesson list

**Step 2: Remove old player routes**

Remove all route handlers except `get_lessons_page`. Remove unused imports that were only needed by deleted routes.

**Step 3: Run tests**

Run: `pytest tests/api/routes/test_lessons.py -v`
Expected: Tests for deleted routes fail. Delete those test functions.

**Step 4: Delete old player test functions**

Remove test functions that test `/play`, `/step/next`, `/step/prev`, `/exercise/submit`, `/complete`, `/handoff` routes.

**Step 5: Run tests again**

Run: `pytest tests/api/routes/test_lessons.py -v`
Expected: PASS (only lesson list tests remain)

**Step 6: Commit**

```bash
git add -u
git commit -m "chore: remove old lesson player routes and tests from lessons.py"
```

---

### Task 3: Update Lessons List Page Links

Change the lessons list template to remove "Play" buttons and update "Learn with Hermano" links to point to `/chat?lesson={id}`.

**Files:**
- Modify: `src/templates/lessons.html` — lines 28, 45, 74, 91

**Step 1: Remove "Play" button links**

Remove or replace the links at lines 28 and 74 that point to `/lessons/{{ lesson.full_id }}/play`.

**Step 2: Update "Learn with Hermano" links**

Change links at lines 45 and 91 from `/chat/lesson/{{ lesson.full_id }}` to `/chat?lesson={{ lesson.full_id }}`.

**Step 3: Verify template renders**

Run: `make dev` and navigate to `/lessons` — verify buttons link correctly.

**Step 4: Commit**

```bash
git add src/templates/lessons.html
git commit -m "feat: update lesson list to use unified /chat?lesson= links, remove Play button"
```

---

### Task 4: Merge Lesson Chat Logic into `chat.py` — GET Handler

Extend the existing `/chat` GET handler to accept an optional `?lesson=` query param and render lesson context.

**Files:**
- Modify: `src/api/routes/chat.py` — extend `chat_page()` (~line 70)
- Reference: `src/api/routes/lesson_chat.py` — `lesson_chat_page()` (lines 60-113) for logic to port

**Step 1: Write failing test — GET /chat?lesson={id} returns lesson context**

In `tests/api/routes/test_chat.py`, add a test:

```python
def test_chat_page_with_lesson_param(client, mock_lesson_service):
    """GET /chat?lesson=es_a1_greetings_01 returns chat page with lesson context."""
    response = client.get("/chat?lesson=es_a1_greetings_01", headers=CSRF_HEADERS)
    assert response.status_code == 200
    assert "es_a1_greetings_01" in response.text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/api/routes/test_chat.py::test_chat_page_with_lesson_param -v`
Expected: FAIL

**Step 3: Implement lesson context in chat_page()**

Add optional `lesson` query param to `chat_page()`. If present:
1. Load lesson via `lesson_service.get_lesson(lesson_id)`
2. Add lesson metadata to template context: `lesson_id`, `lesson_title`, `lesson_level`, `lesson_language`
3. Set `lesson_mode = True` in context

If not present, render as normal freeform chat.

**Step 4: Run test to verify it passes**

Run: `pytest tests/api/routes/test_chat.py::test_chat_page_with_lesson_param -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/api/routes/chat.py tests/api/routes/test_chat.py
git commit -m "feat: extend GET /chat to accept ?lesson= query param with lesson context"
```

---

### Task 5: Merge Lesson Chat Logic into `chat.py` — Stream Handler

Extend `/chat/stream` POST to detect `lesson_id` in form data and route to the lesson graph.

**Files:**
- Modify: `src/api/routes/chat.py` — extend `stream_message()` (~line 326)
- Reference: `src/api/routes/lesson_chat.py` — `stream_lesson_message()` (lines 116-290) for logic to port

**Step 1: Write failing test — POST /chat/stream with lesson_id uses lesson graph**

```python
def test_stream_with_lesson_id_invokes_lesson_graph(client, mock_lesson_service, mock_lesson_graph):
    """POST /chat/stream with lesson_id routes to lesson graph."""
    response = client.post(
        "/chat/stream",
        data={"message": "Start the lesson", "lesson_id": "es_a1_greetings_01"},
        headers=CSRF_HEADERS,
    )
    assert response.status_code == 200
    mock_lesson_graph.astream.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/api/routes/test_chat.py::test_stream_with_lesson_id_invokes_lesson_graph -v`
Expected: FAIL

**Step 3: Implement lesson graph routing in stream_message()**

Port the core logic from `stream_lesson_message()` into `stream_message()`:
1. Check for `lesson_id` in form data
2. If present: load lesson, resolve lesson thread ID (`lesson:{user_or_session}:{lesson_id}`), check checkpoint, build inputs (init on first message, resume otherwise), invoke `build_lesson_chat_graph()`
3. If absent: existing freeform flow (unchanged)
4. SSE event emission stays identical — `lesson_progress`, `exercise_result`, `lesson_complete` events already handled by stream.js
5. Post-stream lesson completion persistence (check `lesson_completed` flag)

**Step 4: Run test to verify it passes**

Run: `pytest tests/api/routes/test_chat.py::test_stream_with_lesson_id_invokes_lesson_graph -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `make test`
Expected: PASS

**Step 6: Commit**

```bash
git add src/api/routes/chat.py tests/api/routes/test_chat.py
git commit -m "feat: extend POST /chat/stream to route lesson_id requests to lesson graph"
```

---

### Task 6: Delete `lesson_chat.py` and Deregister Routes

Now that logic lives in `chat.py`, delete the old lesson_chat module.

**Files:**
- Delete: `src/api/routes/lesson_chat.py`
- Modify: `src/api/main.py` — remove `lesson_chat` import (line 18) and `include_router` (line 123)
- Modify: `tests/api/routes/test_lesson_chat.py` — rewrite or delete (tests now target `/chat/stream`)

**Step 1: Remove lesson_chat from main.py**

Remove the import of `lesson_chat` from line 18 and `app.include_router(lesson_chat.router)` from line 123.

**Step 2: Delete lesson_chat.py**

```bash
rm src/api/routes/lesson_chat.py
```

**Step 3: Update or delete test_lesson_chat.py**

Move any valuable test cases to `test_chat.py` (targeting `/chat/stream` with `lesson_id`). Delete tests that test the old `/chat/lesson/` routes.

**Step 4: Run full test suite**

Run: `make test`
Expected: PASS — no references to deleted module remain

**Step 5: Run lint and typecheck**

Run: `make check`
Expected: PASS — no import errors

**Step 6: Commit**

```bash
git add -u
git commit -m "chore: delete lesson_chat.py, deregister old /chat/lesson routes"
```

---

### Task 7: Update `chat.html` Template — Swappable Header

Replace the bolted-on lesson header with a clean HTMX-swappable region.

**Files:**
- Modify: `src/templates/chat.html`

**Step 1: Remove old lesson mode attributes**

Remove from line 7: `data-lesson-mode="true" data-lesson-id="{{ lesson_id }}"` conditional.
Remove from line 148: `visibility: hidden` hack on selectors.

**Step 2: Create swappable header region**

Replace the current header area (language/level selectors + lesson header block at lines 246-268) with a single HTMX-swappable `div#chat-header`:

- **Freeform mode**: renders language picker + level selector (as today)
- **Lesson mode**: renders lesson title + thin progress bar + "Exit lesson" link

The mode is determined by template context (`lesson_mode` variable), not by JavaScript data attributes.

**Step 3: Add thin progress bar**

Replace the old progress bar (line 264, `#lesson-progress-bar`) with a 2-3px bar at top of chat area:
- CSS: `height: 3px`, theme accent color, `transition: width 0.3s ease`
- Only visible in lesson mode
- No percentage text, no phase badge

**Step 4: Remove old lesson header block**

Delete lines 246-268 (the phase badge, old progress bar, lesson title block).

**Step 5: Verify template renders in both modes**

Run: `make dev`, test `/chat` (freeform) and `/chat?lesson=es_a1_greetings_01` (lesson mode).

**Step 6: Commit**

```bash
git add src/templates/chat.html
git commit -m "feat: swappable chat header with thin progress bar for lesson mode"
```

---

### Task 8: Update `stream.js` — Lesson Mode Detection & Cleanup

Update JavaScript to detect lesson mode from URL params instead of data attributes, and replace the celebration banner with a compact completion card.

**Files:**
- Modify: `src/static/js/modules/stream.js`

**Step 1: Update isLessonMode()**

Change lines 29-32 from checking `[data-lesson-mode]` to:

```javascript
export function isLessonMode() {
    return new URLSearchParams(window.location.search).has('lesson');
}
```

**Step 2: Update getStreamUrl()**

Lines 38-40: endpoint is always `/chat/stream` now (lesson_id is in form data, not URL path).

```javascript
function getStreamUrl() {
    return '/chat/stream';
}
```

**Step 3: Remove PHASE_LABELS and updateLessonProgress phase badge logic**

Remove `PHASE_LABELS` (lines 394-400). Simplify `updateLessonProgress()` (lines 406-417) to only update the progress bar width — no phase badge text update.

**Step 4: Replace showLessonComplete() with compact completion card**

Replace the celebration banner (lines 448-485) with a compact card:
- Score + vocab count in a small card
- Two buttons: "Next Lesson" (links to next lesson) and "Free Chat" (links to `/chat`)
- No confetti, no giant banner

**Step 5: Update autoStartLesson()**

Lines 494-506: Hide the auto-sent "Start the lesson" message from chat so the first visible message is the AI's intro.

**Step 6: Ensure lesson_id is included in form data**

In `streamChat()` (line 297), when in lesson mode, extract `lesson` from URL params and include it as `lesson_id` in the FormData sent to `/chat/stream`.

**Step 7: Write JS tests**

Add Vitest tests for:
- `isLessonMode()` returns true when URL has `?lesson=` param
- `isLessonMode()` returns false on plain `/chat`
- `getStreamUrl()` always returns `/chat/stream`

**Step 8: Run JS tests**

Run: `npx vitest run`
Expected: PASS

**Step 9: Commit**

```bash
git add src/static/js/modules/stream.js tests/js/
git commit -m "feat: update stream.js for unified /chat route, compact lesson completion"
```

---

### Task 9: Fix Exercise Answer Matching — Fill-in-the-Blank

Improve `FillBlankExercise.check_answer()` to normalize whitespace, strip punctuation, and accept multiple valid answers.

**Files:**
- Modify: `src/lessons/models.py` — `FillBlankExercise.check_answer()` (lines 190-202)
- Modify: `tests/` — exercise model tests

**Step 1: Write failing test**

```python
def test_fill_blank_accepts_normalized_answer():
    exercise = FillBlankExercise(
        id="test", type="fill_blank",
        prompt="I am ___",
        answer="estoy bien",
        alternatives=["estoy muy bien"],
    )
    assert exercise.check_answer("Estoy bien.") is True  # punctuation + case
    assert exercise.check_answer("  estoy  bien  ") is True  # whitespace
    assert exercise.check_answer("estoy muy bien") is True  # alternative
    assert exercise.check_answer("wrong answer") is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/lessons/test_models.py::test_fill_blank_accepts_normalized_answer -v`
Expected: FAIL on punctuation/whitespace cases

**Step 3: Implement normalization in check_answer()**

```python
import re
import unicodedata

def _normalize_answer(text: str) -> str:
    """Normalize answer for comparison: lowercase, strip punctuation, collapse whitespace."""
    text = text.strip().lower()
    text = re.sub(r'[^\w\s]', '', text, flags=re.UNICODE)
    text = re.sub(r'\s+', ' ', text)
    return text
```

Update `FillBlankExercise.check_answer()` to use `_normalize_answer()` on both user input and stored answers.

**Step 4: Run test to verify it passes**

Run: `pytest tests/lessons/test_models.py::test_fill_blank_accepts_normalized_answer -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/lessons/models.py tests/lessons/test_models.py
git commit -m "fix: normalize fill-in-the-blank answers (whitespace, punctuation, case)"
```

---

### Task 10: Fix Exercise Answer Matching — Translation (LLM Evaluation)

For translation exercises, use the LLM's judgment instead of string matching.

**Files:**
- Modify: `src/agent/nodes/lesson_chat.py` — `_handle_exercise_eval()` (lines 337-340)
- Modify: `src/agent/prompts_lesson_chat.py` — exercise_eval prompt

**Step 1: Update exercise_eval prompt**

Add instruction to the exercise_eval system prompt: the LLM must include `[CORRECT]` or `[INCORRECT]` tag at the very start of its response for translation exercises. Example:

```
[CORRECT] Great job! "Estoy bien" is exactly right...
[INCORRECT] Not quite — "Estoy bien" means "I'm fine", but...
```

**Step 2: Update _handle_exercise_eval for translation exercises**

In `_handle_exercise_eval()`, for `TranslateExercise`:
1. Don't call `check_answer()` for string matching
2. Instead, after LLM responds, parse the `[CORRECT]`/`[INCORRECT]` tag from the response
3. Use that as the `is_correct` value
4. Strip the tag from the displayed message

**Step 3: Write test**

```python
def test_translation_uses_llm_judgment():
    """Translation exercises use LLM [CORRECT]/[INCORRECT] tag, not string match."""
    # Mock LLM response with [CORRECT] tag
    # Verify is_correct=True even if string doesn't match exactly
```

**Step 4: Run tests**

Run: `pytest tests/agent/nodes/test_lesson_chat.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/agent/nodes/lesson_chat.py src/agent/prompts_lesson_chat.py tests/agent/nodes/test_lesson_chat.py
git commit -m "fix: use LLM judgment for translation exercise evaluation"
```

---

### Task 11: Add Lesson Resume Support

When navigating to `/chat?lesson=X` with an existing checkpoint, show previous messages and a resume indicator.

**Files:**
- Modify: `src/api/routes/chat.py` — `chat_page()` GET handler
- Modify: `src/templates/chat.html` — render previous messages if resuming

**Step 1: In chat_page(), check for existing lesson checkpoint**

If `?lesson=` param present:
1. Build thread_id: `lesson:{user_or_session}:{lesson_id}`
2. Check checkpointer for existing state
3. If checkpoint exists, extract messages and pass to template as `resume_messages`
4. Template renders them as existing chat bubbles before auto-starting

**Step 2: In chat.html, render resume messages**

If `resume_messages` context variable is set, render each message as a chat bubble (reuse existing message partial). Add a system message: "Resuming your lesson — pick up where you left off."

**Step 3: Update autoStartLesson()**

If resume messages are rendered, don't auto-send "Start the lesson" — the lesson is already in progress. User just types their next response.

**Step 4: Write test**

```python
def test_chat_page_resumes_lesson_with_checkpoint(client, mock_checkpointer):
    """GET /chat?lesson=X with checkpoint shows previous messages."""
    # Setup mock checkpoint with messages
    response = client.get("/chat?lesson=es_a1_greetings_01")
    assert "Resuming your lesson" in response.text
```

**Step 5: Run tests**

Run: `pytest tests/api/routes/test_chat.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/api/routes/chat.py src/templates/chat.html tests/api/routes/test_chat.py
git commit -m "feat: lesson resume support with checkpoint message recovery"
```

---

### Task 12: Final Cleanup and Verification

Remove any remaining dead code, run full suite, verify lint/typecheck.

**Files:**
- Modify: `src/api/main.py` — verify no stale imports
- Check: all `src/` files for references to deleted routes/templates

**Step 1: Search for stale references**

```bash
rg "lesson_player" src/
rg "lesson_step" src/
rg "lesson_exercise" src/
rg "/chat/lesson" src/
rg "data-lesson-mode" src/
```

Fix any remaining references.

**Step 2: Run full test suite**

Run: `make test`
Expected: ALL PASS

**Step 3: Run lint and typecheck**

Run: `make check`
Expected: PASS

**Step 4: Run JS tests**

Run: `npx vitest run`
Expected: PASS

**Step 5: Commit any final cleanup**

```bash
git add -u
git commit -m "chore: final cleanup — remove stale references to old lesson system"
```

---

## Task Dependency Graph

```
Task 1 (delete templates) ──┐
Task 2 (delete player routes) ──┼── Task 3 (update lesson list links)
                                │
Task 4 (GET /chat?lesson=) ─────┤
Task 5 (POST /chat/stream) ─────┼── Task 6 (delete lesson_chat.py)
                                │
Task 7 (update chat.html) ──────┤
Task 8 (update stream.js) ──────┤
                                │
Task 9 (fix fill-blank) ────────┤   (independent)
Task 10 (fix translation) ──────┤   (independent)
                                │
Task 11 (resume support) ───────┤   (depends on Task 4+5)
                                │
Task 12 (final cleanup) ────────┘   (depends on all above)
```

**Parallelizable groups:**
- **Group A** (purge): Tasks 1, 2, 3 (can run together)
- **Group B** (unify routes): Tasks 4, 5 → Task 6 (sequential)
- **Group C** (UI): Tasks 7, 8 (can run together)
- **Group D** (exercise fixes): Tasks 9, 10 (can run together)
- **Group E** (resume): Task 11 (depends on Group B)
- **Group F** (cleanup): Task 12 (depends on all)
