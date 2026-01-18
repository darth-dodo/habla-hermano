# Feature: Phase 1 - Basic Chat with LangGraph

## Overview

Phase 1 implements the foundational conversational AI tutor using LangGraph StateGraph. The system delivers level-adaptive responses based on CEFR proficiency levels (A0 through B1), supporting multiple target languages through a single respond node architecture.

**Business Value**: Language learners need conversational practice at their skill level. A tutor that adapts its language mix (native vs. target language) and complexity provides an accessible entry point for beginners while challenging intermediate learners appropriately.

**LangGraph Learning Goal**: Master `StateGraph` basics with single-node graphs, TypedDict state management, and the `add_messages` reducer pattern.

---

## Requirements

### Functional Requirements

1. **LangGraph StateGraph**: Implement conversation flow using LangGraph's StateGraph pattern
2. **Respond Node**: Generate AI responses appropriate to the user's CEFR level
3. **CEFR Level Support**: Support 4 proficiency levels (A0, A1, A2, B1) with distinct behaviors
4. **Multi-Language Support**: Handle Spanish (es), German (de), and French (fr) target languages
5. **Theme Switching**: Provide dark, light, and ocean visual themes
6. **Real-Time UI**: Use HTMX for seamless message updates without page reloads

### Non-Functional Requirements

- Response latency should be acceptable for conversational flow (<3s)
- UI should remain responsive during LLM calls (loading indicator)
- Theme persistence across sessions via localStorage
- Mobile-first responsive design

---

## Architecture

### Graph Structure (Phase 1)

```
                    +-------------+
                    |    START    |
                    +------+------+
                           |
                    +------v------+
                    |   respond   |  <- Generate AI response
                    +------+------+
                           |
                    +------v------+
                    |     END     |
                    +-------------+
```

Phase 1 uses a minimal graph with a single node. The respond node receives the conversation state, generates a level-appropriate response via Claude, and returns the updated messages.

### State Flow

```
Input State:
{
    messages: [HumanMessage("Hola!")],
    level: "A1",
    language: "es"
}

    |
    v  respond_node()

Output State:
{
    messages: [HumanMessage("Hola!"), AIMessage("...")],
    level: "A1",
    language: "es"
}
```

### Components

#### 1. Conversation State (`src/agent/state.py`)

```python
class ConversationState(TypedDict):
    """Main LangGraph state for HablaAI conversations."""
    messages: Annotated[list[BaseMessage], add_messages]
    level: str  # A0, A1, A2, B1
    language: str  # es, de, fr
```

**Responsibility**: Define the shape of data flowing through the graph
**Key Feature**: The `add_messages` reducer automatically appends new messages to the existing list

#### 2. Respond Node (`src/agent/nodes/respond.py`)

```python
async def respond_node(state: ConversationState) -> dict[str, Any]:
    """Generate an AI response appropriate to the user's level."""
    prompt = get_prompt_for_level(language=state["language"], level=state["level"])
    messages = [SystemMessage(content=prompt), *state["messages"]]
    llm = _get_llm()
    response = await llm.ainvoke(messages)
    return {"messages": [response]}
```

**Responsibility**: Call Claude with level-appropriate system prompt and conversation history
**Interface**: Takes ConversationState, returns dict with `messages` key for reducer

#### 3. Graph Builder (`src/agent/graph.py`)

```python
def build_graph() -> CompiledStateGraph[Any]:
    """Build and compile the conversation graph."""
    graph = StateGraph(ConversationState)
    graph.add_node("respond", respond_node)
    graph.set_entry_point("respond")
    graph.add_edge("respond", END)
    return graph.compile()
```

**Responsibility**: Wire together nodes and edges into an executable graph
**Interface**: Returns compiled graph ready for `.ainvoke()` calls

#### 4. System Prompts (`src/agent/prompts.py`)

```python
def get_prompt_for_level(language: str, level: str) -> str:
    """Get the system prompt for a given language and level."""
```

**Responsibility**: Return CEFR-appropriate system prompts with language substitution
**Interface**: Takes language code and level, returns formatted prompt string

#### 5. Chat Route (`src/api/routes/chat.py`)

```python
@router.post("/chat", response_class=HTMLResponse)
async def send_message(...) -> HTMLResponse:
    """Process a chat message and return the response as partial HTML."""
```

**Responsibility**: Handle HTMX form submissions, invoke graph, return HTML fragments
**Interface**: Receives form data, returns partial HTML for HTMX swap

#### 6. Templates (`src/templates/`)

- `base.html`: Theme system, CSS variables, Alpine.js/HTMX setup
- `chat.html`: Main chat interface with header controls and message container
- `partials/message_pair.html`: AI response bubble (user message shown optimistically)

