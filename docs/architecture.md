# HablaAI Technical Architecture

> FastAPI + HTMX + LangGraph architecture for conversational language learning

---

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Backend Framework** | FastAPI | Async support for LLM calls, SSE streaming, Pydantic validation |
| **Frontend** | HTMX + Jinja2 | Server-driven UI, minimal JS, fast iteration |
| **Agent Framework** | LangGraph | Stateful conversations, conditional routing, checkpointing |
| **LLM** | Claude API (Anthropic) | Superior language understanding, structured outputs |
| **Database** | SQLite + SQLAlchemy | Simple persistence, no server setup, good for single-user |
| **Styling** | Tailwind CSS | Utility-first, rapid prototyping |

### Stack Validation

**Why HTMX over React/Vue?**
- Server-driven state eliminates sync complexity with LangGraph
- SSE extension handles streaming responses cleanly
- Matches learning goal: focus on backend patterns, not JS frameworks
- Faster iteration for prototyping

**Why SQLite over PostgreSQL?**
- No server setup required
- Perfect for single-user use case
- Easy to backup (just copy the file)
- SQLAlchemy allows migration to PostgreSQL if needed

---

## Project Structure

```
habla-ai/
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application entry
│   │   ├── config.py               # Settings and configuration
│   │   ├── dependencies.py         # Dependency injection
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── chat.py             # POST /chat, GET /chat/stream
│   │       ├── vocabulary.py       # Vocabulary CRUD endpoints
│   │       ├── session.py          # Session management
│   │       └── settings.py         # User preferences
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── graph.py                # LangGraph definition
│   │   ├── state.py                # TypedDict state definition
│   │   ├── prompts.py              # System prompts per language/level
│   │   ├── nodes/
│   │   │   ├── __init__.py
│   │   │   ├── router.py           # Intent detection and routing
│   │   │   ├── analyzer.py         # Input analysis (grammar, vocab)
│   │   │   ├── responder.py        # Response generation
│   │   │   ├── feedback.py         # Correction formatting
│   │   │   └── state_updater.py    # State persistence
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── dictionary.py       # Word lookup tool
│   │       └── grammar.py          # Grammar rule lookup
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py               # SQLAlchemy models
│   │   ├── repository.py           # Data access layer
│   │   └── seed.py                 # Initial data (grammar rules, etc.)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── vocabulary.py           # Vocabulary extraction logic
│   │   ├── grammar.py              # Grammar checking logic
│   │   └── level.py                # Level assessment logic
│   │
│   ├── templates/
│   │   ├── base.html               # Base template with HTMX
│   │   ├── index.html              # Main chat page
│   │   ├── components/
│   │   │   ├── header.html
│   │   │   ├── sidebar.html
│   │   │   └── settings_modal.html
│   │   └── partials/
│   │       ├── message_user.html   # User message bubble
│   │       ├── message_ai.html     # AI message with feedback
│   │       ├── feedback.html       # Correction card
│   │       ├── vocab_card.html     # Vocabulary item
│   │       └── stats.html          # Session statistics
│   │
│   └── static/
│       ├── css/
│       │   └── output.css          # Tailwind compiled
│       └── js/
│           └── htmx.min.js         # HTMX library
│
├── tests/
│   ├── conftest.py
│   ├── test_graph.py               # LangGraph integration tests
│   ├── test_grammar.py             # Grammar checking tests
│   └── test_vocabulary.py          # Vocabulary extraction tests
│
├── data/
│   ├── habla.db                    # SQLite database
│   └── grammar_rules/              # Grammar rule definitions
│       ├── spanish.json
│       └── german.json
│
├── docs/
│   ├── product.md
│   └── architecture.md
│
├── pyproject.toml
├── Makefile
├── .env.example
└── README.md
```

---

## LangGraph Architecture

### State Definition

