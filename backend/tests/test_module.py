"""
Module-agnosticism.

The suite below builds an adventure that has nothing to do with any module
shipped in this repo — different entity shapes, different bespoke flags, a
different vocabulary for "dead" — and requires the runtime to load, validate and
seed it without a line of adventure-specific code.
"""

from __future__ import annotations

import json

import pytest

from backend.content.module import Module, ModuleError, normalize_status
from backend.content.schema import validate_path


def write_module(root, manifest: dict, **dirs) -> str:
    """Write a module directory from plain dicts and return its path."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "adventure.json").write_text(json.dumps(manifest, indent=2))
    for dirname, files in dirs.items():
        directory = root / dirname
        directory.mkdir(exist_ok=True)
        for name, data in files.items():
            (directory / f"{name}.json").write_text(json.dumps(data, indent=2))
    return str(root)


@pytest.fixture()
def salt_marsh(tmp_path):
    """An invented module. Shapes deliberately unlike Phandelver's."""
    return write_module(
        tmp_path / "ghosts_of_salt_marsh",
        {
            "id": "ghosts_of_salt_marsh",
            "name": "Ghosts of Salt Marsh",
            "campaign_summary": "The party took ship to the drowned village.",
            "current_state": {"location": "sea_ghost", "chapter": "ch1_the_hauntings"},
            "discovered_locations": ["salt_marsh", "sea_ghost"],
            "met_npcs": ["oceanus"],
            "important_events": ["The party burned the smugglers' skiff."],
            # Bespoke, entirely unknown to the runtime:
            "tidal_charts": {"moon_phase": "waning", "spring_tide_in_days": 3},
            "smuggler_ring": {"leader_status": "slain", "leader_hideout": "sea_ghost_hold"},
            "state_bindings": {
                "npcs": [
                    {"npc": "sanbalet", "field": "status", "flag": "smuggler_ring.leader_status"},
                    {"npc": "sanbalet", "field": "location_id", "flag": "smuggler_ring.leader_hideout"},
                    {"npc": "oceanus", "field": "importance", "default": 3},
                ],
                "clocks": [
                    {"name": "The spring tide", "size": 3, "flag": "tidal_charts.spring_tide_in_days"}
                ],
                "canon": [
                    {"flag": "tidal_charts.moon_phase", "text": "The moon is {value}.",
                     "entities": ["moon"]}
                ],
            },
            "active_quests": [
                {"id": "find_the_ring", "name": "Find the smugglers' ring", "status": "active",
                 "giver": "Eliander Fireborn"}
            ],
        },
        locations={
            "salt_marsh": {"id": "salt_marsh", "name": "Salt Marsh", "vibe": "damp"},
            "sea_ghost": {"id": "sea_ghost", "name": "The Sea Ghost", "decks": 3},
        },
        npcs={
            # Two different NPC shapes, neither matching this repo's other module.
            "oceanus": {"id": "oceanus", "name": "Oceanus", "motivations": "Protect the reef"},
            "sanbalet": {"id": "sanbalet", "name": "Sanbalet",
                         "personality": {"goals": ["Move the cargo", "Stay unseen"]}},
        },
        chapters={"ch1_the_hauntings": {"id": "ch1_the_hauntings", "name": "The Hauntings"}},
    )


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def test_an_unknown_module_loads_from_a_path(salt_marsh):
    module = Module.load(salt_marsh)
    assert module.id == "ghosts_of_salt_marsh"
    assert set(module.locations) == {"salt_marsh", "sea_ghost"}
    assert set(module.npcs) == {"oceanus", "sanbalet"}
    assert module.start_location == "sea_ghost"


def test_a_module_with_only_a_manifest_loads(tmp_path):
    path = write_module(tmp_path / "bare", {"id": "bare", "name": "Bare"})
    module = Module.load(path)
    assert module.locations == {} and module.npcs == {}
    assert module.start_location is None


def test_entity_files_keep_their_own_shape(salt_marsh):
    module = Module.load(salt_marsh)
    assert module.locations["sea_ghost"].get("decks") == 3
    assert module.npcs["oceanus"].get("motivations") == "Protect the reef"


def test_files_without_an_id_fall_back_to_the_filename(tmp_path):
    path = write_module(
        tmp_path / "anon", {"id": "anon", "name": "Anon"},
        locations={"the_crypt": {"name": "The Crypt"}},
    )
    assert "the_crypt" in Module.load(path).locations


def test_unknown_metadata_is_preserved_as_world_flags(salt_marsh):
    flags = Module.load(salt_marsh).world_flags()
    assert flags["tidal_charts"]["moon_phase"] == "waning"
    assert flags["smuggler_ring"]["leader_status"] == "slain"
    # Interpreted keys must not leak into the flags.
    assert "current_state" not in flags and "state_bindings" not in flags


def test_a_missing_module_says_where_it_looked():
    with pytest.raises(ModuleError, match="Looked in"):
        Module.load("no_such_module")


def test_invalid_json_names_the_file(tmp_path):
    root = tmp_path / "broken"
    root.mkdir()
    (root / "adventure.json").write_text("{ not json")
    with pytest.raises(ModuleError, match="invalid JSON"):
        Module.load(str(root))


