"""
Rules engine tests. No API keys, no network, no fixtures beyond plain dataclasses.

This file is the safety net that lets the Narrator stop rolling dice.
"""

from __future__ import annotations

import pytest

from backend.engine import combat as combat_rules
from backend.engine import rules_5e as rules
from backend.engine.character import ability_modifier, proficiency_for_level
from backend.engine.dice import DiceRoller

from .conftest import make_combatant


# --------------------------------------------------------------------------
# Modifiers and proficiency
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "score,expected",
    [(1, -5), (8, -1), (9, -1), (10, 0), (11, 0), (12, 1), (16, 3), (20, 5), (30, 10)],
)
def test_ability_modifier(score, expected):
    assert ability_modifier(score) == expected


@pytest.mark.parametrize("level,pb", [(1, 2), (4, 2), (5, 3), (8, 3), (9, 4), (17, 6), (20, 6)])
def test_proficiency_by_level(level, pb):
    assert proficiency_for_level(level) == pb


def test_skill_bonus_includes_proficiency():
    c = make_combatant()
    assert c.skill_bonus("athletics") == 3 + 2  # STR 16 + proficient
    assert c.skill_bonus("stealth") == 1  # DEX 12, not proficient


def test_expertise_doubles_proficiency():
    c = make_combatant(proficiencies={"skills": ["stealth"], "expertise": ["stealth"]})
    assert c.skill_bonus("stealth") == 1 + 4


def test_save_bonus_respects_proficiency():
    c = make_combatant()
    assert c.save_bonus("STR") == 3 + 2
    assert c.save_bonus("DEX") == 1


# --------------------------------------------------------------------------
# Advantage
# --------------------------------------------------------------------------

def test_advantage_and_disadvantage_cancel():
    assert rules.combine_advantage(True, True) == "normal"
    assert rules.combine_advantage(True, False) == "advantage"
    assert rules.combine_advantage(False, True) == "disadvantage"
    assert rules.combine_advantage(False, False) == "normal"


def test_prone_target_grants_the_attacker_advantage():
    attacker = make_combatant(id="a", name="A")
    target = make_combatant(id="b", name="B", conditions=["prone"], ac=5)
    out = rules.attack(attacker, target, DiceRoller(seed=8))
    assert out.attack_roll.advantage == "advantage"


def test_poisoned_attacker_rolls_with_disadvantage():
    attacker = make_combatant(id="a", conditions=["poisoned"])
    target = make_combatant(id="b", ac=5)
    out = rules.attack(attacker, target, DiceRoller(seed=8))
    assert out.attack_roll.advantage == "disadvantage"


# --------------------------------------------------------------------------
# Checks and saves
# --------------------------------------------------------------------------

def test_degree_of_success_bands():
    roller = DiceRoller(seed=1)
    roll = roller.roll("1d20")
    for total, dc, expected in [(20, 15, "success"), (14, 15, "partial"), (10, 15, "fail")]:
        roll.total, roll.kept = total, [10]  # a mid-range natural: no crit band
        assert rules.degree_of_success(roll, dc) == expected


def test_natural_20_is_a_crit_regardless_of_dc():
    roller = DiceRoller(seed=1)
    roll = roller.roll("1d20")
    roll.kept, roll.total = [20], 21
    assert rules.degree_of_success(roll, 30) == "crit_success"


def test_natural_1_fails_even_when_the_total_clears_the_dc():
    roller = DiceRoller(seed=1)
    roll = roller.roll("1d20")
    roll.kept, roll.total = [1], 16
    assert rules.degree_of_success(roll, 10) == "crit_fail"


def test_ability_check_uses_the_skills_ability():
    c = make_combatant()
    out = rules.ability_check(c, "athletics", 10, DiceRoller(seed=4))
    assert out.roll.modifier == 5
    assert out.detail == "Athletics"


def test_unknown_skill_falls_back_to_a_raw_ability_check():
    c = make_combatant()
    out = rules.ability_check(c, "STR", 10, DiceRoller(seed=4))
    assert out.roll.modifier == 3


