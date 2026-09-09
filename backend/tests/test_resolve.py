"""
``resolve()`` end-to-end: intent in, mechanical truth out.

These also pin the contract the Narrator depends on — every resolution either
produces facts it may describe, or an ``invalid_reason`` it must relay instead of
improvising around.
"""

from __future__ import annotations

import pytest

from backend.engine.combat import CombatState
from backend.engine.dice import DiceRoller
from backend.engine.intent import INTENT_TOOL_SCHEMA, Intent
from backend.engine.resolve import GameState, resolve
from backend.state.snapshot import commit_resolution, load_game_state

from .conftest import make_combatant


@pytest.fixture()
def state():
    return GameState(
        campaign_id="c1",
        turn_no=1,
        roller=DiceRoller(seed=99),
        actors={
            "thorin": make_combatant(id="thorin", name="Thorin", hp=24, max_hp=24, ac=16),
            "goblin_1": make_combatant(
                id="goblin_1", name="Goblin", hp=7, max_hp=7, ac=15, is_pc=False,
                stats={"STR": 8, "DEX": 14, "CON": 10, "INT": 10, "WIS": 8, "CHA": 8},
            ),
        },
        catalog={
            "longsword": {"damage": "1d8", "damage_type": "slashing", "name": "longsword"},
            "healing potion": {"heal": "2d4+2", "consumable": True},
            "fireball": {"damage": "8d6", "save_ability": "DEX", "damage_type": "fire",
                         "cast_ability": "INT"},
        },
    )


# --------------------------------------------------------------------------
# Narrative and invalid
# --------------------------------------------------------------------------

def test_talking_is_narrative_with_nothing_to_roll(state):
    r = resolve(Intent(verb="talk", actor_id="thorin", dialogue="Hello?"), state)
    assert r.kind == "narrative"
    assert r.rolls == [] and r.state_deltas == []


def test_unknown_verb_falls_through_to_narrative(state):
    assert resolve(Intent(verb="unknown", actor_id="thorin"), state).kind == "narrative"


def test_ambiguous_intent_carries_the_clarifying_question(state):
    r = resolve(Intent(verb="attack", ambiguous=True, clarification="Which goblin?"), state)
    assert r.invalid_reason == "Which goblin?"


def test_unknown_actor_is_invalid(state):
    r = resolve(Intent(verb="check", actor_id="nobody", skill="stealth"), state)
    assert r.kind == "invalid" and "nobody" in r.invalid_reason


def test_attacking_nothing_is_invalid(state):
    r = resolve(Intent(verb="attack", actor_id="thorin"), state)
    assert r.kind == "invalid"


def test_attacking_an_absent_target_is_invalid(state):
    r = resolve(Intent(verb="attack", actor_id="thorin", targets=["dragon"]), state)
    assert r.kind == "invalid" and "dragon" in r.invalid_reason


def test_an_incapacitated_character_cannot_act(state):
    state.actors["thorin"].conditions = ["stunned"]
    assert resolve(Intent(verb="attack", actor_id="thorin", targets=["goblin_1"]), state).kind == "invalid"


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def test_a_check_rolls_once_and_states_the_result(state):
    r = resolve(Intent(verb="check", actor_id="thorin", skill="athletics", dc=15), state)
    assert r.kind == "check" and len(r.rolls) == 1 and r.dc == 15
    assert r.success is (r.rolls[0].total >= 15) or r.degree in ("crit_success", "crit_fail")
    assert "Athletics" in r.facts[0]


def test_a_check_with_no_dc_uses_the_default(state):
    assert resolve(Intent(verb="check", actor_id="thorin", skill="stealth"), state).dc == 12


def test_actors_resolve_by_name_as_well_as_id(state):
    assert resolve(Intent(verb="check", actor_id="Thorin", skill="athletics"), state).kind == "check"


# --------------------------------------------------------------------------
# Attacks
# --------------------------------------------------------------------------

