"""
Ollama AI Client

Implements BaseAIClient for local Ollama models.
Supports tool calling via prompt engineering.
"""

import json
from typing import List, Optional
import httpx

from .ai_client_base import (
    BaseAIClient,
    Message,
    ToolDefinition,
    ToolCall,
    AIResponse,
)


class OllamaClient(BaseAIClient):
    """
    Ollama client for local models

    Note: Ollama doesn't have native tool calling, so we use
    prompt engineering to simulate it.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "http://localhost:11434",
        model: str = "phi3:mini",  # Optimized for Intel Mac
    ):
        super().__init__(api_key, base_url)
        self.model = model
        # Much longer timeout for Intel Mac (responses can take 30-120 seconds)
        # Set both connect and read timeouts
        self.client = httpx.AsyncClient(
            base_url=base_url, 
            timeout=httpx.Timeout(120.0, connect=10.0)  # 120s read, 10s connect
        )

    def _format_tools_in_prompt(
        self, tools: List[ToolDefinition], system_prompt: str
    ) -> str:
        """
        Add tool definitions to system prompt

        Since Ollama doesn't support native tool calling, we inject
        tool descriptions into the system prompt and ask the model
        to respond with JSON when it wants to use a tool.
        """
        if not tools:
            return system_prompt

        # For Ollama, simplify tool descriptions to reduce prompt size (faster on Intel Mac)
        tools_description = "\n\n# Available Tools (use only when needed)\n\n"
        tools_description += "Format: ```json\n{\"tool\": \"name\", \"parameters\": {...}}\n```\n\n"
        
        # Only include essential tools to keep prompt short
        essential_tools = [t for t in tools if t.name in ["roll_dice", "skill_check", "attack_roll"]]
        for tool in essential_tools[:3]:  # Limit to 3 most common tools
            tools_description += f"{tool.name}: {tool.description}\n"
        
        tools_description += "\nIMPORTANT: Only use tools when absolutely necessary. Prefer narrative description.\n"
        
        return system_prompt + tools_description

    def _extract_tool_calls(self, text: str) -> tuple[Optional[str], List[ToolCall]]:
        """
        Extract tool calls from model response

        Looks for JSON blocks in the response and parses them as tool calls.
        Returns (remaining_text, tool_calls)
        """
        tool_calls = []
        import re

        # Try multiple patterns for JSON blocks
        patterns = [
            r"```json\s*(\{.*?\})\s*```",  # Standard markdown JSON
            r"```\s*(\{.*?\})\s*```",      # JSON without json label
            r"\{[^{}]*\"tool\"[^{}]*\}",    # Inline JSON with tool key
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    # Check for tool call format
                    if "tool" in data:
                        tool_name = data["tool"]
                        # Parameters might be in "parameters" key or directly in the object
                        params = data.get("parameters", {})
                        if not params and isinstance(data, dict):
                            # If no "parameters" key, use all other keys as parameters
                            params = {k: v for k, v in data.items() if k != "tool"}
                        
                        if tool_name:  # Only add if we have a tool name
                            tool_calls.append(
                                ToolCall(
                                    id=f"ollama_{len(tool_calls)}",
                                    name=tool_name,
                                    parameters=params if isinstance(params, dict) else {},
                                )
                            )
                            # Remove the JSON block from text
                            text = text.replace(f"```json\n{match}\n```", "").replace(f"```\n{match}\n```", "").replace(match, "").strip()
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
            if tool_calls:  # Stop after first successful pattern
                break

        return text if text else None, tool_calls

    async def create_message(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AIResponse:
        """Create message with Ollama"""
        
        # Skip tool formatting for speed (tools disabled for Ollama)
        # This significantly reduces prompt size and generation time
        formatted_system = system_prompt or ""

        # Build prompt
        prompt = f"{formatted_system}\n\n"
        for msg in messages:
            if msg.role == "user":
                prompt += f"User: {msg.content}\n"
            elif msg.role == "assistant":
                prompt += f"Assistant: {msg.content}\n"

        prompt += "Assistant: "

        # Call Ollama with longer timeout for Intel Mac (can take 10-30 seconds)
        response = await self.client.post(
            "/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": min(max_tokens, 200),  # Small limit for fast responses on Intel Mac
                },
            },
            timeout=120.0,  # 120 second timeout for Intel Mac (very slow)
        )

        if response.status_code != 200:
            raise Exception(f"Ollama API error: {response.status_code} - {response.text}")
        
        data = response.json()
        response_text = data.get("response", "")
        
        if not response_text:
            raise Exception(f"Ollama returned empty response: {data}")

        # Extract tool calls from response
        text_content, tool_calls = self._extract_tool_calls(response_text)

        finish_reason = "stop"
        if tool_calls:
            finish_reason = "tool_calls"
        elif data.get("done_reason") == "length":
            finish_reason = "length"

        return AIResponse(
            text=text_content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=None,  # Ollama doesn't provide token counts
        )

    async def stream_message(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        """Stream response from Ollama"""

        prompt = f"{system_prompt or ''}\n\n"
        for msg in messages:
            if msg.role == "user":
                prompt += f"User: {msg.content}\n"
            elif msg.role == "assistant":
                prompt += f"Assistant: {msg.content}\n"

        prompt += "Assistant: "

        async with self.client.stream(
            "POST",
            "/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
        ) as response:
            async for line in response.aiter_lines():
                if line:
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]
