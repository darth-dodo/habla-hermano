"""
Lesson state for the lesson delivery subgraph.

Phase 9: AI-enhanced lessons using LangGraph subgraph pattern.

This state is designed to:
1. Share keys with parent graph (messages, level, language) for integration
2. Hold lesson-specific data (step content, enhanced content, exercise feedback)
"""

from typing import Annotated, NotRequired

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class LessonState(TypedDict):
    """State for the lesson delivery subgraph.

    Shared keys (enable communication with parent conversation graph):
        messages: Conversation history (for context-aware enhancements)
        level: CEFR level (A0, A1, A2, B1)
        language: Target language code (es, de, fr)

    Lesson-specific keys:
        lesson_id: Unique identifier for the lesson
        step_index: Current step index (0-based)
        step_type: Type of step (instruction, vocabulary, example, tip, practice)
        step_content: Original content from YAML
        step_vocabulary: Vocabulary items for vocabulary steps
        enhanced_content: AI-generated additions from Hermano
        hermano_intro: Hermano's intro message for the step
        exercise_id: ID of exercise for practice steps
        user_answer: User's submitted answer for exercise validation
        exercise_feedback: AI-generated personalized feedback
        is_correct: Whether the user's answer was correct
    """

    # Shared keys with parent graph
    messages: Annotated[list[BaseMessage], add_messages]
    level: str
    language: str

    # Lesson identification
    lesson_id: str
    step_index: int

    # Step data (populated by load_step node)
    step_type: NotRequired[str]
    step_content: NotRequired[str]
    step_vocabulary: NotRequired[list[dict[str, str]]]
    step_target_text: NotRequired[str | None]
    step_translation: NotRequired[str | None]

    # AI enhancements (populated by enhance_step node)
    enhanced_content: NotRequired[str]
    hermano_intro: NotRequired[str]

    # Exercise handling
    exercise_id: NotRequired[str | None]
    user_answer: NotRequired[str | None]
    exercise_feedback: NotRequired[str | None]
    is_correct: NotRequired[bool | None]
