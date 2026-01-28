# Habla Hermano Technical Architecture

> FastAPI + HTMX + LangGraph for conversational language learning

---

## Current Implementation Status

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Minimal Graph - Basic state, single respond node | ✅ Completed |
| **Phase 2** | Analysis Node - Multi-node graphs, sequential edges | ✅ Completed |
| **Phase 3** | Conditional Routing - Branching logic, scaffolding | ✅ Completed |
| **Phase 4** | Checkpointing - PostgreSQL persistence, conversation memory | ✅ Completed |
| **Phase 5** | Authentication - Supabase Auth, multi-user support | ✅ Completed |
| **Phase 6** | Micro-Lessons - Structured lesson content, exercises, progress | ✅ Completed |
| **Phase 7** | Progress Tracking - Dashboard stats, vocabulary tracking, chart data | ✅ Completed |
| **Phase 8** | Guest Sessions - Anonymous progress, data merge on signup/login | ✅ Completed |

**Test Coverage**: 918+ tests (86%+ coverage) covering agent, API, database, auth, lessons, and service modules. E2E testing is documented in [docs/playwright-e2e.md](./playwright-e2e.md).

---

## Learning Goals

This project is intentionally built with **LangGraph** to learn:
- State management with TypedDict and reducers
- Graph routing with conditional edges
- Checkpointing and conversation persistence
- Node composition and reusability

**Approach**: Start with minimal viable graph, add complexity as features demand it.

---

## The Hermano Personality System

Habla Hermano features "Hermano" - a friendly, laid-back big brother figure who makes language learning feel like chatting with a supportive friend.

### Personality Implementation

The Hermano personality is defined in `src/agent/prompts.py` and adapts based on learner level:

| Level | Hermano's Approach |
|-------|-------------------|
| **A0** | Supportive big brother, heavy encouragement, celebrates tiny wins |
| **A1** | Chill friend who spent a year abroad, relaxed guidance |
| **A2** | Challenges learners while keeping it fun and conversational |
| **B1** | Peer-to-peer natural conversation partner |

### Language Adapter Pattern

The system uses a dictionary adapter pattern for clean language switching, replacing the previous string replacement approach.

**LANGUAGE_ADAPTER Dictionary** (`src/agent/prompts.py`):

```python
LANGUAGE_ADAPTER: dict[str, dict[str, str]] = {
    "es": {
        "language_name": "Spanish",
        "hello": "Hola",
        "my_name_is": "Me llamo",
        "goodbye": "Adios",
        "thank_you": "Gracias",
        # ... more phrases
    },
    "de": {
        "language_name": "German",
        "hello": "Hallo",
        "my_name_is": "Ich heisse",
        # ...
    },
    "fr": {
        "language_name": "French",
        "hello": "Bonjour",
        "my_name_is": "Je m'appelle",
        # ...
    },
}
```

**Prompt Templates** use placeholders:

```python
LEVEL_PROMPTS = {
    "A0": """
You are "Hermano" - a friendly, laid-back language buddy helping absolute beginners learn {language_name}.

PERSONALITY: Think supportive big brother who's been through this journey...

Example exchange:
You: "Hey! Let's start with the basics. '{hello}' means 'hello' - pretty easy, right?"
""",
    # ... A1, A2, B1 prompts
}
```

**Language Resolution** (`get_prompt_for_level`):

```python
def get_prompt_for_level(language: str, level: str) -> str:
    prompt = LEVEL_PROMPTS.get(level, LEVEL_PROMPTS["A1"])
    lang_data = LANGUAGE_ADAPTER.get(language, LANGUAGE_ADAPTER["es"])

    format_dict = {
        "language_name": lang_data["language_name"],
        "hello": lang_data["hello"],
        "hello_lower": lang_data["hello"].lower(),
        "my_name_is": lang_data["my_name_is"],
        # ... all language-specific values
    }

    return prompt.format(**format_dict)
```

### Benefits of the Adapter Pattern

1. **Extensibility**: Add new languages by adding dictionary entries
2. **Separation of Concerns**: Language data separate from prompt logic
3. **Type Safety**: Dictionary structure provides clear interface
4. **Maintainability**: Update phrases in one place, affects all prompts
5. **Testability**: Easy to test language resolution independently

---

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Backend** | FastAPI | Async support, SSE streaming, Pydantic validation |
| **Frontend** | HTMX + Jinja2 | Server-driven UI, minimal JS, fast iteration |
| **Agent** | LangGraph | Learning goal: stateful conversations, routing, checkpointing |
| **LLM** | Claude API | Superior language understanding, structured outputs |
| **Database** | PostgreSQL (Supabase) | Production persistence with MemorySaver fallback for dev |
| **Auth** | Supabase Auth | JWT-based authentication with httponly cookies |
| **Styling** | Tailwind CSS + CSS Variables | Utility-first, 3-theme system (dark/light/ocean) |

---

## Project Structure

Legend: Implemented files are marked with a checkmark. Files without a checkmark are planned for future phases.