```python
from typing import TypedDict, Annotated, Optional
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

class GrammarError(TypedDict):
    original: str           # What the user wrote
    correction: str         # Suggested correction
    rule_id: str           # Grammar rule identifier
    explanation: str        # Brief explanation
    severity: str          # "minor" | "moderate" | "significant"

class VocabItem(TypedDict):
    word: str
    translation: str
    part_of_speech: str
    gender: Optional[str]   # For German nouns
    context: str            # Sentence where encountered

class SessionStats(TypedDict):
    messages_sent: int
    words_learned: int
    errors_corrected: int
    session_start: str

class LearnerState(TypedDict):
    # Conversation
    messages: Annotated[list[BaseMessage], add_messages]

    # Language settings
    target_language: str    # "es" | "de"
    user_level: str         # "A1" | "A2" | "B1" | "B2" | "C1" | "C2"

    # Session data
    session_vocab: list[VocabItem]
    grammar_errors: list[GrammarError]
    session_stats: SessionStats

    # Preferences
    feedback_mode: str      # "gentle" | "detailed" | "minimal"

    # Routing
    current_intent: str     # "chat" | "help" | "vocab_review" | "scenario"
    current_scenario: Optional[str]

    # Control flags
    should_adjust_level: bool
    level_adjustment: Optional[str]  # "up" | "down" | None
```

### Graph Definition

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

def build_graph():
    graph = StateGraph(LearnerState)

    # Add nodes
    graph.add_node("route_input", route_input_node)
    graph.add_node("analyze_message", analyze_message_node)
    graph.add_node("generate_response", generate_response_node)
    graph.add_node("extract_vocabulary", extract_vocabulary_node)
    graph.add_node("check_grammar", check_grammar_node)
    graph.add_node("format_feedback", format_feedback_node)
    graph.add_node("update_state", update_state_node)
    graph.add_node("assess_level", assess_level_node)

    # Entry point
    graph.set_entry_point("route_input")

    # Conditional routing from route_input
    graph.add_conditional_edges(
        "route_input",
        determine_intent,
        {
            "chat": "analyze_message",
            "help": "generate_response",  # Direct to help response
            "vocab_review": "generate_response",
            "scenario": "generate_response",
        }
    )

    # Main conversation flow
    graph.add_edge("analyze_message", "generate_response")
    graph.add_edge("generate_response", "extract_vocabulary")
    graph.add_edge("extract_vocabulary", "check_grammar")

    # Conditional feedback
    graph.add_conditional_edges(
        "check_grammar",
        has_errors,
        {
            True: "format_feedback",
            False: "update_state",
        }
    )
    graph.add_edge("format_feedback", "update_state")

    # Level assessment
    graph.add_edge("update_state", "assess_level")

    # End
    graph.add_edge("assess_level", END)

    return graph.compile(checkpointer=SqliteSaver.from_conn_string("data/habla.db"))
```

### Graph Visualization

```
                    ┌──────────────────┐
                    │   route_input    │
                    └────────┬─────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    [vocab_review]     [analyze_message]    [help]
           │                 │                 │
           └────────────────►│◄────────────────┘
                             │
                    ┌────────▼─────────┐
                    │ generate_response │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ extract_vocabulary│
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  check_grammar   │
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
              │ has_errors?                 │
              ▼                             ▼
     ┌────────────────┐            ┌────────────────┐
     │ format_feedback │            │  update_state  │
     └────────┬───────┘            └────────┬───────┘
              │                             │
              └─────────────►◄──────────────┘
                             │
                    ┌────────▼─────────┐
                    │   assess_level   │
                    └────────┬─────────┘
                             │
                            END
```

### Node Implementations

#### Router Node

```python
async def route_input_node(state: LearnerState) -> LearnerState:
    """Determine user intent from the latest message."""
    last_message = state["messages"][-1].content.lower()

    # Simple heuristics (could use LLM for complex cases)
    if any(word in last_message for word in ["help", "ayuda", "hilfe", "?"]):
        intent = "help"
    elif any(word in last_message for word in ["vocabulary", "words", "vocab"]):
        intent = "vocab_review"
    elif state.get("current_scenario"):
        intent = "scenario"
    else:
        intent = "chat"

    return {"current_intent": intent}

