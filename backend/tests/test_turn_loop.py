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
    from backend.state.models import CharacterRow, LocationRow, NPCRow

    session.add(
        LocationRow(id="antechamber", campaign_id="c1", name="Antechamber",
                    discovered=True, visited=True)
    )
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


@pytest.mark.asyncio
async def test_default_actor_mid_combat_is_whoever_is_up_not_alphabetical(loop, campaign, session):
    """A real bug from actual play: "attack the goblin" with no name given
    defaulted to whichever PC's id sorted first alphabetically (Elara) even
    though it was unambiguously Thorin's turn — Elara was unconscious and
    couldn't act at all. The default should track initiative, not the
    alphabet."""
    from backend.state.events import record_event
    from backend.engine.combat import CombatState, Initiative

    combat = CombatState(
        active=True, round=1, turn_index=0,
        order=[
            Initiative(combatant_id="thorin", name="Thorin", score=18, dex=14, is_pc=True),
            Initiative(combatant_id="elara", name="Elara", score=10, dex=12, is_pc=True),
        ],
    )
    record_event(session, "c1", "combat_state", {"combat": combat.to_dict()}, source="engine", turn_no=1)
    session.commit()

    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "attack", "targets": ["goblin_1"]})  # no actor_id
    client.queue_text("Thorin swings.")

    result = await loop.take_turn(campaign, "attack the goblin", defer_scribe=False)
    assert result.intent["actor_id"] == "thorin"


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


# --------------------------------------------------------------------------
# Anyone present is a valid target, not just the party
# --------------------------------------------------------------------------

def test_new_hostiles_extraction_is_parsed():
    extraction = parse_extraction(
        {"new_hostiles": [{"name": "a goblin", "kind": "goblin"}, {"bad": "entry"}]}
    )
    assert extraction.new_hostiles == [{"name": "a goblin", "kind": "goblin"}]


@pytest.mark.asyncio
async def test_attacking_a_present_npc_that_was_never_statted_works(loop, campaign, session):
    """The Warden fixture is a bare NPCRow — name and attitude, no HP or AC.
    Attacking it should work exactly like attacking the pre-statted goblin."""
    from backend.state.models import CharacterRow, NPCRow

    client = client_of(loop)
    client.queue_tool("record_intent", {
        "verb": "attack", "actor_id": "thorin", "targets": ["warden"],
    })
    client.queue_text("Thorin's blade meets the Warden.")

    result = await loop.take_turn(campaign, "I attack the Warden", defer_scribe=False)

    assert result.resolution is not None
    assert result.resolution["kind"] == "attack"
    session.expire_all()
    warden = session.get(NPCRow, "warden")
    assert warden.character_id is not None
    backing = session.get(CharacterRow, warden.character_id)
    assert backing is not None and backing.is_pc is False and backing.max_hp > 0

    # Initiative is rolled unconditionally before the attack outcome is known
    # (whether it hits or misses), so a real fight — not just an isolated
    # attack roll — is now under way regardless of this roll's result.
    from backend.state.models import EventRow

    combat_events = [e for e in session.query(EventRow).all() if e.type == "combat_state"]
    assert combat_events, "attacking someone should start real initiative-tracked combat"


@pytest.mark.asyncio
async def test_an_ally_present_at_the_fight_does_not_attack_the_party(loop, campaign, session):
    """A real bug caught in actual play: an ally standing in the same room as
    a fight got swept into initiative and attacked a PC, just for being a
    non-PC combatant. Attitude, not is_pc, decides who's on which side."""
    from backend.state.models import NPCRow

    session.add(NPCRow(id="ally", campaign_id="c1", name="A Friendly Guard",
                        status="alive", location_id="antechamber", attitude_to_party=2))
    session.commit()

    client = client_of(loop)
    client.queue_tool("record_intent", {
        "verb": "attack", "actor_id": "thorin", "targets": ["warden"],
    })
    client.queue_text("Thorin's blade meets the Warden.")
    await loop.take_turn(campaign, "I attack the Warden", defer_scribe=False)

    session.expire_all()
    from backend.state.models import EventRow

    combat_payloads = [
        e.payload["combat"] for e in session.query(EventRow).all() if e.type == "combat_state"
    ]
    assert combat_payloads, "combat should have started"
    combatant_ids = {entry["combatant_id"] for entry in combat_payloads[-1]["order"]}
    assert "ally" not in combatant_ids, "an ally in the room should not join a fight it wasn't targeted in"