**Responsibility**: Render the chat UI with theme support and HTMX integration

---

## Data Models

### ConversationState (Phase 1 Core)

```python
class ConversationState(TypedDict):
    """Main LangGraph state for HablaAI conversations."""

    # Message history with automatic accumulation
    messages: Annotated[list[BaseMessage], add_messages]

    # User's proficiency level (CEFR scale)
    level: str  # A0, A1, A2, B1

    # Target language being learned
    language: str  # es, de, fr
```

### CEFR Level Definitions

| Level | Name | Language Mix | Characteristics |
|-------|------|--------------|-----------------|
| A0 | Complete Beginner | 80% English, 20% target | Single concepts, heavy celebration, yes/no questions |
| A1 | Beginner | 50% English, 50% target | Present tense only, 5-8 word sentences, implicit correction |
| A2 | Elementary | 20% English, 80% target | Past tense introduction, 8-12 word sentences, follow-up questions |
| B1 | Intermediate | 5% English, 95% target | Natural conversation, idioms, subjunctive, abstract topics |

---

## The Respond Node

### System Prompt Architecture

The respond node uses level-specific system prompts that define:

1. **Language Mix Ratio**: How much target language vs. English to use
2. **Behavioral Guidelines**: How to handle errors, pace learning, encourage
3. **Topic Scope**: Appropriate conversation topics for the level
4. **Grammar Focus**: What grammatical concepts to introduce

### A0 (Complete Beginner) Prompt

```
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
```

### A1 (Beginner) Prompt

```
LANGUAGE MIX: Speak 50% Spanish, 50% English.
- Use Spanish for simple sentences and common phrases
- Use English to explain or when they seem confused

BEHAVIOR:
- Use present tense only
- Short sentences (5-8 words max)
- Common vocabulary only
- If they make mistakes, respond naturally (model correct form) without explicit correction
```

### Language Adaptation

The prompt system uses string replacement to adapt Spanish-focused prompts for other languages:

```python
if language == "de":
    prompt = prompt.replace("Spanish", "German")
    prompt = prompt.replace("Hola", "Hallo")
    prompt = prompt.replace("Me llamo", "Ich heisse")
elif language == "fr":
    prompt = prompt.replace("Spanish", "French")
    prompt = prompt.replace("Hola", "Bonjour")
    prompt = prompt.replace("Me llamo", "Je m'appelle")
```

---

## HTMX Integration

### Form Submission Flow

```html
<form
    hx-post="/chat"
    hx-target="#chat-messages"
    hx-swap="beforeend"
    hx-indicator="#loading-indicator"
    hx-on::before-request="showLoading()"
    hx-on::after-request="hideLoading(); clearInput()"
>
```

**Attributes Explained**:
- `hx-post="/chat"`: Submit form data to POST /chat endpoint
- `hx-target="#chat-messages"`: Insert response into the messages container
- `hx-swap="beforeend"`: Append new content at the end (preserves history)
- `hx-indicator`: Show loading dots during request
- `hx-on::before-request/after-request`: JavaScript hooks for UI polish

### Response Flow

1. User types message and submits form
2. JavaScript shows user message immediately (optimistic UI)
3. Loading indicator appears
4. HTMX posts form data to `/chat` endpoint
5. FastAPI invokes LangGraph with message, level, language
6. Graph returns AI response
7. Route renders `partials/message_pair.html` with response
8. HTMX swaps HTML fragment into chat container
9. Loading indicator hides, input clears

### Hidden Form Fields

```html
<input type="hidden" name="level" x-ref="levelInput" :value="level">
<input type="hidden" name="language" x-ref="languageInput" :value="language">
```

Alpine.js manages these values reactively when users change settings via dropdowns.

---

## Theme System

### Implementation

Themes use CSS custom properties (variables) that change based on the `data-theme` attribute:

```css
:root, [data-theme="dark"] {
    --surface: #1a1625;
    --text: #f5f3ff;
    --accent: #a78bfa;
    /* ... */
}

[data-theme="light"] {
    --surface: #fefdfb;
    --text: #2d2a26;
    --accent: #5d7c5d;
    /* ... */
}

[data-theme="ocean"] {
    --surface: #0d1b2a;
    --text: #e0e6ed;
    --accent: #d4a55a;
    /* ... */
}
```

### Theme Switching

Alpine.js manages theme state with localStorage persistence:

```javascript
x-data="{
    theme: localStorage.getItem('habla-theme') || 'dark',
    setTheme(newTheme) {
        this.theme = newTheme;
        localStorage.setItem('habla-theme', newTheme);
        document.documentElement.setAttribute('data-theme', newTheme);
    }
}"
```

