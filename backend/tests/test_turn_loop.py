"""
Phase 3 end to end: intent -> resolve -> narrate -> scribe.

The AI client is scripted, so these test the *loop*, not the model: what happens
when the Intent agent is confident, ambiguous, wrong, or down; whether the
Scribe's proposals are gated; whether the whole thing degrades instead of
failing.
"""

from __future__ import annotations

import json

import pytest

from backend.agents.scribe import Extraction, parse_extraction, reconcile, strip_footer
from backend.orchestrator.turn_loop import TurnLoop
from backend.services.ai_client_base import AIResponse, BaseAIClient, ToolCall
from backend.state.events import Delta


class ScriptedClient(BaseAIClient):
    """Returns queued responses in order, recording what it was asked."""

    def __init__(self, script: list[AIResponse] | None = None):
        super().__init__()
        self.script = list(script or [])
        self.calls: list[dict] = []

    def queue_tool(self, name: str, params: dict) -> "ScriptedClient":
        self.script.append(
            AIResponse(
                tool_calls=[ToolCall(id="t", name=name, parameters=params)],
                finish_reason="tool_calls",
                usage={"input_tokens": 100, "output_tokens": 20},
            )
        )
        return self

    def queue_text(self, text: str) -> "ScriptedClient":
        self.script.append(
            AIResponse(
                text=text, finish_reason="stop",
                usage={"input_tokens": 800, "output_tokens": 120},
            )
        )
        return self

    async def create_message(self, messages, tools=None, system_prompt=None, **kwargs):
        self.calls.append(
            {
                "system": system_prompt or "",
                "content": messages[0].content if messages else "",
                "tools": [t.name for t in (tools or [])],
            }
        )
        if not self.script:
            return AIResponse(text="…", finish_reason="stop", usage={})
        return self.script.pop(0)

    async def stream_message(self, messages, system_prompt=None, **kwargs):  # pragma: no cover
        yield ""


@pytest.fixture()
def module(tmp_path):
    """A tiny module, unrelated to anything shipped."""
    from .test_module import write_module
    from backend.content.module import Module

    path = write_module(
        tmp_path / "tomb",
        {"id": "tomb", "name": "The Tomb", "current_state": {"location": "antechamber"}},
        locations={
            "antechamber": {
                "id": "antechamber", "name": "Antechamber",
                "description": "Dust, a cracked altar, three dark doorways.",
            }
        },
        items={
            "shortsword": {"id": "shortsword", "name": "Shortsword", "damage": "1d6",
                           "damage_type": "piercing", "finesse": True}
        },
    )
    return Module.load(path)


@pytest.fixture()
def loop(module, campaign, session):
    """A loop over the seeded test campaign, with the party in the antechamber."""
    from backend.state.models import CharacterRow, NPCRow

    for row in session.query(CharacterRow).all():
        row.location_id = "antechamber"
    session.add(
        NPCRow(id="warden", campaign_id="c1", name="The Warden", status="alive",
               location_id="antechamber", attitude_to_party=-2, importance=3)
    )
    session.commit()
    return TurnLoop(ScriptedClient(), module)


def client_of(loop: TurnLoop) -> ScriptedClient:
    return loop.narrator.ai_client  # type: ignore[return-value]


# --------------------------------------------------------------------------
# The happy path
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_check_turn_rolls_narrates_and_logs(loop, campaign, session):
    from backend.state.models import EventRow

    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "check", "actor_id": "thorin",
                                        "skill": "athletics"})
    client.queue_text("Thorin heaves at the slab; it grinds aside.")
    client.queue_tool("record_changes", {"deltas": [], "facts": [], "summary": "Slab moved."})

    result = await loop.take_turn(campaign, "I try to shove the slab aside", defer_scribe=False)

    assert result.turn_no == 1
    assert result.narration.startswith("Thorin heaves")
    assert result.resolution["kind"] == "check"
    assert len(result.rolls) == 1

    session.expire_all()
    types = [e.type for e in session.query(EventRow).all()]
    assert "player_input" in types and "narration" in types
    assert "roll" in types and "resolution" in types


@pytest.mark.asyncio
async def test_the_narrator_is_told_the_engines_result_not_asked_for_one(loop, campaign):
    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "check", "actor_id": "thorin", "skill": "athletics"})
    client.queue_text("It gives way.")
    client.queue_tool("record_changes", {"deltas": [], "facts": [], "summary": ""})

    await loop.take_turn(campaign, "shove the slab", defer_scribe=False)

    narrator_call = client.calls[1]
    assert "RESOLUTION" in narrator_call["content"]
    assert "Athletics check" in narrator_call["content"]
    assert "cannot alter a number" in narrator_call["system"] or \
           "already final" in narrator_call["system"]


