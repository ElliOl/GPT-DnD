#!/usr/bin/env python3
"""
Migrate the JSON-on-disk game state into the database.

The split this enforces: ``adventure.json`` and its chapter/location/NPC files
stay as **content** — they are read-only module definitions the loader still
reads. What moves is **state**: HP, quest status, who has been met, which
locations are discovered, where the Rockseeker brothers actually are.

Everything is written as one ``campaign_seeded`` event, so turn 0 of the migrated
campaign is reconstructible from the log like any other turn.

Usage:
    python scripts/migrate_state.py --campaign-id my-campaign
    python scripts/migrate_state.py --adventure lost_mines_of_phandelver --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.engine.dice import campaign_seed  # noqa: E402
from backend.state.db import init_db, session_scope  # noqa: E402
from backend.state.events import EventType, record_event  # noqa: E402
from backend.state.models import Campaign  # noqa: E402

ADVENTURES_DIR = REPO_ROOT / "backend" / "adventures"
CHARACTERS_DIR = REPO_ROOT / "data" / "characters"

ABILITY_KEYS = {"str": "STR", "dex": "DEX", "con": "CON", "int": "INT", "wis": "WIS", "cha": "CHA"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text.lower()).strip("_")


def character_rows(campaign_id: str) -> list[dict[str, Any]]:
    """PCs from ``data/characters/*.json``."""
    rows: list[dict[str, Any]] = []
    if not CHARACTERS_DIR.exists():
        return rows

    for path in sorted(CHARACTERS_DIR.glob("*.json")):
        data = _load_json(path)
        stats = {
            ABILITY_KEYS[k]: v
            for k, v in (data.get("abilities") or {}).items()
            if k in ABILITY_KEYS
        }
        rows.append(
            {
                "id": path.stem,
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
                "resources": {
                    "spell_slots": data.get("spell_slots", {}),
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


def inventory_rows(character_rows_: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for char in character_rows_:
        path = CHARACTERS_DIR / f"{char['id']}.json"
        if not path.exists():
            continue
        data = _load_json(path)
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


def npc_rows(adventure_dir: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    """NPC *state* from the module's NPC files plus whatever play has established.

    The rich personality/dialogue content stays in the JSON files — only status,
    location, attitude and goals come across, because those are the fields the
    world tick will start writing to.
    """
    met = {str(n) for n in state.get("met_npcs", [])}
    brothers = state.get("rockseeker_brothers", {}) or {}
    plot = state.get("black_spider_plot", {}) or {}

    rows: list[dict[str, Any]] = []
    npc_dir = adventure_dir / "npcs"
    if not npc_dir.exists():
        return rows

    for path in sorted(npc_dir.glob("*.json")):
        data = _load_json(path)
        npc_id = data.get("id", path.stem)
        personality = data.get("personality", {}) or {}

        status = "alive"
        location = None
        if npc_id in brothers:
            status = brothers[npc_id].get("status", "alive")
            location = brothers[npc_id].get("location")
        for key in ("gundren", "sildar"):
            if npc_id.startswith(key):
                status = plot.get(f"{key}_status", status)
                location = plot.get(f"{key}_location", location)
        if status == "captured":
            status = "alive"  # captured is a condition, not a life state

        rows.append(
            {
                "id": npc_id,
                "template_id": npc_id,
                "name": data.get("name", npc_id),
                "status": status,
                "location_id": location,
                "attitude_to_party": 1 if npc_id in met else 0,
                "importance": 3 if npc_id in met else 1,
                "goals": personality.get("goals", []),
                "schedule": data.get("schedule", {}) or {},
                "resources": {"affiliation": data.get("affiliation", "")},
                "knowledge": [],
            }
        )
    return rows


def location_rows(adventure_dir: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    discovered = {str(loc) for loc in state.get("discovered_locations", [])}
    current = state.get("current_state", {}).get("location")
    rows: list[dict[str, Any]] = []
    loc_dir = adventure_dir / "locations"
    if loc_dir.exists():
        for path in sorted(loc_dir.glob("*.json")):
            data = _load_json(path)
            loc_id = data.get("id", path.stem)
            rows.append(
                {
                    "id": loc_id,
                    "name": data.get("name", loc_id),
                    "discovered": loc_id in discovered or loc_id == current,
                    "visited": loc_id == current,
                    "state_overrides": {},
                }
            )
    known = {r["id"] for r in rows}
    # Places play has been that have no file yet (e.g. "neverwinter").
    for loc_id in discovered - known:
        rows.append({"id": loc_id, "name": loc_id.replace("_", " ").title(),
                     "discovered": True, "visited": False, "state_overrides": {}})
    return rows


def quest_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for quest in state.get("active_quests", []) or []:
        rows.append(
            {
                "id": quest.get("id") or _slug(quest.get("name", "quest")),
                "title": quest.get("name", ""),
                "status": quest.get("status", "active"),
                "giver_npc": _slug(quest.get("giver", "")) or None,
                "hidden": False,
                "details": {k: v for k, v in quest.items() if k not in ("id", "name", "status")},
            }
        )
    return rows


def canon_from_history(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Things play has already committed to become canon facts with provenance."""
    facts: list[dict[str, Any]] = []
    for event in state.get("important_events", []) or []:
        if not event:
            continue
        fact = {"text": str(event), "entities": [], "source": "play"}
        if fact not in facts:  # the legacy log duplicates entries
            facts.append(fact)
    summary = state.get("campaign_summary")
    if summary:
        facts.insert(0, {"text": summary, "entities": [], "source": "module"})
    plot = state.get("black_spider_plot", {}) or {}
    if plot.get("true_name"):
        facts.append(
            {
                "text": f"The Black Spider's true name is {plot['true_name']}"
                + (f", a {plot['race']}." if plot.get("race") else "."),
                "entities": ["black_spider", plot["true_name"].lower()],
                "source": "module",
                # Known to the world, not necessarily to the party.
            }
        )
    return facts


def build_seed_payload(adventure_id: str, campaign_id: str) -> dict[str, Any]:
    adventure_dir = ADVENTURES_DIR / adventure_id
    if not adventure_dir.exists():
        raise SystemExit(f"No such adventure: {adventure_dir}")
    state = _load_json(adventure_dir / "adventure.json")
    current = state.get("current_state", {}) or {}

    chars = character_rows(campaign_id)
    for row in chars:
        row["location_id"] = current.get("location")

    return {
        "campaign": {
            "adventure_id": adventure_id,
            "name": state.get("name", adventure_id),
            "session_no": int(current.get("session_number", 1)),
            "rng_seed": campaign_seed(campaign_id),
        },
        "characters": chars,
        "inventory": inventory_rows(chars),
        "npcs": npc_rows(adventure_dir, state),
        "locations": location_rows(adventure_dir, state),
        "quests": quest_rows(state),
        "clocks": [],
        "canon_facts": canon_from_history(state),
        "legacy": {"chapter": current.get("chapter"), "party_level": current.get("party_level")},
    }


def migrate(adventure_id: str, campaign_id: str, dry_run: bool = False) -> dict[str, Any]:
    payload = build_seed_payload(adventure_id, campaign_id)
    if dry_run:
        return payload

    init_db()
    with session_scope() as session:
        if session.get(Campaign, campaign_id) is not None:
            raise SystemExit(
                f"Campaign {campaign_id!r} already exists. Pick another --campaign-id, "
                "or delete it first — migration is not idempotent by design."
            )
        session.add(
            Campaign(
                id=campaign_id,
                adventure_id=adventure_id,
                name=payload["campaign"]["name"],
                rng_seed=payload["campaign"]["rng_seed"],
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
    parser.add_argument("--adventure", default="lost_mines_of_phandelver")
    parser.add_argument("--campaign-id", default=None, help="defaults to the adventure id")
    parser.add_argument("--dry-run", action="store_true", help="print the payload, write nothing")
    args = parser.parse_args()

    campaign_id = args.campaign_id or args.adventure
    payload = migrate(args.adventure, campaign_id, dry_run=args.dry_run)

    counts = {k: len(v) for k, v in payload.items() if isinstance(v, list)}
    if args.dry_run:
        print(json.dumps(payload, indent=2)[:4000])
        print("\n… dry run, nothing written.")
    print(f"\ncampaign: {campaign_id}  ({args.adventure})")
    for key, count in counts.items():
        print(f"  {key:<14} {count}")


if __name__ == "__main__":
    main()
