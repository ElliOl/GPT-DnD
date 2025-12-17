"""
Game State Models

Defines the structure for game state, characters, encounters, etc.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from enum import Enum


class AbilityScores(BaseModel):
    """Character ability scores"""

    STR: int = 10
    DEX: int = 10
    CON: int = 10
    INT: int = 10
    WIS: int = 10
    CHA: int = 10


class Character(BaseModel):
    """Player or NPC character"""

    name: str
    race: str
    char_class: str  # 'class' is reserved keyword
    level: int = 1
    max_hp: int
    current_hp: int
    armor_class: int
    abilities: AbilityScores
    proficiency_bonus: int = 2
    skills: Dict[str, bool] = {}  # skill_name: is_proficient
    inventory: List[str] = []
    conditions: List[str] = []  # stunned, poisoned, etc.


class CombatState(BaseModel):
    """Current combat encounter state"""

    active: bool = False
    round: int = 0
    turn_order: List[str] = []  # Character names in initiative order
    current_turn: Optional[str] = None


class GameState(BaseModel):
    """Complete game state"""

    session_id: str
    campaign: str
    characters: Dict[str, Character] = {}
    npcs: Dict[str, Character] = {}
    combat: CombatState = CombatState()
    quest_log: List[Dict[str, Any]] = []
    world_state: Dict[str, Any] = {}  # Flags, decisions, etc.
    party_inventory: List[str] = []
    location: Optional[str] = None


class PlayerAction(BaseModel):
    """Player input action"""

    message: str
    character: Optional[str] = None  # Which character is acting
    voice: bool = False  # Whether to generate TTS response
    adventure_context: Optional[Dict[str, Any]] = None  # Adventure-specific context
    session_state: Optional[Dict[str, Any]] = None  # Session state (quest log, world state, etc.)


class DMResponse(BaseModel):
    """DM response to player action"""

    narrative: str
    audio_url: Optional[str] = None
    game_state: GameState
    tool_results: List[Dict[str, Any]] = []
    cost: Optional[Dict[str, int]] = None  # Token usage for transparency
    quest_updates: Optional[List[Dict[str, Any]]] = []  # Automatic quest log updates from narrative
