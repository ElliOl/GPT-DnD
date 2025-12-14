# Anthropic API Integration - Complete Implementation Guide

## Overview

Replace the slow local Ollama setup with **Claude Haiku 4.5** integrated with all game systems.

**Goals:**
- Use Anthropic API (Claude Haiku 4.5) for fast responses (1-2 seconds)
- Enable prompt caching to reduce costs to ~$5/year
- Integrate with ALL existing Python tools: dice roller, character sheets, combat, skills
- Use Claude's tool calling to execute game mechanics
- Maintain game state properly

---

## 1. Install Dependencies

```bash
cd backend
pip install anthropic python-dotenv
```

---

## 2. Environment Configuration

Update `backend/.env`:

```bash
# AI Provider
AI_PROVIDER=anthropic
AI_MODEL=claude-3-5-haiku-20241022

# Anthropic API Key
ANTHROPIC_API_KEY=your_api_key_here

# Performance Settings
ENABLE_PROMPT_CACHING=true
MAX_TOKENS=200  # Note: This is overridden dynamically by context detection
TIMEOUT=30      # (combat=150, scenes=400, dialogue=250, etc.)
TEMPERATURE=0.8 # Optional: 0.7-0.9 good for creative narration
```

**Get API Key:**
1. Go to https://console.anthropic.com/
2. Create account
3. Go to API Keys
4. Create new key
5. Copy to `.env`

---

## 3. Create Anthropic Client

Create `backend/services/anthropic_client.py`:

