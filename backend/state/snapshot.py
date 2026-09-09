"""
The bridge between the database and the rules engine.

``load_game_state`` reads rows into plain dataclasses; ``commit_resolution``
writes a resolution's deltas and events back through the event log. The engine
never sees a Session, and the DB never sees a dice roll that wasn't logged.
"""

from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..engine.character import Combatant
from ..engine.combat import CombatState
from ..engine.dice import DiceRoller
from ..engine.resolve import GameState, Resolution
from .events import Delta, DeltaRejected, EventType, record_event
from .models import Campaign, CharacterRow, InventoryRow, NPCRow

#: Where the last combat state was parked. Combat lives in the event log rather
#: than a table, so a rewind restores it for free.
COMBAT_EVENT = "combat_state"


def _inventory_for(session: Session, character_id: str) -> list[str]:
    return [
        row.item_id
        for row in session.scalars(
            select(InventoryRow).where(InventoryRow.character_id == character_id)
        )
    ]


def ensure_combat_stats(
    session: Session,
    campaign_id: str,
    location_id: str | None,
    *,
    npc_kinds: dict[str, str] | None = None,
    source: str = "engine",
    turn_no: int = 0,
) -> None:
    """Anyone present should be a valid target, not just the party — a module
    authors Klarg's personality and never his AC, and an ad hoc NPC has no stats
    at all until now. First contact backs it with a real, persisted combatant
    (same table PCs use, so every later turn's HP is the same row), written as
    an event like everything else the world remembers.

    Idempotent: only NPCs at this location without one yet are touched, so a
    return trip to a cleared room does nothing.
    """
    if not location_id:
        return

    from ..engine.monsters import stat_block_for

    candidates = session.scalars(
        select(NPCRow).where(
            NPCRow.campaign_id == campaign_id,
            NPCRow.location_id == location_id,
            NPCRow.status.in_(("alive", "captured")),
            NPCRow.character_id.is_(None),
        )
    )
    for npc in candidates:
        kind = (
            (npc.resources or {}).get("kind")
            or (npc_kinds or {}).get(npc.template_id or "")
            or npc.name
        )
        block = stat_block_for(kind)
        char_id = f"npc_{npc.id}"
        record_event(
            session, campaign_id, EventType.HOSTILE_INTRODUCED,
            {"npc_id": npc.id, "name": npc.name, "kind": kind},
            deltas=[
                Delta(
                    "character", char_id, "create", "",
                    {
                        "name": npc.name, "is_pc": False, "level": block["level"],
                        "hp": block["hp"], "max_hp": block["max_hp"], "temp_hp": 0,
                        "ac": block["ac"], "speed": 30, "proficiency_bonus": 2,
                        "stats": block["stats"], "conditions": [],
                        "resources": {"weapons": block["weapons"]},
                        "proficiencies": {}, "location_id": location_id,
                    },
                ),
                Delta("npc", npc.id, "set", "character_id", char_id),
            ],
            source=source, turn_no=turn_no,
        )


def load_combat_state(session: Session, campaign_id: str) -> CombatState:
    from .models import EventRow

    row = session.scalars(
        select(EventRow)
        .where(EventRow.campaign_id == campaign_id, EventRow.type == COMBAT_EVENT)
        .order_by(EventRow.id.desc())
        .limit(1)
    ).first()
    return CombatState.from_dict(row.payload.get("combat", {})) if row else CombatState()