@pytest.mark.asyncio
async def test_intent_agent_is_told_roster_hp_to_resolve_descriptive_targets(loop, campaign, session):
    """"Attack the injured goblin" was unresolvable — the Intent agent only
    ever saw names, never HP, so it had no way to know which one that meant
    and asked every single time. It needs the numbers, not just the roster."""
    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "attack", "actor_id": "thorin", "targets": ["warden"]})
    client.queue_text("Thorin's blade meets the Warden.")
    await loop.take_turn(campaign, "I attack the Warden", defer_scribe=False)

    client.queue_tool("record_intent", {"verb": "look", "actor_id": "thorin"})
    client.queue_text("The room is quiet.")
    await loop.take_turn(campaign, "I look around", defer_scribe=False)

    second_turn_intent_call = client.calls[3]
    assert "warden" in second_turn_intent_call["content"]
    assert "HP" in second_turn_intent_call["content"]


@pytest.mark.asyncio
async def test_a_dm_introduced_hostile_becomes_attackable_next_turn(loop, campaign, session):
    """Turn 1: the DM narrates a goblin the module never named. The Scribe
    notices. Turn 2: attacking "the goblin" resolves instead of looping on
    who the player means — the whole point of the fix."""
    from backend.state.models import NPCRow

    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "narrate", "actor_id": "thorin"})
    client.queue_text("A goblin lurches out from behind the altar, blade raised.")
    client.queue_tool("record_changes", {
        "deltas": [], "facts": [],
        "new_hostiles": [{"name": "a goblin", "kind": "goblin"}],
        "summary": "A goblin appeared.",
    })
    await loop.take_turn(campaign, "we push into the antechamber", defer_scribe=False)

    session.expire_all()
    spawned = [n for n in session.query(NPCRow).all() if n.name == "a goblin"]
    assert len(spawned) == 1
    goblin_id = spawned[0].id

    client.queue_tool("record_intent", {
        "verb": "attack", "actor_id": "thorin", "targets": [goblin_id],
    })
    client.queue_text("Thorin cuts the goblin down.")
    result = await loop.take_turn(campaign, "I attack the goblin", defer_scribe=False)

    assert result.needs_clarification is False
    assert result.resolution is not None
    assert result.resolution["kind"] == "attack"


@pytest.mark.asyncio
async def test_a_dm_described_place_becomes_a_real_nested_location(loop, campaign, session):
    """The module never authored a "hidden passage" off the antechamber. The
    Scribe notices it anyway, and it becomes a real location a later turn can
    move a character onto — the whole point being the module's map is
    reference material, not a hard boundary on where the story can go."""
    from backend.state.models import LocationRow

    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "narrate", "actor_id": "thorin"})
    client.queue_text("Behind a loose stone, a hidden passage slopes downward.")
    client.queue_tool("record_changes", {
        "deltas": [], "facts": [],
        "new_locations": [{"name": "Hidden Passage", "connects_to": "antechamber"}],
        "summary": "A hidden passage was found.",
    })
    await loop.take_turn(campaign, "I search the wall for secret doors", defer_scribe=False)

    session.expire_all()
    passage = session.query(LocationRow).filter_by(name="Hidden Passage").one()
    assert passage.parent_id == "antechamber"
    assert passage.discovered is True and passage.visited is True
    assert "antechamber" in passage.exits

    antechamber = session.get(LocationRow, "antechamber")
    assert passage.id in antechamber.exits, "the link goes both ways"

    # A later turn can now legitimately move a PC onto it.
    client.queue_tool("record_intent", {"verb": "move", "actor_id": "thorin",
                                        "targets": [passage.id]})
    result = await loop.take_turn(campaign, "Thorin heads down the passage", defer_scribe=False)
    assert result.resolution is not None
    assert result.resolution["kind"] == "narrative"


@pytest.mark.asyncio
async def test_scribe_cannot_move_a_character_to_a_place_that_does_not_exist(loop, campaign, session):
    """Without a matching new_locations entry, an invented location name in a
    plain delta is rejected — this is the bug that let two PCs silently drift
    to different, nonexistent rooms in actual play."""
    from backend.state.models import CharacterRow, EventRow

    client = client_of(loop)
    client.queue_tool("record_intent", {"verb": "talk", "actor_id": "thorin"})
    client.queue_text("Thorin wanders off.")
    client.queue_tool("record_changes", {
        "deltas": [{"target": "character", "id": "thorin", "op": "set",
                    "field": "location_id", "value": "some_room_the_scribe_invented"}],
        "facts": [], "summary": "",
    })

    await loop.take_turn(campaign, "Thorin looks around", defer_scribe=False)

    session.expire_all()
    assert session.get(CharacterRow, "thorin").location_id == "antechamber", \
        "the bogus location must not have been applied"
    violations = [e for e in session.query(EventRow).all() if e.type == "audit_violation"]
    assert any("does not exist" in str(e.payload) for e in violations)
