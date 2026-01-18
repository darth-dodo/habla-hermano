# Feature: Phase 2 - Grammar Analysis and Feedback

## Overview

Phase 2 adds an **analyze node** to the LangGraph conversation flow, providing grammar error detection and vocabulary tracking for language learners. This phase introduces the **sequential graph pattern** - extending a linear flow with additional processing nodes.

**Business Value**: Grammar correction is essential for language learning. By analyzing user messages and providing gentle, educational feedback, learners can identify and fix mistakes while maintaining conversational flow.

**LangGraph Learning Goal**: Master multi-node graphs with state updates that pass through sequential nodes.

---

## Requirements

### Functional Requirements

1. **Grammar Error Detection**: Analyze user messages for grammar mistakes appropriate to their CEFR level
2. **Severity Classification**: Categorize errors as minor, moderate, or significant
3. **Educational Explanations**: Provide brief, friendly explanations for each correction
4. **Vocabulary Tracking**: Identify new or notable vocabulary from the conversation
5. **Level-Aware Feedback**:
   - A0: Only flag very basic errors (spelling, basic conjugation). Be very encouraging.
   - A1: Add gender agreement, ser/estar confusion
   - A2: Include past tense errors, reflexive verb issues
   - B1: Include subjunctive, conditional, advanced constructions

### Non-Functional Requirements

- Grammar analysis should add <500ms to response time
- UI should gracefully handle zero grammar errors
- Feedback should not interrupt conversation flow
- Maximum 3 grammar errors and 5 vocabulary words per response (to avoid overwhelming learners)

---

## Architecture

### Graph Structure (Phase 2)

```
                    +-----------+
                    |   START   |
                    +-----+-----+
                          |
                    +-----v-----+
                    |  respond  |  <- Generate AI response
                    +-----+-----+
                          |
                    +-----v-----+
                    |  analyze  |  <- Grammar + vocab extraction
                    +-----+-----+
                          |
                    +-----v-----+
                    |    END    |
                    +-----------+
```

### Components

#### 1. Analyze Node (`src/agent/nodes/analyze.py`)

```python
async def analyze_node(state: ConversationState) -> dict[str, Any]:
    """
    Analyze the user's last message for grammar and vocabulary.

    This node runs after the respond node to provide educational feedback
    without disrupting the conversation flow.

    The analysis is level-aware:
    - A0: Only flag very basic errors (spelling, basic conjugation)
    - A1: Add gender agreement, ser/estar confusion
    - A2: Add past tense errors, reflexive verb issues
    - B1: Add subjunctive, conditional, advanced constructions
    """
```

**Responsibility**: Extract grammar errors and vocabulary from user's message
**Interface**: Takes ConversationState, returns dict with `grammar_feedback` and `new_vocabulary` keys

#### 2. Extended State (`src/agent/state.py`)

```python
class GrammarFeedback(TypedDict):
    """Represents a grammar correction for the user's message."""
    original: str
    correction: str
    explanation: str
    severity: Literal["minor", "moderate", "significant"]

class VocabWord(TypedDict):
    """Represents a vocabulary word introduced or used in conversation."""
    word: str
    translation: str
    part_of_speech: str
```

**Responsibility**: Define data structures for grammar feedback and vocabulary
**Interface**: TypedDicts for type-safe state management

#### 3. Grammar Feedback UI (`src/templates/partials/grammar_feedback.html`)

```html
<!-- Collapsible grammar tips section -->
<div x-data="{ expanded: false }">
    <!-- Toggle button with lightbulb icon -->
    <!-- Expandable content with severity-coded corrections -->
    <!-- Original -> Correction display -->
    <!-- Friendly explanations -->
</div>
```

**Responsibility**: Display grammar feedback in a non-intrusive, expandable format
**Interface**: Jinja2 partial receiving grammar_feedback list

---

## Data Models

### GrammarFeedback (TypedDict)

```python
class GrammarFeedback(TypedDict):
    """
    Represents a grammar correction for the user's message.

    Attributes:
        original: The incorrect phrase from the user's message.
        correction: The corrected version of the phrase.
        explanation: A brief, friendly explanation of the error.
        severity: How significant the error is for learning purposes.
    """

    original: str
    correction: str
    explanation: str
    severity: Literal["minor", "moderate", "significant"]
```

### VocabWord (TypedDict)

```python
class VocabWord(TypedDict):
    """
    Represents a vocabulary word introduced or used in conversation.

    Attributes:
        word: The word in the target language.
        translation: The English translation.
        part_of_speech: Grammatical category (noun, verb, adjective, etc.).
    """

    word: str
    translation: str
    part_of_speech: str
```

### Extended ConversationState