```
habla-hermano/
├── src/
│   ├── api/
│   │   ├── __init__.py          # [Implemented]
│   │   ├── main.py              # [Implemented] FastAPI app entry
│   │   ├── config.py            # [Implemented] Settings (Pydantic)
│   │   ├── dependencies.py      # [Implemented] DI for graph, db session
│   │   ├── auth.py              # [Implemented] JWT validation, CurrentUserDep, OptionalUserDep
│   │   ├── session.py           # [Implemented] Thread ID management
│   │   ├── supabase_client.py   # [Implemented] Supabase client singleton (anon + admin)
│   │   └── routes/
│   │       ├── __init__.py      # [Implemented]
│   │       ├── chat.py          # [Implemented] POST /chat (protected)
│   │       ├── auth.py          # [Implemented] Login, signup, logout
│   │       ├── lessons.py       # [Implemented] Micro-lesson endpoints (list, play, steps, exercises)
│   │       └── progress.py      # [Implemented] Vocabulary, stats endpoints
│   │
│   ├── agent/
│   │   ├── __init__.py          # [Implemented]
│   │   ├── graph.py             # [Implemented] LangGraph: respond → scaffold (conditional) → analyze → END
│   │   ├── state.py             # [Implemented] TypedDict state with GrammarFeedback, VocabWord
│   │   ├── prompts.py           # [Implemented] System prompts by level
│   │   ├── checkpointer.py      # [Implemented] PostgresSaver + MemorySaver fallback
│   │   └── nodes/
│   │       ├── __init__.py      # [Implemented]
│   │       ├── respond.py       # [Implemented] Generate AI response
│   │       ├── analyze.py       # [Implemented] Grammar/vocab analysis
│   │       ├── scaffold.py      # [Implemented] Generate scaffolding (word banks, hints, sentence starters)
│   │       └── feedback.py      # [Planned] Format corrections
│   │
│   ├── lessons/
│   │   ├── __init__.py          # [Implemented] Module exports
│   │   ├── models.py            # [Implemented] Lesson, Step, Exercise, Progress models
│   │   └── service.py           # [Implemented] Lesson loading, filtering, vocabulary extraction
│   │
│   ├── db/
│   │   ├── __init__.py          # [Implemented] Module exports
│   │   ├── models.py            # [Implemented] Pydantic models (Vocabulary, LearningSession, LessonProgress)
│   │   ├── repository.py        # [Implemented] Repository classes for Supabase data access
│   │   └── seed.py              # [Implemented] Initial data seeding
│   │
│   ├── services/
│   │   ├── __init__.py          # [Implemented] Module exports
│   │   ├── vocabulary.py        # [Implemented] Vocab extraction logic
│   │   ├── levels.py            # [Implemented] Level detection/adjustment
│   │   ├── progress.py          # [Implemented] ProgressService for dashboard aggregation
│   │   └── merge.py             # [Implemented] GuestDataMergeService for auth data transfer
│   │
│   ├── templates/               # [Implemented] All template files
│   │   ├── base.html            # [Implemented] Theme system (dark/light/ocean), CSS variables
│   │   ├── chat.html            # [Implemented] Chat UI with hamburger menu (Lessons, New Chat, Theme, Auth), language/level selectors
│   │   ├── lessons.html         # [Implemented] Lesson catalog with beginner/intermediate grouping
│   │   ├── lesson_player.html   # [Implemented] Interactive lesson player with step navigation
│   │   ├── progress.html        # [Implemented] Progress dashboard with stats, vocabulary, charts
│   │   ├── auth/
│   │   │   ├── login.html       # [Implemented] Login page
│   │   │   └── signup.html      # [Implemented] Signup page
│   │   └── partials/
│   │       ├── message.html     # [Implemented] Message bubble styling
│   │       ├── message_pair.html # [Implemented] AI response partial (optimistic UI)
│   │       ├── lesson_step.html # [Implemented] Step content by type (instruction, vocabulary, example, tip, practice)
│   │       ├── lesson_exercise.html # [Implemented] Exercise forms (multiple choice, fill blank, translate)
│   │       ├── lesson_complete.html # [Implemented] Completion celebration with handoff to chat
│   │       ├── grammar_feedback.html # [Implemented] Collapsible grammar feedback
│   │       ├── scaffold.html    # [Implemented] Word bank, hints, sentence starters UI
│   │       ├── vocab_sidebar.html
│   │       ├── progress_vocab.html  # [Implemented] Vocabulary list partial
│   │       └── stats_summary.html   # [Implemented] Stats summary partial
│   │
│   └── static/
│       ├── css/
│       └── js/
│           └── app.js           # [Implemented] HTMX handlers, optimistic UI, keyboard shortcuts
│
├── tests/
├── data/
│   ├── hermano.db
│   └── lessons/                 # [Implemented] Lesson content (YAML)
│       └── es/                  # Spanish lessons
│           └── A0/              # Absolute beginner lessons
│               ├── greetings-001.yaml
│               ├── introductions-001.yaml
│               ├── numbers-001.yaml
│               ├── colors-001.yaml
│               └── family-001.yaml
│
├── docs/
├── pyproject.toml
├── Makefile
└── .env.example
```

---

## LangGraph Learning Progression

Build the graph incrementally, learning concepts as you go:

### Phase 1: Minimal Graph (Week 1) - IMPLEMENTED
**Learn**: Basic graph structure, state, single node

**Status**: This phase is complete and working in production. The minimal graph with a single respond node is fully operational.

```python
# Simplest possible graph - just responds
class ConversationState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    level: str  # A0, A1, A2, B1
    language: str  # es, de

def build_graph():
    graph = StateGraph(ConversationState)
    graph.add_node("respond", respond_node)
    graph.set_entry_point("respond")
    graph.add_edge("respond", END)
    return graph.compile()
```

**What you'll learn**:
- StateGraph basics
- TypedDict state definition
- The `add_messages` reducer pattern
- Node functions that read/write state

### Phase 2: Add Analysis Node (Week 1-2) - IMPLEMENTED
**Learn**: Multi-node graphs, sequential edges

**Status**: This phase is complete. The graph now chains respond → analyze → END, with grammar feedback displayed in a collapsible UI.

```python
def build_graph():
    graph = StateGraph(ConversationState)

    graph.add_node("respond", respond_node)
    graph.add_node("analyze", analyze_node)  # Grammar/vocab analysis

    graph.set_entry_point("respond")
    graph.add_edge("respond", "analyze")     # Chain nodes
    graph.add_edge("analyze", END)

    return graph.compile()
```

**What you learned**:
- Chaining nodes sequentially with `add_edge()`
- State passing between nodes (analyze reads messages from respond)
- Extending state with new fields (grammar_feedback, new_vocabulary)
- Using NotRequired for optional state fields

### Phase 3: Conditional Routing (Week 2) - IMPLEMENTED
**Learn**: Conditional edges, branching logic

**Status**: This phase is complete. The graph now uses conditional routing to provide scaffolding support (word banks, hints, sentence starters) for beginner levels (A0/A1), while skipping scaffolding for intermediate levels (A2/B1).

```python
def needs_scaffold(state: ConversationState) -> str:
    """Route based on user level - beginners get scaffolding support"""
    if state["level"] in ["A0", "A1"]:
        return "scaffold"
    return "analyze"

def build_graph():
    graph = StateGraph(ConversationState)

    graph.add_node("respond", respond_node)
    graph.add_node("scaffold", scaffold_node)  # NEW: Generates contextual help
    graph.add_node("analyze", analyze_node)

    graph.set_entry_point("respond")

    # Conditional routing based on level
    graph.add_conditional_edges(
        "respond",
        needs_scaffold,
        {
            "scaffold": "scaffold",  # A0/A1 learners get scaffolding
            "analyze": "analyze"      # A2/B1 learners skip to analysis
        }
    )

    graph.add_edge("scaffold", "analyze")
    graph.add_edge("analyze", END)

    return graph.compile()
```