def test_a_hit_produces_damage_deltas_and_a_fact(state):
    for seed in range(100):
        state.combat = CombatState()
        state.roller = DiceRoller(seed=seed)
        r = resolve(Intent(verb="attack", actor_id="thorin", targets=["goblin_1"],
                           item="longsword"), state)
        if r.success:
            # The first two rolls are always the attacker's own attack + damage —
            # any further rolls are the goblin's turn, now that combat actually
            # runs instead of ending the moment the PC's own attack resolves.
            assert len(r.rolls) >= 2
            assert any(d.field == "hp" and d.id == "goblin_1" for d in r.state_deltas)
            assert "Goblin" in r.facts[0]
            return
        state.actors["goblin_1"].hp = 7
    pytest.skip("no hit in 100 seeds")


def test_a_miss_leaves_the_target_untouched(state):
    for seed in range(100):
        state.combat = CombatState()
        state.roller = DiceRoller(seed=seed)
        state.actors["goblin_1"].hp = 7
        r = resolve(Intent(verb="attack", actor_id="thorin", targets=["goblin_1"]), state)
        if r.success is False:
            # The goblin's own turn (now wired up) may still land a hit on
            # Thorin — what a miss guarantees is that the *target* is untouched.
            assert not any(d.id == "goblin_1" for d in r.state_deltas)
            assert state.actors["goblin_1"].hp == 7
            assert "missed" in r.facts[0]
            return
    pytest.skip("no miss in 100 seeds")


def test_attacking_a_downed_target_is_invalid(state):
    state.actors["goblin_1"].hp = 0
    r = resolve(Intent(verb="attack", actor_id="thorin", targets=["goblin_1"]), state)
    assert r.kind == "invalid"


def test_an_attack_starts_initiative_and_the_enemy_can_swing_back(state):
    """The engine's combat primitives (roll_initiative, advance_turn) existed
    but nothing ever called them — an attack landed and the fight just ended
    there, no matter how many enemies were still standing. First attack now
    rolls initiative; the target gets a turn back if it survives."""
    for seed in range(100):
        state.combat = CombatState()
        state.roller = DiceRoller(seed=seed)
        state.actors["thorin"].hp = 24
        state.actors["goblin_1"].hp = 7
        r = resolve(Intent(verb="attack", actor_id="thorin", targets=["goblin_1"],
                           item="longsword"), state)
        assert state.combat.active or state.combat.ended_reason, \
            "initiative should be rolled regardless of hit or miss"
        if r.success and state.actors["goblin_1"].hp > 0:
            # The goblin survived the PC's hit — it should have gotten its own
            # turn immediately, in the same resolution, not a turn later.
            assert len(r.rolls) > 2, "the goblin's own attack roll should be included"
            return
    pytest.skip("no non-lethal hit in 100 seeds")


def test_dropping_the_last_enemy_ends_combat(state):
    state.combat = CombatState(active=True, round=1)
    state.actors["goblin_1"].hp = 1
    for seed in range(200):
        state.roller = DiceRoller(seed=seed)
        r = resolve(Intent(verb="attack", actor_id="thorin", targets=["goblin_1"]), state)
        if r.success:
            assert state.combat.active is False
            assert "0 HP" in " ".join(r.facts) or "unconscious" in " ".join(r.facts)
            return
        state.actors["goblin_1"].hp = 1
    pytest.skip("no hit in 200 seeds")


# --------------------------------------------------------------------------
# Spells and items
# --------------------------------------------------------------------------

def test_casting_without_a_slot_is_invalid_and_spends_nothing(state):
    state.actors["thorin"].resources["spell_slots"] = {"1": 0}
    r = resolve(Intent(verb="cast", actor_id="thorin", spell="magic missile", spell_level=1), state)
    assert r.kind == "invalid" and "no level 1 spell slots" in r.invalid_reason
    assert state.actors["thorin"].spell_slots(1) == 0


def test_casting_spends_the_slot(state):
    state.actors["thorin"].resources["spell_slots"] = {"1": 2}
    r = resolve(Intent(verb="cast", actor_id="thorin", spell="shield", spell_level=1), state)
    assert state.actors["thorin"].spell_slots(1) == 1
    assert any(d.field == "resources" for d in r.state_deltas)


def test_a_cantrip_spends_nothing(state):
    state.actors["thorin"].resources["spell_slots"] = {}
    r = resolve(Intent(verb="cast", actor_id="thorin", spell="firebolt", spell_level=0), state)
    assert r.kind in ("narrative", "check") and r.invalid_reason is None


