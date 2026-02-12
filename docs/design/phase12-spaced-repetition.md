# Phase 12: Spaced Repetition System

> Conversational vocabulary review with SM-2 scheduling and intelligent chat weaving

---

## Overview

Add spaced repetition to Habla Hermano through two complementary features:

1. **Dedicated Review Mode** - Conversational micro-quizzes where Hermano asks review questions in the chat interface
2. **Intelligent Chat Weaving** - Hermano naturally incorporates due review words into regular conversations

**Design Philosophy**: Stay true to "conversation, not flashcards." Reviews happen through dialogue with Hermano, not card flips. Users may not even realize they're doing spaced repetition - it just feels like chatting with a friend who helps you remember.

---

## Goals

- Help users retain vocabulary learned in lessons and conversations
- Maintain the Hermano personality throughout review interactions
- No gamification guilt - reviews are optional and pressure-free
- Leverage existing chat UI and infrastructure
- Support both authenticated and guest users

---

## Data Model Changes

### New Fields on `Vocabulary` Table

```python
class Vocabulary(BaseModel):
    # ... existing fields ...
    id: int | None = None
    user_id: str
    word: str
    translation: str
    language: str
    part_of_speech: str | None = None
    first_seen_at: datetime
    times_seen: int = 1
    times_correct: int = 0

    # NEW: SM-2 spaced repetition fields
    easiness_factor: float = 2.5          # How easy this word is (1.3 - 2.5+)
    interval_days: int = 0                # Current review interval
    repetition_count: int = 0             # Successful reviews in a row
    next_review_at: datetime | None = None  # When due (None = not yet in rotation)
    last_reviewed_at: datetime | None = None
```

### Database Migration

```sql
ALTER TABLE vocabulary
ADD COLUMN easiness_factor FLOAT DEFAULT 2.5,
ADD COLUMN interval_days INTEGER DEFAULT 0,
ADD COLUMN repetition_count INTEGER DEFAULT 0,
ADD COLUMN next_review_at TIMESTAMPTZ,
ADD COLUMN last_reviewed_at TIMESTAMPTZ;

-- Index for efficient due word queries
CREATE INDEX idx_vocabulary_next_review
ON vocabulary(user_id, language, next_review_at)
WHERE next_review_at IS NOT NULL;
```

### Query for Due Words

```sql
SELECT * FROM vocabulary
WHERE user_id = :user_id
  AND language = :language
  AND next_review_at IS NOT NULL
  AND next_review_at <= NOW()
ORDER BY next_review_at ASC
LIMIT :count;
```

---

## SM-2 Algorithm

### Quality Score Inference

Instead of asking users to rate difficulty, Hermano infers quality from their response:

| User Response | Quality | Hermano's Interpretation |
|---------------|---------|--------------------------|
| Correct, fast, no hesitation | 5 | "You nailed it!" |
| Correct with minor typo/accent | 4 | "Got it! Small typo but you knew it." |
| Correct after hint shown | 3 | "There you go - hint helped!" |
| Incorrect, recognizes correct answer | 2 | "Ah right, that one's tricky." |
| Incorrect, seems unfamiliar | 1 | "No worries, let's add this one back." |
| Complete blank / skip | 0 | "All good, we'll come back to it." |

### Algorithm Implementation

```python
# src/services/review.py

from datetime import datetime, timedelta
from src.db.models import Vocabulary


def update_sm2(vocab: Vocabulary, quality: int) -> Vocabulary:
    """Update vocabulary item using SM-2 algorithm.

    Args:
        vocab: The vocabulary item to update
        quality: Score 0-5 indicating recall quality

    Returns:
        Updated vocabulary with new scheduling
    """
    if quality >= 3:  # Successful recall
        if vocab.repetition_count == 0:
            vocab.interval_days = 1
        elif vocab.repetition_count == 1:
            vocab.interval_days = 6
        else:
            vocab.interval_days = round(vocab.interval_days * vocab.easiness_factor)

        vocab.repetition_count += 1
    else:  # Failed recall - reset
        vocab.repetition_count = 0
        vocab.interval_days = 1

    # Update easiness factor (never below 1.3)
    vocab.easiness_factor = max(
        1.3,
        vocab.easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    )

    # Schedule next review
    vocab.next_review_at = datetime.utcnow() + timedelta(days=vocab.interval_days)
    vocab.last_reviewed_at = datetime.utcnow()

    # Update accuracy tracking
    vocab.times_seen += 1
    if quality >= 3:
        vocab.times_correct += 1

    return vocab
```

### Practical Effect

- Word you nail consistently (quality 5): 1d → 6d → 15d → 38d → 95d...
- Word you struggle with (quality 2): Resets to 1 day, easiness drops, stays frequent
- Missed words within a session get extra repetitions before session ends