def determine_intent(state: LearnerState) -> str:
    """Routing function for conditional edges."""
    return state["current_intent"]
```

#### Grammar Check Node

```python
async def check_grammar_node(state: LearnerState) -> LearnerState:
    """Analyze user message for grammar errors."""
    user_message = state["messages"][-2].content  # User's message before AI response
    language = state["target_language"]
    level = state["user_level"]

    # Use LLM for grammar analysis
    grammar_prompt = f"""
    Analyze this {language} message for grammar errors.
    User level: {level}
    Message: "{user_message}"

    Return JSON array of errors:
    [{{
        "original": "incorrect phrase",
        "correction": "correct phrase",
        "rule_id": "rule identifier",
        "explanation": "brief explanation",
        "severity": "minor|moderate|significant"
    }}]

    Only flag errors appropriate for {level} level.
    Return empty array if no errors.
    """

    response = await llm.ainvoke(grammar_prompt)
    errors = parse_grammar_response(response)

    return {"grammar_errors": errors}
```

---

## Database Schema

```sql
-- Languages supported
CREATE TABLE languages (
    code TEXT PRIMARY KEY,          -- 'es', 'de'
    name TEXT NOT NULL,             -- 'Spanish', 'German'
    native_name TEXT NOT NULL       -- 'Español', 'Deutsch'
);

-- Master vocabulary list
CREATE TABLE vocabulary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language_code TEXT NOT NULL REFERENCES languages(code),
    word TEXT NOT NULL,
    translation TEXT NOT NULL,
    part_of_speech TEXT,            -- noun, verb, adjective, etc.
    gender TEXT,                    -- m/f/n for German, m/f for Spanish
    example_sentence TEXT,
    example_translation TEXT,
    cefr_level TEXT,                -- A1, A2, B1, B2, C1, C2
    frequency_rank INTEGER,         -- Word frequency ranking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(language_code, word)
);

-- User's vocabulary progress
CREATE TABLE user_vocabulary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vocab_id INTEGER NOT NULL REFERENCES vocabulary(id),
    mastery_level INTEGER DEFAULT 0,    -- 0=new, 1=learning, 2=familiar, 3=mastered
    times_seen INTEGER DEFAULT 0,
    times_correct INTEGER DEFAULT 0,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP,
    next_review_at TIMESTAMP,           -- For spaced repetition
    context_first_seen TEXT             -- Sentence where first encountered
);

-- Conversation sessions
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language_code TEXT NOT NULL REFERENCES languages(code),
    scenario_type TEXT,                 -- NULL for free chat
    level_at_start TEXT NOT NULL,
    level_at_end TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP
);

-- Individual messages
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,                 -- 'user' | 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Grammar feedback given
CREATE TABLE grammar_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages(id),
    original_text TEXT NOT NULL,
    corrected_text TEXT NOT NULL,
    rule_id TEXT,
    explanation TEXT,
    severity TEXT                       -- 'minor' | 'moderate' | 'significant'
);

-- Grammar rules reference
CREATE TABLE grammar_rules (
    id TEXT PRIMARY KEY,                -- e.g., 'es_preterite_vs_imperfect'
    language_code TEXT NOT NULL REFERENCES languages(code),
    name TEXT NOT NULL,
    explanation TEXT NOT NULL,
    examples TEXT,                      -- JSON array of examples
    cefr_level TEXT,
    common_mistakes TEXT                -- JSON array of common errors
);

-- User settings
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Indexes for performance
CREATE INDEX idx_user_vocab_next_review ON user_vocabulary(next_review_at);
CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_vocabulary_language ON vocabulary(language_code);
CREATE INDEX idx_grammar_rules_language ON grammar_rules(language_code);
```

---

## API Endpoints

### Chat Endpoints

```python
# POST /api/chat
# Send a message, receive AI response as HTMX partial

