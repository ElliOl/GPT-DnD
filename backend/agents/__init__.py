"""
Agents. Every LLM call in the system goes through one.

Only the Narrator speaks to players; everything else produces structured data.
"""

from .base import Agent, AgentContext, AgentFailed, AgentSkipped

__all__ = ["Agent", "AgentContext", "AgentFailed", "AgentSkipped"]