def load_game_state(
    session: Session,
    campaign_id: str,
    *,
    catalog: dict[str, dict[str, Any]] | None = None,
    only: Iterable[str] | None = None,
) -> GameState:
    """Snapshot the campaign for one turn.

    ``only`` restricts the loaded actors — the turn loop passes the party plus
    whoever is present in the scene, so a 200-NPC campaign doesn't get read whole.
    """
    campaign = session.get(Campaign, campaign_id)
    if campaign is None:
        raise DeltaRejected(f"campaign {campaign_id!r} does not exist")

    stmt = select(CharacterRow).where(CharacterRow.campaign_id == campaign_id)
    if only is not None:
        wanted = list(only)
        stmt = stmt.where(CharacterRow.id.in_(wanted))

    actors: dict[str, Combatant] = {}
    for row in session.scalars(stmt):
        actors[row.id] = Combatant.from_row(row, _inventory_for(session, row.id))

    # An NPC materialized into a real combatant is still targeted by its own
    # (roster-visible) id everywhere upstream — the Intent agent and the
    # player never learn the backing character row's id. Alias it so
    # ``state.actor("goblin_1")`` finds the same Combatant either way.
    for npc in session.scalars(
        select(NPCRow).where(
            NPCRow.campaign_id == campaign_id, NPCRow.character_id.is_not(None)
        )
    ):
        combatant = actors.get(npc.character_id)
        if combatant is not None:
            actors[npc.id] = combatant

    roller = DiceRoller(seed=campaign.rng_seed)
    roller.start_turn(campaign.turn_no)

    return GameState(
        campaign_id=campaign_id,
        turn_no=campaign.turn_no,
        roller=roller,
        actors=actors,
        combat=load_combat_state(session, campaign_id),
        catalog=catalog or {},
        day=campaign.day,
        hour=campaign.hour,
    )


def commit_resolution(
    session: Session,
    state: GameState,
    resolution: Resolution,
    *,
    source: str = "engine",
) -> list[int]:
    """Persist a resolution: one event per rolled die, then the deltas.

    Rolls are logged even when nothing changed, so a session can be replayed
    exactly. Returns the ids of the events written.
    """
    written: list[int] = []

    for roll in resolution.rolls:
        event = record_event(
            session,
            state.campaign_id,
            EventType.ROLL,
            {"roll": roll.to_dict()},
            source=source,
            turn_no=state.turn_no,
        )
        written.append(event.id)

    resolution_event = record_event(
        session,
        state.campaign_id,
        EventType.RESOLUTION,
        {
            "kind": resolution.kind,
            "dc": resolution.dc,
            "success": resolution.success,
            "degree": resolution.degree,
            "facts": resolution.facts,
            "invalid_reason": resolution.invalid_reason,
        },
        deltas=resolution.state_deltas,
        source=source,
        turn_no=state.turn_no,
    )
    written.append(resolution_event.id)

    for event_type, payload in resolution.events:
        if event_type == EventType.ROLL:
            continue  # already written above, with the full roll record
        event = record_event(
            session, state.campaign_id, event_type, payload,
            source=source, turn_no=state.turn_no,
        )
        written.append(event.id)

    if state.combat.active or state.combat.ended_reason:
        event = record_event(
            session, state.campaign_id, COMBAT_EVENT,
            {"combat": state.combat.to_dict()}, source=source, turn_no=state.turn_no,
        )
        written.append(event.id)

    return written


def apply_proposed_deltas(
    session: Session,
    campaign_id: str,
    raw_deltas: list[dict[str, Any]],
    *,
    source: str,
    turn_no: int,
) -> tuple[list[Delta], list[str]]:
    """Apply deltas proposed by an LLM agent, dropping the ones that don't pass.

    Returns ``(applied, rejections)``. Rejections are kept and logged rather than
    raised: one hallucinated delta should cost the Scribe that delta, not the turn.
    """
    applied: list[Delta] = []
    rejections: list[str] = []
    for raw in raw_deltas:
        try:
            delta = Delta.from_dict(raw)
        except (KeyError, TypeError) as exc:
            rejections.append(f"malformed delta {raw!r}: {exc}")
            continue
        try:
            record_event(
                session, campaign_id, EventType.RESOLUTION,
                {"kind": "proposed", "by": source},
                deltas=[delta], source=source, turn_no=turn_no,
            )
            applied.append(delta)
        except DeltaRejected as exc:
            rejections.append(str(exc))

    if rejections:
        record_event(
            session, campaign_id, EventType.AUDIT_VIOLATION,
            {"stage": "delta_validation", "by": source, "rejections": rejections},
            source="engine", turn_no=turn_no,
        )
    return applied, rejections
