"""Message history extraction from LangGraph checkpoints.

Provides utilities to load conversation messages from checkpoint state
for rendering when switching between threads.
"""

import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from src.agent.checkpointer import get_checkpointer
from src.agent.graph import build_graph

logger = logging.getLogger(__name__)


async def get_thread_messages(thread_id: str) -> list[dict[str, str]]:
    """Extract message history from a LangGraph checkpoint.

    Loads the checkpoint state for the given thread_id and extracts
    human and AI messages in order.

    Args:
        thread_id: The LangGraph thread_id to load messages from.

    Returns:
        List of message dicts with 'role' ('human' or 'ai') and 'content' keys.
        Empty list if no checkpoint exists or no messages found.
    """
    try:
        async with get_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            state = await graph.aget_state(RunnableConfig(configurable={"thread_id": thread_id}))
            if not state or not state.values.get("messages"):
                return []
            return [
                {
                    "role": "human" if isinstance(m, HumanMessage) else "ai",
                    "content": m.content,
                }
                for m in state.values["messages"]
                if isinstance(m, (HumanMessage, AIMessage))
            ]
    except Exception:
        logger.exception("Failed to load messages for thread %s", thread_id)
        return []