```python
class ConversationState(TypedDict):
    # Existing fields (Phase 1)
    messages: Annotated[list[BaseMessage], add_messages]
    level: str  # A0, A1, A2, B1
    language: str  # es, de, fr

    # New fields (Phase 2)
    grammar_feedback: NotRequired[list[GrammarFeedback]]
    new_vocabulary: NotRequired[list[VocabWord]]
```

---

## API Contracts

### Analyze Node LLM Prompt

```python
ANALYSIS_PROMPT = """You are a language learning assistant analyzing a student's message.

The student is learning {language} at CEFR level {level}.

Analyze their message for:
1. Grammar errors appropriate to flag at their level
2. New vocabulary words they used or should learn

LEVEL GUIDELINES:
- A0: Only flag very basic errors (wrong greetings, completely wrong words). Be very encouraging.
- A1: Flag basic present tense errors, gender agreement, ser/estar confusion.
- A2: Include past tense errors, reflexive verbs, object pronouns.
- B1: Include subjunctive, conditionals, idiomatic expressions.

For vocabulary, identify:
- Words the student used correctly (to reinforce)
- Key words from the conversation they should remember

Return ONLY valid JSON in this exact format:
{{
    "grammar_errors": [
        {{
            "original": "the incorrect phrase",
            "correction": "the correct phrase",
            "explanation": "brief friendly explanation",
            "severity": "minor|moderate|significant"
        }}
    ],
    "new_vocabulary": [
        {{
            "word": "word in target language",
            "translation": "English translation",
            "part_of_speech": "noun|verb|adjective|adverb|phrase|other"
        }}
    ]
}}

If there are no errors, return an empty array for grammar_errors.
If there's no notable vocabulary, return an empty array for new_vocabulary.
Keep explanations brief and encouraging. Maximum 3 grammar errors and 5 vocabulary words."""
```

### Chat Route Response

The `/chat` endpoint returns grammar feedback in the template response:

```python
return templates.TemplateResponse(
    "partials/message_pair.html",
    {
        "request": request,
        "ai_message": result["messages"][-1].content,
        "grammar_feedback": result.get("grammar_feedback", []),
        "new_vocabulary": result.get("new_vocabulary", []),
    }
)
```

---

## The "Gentle Nudge" Pattern

A key design philosophy for Phase 2 is the **gentle nudge pattern** - providing educational feedback without interrupting the natural conversation flow.

### How It Works

1. **Natural Response First**: The AI responds naturally to the user's message, modeling correct language usage
2. **Embedded Correction**: The AI may naturally include the correct form in its response
3. **Expandable Feedback**: A collapsible section offers deeper learning for those who want it
4. **User Control**: Learners choose when to engage with feedback

### Example Flow

```
User: "Yo soy hambre" (incorrect - "I am hunger")

AI Response: "Ah, tienes hambre? Yo tambien tengo hambre!
             Vamos a hablar de comida favorita..."

[Grammar Tips (1)] <- Collapsed by default
  |
  v (when expanded)
  +------------------------------------------+
  | "Yo soy hambre" -> "Yo tengo hambre"     |
  | We say "tengo hambre" (I have hunger)    |
  | in Spanish, not "soy hambre".            |
  +------------------------------------------+
```

### Benefits

- Conversation flow is never interrupted
- Learners don't feel "punished" for mistakes
- Feedback is available for deep learning
- Models good language naturally

---

## UI Components

### Collapsible Feedback Section

The grammar feedback UI uses Alpine.js for interactivity and provides:

1. **Toggle Button**: Shows count of grammar tips with a lightbulb icon
2. **Smooth Animation**: x-transition for enter/leave effects
3. **Semantic Structure**: Proper ARIA attributes for accessibility

```html
<button
    @click="expanded = !expanded"
    class="flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium"
    :aria-expanded="expanded"
    aria-controls="grammar-feedback-content"
>
    <!-- Lightbulb icon -->
    <span>{{ grammar_feedback|length }} grammar tip{{ 's' if grammar_feedback|length > 1 else '' }}</span>
    <!-- Chevron (rotates on expand) -->
</button>
```

### Color-Coded Severity

Visual severity indicators help learners prioritize corrections:

| Severity | Color | CSS Class | Use Case |
|----------|-------|-----------|----------|
| Minor | Sky blue | `bg-sky-500` | Small issues (accents, minor spelling) |
| Moderate | Amber | `bg-amber-500` | Common errors (gender, conjugation) |
| Significant | Rose | `bg-rose-500` | Important errors (meaning-changing) |

### Correction Display

Each correction shows:
- **Severity dot**: Color-coded indicator
- **Original**: Strikethrough text showing the error
- **Arrow**: Visual connector
- **Correction**: Highlighted correct form
- **Explanation**: Friendly tip below

