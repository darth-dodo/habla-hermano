# HablaAI Technical Architecture

> FastAPI + HTMX + LangGraph for conversational language learning

---

## Current Implementation Status

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Minimal Graph - Basic state, single respond node | Completed |
| **Phase 2** | Analysis Node - Multi-node graphs, sequential edges | Completed |
| **Phase 3** | Conditional Routing - Branching logic, scaffolding | Planned |
| **Phase 4** | Checkpointing - Persistence, conversation memory | Planned |
| **Phase 5** | Complex State - Rich state management | Planned |
| **Phase 6** | Subgraphs - Graph composition, reusability | Planned |

**Test Coverage**: 641 tests (98% coverage) covering agent, API, database, and service modules. E2E testing is documented in [docs/playwright-e2e.md](./playwright-e2e.md).

---

## Learning Goals

This project is intentionally built with **LangGraph** to learn:
- State management with TypedDict and reducers
- Graph routing with conditional edges
- Checkpointing and conversation persistence
- Node composition and reusability

**Approach**: Start with minimal viable graph, add complexity as features demand it.

---

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Backend** | FastAPI | Async support, SSE streaming, Pydantic validation |
| **Frontend** | HTMX + Jinja2 | Server-driven UI, minimal JS, fast iteration |
| **Agent** | LangGraph | Learning goal: stateful conversations, routing, checkpointing |
| **LLM** | Claude API | Superior language understanding, structured outputs |
| **Database** | SQLite + SQLAlchemy | Simple persistence, no server setup |
| **Styling** | Tailwind CSS + CSS Variables | Utility-first, 3-theme system (dark/light/ocean) |

---

## Project Structure

Legend: Implemented files are marked with a checkmark. Files without a checkmark are planned for future phases.

```
habla-ai/
├── src/
│   ├── api/
│   │   ├── __init__.py          # [Implemented]
│   │   ├── main.py              # [Implemented] FastAPI app entry
│   │   ├── config.py            # [Implemented] Settings (Pydantic)
│   │   ├── dependencies.py      # [Implemented] DI for graph, db session
│   │   └── routes/
│   │       ├── __init__.py      # [Implemented]
│   │       ├── chat.py          # [Implemented] POST /chat, conversation endpoints
│   │       ├── lessons.py       # Micro-lesson endpoints
│   │       └── progress.py      # Vocabulary, stats endpoints
│   │
│   ├── agent/
│   │   ├── __init__.py          # [Implemented]
│   │   ├── graph.py             # [Implemented] LangGraph: respond → analyze → END
│   │   ├── state.py             # [Implemented] TypedDict state with GrammarFeedback, VocabWord
│   │   ├── prompts.py           # [Implemented] System prompts by level
│   │   └── nodes/
│   │       ├── __init__.py      # [Implemented]
│   │       ├── respond.py       # [Implemented] Generate AI response
│   │       ├── analyze.py       # [Implemented] Grammar/vocab analysis
│   │       ├── scaffold.py      # Generate scaffolding (hints, word banks)
│   │       └── feedback.py      # Format corrections
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
│   │   └── partials/
│   │       ├── message.html     # [Implemented] Message bubble styling
│   │       ├── message_pair.html # [Implemented] AI response partial (optimistic UI)
│   │       ├── grammar_feedback.html # [Implemented] Collapsible grammar feedback
│   │       ├── scaffold.html    # Word bank, hints UI
│   │       └── vocab_sidebar.html
│   │
│   └── static/
│       ├── css/
│       └── js/
│           └── app.js           # [Implemented] HTMX handlers, optimistic UI, keyboard shortcuts
│
├── tests/
├── data/
│   ├── habla.db
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

### Phase 3: Conditional Routing (Week 2)
**Learn**: Conditional edges, branching logic

```python
def needs_scaffolding(state: ConversationState) -> str:
    """Route based on user level"""
    if state["level"] in ["A0", "A1"]:
        return "scaffold"
    return "respond_only"

