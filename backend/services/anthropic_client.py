"""
Anthropic Claude AI Client

Implements BaseAIClient for Claude models with tool calling support.
Includes prompt caching for cost optimization.
"""

import os
from typing import List, Optional, Dict, Any
from anthropic import AsyncAnthropic
import anthropic
from pathlib import Path

from .ai_client_base import (
    BaseAIClient,
    Message,
    ToolDefinition,
    ToolCall,
    AIResponse,
)


# Fast-path only, not the source of truth: models already known to reject
# sampling params outright (400 invalid_request_error) rather than just
# deprecating a default. Skipping this set entirely would still work — it just
# costs one wasted round trip the first time a new model is used. The set below,
# `_learned_no_sampling_models`, is what keeps this correct without maintenance:
# it's populated live from the API's own response the first time a model
# rejects a sampling param, so a model added here later, or Haiku changing
# behavior in some future release, is handled without a code change.
_KNOWN_NO_SAMPLING_MODELS = {"claude-sonnet-5", "claude-opus-5"}

#: Process-lifetime cache of models discovered at runtime to reject sampling
#: params. Shared across all AnthropicClient instances in this process, since
#: the rejection is a property of the model, not of any one client.
_learned_no_sampling_models: set[str] = set()

#: Parameters Claude 5 Sonnet/Opus reject together as a group; Haiku 4.5 still
#: accepts all three. `anthropic_client.py` only ever sends `temperature`, but
#: the other two are stripped too if a caller ever adds them.
_SAMPLING_PARAMS = ("temperature", "top_p", "top_k")


def _token_count(usage: Any, field: str) -> int:
    """A usage field as an int, or 0. Older SDKs omit the cache fields
    entirely and test doubles hand back whatever they like, so anything
    that isn't a real number counts as none."""
    value = getattr(usage, field, 0)
    return value if isinstance(value, int) else 0


def _supports_temperature(model: str) -> bool:
    return model not in _KNOWN_NO_SAMPLING_MODELS and model not in _learned_no_sampling_models


def _rejected_sampling_param(exc: "anthropic.BadRequestError") -> bool:
    """Best-effort read of a 400 body: does this look like a sampling-param
    rejection rather than some other bad request?

    There is no documented, structured error code for this — Anthropic's 400
    body is a generic ``invalid_request_error``, and the only available signal
    is that the message conventionally names the offending field (as is
    standard for the vast majority of JSON APIs, though not a documented
    guarantee here). If a future response ever stops matching this — different
    wording, a different field — the exception simply propagates unchanged;
    this never swallows a 400 it isn't sure about.
    """
    message = str(getattr(exc, "message", "") or exc)
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        message = f"{message} {(body.get('error') or {}).get('message', '')}"
    message = message.lower()
    return any(param in message for param in _SAMPLING_PARAMS)


def _without_sampling_params(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in kwargs.items() if k not in _SAMPLING_PARAMS}


class AnthropicClient(BaseAIClient):
    """Claude AI client with tool calling and prompt caching"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "claude-sonnet-5",
    ):
        super().__init__(api_key, base_url)
        self.model = model
        self.client = AsyncAnthropic(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
            base_url=base_url,
        )
        
        # Prompt caching settings
        self.enable_caching = os.getenv("ENABLE_PROMPT_CACHING", "true").lower() == "true"
        
        # Load cached content (DM prompt and D&D rules)
        self.dm_system_prompt = self._load_dm_prompt()
        self.dnd_rules = self._load_dnd_rules()

    def _load_dm_prompt(self) -> str:
        """Load DM system prompt from file or use default"""
        prompt_path = Path(__file__).parent.parent / "prompts" / "dm_system_prompt.txt"
        if prompt_path.exists():
            return prompt_path.read_text()
        # Fallback to a basic prompt if file doesn't exist
        return "You are an expert D&D 5e Dungeon Master. Use tools for all game mechanics."

    def _load_dnd_rules(self) -> str:
        """Load D&D 5e rules from file"""
        rules_path = Path(__file__).parent.parent / "prompts" / "dnd_rules.txt"
        if rules_path.exists():
            return rules_path.read_text(encoding='utf-8')
        # Fallback to minimal rules if file doesn't exist
        return """D&D 5e RULES:
