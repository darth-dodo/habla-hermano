"""LangGraph nodes for HablaAI conversation processing.

Each node is a function that receives ConversationState and returns
a partial state update dict. Nodes are composed into the graph in graph.py.

Current nodes:
- respond: Generate AI response appropriate to user's level

Planned nodes (future phases):
- analyze: Extract grammar errors and new vocabulary
- scaffold: Generate word banks and hints for beginners
- feedback: Format and present corrections to the user
"""

from src.agent.nodes.respond import respond_node

__all__ = ["respond_node"]
