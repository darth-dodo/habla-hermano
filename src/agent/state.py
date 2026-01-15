"""LangGraph state definitions for HablaAI conversations.

This module defines the TypedDict state that flows through the LangGraph.
The state is designed to grow incrementally as features are added.

Phase 1 (Current): Core conversation state only
- messages: Conversation history with add_messages reducer
- level: CEFR level (A0, A1, A2, B1)
- language: Target language code (es, de)

Future phases will add:
- scaffolding: Word banks, hints for beginners
- grammar_feedback: Corrections and explanations
- new_vocabulary: Words learned in session
"""

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ConversationState(TypedDict):
    """Main LangGraph state for HablaAI conversations.

    This state flows through all nodes in the graph. Each node can read
    the full state and return a partial update dict.

    The `messages` field uses the `add_messages` reducer, which means
    returning {"messages": [new_message]} will append rather than replace.

    Attributes:
        messages: Conversation history. Uses add_messages reducer for
            automatic message accumulation.
        level: CEFR proficiency level. One of: A0, A1, A2, B1.
            Determines prompt style and scaffolding behavior.
        language: Target language code. Currently supports: es (Spanish),
            de (German - future).
    """

    messages: Annotated[list[BaseMessage], add_messages]
    level: str
    language: str
