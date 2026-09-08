"""
Mechanical state tables.

These are the *only* place HP, gold, position, and clock progress are allowed to
live. LLM agents may propose changes; nothing here is written except by code in
``state/events.py`` applying a validated delta.

Design notes
------------
* ``events`` is append-only. Every mutation to any other table is preceded by an
  event row that authorizes it, which is what makes rewind-to-turn-N a replay
  rather than an undo.
* JSON columns hold shapes that are read whole and never queried by field. If you
  find yourself wanting ``WHERE resources->>'spell_slots'``, promote it to a column.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for all mechanical-state tables."""

    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    adventure_id: Mapped[str] = mapped_column(String(128))
    # Where the module was loaded from. An id alone is not enough: a module may
    # live outside the runtime's search paths, and a campaign must still find it
    # on the next boot.
    module_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    name: Mapped[str] = mapped_column(String(255), default="")

    # In-world clock.
    day: Mapped[int] = mapped_column(Integer, default=1)
    hour: Mapped[int] = mapped_column(Integer, default=8)

    session_no: Mapped[int] = mapped_column(Integer, default=1)
    turn_no: Mapped[int] = mapped_column(Integer, default=0)

    # Root seed for the campaign RNG. Every roll derives from (seed, turn, index)
    # so a replayed session produces byte-identical dice.
    rng_seed: Mapped[int] = mapped_column(Integer, default=0)

    # Module state the runtime doesn't interpret, kept verbatim. A module can
    # carry any bespoke structure it likes without the engine knowing about it;
    # `state_bindings` in its adventure.json is how it opts specific flags into
    # mechanics. Nothing here is ever lost just because the shape was unfamiliar.
    world_flags: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    created_at: Mapped[_dt.datetime] = mapped_column(DateTime, default=_utcnow)

    characters: Mapped[list["CharacterRow"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class CharacterRow(Base):
    """PCs and statted NPCs alike. ``is_pc`` separates them."""

    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    is_pc: Mapped[bool] = mapped_column(Boolean, default=True)

    level: Mapped[int] = mapped_column(Integer, default=1)
    char_class: Mapped[str] = mapped_column(String(64), default="")
    race: Mapped[str] = mapped_column(String(64), default="")

    hp: Mapped[int] = mapped_column(Integer, default=1)
    max_hp: Mapped[int] = mapped_column(Integer, default=1)
    temp_hp: Mapped[int] = mapped_column(Integer, default=0)
    ac: Mapped[int] = mapped_column(Integer, default=10)
    proficiency_bonus: Mapped[int] = mapped_column(Integer, default=2)
    speed: Mapped[int] = mapped_column(Integer, default=30)

    # {"STR": 10, ...}
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # ["poisoned", "prone"]
    conditions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    # {"spell_slots": {"1": 2}, "hit_dice": 3, "rage": 2, ...}
    resources: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # {"skills": ["Perception"], "saves": ["DEX"], "weapons": [...]}
    proficiencies: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Death saves only matter at 0 hp; reset on any healing.
    death_save_successes: Mapped[int] = mapped_column(Integer, default=0)
    death_save_failures: Mapped[int] = mapped_column(Integer, default=0)

    location_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    campaign: Mapped[Campaign] = relationship(back_populates="characters")


class InventoryRow(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id"), index=True)
    item_id: Mapped[str] = mapped_column(String(128))
    qty: Mapped[int] = mapped_column(Integer, default=1)
    equipped: Mapped[bool] = mapped_column(Boolean, default=False)
    attuned: Mapped[bool] = mapped_column(Boolean, default=False)
    props: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    __table_args__ = (UniqueConstraint("character_id", "item_id", name="uq_inventory_char_item"),)


class NPCRow(Base):
    """Offscreen agency lives here: goals, schedule, and attitude drive the world tick."""

    __tablename__ = "npcs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    template_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    name: Mapped[str] = mapped_column(String(128))

    status: Mapped[str] = mapped_column(String(32), default="alive")  # alive|dead|fled|captured
    location_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attitude_to_party: Mapped[int] = mapped_column(Integer, default=0)  # -5..5
    importance: Mapped[int] = mapped_column(Integer, default=1)  # 1..3, gates world-tick inclusion

    goals: Mapped[list[Any]] = mapped_column(JSON, default=list)
    schedule: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resources: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # What they know and how they learned it — the substrate for rumor spread.
    knowledge: Mapped[list[Any]] = mapped_column(JSON, default=list)

    character_id: Mapped[str | None] = mapped_column(
        ForeignKey("characters.id"), nullable=True
    )


class QuestRow(Base):
    __tablename__ = "quests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="available")
    giver_npc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ClockRow(Base):
    """Progress clocks. Deterministic pressure: they tick from events, not vibes."""

    __tablename__ = "clocks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    filled: Mapped[int] = mapped_column(Integer, default=0)
    size: Mapped[int] = mapped_column(Integer, default=4)
    owner_faction: Mapped[str | None] = mapped_column(String(128), nullable=True)
    on_complete: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    hidden: Mapped[bool] = mapped_column(Boolean, default=True)


class LocationRow(Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    discovered: Mapped[bool] = mapped_column(Boolean, default=False)
    visited: Mapped[bool] = mapped_column(Boolean, default=False)
    # Deltas layered over the content-file definition (cleared rooms, opened doors).
    state_overrides: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class EventRow(Base):
    """Append-only. Never UPDATE, never DELETE — rewind truncates by replaying a prefix."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    turn_no: Mapped[int] = mapped_column(Integer, default=0)
    ts: Mapped[_dt.datetime] = mapped_column(DateTime, default=_utcnow)
    type: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Who authorized this: "engine" | "scribe" | "world_tick" | "admin" | "migration"
    source: Mapped[str] = mapped_column(String(32), default="engine")

    __table_args__ = (Index("ix_events_campaign_turn", "campaign_id", "turn_no"),)


class CanonFactRow(Base):
    """Everything the world has committed to, with provenance. The Auditor's ground truth."""

    __tablename__ = "canon_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    entities: Mapped[list[Any]] = mapped_column(JSON, default=list)
    established_turn: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(32), default="play")  # module|play|architect
    contradicted_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    __table_args__ = (Index("ix_canon_campaign_turn", "campaign_id", "established_turn"),)


class TraceRow(Base):
    """One row per agent call. Built in phase 0 on purpose — with seven agents,
    "why did it say that" is unanswerable without this."""

    __tablename__ = "traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    turn_no: Mapped[int] = mapped_column(Integer, default=0)
    agent: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128), default="")
    ts: Mapped[_dt.datetime] = mapped_column(DateTime, default=_utcnow)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    prompt: Mapped[str] = mapped_column(Text, default="")
    output: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


__all__ = [
    "Base",
    "Campaign",
    "CharacterRow",
    "InventoryRow",
    "NPCRow",
    "QuestRow",
    "ClockRow",
    "LocationRow",
    "EventRow",
    "CanonFactRow",
    "TraceRow",
]
