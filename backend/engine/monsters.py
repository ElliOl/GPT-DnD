"""
Minimal stat blocks for combatants the module never named.

A module authors named NPCs (Klarg, King Grol) but not the dozen interchangeable
goblins between the party and them — those only ever existed as prose until now.
This is a small, code-owned table rather than letting an LLM invent HP and AC for
something it's about to fight; anything not listed falls back to a generic weak
monster rather than refusing to spawn at all.
"""

from __future__ import annotations

from typing import Any

#: 5e basic stat blocks, keyed by lowercase singular name. Small and
#: purpose-built for early Lost Mine of Phandelver encounters — extend as new
#: creature types actually come up in play, not speculatively.
STAT_BLOCKS: dict[str, dict[str, Any]] = {
    "goblin": {
        "hp": 7, "max_hp": 7, "ac": 15, "level": 1,
        "stats": {"STR": 8, "DEX": 14, "CON": 10, "INT": 10, "WIS": 8, "CHA": 8},
        "weapons": [{"name": "Scimitar", "attack_bonus": 4, "damage_dice": "1d6", "damage_bonus": 2, "damage_type": "slashing"}],
    },
    "wolf": {
        "hp": 11, "max_hp": 11, "ac": 13, "level": 1,
        "stats": {"STR": 12, "DEX": 15, "CON": 12, "INT": 3, "WIS": 12, "CHA": 6},
        "weapons": [{"name": "Bite", "attack_bonus": 4, "damage_dice": "2d4", "damage_bonus": 2, "damage_type": "piercing"}],
    },
    "bugbear": {
        "hp": 27, "max_hp": 27, "ac": 16, "level": 3,
        "stats": {"STR": 15, "DEX": 14, "CON": 13, "INT": 8, "WIS": 11, "CHA": 9},
        "weapons": [{"name": "Morningstar", "attack_bonus": 4, "damage_dice": "2d8", "damage_bonus": 2, "damage_type": "piercing"}],
    },
    "hobgoblin": {
        "hp": 11, "max_hp": 11, "ac": 18, "level": 1,
        "stats": {"STR": 13, "DEX": 12, "CON": 12, "INT": 10, "WIS": 10, "CHA": 9},
        "weapons": [{"name": "Longsword", "attack_bonus": 3, "damage_dice": "1d8", "damage_bonus": 1, "damage_type": "slashing"}],
    },
}

#: Used when the name doesn't match anything above — a plausible weak mook
#: rather than a refusal. Deliberately unremarkable; a real encounter should
#: get its own entry in the table above once it comes up.
GENERIC_FALLBACK: dict[str, Any] = {
    "hp": 9, "max_hp": 9, "ac": 12, "level": 1,
    "stats": {"STR": 11, "DEX": 11, "CON": 11, "INT": 10, "WIS": 10, "CHA": 10},
    "weapons": [{"name": "Improvised weapon", "attack_bonus": 3, "damage_dice": "1d6", "damage_bonus": 1, "damage_type": "bludgeoning"}],
}


def stat_block_for(name: str) -> dict[str, Any]:
    """Look up a stat block by creature name, matching loosely on the first word
    ("goblin" out of "goblin warrior") before falling back to a generic mook."""
    key = name.strip().lower()
    if key in STAT_BLOCKS:
        return dict(STAT_BLOCKS[key])
    first_word = key.split()[0] if key.split() else key
    if first_word in STAT_BLOCKS:
        return dict(STAT_BLOCKS[first_word])
    return dict(GENERIC_FALLBACK)