- Ability checks: d20 + modifier + proficiency vs DC (5/10/15/20/25+)
- Combat: d20 + attack bonus vs AC, nat20=crit, nat1=miss
- 0 HP = unconscious (death saves: 10+=success, 9-=failure, 3 of either = result)
- Use tools for ALL mechanics."""

    def _load_additional_rules(self) -> str:
        """Load additional user-defined rules that supplement core D&D rules"""
        from pathlib import Path
        additional_rules_path = Path(__file__).parent.parent.parent / "data" / "additional_rules.txt"
        if additional_rules_path.exists():
            return additional_rules_path.read_text(encoding='utf-8')
        return ""

    async def create_message(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        context_type: Optional[str] = None,
        game_state: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        force_tool: Optional[str] = None,
    ) -> AIResponse:
        """
        Create message with Claude
        
        Args:
            messages: Conversation history
            tools: Available tools
            system_prompt: Optional system prompt (if None, uses cached DM prompt)
            temperature: Randomness
            max_tokens: Max response length (can be overridden by context_type)
            context_type: Type of response needed (adjusts max_tokens dynamically)
                - "scene_description": Entering new area (3-5 sentences)
                - "combat_action": Attack/spell in combat (1-2 sentences)
                - "npc_dialogue": Talking to NPCs (2-3 sentences)
                - "skill_check": Investigation/Perception result (1-2 sentences)
                - "exploration": Looking around (2-4 sentences)
                - "standard": Default (2-3 sentences)
            game_state: Current game state (for context)
        """

        # Dynamic token limits based on context
        if context_type:
            token_limits = {
                "scene_description": 500,    # Entering new area - detailed (increased from 400)
                "combat_action": 150,         # Attack, spell in combat - brief!
                "npc_dialogue": 250,          # Talking to NPCs - moderate
                "skill_check": 150,           # Investigation, Perception - short
                "exploration": 350,           # Looking around - medium detail (increased from 300)
                "standard": 200               # Default
            }
            max_tokens = token_limits.get(context_type, max_tokens)

        # Convert messages to Anthropic format
        # Handle both string content and complex content (for tool results)
        anthropic_messages = []
        for msg in messages:
            if msg.role == "system":
                continue  # System goes in separate param
            
            # Message is a Pydantic model, access attributes directly
            content = msg.content
            
            # Check if content is empty (Anthropic API doesn't allow empty messages)
            is_empty = False
            if isinstance(content, str):
                is_empty = not content or not content.strip()
            elif isinstance(content, (dict, list)):
                # For complex content, check if it's empty
                is_empty = len(content) == 0
            else:
                # Fallback: convert to string and check
                content_str = str(content) if content else ""
                is_empty = not content_str or not content_str.strip()
            
            if is_empty:
                print(f"⚠️  Skipping {msg.role} message with empty content in Anthropic client")
                continue
            
            # If content is already a dict/list (tool results), use it directly
            # Otherwise, use string content as-is
            if isinstance(content, (dict, list)):
                anthropic_messages.append({
                    "role": msg.role,
                    "content": content
                })
            elif isinstance(content, str):
                # String content - use as-is
                anthropic_messages.append({
                    "role": msg.role,
                    "content": content
                })
            else:
                # Fallback: convert to string
                anthropic_messages.append({
                    "role": msg.role,
                    "content": str(content)
                })

        # Convert tools to Anthropic format
        anthropic_tools = None
        if tools:
            anthropic_tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in tools
            ]

        # Build system messages with caching
        # Use provided system prompt or default to cached DM prompt
        final_system_prompt = system_prompt or self.dm_system_prompt

        # The D&D rules belong to the DM persona, not to every caller. An agent
        # that brought its own system prompt gets exactly that — the Intent
        # parser has no use for combat rules, and appending them was both spend
        # and a source of instructions that contradict its actual job.
        combined_dnd_rules = ""
        if system_prompt is None:
            additional_rules = self._load_additional_rules()
            combined_dnd_rules = self.dnd_rules
            if additional_rules and additional_rules.strip():
                combined_dnd_rules = f"{self.dnd_rules}\n\n## ADDITIONAL RULES (User-Defined):\n{additional_rules}"

        # Format game state if provided
        game_state_text = ""
        if game_state:
            game_state_text = f"\n\nCURRENT GAME STATE:\n{self._format_game_state(game_state)}"
        
        # Cache the stable prefix. Tools used to be excluded here on the belief
        # that an array `system` breaks alongside them; it doesn't — verified
        # against the live API. Caching simply won't engage for prompts under
        # the model's minimum cacheable size, which is its own affair.
        if self.enable_caching:
            # When caching, use array of message blocks
            system_blocks = [
                {
                    "type": "text",
                    "text": final_system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ]
            if combined_dnd_rules:
                system_blocks.append({
                    "type": "text",
                    "text": combined_dnd_rules,
                    "cache_control": {"type": "ephemeral"}
                })
            # Add game state (don't cache - changes each turn)
            if game_state_text:
                system_blocks.append({
                    "type": "text",
                    "text": game_state_text.strip()
                })
            system_param = system_blocks
        else:
            # Caching off — one string, same content.
            parts = [p for p in (final_system_prompt, combined_dnd_rules) if p]
            system_param = "\n\n".join(parts) + game_state_text

        # Call Claude
        # Build kwargs carefully - tools must be passed correctly
        resolved_model = model or self.model
        kwargs = {
            "model": resolved_model,
            "max_tokens": max_tokens,
            "messages": anthropic_messages,
        }
        if _supports_temperature(resolved_model):
            kwargs["temperature"] = temperature

        # Set system parameter (array for caching, string for non-caching)
        if system_param:
            kwargs["system"] = system_param

        # Add tools if provided
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools
            if force_tool:
                kwargs["tool_choice"] = {"type": "tool", "name": force_tool}

        response = await self._create_with_sampling_fallback(kwargs)

        # Parse response
        text_content = None
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_content = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        parameters=block.input,
                    )
                )

        # Determine finish reason
        finish_reason = "stop"
        if tool_calls:
            finish_reason = "tool_calls"
        elif response.stop_reason == "max_tokens":
            finish_reason = "length"

        return AIResponse(
            text=text_content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                # Billed, and reported separately from input_tokens — dropping
                # these made every cached call look almost free. The Narrator's
                # whole system prefix was invisible to /cost.
                "cache_write_tokens": _token_count(response.usage, "cache_creation_input_tokens"),
                "cache_read_tokens": _token_count(response.usage, "cache_read_input_tokens"),
            },
        )

    async def _create_with_sampling_fallback(self, kwargs: Dict[str, Any]):
        """``messages.create``, self-healing against sampling-param rejection.

        The `_KNOWN_NO_SAMPLING_MODELS` fast path already skips this for models
        we've seen before, so this only fires the first time a given model
        rejects temperature — after that ``_supports_temperature`` catches it
        up front and this whole path is skipped again.
        """
        try:
            return await self.client.messages.create(**kwargs)
        except anthropic.BadRequestError as exc:
            if not _rejected_sampling_param(exc):
                raise
            _learned_no_sampling_models.add(kwargs.get("model", self.model))
            return await self.client.messages.create(**_without_sampling_params(kwargs))

    async def stream_message(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        """Stream response from Claude"""

        anthropic_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
            if msg.role != "system"
        ]

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": anthropic_messages,
        }
        if _supports_temperature(self.model):
            kwargs["temperature"] = temperature

        if system_prompt:
            kwargs["system"] = system_prompt

        try:
            async with self.client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.BadRequestError as exc:
            if not _rejected_sampling_param(exc):
                raise
            # Nothing will have streamed yet — invalid_request_error is a
            # request-validation failure, raised before any content is sent.
            _learned_no_sampling_models.add(kwargs.get("model", self.model))
            async with self.client.messages.stream(**_without_sampling_params(kwargs)) as stream:
                async for text in stream.text_stream:
                    yield text

    def _format_game_state(self, state: Dict[str, Any]) -> str:
        """Format game state for context"""
        parts = []
        
        if "location" in state:
            parts.append(f"Location: {state['location']}")
        
        if "active_encounter" in state:
            parts.append(f"Active Encounter: {state['active_encounter']}")
        
        if "party" in state:
            parts.append(f"Party: {', '.join(state['party'])}")
        
        if "combat_active" in state:
            parts.append(f"Combat Active: {state['combat_active']}")
        
        return "\n".join(parts) if parts else "No active game state"
