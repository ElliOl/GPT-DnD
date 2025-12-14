"""
D&D 5e Game Engine

Core mechanics for D&D 5e including:
- Dice rolling with advantage/disadvantage
- Skill checks and ability saves
- Combat system with initiative and attacks
- Character management
"""

from .engine import GameEngine
from .roller import roll, roll_with_advantage, roll_with_disadvantage
from .combat import CombatEngine, attack_roll, apply_damage, heal
from .skills import skill_check, ability_save, get_ability_modifier, SKILL_ABILITIES

__all__ = [
    "GameEngine",
    "roll",
    "roll_with_advantage",
    "roll_with_disadvantage",
    "CombatEngine",
    "attack_roll",
    "apply_damage",
    "heal",
    "skill_check",
    "ability_save",
    "get_ability_modifier",
    "SKILL_ABILITIES",
]