@router.post("/chat")
async def send_message(
    message: str = Form(...),
    request: Request,
    graph: CompiledGraph = Depends(get_graph),
    session: AsyncSession = Depends(get_session)
):
    # Invoke LangGraph
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=message)]},
        config={"configurable": {"thread_id": get_thread_id(request)}}
    )

    # Return HTMX partial
    return templates.TemplateResponse(
        "partials/message_ai.html",
        {
            "request": request,
            "content": result["messages"][-1].content,
            "feedback": result.get("grammar_errors", []),
            "new_vocab": result.get("session_vocab", [])
        }
    )


# GET /api/chat/stream
# SSE endpoint for streaming response

@router.get("/chat/stream")
async def stream_response(
    request: Request,
    graph: CompiledGraph = Depends(get_graph)
):
    async def event_generator():
        async for chunk in graph.astream(...):
            if "generate_response" in chunk:
                yield f"data: {chunk['generate_response']['content']}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

### Vocabulary Endpoints

```python
# GET /api/vocab
# Get vocabulary list as HTMX partial

@router.get("/vocab")
async def get_vocabulary(
    request: Request,
    filter: str = Query("all"),  # all, new, learning, mastered
    language: str = Query(None),
    session: AsyncSession = Depends(get_session)
):
    vocab = await repository.get_user_vocabulary(filter, language)
    return templates.TemplateResponse(
        "partials/vocab_list.html",
        {"request": request, "vocabulary": vocab}
    )


# POST /api/vocab/{id}/review
# Mark vocabulary item as reviewed

@router.post("/vocab/{vocab_id}/review")
async def review_vocabulary(
    vocab_id: int,
    correct: bool = Form(...),
    session: AsyncSession = Depends(get_session)
):
    await repository.update_vocabulary_mastery(vocab_id, correct)
    return Response(status_code=204)
```

### Session Endpoints

```python
# POST /api/session/start
# Start new conversation session

@router.post("/session/start")
async def start_session(
    language: str = Form(...),
    level: str = Form(...),
    scenario: str = Form(None),
    session: AsyncSession = Depends(get_session)
):
    conversation = await repository.create_conversation(language, level, scenario)
    return templates.TemplateResponse(
        "partials/session_started.html",
        {"conversation_id": conversation.id}
    )
```

---

## HTMX Integration

### Base Template

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HablaAI</title>
    <link href="/static/css/output.css" rel="stylesheet">
    <script src="/static/js/htmx.min.js"></script>
    <script src="https://unpkg.com/htmx.org/dist/ext/sse.js"></script>
</head>
<body class="bg-gray-50 min-h-screen">
    {% block content %}{% endblock %}
</body>
</html>
```

### Chat Form

```html
<form
    hx-post="/api/chat"
    hx-target="#messages"
    hx-swap="beforeend"
    hx-on::after-request="this.reset(); document.getElementById('messages').scrollTo(0, 999999)"
    class="flex gap-2"
>
    <input
        type="text"
        name="message"
        placeholder="Type your message..."
        autocomplete="off"
        class="flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
    <button
        type="submit"
        class="bg-blue-500 text-white rounded-lg px-4 py-2 hover:bg-blue-600"
    >
        Send
    </button>
