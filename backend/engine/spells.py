"""
Attack-roll spells the module doesn't stat.

A weapon has a damage die and type on the character sheet; a spell attack like
Fire Bolt has neither anywhere in this codebase, so it silently fell through
to pure narrative guesswork — no roll, no damage, no combat continuation, the
DM improvising a kill with nothing backing it. Same shape as
``backend/engine/monsters.py``: a small code-owned table, extended as new
spells actually come up in play rather than speculatively.

Save-based spells (Magic Missile's autohit aside) already have a path via a
module's item catalog (``save_ability``) — this table is only for the ones
that roll to hit like a weapon does.
"""

from __future__ import annotations

from typing import Any

#: Genuine spell-*attack* cantrips only (roll to hit vs AC, like a weapon).
#: Acid Splash, Vicious Mockery, Frostbite, Toll the Dead, Sacred Flame etc.
#: are saving-throw spells in actual 5e — those go through the save_ability
#: path in a module's item catalog instead, not this table.
ATTACK_SPELLS: dict[str, dict[str, Any]] = {
    "fire bolt": {"damage_dice": "1d10", "damage_type": "fire", "ranged": True},
    "ray of frost": {"damage_dice": "1d8", "damage_type": "cold", "ranged": True},
    "eldritch blast": {"damage_dice": "1d10", "damage_type": "force", "ranged": True},
    "shocking grasp": {"damage_dice": "1d8", "damage_type": "lightning"},
    "chill touch": {"damage_dice": "1d8", "damage_type": "necrotic", "ranged": True},
    "produce flame": {"damage_dice": "1d8", "damage_type": "fire", "ranged": True},
}


def attack_spell(name: str) -> dict[str, Any] | None:
    return ATTACK_SPELLS.get(name.strip().lower())
