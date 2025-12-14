"""
Game Engine - Core D&D 5e Mechanics

Handles dice rolling, skill checks, combat, and character management.
Uses ported modules from the previous game engine implementation.
"""

import random
from typing import Dict, Any, List, Optional
from pathlib import Path
import json

from .roller import roll, roll_with_advantage, roll_with_disadvantage
from .combat import CombatEngine, attack_roll, apply_damage, heal
from .skills import skill_check, ability_save, get_ability_modifier, SKILL_ABILITIES


class GameEngine:
    """
    Core D&D 5e game mechanics

    Handles dice rolling, skill checks, combat, and character management.
    All methods are deterministic and rule-based - NO AI interpretation.
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.characters: Dict[str, Dict] = {}
        self.npcs: Dict[str, Dict] = {}
        self.combat_engine = CombatEngine()
        self.combat_state: Dict[str, Any] = {"active": False}
        self.session_id: str = "default-session"
        self.campaign: str = "default-campaign"

        # Load characters and NPCs
        self._load_characters()

    def _load_characters(self):
        """Load character and NPC data from JSON files"""
        char_dir = self.data_dir / "characters"
        if char_dir.exists():
            for char_file in char_dir.glob("*.json"):
                with open(char_file) as f:
                    char_data = json.load(f)
                    self.characters[char_data["name"]] = char_data

        npc_dir = self.data_dir / "npcs"
        if npc_dir.exists():
            for npc_file in npc_dir.glob("*.json"):
                with open(npc_file) as f:
                    npc_data = json.load(f)
                    self.npcs[npc_data["name"]] = npc_data

    def roll_dice(self, dice: str) -> Dict[str, Any]:
        """
        Roll dice using standard notation

        Args:
            dice: Dice notation (e.g., "2d6+3", "1d20")

        Returns:
            int: The total result
        """
        try:
            total = roll(dice)
            return {
                "total": total,
                "notation": dice,
            }
        except ValueError as e:
            return {"error": str(e)}

    def skill_check(
        self,
        character: str,
        skill: str,
        dc: int,
        advantage: bool = False,
        disadvantage: bool = False,
    ) -> Dict[str, Any]:
        """
        Make a skill check using the ported skill system
        """
        char_data = self.characters.get(character) or self.npcs.get(character)
        if not char_data:
            return {"error": f"Character not found: {character}"}

        # Use the imported skill_check function
        result = skill_check(char_data, skill, dc, advantage, disadvantage)
        result["character"] = character
        result["skill"] = skill

        return result

    def saving_throw(
        self,
        character: str,
        ability: str,
        dc: int,
        advantage: bool = False,
        disadvantage: bool = False,
    ) -> Dict[str, Any]:
        """Make a saving throw using the ported ability save system"""
        char_data = self.characters.get(character) or self.npcs.get(character)
        if not char_data:
            return {"error": f"Character not found: {character}"}

        # Use the imported ability_save function
        result = ability_save(char_data, ability, dc, advantage, disadvantage)
        result["character"] = character
        result["ability"] = ability

        return result

    def attack_roll(
        self,
        attacker: str,
        target: str,
        weapon: Optional[str] = None,
        advantage: bool = False,
        disadvantage: bool = False,
    ) -> Dict[str, Any]:
        """
        Make an attack roll using the ported combat system
        """
        attacker_data = self.characters.get(attacker) or self.npcs.get(attacker)
        target_data = self.characters.get(target) or self.npcs.get(target)

        if not attacker_data:
            return {"error": f"Attacker not found: {attacker}"}
        if not target_data:
            return {"error": f"Target not found: {target}"}

        # Use the imported attack_roll function
        result = attack_roll(attacker_data, target_data, advantage, disadvantage)
        result["attacker"] = attacker
        result["target"] = target

        # If the attack hit, apply damage to the target
        if result.get("hit"):
            damage = result.get("damage", 0)
            if damage > 0:
                damage_result = apply_damage(target_data, damage)
                result["damage_result"] = damage_result

        return result

    def update_hp(self, character: str, hp_change: int) -> Dict[str, Any]:
        """Update character HP using ported heal/damage functions"""
        char_data = self.characters.get(character) or self.npcs.get(character)
        if not char_data:
            return {"error": f"Character not found: {character}"}

        # Ensure current_hp is set
        if "hp" not in char_data and "current_hp" in char_data:
            char_data["hp"] = char_data["current_hp"]
        elif "hp" not in char_data:
            char_data["hp"] = char_data.get("max_hp", 0)

        if hp_change > 0:
            # Healing
            heal(char_data, hp_change)
            result = {
                "character": character,
                "change": hp_change,
                "new_hp": char_data["hp"],
                "max_hp": char_data.get("max_hp"),
                "healed": True,
            }
        else:
            # Damage
            damage_result = apply_damage(char_data, abs(hp_change))
            result = {
                "character": character,
                "change": hp_change,
                "new_hp": damage_result["current_hp"],
                "max_hp": damage_result["max_hp"],
                "status": damage_result["status"],
                "damage_taken": damage_result["damage_taken"],
            }

        # Keep current_hp in sync with hp
        char_data["current_hp"] = char_data["hp"]

        return result

    def start_combat(self, participants: List[str]) -> Dict[str, Any]:
        """Start combat and roll initiative using ported CombatEngine"""
        combatants = []

        for participant in participants:
            char_data = self.characters.get(participant) or self.npcs.get(participant)
            if char_data:
                # Get dexterity modifier
                dex_score = char_data.get("abilities", {}).get("dex", 10)
                dex_mod = get_ability_modifier(dex_score)

                combatants.append({
                    "name": participant,
                    "dex_mod": dex_mod,
                    "is_player": participant in self.characters,
                })

        # Use CombatEngine to roll initiative
        initiative_order = self.combat_engine.roll_initiative(combatants)

        self.combat_state = {
            "active": True,
            "round": self.combat_engine.round_number,
            "turn_order": [p["name"] for p in initiative_order],
            "current_turn": initiative_order[0]["name"] if initiative_order else None,
        }

        return {
            "initiative_order": initiative_order,
            "current_turn": self.combat_state["current_turn"],
        }

    def end_combat(self) -> Dict[str, Any]:
        """End combat"""
        self.combat_state = {"active": False}
        return {"message": "Combat ended"}

    def get_character(self, character: str) -> Dict[str, Any]:
        """Get character information"""
        char_data = self.characters.get(character) or self.npcs.get(character)
        if not char_data:
            return {"error": f"Character not found: {character}"}

        return char_data

    def add_to_inventory(
        self, character: str, item: str, quantity: int = 1
    ) -> Dict[str, Any]:
        """Add item to character inventory"""
        char_data = self.characters.get(character)
        if not char_data:
            return {"error": f"Character not found: {character}"}

        if "inventory" not in char_data:
            char_data["inventory"] = []

        char_data["inventory"].append({"item": item, "quantity": quantity})

        return {"character": character, "item": item, "quantity": quantity}

    def get_state(self) -> Dict[str, Any]:
        """Get current game state"""
        return {
            "session_id": self.session_id,
            "campaign": self.campaign,
            "characters": self.characters,
            "npcs": self.npcs,
            "combat": self.combat_state,
            "quest_log": [],
            "world_state": {},
            "party_inventory": [],
            "location": None,
        }