</form>
```

### Message Partial (AI Response)

```html
<!-- partials/message_ai.html -->
<div class="flex gap-3 mb-4">
    <div class="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white">
        🤖
    </div>
    <div class="flex-1">
        <div class="bg-white rounded-lg p-4 shadow-sm">
            {{ content }}
        </div>

        {% if feedback %}
        <details class="mt-2 text-sm">
            <summary class="cursor-pointer text-blue-600 hover:text-blue-800">
                💡 {{ feedback|length }} suggestion(s)
            </summary>
            <div class="mt-2 bg-yellow-50 rounded-lg p-3">
                {% for error in feedback %}
                <div class="mb-2 last:mb-0">
                    <div class="text-red-600 line-through">{{ error.original }}</div>
                    <div class="text-green-600">→ {{ error.correction }}</div>
                    <div class="text-gray-600 text-xs mt-1">{{ error.explanation }}</div>
                </div>
                {% endfor %}
            </div>
        </details>
        {% endif %}
    </div>
</div>
```

### Vocabulary Sidebar Update

```html
<!-- Sidebar that updates when new vocab is learned -->
<div
    id="vocab-sidebar"
    hx-get="/api/vocab?filter=session"
    hx-trigger="vocab-updated from:body"
    hx-swap="innerHTML"
>
    {% include "partials/vocab_list.html" %}
</div>

<!-- Trigger event after chat response -->
<script>
    document.body.addEventListener('htmx:afterSwap', function(event) {
        if (event.detail.target.id === 'messages') {
            htmx.trigger('body', 'vocab-updated');
        }
    });
</script>
```

---

## Prompts

### Spanish Tutor System Prompt

```python
SPANISH_TUTOR_PROMPT = """
You are a friendly Spanish conversation partner. Your role is to:

1. RESPOND naturally in Spanish at {level} CEFR level
2. Keep the conversation flowing naturally
3. Use vocabulary and grammar appropriate for {level}
4. Be encouraging and supportive

Level guidelines for {level}:
- A1: Present tense, basic vocabulary, simple sentences
- A2: Past tense (preterite), common expressions, short paragraphs
- B1: All past tenses, subjunctive basics, opinions and narratives
- B2: Complex subjunctive, conditionals, abstract topics
- C1: Advanced structures, idioms, professional vocabulary
- C2: Native-like complexity, nuanced expression

Current conversation context: {context}

Remember:
- Stay in Spanish for your responses
- Don't explicitly correct errors in your response (that's handled separately)
- Be warm and conversational, not like a textbook
- If the user seems stuck, gently guide them
"""
```

### Grammar Analysis Prompt

```python
GRAMMAR_ANALYSIS_PROMPT = """
Analyze this {language} text for grammar errors.

User's level: {level}
User's message: "{message}"

Focus on errors that a {level} learner should know. Ignore:
- Minor style preferences
- Regional variations
- Errors beyond their level

For each error found, provide:
1. original: The exact incorrect phrase
2. correction: The corrected phrase
3. rule_id: A standardized rule identifier (e.g., "ser_vs_estar", "gender_agreement")
4. explanation: A brief, encouraging explanation (1-2 sentences)
5. severity: "minor" (doesn't affect meaning), "moderate" (slightly confusing), "significant" (changes meaning)

Return as JSON array. Empty array if no errors.

Example output:
[
  {{
    "original": "Yo soy cansado",
    "correction": "Yo estoy cansado",
    "rule_id": "ser_vs_estar_conditions",
    "explanation": "For temporary states like being tired, we use 'estar' not 'ser'. Think: estar = how you're feeling right now.",
    "severity": "moderate"
  }}
]
"""
```

---

## Configuration

### Environment Variables

```bash
# .env.example

# LLM Configuration
ANTHROPIC_API_KEY=your_api_key_here
LLM_MODEL=claude-3-5-sonnet-20241022
LLM_TEMPERATURE=0.7

# Database
DATABASE_URL=sqlite:///data/habla.db

# Application
DEBUG=true
HOST=127.0.0.1
PORT=8000

# Feature flags
ENABLE_VOICE_INPUT=false
ENABLE_SPACED_REPETITION=true
```

### Settings Model

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLM
    anthropic_api_key: str
    llm_model: str = "claude-3-5-sonnet-20241022"
    llm_temperature: float = 0.7

    # Database
    database_url: str = "sqlite:///data/habla.db"

    # Application
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000

    # Features
    enable_voice_input: bool = False
    enable_spaced_repetition: bool = True

    class Config:
        env_file = ".env"
```

