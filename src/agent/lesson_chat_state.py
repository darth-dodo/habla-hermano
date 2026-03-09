"""
State model for conversational lesson delivery (Phase 19).

This module defines the LessonChatState TypedDict used by the LangGraph
lesson chat subgraph. It mirrors all fields from ConversationState and adds
lesson-specific tracking fields for phase progression, exercise evaluation,
and scoring.

Lesson phases flow linearly:
    intro -> teaching -> exercise_ask -> exercise_eval -> complete

The teaching phase delivers lesson steps in batches of STEP_BATCH_SIZE,
advancing step_index each turn until all steps are covered.
"""

from typing import Annotated, Any, Literal, NotRequired

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from src.agent.state import (
    GrammarFeedback,
    PronunciationTip,
    ReviewWordOffered,
    ReviewWordUsed,
    VocabWord,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LESSON_PHASES = Literal["intro", "teaching", "exercise_ask", "exercise_eval", "complete"]
"""Valid phases for conversational lesson delivery."""

STEP_BATCH_SIZE: int = 3
"""Maximum number of lesson steps presented per teaching turn."""


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class LessonChatState(TypedDict):
    """
    LangGraph state for conversational lesson delivery.

    Inherits the same field set as ConversationState so that shared
    nodes (scaffold, analyze) can operate on either state shape.

    Core fields (from ConversationState):
    - messages: Conversation history with add_messages reducer
    - level: CEFR level (A0, A1, A2, B1)
    - language: Target language code (es, de, fr)
    - user_id: User UUID for database access
    - supabase_client: User-scoped Supabase client for RLS-safe DB access
    - grammar_feedback: Grammar corrections from user's last message
    - new_vocabulary: Vocabulary words to highlight
    - scaffolding: ScaffoldingConfig.model_dump() for A0-A1 learners
    - pronunciation_tips: Pronunciation tips for words in the response
    - review_words_offered: Words offered for chat weaving
    - review_words_used: Words successfully used by learner

    Lesson tracking fields (Phase 19):
    - lesson_id: Unique lesson identifier (e.g. "es_a1_greetings_01")
    - lesson_data: Serialized Lesson model (Lesson.model_dump())
    - lesson_phase: Current delivery phase (one of LESSON_PHASES)
    - step_index: Current position in ordered steps (0-based)
    - exercise_index: Current position in exercises (0-based)
    - exercise_results: Accumulated exercise outcomes for scoring
    - lesson_score: Running score 0-100
    - lesson_ui: SSE payload for progress bar, exercise feedback, completion
    - lesson_completed: Flag signalling post-stream persistence is needed
    """

    # === Core conversation fields ===
    messages: Annotated[list[BaseMessage], add_messages]
    level: str  # A0, A1, A2, B1
    language: str  # es, de, fr
    user_id: NotRequired[str]
    supabase_client: NotRequired[Any]
    grammar_feedback: NotRequired[list[GrammarFeedback]]
    new_vocabulary: NotRequired[list[VocabWord]]
    scaffolding: NotRequired[dict[str, Any]]
    pronunciation_tips: NotRequired[list[PronunciationTip]]
    review_words_offered: NotRequired[list[ReviewWordOffered]]
    review_words_used: NotRequired[list[ReviewWordUsed]]

    # === Lesson tracking ===
    lesson_id: str
    lesson_data: dict[str, Any]
    lesson_phase: str  # One of LESSON_PHASES
    step_index: int
    exercise_index: int
    exercise_results: list[dict[str, Any]]  # [{exercise_id, is_correct, user_answer}]
    lesson_score: int  # Running score 0-100
    lesson_ui: NotRequired[dict[str, Any]]  # SSE: progress bar, exercise feedback, completion
    lesson_completed: NotRequired[bool]  # Flag for post-stream persistence