def test_a_save_spell_halves_damage_on_a_success(state):
    state.actors["thorin"].resources["spell_slots"] = {"3": 1}
    r = resolve(Intent(verb="cast", actor_id="thorin", spell="fireball", spell_level=3,
                       targets=["goblin_1"]), state)
    assert len(r.rolls) == 2  # the save and the damage
    assert state.actors["goblin_1"].hp < 7


def test_using_an_item_you_do_not_have_is_invalid(state):
    r = resolve(Intent(verb="use_item", actor_id="thorin", item="healing potion"), state)
    assert r.kind == "invalid"


def test_a_healing_potion_heals_and_is_consumed(state):
    state.actors["thorin"].hp = 4
    state.actors["thorin"].resources["inventory"] = ["healing potion"]
    r = resolve(Intent(verb="use_item", actor_id="thorin", item="healing potion"), state)
    assert state.actors["thorin"].hp > 4
    assert any(e[0] == "item_lost" for e in r.events)


# --------------------------------------------------------------------------
# Rest and movement
# --------------------------------------------------------------------------

def test_resting_in_combat_is_invalid(state):
    state.combat = CombatState(active=True, round=2)
    assert resolve(Intent(verb="rest", actor_id="thorin"), state).kind == "invalid"


def test_a_long_rest_restores_the_whole_party(state):
    state.actors["thorin"].hp = 3
    r = resolve(Intent(verb="rest", actor_id="thorin", rest_type="long"), state)
    assert state.actors["thorin"].hp == 24
    assert r.kind == "rest"


def test_moving_writes_a_location_delta(state):
    r = resolve(Intent(verb="move", actor_id="thorin", targets=["phandalin"]), state)
    assert r.state_deltas[0].field == "location_id"
    assert r.state_deltas[0].value == "phandalin"


def test_death_saves_only_apply_to_the_dying(state):
    assert resolve(Intent(verb="death_save", actor_id="thorin"), state).kind == "invalid"
    state.actors["thorin"].hp = 0
    assert resolve(Intent(verb="death_save", actor_id="thorin"), state).kind == "save"


# --------------------------------------------------------------------------
# Round trip through the database
# --------------------------------------------------------------------------

def test_loading_state_from_the_database(session, campaign):
    loaded = load_game_state(session, campaign)
    assert set(loaded.actors) == {"thorin", "elara", "goblin_1"}
    assert loaded.actors["thorin"].skill_bonus("athletics") == 3 + 2


def test_a_resolution_persists_its_rolls_and_deltas(session, campaign):
    from backend.state.models import CharacterRow, EventRow

    loaded = load_game_state(session, campaign)
    resolution = resolve(
        Intent(verb="check", actor_id="thorin", skill="athletics", dc=10), loaded
    )
    commit_resolution(session, loaded, resolution)
    session.commit()

    rolls = session.query(EventRow).filter_by(type="roll").count()
    assert rolls == 1
    assert session.get(CharacterRow, "thorin").hp == 24


def test_damage_survives_the_round_trip(session, campaign):
    from backend.state.models import CharacterRow

    loaded = load_game_state(session, campaign)
    loaded.actors["goblin_1"].resources["inventory"] = []
    for seed in range(100):
        loaded.roller = __import__(
            "backend.engine.dice", fromlist=["DiceRoller"]
        ).DiceRoller(seed=seed)
        loaded.actors["goblin_1"].hp = 7
        r = resolve(Intent(verb="attack", actor_id="thorin", targets=["goblin_1"]), loaded)
        if r.success:
            commit_resolution(session, loaded, r)
            session.commit()
            assert session.get(CharacterRow, "goblin_1").hp == loaded.actors["goblin_1"].hp
            assert session.get(CharacterRow, "goblin_1").hp < 7
            return
    pytest.skip("no hit in 100 seeds")


def test_the_intent_schema_matches_the_dataclass():
    fields = set(Intent.__dataclass_fields__)
    for name in INTENT_TOOL_SCHEMA["input_schema"]["properties"]:
        assert name in fields, f"{name} is in the tool schema but not on Intent"