@pytest.mark.asyncio
async def test_the_packet_carries_the_scene_and_who_is_present(loop, campaign):
    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "look", "actor_id": "thorin"})
    client.queue_text("Dust hangs in the air.")

    await loop.take_turn(campaign, "look around", defer_scribe=False)

    content = client.calls[1]["content"]
    assert "cracked altar" in content         # scene, from the module
    assert "The Warden" in content            # present NPC
    assert "Thorin" in content                # party line with HP


@pytest.mark.asyncio
async def test_a_narrative_verb_skips_the_engine_entirely(loop, campaign):
    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "talk", "actor_id": "thorin",
                                        "dialogue": "Who guards this place?"})
    client.queue_text('"I do," says the Warden.')

    result = await loop.take_turn(campaign, 'I say "Who guards this place?"', defer_scribe=False)
    assert result.resolution is None and result.rolls == []


# --------------------------------------------------------------------------
# Ambiguity
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_an_ambiguous_intent_ends_the_turn_with_a_question(loop, campaign):
    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "attack", "ambiguous": True,
                                        "clarification": "Which of the three doors?"})

    result = await loop.take_turn(campaign, "I go through the door", defer_scribe=False)

    assert result.needs_clarification is True
    assert result.narration == "Which of the three doors?"
    assert result.resolution is None
    assert len(client.calls) == 1, "no Narrator call, no Scribe call — the turn stopped"


@pytest.mark.asyncio
async def test_a_target_that_is_not_present_becomes_a_question(loop, campaign):
    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "attack", "actor_id": "thorin",
                                        "targets": ["ancient_dragon"]})

    result = await loop.take_turn(campaign, "I attack the dragon", defer_scribe=False)
    assert result.needs_clarification is True
    assert "ancient_dragon" in result.narration


@pytest.mark.asyncio
async def test_an_unknown_actor_falls_back_to_the_party(loop, campaign):
    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "check", "actor_id": "gandalf",
                                        "skill": "perception"})
    client.queue_text("You see nothing.")

    result = await loop.take_turn(campaign, "I look for tracks", defer_scribe=False)
    assert result.intent["actor_id"] in ("elara", "goblin_1", "thorin")
    assert result.resolution["kind"] == "check"


# --------------------------------------------------------------------------
# Degradation
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_failing_intent_agent_falls_back_to_keywords(loop, campaign):
    client = client_of(loop)
    client.script.append(AIResponse(text="I'm not sure!", finish_reason="stop", usage={}))
    client.script.append(AIResponse(text="I'm still not sure!", finish_reason="stop", usage={}))
    client.queue_text("Thorin swings.")

    result = await loop.take_turn(campaign, "I attack the goblin", defer_scribe=False)
    assert result.intent["verb"] == "attack"        # the keyword parser caught it
    assert result.narration == "Thorin swings."


@pytest.mark.asyncio
async def test_the_turn_survives_the_scribe_failing(loop, campaign):
    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "look", "actor_id": "thorin"})
    client.queue_text("The dust settles.")
    client.script.append(AIResponse(text="not json", finish_reason="stop", usage={}))
    client.script.append(AIResponse(text="still not json", finish_reason="stop", usage={}))

    result = await loop.take_turn(campaign, "look around", defer_scribe=False)
    assert result.narration == "The dust settles."


@pytest.mark.asyncio
async def test_a_spent_budget_drops_the_scribe_but_not_the_narrator(loop, campaign):
    client = client_of(loop)
    loop.budget_for(campaign).spent_usd = 0.99  # effectively exhausted
    client.queue_tool("record_intent", {"verb": "look", "actor_id": "thorin"})
    client.queue_text("Nothing stirs.")

    result = await loop.take_turn(campaign, "look around", defer_scribe=False)
    assert result.narration == "Nothing stirs."
    assert "scribe" in result.budget["dropped"]


# --------------------------------------------------------------------------
# The Scribe, and the wall in front of it
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scribe_deltas_are_applied_when_they_are_allowed(loop, campaign, session):
    from backend.state.models import NPCRow

    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "talk", "actor_id": "thorin"})
    client.queue_text("The Warden's jaw unclenches.")
    client.queue_tool("record_changes", {
        "deltas": [{"target": "npc", "id": "warden", "op": "inc",
                    "field": "attitude_to_party", "value": 2}],
        "facts": [{"text": "The Warden accepted Thorin's oath.", "entities": ["warden"]}],
        "summary": "Thorin swore an oath.",
    })

    await loop.take_turn(campaign, "I swear an oath to the Warden", defer_scribe=False)

    session.expire_all()
    assert session.get(NPCRow, "warden").attitude_to_party == 0  # -2 + 2