**Graph Flow**:
- **A0/A1 learners**: START -> respond -> scaffold -> analyze -> END
- **A2/B1 learners**: START -> respond -> analyze -> END

**What you learned**:
- Conditional edge functions with `add_conditional_edges()`
- Routing logic based on state fields (user level)
- Branching paths that merge back together
- Using Pydantic models for structured LLM outputs (ScaffoldingConfig)

### Phase 4: Checkpointing (Week 2-3)
**Learn**: Persistence, conversation memory

```python
from langgraph.checkpoint.sqlite import SqliteSaver

def build_graph():
    graph = StateGraph(ConversationState)
    # ... nodes and edges ...

    # Add checkpointing for conversation persistence
    checkpointer = SqliteSaver.from_conn_string("data/hermano.db")
    return graph.compile(checkpointer=checkpointer)

# Usage with thread_id for conversation continuity
result = await graph.ainvoke(
    {"messages": [HumanMessage(content="Hola")]},
    config={"configurable": {"thread_id": "user-session-123"}}
)
```

**What you'll learn**:
- SqliteSaver checkpointer
- Thread IDs for conversation isolation
- Resuming conversations across requests

### Phase 5: Complex State (Week 3)
**Learn**: Rich state management, nested structures

```python
class ScaffoldingConfig(TypedDict):
    show_word_bank: bool
    show_translation: bool
    show_hints: bool
    hint_text: Optional[str]
    word_bank: list[str]

class GrammarFeedback(TypedDict):
    original: str
    correction: str
    explanation: str
    rule: str

class ConversationState(TypedDict):
    # Core
    messages: Annotated[list[BaseMessage], add_messages]
    level: str
    language: str

    # Scaffolding (A0-A1)
    scaffolding: ScaffoldingConfig

    # Analysis results
    grammar_feedback: list[GrammarFeedback]
    new_vocabulary: list[str]

    # Session tracking
    words_this_session: list[str]
    corrections_count: int

    # Level adjustment signals
    should_adjust_level: bool
    adjustment_direction: Optional[str]  # "up" | "down"
```

**What you'll learn**:
- Complex nested state
- Multiple state fields updated by different nodes
- State as the single source of truth

### Phase 6: Micro-Lessons (Week 4) - IMPLEMENTED
**Learn**: Structured content delivery, YAML-based data, service patterns

**Status**: This phase is complete. The application now includes a full micro-lessons system with structured content, interactive exercises, and lesson-to-chat handoff.

**Key Components**:

1. **Lesson Models** (`src/lessons/models.py`):
```python
class LessonLevel(str, Enum):
    A0 = "A0"  # Absolute beginner
    A1 = "A1"  # Beginner
    A2 = "A2"  # Elementary
    B1 = "B1"  # Intermediate

class LessonStepType(str, Enum):
    INSTRUCTION = "instruction"  # Text explanation
    VOCABULARY = "vocabulary"    # Word list with translations
    EXAMPLE = "example"          # Example sentence/phrase
    TIP = "tip"                  # Cultural note or learning tip
    PRACTICE = "practice"        # Exercise reference

class ExerciseType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    FILL_BLANK = "fill_blank"
    TRANSLATE = "translate"
```

2. **Lesson Service** (`src/lessons/service.py`):
```python
class LessonService:
    """Service for loading and managing lessons from YAML files."""

    def get_lesson(self, lesson_id: str) -> Lesson | None
    def get_lessons(self, language: str, level: LessonLevel) -> list[Lesson]
    def get_lesson_vocabulary(self, lesson_id: str) -> list[dict]
    def get_next_recommended(self, user_id: str, ...) -> Lesson | None
```

3. **YAML Lesson Format** (`data/lessons/es/A0/greetings-001.yaml`):
```yaml
id: greetings-001
title: Basic Greetings
language: es
level: A0
category: greetings
icon: "👋"

steps:
  - type: instruction
    content: "Welcome to your first Spanish lesson!"
    order: 1
  - type: vocabulary
    vocabulary:
      - word: hola
        translation: hello
    order: 2
  - type: practice
    exercise_id: "ex-mc-greet-001"
    order: 3

exercises:
  - id: ex-mc-greet-001
    type: multiple_choice
    question: "How do you say 'hello' in Spanish?"
    options: [Hola, Adios, Gracias]
    correct_index: 0
```

**What you learned**:
- YAML-based content loading with validation
- Pydantic models for structured lesson data
- Service layer pattern for data access
- Step-based content navigation with HTMX
- Exercise answer validation with multiple types
- Lesson-to-chat handoff for practice reinforcement

### Phase 7: Progress Tracking (Week 5) - IMPLEMENTED
**Learn**: Dashboard aggregation, repository pattern, service layer composition

**Status**: This phase is complete. The application now includes comprehensive progress tracking with dashboard statistics, vocabulary management, and chart data generation.

**Key Components**:

1. **ProgressService** (`src/services/progress.py`):
```python
class ProgressService:
    """Aggregates data from repositories into dashboard-ready structures."""

    def __init__(self, user_id: str, client: SupabaseClient | None = None) -> None:
        self._vocab_repo = VocabularyRepository(user_id, client=client)
        self._session_repo = LearningSessionRepository(user_id, client=client)
        self._lesson_repo = LessonProgressRepository(user_id, client=client)

    def get_dashboard_stats(self, language: str = "es") -> DashboardStats:
        """Aggregate stats: total_words, sessions, lessons, streak, accuracy."""

    def get_chart_data(self, language: str = "es", days: int = 30) -> ChartData:
        """Generate vocab_growth and accuracy_trend time series."""

    def record_chat_activity(self, language: str, level: str, new_vocab: list) -> None:
        """Fire-and-forget vocabulary capture from chat interactions."""
```

2. **Dashboard Stats** aggregation from 3 repositories:
```python
@dataclass(frozen=True)
class DashboardStats:
    total_words: int          # From VocabularyRepository
    total_sessions: int       # From LearningSessionRepository
    lessons_completed: int    # From LessonProgressRepository
    current_streak: int       # Computed from session dates
    accuracy_rate: float      # times_correct / times_seen
    words_learned_today: int  # Filtered by date
    messages_today: int       # Aggregated from sessions
```

3. **Chart Data** generation:
```python
@dataclass(frozen=True)
class ChartData:
    vocab_growth: list[VocabGrowthPoint]     # Cumulative word count over time
    accuracy_trend: list[AccuracyPoint]      # Accuracy percentage over time
```