def test_saving_throw_success_matches_the_total():
    c = make_combatant()
    out = rules.saving_throw(c, "STR", 5, DiceRoller(seed=4))
    assert out.success is (out.roll.total >= 5)


# --------------------------------------------------------------------------
# Attacks and damage
# --------------------------------------------------------------------------

def test_natural_1_always_misses():
    attacker = make_combatant(id="a")
    target = make_combatant(id="b", ac=1)  # unmissable but for the nat 1
    for seed in range(200):
        out = rules.attack(attacker, target, DiceRoller(seed=seed))
        if out.attack_roll.natural == 1:
            assert out.hit is False
            return
    pytest.skip("no natural 1 in 200 seeds")


def test_natural_20_always_hits_and_crits():
    attacker = make_combatant(id="a")
    target = make_combatant(id="b", ac=40)  # unhittable but for the nat 20
    for seed in range(200):
        out = rules.attack(attacker, target, DiceRoller(seed=seed))
        if out.attack_roll.natural == 20:
            assert out.hit and out.critical
            assert out.damage > 0
            return
    pytest.skip("no natural 20 in 200 seeds")


def test_damage_reduces_hp_and_never_goes_below_zero():
    target = make_combatant(hp=5)
    result = rules.apply_damage(target, 50, "slashing")
    assert target.hp == 0
    assert result["dropped"] is True
    assert target.has_condition("unconscious")


def test_temp_hp_absorbs_first():
    target = make_combatant(hp=20, temp_hp=6)
    result = rules.apply_damage(target, 8, "fire")
    assert result["absorbed_by_temp_hp"] == 6
    assert target.temp_hp == 0
    assert target.hp == 18


def test_resistance_halves_and_immunity_zeroes():
    resistant = make_combatant(resources={"resistances": ["fire"]})
    rules.apply_damage(resistant, 10, "fire")
    assert resistant.hp == 15

    immune = make_combatant(resources={"immunities": ["poison"]})
    rules.apply_damage(immune, 10, "poison")
    assert immune.hp == 20


def test_vulnerability_doubles():
    c = make_combatant(resources={"vulnerabilities": ["cold"]})
    rules.apply_damage(c, 5, "cold")
    assert c.hp == 10


def test_healing_caps_at_max_and_revives():
    c = make_combatant(hp=0, conditions=["unconscious"], death_save_failures=2)
    result = rules.apply_healing(c, 100)
    assert c.hp == c.max_hp
    assert result["revived"] is True
    assert not c.has_condition("unconscious")
    assert c.death_save_failures == 0


# --------------------------------------------------------------------------
# Resources
# --------------------------------------------------------------------------

def test_spending_a_slot_you_have():
    c = make_combatant(resources={"spell_slots": {"1": 2}})
    assert rules.spend_spell_slot(c, 1) is True
    assert c.spell_slots(1) == 1


def test_spending_a_slot_you_do_not_have_fails_without_mutating():
    c = make_combatant(resources={"spell_slots": {"1": 0}})
    assert rules.spend_spell_slot(c, 1) is False
    assert c.spell_slots(1) == 0


def test_spell_save_dc():
    c = make_combatant(stats={"INT": 16}, proficiency_bonus=3)
    assert rules.spell_save_dc(c, "INT") == 8 + 3 + 3


def test_short_rest_spends_hit_dice_and_heals():
    c = make_combatant(hp=5, resources={"hit_dice": 3})
    result = rules.short_rest(c, 2, DiceRoller(seed=6))
    assert c.resources["hit_dice"] == 1
    assert result["hit_dice_spent"] == 2
    assert c.hp > 5


def test_short_rest_cannot_spend_more_dice_than_you_have():
    c = make_combatant(hp=1, resources={"hit_dice": 1})
    result = rules.short_rest(c, 5, DiceRoller(seed=6))
    assert result["hit_dice_spent"] == 1


