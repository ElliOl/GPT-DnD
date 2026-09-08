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


# --------------------------------------------------------------------------
# Is a played session actually usable as a phase 4 eval set?
# --------------------------------------------------------------------------

async def _play(loop, campaign_id, message, narration, *, intent=None, facts=None):
    client = loop.narrator.ai_client
    client.queue_tool("record_intent", intent or {"verb": "look", "actor_id": "bex"})
    client.queue_text(narration)
    client.queue_tool("record_changes",
                      {"deltas": [], "facts": facts or [], "summary": ""})
    return await loop.take_turn(campaign_id, message, defer_scribe=False)


@pytest.fixture()
async def played(db, module_path, party):
    """A short session with one labelled violation and one labelled non-violation."""
    from backend.content.module import Module
    from backend.orchestrator.turn_loop import TurnLoop, label_turn

    play.ensure_campaign(module_path, "hollow-1", party)
    loop = TurnLoop(ScriptedClient(), Module.load(module_path))

    await _play(loop, "hollow-1", "I ask the pines their name",
                "The trees say nothing.",
                facts=[{"text": "The clearing has exactly one exit, north."}])
    await _play(loop, "hollow-1", "I leave to the east",
                "You take the eastern path out of the clearing.")
    label_turn("hollow-1", 2, "violation", "canon says one exit, north", "hard")
    await _play(loop, "hollow-1", "I look for the exit again",
                "The northern gap is where it always was.")
    label_turn("hollow-1", 3, "ok", "sounded like a retcon, was consistent", "soft")
    return loop


async def test_an_export_carries_what_the_narrator_was_shown(played, tmp_path):
    out = tmp_path / "eval.json"
    play.export_transcript("hollow-1", out)
    fixture = json.loads(out.read_text())

    turn = next(t for t in fixture["turns"] if t["turn_no"] == 2)
    assert turn["context"] is not None, "an eval case must be reproducible"
    assert "retrieved_canon" in turn["context"]
    assert "Ringed by black pines" in turn["context"]["scene"]


async def test_an_export_carries_the_human_verdict(played, tmp_path):
    out = tmp_path / "eval.json"
    play.export_transcript("hollow-1", out)
    fixture = json.loads(out.read_text())

    assert fixture["counts"] == {"turns": 3, "labelled": 2, "violations": 1, "legitimate": 1}
    flagged = next(t for t in fixture["turns"] if t["turn_no"] == 2)
    assert flagged["label"]["verdict"] == "violation"
    assert flagged["label"]["severity"] == "hard"
    assert "one exit" in flagged["label"]["note"]

    # The negative case is the one the Auditor's false positives need.
    clean = next(t for t in fixture["turns"] if t["turn_no"] == 3)
    assert clean["label"]["verdict"] == "ok"


async def test_canon_at_turn_is_what_was_true_before_that_turn(played, tmp_path):
    out = tmp_path / "eval.json"
    play.export_transcript("hollow-1", out)
    fixture = json.loads(out.read_text())

    turn1 = next(t for t in fixture["turns"] if t["turn_no"] == 1)
    turn2 = next(t for t in fixture["turns"] if t["turn_no"] == 2)

    # The exits fact was established on turn 1, so it constrains turn 2, not turn 1.
    def has_exits(turn):
        return any("one exit" in f["text"] for f in turn["canon_at_turn"])

    assert not has_exits(turn1)
    assert has_exits(turn2)


async def test_superseded_facts_survive_the_export(db, module_path, party, tmp_path):
    from backend.state.canon import add_fact, contradict
    from backend.state.db import session_scope

    play.ensure_campaign(module_path, "hollow-1", party)
    with session_scope() as session:
        old = add_fact(session, "hollow-1", "The bridge is intact.", turn=1)
        new = add_fact(session, "hollow-1", "The bridge is burned.", turn=4)
        contradict(session, old.id, new.id)

    out = tmp_path / "eval.json"
    play.export_transcript("hollow-1", out)
    fixture = json.loads(out.read_text())

    texts = {f["text"]: f for f in fixture["canon_facts"]}
    assert "The bridge is intact." in texts, "a walked-back fact is the interesting case"
    assert texts["The bridge is intact."]["contradicted_by"] == texts["The bridge is burned."]["id"]


async def test_traces_ride_along_with_their_turn(played, tmp_path):
    out = tmp_path / "eval.json"
    play.export_transcript("hollow-1", out)
    fixture = json.loads(out.read_text())

    turn = next(t for t in fixture["turns"] if t["turn_no"] == 1)
    agents = {t["agent"] for t in turn["traces"]}
    assert {"intent", "narrator", "scribe"} <= agents
    narrator = next(t for t in turn["traces"] if t["agent"] == "narrator")
    assert "RESOLUTION" in narrator["prompt"]


async def test_an_unlabelled_session_says_it_is_not_an_auditor_set(
    db, module_path, party, tmp_path, capsys
):
    from backend.content.module import Module
    from backend.orchestrator.turn_loop import TurnLoop

    play.ensure_campaign(module_path, "hollow-1", party)
    loop = TurnLoop(ScriptedClient(), Module.load(module_path))
    await _play(loop, "hollow-1", "look", "Quiet.")

    play.export_transcript("hollow-1", tmp_path / "eval.json")
    out = capsys.readouterr().out
    assert "not yet an" in out and "Auditor" in out


def test_labelling_before_anything_is_played_says_so(db, module_path, party, capsys):
    play.ensure_campaign(module_path, "hollow-1", party)
    play.do_label("hollow-1", "violation", "nope")
    assert "nothing played yet" in capsys.readouterr().out


async def test_the_label_count_tracks_progress(played, capsys):
    play.show_labels("hollow-1")
    out = capsys.readouterr().out
    assert "2 labelled (1 violations, 1 legitimate)" in out
    assert "about 50" in out


def test_a_bad_verdict_is_refused(db, module_path, party):
    from backend.orchestrator.turn_loop import label_turn

    play.ensure_campaign(module_path, "hollow-1", party)
    with pytest.raises(ValueError, match="violation"):
        label_turn("hollow-1", 1, "meh")


async def test_labelling_an_earlier_turn_by_number(played, tmp_path):
    play.do_label("hollow-1", "violation", "1 the trees were described wrong", "soft")
    play.export_transcript("hollow-1", tmp_path / "eval.json")
    fixture = json.loads((tmp_path / "eval.json").read_text())

    turn1 = next(t for t in fixture["turns"] if t["turn_no"] == 1)
    assert turn1["label"]["verdict"] == "violation"
    assert turn1["label"]["note"] == "the trees were described wrong"


async def test_relabelling_a_turn_replaces_the_verdict(played, tmp_path):
    play.do_label("hollow-1", "ok", "2 on reflection this was fine", "soft")
    play.export_transcript("hollow-1", tmp_path / "eval.json")
    fixture = json.loads((tmp_path / "eval.json").read_text())

    turn2 = next(t for t in fixture["turns"] if t["turn_no"] == 2)
    assert turn2["label"]["verdict"] == "ok"
    assert fixture["counts"]["violations"] == 0


async def test_labelling_a_turn_that_has_not_happened(played, capsys):
    play.do_label("hollow-1", "violation", "99 way ahead of myself")
    assert "hasn't been played" in capsys.readouterr().out