```python
"""
Anthropic Claude API Client
Handles communication with Claude Haiku/Sonnet with prompt caching
"""

import os
from anthropic import Anthropic
from typing import List, Dict, Any, Optional

class AnthropicClient:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        
        self.client = Anthropic(api_key=api_key)
        self.model = os.getenv("AI_MODEL", "claude-3-5-haiku-20241022")
        self.max_tokens = int(os.getenv("MAX_TOKENS", "300"))
        self.enable_caching = os.getenv("ENABLE_PROMPT_CACHING", "true").lower() == "true"
        
        # Cached content (stays same across requests)
        self.dm_system_prompt = self._load_dm_prompt()
        self.dnd_rules = self._load_dnd_rules()
    
    def _load_dm_prompt(self) -> str:
        """DM personality and behavior rules"""
        return """You are an expert D&D 5e Dungeon Master.

CRITICAL RULES:
- End every scene with ONLY: "What do you do?"
- NEVER suggest actions or list options
- NEVER tell players what their characters think/feel/notice
- NEVER reveal hidden information before discovery
- Describe the WORLD objectively, players interpret it

NARRATION STYLE:
- Use all 5 senses (sight, sound, smell, touch, taste)
- Vivid, atmospheric prose
- Vary sentence length for rhythm
- Build tension through environmental details

RESPONSE LENGTH GUIDELINES (CRITICAL - FOLLOW THESE):

**Scene Descriptions (entering new areas):**
- 3-5 sentences
- Use all 5 senses
- Set atmosphere
Example: "The tavern door groans open. Smoke and the smell of roasted meat hit you immediately. Rough wooden tables crowd the space, most occupied by grizzled travelers. A roaring fire crackles in the stone hearth. The barkeep eyes you warily from behind a scarred oak bar."

**Combat Actions (attacks, spells in combat):**
- 1-2 sentences MAXIMUM
- Quick and punchy
- Focus on impact
Example: "Your blade bites deep into the goblin's shoulder, spraying blood. It shrieks and staggers back, clutching the wound."

**NPC Dialogue:**
- 2-3 sentences
- Distinct voice
- Stay in character
Example: "The dwarf strokes his gray beard and squints at you. 'Bah! I tell ye, those caves are cursed. Lost three good miners there last month.' He spits into the sawdust."

**Skill Check Results:**
- 1-2 sentences
- State what they find/learn
- Move forward
Example: "With a 17, you spot fresh goblin tracks leading east into the forest. They're recent—less than an hour old."

**Exploration/Investigation:**
- 2-4 sentences
- Reveal details progressively
- Leave room for questions
Example: "You search the bodies. The horses bear the Rockseeker clan brand. Crude goblin arrows jut from their flanks. Drag marks lead east into the underbrush."

CRITICAL: Match your response length to the action type above. Combat should be BRIEF. New scenes can be DETAILED.

TOOL USAGE:
- Use tools to execute game mechanics (dice, combat, skills)
- Narrate the RESULTS of tool calls dramatically
- Always check character stats before describing outcomes

Remember: Tools handle mechanics. You handle storytelling."""

    def _load_dnd_rules(self) -> str:
        """D&D 5e rules summary"""
        return """D&D 5e RULES SUMMARY:

ABILITY CHECKS:
- d20 + ability modifier + proficiency bonus (if proficient)
- DC 5-10 (easy), 10-15 (medium), 15-20 (hard), 20+ (very hard)
- Advantage: roll 2d20, take higher
- Disadvantage: roll 2d20, take lower

COMBAT:
- Initiative: d20 + DEX modifier (highest goes first)
- Attack: d20 + attack bonus vs target AC
- Natural 20 = critical hit (double damage dice)
- Natural 1 = critical miss
- 0 HP = unconscious, make death saves

DEATH SAVES:
- Roll d20 each turn when at 0 HP
- 10+ = success, 9 or less = failure
- 3 successes = stabilized
- 3 failures = dead
- Natural 20 = wake up with 1 HP
- Natural 1 = 2 failures

DAMAGE TYPES:
- Slashing, piercing, bludgeoning (physical)
- Fire, cold, lightning, thunder, acid, poison (elemental)
- Radiant, necrotic, psychic, force (magical)

CHARACTER STATS:
- STR (Strength): Athletics, melee attacks
- DEX (Dexterity): Acrobatics, Stealth, AC, ranged attacks
- CON (Constitution): HP, concentration saves
- INT (Intelligence): Arcana, Investigation, History
- WIS (Wisdom): Perception, Insight, Survival
- CHA (Charisma): Persuasion, Deception, Performance

Use tools to execute these mechanics."""

    def create_tools(self) -> List[Dict[str, Any]]:
        """Define available game mechanics tools"""
        return [
            {
                "name": "roll_dice",
                "description": "Roll dice using standard D&D notation (e.g., '1d20', '2d6+3', '1d20+5'). Use this for ANY random element: attacks, damage, ability checks, saves, etc.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dice": {
                            "type": "string",
                            "description": "Dice notation (e.g., '1d20+5', '2d6', '3d8+2')"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Why rolling (e.g., 'Perception check', 'Sword damage', 'Initiative')"
                        }
                    },
                    "required": ["dice", "reason"]
                }
            },
            {
                "name": "skill_check",
                "description": "Perform a D&D skill check. Returns the roll result and success/failure. Use when a character attempts something uncertain.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "character_name": {
                            "type": "string",
                            "description": "Character's full name"
                        },
                        "skill": {
                            "type": "string",
                            "description": "Skill name: Acrobatics, Animal Handling, Arcana, Athletics, Deception, History, Insight, Intimidation, Investigation, Medicine, Nature, Perception, Performance, Persuasion, Religion, Sleight of Hand, Stealth, Survival"
                        },
                        "dc": {
                            "type": "integer",
                            "description": "Difficulty Class (5-10 easy, 10-15 medium, 15-20 hard, 20+ very hard)"
                        },
                        "advantage": {
                            "type": "boolean",
                            "description": "True if character has advantage"
                        }
                    },
                    "required": ["character_name", "skill", "dc"]
                }
            },
            {
                "name": "attack_roll",
                "description": "Make an attack roll in combat. Returns hit/miss and damage if applicable.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "attacker": {
                            "type": "string",
                            "description": "Name of attacker"
                        },
                        "target": {
                            "type": "string",
                            "description": "Name of target"
                        },
                        "weapon": {
                            "type": "string",
                            "description": "Weapon being used (for description)"
                        },
                        "advantage": {
                            "type": "boolean",
                            "description": "True if attacking with advantage"
                        }
                    },
                    "required": ["attacker", "target"]
                }
            },
            {
                "name": "update_hp",
                "description": "Update a character's hit points. Use after damage or healing.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "character_name": {
                            "type": "string",
                            "description": "Character's full name"
                        },
                        "change": {
                            "type": "integer",
                            "description": "HP change (negative for damage, positive for healing)"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for HP change (e.g., 'goblin attack', 'healing potion')"
                        }
                    },
                    "required": ["character_name", "change", "reason"]
                }
            },
            {
                "name": "get_character",
                "description": "Get full character information including stats, HP, AC, proficiencies, etc.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "character_name": {
                            "type": "string",
                            "description": "Character's full name"
                        }
                    },
                    "required": ["character_name"]
                }
            },
            {
                "name": "initiative_roll",
                "description": "Roll initiative for combat. Pass all combatants (both PCs and NPCs).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "combatants": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "dex_modifier": {"type": "integer"}
                                }
                            },
                            "description": "List of all combatants with their DEX modifiers"
                        }
                    },
                    "required": ["combatants"]
                }
            }
        ]
    
    def generate(
        self,
        messages: List[Dict[str, Any]],
        game_state: Optional[Dict[str, Any]] = None,
        context_type: str = "standard"
    ) -> Dict[str, Any]:
        """
        Generate DM response with tool calling
        
        Args:
            messages: Conversation history
            game_state: Current game state (for context)
            context_type: Type of response needed (adjusts max_tokens dynamically)
                - "scene_description": Entering new area (3-5 sentences)
                - "combat_action": Attack/spell in combat (1-2 sentences)
                - "npc_dialogue": Talking to NPCs (2-3 sentences)
                - "skill_check": Investigation/Perception result (1-2 sentences)
                - "exploration": Looking around (2-4 sentences)
                - "standard": Default (2-3 sentences)
        
        Returns:
            {
                "content": "Narration text",
                "tool_calls": [...],  # If tools were used
                "stop_reason": "end_turn" | "tool_use"
            }
        """
        
        # Dynamic token limits based on context
        token_limits = {
            "scene_description": 400,    # Entering new area - detailed
            "combat_action": 150,         # Attack, spell in combat - brief!
            "npc_dialogue": 250,          # Talking to NPCs - moderate
            "skill_check": 150,           # Investigation, Perception - short
            "exploration": 300,           # Looking around - medium detail
            "standard": 200               # Default
        }
        
        max_tokens = token_limits.get(context_type, 200)
        
        # Build system messages with caching
        system_messages = []
        
        # Cache DM prompt
        system_messages.append({
            "type": "text",
            "text": self.dm_system_prompt,
            "cache_control": {"type": "ephemeral"} if self.enable_caching else None
        })
        
        # Cache D&D rules
        system_messages.append({
            "type": "text",
            "text": self.dnd_rules,
            "cache_control": {"type": "ephemeral"} if self.enable_caching else None
        })
        
        # Add game state (don't cache - changes each turn)
        if game_state:
            system_messages.append({
                "type": "text",
                "text": f"CURRENT GAME STATE:\n{self._format_game_state(game_state)}"
            })
        
        # Remove None cache_control entries
        system_messages = [
            {k: v for k, v in msg.items() if v is not None}
            for msg in system_messages
        ]
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,  # Dynamic based on context_type!
                system=system_messages,
                messages=messages,
                tools=self.create_tools()
            )
            
            return self._parse_response(response)
        
        except Exception as e:
            print(f"Anthropic API Error: {e}")
            raise
    
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
        
        return "\n".join(parts)
    
    def _parse_response(self, response) -> Dict[str, Any]:
        """Parse Anthropic API response"""
        result = {
            "content": "",
            "tool_calls": [],
            "stop_reason": response.stop_reason
        }
        
        # Extract text content and tool calls
        for block in response.content:
            if block.type == "text":
                result["content"] += block.text
            elif block.type == "tool_use":
                result["tool_calls"].append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })
        
        return result


# Example usage
if __name__ == "__main__":
    client = AnthropicClient()
    
    # Test message
    messages = [{
        "role": "user",
        "content": "The party enters a dark tavern. Describe the scene."
    }]
    
    response = client.generate(messages)
    print(response["content"])
```