def build_graph():
    graph = StateGraph(ConversationState)

    graph.add_node("respond", respond_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("scaffold", scaffold_node)  # NEW

    graph.set_entry_point("respond")

    # Conditional routing based on level
    graph.add_conditional_edges(
        "respond",
        needs_scaffolding,
        {
            "scaffold": "scaffold",
            "respond_only": "analyze"
        }
    )

    graph.add_edge("scaffold", "analyze")
    graph.add_edge("analyze", END)

    return graph.compile()
```

**What you'll learn**:
- Conditional edge functions
- Routing based on state
- Branching and merging paths

### Phase 4: Checkpointing (Week 2-3)
**Learn**: Persistence, conversation memory

```python
from langgraph.checkpoint.sqlite import SqliteSaver

def build_graph():
    graph = StateGraph(ConversationState)
    # ... nodes and edges ...

    # Add checkpointing for conversation persistence
    checkpointer = SqliteSaver.from_conn_string("data/habla.db")
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

class ScaffoldingConfig(TypedDict):
    """Scaffolding UI configuration for beginners"""
    enabled: bool
    show_word_bank: bool
    word_bank: list[str]
    show_hint: bool
    hint_text: Optional[str]
    show_translation: bool
    translation: Optional[str]
    sentence_starter: Optional[str]

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
    """Main LangGraph state for HablaAI"""

    # === Core Conversation ===
    messages: Annotated[list[BaseMessage], add_messages]

    # === Language Settings ===
    language: str           # "es" | "de"
    level: str              # "A0" | "A1" | "A2" | "B1"

    # === Scaffolding (populated for A0-A1) ===
    scaffolding: ScaffoldingConfig

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

### MVP Graph (Phases 1-4)

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
              │ needs_scaffolding?      │
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

### Scaffold Node

```python
async def scaffold_node(state: ConversationState) -> dict:
    """Generate scaffolding for A0-A1 learners"""

    if state["level"] not in ["A0", "A1"]:
        return {"scaffolding": {"enabled": False}}

    # Get the AI's response to analyze
    ai_response = state["messages"][-1].content

    # Generate contextual scaffolding
    scaffolding_prompt = f"""
    The AI just said: "{ai_response}"
    User level: {state["level"]}
    Language: {state["language"]}

    Generate scaffolding to help the user respond:
    1. A simple hint (1 sentence)
    2. 4-6 relevant words for a word bank
    3. A sentence starter if appropriate

    Return JSON:
    {{
        "hint": "...",
        "word_bank": ["word1", "word2", ...],
        "sentence_starter": "..." or null
    }}
    """

    result = await llm.ainvoke(scaffolding_prompt)
    scaffolding_data = parse_json(result.content)

    return {
        "scaffolding": {
            "enabled": True,
            "show_word_bank": True,
            "word_bank": scaffolding_data["word_bank"],
            "show_hint": state["level"] == "A0",  # Auto-show for A0
            "hint_text": scaffolding_data["hint"],
            "sentence_starter": scaffolding_data.get("sentence_starter")
        }
    }
```

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

```python
LEVEL_PROMPTS = {
    "A0": """
You are a friendly Spanish tutor for absolute beginners.

LANGUAGE MIX: Speak 80% English, 20% Spanish.
- Use Spanish for greetings, simple words, and the phrase you want them to learn
- Use English for everything else

BEHAVIOR:
- Keep it VERY simple: one concept at a time
- Celebrate every attempt: "Great job!", "You said your first Spanish word!"
- If they struggle, give the answer and move on positively
- Ask simple yes/no or single-word questions
- Always model the correct Spanish phrase clearly

TOPICS: Greetings, name, how are you, numbers 1-10, colors, yes/no

Example exchange:
You: "¡Hola! That means 'hello' in Spanish! Can you say hola?"
User: "hola"
You: "Perfect! ¡Hola! Now let's learn your name. In Spanish we say 'Me llamo [name]'. Me llamo Ana. What's your name? Try: Me llamo..."
""",

    "A1": """
You are a friendly Spanish conversation partner for beginners.

LANGUAGE MIX: Speak 50% Spanish, 50% English.
- Use Spanish for simple sentences and common phrases
- Use English to explain or when they seem confused

BEHAVIOR:
- Use present tense only
- Short sentences (5-8 words max)
- Common vocabulary only
- If they make mistakes, respond naturally (model correct form) without explicit correction
- Offer translation if they seem stuck: "(That means: ...)"

TOPICS: Daily routine, family, food, hobbies, weather, describing things

GRAMMAR FOCUS: ser/estar basics, present tense, gender agreement
""",

    "A2": """
You are a Spanish conversation partner for elementary learners.

LANGUAGE MIX: Speak 80% Spanish, 20% English.
- Use English only for complex explanations
- Offer translation toggle, don't auto-translate

BEHAVIOR:
- Introduce past tense naturally through questions about yesterday/last week
- Longer sentences OK (8-12 words)
- Ask follow-up questions to extend conversation
- Let small errors slide, only note patterns that repeat

TOPICS: Travel, shopping, describing experiences, making plans, telling stories

GRAMMAR FOCUS: Preterite basics, reflexive verbs, object pronouns
""",

    "B1": """
You are a Spanish conversation partner for intermediate learners.

LANGUAGE MIX: Speak 95%+ Spanish.
- Only use English if explicitly asked or for nuanced grammar explanations

BEHAVIOR:
- Have natural conversations on any topic
- Use idiomatic expressions and explain them in Spanish
- Ask for opinions and reasons
- Discuss hypotheticals and abstract topics
- Corrections are gentle asides, not interruptions

TOPICS: News, opinions, work, relationships, culture, hypotheticals

GRAMMAR FOCUS: Subjunctive, conditionals, advanced past tenses
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
name = "habla-ai"
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
