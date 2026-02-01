# Phase 9: AI-Enhanced Lessons with LangGraph Subgraph

> Dynamic lesson content generation using Hermano as the teacher within a reusable subgraph

---

## Overview

Phase 9 combines two powerful concepts:
1. **AI-Generated Content**: Hermano dynamically generates examples, explanations, and variations within lessons
2. **LangGraph Subgraph**: A reusable lesson delivery graph that can be invoked from the main conversation graph

**Learning Goals**:
- Master LangGraph subgraph composition pattern
- Implement AI-augmented structured content delivery
- Create a hybrid approach: YAML structure + AI-generated content

---

## Architecture

### Current vs. New Lesson Flow

**Current (Phase 6)**: Static YAML → Template Rendering
```
YAML File → LessonService → Template → HTML
```

**New (Phase 9)**: YAML Structure + AI Enhancement
```
YAML Structure → Lesson Subgraph → AI-Enhanced Content → Template → HTML

Lesson Subgraph:
├── load_step: Load step from YAML
├── enhance_step: Hermano adds context, examples, encouragement
└── validate_exercise: Check answers with personalized feedback
```

### Subgraph Design

```
┌─────────────────────────────────────────────────────────────────┐
│                      LESSON SUBGRAPH                             │
│                                                                  │
│  ┌──────────────┐                                               │
│  │   START      │                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │  load_step   │ ← Load step data from YAML                    │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │ enhance_step │ ← Hermano generates contextual content        │
│  │              │   - Additional examples                        │
│  │              │   - Cultural notes                            │
│  │              │   - Personalized encouragement                │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │     END      │                                               │
│  └──────────────┘                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### State Definition

```python
class LessonState(TypedDict):
    """State for lesson subgraph."""

    # Shared with parent (if invoked from conversation)
    messages: Annotated[list[BaseMessage], add_messages]
    level: str
    language: str

    # Lesson-specific
    lesson_id: str
    step_index: int
    step_data: dict  # Raw step from YAML
    enhanced_content: str  # AI-generated additions
    exercise_feedback: str | None  # Personalized exercise feedback
```

---

## Implementation Plan

### Task 1: Lesson State and Subgraph Module

**File**: `src/agent/lesson_state.py`

```python
from typing import Annotated, Any
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class LessonState(TypedDict):
    """State for the lesson delivery subgraph."""

    # Shared keys (enable communication with parent graph)
    messages: Annotated[list[BaseMessage], add_messages]
    level: str
    language: str

    # Lesson-specific keys
    lesson_id: str
    step_index: int
    step_type: str  # instruction, vocabulary, example, tip, practice
    step_content: str  # Original content from YAML
    step_vocabulary: list[dict[str, str]]  # For vocabulary steps
    enhanced_content: str  # AI-generated additions
    hermano_intro: str  # Hermano's intro for the step
    exercise_id: str | None
    user_answer: str | None
    exercise_feedback: str | None
    is_correct: bool | None
```

### Task 2: Lesson Nodes

**File**: `src/agent/nodes/lesson.py`

```python
async def load_step_node(state: LessonState) -> dict:
    """Load step data from lesson service.

    Reads the current step from YAML and populates state fields.
    """
    service = get_lesson_service()
    lesson = service.get_lesson(state["lesson_id"])
    steps = lesson.content.get_ordered_steps()
    step = steps[state["step_index"]]

    return {
        "step_type": step.type.value,
        "step_content": step.content,
        "step_vocabulary": step.vocabulary,
        "exercise_id": step.exercise_id,
    }


async def enhance_step_node(state: LessonState) -> dict:
    """Hermano enhances the step with dynamic content.

    Based on step type, generates:
    - instruction: Warm intro + additional context
    - vocabulary: Example sentences using the words
    - example: Alternative phrasings
    - tip: Cultural anecdotes
    - practice: Encouragement before exercise
    """
    llm = _get_llm()

    prompt = get_lesson_enhance_prompt(
        language=state["language"],
        level=state["level"],
        step_type=state["step_type"],
        step_content=state["step_content"],
        vocabulary=state["step_vocabulary"],
    )

    response = await llm.ainvoke([SystemMessage(content=prompt)])

    return {
        "enhanced_content": response.content,
        "hermano_intro": extract_intro(response.content),
    }


async def validate_exercise_node(state: LessonState) -> dict:
    """Validate exercise answer with personalized feedback from Hermano.

    Goes beyond correct/incorrect to provide:
    - Encouragement on correct answers
    - Helpful hints on incorrect answers
    - Cultural context when relevant
    """
    if not state.get("user_answer"):
        return {}

    service = get_lesson_service()
    lesson = service.get_lesson(state["lesson_id"])
    exercise = lesson.content.get_exercise_by_id(state["exercise_id"])

    # Check correctness
    is_correct = check_answer(exercise, state["user_answer"])

    # Generate personalized feedback
    llm = _get_llm()
    feedback_prompt = get_exercise_feedback_prompt(
        language=state["language"],
        level=state["level"],
        exercise=exercise,
        user_answer=state["user_answer"],
        is_correct=is_correct,
    )

    response = await llm.ainvoke([SystemMessage(content=feedback_prompt)])

    return {
        "is_correct": is_correct,
        "exercise_feedback": response.content,
    }
