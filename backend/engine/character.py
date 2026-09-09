"""
Character sheets as plain data.

``Combatant`` is the engine's view of a creature — a snapshot loaded from the DB,
operated on by the rules, and written back as deltas. It deliberately knows
nothing about the database or about prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ABILITIES = ("STR", "DEX", "CON", "INT", "WIS", "CHA")

SKILL_ABILITY: dict[str, str] = {
    "acrobatics": "DEX",
    "animal handling": "WIS",
    "arcana": "INT",
    "athletics": "STR",
    "deception": "CHA",
    "history": "INT",
    "insight": "WIS",
    "intimidation": "CHA",
    "investigation": "INT",
    "medicine": "WIS",
    "nature": "INT",
    "perception": "WIS",
    "performance": "CHA",
    "persuasion": "CHA",
    "religion": "INT",
    "sleight of hand": "DEX",
    "stealth": "DEX",
    "survival": "WIS",
}

#: Conditions that stop a creature acting at all.
INCAPACITATING = {"unconscious", "paralyzed", "petrified", "stunned", "incapacitated"}


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


@dataclass
class Combatant:
    id: str
    name: str
    hp: int
    max_hp: int
    ac: int
    stats: dict[str, int] = field(default_factory=dict)
    proficiency_bonus: int = 2
    level: int = 1
    is_pc: bool = True
    speed: int = 30
    temp_hp: int = 0
    conditions: list[str] = field(default_factory=list)
    resources: dict[str, Any] = field(default_factory=dict)
    proficiencies: dict[str, Any] = field(default_factory=dict)
    death_save_successes: int = 0
    death_save_failures: int = 0
    location_id: str | None = None
    #: Whether an automatic NPC turn should treat this combatant as an enemy
    #: to swing at the party. Defaults True — a bare statted monster (no NPCRow
    #: behind it, e.g. a test fixture) is always presumed hostile, matching
    #: what "PCs and statted NPCs alike" has always meant here. A combatant
    #: backed by an NPCRow gets this overridden from its actual attitude, so
    #: an ally caught in the fight doesn't get swept into attacking the party.
    hostile: bool = True

    # ---- derived ----------------------------------------------------------

    def modifier(self, ability: str) -> int:
        return ability_modifier(self.stats.get(ability.upper(), 10))

    def has_skill_proficiency(self, skill: str) -> bool:
        listed = [str(s).lower() for s in self.proficiencies.get("skills", [])]
        return skill.lower() in listed

    def has_expertise(self, skill: str) -> bool:
        listed = [str(s).lower() for s in self.proficiencies.get("expertise", [])]
        return skill.lower() in listed

    def has_save_proficiency(self, ability: str) -> bool:
        listed = [str(s).upper() for s in self.proficiencies.get("saves", [])]
        return ability.upper() in listed

    def skill_bonus(self, skill: str) -> int:
        ability = SKILL_ABILITY.get(skill.lower(), "STR")
        bonus = self.modifier(ability)
        if self.has_expertise(skill):
            bonus += self.proficiency_bonus * 2
        elif self.has_skill_proficiency(skill):
            bonus += self.proficiency_bonus
        return bonus

    def save_bonus(self, ability: str) -> int:
        bonus = self.modifier(ability)
        if self.has_save_proficiency(ability):
            bonus += self.proficiency_bonus
        return bonus

    @property
    def is_down(self) -> bool:
        return self.hp <= 0

    @property
    def can_act(self) -> bool:
        return not self.is_down and not (INCAPACITATING & {c.lower() for c in self.conditions})

    def has_condition(self, name: str) -> bool:
        return name.lower() in {c.lower() for c in self.conditions}

    # ---- resources --------------------------------------------------------

    def spell_slots(self, level: int) -> int:
        return int((self.resources.get("spell_slots") or {}).get(str(level), 0))

    def has_slot(self, level: int) -> bool:
        return self.spell_slots(level) > 0

    def has_item(self, item_id: str) -> bool:
        return item_id.lower() in {str(i).lower() for i in self.resources.get("inventory", [])}

    # ---- construction -----------------------------------------------------

    @classmethod
    def from_row(cls, row, inventory: list[str] | None = None) -> "Combatant":
        """Build from a ``CharacterRow`` without importing the ORM here."""
        resources = dict(row.resources or {})
        if inventory is not None:
            resources["inventory"] = inventory
        return cls(
            id=row.id,
            name=row.name,
            hp=row.hp,
            max_hp=row.max_hp,
            ac=row.ac,
            stats=dict(row.stats or {}),
            proficiency_bonus=row.proficiency_bonus,
            level=row.level,
            is_pc=row.is_pc,
            speed=row.speed,
            temp_hp=row.temp_hp,
            conditions=list(row.conditions or []),
            resources=resources,
            proficiencies=dict(row.proficiencies or {}),
            death_save_successes=row.death_save_successes,
            death_save_failures=row.death_save_failures,
            location_id=row.location_id,
        )


def proficiency_for_level(level: int) -> int:
    return 2 + (max(1, level) - 1) // 4