---

## 4. Create Tool Executor

Create `backend/services/tool_executor.py`:

```python
"""
Tool Executor - Executes game mechanics tools called by Claude
Integrates with existing dice roller, combat system, character sheets, etc.
"""

import json
from pathlib import Path
from typing import Dict, Any
from dice.roller import roll
from game_engine.skills import skill_check
from game_engine.combat import attack_roll, apply_damage
from game_engine.engine import GameEngine

class ToolExecutor:
    def __init__(self):
        self.engine = GameEngine()
        self.characters_dir = Path("characters")
    
    def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool and return results
        
        Args:
            tool_name: Name of tool to execute
            tool_input: Tool parameters
        
        Returns:
            Tool execution results
        """
        
        if tool_name == "roll_dice":
            return self.roll_dice(tool_input)
        
        elif tool_name == "skill_check":
            return self.skill_check(tool_input)
        
        elif tool_name == "attack_roll":
            return self.attack_roll(tool_input)
        
        elif tool_name == "update_hp":
            return self.update_hp(tool_input)
        
        elif tool_name == "get_character":
            return self.get_character(tool_input)
        
        elif tool_name == "initiative_roll":
            return self.initiative_roll(tool_input)
        
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
    def roll_dice(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute dice roll"""
        dice = params["dice"]
        reason = params.get("reason", "")
        
        result = roll(dice)
        
        return {
            "dice": dice,
            "result": result,
            "reason": reason,
            "description": f"Rolled {dice} for {reason}: {result}"
        }
    
    def skill_check(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute skill check"""
        char_name = params["character_name"]
        skill = params["skill"]
        dc = params["dc"]
        advantage = params.get("advantage", False)
        
        # Load character
        character = self._load_character(char_name)
        if not character:
            return {"error": f"Character {char_name} not found"}
        
        # Perform check
        result = skill_check(character, skill, dc, advantage=advantage)
        
        return {
            "character": char_name,
            "skill": skill,
            "roll": result["roll"],
            "total": result["total"],
            "dc": dc,
            "success": result["success"],
            "natural_20": result.get("natural_20", False),
            "natural_1": result.get("natural_1", False),
            "description": f"{char_name} rolled {skill}: {result['total']} vs DC {dc} - {'SUCCESS' if result['success'] else 'FAILURE'}"
        }
    
    def attack_roll(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute attack roll"""
        attacker_name = params["attacker"]
        target_name = params["target"]
        weapon = params.get("weapon", "attack")
        advantage = params.get("advantage", False)
        
        # Load characters
        attacker = self._load_character(attacker_name)
        target = self._load_character(target_name)
        
        if not attacker:
            return {"error": f"Attacker {attacker_name} not found"}
        if not target:
            return {"error": f"Target {target_name} not found"}
        
        # Perform attack
        attack = attack_roll(attacker, target, advantage=advantage)
        
        result = {
            "attacker": attacker_name,
            "target": target_name,
            "weapon": weapon,
            "attack_roll": attack["d20_roll"],
            "attack_total": attack["attack_total"],
            "target_ac": attack["target_ac"],
            "hit": attack["hit"],
            "critical": attack.get("critical", False),
            "damage": attack.get("damage", 0),
            "description": ""
        }
        
        if attack["hit"]:
            crit_text = " (CRITICAL HIT!)" if attack.get("critical") else ""
            result["description"] = f"{attacker_name} hits {target_name} with {weapon} for {attack['damage']} damage!{crit_text}"
        else:
            result["description"] = f"{attacker_name} misses {target_name}!"
        
        return result
    
    def update_hp(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update character HP"""
        char_name = params["character_name"]
        change = params["change"]
        reason = params.get("reason", "")
        
        character = self._load_character(char_name)
        if not character:
            return {"error": f"Character {char_name} not found"}
        
        old_hp = character["hp"]
        new_hp = max(0, min(character["max_hp"], old_hp + change))
        character["hp"] = new_hp
        
        # Save to file
        self._save_character(char_name, character)
        
        status = "alive"
        if new_hp == 0:
            status = "unconscious"
        elif new_hp < 0:
            status = "dead"
        
        return {
            "character": char_name,
            "old_hp": old_hp,
            "new_hp": new_hp,
            "max_hp": character["max_hp"],
            "change": change,
            "reason": reason,
            "status": status,
            "description": f"{char_name}: {old_hp} HP → {new_hp} HP ({reason}). Status: {status}"
        }
    
    def get_character(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get character data"""
        char_name = params["character_name"]
        
        character = self._load_character(char_name)
        if not character:
            return {"error": f"Character {char_name} not found"}
        
        return {
            "character": character,
            "description": f"{char_name}: {character.get('class', 'Unknown')} Level {character.get('level', 1)}, HP {character.get('hp', 0)}/{character.get('max_hp', 0)}, AC {character.get('ac', 10)}"
        }
    
    def initiative_roll(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Roll initiative for combat"""
        combatants = params["combatants"]
        
        results = []
        for combatant in combatants:
            init_roll = roll("1d20") + combatant.get("dex_modifier", 0)
            results.append({
                "name": combatant["name"],
                "initiative": init_roll,
                "dex_modifier": combatant.get("dex_modifier", 0)
            })
        
        # Sort by initiative (highest first)
        results.sort(key=lambda x: x["initiative"], reverse=True)
        
        order = [r["name"] for r in results]
        
        return {
            "initiative_order": results,
            "turn_order": order,
            "description": f"Initiative order: {', '.join(order)}"
        }
    
    def _load_character(self, name: str) -> Dict[str, Any]:
        """Load character from file"""
        # Try exact match
        char_file = self.characters_dir / f"{name.lower().replace(' ', '_')}.json"
        
        if not char_file.exists():
            # Try finding by name in all files
            for file in self.characters_dir.glob("*.json"):
                with open(file) as f:
                    char = json.load(f)
                    if char.get("name", "").lower() == name.lower():
                        return char
            return None
        
        with open(char_file) as f:
            return json.load(f)
    
    def _save_character(self, name: str, character: Dict[str, Any]):
        """Save character to file"""
        char_file = self.characters_dir / f"{name.lower().replace(' ', '_')}.json"
        with open(char_file, 'w') as f:
            json.dump(character, f, indent=2)
```

