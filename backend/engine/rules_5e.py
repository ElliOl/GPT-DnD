"""
D&D 5e resolution primitives: checks, saves, attacks, damage.

Every function here takes a roller and returns a structured outcome. None of them
touch the database — they compute, and ``resolve.py`` turns the outcome into
deltas. That split is what lets the whole file be unit-tested with no API key and
no fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .character import Combatant
from .dice import Advantage, DiceRoller, Roll

Degree = Literal["crit_fail", "fail", "partial", "success", "crit_success"]

DC_BY_NAME = {
    "trivial": 5,
    "easy": 10,
    "medium": 12,
    "moderate": 15,
    "hard": 18,
    "very_hard": 20,
    "nearly_impossible": 25,
}

DAMAGE_TYPES = {
    "acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic",
    "piercing", "poison", "psychic", "radiant", "slashing", "thunder",
}

#: Conditions that hand the attacker advantage against their bearer.
ADVANTAGE_AGAINST = {"blinded", "paralyzed", "petrified", "prone", "restrained", "stunned", "unconscious"}
#: Conditions that impose disadvantage on their bearer's own d20 rolls.
DISADVANTAGE_SELF = {"blinded", "poisoned", "frightened", "restrained", "prone"}


def combine_advantage(advantage: bool, disadvantage: bool) -> Advantage:
    """5e stacks nothing: any advantage plus any disadvantage is a flat roll."""
    if advantage and disadvantage:
        return "normal"
    if advantage:
        return "advantage"
    if disadvantage:
        return "disadvantage"
    return "normal"


def degree_of_success(roll: Roll, dc: int, *, is_d20: bool = True) -> Degree:
    """Four-tier outcome. ``partial`` is missing by 1-2 — the band where a DM
    says "yes, but". The Narrator is told which band it landed in and describes it."""
    if is_d20:
        if roll.natural == 20:
            return "crit_success"
        if roll.natural == 1:
            return "crit_fail"
    if roll.total >= dc:
        return "success"
    if roll.total >= dc - 2:
        return "partial"
    return "fail"


@dataclass
class CheckOutcome:
    kind: str
    actor_id: str
    roll: Roll
    dc: int
    success: bool
    degree: Degree
    detail: str = ""
    extra_rolls: list[Roll] = field(default_factory=list)


def ability_check(
    actor: Combatant,
    skill_or_ability: str,
    dc: int,
    roller: DiceRoller,
    *,
    advantage: bool = False,
    disadvantage: bool = False,
) -> CheckOutcome:
    """A skill check when ``skill_or_ability`` names a skill, a raw ability check otherwise."""
    from .character import SKILL_ABILITY

    key = skill_or_ability.lower()
    if key in SKILL_ABILITY:
        bonus = actor.skill_bonus(key)
        label = skill_or_ability.title()
    else:
        bonus = actor.modifier(skill_or_ability)
        label = skill_or_ability.upper()

    disadvantage = disadvantage or bool(
        DISADVANTAGE_SELF & {c.lower() for c in actor.conditions}
    )
    adv = combine_advantage(advantage, disadvantage)
    roll = roller.d20(bonus, purpose=f"{label} check", advantage=adv)
    degree = degree_of_success(roll, dc)
    return CheckOutcome(
        kind="check",
        actor_id=actor.id,
        roll=roll,
        dc=dc,
        success=degree in ("success", "crit_success"),
        degree=degree,
        detail=label,
    )


def saving_throw(
    actor: Combatant,
    ability: str,
    dc: int,
    roller: DiceRoller,
    *,
    advantage: bool = False,
    disadvantage: bool = False,
) -> CheckOutcome:
    adv = combine_advantage(advantage, disadvantage)
    roll = roller.d20(actor.save_bonus(ability), purpose=f"{ability.upper()} save", advantage=adv)
    degree = degree_of_success(roll, dc)
    return CheckOutcome(
        kind="save",
        actor_id=actor.id,
        roll=roll,
        dc=dc,
        success=degree in ("success", "crit_success"),
        degree=degree,
        detail=ability.upper(),
    )


@dataclass
class AttackOutcome:
    attacker_id: str
    target_id: str
    attack_roll: Roll
    target_ac: int
    hit: bool
    critical: bool
    damage: int = 0
    damage_type: str = "bludgeoning"
    damage_roll: Roll | None = None
    weapon: str = ""


def attack(
    attacker: Combatant,
    target: Combatant,
    roller: DiceRoller,
    *,
    attack_bonus: int | None = None,
    damage_dice: str = "1d6",
    damage_type: str = "bludgeoning",
    weapon: str = "",
    advantage: bool = False,
    disadvantage: bool = False,
    finesse: bool = False,
    ranged: bool = False,
) -> AttackOutcome:
    """A single attack. Nat 20 always hits and crits; nat 1 always misses."""
    if attack_bonus is None:
        ability = "DEX" if (ranged or finesse) else "STR"
        attack_bonus = attacker.modifier(ability) + attacker.proficiency_bonus

    advantage = advantage or bool(ADVANTAGE_AGAINST & {c.lower() for c in target.conditions})
    disadvantage = disadvantage or bool(
        DISADVANTAGE_SELF & {c.lower() for c in attacker.conditions}
    )
    adv = combine_advantage(advantage, disadvantage)

    roll = roller.d20(attack_bonus, purpose=f"attack: {weapon or 'strike'}", advantage=adv)
    critical = roll.natural == 20
    auto_miss = roll.natural == 1
    hit = critical or (not auto_miss and roll.total >= target.ac)

    outcome = AttackOutcome(
        attacker_id=attacker.id,
        target_id=target.id,
        attack_roll=roll,
        target_ac=target.ac,
        hit=hit,
        critical=critical,
        damage_type=damage_type,
        weapon=weapon,
    )
    if hit:
        ability = "DEX" if (ranged or finesse) else "STR"
        mod = attacker.modifier(ability)
        notation = damage_dice if mod == 0 else f"{damage_dice}{'+' if mod > 0 else '-'}{abs(mod)}"
        damage_roll = roller.damage(notation, critical=critical, purpose="damage")
        outcome.damage_roll = damage_roll
        outcome.damage = max(0, damage_roll.total)
    return outcome


def apply_damage(target: Combatant, amount: int, damage_type: str = "") -> dict:
    """Resolve damage against temp HP first, then HP. Returns what changed.

    Death is not decided here — dropping to 0 sets ``unconscious`` and the death
    save track; ``combat.py`` runs the saves.
    """
    resistances = {str(r).lower() for r in (target.resources.get("resistances") or [])}
    immunities = {str(r).lower() for r in (target.resources.get("immunities") or [])}
    vulnerabilities = {str(r).lower() for r in (target.resources.get("vulnerabilities") or [])}

    dt = damage_type.lower()
    if dt and dt in immunities:
        amount = 0
    elif dt and dt in resistances:
        amount //= 2
    elif dt and dt in vulnerabilities:
        amount *= 2

    absorbed = min(target.temp_hp, amount)
    target.temp_hp -= absorbed
    to_hp = amount - absorbed
    before = target.hp
    target.hp = max(0, target.hp - to_hp)

    dropped = before > 0 and target.hp == 0
    if dropped and not target.has_condition("unconscious"):
        target.conditions.append("unconscious")

    return {
        "amount": amount,
        "absorbed_by_temp_hp": absorbed,
        "hp_before": before,
        "hp_after": target.hp,
        "dropped": dropped,
        "damage_type": damage_type,
    }


def apply_healing(target: Combatant, amount: int) -> dict:
    """Any healing above 0 revives an unconscious creature and clears death saves."""
    before = target.hp
    target.hp = min(target.max_hp, target.hp + max(0, amount))
    revived = before == 0 and target.hp > 0
    if revived:
        target.conditions = [c for c in target.conditions if c.lower() != "unconscious"]
        target.death_save_successes = 0
        target.death_save_failures = 0
    return {"amount": target.hp - before, "hp_before": before, "hp_after": target.hp, "revived": revived}


def spend_spell_slot(actor: Combatant, level: int) -> bool:
    """Decrement a slot. Returns False if there was none — the caller turns that
    into an ``invalid`` resolution rather than letting the Narrator improvise one."""
    slots = dict(actor.resources.get("spell_slots") or {})
    key = str(level)
    if int(slots.get(key, 0)) <= 0:
        return False
    slots[key] = int(slots[key]) - 1
    actor.resources["spell_slots"] = slots
    return True


def spell_save_dc(caster: Combatant, ability: str = "INT") -> int:
    return 8 + caster.proficiency_bonus + caster.modifier(ability)


def passive_score(actor: Combatant, skill: str) -> int:
    return 10 + actor.skill_bonus(skill)


def short_rest(actor: Combatant, hit_dice_spent: int, roller: DiceRoller, hit_die: int = 8) -> dict:
    """Spend hit dice for healing. Con modifier per die, minimum 0 per die."""
    available = int(actor.resources.get("hit_dice", actor.level))
    spend = max(0, min(hit_dice_spent, available))
    healed = 0
    rolls = []
    for _ in range(spend):
        r = roller.roll(f"1d{hit_die}", purpose="hit die")
        rolls.append(r)
        healed += max(0, r.total + actor.modifier("CON"))
    actor.resources["hit_dice"] = available - spend
    result = apply_healing(actor, healed)
    result.update({"hit_dice_spent": spend, "rolls": [r.to_dict() for r in rolls]})
    return result


def long_rest(actor: Combatant, slot_table: dict[str, int] | None = None) -> dict:
    """Full HP, half hit dice back (min 1), slots restored to the given table."""
    actor.hp = actor.max_hp
    actor.temp_hp = 0
    actor.death_save_successes = 0
    actor.death_save_failures = 0
    actor.conditions = [
        c for c in actor.conditions if c.lower() not in {"unconscious", "exhaustion_1"}
    ]
    regained = max(1, actor.level // 2)
    actor.resources["hit_dice"] = min(actor.level, int(actor.resources.get("hit_dice", 0)) + regained)
    if slot_table is not None:
        actor.resources["spell_slots"] = dict(slot_table)
    return {"hp": actor.hp, "hit_dice": actor.resources["hit_dice"], "regained_hit_dice": regained}