**What you learned**:
- Service layer pattern for aggregating multiple repositories
- Dataclass-based DTOs for dashboard data structures
- Streak calculation algorithm (consecutive days from today)
- Fire-and-forget logging pattern for non-critical persistence

### Phase 8: Guest Sessions (Week 5-6) - IMPLEMENTED
**Learn**: Anonymous user support, data migration, RLS bypass patterns

**Status**: This phase is complete. The application now supports anonymous guest usage with progress tracking, and seamlessly merges guest data when users sign up or log in.

**Key Components**:

1. **Session ID Cookie Mechanism**:
```python
# Guest identification via session_id cookie (UUID)
# Set on first visit, used as user_id for database operations
session_id: Annotated[str | None, Cookie()] = None
```

2. **Admin Client for RLS Bypass** (`src/api/supabase_client.py`):
```python
def get_supabase_admin() -> SupabaseClient:
    """Service role client that bypasses Row Level Security.

    Required for guest data access since session_id != auth.uid().
    """
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
```

3. **Identity Resolution Pattern** (`src/api/routes/progress.py`):
```python
def _resolve_identity(user, session_id) -> tuple[str | None, SupabaseClient | None]:
    """Resolve effective user ID and client for auth or guest users.

    Returns:
        (user_id, None) for authenticated users (uses anon client with RLS)
        (session_id, admin_client) for guests (bypasses RLS)
        (None, None) when neither available
    """
    if user:
        return user.id, None
    if session_id:
        return session_id, get_supabase_admin()
    return None, None
```

4. **GuestDataMergeService** (`src/services/merge.py`):
```python
class GuestDataMergeService:
    """Merges guest session data into authenticated account on signup/login."""

    def merge_all(self) -> dict[str, int]:
        """Transfer vocabulary, sessions, and lessons from guest to auth user."""
        return {
            "vocabulary": self._merge_vocabulary(),   # Sum counters, keep earliest
            "sessions": self._merge_sessions(),       # Transfer all
            "lessons": self._merge_lessons(),         # Keep higher score
        }
```

5. **Merge Integration in Auth Routes** (`src/api/routes/auth.py`):
```python
# On signup/login success:
guest_session_id = request.cookies.get("session_id")
if guest_session_id and auth_response.user:
    merge_service = GuestDataMergeService(guest_session_id, auth_response.user.id)
    merge_service.merge_all()
    response.delete_cookie(key="session_id")  # Clear guest cookie
```

**What you learned**:
- Anonymous user support with cookie-based session identification
- Row Level Security bypass patterns using service role client
- Data migration strategies (merge vs transfer) for different entity types
- Fire-and-forget merge operations that don't block authentication flow

### Phase 9: Subgraphs (Future)
**Learn**: Graph composition, reusability

```python
# Lesson subgraph - reusable for different lesson types
def build_lesson_graph():
    graph = StateGraph(LessonState)
    graph.add_node("present", present_content_node)
    graph.add_node("practice", practice_node)
    graph.add_node("evaluate", evaluate_node)
    # ...
    return graph.compile()

# Main graph can invoke lesson subgraph
def build_main_graph():
    graph = StateGraph(ConversationState)
    graph.add_node("chat", chat_subgraph)
    graph.add_node("lesson", build_lesson_graph())  # Subgraph as node
    # ...
```

---

## State Definition (Full)

```python
from typing import TypedDict, Annotated, Optional
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

# === Pydantic Models for Structured LLM Output ===

class ScaffoldingConfig(BaseModel):
    """Scaffolding UI configuration for beginners (A0-A1 levels)

    Used with LLM structured output to generate contextual learning aids
    based on the AI tutor's last response.
    """
    enabled: bool = Field(
        default=False,
        description="Whether scaffolding is active for this response"
    )
    word_bank: list[str] = Field(
        default_factory=list,
        description="4-6 contextual vocabulary words to help form a response"
    )
    hint_text: str | None = Field(
        default=None,
        description="A simple hint (1 sentence) to guide the learner's response"
    )
    sentence_starter: str | None = Field(
        default=None,
        description="Optional sentence beginning to reduce blank-page anxiety"
    )
    auto_expand: bool = Field(
        default=False,
        description="Whether to auto-expand scaffolding UI (True for A0)"
    )

# === TypedDict Models for State ===

class GrammarFeedback(TypedDict):
    """A single grammar correction"""
    original: str
    correction: str
    explanation: str
    rule_id: str
    severity: str  # minor, moderate, significant

class VocabWord(TypedDict):
    """A vocabulary item encountered in conversation"""
    word: str
    translation: str
    part_of_speech: str
    context: str  # The sentence it appeared in

class ConversationState(TypedDict):
    """Main LangGraph state for Habla Hermano"""

    # === Core Conversation ===
    messages: Annotated[list[BaseMessage], add_messages]

    # === Language Settings ===
    language: str           # "es" | "de"
    level: str              # "A0" | "A1" | "A2" | "B1"

    # === Scaffolding (populated for A0-A1 via conditional routing) ===
    scaffolding: ScaffoldingConfig  # Pydantic model for structured LLM output

    # === Analysis Results ===
    grammar_feedback: list[GrammarFeedback]
    new_vocabulary: list[VocabWord]

    # === Session Tracking ===
    session_id: str
    message_count: int
    words_learned_this_session: list[str]

    # === Level Adjustment ===
    consecutive_correct: int
    consecutive_errors: int
    should_suggest_level_change: bool
    suggested_level: Optional[str]
```

---

## Graph Visualization

### Current Graph (Phases 1-3 Implemented)

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   respond   │  ← Generate AI response
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │     needs_scaffold()    │
              │   checks state["level"] │
              ▼                         ▼
         A0 or A1                  A2 or B1
              │                         │
    ┌─────────▼─────────┐               │
    │     scaffold      │               │
    │  - word_bank      │               │
    │  - hint_text      │               │
    │  - sentence_start │               │
    └─────────┬─────────┘               │
              │                         │
              └──────────┬──────────────┘
                         │
                  ┌──────▼──────┐
                  │   analyze   │  ← Grammar + vocab extraction
                  └──────┬──────┘
                         │
                  ┌──────▼──────┐
                  │     END     │
                  └─────────────┘
```

**Conditional Routing Logic**:

The `needs_scaffold()` function determines the graph path based on the learner's proficiency level:

```python
def needs_scaffold(state: ConversationState) -> str:
    """Route beginners to scaffolding, others directly to analysis"""
    if state["level"] in ["A0", "A1"]:
        return "scaffold"
    return "analyze"
