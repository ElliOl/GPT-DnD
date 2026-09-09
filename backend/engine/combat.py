"""
Combat: initiative order, turn advancement, death saves.

``CombatState`` is serializable to and from JSON so it round-trips through the
event log. Reconstructing combat mid-encounter after a rewind is just
``CombatState.from_dict`` on the last logged state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .character import Combatant
from .dice import DiceRoller
from .rules_5e import apply_healing


@dataclass
class Initiative:
    combatant_id: str
    name: str
    score: int
    dex: int
    is_pc: bool


@dataclass
class CombatState:
    active: bool = False
    round: int = 0
    order: list[Initiative] = field(default_factory=list)
    turn_index: int = 0
    ended_reason: str = ""

    @property
    def current(self) -> Initiative | None:
        if not self.active or not self.order:
            return None
        return self.order[self.turn_index % len(self.order)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "round": self.round,
            "turn_index": self.turn_index,
            "ended_reason": self.ended_reason,
            "order": [vars(i) for i in self.order],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CombatState":
        return cls(
            active=d.get("active", False),
            round=d.get("round", 0),
            turn_index=d.get("turn_index", 0),
            ended_reason=d.get("ended_reason", ""),
            order=[Initiative(**i) for i in d.get("order", [])],
        )


def roll_initiative(combatants: list[Combatant], roller: DiceRoller) -> CombatState:
    """Ties break on DEX, then on PCs first — deterministic, so replay agrees."""
    entries: list[Initiative] = []
    for c in combatants:
        roll = roller.d20(c.modifier("DEX"), purpose=f"initiative: {c.name}")
        entries.append(
            Initiative(
                combatant_id=c.id,
                name=c.name,
                score=roll.total,
                dex=c.stats.get("DEX", 10),
                is_pc=c.is_pc,
            )
        )
    entries.sort(key=lambda e: (e.score, e.dex, e.is_pc), reverse=True)
    return CombatState(active=True, round=1, order=entries, turn_index=0)


def advance_turn(state: CombatState) -> CombatState:
    """Step to the next combatant, incrementing the round when the order wraps."""
    if not state.active or not state.order:
        return state
    state.turn_index += 1
    if state.turn_index >= len(state.order):
        state.turn_index = 0
        state.round += 1
    return state


def remove_combatant(state: CombatState, combatant_id: str) -> CombatState:
    """Drop someone from the order without skipping whoever was next."""
    if not state.order:
        return state
    current_id = state.current.combatant_id if state.current else None
    state.order = [e for e in state.order if e.combatant_id != combatant_id]
    if not state.order:
        return end_combat(state, "no combatants remain")
    if current_id == combatant_id:
        state.turn_index %= len(state.order)
    else:
        state.turn_index = next(
            (i for i, e in enumerate(state.order) if e.combatant_id == current_id),
            state.turn_index % len(state.order),
        )
    return state


def end_combat(state: CombatState, reason: str = "") -> CombatState:
    state.active = False
    state.ended_reason = reason
    return state


def check_combat_end(state: CombatState, combatants: dict[str, Combatant]) -> CombatState:
    """Combat ends when one side can no longer act.

    A foe is a hostile combatant, not merely a non-PC — an ally standing in
    the room is neither side's problem, and counting them as an enemy keeps a
    finished fight running forever with nothing left to fight.

    Only combatants actually in the initiative order count: someone who never
    joined the fight can't be the reason it hasn't ended.
    """
    if not state.active:
        return state
    in_fight = {e.combatant_id for e in state.order}
    engaged = [c for c in combatants.values() if not in_fight or c.id in in_fight]
    live_pcs = [c for c in engaged if c.is_pc and c.can_act]
    live_foes = [c for c in engaged if not c.is_pc and c.hostile and c.can_act]
    if not live_foes:
        return end_combat(state, "all enemies down")
    if not live_pcs:
        return end_combat(state, "party down")
    return state


@dataclass
class DeathSaveOutcome:
    combatant_id: str
    result: str  # success | failure | stabilized | dead | revived
    successes: int
    failures: int
    natural: int


def death_save(target: Combatant, roller: DiceRoller) -> DeathSaveOutcome:
    """5e RAW: three successes stabilize, three failures kill, nat 20 revives at 1 HP,
    nat 1 counts as two failures."""
    roll = roller.d20(purpose=f"death save: {target.name}")
    nat = roll.natural

    if nat == 20:
        apply_healing(target, 1)
        return DeathSaveOutcome(target.id, "revived", 0, 0, nat)

    if nat == 1:
        target.death_save_failures += 2
    elif roll.total >= 10:
        target.death_save_successes += 1
    else:
        target.death_save_failures += 1

    if target.death_save_failures >= 3:
        if "dead" not in [c.lower() for c in target.conditions]:
            target.conditions.append("dead")
        return DeathSaveOutcome(target.id, "dead", target.death_save_successes, target.death_save_failures, nat)

    if target.death_save_successes >= 3:
        if "stable" not in [c.lower() for c in target.conditions]:
            target.conditions.append("stable")
        return DeathSaveOutcome(target.id, "stabilized", target.death_save_successes, target.death_save_failures, nat)

    result = "success" if (nat != 1 and roll.total >= 10) else "failure"
    return DeathSaveOutcome(
        target.id, result, target.death_save_successes, target.death_save_failures, nat
    )