```

### Task 3: Lesson Subgraph Builder

**File**: `src/agent/lesson_graph.py`

```python
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.lesson_state import LessonState
from src.agent.nodes.lesson import (
    load_step_node,
    enhance_step_node,
    validate_exercise_node,
)


def build_lesson_subgraph() -> CompiledStateGraph:
    """Build the lesson delivery subgraph.

    Flow:
        START → load_step → enhance_step → END

    For exercise validation (separate invocation):
        START → validate_exercise → END
    """
    graph = StateGraph(LessonState)

    # Add nodes
    graph.add_node("load_step", load_step_node)
    graph.add_node("enhance_step", enhance_step_node)

    # Define flow
    graph.set_entry_point("load_step")
    graph.add_edge("load_step", "enhance_step")
    graph.add_edge("enhance_step", END)

    return graph.compile()


def build_exercise_validation_graph() -> CompiledStateGraph:
    """Build exercise validation subgraph.

    Separate graph for validating exercise answers with AI feedback.
    """
    graph = StateGraph(LessonState)

    graph.add_node("validate_exercise", validate_exercise_node)
    graph.set_entry_point("validate_exercise")
    graph.add_edge("validate_exercise", END)

    return graph.compile()


# Pre-compiled instances
lesson_subgraph = build_lesson_subgraph()
exercise_validation_graph = build_exercise_validation_graph()
```

### Task 4: Lesson Enhancement Prompts

**File**: `src/agent/prompts.py` (additions)

```python
LESSON_ENHANCE_PROMPTS = {
    "instruction": """
You are Hermano, the friendly language tutor. You're about to introduce a new concept.

Language: {language_name}
Level: {level}
Topic: {step_content}

Add a warm, encouraging intro (2-3 sentences) that:
- Makes the learner feel excited about what they're about to learn
- Relates the topic to real-life situations
- Uses your signature casual, supportive tone

Then provide 1-2 additional context points that weren't in the original content.
""",

    "vocabulary": """
You are Hermano teaching vocabulary. Make these words memorable!

Language: {language_name}
Level: {level}
Words: {vocabulary}

For each word, add:
- A simple example sentence using the word (appropriate for {level} level)
- A memory tip or association (optional, only if natural)

Keep it fun and casual. Use your supportive big-brother voice.
""",

    "example": """
You are Hermano showing how a phrase is used in real life.

Language: {language_name}
Level: {level}
Example: {step_content}

Add:
- One alternative way to say the same thing
- A brief note on when you'd use this (formal/informal, region, etc.)

Keep explanations short and relatable.
""",

    "tip": """
You are Hermano sharing a cultural tip or learning insight.

Language: {language_name}
Level: {level}
Tip: {step_content}

Expand with:
- A personal anecdote or "I remember when..." moment
- Why this matters for real conversations

Keep it warm and conversational.
""",

    "practice": """
You are Hermano encouraging the learner before an exercise.

Language: {language_name}
Level: {level}
Exercise topic: {step_content}

Give a brief (1-2 sentence) pep talk that:
- Builds confidence
- Reminds them it's okay to make mistakes
- Uses your signature encouraging tone
""",
}


def get_lesson_enhance_prompt(
    language: str,
    level: str,
    step_type: str,
    step_content: str,
    vocabulary: list[dict[str, str]] | None = None,
) -> str:
    """Get the enhancement prompt for a lesson step."""
    prompt_template = LESSON_ENHANCE_PROMPTS.get(step_type, LESSON_ENHANCE_PROMPTS["instruction"])
    lang_data = LANGUAGE_ADAPTER.get(language, LANGUAGE_ADAPTER["es"])

    vocab_str = ""
    if vocabulary:
        vocab_str = "\n".join(f"- {v['word']}: {v['translation']}" for v in vocabulary)

    return prompt_template.format(
        language_name=lang_data["language_name"],
        level=level,
        step_content=step_content,
        vocabulary=vocab_str,
    )
```

### Task 5: Updated Lesson Routes

**File**: `src/api/routes/lessons.py` (updates)

```python
@router.get("/{lesson_id}/step/{step_index}/enhanced", response_class=HTMLResponse)
async def get_enhanced_lesson_step(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    lesson_id: str,
    step_index: int,
    level: str = "A1",
    language: str = "es",
) -> HTMLResponse:
    """Get AI-enhanced lesson step content.

    Uses the lesson subgraph to:
    1. Load the step from YAML
    2. Have Hermano enhance it with dynamic content
    """
    from src.agent.lesson_graph import lesson_subgraph

    result = await lesson_subgraph.ainvoke({
        "lesson_id": lesson_id,
        "step_index": step_index,
        "level": level,
        "language": language,
        "messages": [],
    })

    return templates.TemplateResponse(
        request=request,
        name="partials/lesson_step_enhanced.html",
        context={
            "step_type": result["step_type"],
            "step_content": result["step_content"],
            "enhanced_content": result["enhanced_content"],
            "hermano_intro": result["hermano_intro"],
            "vocabulary": result.get("step_vocabulary", []),
            "step_index": step_index,
            "lesson_id": lesson_id,
        },
    )


