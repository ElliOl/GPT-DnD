#!/usr/bin/env python3
"""
Seed a campaign in the database from any adventure module.

The split this enforces: a module's JSON stays as **content** — read-only
definitions the loader still reads. What moves into the database is **state**:
HP, quest status, who has been met, which locations are discovered.

Nothing here knows about any particular adventure. Module-specific state is
handled two ways, both generic:

* anything in ``adventure.json`` the runtime doesn't interpret is preserved
  verbatim as ``campaign.world_flags`` — a module never loses state because its
  shape was unfamiliar;
* a module that wants specific flags understood mechanically declares that in an
  optional ``state_bindings`` block (see ``backend/content/module.py``), which is
  data, not code.

Everything is written as one ``campaign_seeded`` event, so turn 0 of a migrated
campaign replays like any other turn.

Usage:
    python scripts/migrate_state.py --module my_module --campaign-id my-campaign
    python scripts/migrate_state.py --module my_module --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.content.module import Entity, Module, normalize_status  # noqa: E402
from backend.content.schema import validate_path  # noqa: E402
from backend.engine.dice import campaign_seed  # noqa: E402
from backend.state.db import init_db, session_scope  # noqa: E402
from backend.state.events import EventType, record_event  # noqa: E402
from backend.state.models import Campaign  # noqa: E402

DEFAULT_PARTY_DIR = REPO_ROOT / "data" / "characters"

ABILITY_KEYS = {"str": "STR", "dex": "DEX", "con": "CON", "int": "INT", "wis": "WIS", "cha": "CHA"}


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in str(text).lower()).strip("_")


# --------------------------------------------------------------------------
# The party
# --------------------------------------------------------------------------

def _normalize_slot_levels(slots: dict[str, Any]) -> dict[str, int]:
    """Sheet slot keys are ordinals ("1st"); the rules engine indexes by plain
    digit ("1"). Strip whatever's not a leading number so either shape works."""
    normalized: dict[str, int] = {}
    for key, value in slots.items():
        digits = "".join(c for c in str(key) if c.isdigit())
        if digits:
            normalized[digits] = int(value)
    return normalized


