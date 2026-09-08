"""
The play client's non-interactive parts.

Everything here runs without an API key: seeding, the inspection commands, and
the transcript export that turns a played session into a test fixture.
"""

from __future__ import annotations

import json

import pytest

from scripts import play

from .test_module import write_module
from .test_turn_loop import ScriptedClient


@pytest.fixture()
def module_path(tmp_path):
    return write_module(
        tmp_path / "hollow",
        {"id": "hollow", "name": "The Hollow", "current_state": {"location": "clearing"},
         "campaign_summary": "Something moved in the trees."},
        locations={"clearing": {"id": "clearing", "name": "The Clearing",
                                "description": "Ringed by black pines."}},
    )


@pytest.fixture()
def party(tmp_path):
    directory = tmp_path / "party"
    directory.mkdir()
    (directory / "bex.json").write_text(json.dumps({
        "name": "Bex", "class": "Fighter", "level": 1, "hp": 11, "max_hp": 11, "ac": 16,
        "abilities": {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 12, "cha": 10},
        "proficiencies": ["Athletics"], "save_proficiencies": ["str", "con"],
    }))
    return directory


def test_seeding_creates_the_campaign_once(db, module_path, party):
    ref = play.ensure_campaign(module_path, "hollow-1", party)
    assert ref  # the module path, recorded for next boot

    # Second call must not raise — it resumes rather than reseeding.
    again = play.ensure_campaign(module_path, "hollow-1", party)
    assert again == ref

    from backend.state.db import session_scope
    from backend.state.models import CharacterRow

    with session_scope() as session:
        assert session.query(CharacterRow).count() == 1


def test_seeding_warns_when_the_party_is_empty(db, module_path, tmp_path, capsys):
    empty = tmp_path / "nobody"
    empty.mkdir()
    play.ensure_campaign(module_path, "hollow-2", empty)
    assert "no PCs found" in capsys.readouterr().out


def test_inspection_commands_run_on_a_fresh_campaign(db, module_path, party, capsys):
    play.ensure_campaign(module_path, "hollow-1", party)

    play.show_state("hollow-1")
    play.show_rolls("hollow-1")
    play.show_canon("hollow-1")
    play.show_events("hollow-1")

    out = capsys.readouterr().out
    assert "Bex" in out and "11/11" in out
    assert "no rolls yet" in out
    assert "Something moved in the trees." in out
    assert "campaign_seeded" in out


def test_canon_search_filters(db, module_path, party, capsys):
    play.ensure_campaign(module_path, "hollow-1", party)
    play.show_canon("hollow-1", "trees")
    assert "moved in the trees" in capsys.readouterr().out


async def test_a_played_turn_exports_as_a_transcript_fixture(db, module_path, party, tmp_path):
    from backend.content.module import Module
    from backend.orchestrator.turn_loop import TurnLoop

    play.ensure_campaign(module_path, "hollow-1", party)
    client = ScriptedClient()
    loop = TurnLoop(client, Module.load(module_path))

    client.queue_tool("record_intent", {"verb": "check", "actor_id": "bex", "skill": "athletics"})
    client.queue_text("Bex hauls herself onto the branch.")
    client.queue_tool("record_changes", {"deltas": [], "facts": [
        {"text": "The lowest branch of the black pine bears weight."}], "summary": "Bex climbed."})

    await loop.take_turn("hollow-1", "I climb the nearest pine", defer_scribe=False)

    out = tmp_path / "fixture.json"
    play.export_transcript("hollow-1", out)

    fixture = json.loads(out.read_text())
    turn = next(t for t in fixture["turns"] if t["turn_no"] == 1)
    assert turn["player"] == "I climb the nearest pine"
    assert turn["narration"] == "Bex hauls herself onto the branch."
    assert turn["resolution"]["kind"] == "check"
    assert len(turn["rolls"]) == 1
    assert any("black pine" in f["text"] for f in fixture["canon_facts"])


async def test_rewind_from_the_client_restores_state(db, module_path, party, capsys):
    from backend.content.module import Module
    from backend.orchestrator.turn_loop import TurnLoop
    from backend.state.db import session_scope
    from backend.state.models import CharacterRow

    play.ensure_campaign(module_path, "hollow-1", party)
    client = ScriptedClient()
    loop = TurnLoop(client, Module.load(module_path))

    client.queue_tool("record_intent", {"verb": "look", "actor_id": "bex"})
    client.queue_text("Nothing yet.")
    client.queue_tool("record_changes", {"deltas": [], "facts": [], "summary": ""})
    await loop.take_turn("hollow-1", "look around", defer_scribe=False)

    with session_scope() as session:
        session.get(CharacterRow, "bex").hp = 3

    play.do_rewind("hollow-1", 0, loop)
    with session_scope() as session:
        assert session.get(CharacterRow, "bex").hp == 11
    assert "replayed" in capsys.readouterr().out


# --------------------------------------------------------------------------
# Per-agent model routing — the table has to describe the calls that happen
# --------------------------------------------------------------------------

def test_routing_sends_cheap_agents_to_cheap_models():
    from backend.orchestrator.budget import route_model

    assert route_model("narrator", "claude-sonnet-5") == "claude-sonnet-5"
    assert route_model("intent", "claude-sonnet-5") == "claude-haiku-4-5"
    assert route_model("architect", "claude-sonnet-5") == "claude-opus-5"


def test_routing_leaves_non_anthropic_providers_alone():
    from backend.orchestrator.budget import route_model

    assert route_model("intent", "phi3:mini") == "phi3:mini"
    assert route_model("architect", "gpt-4-turbo-preview") == "gpt-4-turbo-preview"


def test_routing_can_be_turned_off(monkeypatch):
    from backend.orchestrator.budget import route_model

    monkeypatch.setenv("AGENT_MODEL_ROUTING", "off")
    assert route_model("intent", "claude-sonnet-5") == "claude-sonnet-5"


async def test_agents_send_and_trace_the_model_they_actually_use(db):
    from backend.agents.intent import IntentAgent

    class Client(ScriptedClient):
        model = "claude-sonnet-5"

        async def create_message(self, messages, tools=None, system_prompt=None, **kwargs):
            self.used_model = kwargs.get("model")
            return await super().create_message(messages, tools, system_prompt, **kwargs)

    client = Client()
    client.queue_tool("record_intent", {"verb": "look"})
    agent = IntentAgent(client)

    assert agent.resolved_model == "claude-haiku-4-5"
    await agent.run(player_message="look around")
    assert client.used_model == "claude-haiku-4-5"

    from backend.orchestrator.trace import recent

    assert recent(1)[0].model == "claude-haiku-4-5"
