"""
The rules engine. NO LLM CALLS IN HERE — that is the whole point of the package.

Deterministic, seeded, and unit-tested without an API key. ``resolve`` is the
single entry point; everything else supports it.
"""

from .character import Combatant
from .dice import DiceRoller, Roll, campaign_seed
from .intent import Intent
from .resolve import GameState, Resolution, resolve

__all__ = [
    "Combatant",
    "DiceRoller",
    "GameState",
    "Intent",
    "Resolution",
    "Roll",
    "campaign_seed",
    "resolve",
]