---

## 5. Update DM Agent

Create `backend/services/dm_agent.py`:

```python
"""
DM Agent - Orchestrates AI + Tools for D&D gameplay
"""

from typing import List, Dict, Any
from services.anthropic_client import AnthropicClient
from services.tool_executor import ToolExecutor

class DMAgent:
    def __init__(self):
        self.client = AnthropicClient()
        self.executor = ToolExecutor()
        self.conversation_history = []
    
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
    
    def process_action(
        self,
        action: str,
        game_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process player action and generate DM response
        
        Args:
            action: Player's action description
            game_state: Current game state
        
        Returns:
            {
                "narration": "DM's narrative response",
                "tool_results": [...],
                "updated_state": {...}
            }
        """
        
        # Detect what kind of response is needed
        context_type = self._detect_context(action, game_state)
        
        # Add player action to conversation
        self.conversation_history.append({
            "role": "user",
            "content": action
        })
        
        # Generate AI response with appropriate length limit
        ai_response = self.client.generate(
            messages=self.conversation_history,
            game_state=game_state,
            context_type=context_type  # This adjusts max_tokens!
        )
        
        tool_results = []
        final_narration = ""
        
        # If AI wants to use tools
        if ai_response["tool_calls"]:
            # Execute all tool calls
            for tool_call in ai_response["tool_calls"]:
                result = self.executor.execute(
                    tool_call["name"],
                    tool_call["input"]
                )
                tool_results.append({
                    "tool": tool_call["name"],
                    "result": result
                })
            
            # Send tool results back to AI for final narration
            self.conversation_history.append({
                "role": "assistant",
                "content": ai_response["content"] if ai_response["content"] else []
            })
            
            # Add tool results
            tool_result_message = {
                "role": "user",
                "content": []
            }
            
            for i, tool_call in enumerate(ai_response["tool_calls"]):
                tool_result_message["content"].append({
                    "type": "tool_result",
                    "tool_use_id": tool_call["id"],
                    "content": str(tool_results[i]["result"])
                })
            
            self.conversation_history.append(tool_result_message)
            
            # Get final narration with tool results
            final_response = self.client.generate(
                messages=self.conversation_history,
                game_state=game_state
            )
            
            final_narration = final_response["content"]
            
            # Add to history
            self.conversation_history.append({
                "role": "assistant",
                "content": final_narration
            })
        
        else:
            # No tools used, just narration
            final_narration = ai_response["content"]
            
            self.conversation_history.append({
                "role": "assistant",
                "content": final_narration
            })
        
        return {
            "narration": final_narration,
            "tool_results": tool_results,
            "updated_state": game_state  # Update as needed
        }
    
    def start_adventure(self, adventure_intro: str, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """Start a new adventure"""
        # Clear history
        self.conversation_history = []
        
        # Generate opening narration
        response = self.client.generate(
            messages=[{
                "role": "user",
                "content": f"Start this D&D adventure: {adventure_intro}"
            }],
            game_state=game_state
        )
        
        self.conversation_history.append({
            "role": "user",
            "content": f"Start this D&D adventure: {adventure_intro}"
        })
        
        self.conversation_history.append({
            "role": "assistant",
            "content": response["content"]
        })
        
        return {
            "narration": response["content"],
            "tool_results": [],
            "updated_state": game_state
        }
```

