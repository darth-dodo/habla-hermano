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
| **Phase 6** | Subgraphs - Graph composition, reusability | Planned |

**Test Coverage**: 829+ tests (86%+ coverage) covering agent, API, database, auth, and service modules. E2E testing is documented in [docs/playwright-e2e.md](./playwright-e2e.md).

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
│   │   ├── auth.py              # [Implemented] JWT validation, CurrentUserDep
│   │   ├── session.py           # [Implemented] Thread ID management
│   │   ├── supabase_client.py   # [Implemented] Supabase client singleton
│   │   └── routes/
│   │       ├── __init__.py      # [Implemented]
│   │       ├── chat.py          # [Implemented] POST /chat (protected)
│   │       ├── auth.py          # [Implemented] Login, signup, logout
│   │       ├── lessons.py       # Micro-lesson endpoints
│   │       └── progress.py      # Vocabulary, stats endpoints
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
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── repository.py        # Data access layer
│   │   └── seed.py              # Initial data
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── vocabulary.py        # Vocab extraction logic
│   │   └── levels.py            # Level detection/adjustment
│   │
│   ├── templates/               # [Implemented] All template files
│   │   ├── base.html            # [Implemented] Theme system (dark/light/ocean), CSS variables
│   │   ├── chat.html            # [Implemented] Chat UI with language/level selectors, theme toggle
│   │   ├── lessons.html
│   │   ├── auth/
│   │   │   ├── login.html       # [Implemented] Login page
│   │   │   └── signup.html      # [Implemented] Signup page
│   │   └── partials/
│   │       ├── message.html     # [Implemented] Message bubble styling
│   │       ├── message_pair.html # [Implemented] AI response partial (optimistic UI)
│   │       ├── grammar_feedback.html # [Implemented] Collapsible grammar feedback
│   │       ├── scaffold.html    # [Implemented] Word bank, hints, sentence starters UI
│   │       └── vocab_sidebar.html
│   │
│   └── static/
│       ├── css/
│       └── js/
│           └── app.js           # [Implemented] HTMX handlers, optimistic UI, keyboard shortcuts
│
├── tests/
├── data/
│   ├── hermano.db
│   └── lessons/                 # Lesson content (JSON/YAML)
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

### Phase 6: Subgraphs (Future)
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

---

## Database Schema (Simplified for MVP)

```sql
-- Vocabulary learned across all sessions
CREATE TABLE vocabulary (
    id INTEGER PRIMARY KEY,
    word TEXT NOT NULL,
    translation TEXT NOT NULL,
    language TEXT NOT NULL,  -- 'es' or 'de'
    part_of_speech TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    times_seen INTEGER DEFAULT 1,
    UNIQUE(word, language)
);

-- Session statistics
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    language TEXT NOT NULL,
    level TEXT NOT NULL,
    messages_count INTEGER DEFAULT 0,
    words_learned INTEGER DEFAULT 0
);

-- User settings (single user for MVP)
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Lesson progress
CREATE TABLE lesson_progress (
    lesson_id TEXT PRIMARY KEY,
    completed_at TIMESTAMP,
    score INTEGER  -- Optional: how well they did
);
```

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

### Week 3: Polish + Learning Features
1. Micro-lessons (start with 3-5)
2. Progress view (words learned, sessions)
3. Grammar feedback UI
4. Mobile responsiveness

### Week 4+: Iterate
1. Test with real beginners
2. Tune scaffolding based on feedback
3. Add more lessons
4. German support (if time)