@router.post("/{lesson_id}/exercise/{exercise_id}/submit/enhanced", response_class=HTMLResponse)
async def submit_exercise_enhanced(
    request: Request,
    templates: TemplatesDep,
    user: OptionalUserDep,
    lesson_id: str,
    exercise_id: str,
    answer: str = Form(...),
    level: str = Form("A1"),
    language: str = Form("es"),
) -> HTMLResponse:
    """Submit exercise with AI-generated personalized feedback."""
    from src.agent.lesson_graph import exercise_validation_graph

    result = await exercise_validation_graph.ainvoke({
        "lesson_id": lesson_id,
        "exercise_id": exercise_id,
        "user_answer": answer,
        "level": level,
        "language": language,
        "messages": [],
    })

    return templates.TemplateResponse(
        request=request,
        name="partials/exercise_feedback_enhanced.html",
        context={
            "is_correct": result["is_correct"],
            "feedback": result["exercise_feedback"],
            "lesson_id": lesson_id,
            "exercise_id": exercise_id,
        },
    )
```

### Task 6: Enhanced Templates

**File**: `src/templates/partials/lesson_step_enhanced.html`

```html
<div class="lesson-step enhanced">
    <!-- Hermano's intro -->
    <div class="hermano-intro bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg mb-4">
        <div class="flex items-start gap-3">
            <span class="text-2xl">🤙</span>
            <p class="text-gray-700 dark:text-gray-300 italic">
                {{ hermano_intro }}
            </p>
        </div>
    </div>

    <!-- Original step content -->
    <div class="step-content mb-4">
        {% if step_type == "vocabulary" %}
            {% include "partials/vocabulary_grid.html" %}
        {% elif step_type == "example" %}
            {% include "partials/example_block.html" %}
        {% else %}
            <p class="text-gray-800 dark:text-gray-200">{{ step_content }}</p>
        {% endif %}
    </div>

    <!-- AI-enhanced additions -->
    {% if enhanced_content %}
    <div class="enhanced-content bg-green-50 dark:bg-green-900/20 p-4 rounded-lg border-l-4 border-green-500">
        <p class="text-sm text-gray-600 dark:text-gray-400 mb-2">
            <span class="font-medium">Hermano adds:</span>
        </p>
        <div class="text-gray-700 dark:text-gray-300 prose prose-sm dark:prose-invert">
            {{ enhanced_content | safe }}
        </div>
    </div>
    {% endif %}
</div>
```

---

## Integration with Main Graph (Future)

Once the lesson subgraph is working standalone, it can be integrated into the main conversation graph:

```python
def build_graph_with_lessons(checkpointer=None):
    """Main graph that can route to lesson subgraph."""

    graph = StateGraph(ConversationState)

    # Existing nodes
    graph.add_node("respond", respond_node)
    graph.add_node("scaffold", scaffold_node)
    graph.add_node("analyze", analyze_node)

    # Add lesson subgraph as a node
    graph.add_node("lesson", lesson_subgraph)

    # Routing logic could detect "let's do a lesson" requests
    # and route to the lesson subgraph

    return graph.compile(checkpointer=checkpointer)
```

---

## Testing Strategy

### Unit Tests
- `test_load_step_node`: Verify YAML loading
- `test_enhance_step_node`: Verify AI content generation
- `test_validate_exercise_node`: Verify answer checking + feedback

### Integration Tests
- `test_lesson_subgraph_flow`: Full subgraph invocation
- `test_enhanced_step_endpoint`: API endpoint with AI content
- `test_exercise_feedback_enhanced`: Personalized feedback generation

### E2E Tests
- Navigate to lesson, see AI-enhanced content
- Submit exercise, receive personalized feedback
- Verify Hermano's voice consistency

---

## Success Criteria

- [ ] Lesson subgraph compiles and runs standalone
- [ ] AI-enhanced content appears for each step type
- [ ] Exercise feedback is personalized by Hermano
- [ ] Hermano's voice is consistent with chat personality
- [ ] Response time < 3s for enhanced steps (acceptable for AI generation)
- [ ] All existing tests pass
- [ ] New tests achieve 90%+ coverage on lesson subgraph

---

## File Summary

| File | Action | Description |
|------|--------|-------------|
| `src/agent/lesson_state.py` | Create | LessonState TypedDict |
| `src/agent/nodes/lesson.py` | Create | load_step, enhance_step, validate_exercise nodes |
| `src/agent/lesson_graph.py` | Create | Subgraph builder and compiled instances |
| `src/agent/prompts.py` | Modify | Add LESSON_ENHANCE_PROMPTS |
| `src/api/routes/lessons.py` | Modify | Add enhanced endpoints |
| `src/templates/partials/lesson_step_enhanced.html` | Create | Enhanced step template |
| `src/templates/partials/exercise_feedback_enhanced.html` | Create | Enhanced feedback template |
| `tests/test_lesson_subgraph.py` | Create | Unit and integration tests |