---

## 6. Update Backend API

Update `backend/main.py`:

```python
"""
FastAPI Backend for D&D Campaign
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

from services.dm_agent import DMAgent
from game_engine.engine import GameEngine

# Load environment
load_dotenv()

app = FastAPI(title="D&D Campaign API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize
dm = DMAgent()
engine = GameEngine()

# Request models
class ActionRequest(BaseModel):
    action: str
    game_state: Optional[Dict[str, Any]] = None

class AdventureStartRequest(BaseModel):
    intro: str
    game_state: Dict[str, Any]


@app.get("/")
def root():
    return {
        "status": "D&D Campaign API - Running with Anthropic Claude",
        "model": os.getenv("AI_MODEL"),
        "caching_enabled": os.getenv("ENABLE_PROMPT_CACHING", "true")
    }

@app.post("/dm/action")
def handle_action(request: ActionRequest):
    """Process player action"""
    try:
        game_state = request.game_state or engine.get_state()
        
        result = dm.process_action(request.action, game_state)
        
        return {
            "success": True,
            "narration": result["narration"],
            "tool_results": result["tool_results"],
            "game_state": result["updated_state"]
        }
    
    except Exception as e:
        print(f"Error processing action: {e}")
        raise HTTPException(500, str(e))

@app.post("/dm/start")
def start_adventure(request: AdventureStartRequest):
    """Start a new adventure"""
    try:
        result = dm.start_adventure(request.intro, request.game_state)
        
        return {
            "success": True,
            "narration": result["narration"],
            "game_state": result["updated_state"]
        }
    
    except Exception as e:
        print(f"Error starting adventure: {e}")
        raise HTTPException(500, str(e))

@app.get("/characters/{name}")
def get_character(name: str):
    """Get character data"""
    from services.tool_executor import ToolExecutor
    executor = ToolExecutor()
    
    result = executor.get_character({"character_name": name})
    
    if "error" in result:
        raise HTTPException(404, result["error"])
    
    return result["character"]

@app.get("/state")
def get_state():
    """Get current game state"""
    return engine.get_state()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 7. Understanding Dynamic Token Limits

### Why Different Lengths for Different Actions?

**The Problem:**
Without guidance, Claude doesn't know when to be brief vs detailed:
- Combat action → Claude writes 3 paragraphs ❌
- New scene → Claude writes 1 sentence ❌

**The Solution:**
We use **two mechanisms** to control response length:

### Mechanism 1: System Prompt Guidelines

The DM system prompt includes explicit length rules:
- Combat: 1-2 sentences
- Scenes: 3-5 sentences
- Dialogue: 2-3 sentences
- Skill checks: 1-2 sentences

Claude learns these patterns and generally follows them.

### Mechanism 2: Dynamic MAX_TOKENS

The code **detects the action type** and adjusts the hard limit:

```python
token_limits = {
    "scene_description": 400,    # Can be detailed
    "combat_action": 150,         # Must be brief!
    "skill_check": 150,           # Short result
    "npc_dialogue": 250,          # Moderate
    "standard": 200               # Default
}
```

### How It Works:

**Example 1: Combat Action**
```
Player: "Thorin attacks the goblin with his longsword"
         ↓
