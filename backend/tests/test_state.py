"""
State layer: delta validation, reducers, and rewind.

The rewind tests are the important ones — event sourcing that can't actually
replay is just a log with extra steps.
"""

from __future__ import annotations

import pytest

from backend.state.canon import add_fact, all_facts, facts_about, relevant_facts
from backend.state.events import (
    Delta,
    DeltaRejected,
    EventType,
    apply_delta,
    record_event,
    replay_to,
    validate_delta,
)
from backend.state.models import CharacterRow, ClockRow, EventRow, InventoryRow


# --------------------------------------------------------------------------
# Delta validation — the wall between the Scribe and the numbers
# --------------------------------------------------------------------------

def test_unknown_target_is_rejected():
    with pytest.raises(DeltaRejected):
        validate_delta(Delta("wallet", "x", "set", "gold", 500), "engine")


def test_unwritable_field_is_rejected():
    with pytest.raises(DeltaRejected):
        validate_delta(Delta("character", "thorin", "set", "name", "Steve"), "engine")


def test_scribe_cannot_touch_hp_without_authorization():
    with pytest.raises(DeltaRejected, match="requires engine authorization"):
        validate_delta(Delta("character", "thorin", "inc", "hp", 500), "scribe")


def test_scribe_may_move_a_character():
    validate_delta(Delta("character", "thorin", "set", "location_id", "phandalin"), "scribe")


def test_engine_may_touch_hp():
    validate_delta(Delta("character", "thorin", "inc", "hp", -5), "engine")


def test_an_authorizing_event_lets_a_guarded_delta_through():
    validate_delta(Delta("character", "t", "inc", "hp", -5, authorized_by=17), "scribe")


def test_inc_requires_a_number():
    with pytest.raises(DeltaRejected):
        validate_delta(Delta("character", "t", "inc", "hp", "lots"), "engine")


# --------------------------------------------------------------------------
# Applying deltas
# --------------------------------------------------------------------------

def test_hp_is_clamped_to_zero_and_max(session, campaign):
    apply_delta(session, Delta("character", "thorin", "inc", "hp", -1000))
    assert session.get(CharacterRow, "thorin").hp == 0
    apply_delta(session, Delta("character", "thorin", "inc", "hp", 1000))
    assert session.get(CharacterRow, "thorin").hp == 24


def test_clock_is_clamped_to_its_size(session, campaign):
    apply_delta(session, Delta("clock", "redbrand_pressure", "inc", "filled", 99))
    assert session.get(ClockRow, "redbrand_pressure").filled == 6


def test_attitude_is_clamped_to_the_scale(session, campaign):
    from backend.state.models import NPCRow

    apply_delta(session, Delta("npc", "sildar", "inc", "attitude_to_party", 99))
    assert session.get(NPCRow, "sildar").attitude_to_party == 5


def test_append_and_remove_on_a_list_field(session, campaign):
    apply_delta(session, Delta("character", "thorin", "append", "conditions", "poisoned"))
    apply_delta(session, Delta("character", "thorin", "append", "conditions", "poisoned"))
    assert session.get(CharacterRow, "thorin").conditions == ["poisoned"]
    apply_delta(session, Delta("character", "thorin", "remove", "conditions", "poisoned"))
    assert session.get(CharacterRow, "thorin").conditions == []


def test_delta_against_a_missing_row_is_rejected(session, campaign):
    with pytest.raises(DeltaRejected):
        apply_delta(session, Delta("character", "nobody", "set", "hp", 1))


# --------------------------------------------------------------------------
# Events and reducers
# --------------------------------------------------------------------------

def test_seeding_populated_every_table(session, campaign):
    assert session.query(CharacterRow).count() == 3
    assert session.query(ClockRow).count() == 1
    assert all_facts(session, campaign)


def test_recording_an_event_applies_its_deltas(session, campaign):
    record_event(
        session, campaign, EventType.DAMAGE, {"target": "goblin_1", "amount": 5},
        deltas=[Delta("character", "goblin_1", "inc", "hp", -5)],
    )
    assert session.get(CharacterRow, "goblin_1").hp == 2


def test_engine_deltas_are_stamped_with_their_authorizing_event(session, campaign):
    event = record_event(
        session, campaign, EventType.DAMAGE, {},
        deltas=[Delta("character", "goblin_1", "inc", "hp", -1)],
    )
    assert event.payload["deltas"][0]["authorized_by"] == event.id


def test_item_gained_then_lost(session, campaign):
    record_event(session, campaign, EventType.ITEM_GAINED,
                 {"character_id": "thorin", "item_id": "rope", "qty": 2})
    assert session.query(InventoryRow).filter_by(character_id="thorin").one().qty == 2

    record_event(session, campaign, EventType.ITEM_GAINED,
                 {"character_id": "thorin", "item_id": "rope", "qty": 1})
    assert session.query(InventoryRow).filter_by(character_id="thorin").one().qty == 3

    record_event(session, campaign, EventType.ITEM_LOST,
                 {"character_id": "thorin", "item_id": "rope", "qty": 3})
    assert session.query(InventoryRow).filter_by(character_id="thorin").count() == 0