---

## Feature 1: Dedicated Review Mode

### Entry Points

**1. Progress Page Card**

New card in the progress dashboard showing due word count:

```html
<div class="review-card">
  <div class="review-count">12</div>
  <div class="review-label">words due for review</div>

  <a href="/chat?mode=review" class="review-button">
    Review Now
  </a>

  <p class="review-hint">~5 minutes</p>
</div>
```

**2. Chat Entry Prompt**

When user opens chat with words due:

```html
<div class="warmup-prompt">
  <p>Hey, you've got some words getting rusty - want a quick warmup?</p>
  <button hx-get="/chat?mode=review">Sure!</button>
  <button hx-delete="/review/warmup-prompt">Skip for now</button>
</div>
```

### Session Flow

**Session Start (on Chat page with `?mode=review`):**

```
Hermano: "You've got 23 words ready for review! How much time do you have?"

[ Quick (5) ]  [ Regular (10) ✓ ]  [ All (23) ]

                [ Let's go! ]
```

- Pre-select "Regular (10)" as default
- User can change or just hit start
- Hermano frames options casually, not clinically

**Review Loop:**

1. Hermano asks a question (varied formats):
   - Translation: "How do you say 'thank you'?"
   - Fill-in-context: "At a restaurant, you'd say '_____ la cuenta, por favor' to ask for the bill"
   - Recognition: "What does 'cansado' mean?"

2. User responds in chat input

3. Hermano gives feedback (warm, brief):
   - Correct: "Nice! 'Gracias' - you've got it."
   - Incorrect: "Close! It's 'pedir'. No worries, we'll circle back."
   - Repeat miss: "Let's slow down on this one..." + brief teaching moment

4. Progress indicator updates: "Review: 4 of 10"

5. Repeat until session complete

**Session End:**

```
Hermano: "Nice work! You reviewed 10 words - 8 solid, 2 we'll
         practice again soon. Want to keep chatting or call it?"

[ Continue Chatting ]  [ I'm done for now ]
```

### UI Components

**Review Mode Banner (when active):**

```html
<div class="review-banner">
  Review Session: <span id="review-progress">3 of 10</span>
  <button hx-post="/review/end">End Early</button>
</div>
```

**Session Start Selector:**

```html
<div class="review-start">
  <p>You've got <strong>23 words</strong> ready for review!</p>

  <div class="review-options">
    <button hx-post="/review/start?count=5">Quick (5)</button>
    <button hx-post="/review/start?count=10" class="selected">Regular (10)</button>
    <button hx-post="/review/start?count=all">All (23)</button>
  </div>
</div>
```

---

## Feature 2: Intelligent Chat Weaving

### How It Works

During regular (non-review) conversation, Hermano naturally incorporates words that are due for review when they fit the topic.

**Flow:**