```html
<div class="flex flex-wrap items-center gap-2 text-sm">
    <span class="w-2 h-2 rounded-full bg-amber-500"></span>
    <span class="line-through text-text-muted">Yo soy hambre</span>
    <svg><!-- Arrow icon --></svg>
    <span class="font-medium text-accent">Yo tengo hambre</span>
</div>
<p class="mt-1.5 ml-4 text-xs text-text-muted">
    We say "tengo hambre" in Spanish, not "soy hambre"
</p>
```

### Severity Legend

When multiple severities are present, a legend appears at the bottom:

```html
{% set severities = grammar_feedback | map(attribute='severity') | list | unique | list %}
{% if severities|length > 1 %}
<div class="flex flex-wrap gap-4 text-xs text-text-subtle">
    <div class="flex items-center gap-1.5">
        <span class="w-2 h-2 rounded-full bg-sky-500"></span>
        <span>Minor</span>
    </div>
    <!-- Moderate, Significant -->
</div>
{% endif %}
```

---

## Dependencies

### External Libraries

- `langchain-anthropic`: Claude API for grammar analysis
- `langgraph`: Sequential node execution

### Internal Modules

- `src/agent/state.py`: Extended with GrammarFeedback, VocabWord
- `src/agent/graph.py`: Updated with analyze node
- `src/agent/nodes/analyze.py`: New analyze node implementation
- `src/api/routes/chat.py`: Pass feedback to templates
- `src/templates/partials/grammar_feedback.html`: Feedback UI

---

## Implementation Details

### JSON Parsing

The analyze node must handle various LLM response formats:

```python
def _parse_analysis_response(content: str) -> tuple[list[GrammarFeedback], list[VocabWord]]:
    """Parse the LLM's JSON response into typed structures."""
    try:
        # Handle potential markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())
        # ... parse and validate ...
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
        logger.warning(f"Failed to parse analysis response: {e}")
        return [], []
```

### Severity Validation

Severity values are validated and normalized:

```python
raw_severity = error.get("severity", "minor")
if raw_severity not in ("minor", "moderate", "significant"):
    raw_severity = "minor"
severity = cast("SeverityLevel", raw_severity)
```

### Message Indexing

The analyze node must locate the user's message correctly:

```python
# User's message is at index -2 (before the AI response at -1)
if len(messages) < 2:
    return {"grammar_feedback": [], "new_vocabulary": []}

user_message = messages[-2]

if not isinstance(user_message, HumanMessage):
    return {"grammar_feedback": [], "new_vocabulary": []}
```

---

## Testing Strategy

### Unit Tests

- `test_analyze_node.py`: Test grammar analysis
  - Returns valid GrammarFeedback list
  - Handles empty user message gracefully
  - Respects level-specific guidelines
  - Validates severity normalization
  - Handles malformed JSON responses

### Integration Tests

- `test_agent_graph.py`: Test analyze node in graph
  - Phase 2 flow: respond -> analyze -> END
  - Grammar feedback appears in result state
  - Vocabulary tracking works correctly

### E2E Tests (Playwright)

- Test chat shows grammar feedback when errors exist
- Test feedback is collapsible/expandable
- Test severity colors display correctly
- Test no feedback section when no errors

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM returns invalid JSON | Medium | Low | Robust parsing with fallback to empty arrays |
| Over-correction at low levels | Medium | Medium | Strict level guidelines in prompt |
| Analysis adds too much latency | Low | Medium | Lower temperature (0.3) for faster, consistent output |
| Feedback overwhelms learners | Low | Medium | Cap at 3 errors, 5 vocab words |
| Incorrect severity classification | Low | Low | Default to "minor" for unknown values |

---

## Success Criteria

### Functional

- [ ] Grammar errors are detected appropriate to learner level
- [ ] Severity is correctly classified (minor, moderate, significant)
- [ ] Explanations are brief and encouraging
- [ ] Vocabulary words are tracked with translations
- [ ] UI displays feedback in collapsible section

### Technical

- [ ] Analyze node integrates cleanly in graph
- [ ] JSON parsing handles edge cases gracefully
- [ ] State updates flow correctly through graph
- [ ] All tests passing (target: maintain 98% coverage)

### Performance

- [ ] Analysis adds <500ms to response time
- [ ] Lower temperature (0.3) produces consistent output
- [ ] No degradation in conversation response times

---

## Appendix: LangGraph Sequential Pattern Reference

```python
from langgraph.graph import StateGraph, END

def build_graph():
    graph = StateGraph(ConversationState)

    # Add nodes
    graph.add_node("respond", respond_node)
    graph.add_node("analyze", analyze_node)  # NEW in Phase 2

    # Set entry point
    graph.set_entry_point("respond")

    # Sequential flow: respond -> analyze -> END
    graph.add_edge("respond", "analyze")
    graph.add_edge("analyze", END)

    return graph.compile()
```

This is the key LangGraph pattern learned in Phase 2 - extending a graph with additional processing nodes that update state sequentially.