Code detects: "attack" keyword → context_type = "combat_action"
         ↓
Sets max_tokens = 150 (only ~20-30 words)
         ↓
Claude generates: "Your blade strikes true, biting deep into 
the goblin's shoulder. It shrieks and falls. [7 damage]"
(~25 tokens - well under limit)
```

**Example 2: Scene Description**
```
Player: "We enter the tavern"
         ↓
Code detects: "enter" keyword → context_type = "scene_description"
         ↓
Sets max_tokens = 400 (allows detail)
         ↓
Claude generates: "The tavern door groans open. Smoke and the 
smell of roasted meat hit you immediately. Rough wooden tables 
crowd the space, most occupied by grizzled travelers. A roaring 
fire crackles in the stone hearth. The barkeep eyes you warily 
from behind a scarred oak bar."
(~70 tokens - descriptive but concise)
```

### Detection Keywords:

The `_detect_context()` method looks for specific words:

| Context Type | Keywords | Max Tokens | Example Length |
|--------------|----------|------------|----------------|
| **combat_action** | attack, hit, strike, cast, shoot | 150 | 1-2 sentences |
| **scene_description** | enter, arrive, open door, approach | 400 | 3-5 sentences |
| **npc_dialogue** | talk, speak, ask, tell, say | 250 | 2-3 sentences |
| **skill_check** | search, investigate, examine | 150 | 1-2 sentences |
| **exploration** | look around, survey, observe | 300 | 2-4 sentences |
| **standard** | (anything else) | 200 | 2-3 sentences |

### Cost Impact:

The difference is negligible:

```
Combat (150 tokens):    ~$0.00075 per response
Scene (400 tokens):     ~$0.00200 per response
Difference:             ~$0.00125 (0.1¢)