```

**Flow Paths**:
- **A0/A1 learners**: START -> respond -> scaffold -> analyze -> END
- **A2/B1 learners**: START -> respond -> analyze -> END

### Future Graph (Phase 4+ with Feedback Node)

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   respond   │  ← Generate AI response
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │ needs_scaffold()?       │
              ▼                         ▼
    ┌─────────────────┐       ┌─────────────────┐
    │    scaffold     │       │     (skip)      │
    │ (A0-A1 only)    │       │                 │
    └────────┬────────┘       └────────┬────────┘
             │                         │
             └──────────┬──────────────┘
                        │
                 ┌──────▼──────┐
                 │   analyze   │  ← Grammar + vocab extraction
                 └──────┬──────┘
                        │
              ┌─────────┴─────────┐
              │ has_feedback?     │
              ▼                   ▼
    ┌─────────────────┐    ┌─────────────────┐
    │    feedback     │    │     (skip)      │
    └────────┬────────┘    └────────┬────────┘
             │                      │
             └──────────┬───────────┘
                        │
                 ┌──────▼──────┐
                 │     END     │
                 └─────────────┘
```

---

## Micro-Lessons Data Flow (Phase 6)

The micro-lessons system operates independently from the LangGraph conversation graph, providing structured learning content that complements free-form chat practice.

### Lesson Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        LESSONS PAGE                              │
│  /lessons/                                                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │ Greetings   │ │ Numbers     │ │ Colors      │                │
│  │ 👋 A0       │ │ 🔢 A0       │ │ 🎨 A0       │                │
│  └──────┬──────┘ └─────────────┘ └─────────────┘                │
└─────────┼───────────────────────────────────────────────────────┘
          │ Click "Play"
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LESSON PLAYER                               │
│  /lessons/{id}/play                                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Progress: [████████░░░░░░░░░░░░] Step 3 of 7              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │               STEP CONTENT (HTMX Swap)                     │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │ instruction │ vocabulary │ example │ tip │ practice  │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌──────────┐                                    ┌──────────┐   │
│  │ Previous │ ◄──── HTMX POST ────► │   Next   │           │   │
│  └──────────┘                                    └──────────┘   │
└─────────────────────────────────────────────────────────────────┘
          │ Final Step: "Complete Lesson"
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    COMPLETION VIEW                               │
│  🎉 Lesson Complete!                                             │
│  Score: 100%  |  Words Learned: 6                               │
│                                                                  │
│  ┌────────────────────┐  ┌────────────────────┐                 │
│  │ Practice with      │  │ More Lessons       │                 │
│  │ Hermano           │  │                    │                 │
│  └─────────┬──────────┘  └────────────────────┘                 │
└────────────┼────────────────────────────────────────────────────┘
             │ Handoff (HX-Redirect)
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        CHAT PAGE                                 │
│  /chat?lesson={id}&topic={category}                              │
│  Chat with Hermano using vocabulary from the lesson              │
└─────────────────────────────────────────────────────────────────┘
```

### Step Types and Templates

| Step Type | Template Rendering | Purpose |
|-----------|-------------------|---------|
| `instruction` | Text block with prose styling | Introduce concepts |
| `vocabulary` | Grid of word/translation cards | Present new words |
| `example` | Highlighted target text + translation | Show usage in context |
| `tip` | Yellow info box with lightbulb icon | Cultural notes, learning tips |
| `practice` | Dynamic exercise form (HTMX load) | Interactive practice |

### Exercise Types and Validation

| Exercise Type | Input | Validation Logic |
|--------------|-------|------------------|
| `multiple_choice` | Radio button index | `selected_index == correct_index` |
| `fill_blank` | Text input | Case-insensitive match with alternatives |
| `translate` | Text input | Case-insensitive match with alternatives |

### Data Loading Pipeline

```
YAML Files (data/lessons/)
        │
        ▼
LessonService._load_all_lessons()
        │
        ├── Parse YAML with yaml.safe_load()
        ├── Validate with Pydantic models
        └── Cache in _lessons dict
        │
        ▼
Dependency Injection (LessonServiceDep)
        │
        ▼
