"""
Event log, typed deltas, and reducers.

The contract:

* Nothing mutates mechanical state except :func:`apply_delta`, and it is only
  reachable through :func:`record_event`.
* Every event is appended before its deltas are applied, so the log is a complete
  description of how the world got here.
* Because of that, ``replay_to(turn_n)`` rebuilds the world exactly — which is
  how rewind works. It is a replay, not an undo, and it only works if nobody
  writes behind the log's back.

Deltas proposed by an LLM (the Scribe) go through the same validator as deltas
produced by the rules engine. High-risk fields (hp, gold, xp, item grants) are
refused unless an engine-authored event authorizes them. Scribe proposes; code
disposes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import (
    Campaign,
    CanonFactRow,
    CharacterRow,
    ClockRow,
    EventRow,
    InventoryRow,
    LocationRow,
    NPCRow,
    QuestRow,
)


# --------------------------------------------------------------------------
# Event vocabulary
# --------------------------------------------------------------------------

class EventType:
    """Closed vocabulary. Adding a type means adding a reducer or a visibility rule."""

    CAMPAIGN_SEEDED = "campaign_seeded"
    TURN_STARTED = "turn_started"
    ROLL = "roll"
    RESOLUTION = "resolution"
    DAMAGE = "damage"
    HEAL = "heal"
    CONDITION_APPLIED = "condition_applied"
    CONDITION_REMOVED = "condition_removed"
    RESOURCE_SPENT = "resource_spent"
    ITEM_GAINED = "item_gained"
    ITEM_LOST = "item_lost"
    MOVED = "moved"
    NPC_ACTION = "npc_action"
    ATTITUDE_CHANGED = "attitude_changed"
    CLOCK_ADVANCED = "clock_advanced"
    CLOCK_FILLED = "clock_filled"
    QUEST_CHANGED = "quest_changed"
    LOCATION_DISCOVERED = "location_discovered"
    REST = "rest"
    CANON_ESTABLISHED = "canon_established"
    NARRATION = "narration"
    SCENE_SUMMARY = "scene_summary"
    AUDIT_VIOLATION = "audit_violation"


# --------------------------------------------------------------------------
# Deltas
# --------------------------------------------------------------------------

TARGETS = {
    "campaign": Campaign,
    "character": CharacterRow,
    "npc": NPCRow,
    "quest": QuestRow,
    "clock": ClockRow,
    "location": LocationRow,
}

OPS = {"set", "inc", "append", "remove"}

#: Fields a delta may touch, per target. Anything else is rejected outright.
ALLOWED_FIELDS: dict[str, set[str]] = {
    "campaign": {"day", "hour", "session_no", "turn_no"},
    "character": {
        "hp", "temp_hp", "max_hp", "ac", "level", "conditions", "resources",
        "location_id", "death_save_successes", "death_save_failures",
        "proficiency_bonus", "speed", "stats",
    },
    "npc": {
        "status", "location_id", "attitude_to_party", "goals", "knowledge",
        "resources", "schedule", "importance",
    },
    "quest": {"status", "hidden", "details", "title", "location_id", "giver_npc"},
    "clock": {"filled", "size", "hidden", "on_complete", "name"},
    "location": {"discovered", "visited", "state_overrides", "name"},
}

#: Fields an LLM may never move on its own authority. An engine-authored event
#: (or an explicit ``authorized_by`` event id) is required.
GUARDED_FIELDS: dict[str, set[str]] = {
    "character": {"hp", "max_hp", "temp_hp", "level", "resources", "ac", "stats"},
    "npc": {"status"},
    "clock": {"filled", "size"},
}

TRUSTED_SOURCES = {"engine", "admin", "migration", "world_tick"}


class DeltaRejected(ValueError):
    """A proposed delta failed validation and was not applied."""


@dataclass
class Delta:
    """One typed mutation. ``target`` names a table, ``id`` a row, ``field`` a column."""

    target: str
    id: str
    op: str
    field: str
    value: Any = None
    #: Event id that authorizes a guarded field. Engine deltas set this implicitly.
    authorized_by: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "id": self.id,
            "op": self.op,
            "field": self.field,
            "value": self.value,
            "authorized_by": self.authorized_by,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Delta":
        return cls(
            target=d["target"],
            id=str(d["id"]),
            op=d.get("op", "set"),
            field=d["field"],
            value=d.get("value"),
            authorized_by=d.get("authorized_by"),
        )


def validate_delta(d: Delta, source: str) -> None:
    """Raise :class:`DeltaRejected` if this delta may not be applied from ``source``."""
    if d.target not in TARGETS:
        raise DeltaRejected(f"unknown target {d.target!r}")
    if d.op not in OPS:
        raise DeltaRejected(f"unknown op {d.op!r}")
    allowed = ALLOWED_FIELDS.get(d.target, set())
    if d.field not in allowed:
        raise DeltaRejected(f"{d.target}.{d.field} is not a writable field")
    guarded = GUARDED_FIELDS.get(d.target, set())
    if d.field in guarded and source not in TRUSTED_SOURCES and d.authorized_by is None:
        raise DeltaRejected(
            f"{d.target}.{d.field} requires engine authorization "
            f"(source={source!r} proposed it with no authorizing event)"
        )
    if d.op == "inc" and not isinstance(d.value, (int, float)):
        raise DeltaRejected(f"inc on {d.field} needs a number, got {type(d.value).__name__}")


def _load_row(session: Session, target: str, row_id: str):
    model = TARGETS[target]
    row = session.get(model, row_id)
    if row is None:
        raise DeltaRejected(f"{target} {row_id!r} does not exist")
    return row


def apply_delta(session: Session, d: Delta, source: str = "engine") -> None:
    """Validate and apply a single delta. The only writer of mechanical state."""
    validate_delta(d, source)
    row = _load_row(session, d.target, d.id)
    current = getattr(row, d.field)

    if d.op == "set":
        new = d.value
    elif d.op == "inc":
        new = (current or 0) + d.value
    elif d.op == "append":
        items = list(current or [])
        if d.value not in items:
            items.append(d.value)
        new = items
    else:  # remove
        items = list(current or [])
        new = [i for i in items if i != d.value]

    # Clamp the invariants code owns, so no caller can push hp past its bounds.
    if d.target == "character" and d.field == "hp":
        new = max(0, min(int(new), row.max_hp))
    if d.target == "clock" and d.field == "filled":
        new = max(0, min(int(new), row.size))
    if d.target == "npc" and d.field == "attitude_to_party":
        new = max(-5, min(5, int(new)))

    setattr(row, d.field, new)


# --------------------------------------------------------------------------
# Append + reduce
# --------------------------------------------------------------------------

def record_event(
    session: Session,
    campaign_id: str,
    type: str,
    payload: dict[str, Any] | None = None,
    *,
    deltas: Iterable[Delta] | None = None,
    actor: str | None = None,
    source: str = "engine",
    turn_no: int | None = None,
    apply: bool = True,
) -> EventRow:
    """Append an event and apply its deltas.

    The event row is flushed first so guarded deltas can reference its id.
    """
    campaign = session.get(Campaign, campaign_id)
    if campaign is None:
        raise DeltaRejected(f"campaign {campaign_id!r} does not exist")

    delta_list = list(deltas or [])
    base_payload = dict(payload or {})
    row = EventRow(
        campaign_id=campaign_id,
        turn_no=campaign.turn_no if turn_no is None else turn_no,
        type=type,
        actor=actor,
        source=source,
        payload={**base_payload, "deltas": [d.to_dict() for d in delta_list]},
    )
    session.add(row)
    session.flush()

    if apply:
        for d in delta_list:
            if d.authorized_by is None and source in TRUSTED_SOURCES:
                d.authorized_by = row.id
            apply_delta(session, d, source=source)
        # Rewrite the payload now that the deltas carry the id that authorized
        # them, so replay sees the same provenance the live application did.
        row.payload = {**base_payload, "deltas": [d.to_dict() for d in delta_list]}
        _run_reducer(session, row)
        session.flush()
    return row


# Reducers handle the state changes that are structural rather than a field poke —
# rows created, clocks firing, canon written.
Reducer = Callable[[Session, EventRow], None]
_REDUCERS: dict[str, Reducer] = {}


def reducer(event_type: str) -> Callable[[Reducer], Reducer]:
    def deco(fn: Reducer) -> Reducer:
        _REDUCERS[event_type] = fn
        return fn

    return deco


def _run_reducer(session: Session, event: EventRow) -> None:
    fn = _REDUCERS.get(event.type)
    if fn is not None:
        fn(session, event)


@reducer(EventType.CAMPAIGN_SEEDED)
def _reduce_seed(session: Session, event: EventRow) -> None:
    """Materialize the whole opening world from the event payload.

    Seeding through an event (rather than direct inserts) is what makes replay
    total: turn 0 of any campaign is reconstructible from the log alone.
    """
    p = event.payload
    campaign = session.get(Campaign, event.campaign_id)
    for k, v in (p.get("campaign") or {}).items():
        if hasattr(campaign, k) and k != "id":
            setattr(campaign, k, v)

    for row in p.get("characters", []):
        session.merge(CharacterRow(campaign_id=event.campaign_id, **row))
    for row in p.get("npcs", []):
        session.merge(NPCRow(campaign_id=event.campaign_id, **row))
    for row in p.get("locations", []):
        session.merge(LocationRow(campaign_id=event.campaign_id, **row))
    for row in p.get("quests", []):
        session.merge(QuestRow(campaign_id=event.campaign_id, **row))
    for row in p.get("clocks", []):
        session.merge(ClockRow(campaign_id=event.campaign_id, **row))
    for row in p.get("inventory", []):
        session.merge(InventoryRow(**row))
    for fact in p.get("canon_facts", []):
        session.add(
            CanonFactRow(
                campaign_id=event.campaign_id,
                text=fact["text"] if isinstance(fact, dict) else str(fact),
                entities=fact.get("entities", []) if isinstance(fact, dict) else [],
                established_turn=0,
                source="module",
            )
        )
    session.flush()


@reducer(EventType.TURN_STARTED)
def _reduce_turn(session: Session, event: EventRow) -> None:
    campaign = session.get(Campaign, event.campaign_id)
    campaign.turn_no = max(campaign.turn_no, event.turn_no)


@reducer(EventType.ITEM_GAINED)
def _reduce_item_gained(session: Session, event: EventRow) -> None:
    p = event.payload
    char_id, item_id = p.get("character_id"), p.get("item_id")
    if not char_id or not item_id:
        return
    qty = int(p.get("qty", 1))
    existing = session.scalar(
        select(InventoryRow).where(
            InventoryRow.character_id == char_id, InventoryRow.item_id == item_id
        )
    )
    if existing:
        existing.qty += qty
    else:
        session.add(
            InventoryRow(
                character_id=char_id, item_id=item_id, qty=qty, props=p.get("props", {})
            )
        )
    session.flush()


@reducer(EventType.ITEM_LOST)
def _reduce_item_lost(session: Session, event: EventRow) -> None:
    p = event.payload
    existing = session.scalar(
        select(InventoryRow).where(
            InventoryRow.character_id == p.get("character_id"),
            InventoryRow.item_id == p.get("item_id"),
        )
    )
    if existing is None:
        return
    existing.qty -= int(p.get("qty", 1))
    if existing.qty <= 0:
        session.delete(existing)
    session.flush()


@reducer(EventType.CLOCK_ADVANCED)
def _reduce_clock(session: Session, event: EventRow) -> None:
    """A clock that fills emits its own follow-up event, so consequences are logged too."""
    clock = session.get(ClockRow, event.payload.get("clock_id", ""))
    if clock is None or clock.filled < clock.size:
        return
    fired = session.scalars(
        select(EventRow).where(
            EventRow.campaign_id == event.campaign_id,
            EventRow.type == EventType.CLOCK_FILLED,
        )
    )
    if any(e.payload.get("clock_id") == clock.id for e in fired):
        return
    session.add(
        EventRow(
            campaign_id=event.campaign_id,
            turn_no=event.turn_no,
            type=EventType.CLOCK_FILLED,
            source=event.source,
            payload={"clock_id": clock.id, "name": clock.name, "on_complete": clock.on_complete},
        )
    )
    session.flush()


@reducer(EventType.CANON_ESTABLISHED)
def _reduce_canon(session: Session, event: EventRow) -> None:
    for fact in event.payload.get("facts", []):
        text = fact["text"] if isinstance(fact, dict) else str(fact)
        session.add(
            CanonFactRow(
                campaign_id=event.campaign_id,
                text=text,
                entities=fact.get("entities", []) if isinstance(fact, dict) else [],
                established_turn=event.turn_no,
                source=fact.get("source", "play") if isinstance(fact, dict) else "play",
            )
        )
    session.flush()


# --------------------------------------------------------------------------
# Replay / rewind
# --------------------------------------------------------------------------

DERIVED_MODELS = (InventoryRow, CanonFactRow, ClockRow, QuestRow, LocationRow, NPCRow, CharacterRow)


def replay_to(session: Session, campaign_id: str, turn_no: int) -> int:
    """Rebuild campaign state from the log, stopping after ``turn_no``.

    Events after the cut are dropped — the log stays append-only in the sense
    that history is never rewritten, but a rewind genuinely discards the futures
    the party chose to unmake. Returns the number of events replayed.
    """
    events = list(
        session.scalars(
            select(EventRow)
            .where(EventRow.campaign_id == campaign_id, EventRow.turn_no <= turn_no)
            .order_by(EventRow.id)
        )
    )

    # Wipe derived rows; children first so foreign keys stay satisfied.
    char_ids = list(
        session.scalars(select(CharacterRow.id).where(CharacterRow.campaign_id == campaign_id))
    )
    if char_ids:
        session.execute(delete(InventoryRow).where(InventoryRow.character_id.in_(char_ids)))
    for model in DERIVED_MODELS:
        if model is InventoryRow:
            continue
        session.execute(delete(model).where(model.campaign_id == campaign_id))
    session.execute(
        delete(EventRow).where(EventRow.campaign_id == campaign_id, EventRow.turn_no > turn_no)
    )
    campaign = session.get(Campaign, campaign_id)
    campaign.turn_no = 0
    session.flush()

    for event in events:
        for raw in event.payload.get("deltas", []):
            try:
                apply_delta(session, Delta.from_dict(raw), source="engine")
            except DeltaRejected:
                # A delta whose row no longer exists at this point in history is
                # not an error during replay; the event that created it may have
                # been cut. Skip it rather than aborting the rebuild.
                continue
        _run_reducer(session, event)

    campaign.turn_no = turn_no
    session.flush()
    return len(events)


def events_for(
    session: Session, campaign_id: str, *, since_turn: int = 0, types: Iterable[str] | None = None
) -> list[EventRow]:
    stmt = select(EventRow).where(
        EventRow.campaign_id == campaign_id, EventRow.turn_no >= since_turn
    )
    if types is not None:
        stmt = stmt.where(EventRow.type.in_(list(types)))
    return list(session.scalars(stmt.order_by(EventRow.id)))