def test_a_full_clock_fires_exactly_once(session, campaign):
    for _ in range(6):
        record_event(session, campaign, EventType.CLOCK_ADVANCED,
                     {"clock_id": "redbrand_pressure"},
                     deltas=[Delta("clock", "redbrand_pressure", "inc", "filled", 1)])
    fired = session.query(EventRow).filter_by(type=EventType.CLOCK_FILLED).all()
    assert len(fired) == 1

    record_event(session, campaign, EventType.CLOCK_ADVANCED, {"clock_id": "redbrand_pressure"},
                 deltas=[Delta("clock", "redbrand_pressure", "inc", "filled", 1)])
    assert session.query(EventRow).filter_by(type=EventType.CLOCK_FILLED).count() == 1


def test_canon_established_writes_facts(session, campaign):
    record_event(session, campaign, EventType.CANON_ESTABLISHED,
                 {"facts": [{"text": "Klarg is dead.", "entities": ["klarg"]}]}, turn_no=4)
    facts = facts_about(session, campaign, ["klarg"])
    assert len(facts) == 1
    assert facts[0].established_turn == 4


# --------------------------------------------------------------------------
# Rewind
# --------------------------------------------------------------------------

def test_replay_rebuilds_state_at_an_earlier_turn(session, campaign):
    from backend.state.models import Campaign

    for turn, damage in enumerate([5, 5, 5], start=1):
        session.get(Campaign, campaign).turn_no = turn
        record_event(session, campaign, EventType.DAMAGE, {"target": "thorin"},
                     deltas=[Delta("character", "thorin", "inc", "hp", -damage)],
                     turn_no=turn)
    assert session.get(CharacterRow, "thorin").hp == 9

    replay_to(session, campaign, 1)
    assert session.get(CharacterRow, "thorin").hp == 19


def test_rewind_drops_the_events_after_the_cut(session, campaign):
    from backend.state.models import Campaign

    for turn in range(1, 4):
        session.get(Campaign, campaign).turn_no = turn
        record_event(session, campaign, EventType.NARRATION, {"text": f"turn {turn}"},
                     turn_no=turn)
    replay_to(session, campaign, 1)
    remaining = {e.turn_no for e in session.query(EventRow).all()}
    assert remaining <= {0, 1}
    assert session.get(Campaign, campaign).turn_no == 1


def test_rewind_restores_inventory(session, campaign):
    from backend.state.models import Campaign

    session.get(Campaign, campaign).turn_no = 2
    record_event(session, campaign, EventType.ITEM_GAINED,
                 {"character_id": "thorin", "item_id": "crown", "qty": 1}, turn_no=2)
    assert session.query(InventoryRow).filter_by(item_id="crown").count() == 1

    replay_to(session, campaign, 1)
    assert session.query(InventoryRow).filter_by(item_id="crown").count() == 0


def test_replay_is_idempotent(session, campaign):
    from backend.state.models import Campaign

    session.get(Campaign, campaign).turn_no = 1
    record_event(session, campaign, EventType.DAMAGE, {},
                 deltas=[Delta("character", "thorin", "inc", "hp", -4)], turn_no=1)
    replay_to(session, campaign, 1)
    once = session.get(CharacterRow, "thorin").hp
    replay_to(session, campaign, 1)
    assert session.get(CharacterRow, "thorin").hp == once


# --------------------------------------------------------------------------
# Canon
# --------------------------------------------------------------------------

def test_facts_about_matches_tags_and_text(session, campaign):
    add_fact(session, campaign, "Klarg leads the goblins.", entities=["klarg"], turn=1)
    add_fact(session, campaign, "The bridge is out.", turn=1)
    assert len(facts_about(session, campaign, ["klarg"])) == 1
    assert len(facts_about(session, campaign, ["bridge"])) == 1
    assert facts_about(session, campaign, []) == []


def test_contradicted_facts_drop_out_of_queries(session, campaign):
    from backend.state.canon import contradict

    old = add_fact(session, campaign, "Sildar is captive.", entities=["sildar"], turn=1)
    new = add_fact(session, campaign, "Sildar is free.", entities=["sildar"], turn=5)
    contradict(session, old.id, new.id)
    session.flush()
    texts = [f.text for f in facts_about(session, campaign, ["sildar"])]
    assert "Sildar is captive." not in texts


def test_relevant_facts_ranks_by_overlap(session, campaign):
    add_fact(session, campaign, "Glasstaff commands the Redbrands from the manor cellar.",
             entities=["glasstaff"], turn=2)
    add_fact(session, campaign, "The weather is fine.", turn=2)
    top = relevant_facts(session, campaign, "where do the redbrands take orders from", top_k=1)
    assert top and "Redbrands" in top[0].text


def test_relevant_facts_returns_nothing_for_an_unrelated_query(session, campaign):
    add_fact(session, campaign, "Klarg leads the goblins.", turn=1)
    assert relevant_facts(session, campaign, "zzz", top_k=3) == []