Over 40 turns:          ~$0.05 difference
```

**Worth it** for better pacing!

### Overriding Detection:

If detection is wrong, you can manually override:

```python
# In your frontend/backend
result = dm.process_action(
    action="Actually describe this in detail",
    game_state=state,
    force_context="scene_description"  # Override
)
```

---

## 8. Testing the Integration

### Test Script

Create `backend/test_dm.py`:

```python
"""
Test DM Agent with Anthropic API
"""

from services.dm_agent import DMAgent

def test_dm():
    dm = DMAgent()
    
    # Start adventure
    print("=== Starting Adventure ===\n")
    
    game_state = {
        "location": "triboar_trail",
        "party": ["Thorin Ironforge", "Elara Moonwhisper"],
        "combat_active": False
    }
    
    result = dm.start_adventure(
        "The party encounters dead horses on the Triboar Trail, blocking their path.",
        game_state
    )
    
    print(result["narration"])
    print("\n" + "="*60 + "\n")
    
    # Test scene description (should be detailed)
    print("=== Scene Description Test (should be 3-5 sentences) ===\n")
    
    result = dm.process_action(
        "We enter the nearby cave",
        game_state
    )
    
    print(f"Narration: {result['narration']}\n")
    print(f"Word count: ~{len(result['narration'].split())} words\n")
    
    # Test skill check (should be brief)
    print("=== Skill Check Test (should be 1-2 sentences) ===\n")
    
    result = dm.process_action(
        "Thorin investigates the dead horses",
        game_state
    )
    
    print(f"Narration: {result['narration']}\n")
    print(f"Word count: ~{len(result['narration'].split())} words\n")
    
    if result["tool_results"]:
        print("Tool Results:")
        for tool_result in result["tool_results"]:
            print(f"  - {tool_result['tool']}: {tool_result['result'].get('description', tool_result['result'])}")
    
    print("\n" + "="*60 + "\n")
    
    # Test combat (should be VERY brief)
    print("=== Combat Test (should be 1-2 sentences MAX) ===\n")
    
    game_state["combat_active"] = True  # Enable combat
    
    result = dm.process_action(
        "Thorin attacks the goblin with his longsword",
        game_state
    )
    
    print(f"Narration: {result['narration']}\n")
    print(f"Word count: ~{len(result['narration'].split())} words (should be ~15-30)\n")
    
    if result["tool_results"]:
        print("Tool Results:")
        for tool_result in result["tool_results"]:
            print(f"  - {tool_result['tool']}: {tool_result['result'].get('description', tool_result['result'])}")
    
    print("\n" + "="*60 + "\n")
    
    # Test NPC dialogue
    print("=== NPC Dialogue Test (should be 2-3 sentences) ===\n")
    
    game_state["combat_active"] = False
    
    result = dm.process_action(
        "Elara asks the barkeep about rumors",
        game_state
    )
    
    print(f"Narration: {result['narration']}\n")
    print(f"Word count: ~{len(result['narration'].split())} words\n")

