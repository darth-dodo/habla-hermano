"""
Conversation state for HablaAI LangGraph.

This module defines the TypedDict state used by the LangGraph conversation flow.
Phase 2 adds grammar feedback and vocabulary tracking.
"""

from typing import Annotated, Literal, NotRequired

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


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
    Main LangGraph state for HablaAI conversations.

    Core fields:
    - messages: Conversation history with add_messages reducer
    - level: CEFR level (A0, A1, A2, B1)
    - language: Target language code (es, de, fr)

    Analysis fields (Phase 2):
    - grammar_feedback: List of grammar corrections from user's last message
    - new_vocabulary: List of vocabulary words to highlight

    The add_messages reducer handles message accumulation automatically,
    appending new messages to the existing list.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    level: str  # A0, A1, A2, B1
    language: str  # es, de, fr
    grammar_feedback: NotRequired[list[GrammarFeedback]]
    new_vocabulary: NotRequired[list[VocabWord]]
