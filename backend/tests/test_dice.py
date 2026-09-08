"""Dice must be replayable. Everything else in the engine depends on it."""

from __future__ import annotations

import pytest

from backend.engine.dice import DiceError, DiceRoller, campaign_seed, parse


def test_parse_notation():
    assert parse("2d6+3") == (2, 6, None, 2, 3)
    assert parse("1d20") == (1, 20, None, 1, 0)
    assert parse("4d6kh3") == (4, 6, "kh", 3, 0)
    assert parse("4d6kl1-2") == (4, 6, "kl", 1, -2)


@pytest.mark.parametrize("bad", ["", "d", "20", "1d1", "0d6", "hello"])
def test_parse_rejects_garbage(bad):
    with pytest.raises(DiceError):
        parse(bad)


def test_same_seed_and_turn_reproduces_the_session():
    def session():
        r = DiceRoller(seed=campaign_seed("c1"))
        r.start_turn(7)
        return [r.roll("1d20+3").total for _ in range(10)]

    assert session() == session()


def test_different_turns_diverge():
    a, b = DiceRoller(seed=99), DiceRoller(seed=99)
    a.start_turn(1)
    b.start_turn(2)
    assert [a.roll("1d20").total for _ in range(8)] != [b.roll("1d20").total for _ in range(8)]


def test_repeated_rolls_in_one_turn_are_independent():
    r = DiceRoller(seed=7)
    r.start_turn(1)
    rolls = [r.roll("1d20").total for _ in range(20)]
    assert len(set(rolls)) > 1, "the stream index must advance between rolls"


def test_advantage_keeps_the_higher_of_two():
    r = DiceRoller(seed=5)
    roll = r.d20(advantage="advantage")
    assert len(roll.raw) == 2
    assert roll.kept == [max(roll.raw)]


def test_disadvantage_keeps_the_lower_of_two():
    r = DiceRoller(seed=5)
    roll = r.d20(advantage="disadvantage")
    assert roll.kept == [min(roll.raw)]


def test_keep_highest_drops_the_rest():
    r = DiceRoller(seed=3)
    roll = r.roll("4d6kh3")
    assert len(roll.raw) == 4 and len(roll.kept) == 3
    assert roll.total == sum(sorted(roll.raw, reverse=True)[:3])


def test_crit_doubles_dice_not_modifier():
    r = DiceRoller(seed=11)
    crit = r.damage("2d6+4", critical=True)
    assert crit.notation == "4d6+4"
    assert crit.modifier == 4


def test_rolls_stay_in_range():
    r = DiceRoller(seed=123)
    for _ in range(500):
        assert 1 <= r.roll("1d20").total <= 20


def test_every_roll_is_logged():
    r = DiceRoller(seed=1)
    for _ in range(5):
        r.roll("1d8")
    assert len(r.log) == 5
    assert all(x.stream for x in r.log), "each roll records the stream it came from"
