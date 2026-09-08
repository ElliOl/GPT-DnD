"""
Assembles the packet the Narrator sees.

The budget is roughly 3-5k tokens, and the shape matters more than the size: a
stable system prompt (cacheable), then the scene, then who is present, then the
handful of canon facts that bear on *this* turn, then the resolution. Volatile
content goes last so the cached prefix survives.

Two rules this module exists to enforce:

* the Narrator is never handed a hidden clock or a secret it could leak, and
* it is never handed more canon than it can hold in mind — five relevant facts
  beat fifty irrelevant ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..content.module import Module
from ..engine.resolve import Resolution
from ..state.canon import relevant_facts
from ..state.events import EventType
from ..state.models import Campaign, CharacterRow, ClockRow, EventRow, LocationRow, NPCRow

#: How many prior turns of transcript ride along.
RECENT_TURNS = 6
#: How many canon facts to retrieve for a turn.
TOP_FACTS = 5
#: Scene text is trimmed hard — the Narrator needs the shape of the room, not the
#: module's full prose, which it would otherwise be tempted to recite.
SCENE_CHARS = 900


@dataclass
class ContextPacket:
    """Everything the Narrator gets for one turn."""

    player_message: str
    scene: str = ""
    present_npcs: list[str] = field(default_factory=list)
    canon_facts: list[str] = field(default_factory=list)
    recent_turns: list[dict[str, Any]] = field(default_factory=list)
    resolution_facts: list[str] = field(default_factory=list)
    invalid_reason: str | None = None
    clocks: list[str] = field(default_factory=list)
    party: list[str] = field(default_factory=list)

    def as_kwargs(self) -> dict[str, Any]:
        """Shaped for ``NarratorAgent.build_messages``."""
        scene = self.scene
        if self.clocks:
            scene = f"{scene}\n\nPressure: {'; '.join(self.clocks)}".strip()
        return {
            "player_message": self.player_message,
            "scene": scene,
            "present_npcs": self.present_npcs + self.party,
            "canon_facts": self.canon_facts,
            "recent_turns": self.recent_turns,
            "resolution_facts": self.resolution_facts,
            "invalid_reason": self.invalid_reason,
        }


def _scene_text(module: Module, location_id: str | None, overrides: dict[str, Any]) -> str:
    """Describe a location from whatever fields the module happens to use."""
    if not location_id:
        return ""
    entity = module.entity(location_id, "location")
    if entity is None:
        return location_id.replace("_", " ").title()

    parts = [entity.name]
    for key in ("description", "atmosphere", "current_problem", "overview", "summary"):
        value = entity.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    text = "\n".join(parts)[:SCENE_CHARS]

    if overrides:
        changes = "; ".join(f"{k}: {v}" for k, v in overrides.items())
        text = f"{text}\n\nChanged since the module: {changes}"
    return text


def party_location(session: Session, campaign_id: str) -> str | None:
    """Where the party is. The first PC with a location wins; they travel together."""
    row = session.scalars(
        select(CharacterRow)
        .where(
            CharacterRow.campaign_id == campaign_id,
            CharacterRow.is_pc.is_(True),
            CharacterRow.location_id.is_not(None),
        )
        .limit(1)
    ).first()
    return row.location_id if row else None


def present_npcs(session: Session, campaign_id: str, location_id: str | None) -> list[NPCRow]:
    """Who is on stage: alive, here, and not hiding elsewhere."""
    if not location_id:
        return []
    return list(
        session.scalars(
            select(NPCRow).where(
                NPCRow.campaign_id == campaign_id,
                NPCRow.location_id == location_id,
                NPCRow.status.in_(("alive", "captured")),
            )
        )
    )


def recent_transcript(session: Session, campaign_id: str, limit: int = RECENT_TURNS) -> list[dict]:
    """The last few exchanges, oldest first."""
    rows = list(
        session.scalars(
            select(EventRow)
            .where(
                EventRow.campaign_id == campaign_id,
                EventRow.type.in_((EventType.PLAYER_INPUT, EventType.NARRATION)),
            )
            .order_by(EventRow.id.desc())
            .limit(limit * 2)
        )
    )
    rows.reverse()
    return [
        {
            "role": "player" if r.type == EventType.PLAYER_INPUT else "dm",
            "text": str(r.payload.get("text", ""))[:1200],
        }
        for r in rows
    ]


def build_packet(
    session: Session,
    campaign_id: str,
    module: Module,
    player_message: str,
    resolution: Resolution | None = None,
) -> ContextPacket:
    """Assemble one turn's packet."""
    campaign = session.get(Campaign, campaign_id)
    location_id = party_location(session, campaign_id)

    location_row = session.get(LocationRow, location_id) if location_id else None
    overrides = dict(location_row.state_overrides or {}) if location_row else {}

    npcs = present_npcs(session, campaign_id, location_id)
    party = list(
        session.scalars(
            select(CharacterRow).where(
                CharacterRow.campaign_id == campaign_id, CharacterRow.is_pc.is_(True)
            )
        )
    )

    # Retrieve against the player's words plus whatever the engine just made true,
    # so a resolution that names an NPC pulls in what canon knows about them.
    query = " ".join([player_message] + (resolution.facts if resolution else []))
    facts = relevant_facts(session, campaign_id, query, top_k=TOP_FACTS)

    # Only clocks the party could plausibly perceive. A hidden clock in the
    # packet is a hidden clock the Narrator will eventually mention.
    visible_clocks = session.scalars(
        select(ClockRow).where(
            ClockRow.campaign_id == campaign_id, ClockRow.hidden.is_(False)
        )
    )

    return ContextPacket(
        player_message=player_message,
        scene=_scene_text(module, location_id, overrides),
        present_npcs=[
            f"{n.name} (attitude {n.attitude_to_party:+d})"
            + (" — captive" if n.status == "captured" else "")
            for n in npcs
        ],
        party=[
            f"{c.name}, {c.race} {c.char_class} {c.level} ({c.hp}/{c.max_hp} HP"
            + (f", {', '.join(c.conditions)}" if c.conditions else "")
            + ")"
            for c in party
        ],
        canon_facts=[f.text for f in facts],
        recent_turns=recent_transcript(session, campaign_id),
        resolution_facts=list(resolution.facts) if resolution else [],
        invalid_reason=resolution.invalid_reason if resolution else None,
        clocks=[f"{c.name} {c.filled}/{c.size}" for c in visible_clocks],
    )


def scene_roster(session: Session, campaign_id: str) -> dict[str, str]:
    """Names the Intent agent may resolve a target to: the party plus who's here.

    Without this it will happily target a goblin from three sessions ago.
    """
    location_id = party_location(session, campaign_id)
    roster: dict[str, str] = {}
    for row in session.scalars(
        select(CharacterRow).where(CharacterRow.campaign_id == campaign_id)
    ):
        if row.is_pc or row.location_id == location_id:
            roster[row.id] = row.name
    for npc in present_npcs(session, campaign_id, location_id):
        roster[npc.id] = npc.name
    return roster