API Routes (src/api/routes/lessons.py)
```

---

## Progress Data Flow (Phase 7-8)

The progress system aggregates data from three repositories through the ProgressService, supporting both authenticated and guest users.

### Progress Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        PROGRESS PAGE REQUEST                             │
│  GET /progress/                                                          │
│  Cookies: sb-access-token (auth) OR session_id (guest)                  │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       IDENTITY RESOLUTION                                │
│  _resolve_identity(user, session_id)                                    │
│  ┌─────────────────┐         ┌─────────────────┐                        │
│  │ Authenticated?  │───Yes──►│ user_id = JWT   │                        │
│  │                 │         │ client = None   │                        │
│  └────────┬────────┘         │ (uses anon+RLS) │                        │
│           │ No               └─────────────────┘                        │
│           ▼                                                             │
│  ┌─────────────────┐         ┌─────────────────┐                        │
│  │ Has session_id? │───Yes──►│ user_id = UUID  │                        │
│  │                 │         │ client = admin  │                        │
│  └────────┬────────┘         │ (bypasses RLS)  │                        │
│           │ No               └─────────────────┘                        │
│           ▼                                                             │
│  ┌─────────────────┐                                                    │
│  │ Return empty    │                                                    │
│  │ stats (new user)│                                                    │
│  └─────────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        PROGRESS SERVICE                                  │
│  ProgressService(user_id, client)                                       │
│                                                                         │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐            │
│  │ VocabularyRepo │  │ SessionRepo    │  │ LessonRepo     │            │
│  │ .get_all()     │  │ .get_all()     │  │ .get_completed │            │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘            │
│          │                   │                   │                      │
│          └───────────────────┼───────────────────┘                      │
│                              ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    AGGREGATION LAYER                             │   │
│  │  DashboardStats:                                                 │   │
│  │  - total_words = len(vocab)                                      │   │
│  │  - total_sessions = len(sessions)                                │   │
│  │  - lessons_completed = len(completed)                            │   │
│  │  - current_streak = _calculate_streak(sessions)                  │   │
│  │  - accuracy_rate = sum(correct) / sum(seen) * 100                │   │
│  │  - words_learned_today = filter by date                          │   │
│  │  - messages_today = sum(session.messages) by date                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        TEMPLATE RENDERING                                │
│  progress.html                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Stats Cards: Words | Sessions | Streak | Lessons                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Vocabulary List (HTMX partial load from /progress/vocabulary)    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Charts: vocab_growth (line) | accuracy_trend (line)              │   │
│  │ Data loaded via /progress/chart-data as JSON                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Guest Data Merge Flow

When a guest user signs up or logs in, their progress data is transferred to their authenticated account.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        LOGIN/SIGNUP SUCCESS                              │
│  auth_response.session != None                                          │
│  Cookies: session_id (guest UUID) exists                                │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    GUEST DATA MERGE SERVICE                              │
│  GuestDataMergeService(guest_session_id, authenticated_user_id)         │
│  Uses admin client (service role) to bypass RLS                         │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ _merge_vocabulary()                                              │   │
│  │ - Query guest vocabulary entries                                 │   │
│  │ - For each entry:                                                │   │
│  │   - If auth user has same word+language:                         │   │
│  │     - Sum times_seen and times_correct                           │   │
│  │     - Keep earliest first_seen_at                                │   │
│  │     - Delete guest entry                                         │   │
│  │   - Else: Update user_id to auth user                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ _merge_sessions()                                                │   │
│  │ - Transfer all guest sessions (no dedup needed)                  │   │
│  │ - Bulk update: SET user_id = auth_id WHERE user_id = guest_id    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ _merge_lessons()                                                 │   │
│  │ - For duplicate lessons: keep higher score                       │   │
│  │ - Otherwise: transfer ownership                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Returns: {"vocabulary": N, "sessions": N, "lessons": N}                │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        CLEANUP                                           │
│  response.delete_cookie(key="session_id")                               │
│  Guest continues as authenticated user with all their progress          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Chat Vocabulary Capture

When users chat with Hermano, new vocabulary extracted by the analyze node is persisted via `record_chat_activity()`.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CHAT INTERACTION                                  │
│  POST /chat with message                                                │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        LANGGRAPH EXECUTION                               │
│  respond → scaffold (A0/A1) → analyze → END                             │
│                                  │                                       │
│                                  ▼                                       │
│  Analyze node extracts: new_vocabulary: list[VocabWord]                 │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        PROGRESS SERVICE                                  │
│  ProgressService.record_chat_activity(language, level, new_vocab)       │
│                                                                         │
│  Fire-and-forget (logs errors, never blocks response):                  │
│  1. For each word in new_vocab:                                         │
│     - VocabularyRepository.upsert(word, translation, language)          │
│     - Increments times_seen if exists, creates if not                   │
│  2. Ensure active session exists:                                       │
│     - LearningSessionRepository.get_active() or .create()               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Node Implementations

### Respond Node

```python
async def respond_node(state: ConversationState) -> dict:
    """Generate AI response appropriate to user's level"""

    prompt = get_prompt_for_level(state["language"], state["level"])

    response = await llm.ainvoke([
        SystemMessage(content=prompt),
        *state["messages"]
    ])

    return {"messages": [response]}
```

### Scaffold Node (Phase 3)

The scaffold node generates contextual learning aids for beginner learners (A0/A1). It uses an LLM to analyze the AI's last response and create relevant word banks, hints, and sentence starters.

**ScaffoldingConfig Pydantic Model**:

```python
from pydantic import BaseModel, Field

class ScaffoldingConfig(BaseModel):
    """Configuration for scaffolding UI elements displayed to beginner learners"""

    enabled: bool = Field(
        default=False,
        description="Whether scaffolding is active for this response"
    )
    word_bank: list[str] = Field(
        default_factory=list,
        description="4-6 contextual vocabulary words to help form a response"
    )
    hint_text: str | None = Field(
        default=None,
        description="A simple hint (1 sentence) to guide the learner's response"
    )
    sentence_starter: str | None = Field(
        default=None,
        description="Optional sentence beginning to reduce blank-page anxiety"
    )
    auto_expand: bool = Field(
        default=False,
        description="Whether to auto-expand scaffolding UI (True for A0)"
    )
```

**Node Implementation**:

```python
async def scaffold_node(state: ConversationState) -> dict:
    """Generate scaffolding for A0-A1 learners based on AI's last response"""

    # Get the AI's response to analyze for context
    ai_response = state["messages"][-1].content

    # Generate contextual scaffolding using LLM
    scaffolding_prompt = f"""
    The AI tutor just said: "{ai_response}"
    User level: {state["level"]}
    Language: {state["language"]}

    Generate scaffolding to help the beginner respond:
    1. A simple hint (1 sentence) that guides without giving the answer
    2. 4-6 relevant vocabulary words for a word bank
    3. A sentence starter if appropriate (helps reduce blank-page anxiety)

    Return JSON matching this structure:
    {{
        "hint_text": "...",
        "word_bank": ["word1", "word2", ...],
        "sentence_starter": "..." or null
    }}
    """

    # Use structured output with Pydantic model
    result = await llm.with_structured_output(ScaffoldingConfig).ainvoke(
        scaffolding_prompt
    )

    return {
        "scaffolding": ScaffoldingConfig(
            enabled=True,
            word_bank=result.word_bank,
            hint_text=result.hint_text,
            sentence_starter=result.sentence_starter,
            auto_expand=state["level"] == "A0"  # Auto-show for absolute beginners
        )
    }
```

**Key Design Decisions**:

1. **LLM-generated context**: The scaffold node reads the AI's last response to generate relevant vocabulary and hints, making scaffolding contextually appropriate rather than generic.

2. **Level-based auto-expand**: A0 learners see scaffolding expanded by default (`auto_expand=True`), while A1 learners can click to expand.

3. **Pydantic structured output**: Using `with_structured_output()` ensures type-safe responses from the LLM and eliminates JSON parsing errors.

### Analyze Node

```python
async def analyze_node(state: ConversationState) -> dict:
    """Analyze user's message for grammar errors and new vocabulary"""

    # Get the user's last message (before AI response)
    user_message = state["messages"][-2].content

    analysis_prompt = f"""
    Analyze this {state["language"]} message from a {state["level"]} learner:
    "{user_message}"

    Return JSON:
    {{
        "grammar_errors": [
            {{
                "original": "incorrect phrase",
                "correction": "correct phrase",
                "explanation": "brief friendly explanation",
                "rule_id": "rule_name",
                "severity": "minor|moderate|significant"
            }}
        ],
        "new_vocabulary": [
            {{
                "word": "word",
                "translation": "english",
                "part_of_speech": "noun|verb|adj|etc"
            }}
        ]
    }}

    Only flag errors appropriate for {state["level"]} level.
    Only include vocabulary that's notable for their level.
    """

    result = await llm.ainvoke(analysis_prompt)
    analysis = parse_json(result.content)

    return {
        "grammar_feedback": analysis.get("grammar_errors", []),
        "new_vocabulary": analysis.get("new_vocabulary", [])
    }
