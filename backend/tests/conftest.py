"""Shared fixtures. Nothing here needs an API key — the engine and state layer
are entirely deterministic, which is the point of building them first."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """A fresh SQLite file per test."""
    from backend.state import db as db_module

    monkeypatch.setenv("GAME_DB_URL", f"sqlite:///{tmp_path / 'test.db'}")
    db_module.reset_engine()
    db_module.init_db()
    yield db_module
    db_module.reset_engine()


@pytest.fixture()
def session(db):
    s = db.get_session()
    yield s
    s.close()


@pytest.fixture()
def campaign(session):
    """A two-PC, one-goblin campaign seeded through the event log."""
    from backend.state.events import EventType, record_event
    from backend.state.models import Campaign

    session.add(Campaign(id="c1", adventure_id="test_adventure", name="Test", rng_seed=1234))
    session.flush()
    record_event(
        session, "c1", EventType.CAMPAIGN_SEEDED,
        {
            "characters": [
                {
                    "id": "thorin", "name": "Thorin", "is_pc": True, "level": 3,
                    "hp": 24, "max_hp": 24, "ac": 16, "proficiency_bonus": 2,
                    "stats": {"STR": 16, "DEX": 12, "CON": 15, "INT": 10, "WIS": 12, "CHA": 8},
                    "proficiencies": {"skills": ["Athletics"], "saves": ["STR", "CON"]},
                    "resources": {"hit_dice": 3, "spell_slots": {}},
                },
                {
                    "id": "elara", "name": "Elara", "is_pc": True, "level": 3,
                    "hp": 16, "max_hp": 16, "ac": 12, "proficiency_bonus": 2,
                    "stats": {"STR": 8, "DEX": 14, "CON": 13, "INT": 16, "WIS": 12, "CHA": 10},
                    "proficiencies": {"skills": ["Arcana"], "saves": ["INT", "WIS"]},
                    "resources": {"hit_dice": 3, "spell_slots": {"1": 2}},
                },
                {
                    "id": "goblin_1", "name": "Goblin", "is_pc": False, "level": 1,
                    "hp": 7, "max_hp": 7, "ac": 15, "proficiency_bonus": 2,
                    "stats": {"STR": 8, "DEX": 14, "CON": 10, "INT": 10, "WIS": 8, "CHA": 8},
                },
            ],
            "locations": [{"id": "cragmaw_hideout", "name": "Cragmaw Hideout", "discovered": True}],
            "npcs": [{"id": "sildar", "name": "Sildar Hallwinter", "status": "alive", "importance": 3}],
            "clocks": [{"id": "redbrand_pressure", "name": "Redbrand pressure", "filled": 0, "size": 6}],
            "canon_facts": [{"text": "Sildar Hallwinter is a member of the Lords' Alliance."}],
        },
        source="migration", turn_no=0,
    )
    session.commit()
    return "c1"


@pytest.fixture()
def roller():
    from backend.engine.dice import DiceRoller

    return DiceRoller(seed=42)


def make_combatant(**overrides):
    """A level-3 fighter, unless you say otherwise."""
    from backend.engine.character import Combatant

    defaults = dict(
        id="test", name="Test", hp=20, max_hp=20, ac=14, level=3, proficiency_bonus=2,
        stats={"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
        proficiencies={"skills": ["Athletics"], "saves": ["STR"]},
        resources={"hit_dice": 3},
    )
    defaults.update(overrides)
    return Combatant(**defaults)