### Theme Characteristics

| Theme | Background | Accent | Character |
|-------|------------|--------|-----------|
| Dark | Purple noir (#1a1625) | Violet (#a78bfa) | Modern, focused |
| Light | Warm sand (#fefdfb) | Sage green (#5d7c5d) | Clean, calming |
| Ocean | Midnight blue (#0d1b2a) | Golden sand (#d4a55a) | Immersive, deep |

---

## API Contracts

### POST /chat

**Request** (form data):
```
message: string (required) - User's message
level: string (optional, default "A1") - CEFR level (A0, A1, A2, B1)
language: string (optional, default "es") - Target language (es, de, fr)
```

**Response** (HTML fragment):
```html
<!-- AI Response -->
<div class="message-enter flex justify-start mb-6">
    <div class="bg-ai rounded-2xl rounded-bl-sm px-4 py-3 max-w-[80%] shadow-sm">
        <div class="text-ai-text leading-relaxed">
            [AI response text]
        </div>
    </div>
</div>
```

### GET /

**Response**: Full chat page HTML with:
- Header with language/level selectors and theme toggle
- Chat message container
- Input form with HTMX configuration
- Welcome message from AI tutor

---

## Dependencies

### External Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| `langgraph` | ^0.2 | StateGraph, graph compilation |
| `langchain-anthropic` | ^0.3 | Claude API integration |
| `langchain-core` | ^0.3 | BaseMessage types |
| `fastapi` | ^0.115 | Web framework |
| `jinja2` | ^3.1 | HTML templating |
| `htmx.org` | 1.9.10 | Frontend interactivity |
| `alpinejs` | 3.13.3 | Reactive UI state |
| `tailwindcss` | CDN | Styling |

### Internal Modules

```
src/agent/
    __init__.py      - Exports compiled_graph
    graph.py         - Graph builder function
    state.py         - ConversationState TypedDict
    prompts.py       - CEFR level system prompts
    nodes/
        __init__.py
        respond.py   - Respond node implementation

src/api/
    config.py        - Settings (API keys, model config)
    dependencies.py  - FastAPI dependency injection
    routes/
        chat.py      - Chat endpoints

src/templates/
    base.html        - Theme system, layout
    chat.html        - Chat interface
    partials/
        message_pair.html - Message rendering
```

---

## Testing Strategy

### Unit Tests

- `test_state.py`: Verify ConversationState structure
- `test_prompts.py`: Test prompt generation for all level/language combinations
- `test_respond_node.py`: Mock LLM and verify node behavior

### Integration Tests

- `test_agent_graph.py`: Test full graph invocation
- `test_chat_route.py`: Test API endpoint with mocked graph

### Manual Testing Scenarios

1. Start conversation at A0 level - expect mostly English response
2. Start conversation at B1 level - expect mostly target language
3. Switch languages mid-session - verify prompt adaptation
4. Switch themes - verify CSS variable changes persist
5. Mobile viewport - verify responsive layout

---

## Success Criteria

### Functional

- [x] LangGraph StateGraph compiles and executes without errors
- [x] Respond node generates level-appropriate responses
- [x] All 4 CEFR levels produce distinct language mix ratios
- [x] Language switching works for Spanish, German, French
- [x] Theme switching persists across page reloads

### Technical

- [x] Graph uses `add_messages` reducer correctly
- [x] Async node execution with `ainvoke`
- [x] HTMX partial responses work without full page reloads
- [x] Alpine.js manages UI state reactively

### User Experience

- [x] Chat feels conversational and responsive
- [x] Loading indicator provides feedback during AI generation
- [x] Level/language selectors are intuitive
- [x] Themes provide distinct visual experiences

---

## Appendix: LangGraph StateGraph Reference

### Basic Pattern

```python
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing import Annotated
from typing_extensions import TypedDict

class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

def build_graph():
    graph = StateGraph(State)
    graph.add_node("node_name", node_function)
    graph.set_entry_point("node_name")
    graph.add_edge("node_name", END)
    return graph.compile()
```

### Key Concepts

1. **StateGraph**: Container for nodes and edges
2. **TypedDict State**: Defines shape of data flowing through graph
3. **Reducers**: Functions like `add_messages` that combine state updates
4. **Nodes**: Functions that receive state and return partial state updates
5. **Edges**: Connect nodes in sequence (`add_edge`) or conditionally (`add_conditional_edges`)

### Phase 1 Simplification

Phase 1 uses the simplest possible graph structure to establish the pattern before adding complexity:

- Single node (respond)
- No conditional routing
- Direct edge to END
- State contains only essential fields

This foundation enables Phase 2 (analyze node) and Phase 3 (conditional routing) to build incrementally.
