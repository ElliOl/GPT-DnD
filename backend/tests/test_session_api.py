"""
The session endpoint: create a campaign from any module, then play it.

Proves the runtime is genuinely module-agnostic at the HTTP boundary — the
module here is invented in the test's tmp dir and the API has never seen it.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import session as session_router

from .test_module import write_module
from .test_turn_loop import ScriptedClient


@pytest.fixture()
def api(db, monkeypatch):
    client = ScriptedClient()
    monkeypatch.setattr(session_router, "_ai_client", lambda: client)
    session_router._loops.clear()
    app = FastAPI()
    app.include_router(session_router.router)
    return TestClient(app), client


@pytest.fixture()
def barrow(tmp_path):
    return write_module(
        tmp_path / "the_barrow",
        {"id": "the_barrow", "name": "The Barrow",
         "current_state": {"location": "mound"},
         "campaign_summary": "A cold wind off the moor."},
        locations={"mound": {"id": "mound", "name": "The Mound",
                             "description": "A green swell in the heather."}},
        npcs={"digger": {"id": "digger", "name": "Old Digger"}},
    )


@pytest.fixture()
def party(tmp_path):
    directory = tmp_path / "party"
    directory.mkdir()
    (directory / "mab.json").write_text(json.dumps({
        "name": "Mab", "class": "Rogue", "level": 2, "hp": 13, "max_hp": 13, "ac": 14,
        "abilities": {"str": 10, "dex": 17, "con": 12, "int": 12, "wis": 11, "cha": 14},
        "proficiencies": ["Stealth"], "save_proficiencies": ["dex"],
    }))
    return str(directory)


def test_creating_a_campaign_from_an_unseen_module(api, barrow, party):
    client, _ = api
    response = client.post("/api/session", json={
        "module": barrow, "campaign_id": "barrow-1", "party_dir": party})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["module"] == "the_barrow"
    assert body["seeded"]["characters"] == 1


def test_creating_the_same_campaign_twice_conflicts(api, barrow, party):
    client, _ = api
    client.post("/api/session", json={"module": barrow, "campaign_id": "b", "party_dir": party})
    again = client.post("/api/session", json={"module": barrow, "campaign_id": "b",
                                              "party_dir": party})
    assert again.status_code == 409


def test_creating_from_a_module_that_does_not_exist(api, party):
    client, _ = api
    response = client.post("/api/session", json={"module": "not_a_module", "party_dir": party})
    assert response.status_code == 400
    assert "Looked in" in response.json()["detail"]


def test_playing_a_turn_through_the_api(api, barrow, party):
    client, scripted = api
    client.post("/api/session", json={"module": barrow, "campaign_id": "barrow-1",
                                      "party_dir": party})

    scripted.queue_tool("record_intent", {"verb": "check", "actor_id": "mab", "skill": "stealth"})
    scripted.queue_text("Mab melts into the heather.")
    scripted.queue_tool("record_changes", {"deltas": [], "facts": [], "summary": "Mab hid."})

    response = client.post("/api/session/barrow-1/action", json={"message": "I sneak up the mound"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["narration"] == "Mab melts into the heather."
    assert body["resolution"]["kind"] == "check"
    assert len(body["rolls"]) == 1
    assert body["turn_no"] == 1
    # The module's own scene text reached the Narrator.
    assert "green swell" in scripted.calls[1]["content"]


def test_an_empty_message_is_rejected(api, barrow, party):
    client, _ = api
    client.post("/api/session", json={"module": barrow, "campaign_id": "barrow-1",
                                      "party_dir": party})
    assert client.post("/api/session/barrow-1/action", json={"message": "  "}).status_code == 400


def test_playing_a_campaign_that_does_not_exist(api):
    client, _ = api
    response = client.post("/api/session/ghost/action", json={"message": "hello"})
    assert response.status_code == 404


def test_listing_modules_reports_validity(api, barrow):
    client, _ = api
    listed = client.get("/api/session/modules").json()
    assert all("valid" in m for m in listed)
    assert any(m["id"] == "lost_mines_of_phandelver" for m in listed)