def test_long_rest_restores_hp_and_half_hit_dice():
    c = make_combatant(hp=1, level=4, resources={"hit_dice": 0})
    rules.long_rest(c, slot_table={"1": 3})
    assert c.hp == c.max_hp
    assert c.resources["hit_dice"] == 2
    assert c.resources["spell_slots"] == {"1": 3}


def test_incapacitating_conditions_stop_a_creature_acting():
    assert make_combatant(conditions=["stunned"]).can_act is False
    assert make_combatant(hp=0).can_act is False
    assert make_combatant(conditions=["prone"]).can_act is True


# --------------------------------------------------------------------------
# Combat
# --------------------------------------------------------------------------

def test_initiative_is_sorted_high_to_low():
    party = [make_combatant(id=f"c{i}", name=f"C{i}") for i in range(5)]
    state = combat_rules.roll_initiative(party, DiceRoller(seed=2))
    scores = [e.score for e in state.order]
    assert scores == sorted(scores, reverse=True)
    assert state.active and state.round == 1


def test_turns_wrap_and_increment_the_round():
    party = [make_combatant(id=f"c{i}") for i in range(3)]
    state = combat_rules.roll_initiative(party, DiceRoller(seed=2))
    for _ in range(3):
        combat_rules.advance_turn(state)
    assert state.round == 2
    assert state.turn_index == 0


def test_removing_a_combatant_does_not_skip_the_next_one():
    party = [make_combatant(id=f"c{i}", name=f"C{i}") for i in range(3)]
    state = combat_rules.roll_initiative(party, DiceRoller(seed=2))
    combat_rules.advance_turn(state)
    current = state.current.combatant_id
    doomed = next(e.combatant_id for e in state.order if e.combatant_id != current)
    combat_rules.remove_combatant(state, doomed)
    assert state.current.combatant_id == current
    assert doomed not in [e.combatant_id for e in state.order]


def test_combat_ends_when_one_side_is_down():
    pcs = {"p": make_combatant(id="p", is_pc=True)}
    foes = {"f": make_combatant(id="f", is_pc=False, hp=0)}
    state = combat_rules.CombatState(active=True, round=1)
    combat_rules.check_combat_end(state, {**pcs, **foes})
    assert state.active is False
    assert state.ended_reason == "all enemies down"


def test_combat_state_round_trips_through_json():
    party = [make_combatant(id=f"c{i}") for i in range(3)]
    state = combat_rules.roll_initiative(party, DiceRoller(seed=2))
    restored = combat_rules.CombatState.from_dict(state.to_dict())
    assert restored.to_dict() == state.to_dict()


# --------------------------------------------------------------------------
# Death saves
# --------------------------------------------------------------------------

def test_three_failures_kill():
    c = make_combatant(hp=0, death_save_failures=2)
    roller = DiceRoller(seed=0)
    for seed in range(300):
        c.death_save_failures = 2
        c.conditions = []
        roller = DiceRoller(seed=seed)
        out = combat_rules.death_save(c, roller)
        if out.result == "dead":
            assert c.has_condition("dead")
            return
    pytest.skip("no failing death save in 300 seeds")


def test_three_successes_stabilize():
    for seed in range(300):
        c = make_combatant(hp=0, death_save_successes=2)
        out = combat_rules.death_save(c, DiceRoller(seed=seed))
        if out.result == "stabilized":
            assert c.has_condition("stable")
            return
    pytest.skip("no succeeding death save in 300 seeds")


def test_natural_20_on_a_death_save_revives_at_1_hp():
    for seed in range(400):
        c = make_combatant(hp=0, conditions=["unconscious"])
        out = combat_rules.death_save(c, DiceRoller(seed=seed))
        if out.natural == 20:
            assert out.result == "revived"
            assert c.hp == 1
            return
    pytest.skip("no natural 20 in 400 seeds")


def test_natural_1_counts_as_two_failures():
    for seed in range(400):
        c = make_combatant(hp=0)
        out = combat_rules.death_save(c, DiceRoller(seed=seed))
        if out.natural == 1:
            assert c.death_save_failures == 2
            return
    pytest.skip("no natural 1 in 400 seeds")
