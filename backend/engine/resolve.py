"""
The single entry point into the rules: ``resolve(intent, state) -> Resolution``.

The Narrator receives ``Resolution.facts`` — mechanically true statements — and
*describes* them. It cannot alter a number, because by the time it is called the
dice have already been rolled and the deltas already computed.

When the rules don't cover what the player tried, ``kind="narrative"`` and the
Narrator is free. When the player tried something they cannot do, ``kind="invalid"``
and ``invalid_reason`` says why in words a DM would use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..state.events import Delta, EventType
from . import combat as combat_rules
from . import rules_5e as rules
from .character import Combatant
from .dice import DiceRoller, Roll
from .intent import Intent

DEFAULT_DC = 12


@dataclass
class GameState:
    """The engine's snapshot of the world for one turn.

    Loaded from the database by ``state.snapshot``, mutated in place by the rules,
    and written back as deltas. Nothing here talks to the DB itself.
    """

    campaign_id: str
    turn_no: int
    roller: DiceRoller
    actors: dict[str, Combatant] = field(default_factory=dict)
    combat: combat_rules.CombatState = field(default_factory=combat_rules.CombatState)
    location_id: str | None = None
    day: int = 1
    hour: int = 8
    #: Weapon/spell stat blocks available this turn, keyed by lowercase name.
    catalog: dict[str, dict[str, Any]] = field(default_factory=dict)

    def actor(self, actor_id: str) -> Combatant | None:
        if actor_id in self.actors:
            return self.actors[actor_id]
        wanted = actor_id.strip().lower()
        for c in self.actors.values():
            if c.name.lower() == wanted or c.id.lower() == wanted:
                return c
        return None


@dataclass
class Resolution:
    kind: str  # check | attack | save | combat | rest | narrative | invalid
    rolls: list[Roll] = field(default_factory=list)
    dc: int | None = None
    success: bool | None = None
    degree: str | None = None
    state_deltas: list[Delta] = field(default_factory=list)
    #: Mechanically true statements, in plain English, for the Narrator to dress.
    facts: list[str] = field(default_factory=list)
    invalid_reason: str | None = None
    #: Events the turn loop should append, as ``(type, payload)`` pairs.
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "rolls": [r.to_dict() for r in self.rolls],
            "dc": self.dc,
            "success": self.success,
            "degree": self.degree,
            "state_deltas": [d.to_dict() for d in self.state_deltas],
            "facts": self.facts,
            "invalid_reason": self.invalid_reason,
        }


def _hp_deltas(actor: Combatant) -> list[Delta]:
    """Deltas that mirror in-place mutations the rules made to a snapshot."""
    return [
        Delta("character", actor.id, "set", "hp", actor.hp),
        Delta("character", actor.id, "set", "temp_hp", actor.temp_hp),
        Delta("character", actor.id, "set", "conditions", list(actor.conditions)),
    ]


def _invalid(reason: str) -> Resolution:
    return Resolution(kind="invalid", invalid_reason=reason, facts=[reason])


# --------------------------------------------------------------------------
# Combat: the engine primitives (roll_initiative, advance_turn) existed but
# nothing ever called them — an attack landed, nothing else ever happened.
# This is the wiring, kept small on purpose: who acts and in what order is
# real 5e; what a monster *does* on its turn is a one-line tactic ("hit the
# weakest PC"), because actual NPC decision-making is a later phase's job.
# --------------------------------------------------------------------------

def _combatants_here(state: GameState, location_id: str | None) -> list[Combatant]:
    """Everyone able to fight at this location — the party wherever it stands,
    plus anything hostile that's been introduced there. A materialized NPC's
    location is set at creation, so this covers named and ad hoc monsters
    alike without needing to know which is which.

    An ally present in the same room (Sildar) is not swept into the fight just
    for standing there — only PCs and combatants flagged hostile join
    automatically. Someone the player deliberately targets still joins
    regardless, via the explicit actor/target passed to
    ``_ensure_combat_started``.
    """
    candidates = state.actors.values() if location_id is None else (
        c for c in state.actors.values() if c.location_id == location_id
    )
    return [c for c in candidates if c.can_act and (c.is_pc or c.hostile)]


def _ensure_combat_started(state: GameState, actor: Combatant, target: Combatant) -> None:
    if state.combat.active:
        return
    location_id = actor.location_id or target.location_id
    participants = {c.id: c for c in _combatants_here(state, location_id)}
    participants[actor.id] = actor
    participants[target.id] = target
    state.combat = combat_rules.roll_initiative(list(participants.values()), state.roller)


def _run_npc_turns(state: GameState) -> tuple[list[str], list[Delta], list[Roll], list[tuple[str, dict]]]:
    """Resolve every consecutive NPC turn until it's a PC's turn again or the
    fight ends. One player message drives one PC's action — the monsters
    don't wait for a second message to swing back.

    Target choice is deterministic (lowest current HP) rather than random, so
    a rewind reproduces the same fight rather than a different one.
    """
    facts: list[str] = []
    deltas: list[Delta] = []
    rolls: list[Roll] = []
    events: list[tuple[str, dict[str, Any]]] = []

    guard = 0
    while (
        state.combat.active and state.combat.current
        and not state.combat.current.is_pc and guard < 12
    ):
        guard += 1
        npc = state.actors.get(state.combat.current.combatant_id)
        if npc is None or not npc.can_act:
            state.combat = combat_rules.advance_turn(state.combat)
            continue

        alive_pcs = [c for c in state.actors.values() if c.is_pc and c.can_act]
        if not alive_pcs:
            state.combat = combat_rules.end_combat(state.combat, "party down")
            break
        target = min(alive_pcs, key=lambda c: c.hp)

        weapon = (npc.resources.get("weapons") or [{}])[0]
        outcome = rules.attack(
            npc, target, state.roller,
            damage_dice=weapon.get("damage_dice", "1d6"),
            damage_type=weapon.get("damage_type", "bludgeoning"),
            weapon=weapon.get("name", "attack"),
        )
        rolls.append(outcome.attack_roll)
        events.append(
            (EventType.ROLL, {"actor": npc.id, "roll": outcome.attack_roll.to_dict(), "dc": target.ac})
        )
        if outcome.hit:
            rolls.append(outcome.damage_roll)
            damage = rules.apply_damage(target, outcome.damage, outcome.damage_type)
            deltas.extend(_hp_deltas(target))
            events.append(
                (EventType.DAMAGE, {
                    "actor": npc.id, "target": target.id, "amount": damage["amount"],
                    "damage_type": outcome.damage_type, "critical": outcome.critical,
                    "hp_after": target.hp,
                })
            )
            hit_word = "critically hits" if outcome.critical else "hits"
            facts.append(
                f"{npc.name} {hit_word} {target.name} for {damage['amount']} "
                f"{outcome.damage_type} damage. {target.name} is at {target.hp}/{target.max_hp} HP."
            )
            if damage["dropped"]:
                facts.append(f"{target.name} dropped to 0 HP and is unconscious.")
        else:
            facts.append(
                f"{npc.name} attacks {target.name} and misses "
                f"(rolled {outcome.attack_roll.total} against AC {target.ac})."
            )

        state.combat = combat_rules.advance_turn(state.combat)
        state.combat = combat_rules.check_combat_end(state.combat, state.actors)

    if state.combat.ended_reason:
        facts.append(f"Combat ends: {state.combat.ended_reason}.")

    return facts, deltas, rolls, events


# --------------------------------------------------------------------------
# Verb handlers
# --------------------------------------------------------------------------

def _resolve_check(intent: Intent, state: GameState) -> Resolution:
    actor = state.actor(intent.actor_id)
    if actor is None:
        return _invalid(f"No such character: {intent.actor_id!r}.")
    if not actor.can_act:
        return _invalid(f"{actor.name} cannot act right now.")

    what = intent.skill or intent.ability or "STR"
    dc = intent.dc or DEFAULT_DC
    outcome = rules.ability_check(
        actor, what, dc, state.roller,
        advantage=intent.advantage, disadvantage=intent.disadvantage,
    )
    fact = (
        f"{actor.name} rolled {outcome.roll.total} on a {outcome.detail} check "
        f"against DC {dc} — {outcome.degree.replace('_', ' ')}."
    )
    return Resolution(
        kind="check",
        rolls=[outcome.roll],
        dc=dc,
        success=outcome.success,
        degree=outcome.degree,
        facts=[fact],
        events=[(EventType.ROLL, {"actor": actor.id, "roll": outcome.roll.to_dict(), "dc": dc})],
    )


def _resolve_save(intent: Intent, state: GameState) -> Resolution:
    actor = state.actor(intent.actor_id)
    if actor is None:
        return _invalid(f"No such character: {intent.actor_id!r}.")
    ability = (intent.ability or "DEX").upper()
    dc = intent.dc or DEFAULT_DC
    outcome = rules.saving_throw(
        actor, ability, dc, state.roller,
        advantage=intent.advantage, disadvantage=intent.disadvantage,
    )
    fact = (
        f"{actor.name} rolled {outcome.roll.total} on a {ability} saving throw "
        f"against DC {dc} — {'success' if outcome.success else 'failure'}."
    )
    return Resolution(
        kind="save",
        rolls=[outcome.roll],
        dc=dc,
        success=outcome.success,
        degree=outcome.degree,
        facts=[fact],
        events=[(EventType.ROLL, {"actor": actor.id, "roll": outcome.roll.to_dict(), "dc": dc})],
    )


def _resolve_attack(intent: Intent, state: GameState) -> Resolution:
    actor = state.actor(intent.actor_id)
    if actor is None:
        return _invalid(f"No such character: {intent.actor_id!r}.")
    if not actor.can_act:
        return _invalid(f"{actor.name} cannot act right now.")
    if not intent.targets:
        return _invalid("No target given for the attack.")

    target = state.actor(intent.targets[0])
    if target is None:
        return _invalid(f"There is no {intent.targets[0]!r} here to attack.")
    if target.is_down:
        return _invalid(f"{target.name} is already down.")

    _ensure_combat_started(state, actor, target)
    if state.combat.active:
        # Whoever the player named acts now, regardless of where initiative
        # put them — this loop doesn't gate PC actions on turn order, only
        # uses it to decide who swings back next.
        actor_index = next(
            (i for i, e in enumerate(state.combat.order) if e.combatant_id == actor.id), None
        )
        if actor_index is not None:
            state.combat.turn_index = actor_index

    weapon_name = intent.item or ""
    spec = state.catalog.get(weapon_name.lower(), {}) if weapon_name else {}
    outcome = rules.attack(
        actor, target, state.roller,
        damage_dice=spec.get("damage", "1d6"),
        damage_type=spec.get("damage_type", "bludgeoning"),
        weapon=weapon_name or spec.get("name", ""),
        advantage=intent.advantage,
        disadvantage=intent.disadvantage,
        finesse=bool(spec.get("finesse")),
        ranged=bool(spec.get("ranged")),
    )

    rolls = [outcome.attack_roll]
    facts = []
    deltas: list[Delta] = []
    events: list[tuple[str, dict[str, Any]]] = [
        (EventType.ROLL, {"actor": actor.id, "roll": outcome.attack_roll.to_dict(), "dc": target.ac})
    ]

    if not outcome.hit:
        facts.append(
            f"{actor.name} attacked {target.name} and missed "
            f"(rolled {outcome.attack_roll.total} against AC {target.ac})."
        )
        resolution = Resolution(
            kind="attack", rolls=rolls, dc=target.ac, success=False,
            degree="crit_fail" if outcome.attack_roll.natural == 1 else "fail",
            facts=facts, events=events,
        )
    else:
        rolls.append(outcome.damage_roll)
        damage = rules.apply_damage(target, outcome.damage, outcome.damage_type)
        deltas.extend(_hp_deltas(target))
        events.append(
            (EventType.DAMAGE, {
                "actor": actor.id, "target": target.id,
                "amount": damage["amount"], "damage_type": outcome.damage_type,
                "critical": outcome.critical, "hp_after": target.hp,
            })
        )

        hit_word = "critically hit" if outcome.critical else "hit"
        facts.append(
            f"{actor.name} {hit_word} {target.name} for {damage['amount']} "
            f"{outcome.damage_type} damage. {target.name} is at {target.hp}/{target.max_hp} HP."
        )
        if damage["dropped"]:
            facts.append(f"{target.name} dropped to 0 HP and is unconscious.")

        resolution = Resolution(
            kind="attack", rolls=rolls, dc=target.ac, success=True,
            degree="crit_success" if outcome.critical else "success",
            state_deltas=deltas, facts=facts, events=events,
        )

    if state.combat.active:
        state.combat = combat_rules.advance_turn(state.combat)
        state.combat = combat_rules.check_combat_end(state.combat, state.actors)
        npc_facts, npc_deltas, npc_rolls, npc_events = _run_npc_turns(state)
        resolution.facts.extend(npc_facts)
        resolution.state_deltas.extend(npc_deltas)
        resolution.rolls.extend(npc_rolls)
        resolution.events.extend(npc_events)

    return resolution


def _resolve_cast(intent: Intent, state: GameState) -> Resolution:
    actor = state.actor(intent.actor_id)
    if actor is None:
        return _invalid(f"No such character: {intent.actor_id!r}.")
    if not actor.can_act:
        return _invalid(f"{actor.name} cannot act right now.")

    level = intent.spell_level if intent.spell_level is not None else 1
    spell = intent.spell or "a spell"
    if level > 0 and not rules.spend_spell_slot(actor, level):
        return _invalid(
            f"{actor.name} has no level {level} spell slots remaining and cannot cast {spell}."
        )

    deltas = [Delta("character", actor.id, "set", "resources", dict(actor.resources))]
    facts = [
        f"{actor.name} cast {spell}"
        + (f" using a level {level} slot." if level > 0 else " (a cantrip).")
    ]
    events: list[tuple[str, dict[str, Any]]] = [
        (EventType.RESOURCE_SPENT, {"actor": actor.id, "resource": "spell_slot", "level": level, "spell": spell})
    ]

    # The spell's own effect needs a stat block. Without one, hand the shape of
    # the cast to the Narrator rather than inventing damage.
    spec = state.catalog.get(spell.lower(), {})
    rolls: list[Roll] = []
    if spec.get("save_ability") and intent.targets:
        dc = rules.spell_save_dc(actor, spec.get("cast_ability", "INT"))
        for target_ref in intent.targets:
            target = state.actor(target_ref)
            if target is None:
                continue
            save = rules.saving_throw(target, spec["save_ability"], dc, state.roller)
            rolls.append(save.roll)
            dmg_roll = state.roller.roll(spec.get("damage", "1d6"), purpose=f"{spell} damage")
            rolls.append(dmg_roll)
            amount = dmg_roll.total // 2 if save.success else dmg_roll.total
            applied = rules.apply_damage(target, amount, spec.get("damage_type", "force"))
            deltas.extend(_hp_deltas(target))
            facts.append(
                f"{target.name} {'saved' if save.success else 'failed the save'} "
                f"(DC {dc}) and took {applied['amount']} damage — now "
                f"{target.hp}/{target.max_hp} HP."
            )
            events.append(
                (EventType.DAMAGE, {
                    "actor": actor.id, "target": target.id,
                    "amount": applied["amount"], "spell": spell, "hp_after": target.hp,
                })
            )
    elif spec.get("heal") and intent.targets:
        for target_ref in intent.targets:
            target = state.actor(target_ref)
            if target is None:
                continue
            heal_roll = state.roller.roll(spec["heal"], purpose=f"{spell} healing")
            rolls.append(heal_roll)
            healed = rules.apply_healing(target, heal_roll.total)
            deltas.extend(_hp_deltas(target))
            deltas.append(Delta("character", target.id, "set", "death_save_successes", target.death_save_successes))
            deltas.append(Delta("character", target.id, "set", "death_save_failures", target.death_save_failures))
            facts.append(
                f"{target.name} healed {healed['amount']} HP — now {target.hp}/{target.max_hp}."
            )
            events.append((EventType.HEAL, {"target": target.id, "amount": healed["amount"]}))

    return Resolution(
        kind="check" if rolls else "narrative",
        rolls=rolls, success=True, state_deltas=deltas, facts=facts, events=events,
    )


def _resolve_use_item(intent: Intent, state: GameState) -> Resolution:
    actor = state.actor(intent.actor_id)
    if actor is None:
        return _invalid(f"No such character: {intent.actor_id!r}.")
    item = intent.item or ""
    if not item:
        return _invalid("No item named.")
    if not actor.has_item(item):
        return _invalid(f"{actor.name} does not have {item}.")

    spec = state.catalog.get(item.lower(), {})
    rolls: list[Roll] = []
    deltas: list[Delta] = []
    facts = [f"{actor.name} used {item}."]
    events: list[tuple[str, dict[str, Any]]] = []

    if spec.get("heal"):
        target = state.actor(intent.targets[0]) if intent.targets else actor
        target = target or actor
        heal_roll = state.roller.roll(spec["heal"], purpose=f"{item} healing")
        rolls.append(heal_roll)
        healed = rules.apply_healing(target, heal_roll.total)
        deltas.extend(_hp_deltas(target))
        facts.append(f"{target.name} regained {healed['amount']} HP — now {target.hp}/{target.max_hp}.")
        events.append((EventType.HEAL, {"target": target.id, "amount": healed["amount"]}))

    if spec.get("consumable", True):
        events.append((EventType.ITEM_LOST, {"character_id": actor.id, "item_id": item, "qty": 1}))

    return Resolution(
        kind="check" if rolls else "narrative",
        rolls=rolls, success=True, state_deltas=deltas, facts=facts, events=events,
    )


def _resolve_rest(intent: Intent, state: GameState) -> Resolution:
    actor = state.actor(intent.actor_id)
    if actor is None:
        return _invalid(f"No such character: {intent.actor_id!r}.")
    if state.combat.active:
        return _invalid("You cannot rest while combat is under way.")

    deltas: list[Delta] = []
    facts: list[str] = []
    rolls: list[Roll] = []
    hours_spent = 8 if (intent.rest_type or "short") == "long" else 1
    if (intent.rest_type or "short") == "long":
        for c in state.actors.values():
            if not c.is_pc:
                continue
            slot_table = c.resources.get("max_spell_slots")
            rules.long_rest(c, slot_table=slot_table)
            deltas.extend(_hp_deltas(c))
            deltas.append(Delta("character", c.id, "set", "resources", dict(c.resources)))
            facts.append(f"{c.name} finished a long rest at {c.hp}/{c.max_hp} HP.")
    else:
        result = rules.short_rest(actor, 1, state.roller)
        rolls.extend(state.roller.log[-1:])
        deltas.extend(_hp_deltas(actor))
        deltas.append(Delta("character", actor.id, "set", "resources", dict(actor.resources)))
        facts.append(
            f"{actor.name} took a short rest, spent one hit die and regained "
            f"{result['amount']} HP — now {actor.hp}/{actor.max_hp}."
        )

    total_hours = state.hour + hours_spent
    new_day = state.day + total_hours // 24
    new_hour = total_hours % 24
    deltas.append(Delta("campaign", state.campaign_id, "set", "day", new_day))
    deltas.append(Delta("campaign", state.campaign_id, "set", "hour", new_hour))
    facts.append(f"Time passed: now day {new_day}, {new_hour:02d}:00.")

    return Resolution(
        kind="rest", rolls=rolls, success=True, state_deltas=deltas, facts=facts,
        events=[(EventType.REST, {"type": intent.rest_type or "short", "actor": actor.id})],
    )


def _resolve_death_save(intent: Intent, state: GameState) -> Resolution:
    actor = state.actor(intent.actor_id)
    if actor is None:
        return _invalid(f"No such character: {intent.actor_id!r}.")
    if not actor.is_down:
        return _invalid(f"{actor.name} is not dying.")

    outcome = combat_rules.death_save(actor, state.roller)
    deltas = _hp_deltas(actor) + [
        Delta("character", actor.id, "set", "death_save_successes", actor.death_save_successes),
        Delta("character", actor.id, "set", "death_save_failures", actor.death_save_failures),
    ]
    fact = {
        "revived": f"{actor.name} rolled a natural 20 on a death save and is conscious at 1 HP.",
        "dead": f"{actor.name} failed a third death save and has died.",
        "stabilized": f"{actor.name} succeeded on a third death save and is stable.",
    }.get(
        outcome.result,
        f"{actor.name} {outcome.result}ed a death save "
        f"({outcome.successes} successes, {outcome.failures} failures).",
    )
    return Resolution(
        kind="save",
        rolls=state.roller.log[-1:],
        success=outcome.result in ("success", "stabilized", "revived"),
        state_deltas=deltas,
        facts=[fact],
        events=[(EventType.ROLL, {"actor": actor.id, "death_save": outcome.result})],
    )


def _resolve_move(intent: Intent, state: GameState) -> Resolution:
    actor = state.actor(intent.actor_id)
    if actor is None:
        return _invalid(f"No such character: {intent.actor_id!r}.")
    destination = intent.targets[0] if intent.targets else None
    if not destination:
        return _invalid("No destination given.")
    return Resolution(
        kind="narrative",
        success=True,
        state_deltas=[Delta("character", actor.id, "set", "location_id", destination)],
        facts=[f"{actor.name} moved to {destination}."],
        events=[(EventType.MOVED, {"actor": actor.id, "to": destination})],
    )


_HANDLERS = {
    "check": _resolve_check,
    "save": _resolve_save,
    "attack": _resolve_attack,
    "cast": _resolve_cast,
    "use_item": _resolve_use_item,
    "rest": _resolve_rest,
    "death_save": _resolve_death_save,
    "move": _resolve_move,
}


def resolve(intent: Intent, state: GameState) -> Resolution:
    """Turn an intent into mechanical truth. The one door into the rules."""
    if intent.ambiguous:
        return Resolution(
            kind="narrative",
            facts=[],
            invalid_reason=intent.clarification or "The intent was ambiguous.",
        )
    handler = _HANDLERS.get(intent.verb)
    if handler is None:
        # Talk, look, wait, unknown — nothing to roll. The Narrator takes it.
        return Resolution(kind="narrative", facts=[])
    return handler(intent, state)