# --------------------------------------------------------------------------
# Bindings — module state understood mechanically, declared as data
# --------------------------------------------------------------------------

def test_bindings_resolve_a_modules_own_flags(salt_marsh):
    bound = Module.load(salt_marsh).bound_npc_states()
    assert bound["sanbalet"]["status"] == "dead"  # "slain" normalised
    assert bound["sanbalet"]["location_id"] == "sea_ghost_hold"
    assert bound["oceanus"]["importance"] == 3


def test_bindings_build_clocks_from_flags(salt_marsh):
    clock = Module.load(salt_marsh).bound_clocks()[0]
    assert clock["name"] == "The spring tide"
    assert clock["size"] == 3 and clock["filled"] == 3


def test_bindings_render_canon_facts(salt_marsh):
    facts = Module.load(salt_marsh).bound_canon()
    assert facts[0]["text"] == "The moon is waning."


def test_a_binding_on_a_missing_flag_is_skipped(tmp_path):
    path = write_module(
        tmp_path / "m", {
            "id": "m", "name": "M",
            "state_bindings": {"canon": [{"flag": "nothing.here", "text": "never {value}"}]},
        },
    )
    assert Module.load(path).bound_canon() == []


@pytest.mark.parametrize(
    "raw,expected",
    [("slain", "dead"), ("deceased", "dead"), ("prisoner", "captured"),
     ("escaped", "fled"), ("well", "alive"), ("", "alive"), (None, "alive"),
     ("something odd", "alive")],
)
def test_status_vocabulary_is_normalised(raw, expected):
    assert normalize_status(raw) == expected


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def test_a_well_formed_module_validates(salt_marsh):
    from pathlib import Path

    report = validate_path(Path(salt_marsh))
    assert report.ok, report.render()
    assert report.counts["npc"] == 2


def test_a_manifest_without_an_id_is_an_error(tmp_path):
    from pathlib import Path

    path = write_module(tmp_path / "noid", {"name": "No Id"})
    report = validate_path(Path(path))
    assert not report.ok
    assert any("'id' is required" in e for e in report.errors)


def test_a_missing_manifest_is_an_error(tmp_path):
    from pathlib import Path

    (tmp_path / "empty").mkdir()
    report = validate_path(tmp_path / "empty")
    assert not report.ok


def test_dangling_references_warn_but_do_not_block(tmp_path):
    from pathlib import Path

    path = write_module(
        tmp_path / "dangling",
        {"id": "d", "name": "D", "discovered_locations": ["atlantis"],
         "current_state": {"location": "atlantis"}},
        locations={"shore": {"id": "shore", "name": "Shore"}},
    )
    report = validate_path(Path(path))
    assert report.ok
    assert any("atlantis" in w for w in report.warnings)


def test_a_broken_binding_is_an_error(tmp_path):
    from pathlib import Path

    path = write_module(
        tmp_path / "badbind",
        {"id": "b", "name": "B", "state_bindings": {"npcs": [{"npc": "x"}]}},
    )
    report = validate_path(Path(path))
    assert not report.ok
    assert any("needs 'field'" in e for e in report.errors)


# --------------------------------------------------------------------------
# Seeding an unknown module end to end
# --------------------------------------------------------------------------

def test_an_unknown_module_seeds_a_playable_campaign(db, salt_marsh, tmp_path):
    from scripts.migrate_state import migrate

    party = tmp_path / "party"
    party.mkdir()
    (party / "wren.json").write_text(json.dumps({
        "name": "Wren", "class": "Ranger", "level": 2, "hp": 14, "max_hp": 16, "ac": 15,
        "abilities": {"str": 12, "dex": 16, "con": 14, "int": 10, "wis": 14, "cha": 8},
        "proficiencies": ["Survival"], "save_proficiencies": ["dex"],
        "inventory": ["Longbow", {"name": "Rations", "qty": 5}],
    }))

    migrate(salt_marsh, "salt-1", party_dir=party)

    from backend.state.db import session_scope
    from backend.state.models import Campaign, CanonFactRow, CharacterRow, ClockRow, NPCRow

    with session_scope() as session:
        campaign = session.get(Campaign, "salt-1")
        assert campaign.adventure_id == "ghosts_of_salt_marsh"
        # The module's own bespoke state survived the trip.
        assert campaign.world_flags["tidal_charts"]["moon_phase"] == "waning"

        wren = session.get(CharacterRow, "wren")
        assert wren.hp == 14 and wren.location_id == "sea_ghost"

        assert session.get(NPCRow, "sanbalet").status == "dead"
        assert session.get(NPCRow, "oceanus").importance == 3
        assert session.query(ClockRow).count() == 1
        texts = [f.text for f in session.query(CanonFactRow).all()]
        assert "The moon is waning." in texts
        assert "The party burned the smugglers' skiff." in texts


def test_seeding_the_same_campaign_twice_is_refused(db, salt_marsh, tmp_path):
    from scripts.migrate_state import migrate

    party = tmp_path / "party"
    party.mkdir()
    migrate(salt_marsh, "salt-2", party_dir=party)
    with pytest.raises(SystemExit, match="already exists"):
        migrate(salt_marsh, "salt-2", party_dir=party)