def character_rows(party_dir: Path, start_location: str | None) -> list[dict[str, Any]]:
    """PCs from a directory of character sheets.

    Sheet shape is the repo's existing one; unknown keys ride along in
    ``resources`` rather than being dropped.
    """
    rows: list[dict[str, Any]] = []
    if not party_dir.exists():
        return rows

    for path in sorted(party_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        stats = {
            ABILITY_KEYS[k]: v
            for k, v in (data.get("abilities") or {}).items()
            if k in ABILITY_KEYS
        }
        # Spellcasting sheets nest slots under `spellcasting`; a top-level
        # `spell_slots` is kept as a fallback for other sheet shapes.
        spellcasting = data.get("spellcasting") or {}
        max_slots = _normalize_slot_levels(
            spellcasting.get("spell_slots") or data.get("spell_slots") or {}
        )
        rows.append(
            {
                "id": str(data.get("id") or path.stem),
                "name": data.get("name", path.stem),
                "is_pc": True,
                "level": int(data.get("level", 1)),
                "char_class": data.get("class", ""),
                "race": data.get("race", ""),
                "hp": int(data.get("hp", data.get("max_hp", 1))),
                "max_hp": int(data.get("max_hp", 1)),
                "temp_hp": int(data.get("temp_hp", 0)),
                "ac": int(data.get("ac", 10)),
                "speed": int(data.get("speed", 30)),
                "proficiency_bonus": int(data.get("proficiency_bonus", 2)),
                "stats": stats,
                "conditions": list(data.get("conditions", [])),
                "location_id": start_location,
                "resources": {
                    "spell_slots": dict(max_slots),
                    "max_spell_slots": dict(max_slots),
                    "hit_dice": data.get("hit_dice", data.get("level", 1)),
                    "weapons": data.get("weapons", []),
                    "gold": data.get("gold", 0),
                },
                "proficiencies": {
                    "skills": data.get("proficiencies", []),
                    "saves": [s.upper() for s in data.get("save_proficiencies", [])],
                },
            }
        )
    return rows


def inventory_rows(party_dir: Path, characters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for char in characters:
        path = party_dir / f"{char['id']}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data.get("inventory", []) or []:
            name = item if isinstance(item, str) else item.get("name", "")
            if not name:
                continue
            rows.append(
                {
                    "character_id": char["id"],
                    "item_id": _slug(name),
                    "qty": 1 if isinstance(item, str) else int(item.get("qty", 1)),
                    "props": {"name": name},
                }
            )
    return rows


# --------------------------------------------------------------------------
# The module
# --------------------------------------------------------------------------

def _npc_goals(entity: Entity) -> list[Any]:
    """Goals live in different places in different modules. Try the common ones."""
    for path in (("personality", "goals"), ("goals",), ("motivations",)):
        node: Any = entity.data
        for part in path:
            node = node.get(part) if isinstance(node, dict) else None
        if isinstance(node, list):
            return node
        if isinstance(node, str):
            return [node]
    return []


def npc_rows(module: Module) -> list[dict[str, Any]]:
    """NPC *state* only. Personality, dialogue and tactics stay in the files.

    Status and location come from the module's ``state_bindings`` when it
    declares them, and default to alive-and-unplaced otherwise.
    """
    met = {str(n) for n in module.metadata.get("met_npcs", []) or []}
    bound = module.bound_npc_states()

    rows: list[dict[str, Any]] = []
    for npc_id, entity in module.npcs.items():
        overrides = bound.get(npc_id, {})
        rows.append(
            {
                "id": npc_id,
                "template_id": npc_id,
                "name": entity.name,
                "status": normalize_status(overrides.get("status", entity.get("status", "alive"))),
                "location_id": overrides.get("location_id") or entity.get("location"),
                "attitude_to_party": int(overrides.get("attitude_to_party", 1 if npc_id in met else 0)),
                "importance": int(overrides.get("importance", 3 if npc_id in met else 1)),
                "goals": _npc_goals(entity),
                "schedule": entity.get("schedule") or {},
                "resources": {"affiliation": entity.get("affiliation", "")},
                "knowledge": [],
            }
        )

    # NPCs a binding names but that have no file yet — keep the state anyway.
    for npc_id, overrides in bound.items():
        if npc_id in module.npcs:
            continue
        rows.append(
            {
                "id": npc_id,
                "template_id": None,
                "name": npc_id.replace("_", " ").title(),
                "status": normalize_status(overrides.get("status", "alive")),
                "location_id": overrides.get("location_id"),
                "attitude_to_party": int(overrides.get("attitude_to_party", 0)),
                "importance": int(overrides.get("importance", 1)),
                "goals": [], "schedule": {}, "resources": {}, "knowledge": [],
            }
        )
    return rows


def location_rows(module: Module) -> list[dict[str, Any]]:
    discovered = {str(loc) for loc in module.metadata.get("discovered_locations", []) or []}
    current = module.start_location

    rows = [
        {
            "id": loc_id,
            "name": entity.name,
            "discovered": loc_id in discovered or loc_id == current,
            "visited": loc_id == current,
            "state_overrides": {},
        }
        for loc_id, entity in module.locations.items()
    ]
    known = {r["id"] for r in rows}
    # Somewhere play has been that has no file — a named region, an offscreen city.
    for loc_id in discovered - known:
        rows.append(
            {
                "id": loc_id,
                "name": loc_id.replace("_", " ").title(),
                "discovered": True, "visited": False, "state_overrides": {},
            }
        )
    return rows


def quest_rows(module: Module) -> list[dict[str, Any]]:
    rows = []
    for quest in module.metadata.get("active_quests", []) or []:
        title = quest.get("name") or quest.get("title") or ""
        rows.append(
            {
                "id": str(quest.get("id") or _slug(title) or f"quest_{len(rows)}"),
                "title": title,
                "status": quest.get("status", "active"),
                "giver_npc": _slug(quest["giver"]) if quest.get("giver") else None,
                "location_id": quest.get("location"),
                "hidden": bool(quest.get("hidden", False)),
                "details": {
                    k: v for k, v in quest.items()
                    if k not in ("id", "name", "title", "status", "giver", "location", "hidden")
                },
            }
        )
    return rows


def canon_rows(module: Module) -> list[dict[str, Any]]:
    """Established truth: the campaign summary, what play has already done, and
    whatever the module binds as canon."""
    facts: list[dict[str, Any]] = []
    summary = module.metadata.get("campaign_summary")
    if summary:
        facts.append({"text": str(summary), "entities": [], "source": "module"})

    seen = {summary}
    for event in module.metadata.get("important_events", []) or []:
        text = str(event).strip()
        if text and text not in seen:  # legacy logs repeat entries
            seen.add(text)
            facts.append({"text": text, "entities": [], "source": "play"})

    facts.extend(module.bound_canon())
    return facts


# --------------------------------------------------------------------------
# Seeding
# --------------------------------------------------------------------------

def build_seed_payload(
    module: Module, campaign_id: str, party_dir: Path
) -> dict[str, Any]:
    current = module.metadata.get("current_state") or {}
    characters = character_rows(party_dir, module.start_location)

    return {
        "campaign": {
            "adventure_id": module.id,
            "name": module.name,
            "session_no": int(current.get("session_number", 1)),
            "rng_seed": campaign_seed(campaign_id),
            "world_flags": module.world_flags(),
            "module_path": str(module.root),
        },
        "characters": characters,
        "inventory": inventory_rows(party_dir, characters),
        "npcs": npc_rows(module),
        "locations": location_rows(module),
        "quests": quest_rows(module),
        "clocks": module.bound_clocks(),
        "canon_facts": canon_rows(module),
    }


def migrate(
    module_id: str,
    campaign_id: str,
    *,
    party_dir: Path = DEFAULT_PARTY_DIR,
    dry_run: bool = False,
) -> dict[str, Any]:
    module = Module.load(module_id)
    report = validate_path(module.root)
    if not report.ok:
        raise SystemExit(f"{report.render()}\n\nFix the errors above, then migrate.")

    payload = build_seed_payload(module, campaign_id, party_dir)
    if dry_run:
        return payload

    init_db()
    with session_scope() as session:
        if session.get(Campaign, campaign_id) is not None:
            raise SystemExit(
                f"Campaign {campaign_id!r} already exists. Pick another --campaign-id, "
                "or delete it first — seeding is not idempotent by design."
            )
        session.add(
            Campaign(
                id=campaign_id,
                adventure_id=module.id,
                name=module.name,
                rng_seed=payload["campaign"]["rng_seed"],
                world_flags=payload["campaign"]["world_flags"],
                module_path=payload["campaign"]["module_path"],
            )
        )
        session.flush()
        record_event(
            session, campaign_id, EventType.CAMPAIGN_SEEDED, payload,
            source="migration", turn_no=0,
        )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", "--adventure", dest="module", required=True,
                        help="module id, e.g. lost_mines_of_phandelver")
    parser.add_argument("--campaign-id", default=None, help="defaults to the module id")
    parser.add_argument("--party", default=str(DEFAULT_PARTY_DIR),
                        help="directory of PC sheets to seed the party from")
    parser.add_argument("--dry-run", action="store_true", help="print the payload, write nothing")
    args = parser.parse_args()

    campaign_id = args.campaign_id or args.module
    payload = migrate(
        args.module, campaign_id, party_dir=Path(args.party), dry_run=args.dry_run
    )

    if args.dry_run:
        print(json.dumps(payload, indent=2)[:4000])
        print("\n… dry run, nothing written.")
    print(f"\ncampaign: {campaign_id}  ({args.module})")
    for key, value in payload.items():
        if isinstance(value, list):
            print(f"  {key:<14} {len(value)}")
    flags = payload["campaign"]["world_flags"]
    if flags:
        print(f"  world_flags    {', '.join(flags)} (preserved verbatim)")


if __name__ == "__main__":
    main()