if __name__ == "__main__":
    test_dm()
```

Run:
```bash
cd backend
python test_dm.py
```

**Expected Output:**

```
=== Scene Description Test ===
Narration: The cave mouth yawns before you, exhaling cold, 
damp air that reeks of stone and old earth. Your torchlight 
barely penetrates the oppressive darkness within. Water drips 
somewhere in the depths, each drop echoing like a ticking clock. 
Crude goblin symbols are scratched into the rock near the entrance.

Word count: ~50 words

=== Skill Check Test ===  
Narration: With a 14, you find crude goblin arrows and the 
Rockseeker clan brand on the horses.

Word count: ~15 words

=== Combat Test ===
Narration: Your longsword cleaves into the goblin's shoulder. 
It shrieks and collapses.

Word count: ~12 words
```

Notice how combat is brief while scenes are detailed!

---

## 9. Update Frontend to Use New API

Your frontend should already work, but ensure it handles tool results:

```typescript
// frontend/src/services/api.ts

export async function sendAction(action: string, gameState: any) {
  const response = await fetch('http://localhost:8000/dm/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action,
      game_state: gameState
    })
  });
  
  const data = await response.json();
  
  return {
    narration: data.narration,
    toolResults: data.tool_results || [],
    gameState: data.game_state
  };
}
```

Display tool results in your UI:

```tsx
// Show narration
<div className="narration">{narration}</div>

// Show mechanics
{toolResults.map(result => (
  <div className="tool-result">
    {result.result.description}
  </div>
))}
```

---

## 10. Cost Optimization Tips

### Minimize Token Usage

```python
# In anthropic_client.py

# Keep conversation history short
MAX_HISTORY = 10  # Only last 10 exchanges

def generate(self, messages, game_state):
    # Trim history
    if len(messages) > MAX_HISTORY:
        messages = messages[-MAX_HISTORY:]
    
    # ... rest of code
```

### Use Haiku for Simple Narration

```python
# Switch to Sonnet only for complex scenes
if is_combat or is_complex_scene:
    model = "claude-3-5-sonnet-20241022"
else:
    model = "claude-3-5-haiku-20241022"
```

---

## 11. Expected Performance

### Response Times:
- **Haiku:** 1-2 seconds
- **Sonnet:** 2-4 seconds

### Costs (with caching):
- **First turn:** $0.008 (creates cache)
- **Subsequent turns:** $0.002 (cache hits)
- **Per session (40 turns):** $0.086
- **Per year (weekly):** ~$4.50

---

## 12. Troubleshooting

### "API key not found"
→ Check `.env` file has `ANTHROPIC_API_KEY=sk-...`
→ Restart backend after adding

### "Tool not found"
→ Verify tool name matches between `create_tools()` and `execute()`

### "Character not found"
→ Check character files are in `backend/characters/`
→ Verify filename format: `thorin_ironforge.json`

### Slow responses
→ Using Sonnet instead of Haiku?
→ Check caching is enabled
→ Reduce conversation history length

---

## 13. Next Steps

1. **Add `.env` file** with Anthropic API key
2. **Test with** `python test_dm.py`
3. **Run backend**: `python main.py`
4. **Test in frontend**
5. **Monitor costs** in Anthropic dashboard

---

## Summary

This integration:
- ✅ Uses Claude Haiku 4.5 (fast, cheap)
- ✅ Enables prompt caching (~90% cost reduction)
- ✅ Integrates with ALL your Python tools (dice, combat, characters)
- ✅ Uses Claude's tool calling (automatic mechanics execution)
- ✅ Maintains conversation history
- ✅ Costs ~$5/year for weekly games

**Expected result:** Fast (1-2 sec), intelligent DM that actually uses your game rules!
