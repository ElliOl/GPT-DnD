"""
OpenAI AI Client

Implements BaseAIClient for GPT models with function calling support.
"""

import os
import json
from typing import List, Optional
from openai import AsyncOpenAI

from .ai_client_base import (
    BaseAIClient,
    Message,
    ToolDefinition,
    ToolCall,
    AIResponse,
)


class OpenAIClient(BaseAIClient):
    """OpenAI GPT client with function calling"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-4-turbo-preview",
    ):
        super().__init__(api_key, base_url)
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url,
        )

    async def create_message(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AIResponse:
        """Create message with OpenAI"""

        # Convert messages to OpenAI format
        openai_messages = []

        # Add system prompt if provided
        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})

        # Add conversation messages
        for msg in messages:
            openai_messages.append({"role": msg.role, "content": msg.content})

        # Convert tools to OpenAI function calling format
        functions = None
        if tools:
            functions = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
                for tool in tools
            ]

        # Call OpenAI
        kwargs = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if functions:
            kwargs["tools"] = functions
            kwargs["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**kwargs)

        # Parse response
        message = response.choices[0].message
        text_content = message.content
        tool_calls = []

        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        parameters=json.loads(tc.function.arguments),
                    )
                )

        # Determine finish reason
        finish_reason = "stop"
        if tool_calls:
            finish_reason = "tool_calls"
        elif response.choices[0].finish_reason == "length":
            finish_reason = "length"

        return AIResponse(
            text=text_content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            },
        )

    async def stream_message(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        """Stream response from OpenAI"""

        openai_messages = []

        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            openai_messages.append({"role": msg.role, "content": msg.content})

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