```

---

## Prompts by Level

The prompts define Hermano's personality and behavior at each CEFR level. They use the LANGUAGE_ADAPTER pattern for language switching.

```python
LEVEL_PROMPTS = {
    "A0": """
You are "Hermano" - a friendly, laid-back language buddy helping absolute beginners learn {language_name}.

PERSONALITY: Think supportive big brother who's been through this journey. You're patient, never condescending, and genuinely excited when they try anything.

LANGUAGE MIX: Speak 80% English, 20% {language_name}.
- Use {language_name} for greetings, simple words, and the phrase you want them to learn
- Use English for everything else

BEHAVIOR:
- Keep it VERY simple: one concept at a time
- Celebrate every attempt: "Nice!", "You got this!", "That's the spirit!"
- If they struggle, give the answer and move on positively: "No worries, it's like this..."
- Ask simple yes/no or single-word questions
- Share relatable moments: "This one tripped me up at first too"

TONE: Warm, casual, encouraging. Like texting a friend who speaks {language_name}.

TOPICS: Greetings, name, how are you, numbers 1-10, colors, yes/no

Example exchange:
You: "Hey! Let's start with the basics. '{hello}' means 'hello' - pretty easy, right? Give it a shot!"
User: "{hello_lower}"
You: "Nice! See, you're already speaking {language_name}! Now here's a fun one: '{my_name_is}' means 'My name is'..."
""",

    "A1": """
You are "Hermano" - a chill, supportive language buddy for {language_name} beginners.

PERSONALITY: You're like that friend who spent a year abroad and loves sharing what they learned. Relaxed, encouraging, and you make mistakes feel like no big deal.

LANGUAGE MIX: Speak 50% {language_name}, 50% English.

BEHAVIOR:
- Use present tense only
- Short sentences (5-8 words max)
- If they make mistakes, respond naturally (model correct form) without calling them out
- Offer translation casually if they seem stuck

TONE: Relaxed, friendly, patient. Never lecture-y.
""",

    "A2": """
You are "Hermano" - a supportive language partner for elementary {language_name} learners.

PERSONALITY: You've been where they are and you know they're ready for more. You challenge them just enough while keeping things fun.

LANGUAGE MIX: Speak 80% {language_name}, 20% English.

BEHAVIOR:
- Introduce past tense naturally
- Ask follow-up questions to keep conversation flowing
- Share expressions: "Here's one locals actually use..."

TONE: Conversational, encouraging growth, casual but substantive.
""",

    "B1": """
You are "Hermano" - a natural conversation partner for intermediate {language_name} learners.

PERSONALITY: At this point, you're basically having real conversations. You treat them as a peer who's just polishing their skills.

LANGUAGE MIX: Speak 95%+ {language_name}.

BEHAVIOR:
- Have natural conversations on any topic
- Drop in idiomatic expressions and explain them in {language_name}
- Corrections are gentle asides: "By the way, you could also say..."

TONE: Natural, peer-to-peer, warm but authentic. Like catching up with a bilingual friend.
"""
}
```

---

## API Endpoints

### Chat

```python
@router.post("/chat")
async def send_message(
    message: str = Form(...),
    request: Request,
    graph: CompiledGraph = Depends(get_graph),
):
    """Send a message, get AI response with scaffolding/feedback"""

    thread_id = get_or_create_thread_id(request)

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=message)]},
        config={"configurable": {"thread_id": thread_id}}
    )

    return templates.TemplateResponse(
        "partials/message.html",
        {
            "request": request,
            "ai_message": result["messages"][-1].content,
            "scaffolding": result.get("scaffolding", {}),
            "feedback": result.get("grammar_feedback", []),
            "new_vocab": result.get("new_vocabulary", [])
        }
    )
```

### Level Selection

```python
@router.post("/settings/level")
async def set_level(
    level: str = Form(...),
    request: Request,
):
    """Update user's CEFR level"""
    # Store in session/cookie
    # Reset conversation thread for fresh start at new level
    ...
```

### Lessons (Phase 6)

The lessons module provides a complete API for structured micro-lessons with step navigation, exercises, and progress tracking.

**Lesson List**:
```python
@router.get("/")
async def get_lessons_page(
    language: str | None = None,
    level: str | None = None,
) -> HTMLResponse:
    """Render lessons catalog with filtering by language and level."""
```

**Lesson Player**:
```python
@router.get("/{lesson_id}/play")
async def get_lesson_player(lesson_id: str) -> HTMLResponse:
    """Render interactive lesson player with step navigation."""
```

**Step Navigation**:
```python
@router.get("/{lesson_id}/step/{step_index}")
async def get_lesson_step(lesson_id: str, step_index: int) -> HTMLResponse:
    """Get specific step content as partial HTML for HTMX navigation."""

@router.post("/{lesson_id}/step/next")
async def next_lesson_step(lesson_id: str, current_step: int) -> HTMLResponse:
    """Navigate to next step."""

@router.post("/{lesson_id}/step/prev")
async def previous_lesson_step(lesson_id: str, current_step: int) -> HTMLResponse:
    """Navigate to previous step."""
```

**Exercise Handling**:
```python
@router.get("/{lesson_id}/exercise/{exercise_id}")
async def get_exercise(lesson_id: str, exercise_id: str) -> HTMLResponse:
    """Render exercise form based on type (multiple choice, fill blank, translate)."""

@router.post("/{lesson_id}/exercise/{exercise_id}/submit")
async def submit_exercise(lesson_id: str, exercise_id: str, answer: str) -> HTMLResponse:
    """Validate answer and return feedback HTML."""
```

**Lesson Completion and Handoff**:
```python
@router.post("/{lesson_id}/complete")
async def complete_lesson(lesson_id: str, score: int) -> HTMLResponse:
    """Mark lesson complete and show celebration view."""

@router.post("/{lesson_id}/handoff")
async def handoff_to_chat(lesson_id: str) -> Response:
    """Redirect to chat with lesson context for practice."""