---

## Development Setup

### Makefile

```makefile
.PHONY: install dev build test clean

install:
	pip install -e ".[dev]"
	npm install  # For Tailwind

dev:
	uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000

dev-css:
	npx tailwindcss -i ./src/static/css/input.css -o ./src/static/css/output.css --watch

build:
	npx tailwindcss -i ./src/static/css/input.css -o ./src/static/css/output.css --minify

test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=src --cov-report=html

lint:
	ruff check src/
	ruff format src/

db-init:
	python -c "from src.db.models import init_db; init_db()"

db-seed:
	python src/db/seed.py

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} +
```

### pyproject.toml

```toml
[project]
name = "habla-ai"
version = "0.1.0"
description = "AI-powered Spanish and German conversation partner"
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
    "pydantic-settings>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.1.0",
    "httpx>=0.26.0",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## Testing Strategy

### Graph Integration Test

```python
import pytest
from src.agent.graph import build_graph
from langchain_core.messages import HumanMessage

@pytest.mark.asyncio
async def test_basic_conversation():
    graph = build_graph()

    result = await graph.ainvoke({
        "messages": [HumanMessage(content="Hola, me llamo Juan")],
        "target_language": "es",
        "user_level": "A1",
        "feedback_mode": "gentle"
    })

    # Should have AI response
    assert len(result["messages"]) == 2
    assert result["messages"][-1].type == "ai"

    # Response should be in Spanish
    assert any(word in result["messages"][-1].content.lower()
               for word in ["hola", "mucho", "gusto", "juan"])

@pytest.mark.asyncio
async def test_grammar_correction():
    graph = build_graph()

    result = await graph.ainvoke({
        "messages": [HumanMessage(content="Yo soy cansado")],  # Error: should be estoy
        "target_language": "es",
        "user_level": "A2",
        "feedback_mode": "detailed"
    })

    # Should detect ser/estar error
    errors = result.get("grammar_errors", [])
    assert len(errors) > 0
    assert any("estar" in e["correction"] for e in errors)
```

### API Test

```python
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_send_message():
    response = client.post(
        "/api/chat",
        data={"message": "Hola, ¿cómo estás?"}
    )
    assert response.status_code == 200
    assert "message_ai" in response.text or "🤖" in response.text

def test_get_vocabulary():
    response = client.get("/api/vocab")
    assert response.status_code == 200
```

---

## Deployment

### Local Development

```bash
# Clone and setup
git clone <repo>
cd habla-ai

# Install dependencies
make install

# Initialize database
make db-init
make db-seed

# Start development server (run in separate terminals)
make dev      # Backend
make dev-css  # Tailwind watcher
```

### Production Deployment

For single-user self-hosting:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application
COPY src/ src/
COPY data/ data/

# Build CSS
RUN pip install nodejs-bin
RUN npx tailwindcss -i ./src/static/css/input.css -o ./src/static/css/output.css --minify

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Future Considerations

### Voice Input (V2)

```python
# Integration with Whisper for speech-to-text
@router.post("/api/chat/voice")
async def voice_message(
    audio: UploadFile = File(...),
    whisper_client: WhisperClient = Depends(get_whisper)
):
    transcript = await whisper_client.transcribe(audio)
    # Process transcript through normal chat flow
    return await send_message(message=transcript, ...)
```

### Multi-User Support (Future)

- Add `users` table with authentication
- Add `user_id` foreign key to relevant tables
- Implement session management with JWT or cookies
- Consider moving to PostgreSQL for concurrent access

### Additional Languages (Future)

- Add language-specific grammar rules to `data/grammar_rules/`
- Create language-specific prompts in `src/agent/prompts.py`
- Populate `vocabulary` table with frequency lists
- Test with native speakers for quality
