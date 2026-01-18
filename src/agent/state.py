"""
Conversation state for Habla Hermano LangGraph.

This module defines the TypedDict state used by the LangGraph conversation flow.
Phase 2 adds grammar feedback and vocabulary tracking.
Phase 3 adds scaffolding support for A0-A1 learners.
"""

from typing import Annotated, Any, Literal, NotRequired

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class ScaffoldingConfig(BaseModel):
    """
    Scaffolding configuration for A0-A1 learners.

    Provides assistance tools to help beginner learners formulate responses:
    - Word bank: Relevant vocabulary they can use
    - Hint text: Guidance on how to respond
    - Sentence starter: A partial sentence to get them going
    - Auto-expand: Whether to show scaffolding expanded by default

    Attributes:
        enabled: Whether scaffolding is active for this response.
        word_bank: List of relevant words/phrases for the learner to use.
        hint_text: A brief tip in English on how to respond.
        sentence_starter: Optional partial sentence to help begin the response.
        auto_expand: If True (A0), show scaffolding expanded; if False (A1), collapsed.
    """

    enabled: bool = False
    word_bank: list[str] = Field(default_factory=list)
    hint_text: str = ""
    sentence_starter: str | None = None
    auto_expand: bool = False  # True for A0, False for A1


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


class ConversationState(TypedDict):
    """
    Main LangGraph state for Habla Hermano conversations.

    Core fields:
    - messages: Conversation history with add_messages reducer
    - level: CEFR level (A0, A1, A2, B1)
    - language: Target language code (es, de, fr)

    Analysis fields (Phase 2):
    - grammar_feedback: List of grammar corrections from user's last message
    - new_vocabulary: List of vocabulary words to highlight

    Scaffolding fields (Phase 3):
    - scaffolding: Dict from ScaffoldingConfig.model_dump() for A0-A1 learners

    The add_messages reducer handles message accumulation automatically,
    appending new messages to the existing list.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    level: str  # A0, A1, A2, B1
    language: str  # es, de, fr
    grammar_feedback: NotRequired[list[GrammarFeedback]]
    new_vocabulary: NotRequired[list[VocabWord]]
    scaffolding: NotRequired[dict[str, Any]]  # ScaffoldingConfig.model_dump() for A0-A1