```

### Progress (Phase 7-8)

The progress module provides endpoints for dashboard statistics, vocabulary management, and chart data. All endpoints support both authenticated and guest users.

**Dashboard Page**:
```python
@router.get("/")
async def get_progress_page(
    user: OptionalUserDep,
    session_id: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """Render progress overview with stats from ProgressService."""
```

**Vocabulary Management**:
```python
@router.get("/vocabulary")
async def get_vocabulary(
    user: OptionalUserDep,
    session_id: Annotated[str | None, Cookie()] = None,
    language: str = "es",
) -> HTMLResponse:
    """Render vocabulary list partial for HTMX loading."""

@router.delete("/vocabulary/{word_id}")
async def remove_vocabulary_word(
    user: OptionalUserDep,
    word_id: int,
    session_id: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """Remove word from vocabulary (returns empty for HTMX swap)."""
```

**Statistics and Charts**:
```python
@router.get("/stats")
async def get_stats(
    user: OptionalUserDep,
    session_id: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """Render stats summary partial with DashboardStats."""

@router.get("/chart-data")
async def get_chart_data(
    user: OptionalUserDep,
    session_id: Annotated[str | None, Cookie()] = None,
    language: str = "es",
    days: int = 30,
) -> JSONResponse:
    """Return vocab_growth and accuracy_trend as JSON for charts."""
```

---

## Database Schema (Supabase PostgreSQL)

The application uses Supabase PostgreSQL with Row Level Security (RLS) policies. All tables include a `user_id` column that references either an authenticated user's UUID or a guest session UUID.

```sql
-- User profiles (auto-created via database trigger on auth.users insert)
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id),
    display_name TEXT,
    preferred_language TEXT DEFAULT 'es',
    current_level TEXT DEFAULT 'A1',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vocabulary learned across all sessions
CREATE TABLE vocabulary (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,  -- auth.users UUID or guest session UUID
    word TEXT NOT NULL,
    translation TEXT NOT NULL,
    language TEXT NOT NULL,  -- 'es', 'de', 'fr'
    part_of_speech TEXT,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    times_seen INTEGER DEFAULT 1,
    times_correct INTEGER DEFAULT 0,  -- For accuracy tracking
    UNIQUE(user_id, word, language)
);

-- Learning session statistics
CREATE TABLE learning_sessions (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    language TEXT NOT NULL,
    level TEXT NOT NULL,  -- A0, A1, A2, B1
    messages_count INTEGER DEFAULT 0,
    words_learned INTEGER DEFAULT 0
);

-- Lesson completion tracking
CREATE TABLE lesson_progress (
    user_id UUID NOT NULL,
    lesson_id TEXT NOT NULL,
    completed_at TIMESTAMPTZ,
    score INTEGER,  -- 0-100 percentage
    PRIMARY KEY (user_id, lesson_id)
);

-- RLS Policies (example for vocabulary table)
ALTER TABLE vocabulary ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own vocabulary"
    ON vocabulary FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own vocabulary"
    ON vocabulary FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own vocabulary"
    ON vocabulary FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own vocabulary"
    ON vocabulary FOR DELETE
    USING (auth.uid() = user_id);
```

**RLS Bypass for Guest Users**: Guest users store data using their session UUID as `user_id`. Since this doesn't match `auth.uid()`, the service role client (admin) is used to bypass RLS for guest data access. On signup/login, the `GuestDataMergeService` transfers guest data to the authenticated user's account.

---

## Development Setup

### Makefile

```makefile
.PHONY: install dev test lint clean

install:
	pip install -e ".[dev]"

dev:
	uvicorn src.api.main:app --reload --port 8000

dev-css:
	npx tailwindcss -i ./src/static/css/input.css -o ./src/static/css/output.css --watch

test:
	pytest tests/ -v

lint:
	ruff check src/
	ruff format src/

db-init:
	python -c "from src.db.models import init_db; init_db()"

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
```

### pyproject.toml

```toml
[project]
name = "habla-hermano"
version = "0.1.0"
description = "AI language tutor: A0 to B1"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.6",
    "sqlalchemy>=2.0.0",
    "aiosqlite>=0.19.0",
    "langchain>=0.1.0",
    "langchain-anthropic>=0.1.0",
    "langgraph>=0.0.30",
    "langgraph-checkpoint>=1.0.0",
    "pydantic-settings>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.1.0",
    "httpx>=0.26.0",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

## Implementation Order

### Week 1: Foundation + Phase 1-2 LangGraph
1. Project setup (FastAPI, templates, static files)
2. Basic LangGraph with respond node only
3. Simple chat UI with HTMX
4. Add analyze node for grammar feedback
5. Level selection (A0/A1/A2/B1) with different prompts

### Week 2: Scaffolding + Phase 3-4 LangGraph
1. Scaffold node with conditional routing
2. Word bank and hint UI components
3. Checkpointing for conversation persistence
4. Vocabulary tracking and display

### Week 3: Authentication + Persistence (Phase 4-5)
1. PostgreSQL checkpointing with Supabase
2. Supabase Auth integration
3. JWT cookie authentication
4. Multi-user conversation isolation

### Week 4: Micro-Lessons (Phase 6) - COMPLETED
1. Lesson data models (Pydantic: Lesson, Step, Exercise, Progress)
2. YAML content format and 5 Spanish A0 lessons
3. LessonService for loading and filtering
4. Lessons API routes (list, play, steps, exercises, complete)
5. HTMX-powered lesson player with step navigation
6. Exercise templates (multiple choice, fill blank, translate)
7. Lesson completion and chat handoff
8. 918+ tests with comprehensive coverage

### Week 5: Progress Tracking (Phase 7) - COMPLETED
1. Repository pattern for vocabulary, sessions, and lesson progress
2. ProgressService for dashboard aggregation
3. DashboardStats and ChartData dataclasses
4. Streak calculation algorithm
5. Progress API endpoints (page, vocabulary, stats, chart-data)
6. Vocabulary capture from chat via record_chat_activity()
7. Progress page template with HTMX partial loading

### Week 5-6: Guest Sessions (Phase 8) - COMPLETED
1. Session ID cookie mechanism for anonymous users
2. Admin Supabase client for RLS bypass
3. Identity resolution pattern in progress routes
4. GuestDataMergeService for data transfer on auth
5. Merge integration in signup/login routes
6. Merge strategies: sum counters, transfer sessions, keep higher score

### Week 7+: Iterate
1. Test with real beginners
2. Tune scaffolding based on feedback
3. Add more lessons (A1, A2, B1)
4. German/French support (if time)
5. Phase 9: Subgraphs for lesson integration
