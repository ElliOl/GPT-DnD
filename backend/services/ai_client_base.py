"""
Base class for AI clients with tool calling support

All AI providers must implement this interface to ensure
consistent behavior across different models.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class ToolDefinition(BaseModel):
    """Standard tool definition"""
    name: str
    description: str
    input_schema: Dict[str, Any]


class Message(BaseModel):
    """Standard message format"""
    role: str  # "user", "assistant", "system"
    content: Any  # Can be str, list, or dict (for tool results in Anthropic format)
    
    class Config:
        arbitrary_types_allowed = True
        # Don't validate content type strictly - allow Any
        extra = "allow"


class ToolCall(BaseModel):
    """Tool call request from AI"""
    id: str
    name: str
    parameters: Dict[str, Any]


class AIResponse(BaseModel):
    """Standardized response from AI"""
    text: Optional[str] = None
    tool_calls: List[ToolCall] = []
    finish_reason: str  # "stop", "tool_calls", "length"
    usage: Optional[Dict[str, int]] = None


class BaseAIClient(ABC):
    """
    Base class for all AI providers

    Ensures consistent interface across Anthropic, OpenAI,
    Ollama, LM Studio, and OpenRouter.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    async def create_message(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        model: Optional[str] = None,
        force_tool: Optional[str] = None,
    ) -> AIResponse:
        """
        Create a message with optional tool calling

        Args:
            messages: Conversation history
            tools: Available tools for the AI to call
            system_prompt: System instructions
            temperature: Randomness (0-1)
            max_tokens: Max response length
            model: Override the client's default model for this call. Used by the
                multi-agent stack to route cheap agents to cheap models; ignored
                by callers that only ever want one model.
            force_tool: Name of a tool in `tools` the model MUST call, rather than
                choosing to respond with plain text instead. Used by agents whose
                only valid output is a tool call (Intent, Scribe) — without it,
                the model is always free to just answer conversationally, which
                for those agents is a failure, not an alternative. Providers or
                models that cannot force tool choice should fall back to their
                normal "auto" behavior rather than erroring; the caller already
                retries and degrades when a forced call still doesn't arrive.

        Returns:
            AIResponse with text and/or tool calls
        """
        pass

    @abstractmethod
    async def stream_message(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        """
        Stream response tokens as they're generated

        Yields text chunks for real-time display
        """
        pass
