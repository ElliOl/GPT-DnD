"""
DM Agent - The AI Dungeon Master

Handles player input, manages conversation with AI,
and executes game mechanics through tool calling.
"""

import json
from typing import List, Dict, Any, Optional
from pathlib import Path

from .ai_client_base import BaseAIClient, Message, ToolDefinition
from ..models.game_state import GameState


class DMAgent:
    """
    AI Dungeon Master Agent

    Manages the conversation with the AI and executes game mechanics.
    The AI has access to D&D tools (dice rolling, skill checks, combat, etc.)
    """

    def __init__(
        self,
        ai_client: BaseAIClient,
        game_engine,
        tts_service,
        system_prompt: Optional[str] = None,
        adventure_context=None,
    ):
        self.ai_client = ai_client
        self.game_engine = game_engine
        self.tts_service = tts_service
        self.adventure_context = adventure_context
        self.conversation_history: List[Message] = []

        # Load system prompt (DM personality and rules)
        if system_prompt:
            self.system_prompt = system_prompt
        else:
            prompt_path = Path(__file__).parent.parent / "prompts" / "dm_system_prompt.txt"
            if prompt_path.exists():
                self.system_prompt = prompt_path.read_text()
            else:
                self.system_prompt = self._default_system_prompt()

        # Define tools available to the AI
        self.tools = self._define_tools()

    def _detect_context(self, action: str, game_state: Dict[str, Any]) -> str:
        """
        Detect what kind of response is needed based on player action
        
        This determines the appropriate response length:
        - Combat actions should be brief (1-2 sentences)
        - Scene descriptions should be detailed (3-5 sentences)
        - Skill checks should be concise (1-2 sentences)
        - etc.
        
        Args:
            action: Player's action text
            game_state: Current game state
            
        Returns:
            Context type string
        """
        action_lower = action.lower()
        
        # Check game state first
        if game_state.get("combat_active"):
            return "combat_action"
        
        # Combat keywords
        combat_words = [
            "attack", "hit", "strike", "shoot", "stab", "slash", 
            "cast", "fireball", "spell", "swing", "punch", "kick"
        ]
        if any(word in action_lower for word in combat_words):
            return "combat_action"
        
        # Scene transition keywords
        scene_words = [
            "enter", "arrive", "open door", "approach", "go to", 
            "walk into", "step into", "move to", "head to"
        ]
        if any(word in action_lower for word in scene_words):
            return "scene_description"
        
        # NPC dialogue keywords
        dialogue_words = [
            "talk", "speak", "ask", "tell", "say to", "greet", 
            "question", "inquire", "chat", "converse"
        ]
        if any(word in action_lower for word in dialogue_words):
            return "npc_dialogue"
        
        # Skill check keywords
        skill_words = [
            "search", "investigate", "look for", "examine", 
            "check for", "perceive", "inspect", "study"
        ]
        if any(word in action_lower for word in skill_words):
            return "skill_check"
        
        # Exploration keywords
        explore_words = [
            "look around", "survey", "observe", "scan", 
            "take in", "view", "regard"
        ]
        if any(word in action_lower for word in explore_words):
            return "exploration"
        
        return "standard"

    def _default_system_prompt(self) -> str:
        """Default DM personality if no custom prompt provided"""
        return """You are an expert Dungeon Master for D&D 5th Edition.

Your role:
- Narrate vivid, engaging scenes that bring the world to life
- Follow D&D 5e rules strictly - use the tools provided for all mechanics
- Call for appropriate skill checks, saving throws, and combat rolls
- WAIT for dice roll results - never invent outcomes
- Be fair but challenging
- Reward creative problem-solving
- Maintain consistent NPCs with distinct personalities
- Track important story details and consequences

When players describe actions:
1. Determine if a roll is needed
2. Call the appropriate tool (skill_check, attack_roll, etc.)
3. Wait for the result
4. Narrate the outcome based on the roll

Always use tools for game mechanics - never guess or simulate dice rolls yourself.
"""

    def _define_tools(self) -> List[ToolDefinition]:
        """Define D&D game mechanic tools for the AI"""
        return [
            ToolDefinition(
                name="roll_dice",
                description="Roll dice using standard D&D notation (e.g., '2d6+3', '1d20'). Use this for any random rolling needed.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "dice": {
                            "type": "string",
                            "description": "Dice notation (e.g., '2d6+3', '1d20', '4d6')",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Why you're rolling (for the narrative)",
                        },
                    },
                    "required": ["dice"],
                },
            ),
            ToolDefinition(
                name="skill_check",
                description="Make a skill check for a character. The system will roll d20 + modifiers and compare to DC.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "character": {
                            "type": "string",
                            "description": "Character name",
                        },
                        "skill": {
                            "type": "string",
                            "description": "Skill name (e.g., 'perception', 'stealth', 'investigation')",
                        },
                        "dc": {
                            "type": "integer",
                            "description": "Difficulty Class (5=very easy, 10=easy, 15=medium, 20=hard, 25=very hard)",
                        },
                        "advantage": {
                            "type": "boolean",
                            "description": "Whether the character has advantage",
                        },
                        "disadvantage": {
                            "type": "boolean",
                            "description": "Whether the character has disadvantage",
                        },
                    },
                    "required": ["character", "skill", "dc"],
                },
            ),
            ToolDefinition(
                name="saving_throw",
                description="Make a saving throw for a character against a DC.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "character": {
                            "type": "string",
                            "description": "Character name",
                        },
                        "ability": {
                            "type": "string",
                            "description": "Ability (STR, DEX, CON, INT, WIS, CHA)",
                        },
                        "dc": {
                            "type": "integer",
                            "description": "Difficulty Class",
                        },
                        "advantage": {"type": "boolean"},
                        "disadvantage": {"type": "boolean"},
                    },
                    "required": ["character", "ability", "dc"],
                },
            ),
            ToolDefinition(
                name="attack_roll",
                description="Make an attack roll in combat. Returns hit/miss and damage if successful.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "attacker": {
                            "type": "string",
                            "description": "Name of attacking creature",
                        },
                        "target": {
                            "type": "string",
                            "description": "Name of target creature",
                        },
                        "weapon": {
                            "type": "string",
                            "description": "Weapon being used (optional)",
                        },
                        "advantage": {"type": "boolean"},
                        "disadvantage": {"type": "boolean"},
                    },
                    "required": ["attacker", "target"],
                },
            ),
            ToolDefinition(
                name="update_hp",
                description="Update a character or creature's hit points.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "character": {"type": "string"},
                        "hp_change": {
                            "type": "integer",
                            "description": "HP change (negative for damage, positive for healing)",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for HP change",
                        },
                    },
                    "required": ["character", "hp_change"],
                },
            ),
            ToolDefinition(
                name="start_combat",
                description="Initialize combat and roll initiative for all participants.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "participants": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of all combatants (PCs and NPCs)",
                        },
                    },
                    "required": ["participants"],
                },
            ),
            ToolDefinition(
                name="end_combat",
                description="End the current combat encounter.",
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDefinition(
                name="get_character_info",
                description="Get full information about a character (stats, HP, inventory, etc.)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "character": {"type": "string"},
                    },
                    "required": ["character"],
                },
            ),
            ToolDefinition(
                name="add_to_inventory",
                description="Add an item to a character's inventory.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "character": {"type": "string"},
                        "item": {"type": "string"},
                        "quantity": {"type": "integer"},
                    },
                    "required": ["character", "item"],
                },
            ),
            ToolDefinition(
                name="check_level_up_status",
                description="Check if the party is eligible for a level up. Call this after significant progress (defeating encounters, completing quests, discovering important locations) to see if players can level up on their next rest. This helps you inform players proactively.",
                input_schema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            ToolDefinition(
                name="long_rest",
                description="Process a long rest for the party. Restores HP, spell slots, and checks for level up eligibility. Call this when players take a long rest (8 hours of rest).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Brief description of where/how they're resting"
                        }
                    },
                    "required": [],
                },
            ),
        ]

    async def process_player_input(
        self, 
        player_message: str, 
        voice: bool = False,
        adventure_context: Optional[Dict[str, Any]] = None,
        session_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process player input and generate DM response

        Args:
            player_message: What the player said/typed
            voice: Whether to generate TTS audio

        Returns:
            {
                "narrative": str,
                "audio_url": Optional[str],
                "game_state": dict,
                "tool_results": List[dict]
            }
        """

        # Add player message to history
        self.conversation_history.append(
            Message(role="user", content=player_message)
        )

        # Get current game state
        game_state = self.game_engine.get_state()
        
        # Build enhanced system prompt with adventure context
        enhanced_system_prompt = self._build_enhanced_system_prompt(
            adventure_context, session_state
        )
        
        # Detect context type for dynamic token limits
        context_type = self._detect_context(player_message, game_state)
        
        # Get AI response
        # For Ollama (local models), disable tool calling for speed
        # Tool calling via prompt engineering is slow and unreliable on local models
        # Check if using Ollama by class name (avoid circular import)
        is_ollama = type(self.ai_client).__name__ == "OllamaClient"
        
        # For Anthropic, use context-aware token limits and pass game state
        # Filter out empty messages before sending (Anthropic API requirement)
        filtered_history = [
            msg for msg in self.conversation_history
            if msg.content and (
                (isinstance(msg.content, str) and msg.content.strip()) or
                (isinstance(msg.content, (dict, list)) and len(msg.content) > 0) or
                (not isinstance(msg.content, (str, dict, list)) and str(msg.content).strip())
            )
        ]
        
        if type(self.ai_client).__name__ == "AnthropicClient":
            response = await self.ai_client.create_message(
                messages=filtered_history,
                tools=self.tools,
                system_prompt=enhanced_system_prompt,
                temperature=0.7,
                max_tokens=300,  # Default, will be overridden by context_type
                context_type=context_type,
                game_state=game_state,
            )
        else:
            # For other providers (Ollama, OpenAI, etc.)
            response = await self.ai_client.create_message(
                messages=self.conversation_history,
                tools=None if is_ollama else self.tools,  # Disable tools for Ollama (much faster)
                system_prompt=enhanced_system_prompt,
                temperature=0.7,
                max_tokens=150 if is_ollama else 300,  # Small tokens for fast Ollama responses
            )

        # Execute any tool calls
        tool_results = []
        if response.tool_calls:
            for tool_call in response.tool_calls:
                try:
                    result = await self._execute_tool(tool_call.name, tool_call.parameters)
                    tool_results.append(
                        {
                            "tool": tool_call.name,
                            "parameters": tool_call.parameters,
                            "result": result,
                        }
                    )
                except Exception as e:
                    # Tool execution failed - log error and include error in result
                    error_msg = f"Tool '{tool_call.name}' failed: {str(e)}"
                    print(f"❌ {error_msg}")
                    import traceback
                    traceback.print_exc()
                    tool_results.append(
                        {
                            "tool": tool_call.name,
                            "parameters": tool_call.parameters,
                            "result": {"error": error_msg, "success": False},
                        }
                    )

            # Add tool results to conversation and get final narration
            # (AI needs to see tool results to narrate the outcome)
            
            # For Anthropic, we need to send tool results in the proper format
            # with tool_use_id references
            if type(self.ai_client).__name__ == "AnthropicClient":
                try:
                    # First, add the assistant message with tool_use blocks
                    assistant_content = []
                    for tool_call in response.tool_calls:
                        assistant_content.append({
                            "type": "tool_use",
                            "id": tool_call.id,
                            "name": tool_call.name,
                            "input": tool_call.parameters
                        })
                    # Add any text content if present
                    if response.text:
                        assistant_content.insert(0, {"type": "text", "text": response.text})
                    
                    self.conversation_history.append(
                        Message(role="assistant", content=assistant_content)
                    )
                    
                    # Now add tool results in Anthropic's expected format
                    tool_result_content = []
                    for i, tool_call in enumerate(response.tool_calls):
                        # Ensure result is properly formatted as string
                        result_str = json.dumps(tool_results[i]["result"], indent=2) if isinstance(tool_results[i]["result"], (dict, list)) else str(tool_results[i]["result"])
                        tool_result_content.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": result_str
                        })
                    
                    self.conversation_history.append(
                        Message(role="user", content=tool_result_content)
                    )
                except Exception as e:
                    # Fallback to text format if there's an error
                    print(f"⚠️  Error formatting Anthropic tool results, falling back to text: {e}")
                    import traceback
                    traceback.print_exc()
                    # Use text format as fallback
                    tool_results_message = "Tool results:\n" + "\n".join(
                        f"- {tr['tool']}: {json.dumps(tr['result'])}" for tr in tool_results
                    )
                    self.conversation_history.append(
                        Message(role="user", content=tool_results_message)
                    )
            else:
                # For other providers, use plain text format
                self.conversation_history.append(
                    Message(
                        role="assistant",
                        content=f"[Used tools: {', '.join(tc.name for tc in response.tool_calls)}]",
                    )
                )

                tool_results_message = "Tool results:\n" + "\n".join(
                    f"- {tr['tool']}: {json.dumps(tr['result'])}" for tr in tool_results
                )

                self.conversation_history.append(
                    Message(role="user", content=tool_results_message)
                )

            # Get final narration
            # Use context-aware limits for Anthropic
            # Increase token limit for final narration to prevent truncation
            final_max_tokens = None  # Initialize to avoid NameError
            if type(self.ai_client).__name__ == "AnthropicClient":
                # Use higher token limit for final narration to ensure complete thoughts
                final_token_limits = {
                    "scene_description": 600,    # Increased for complete scene descriptions
                    "combat_action": 200,         # Increased slightly for combat
                    "npc_dialogue": 350,          # Increased for dialogue
                    "skill_check": 200,           # Increased for skill checks
                    "exploration": 450,           # Increased for exploration
                    "standard": 300               # Increased default
                }
                final_max_tokens = final_token_limits.get(context_type, 300)
                
                final_response = await self.ai_client.create_message(
                    messages=self.conversation_history,
                    system_prompt=enhanced_system_prompt,
                    temperature=0.7,
                    max_tokens=final_max_tokens,  # Use increased limit
                    context_type=context_type,
                    game_state=game_state,
                )
            else:
                final_max_tokens = 150 if is_ollama else 300
                final_response = await self.ai_client.create_message(
                    messages=self.conversation_history,
                    system_prompt=enhanced_system_prompt,
                    temperature=0.7,
                    max_tokens=final_max_tokens,  # Small for Ollama speed
                )

            narrative = final_response.text or ""
            
            # Check if response was truncated (hit max_tokens)
            if final_response.finish_reason == "length":
                print(f"⚠️  WARNING: Response was truncated (hit max_tokens={final_max_tokens}). Consider increasing token limit for context_type: {context_type}")
                # Try to complete the thought more intelligently
                if narrative:
                    # Remove any incomplete sentence at the end
                    narrative = narrative.rstrip()
                    # If it doesn't end with proper punctuation, try to fix it
                    if not narrative.endswith(('.', '!', '?', '"', "'")):
                        # Find the last complete sentence
                        last_period = narrative.rfind('.')
                        last_exclamation = narrative.rfind('!')
                        last_question = narrative.rfind('?')
                        last_punct = max(last_period, last_exclamation, last_question)
                        
                        if last_punct > 0:
                            # Keep everything up to the last complete sentence
                            narrative = narrative[:last_punct + 1]
                    
                    # Add closing question if missing
                    if not narrative.strip().endswith("?"):
                        narrative += " What do you do?"
                else:
                    narrative = "What do you do?"
        else:
            narrative = response.text or ""
            
            # Check if response was truncated (hit max_tokens)
            if response.finish_reason == "length":
                print(f"⚠️  WARNING: Response was truncated (hit max_tokens). Consider increasing token limit for context_type: {context_type}")
                # Try to complete the thought more intelligently
                if narrative:
                    # Remove any incomplete sentence at the end
                    narrative = narrative.rstrip()
                    # If it doesn't end with proper punctuation, try to fix it
                    if not narrative.endswith(('.', '!', '?', '"', "'")):
                        # Find the last complete sentence
                        last_period = narrative.rfind('.')
                        last_exclamation = narrative.rfind('!')
                        last_question = narrative.rfind('?')
                        last_punct = max(last_period, last_exclamation, last_question)
                        
                        if last_punct > 0:
                            # Keep everything up to the last complete sentence
                            narrative = narrative[:last_punct + 1]
                    
                    # Add closing question if missing
                    if not narrative.strip().endswith("?"):
                        narrative += " What do you do?"
                else:
                    narrative = "What do you do?"

        # Add narrative to conversation history
        self.conversation_history.append(Message(role="assistant", content=narrative))
        
        # Trim conversation history if it gets too long (prevents token bloat)
        self._trim_conversation_history(max_messages=50)

        # Generate TTS if requested (will return None if TTS is disabled/failed)
        audio_url = None
        if voice and narrative and self.tts_service:
            try:
                print(f"🎤 Generating TTS audio for narrative (length: {len(narrative)} chars)")
                audio_url = await self.tts_service.generate(narrative)
                if audio_url:
                    print(f"✅ TTS audio generated: {audio_url}")
                else:
                    print(f"⚠️  TTS returned None (service may be disabled)")
            except Exception as e:
                # TTS failed, continue without audio
                print(f"⚠️  TTS generation failed: {e}")
                import traceback
                traceback.print_exc()
                audio_url = None

        return {
            "narrative": narrative,
            "audio_url": audio_url,
            "game_state": self.game_engine.get_state(),
            "tool_results": tool_results,
        }

    async def _execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Execute a game mechanic tool"""
        
        # Helper to get required parameter with better error message
        def get_param(key: str, default=None):
            if key not in parameters:
                if default is not None:
                    return default
                raise ValueError(f"Missing required parameter '{key}' for tool '{tool_name}'. Received parameters: {list(parameters.keys())}")
            return parameters[key]

        if tool_name == "roll_dice":
            return self.game_engine.roll_dice(get_param("dice"))

        elif tool_name == "skill_check":
            return self.game_engine.skill_check(
                character=get_param("character"),
                skill=get_param("skill"),
                dc=get_param("dc"),
                advantage=parameters.get("advantage", False),
                disadvantage=parameters.get("disadvantage", False),
            )

        elif tool_name == "saving_throw":
            return self.game_engine.saving_throw(
                character=get_param("character"),
                ability=get_param("ability"),
                dc=get_param("dc"),
                advantage=parameters.get("advantage", False),
                disadvantage=parameters.get("disadvantage", False),
            )

        elif tool_name == "attack_roll":
            return self.game_engine.attack_roll(
                attacker=get_param("attacker"),
                target=get_param("target"),
                weapon=parameters.get("weapon"),
                advantage=parameters.get("advantage", False),
                disadvantage=parameters.get("disadvantage", False),
            )

        elif tool_name == "update_hp":
            return self.game_engine.update_hp(
                character=get_param("character"),
                hp_change=get_param("hp_change"),
            )

        elif tool_name == "start_combat":
            return self.game_engine.start_combat(get_param("participants"))

        elif tool_name == "end_combat":
            result = self.game_engine.end_combat()
            # Track combat encounter completion for leveling
            if self.adventure_context and hasattr(self.adventure_context, 'leveling'):
                # Try to identify the encounter from combat state
                combat_state = self.game_engine.combat_state
                if combat_state.get("active") == False and combat_state.get("round", 0) > 0:
                    # Combat just ended - track it
                    encounter_id = f"encounter_{combat_state.get('round', 0)}"
                    self.adventure_context.leveling.track_combat_encounter(encounter_id)
            return result

        elif tool_name == "get_character_info":
            return self.game_engine.get_character(get_param("character"))

        elif tool_name == "add_to_inventory":
            return self.game_engine.add_to_inventory(
                character=get_param("character"),
                item=get_param("item"),
                quantity=parameters.get("quantity", 1),
            )

        elif tool_name == "check_level_up_status":
            # Check if party is eligible for level up (without actually leveling)
            if not self.adventure_context:
                return {"error": "No adventure loaded. Cannot check level up status."}
            
            try:
                current_state = self.adventure_context.metadata.get("current_state", {})
                current_level = current_state.get("party_level", 1)
                
                # Check eligibility without processing rest
                result = self.adventure_context.leveling.check_level_up_eligibility(current_level)
                
                return {
                    "eligible": result.get("eligible", False),
                    "current_level": current_level,
                    "new_level": result.get("new_level", current_level),
                    "reason": result.get("reason", ""),
                    "progress_summary": result.get("progress_summary", {}),
                    "message": f"You are eligible to level up to level {result.get('new_level', current_level)} on your next long rest!" if result.get("eligible") else f"Not yet eligible for level up. {result.get('reason', '')}"
                }
            except Exception as e:
                import traceback
                return {"error": f"Error checking level up status: {str(e)}", "traceback": traceback.format_exc()}

        elif tool_name == "long_rest":
            # Process long rest and check for level up
            if not self.adventure_context:
                return {"error": "No adventure loaded. Cannot process long rest."}
            
            try:
                current_state = self.adventure_context.metadata.get("current_state", {})
                current_level = current_state.get("party_level", 1)
                
                # Process long rest through leveling system
                result = self.adventure_context.leveling.process_long_rest(current_level)
                
                # Restore HP for all characters (long rest restores all HP)
                if self.game_engine:
                    for char_name in self.game_engine.characters.keys():
                        char = self.game_engine.characters[char_name]
                        if "max_hp" in char:
                            char["hp"] = char["max_hp"]
                            char["current_hp"] = char["max_hp"]
                
                return {
                    "rest_complete": True,
                    "hp_restored": True,
                    "level_up": result.get("level_up", False),
                    "old_level": result.get("old_level", current_level),
                    "new_level": result.get("new_level", current_level),
                    "reason": result.get("reason", ""),
                    "message": f"Level up to {result.get('new_level', current_level)}!" if result.get("level_up") else "Rest complete. No level up."
                }
            except Exception as e:
                import traceback
                return {"error": f"Error processing long rest: {str(e)}", "traceback": traceback.format_exc()}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def _build_enhanced_system_prompt(
        self,
        adventure_context: Optional[Dict[str, Any]] = None,
        session_state: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build enhanced system prompt with adventure and session context
        
        Args:
            adventure_context: Adventure metadata or modular adventure context string
            session_state: Session state (quest log, world state, location, etc.)
        
        Returns:
            Enhanced system prompt string
        """
        # Debug logging for session_state
        if session_state:
            party_members = session_state.get("party_members")
            print(f"🔍 DEBUG: Building system prompt with session_state")
            print(f"   - party_members present: {party_members is not None}")
            print(f"   - party_members count: {len(party_members) if party_members else 0}")
            if party_members:
                print(f"   - party_members names: {[m.get('name', 'Unknown') if isinstance(m, dict) else str(m) for m in party_members]}")
        
        prompt_parts = [self.system_prompt]
        
        # Add adventure context
        if adventure_context:
            # Check if this is a modular adventure context string (from AdventureContext)
            if isinstance(adventure_context, str):
                prompt_parts.append("\n## CURRENT ADVENTURE:")
                prompt_parts.append(adventure_context)
            elif isinstance(adventure_context, dict):
                # Legacy format - simple adventure metadata
                prompt_parts.append("\n## ADVENTURE CONTEXT:")
                
                if adventure_context.get("name"):
                    prompt_parts.append(f"\n**Adventure:** {adventure_context['name']}")
                
                if adventure_context.get("description"):
                    prompt_parts.append(f"\n**Description:** {adventure_context['description']}")
                
                if adventure_context.get("notes"):
                    prompt_parts.append(f"\n**Notes:** {adventure_context['notes']}")
        
        # Add session state context
        if session_state:
            prompt_parts.append("\n## CURRENT SESSION STATE:")
            
            if session_state.get("campaign"):
                prompt_parts.append(f"\n**Campaign:** {session_state['campaign']}")
            
            if session_state.get("session_number"):
                prompt_parts.append(f"\n**Session:** {session_state['session_number']}")
            
            if session_state.get("current_location"):
                prompt_parts.append(f"\n**Current Location:** {session_state['current_location']}")
            
            if session_state.get("active_encounter"):
                prompt_parts.append(f"\n**Active Encounter:** {session_state['active_encounter']}")
            
            # Add party/character information
            if session_state.get("party_members"):
                party_members = session_state["party_members"]
                print(f"✅ DEBUG: Found party_members in session_state: {len(party_members) if party_members else 0} members")
                if party_members and len(party_members) > 0:
                    prompt_parts.append("\n**Party Members:**")
                    for member in party_members:
                        if isinstance(member, dict):
                            name = member.get("name", "Unknown")
                            char_class = member.get("char_class") or member.get("class", "Unknown")
                            level = member.get("level", "?")
                            hp = member.get("current_hp") or member.get("hp", "?")
                            max_hp = member.get("max_hp", "?")
                            member_str = f"  - {name} ({char_class} Level {level}, HP: {hp}/{max_hp})"
                            prompt_parts.append(member_str)
                            print(f"   Added to prompt: {member_str}")
                        else:
                            prompt_parts.append(f"  - {member}")
                            print(f"   Added to prompt (non-dict): {member}")
                else:
                    print(f"⚠️  DEBUG: party_members is empty or None")
            elif session_state.get("party"):
                # Fallback to party array (just names)
                print(f"⚠️  DEBUG: No party_members, using party array fallback")
                party = session_state["party"]
                if isinstance(party, list) and len(party) > 0:
                    prompt_parts.append(f"\n**Party:** {', '.join(str(p) for p in party)}")
            else:
                print(f"⚠️  DEBUG: No party_members or party in session_state. Available keys: {list(session_state.keys()) if session_state else 'None'}")
            
            # Quest log
            if session_state.get("quest_log") and len(session_state["quest_log"]) > 0:
                prompt_parts.append("\n**Quest Log:**")
                for quest in session_state["quest_log"]:
                    status = quest.get("status", "unknown").upper().replace("_", " ")
                    prompt_parts.append(f"  - {quest.get('name', 'Unnamed Quest')} ({status})")
                    if quest.get("description"):
                        prompt_parts.append(f"    {quest['description']}")
                    if quest.get("notes"):
                        prompt_parts.append(f"    Notes: {quest['notes']}")
            
            # World state (key information)
            if session_state.get("world_state") and isinstance(session_state["world_state"], dict):
                world_state = session_state["world_state"]
                # Only include significant state changes (not every flag)
                significant_state = {
                    k: v for k, v in world_state.items()
                    if v not in (None, False, "", []) and k not in ["_internal", "_metadata"]
                }
                if significant_state:
                    prompt_parts.append("\n**World State:**")
                    for key, value in significant_state.items():
                        # Format key nicely
                        key_display = key.replace("_", " ").title()
                        if isinstance(value, bool):
                            value_display = "Yes" if value else "No"
                        else:
                            value_display = str(value)
                        prompt_parts.append(f"  - {key_display}: {value_display}")
            
            # Recent notes (last 3)
            if session_state.get("notes") and len(session_state["notes"]) > 0:
                recent_notes = session_state["notes"][-3:]
                prompt_parts.append("\n**Recent Notes:**")
                for note in recent_notes:
                    prompt_parts.append(f"  - {note}")
        
        return "\n".join(prompt_parts)

    def reset_conversation(self):
        """Clear conversation history (start fresh session)"""
        self.conversation_history = []
    
    def restore_conversation_history(self, messages: List[Dict[str, Any]]):
        """
        Restore conversation history from archived messages
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
        """
        self.conversation_history = []
        for msg in messages:
            # Convert dict to Message object
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # Filter out messages with empty content (except system messages which can be empty)
            # Anthropic API requires all messages except the final assistant message to have non-empty content
            if role in ("user", "assistant", "system"):
                # Skip empty content messages (Anthropic doesn't allow them)
                if not content or not content.strip():
                    print(f"⚠️  Skipping {role} message with empty content")
                    continue
                self.conversation_history.append(Message(role=role, content=content))
    
    def _trim_conversation_history(self, max_messages: int = 50):
        """
        Trim conversation history to keep only recent messages
        
        Keeps the most recent messages to prevent token bloat in long sessions.
        Always keeps at least the last 2 messages (player + DM) for context.
        
        Args:
            max_messages: Maximum number of messages to keep (default: 50)
        """
        if len(self.conversation_history) <= max_messages:
            return  # No trimming needed
        
        # Keep the most recent messages
        # This preserves recent context while removing older messages
        self.conversation_history = self.conversation_history[-max_messages:]