1. Before generating response, query due review words
2. Check if any match the conversation topic
3. Include relevant words in Hermano's prompt as suggestions
4. Hermano uses them naturally (or ignores if they don't fit)
5. Track user's response - if they correctly use/understand the word, update SM-2

### Example

```
User: "I went to the beach yesterday"

[System detects: "playa" (beach) and "ayer" (yesterday) are due
 and topically relevant]

Hermano: "¡Qué bien! ¿Te gustó la playa? I love beach days.
         ¿Qué hiciste ayer después?"

[Uses both review words naturally]

User: "Sí, la playa was beautiful. Ayer I also got ice cream"

[User correctly used both words in context → Update SM-2 as quality 4-5]
```

### Prompt Addition

```
REVIEW OPPORTUNITY (use naturally if relevant, ignore if not):
These words are due for review: [playa, cansado, mañana]
If conversation allows, try to use them or prompt the user to use them.
Do NOT force them awkwardly - conversation flow comes first.
```

### Tracking Logic

- Parse user's response for review words
- Correct usage in context → quality 4-5, update SM-2
- Incorrect usage → Hermano gently models correct form, quality 2
- Word doesn't fit topic → no update, stays in queue

**Key constraint**: Conversation flow always wins. Hermano never forces awkward word insertions.

---

## LangGraph Integration

### Review State

```python
# src/agent/review_state.py

from typing import TypedDict, NotRequired


class ReviewState(TypedDict):
    """State for review session subgraph."""
    user_id: str
    language: str
    level: str

    # Session tracking
    words_to_review: list[dict]     # Queue of vocab items
    current_word_index: int
    session_size: int               # 5, 10, or total count

    # Current question
    current_word: NotRequired[dict]
    question_type: NotRequired[str]  # translate, fill_blank, recognize
    question_text: NotRequired[str]

    # Answer evaluation
    user_answer: NotRequired[str]
    quality_score: NotRequired[int]  # 0-5 SM-2 score
    feedback_text: NotRequired[str]

    # Session results
    results: list[dict]             # [{word_id, quality, correct}]
```

### Review Subgraph

```python
# src/agent/review_graph.py

def build_review_subgraph() -> CompiledGraph:
    """Build the review session subgraph."""
    graph = StateGraph(ReviewState)

    graph.add_node("generate_question", generate_question_node)
    graph.add_node("evaluate_answer", evaluate_answer_node)
    graph.add_node("update_sm2", update_sm2_node)

    graph.set_entry_point("generate_question")
    graph.add_edge("generate_question", END)  # Wait for user input

    # After user answers:
    # evaluate_answer -> update_sm2 -> END

    return graph.compile()
```

**Graph Flow:**

```
┌─────────────────────┐
│  generate_question  │ ← Pick question type, format with Hermano voice
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  evaluate_answer    │ ← Infer quality score, generate feedback
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  update_sm2         │ ← Persist new intervals to database
└──────────┬──────────┘
           │
           ▼
         [END]
```

### Chat Weaving Integration

Modify `respond_node` in main conversation graph:

```python
async def respond_node(state: ConversationState) -> dict:
    """Generate AI response with optional review word weaving."""

    # Check for due review words matching conversation topic
    due_words = await get_topical_review_words(
        user_id=state["user_id"],
        recent_messages=state["messages"][-4:],
        language=state["language"]
    )

    # Build prompt
    prompt = get_prompt_for_level(state["language"], state["level"])

    if due_words:
        prompt += f"""

REVIEW OPPORTUNITY (use naturally if relevant, ignore if not):
These words are due for review: {[w['word'] for w in due_words]}
If conversation allows, use them or prompt the user to use them.
Do NOT force them awkwardly - conversation flow comes first.
"""

    response = await llm.ainvoke([
        SystemMessage(content=prompt),
        *state["messages"]
    ])

    return {"messages": [response], "review_words_offered": due_words}
```

---

## API Endpoints

### New Routes: `src/api/routes/review.py`

```python
from fastapi import APIRouter, Depends, Cookie
from typing import Annotated, Literal

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/stats")
async def get_review_stats(
    user: OptionalUserDep,
    session_id: Annotated[str | None, Cookie()] = None,
    language: str = "es",
) -> dict:
    """Get review statistics for progress page.

    Returns:
        {due_count: 12, next_review_in: "2 hours", total_in_rotation: 45}
    """


@router.post("/start")
async def start_review_session(
    count: int | Literal["all"],
    user: OptionalUserDep,
    session_id: Annotated[str | None, Cookie()] = None,
    language: str = "es",
) -> HTMLResponse:
    """Initialize review session and return first question.

    Args:
        count: Number of words (5, 10, or "all")
    """


@router.post("/answer")
async def submit_review_answer(
    word_id: int,
    user_answer: str,
    user: OptionalUserDep,
    session_id: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """Validate answer, update SM-2, return feedback + next question."""


@router.post("/end")
async def end_review_session(
    user: OptionalUserDep,
    session_id: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """End session early, return summary partial."""


@router.delete("/warmup-prompt")
async def dismiss_warmup(
    user: OptionalUserDep,
    session_id: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """Dismiss warmup prompt for this session."""
```

### Modified Existing Routes

**`src/api/routes/chat.py`:**

```python
@router.get("/")
async def chat_page(
    request: Request,
    mode: str | None = None,  # NEW: "review" mode
    ...
):
    """Render chat page, with review mode support."""
    if mode == "review":
        review_stats = await get_review_stats(user_id, language)
        return templates.TemplateResponse(
            "chat.html",
            {"review_mode": True, "review_stats": review_stats, ...}
        )
    # ... normal chat rendering
```

**`src/api/routes/progress.py`:**

```python
@router.get("/")
async def progress_page(...):
    """Include review stats in progress dashboard."""
    review_stats = await review_service.get_stats(user_id, language)

    return templates.TemplateResponse(
        "progress.html",
        {
            "stats": dashboard_stats,
            "review_stats": review_stats,  # NEW
            ...
        }
    )
```

---

## Service Layer

### `src/services/review.py`

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from src.db.models import Vocabulary
from src.db.repository import VocabularyRepository


@dataclass(frozen=True)
class ReviewStats:
    """Statistics for review UI."""
    due_count: int
    next_review_in: str | None  # "2 hours", "tomorrow", None if nothing due
    total_in_rotation: int


@dataclass(frozen=True)
class ReviewSession:
    """Active review session state."""
    words: list[Vocabulary]
    current_index: int
    session_size: int
    results: list[dict]


class ReviewService:
    """Service for spaced repetition review operations."""

    def __init__(self, user_id: str, client=None):
        self._user_id = user_id
        self._vocab_repo = VocabularyRepository(user_id, client=client)

    def get_stats(self, language: str = "es") -> ReviewStats:
        """Get review statistics for UI."""
        ...

    def get_due_words(
        self,
        language: str,
        limit: int | None = None
    ) -> list[Vocabulary]:
        """Get words due for review, ordered by most overdue."""
        ...

    def get_topical_review_words(
        self,
        language: str,
        topic_keywords: list[str],
        limit: int = 5,
    ) -> list[Vocabulary]:
        """Get due words matching conversation topic for weaving."""
        ...

    def update_sm2(self, vocab_id: int, quality: int) -> Vocabulary:
        """Apply SM-2 algorithm and persist."""
        ...

    def initialize_word_for_review(self, vocab_id: int) -> Vocabulary:
        """Set initial next_review_at for a newly learned word."""
        ...
```

---

## Word Entry into Review Rotation

Words enter the review rotation from two sources:

### 1. After Lessons

When a lesson is completed, vocabulary from that lesson gets scheduled:

```python
# In lesson completion handler
async def complete_lesson(lesson_id: str, ...):
    vocab_words = lesson_service.get_lesson_vocabulary(lesson_id)

    for word in vocab_words:
        # Ensure word exists in user's vocabulary
        vocab = vocab_repo.upsert(word, ...)

        # Schedule for review starting tomorrow
        if vocab.next_review_at is None:
            review_service.initialize_word_for_review(vocab.id)
```

### 2. After Chat Conversations

Words extracted by the analyze node get scheduled:

```python
# In record_chat_activity
async def record_chat_activity(new_vocab: list[VocabWord], ...):
    for word in new_vocab:
        vocab = vocab_repo.upsert(word, ...)

        # Schedule for review if new
        if vocab.next_review_at is None:
            review_service.initialize_word_for_review(vocab.id)
```

---

## Implementation Phases

### Phase 1: Data Model & Core Algorithm
- Add SM-2 fields to Vocabulary model
- Database migration for new columns
- Implement `ReviewService` with SM-2 calculation
- Add `get_due_words()` query
- Unit tests for SM-2 algorithm
- Initialize existing vocabulary with review scheduling

### Phase 2: Dedicated Review Mode
- Create review subgraph (state, nodes)
- Add `/review` API endpoints
- Review session start UI (count selector)
- Question generation with varied formats
- Answer evaluation and quality inference
- Hermano-style feedback generation
- Session progress tracking and summary

### Phase 3: Entry Points & UI
- Progress page review card with due count
- Chat page warmup prompt when words due
- Review mode banner and progress indicator
- "End Early" and session completion flows
- HTMX partials for all review UI states

### Phase 4: Intelligent Chat Weaving
- Topical word matching logic
- Prompt injection for due words in respond_node
- Response parsing to detect word usage
- Background SM-2 updates from conversation
- Silent tracking without interrupting flow

### Phase 5: Polish & Edge Cases
- Handle zero due words gracefully
- Guest user support (using existing identity resolution)
- Words that fail multiple times get extra repetition in session
- Configurable new word graduation delay
- Review statistics in progress charts

---

## Testing Strategy

### Unit Tests

- SM-2 algorithm calculations for all quality scores
- Interval progression over multiple reviews
- Easiness factor bounds (never below 1.3)
- Due word query correctness
- Quality score inference logic

### Integration Tests

- Review session lifecycle (start → answer → complete)
- Session persistence across requests
- Guest user review support
- Word entry into rotation from lessons
- Word entry into rotation from chat

### E2E Tests (Playwright)

- Start review from Progress page
- Start review from Chat warmup prompt
- Complete full review session
- End review session early
- Dismiss warmup and proceed to chat

---

## Success Metrics

### Retention Effectiveness
- Words with 3+ successful reviews (quality 3+)
- Average easiness factor trending upward over time
- Reduction in "forgot completely" (quality 0-1) over time

### Engagement
- Review sessions started per user per week
- Completion rate (finished vs. ended early)
- Warmup prompt acceptance rate

### Integration Quality
- Words reviewed via intelligent weaving vs. dedicated mode
- Conversation naturalness (no complaints about forced words)

---

## Future Enhancements (Out of Scope)

- Audio pronunciation in review questions
- Review reminders via notifications
- Customizable session lengths
- "Cram mode" before travel/exams
- Review statistics visualization in Progress charts
- Shared/competitive review challenges

---

## Dependencies

- Existing Vocabulary model and repository
- Existing Progress page infrastructure
- Existing Chat page and HTMX patterns
- Existing LangGraph subgraph patterns (lessons)
- Existing guest user support (identity resolution)
