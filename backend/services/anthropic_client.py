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


class AnthropicClient(BaseAIClient):
    """Claude AI client with tool calling and prompt caching"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
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
        
        # Load additional rules (user-defined rules that supplement core D&D rules)
        additional_rules = self._load_additional_rules()
        
        # Combine core D&D rules with additional rules
        combined_dnd_rules = self.dnd_rules
        if additional_rules and additional_rules.strip():
            combined_dnd_rules = f"{self.dnd_rules}\n\n## ADDITIONAL RULES (User-Defined):\n{additional_rules}"
        
        # Format game state if provided
        game_state_text = ""
        if game_state:
            game_state_text = f"\n\nCURRENT GAME STATE:\n{self._format_game_state(game_state)}"
        
        # Cache DM prompt if caching enabled
        # Note: When using tools, system as array might cause issues, so use string format
        if self.enable_caching and not anthropic_tools:
            # When caching without tools, use array of message blocks
            system_blocks = [
                {
                    "type": "text",
                    "text": final_system_prompt,
                    "cache_control": {"type": "ephemeral"}
                },
                {
                    "type": "text",
                    "text": combined_dnd_rules,
                    "cache_control": {"type": "ephemeral"}
                }
            ]
            # Add game state (don't cache - changes each turn)
            if game_state_text:
                system_blocks.append({
                    "type": "text",
                    "text": game_state_text.strip()
                })
            system_param = system_blocks
        else:
            # No caching or using tools - combine into single string
            # (Tools work better with string system parameter)
            combined_prompt = f"{final_system_prompt}\n\n{combined_dnd_rules}{game_state_text}"
            system_param = combined_prompt

        # Call Claude
        # Build kwargs carefully - tools must be passed correctly
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anthropic_messages,
        }

        # Set system parameter (array for caching, string for non-caching)
        if system_param:
            kwargs["system"] = system_param

        # Add tools if provided
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = await self.client.messages.create(**kwargs)

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
            },
        )

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
            "temperature": temperature,
            "messages": anthropic_messages,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        async with self.client.messages.stream(**kwargs) as stream:
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