@pytest.mark.asyncio
async def test_a_hallucinated_hp_delta_is_refused_and_logged(loop, campaign, session):
    from backend.state.models import CharacterRow, EventRow

    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "look", "actor_id": "thorin"})
    client.queue_text("A chest gapes open.")
    client.queue_tool("record_changes", {
        "deltas": [{"target": "character", "id": "thorin", "op": "set", "field": "hp", "value": 999},
                   {"target": "location", "id": "cragmaw_hideout", "op": "set",
                    "field": "discovered", "value": True}],
        "facts": [], "summary": "",
    })

    await loop.take_turn(campaign, "I open the chest", defer_scribe=False)

    session.expire_all()
    assert session.get(CharacterRow, "thorin").hp == 24, "hp must not move on the Scribe's say-so"
    violations = session.query(EventRow).filter_by(type="audit_violation").all()
    assert violations, "the refusal is logged, not silent"


@pytest.mark.asyncio
async def test_scribe_facts_become_canon(loop, campaign, session):
    from backend.state.canon import facts_about

    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "talk", "actor_id": "thorin"})
    client.queue_text("She gives her name as Vess.")
    client.queue_tool("record_changes", {
        "deltas": [],
        "facts": [{"text": "The Warden's name is Vess.", "entities": ["warden"]}],
        "summary": "Names exchanged.",
    })

    await loop.take_turn(campaign, "I ask her name", defer_scribe=False)

    session.expire_all()
    assert any("Vess" in f.text for f in facts_about(session, campaign, ["warden"]))


@pytest.mark.asyncio
async def test_the_narrators_hidden_footer_is_stripped_and_used(loop, campaign, session):
    from backend.state.models import EventRow, LocationRow

    session.add(LocationRow(id="antechamber", campaign_id=campaign, name="Antechamber"))
    session.commit()

    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "look", "actor_id": "thorin"})
    client.queue_text(
        "The far door swings inward.\n"
        '<state_delta>{"deltas": [{"target": "location", "id": "antechamber", '
        '"op": "set", "field": "visited", "value": true}], "facts": [], '
        '"summary": "A door opened."}</state_delta>'
    )
    client.queue_tool("record_changes", {"deltas": [], "facts": [], "summary": ""})

    result = await loop.take_turn(campaign, "I push the door", defer_scribe=False)

    assert "<state_delta>" not in result.narration
    assert result.narration == "The far door swings inward."
    session.expire_all()
    assert session.get(LocationRow, "antechamber").visited is True
    # The two extractors disagreed (only the Narrator saw it) — logged for tuning.
    assert session.query(EventRow).filter_by(type="audit_violation").count() >= 1


@pytest.mark.asyncio
async def test_the_scribe_is_deferred_by_default(loop, campaign):
    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "look", "actor_id": "thorin"})
    client.queue_text("Quiet.")
    client.queue_tool("record_changes", {"deltas": [], "facts": [], "summary": "quiet"})

    result = await loop.take_turn(campaign, "look")
    assert result.scribe_task is not None
    await result.scribe_task  # the player never waits on this


# --------------------------------------------------------------------------
# Footer parsing and reconciliation, in isolation
# --------------------------------------------------------------------------

def test_prose_without_a_footer_is_untouched():
    text, extraction = strip_footer("Just prose.")
    assert text == "Just prose." and extraction.deltas == []


def test_a_malformed_footer_costs_the_crosscheck_not_the_turn():
    text, extraction = strip_footer("Prose.\n<state_delta>{broken</state_delta>")
    assert text == "Prose." and extraction.deltas == []


def test_reconcile_dedupes_agreed_deltas():
    d = {"target": "npc", "id": "x", "op": "inc", "field": "attitude_to_party", "value": 1}
    merged, _, disagreements = reconcile(
        parse_extraction({"deltas": [d]}), parse_extraction({"deltas": [d]})
    )
    assert len(merged) == 1 and disagreements == []


def test_reconcile_reports_what_only_one_extractor_saw():
    merged, _, disagreements = reconcile(
        parse_extraction({"deltas": [{"target": "npc", "id": "x", "op": "set",
                                      "field": "status", "value": "fled"}]}),
        Extraction(),
    )
    assert len(merged) == 1
    assert "only narrator saw" in disagreements[0]


def test_reconcile_dedupes_facts_case_insensitively():
    _, facts, _ = reconcile(
        parse_extraction({"facts": [{"text": "The door is open."}]}),
        parse_extraction({"facts": [{"text": "the door is open."}]}),
    )
    assert len(facts) == 1


def test_malformed_delta_entries_are_dropped_not_fatal():
    extraction = parse_extraction({"deltas": [{"nonsense": True}, {
        "target": "npc", "id": "x", "op": "set", "field": "status", "value": "fled"}]})
    assert len(extraction.deltas) == 1
