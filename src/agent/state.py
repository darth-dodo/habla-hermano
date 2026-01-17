"""
Phase 1: Minimal conversation state for HablaAI LangGraph.

This module defines the TypedDict state used by the LangGraph conversation flow.
Keeps it simple for Phase 1 - just messages, level, and language.
"""

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ConversationState(TypedDict):
    """
    Main LangGraph state for HablaAI conversations.

    Phase 1 keeps it minimal:
    - messages: Conversation history with add_messages reducer
    - level: CEFR level (A0, A1, A2, B1)
    - language: Target language code (es, de)

    The add_messages reducer handles message accumulation automatically,
    appending new messages to the existing list.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    level: str  # A0, A1, A2, B1
    language: str  # es, de
