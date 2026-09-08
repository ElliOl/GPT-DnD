"""
Dice. Seeded, replayable, and the only source of randomness in the system.

Every roll is drawn from a stream derived from ``(campaign_seed, turn, index)``,
so replaying a session reproduces the same dice. That is the difference between
a rewind that works and a rewind that quietly rerolls the party's crit.

No LLM ever reports a number that did not come from here.
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass, field
from typing import Literal

DICE_RE = re.compile(
    r"^\s*(?P<count>\d*)d(?P<sides>\d+)"
    r"(?:(?P<keep>k[hl])(?P<keep_n>\d+))?"
    r"(?P<mods>(?:\s*[+-]\s*\d+)*)\s*$",
    re.IGNORECASE,
)

Advantage = Literal["normal", "advantage", "disadvantage"]


class DiceError(ValueError):
    """Malformed dice notation."""


@dataclass
class Roll:
    """One roll, fully explained. Serialized into the event log verbatim."""

    notation: str
    die: int
    raw: list[int]
    kept: list[int]
    modifier: int
    total: int
    stream: str
    advantage: Advantage = "normal"
    purpose: str = ""

    def to_dict(self) -> dict:
        return {
            "notation": self.notation,
            "die": self.die,
            "raw": self.raw,
            "kept": self.kept,
            "modifier": self.modifier,
            "total": self.total,
            "stream": self.stream,
            "advantage": self.advantage,
            "purpose": self.purpose,
        }

    @property
    def natural(self) -> int:
        """The unmodified d20 face, for crit detection. Meaningless on other dice."""
        return self.kept[0] if self.kept else 0


def parse(notation: str) -> tuple[int, int, str | None, int, int]:
    """``"4d6kh3+2"`` -> ``(4, 6, "kh", 3, 2)``."""
    m = DICE_RE.match(notation)
    if not m:
        raise DiceError(f"invalid dice notation: {notation!r}")
    count = int(m.group("count") or 1)
    sides = int(m.group("sides"))
    if count < 1 or sides < 2:
        raise DiceError(f"nonsensical dice: {notation!r}")
    keep = (m.group("keep") or "").lower() or None
    keep_n = int(m.group("keep_n") or count)
    modifier = sum(int(part.replace(" ", "")) for part in re.findall(r"[+-]\s*\d+", m.group("mods") or ""))
    return count, sides, keep, keep_n, modifier


@dataclass
class DiceRoller:
    """Deterministic roller bound to a campaign seed.

    ``index`` advances on every roll and is part of the stream key, so two
    identical rolls in one turn still differ — while a replay of that same turn
    reproduces both exactly.
    """

    seed: int = 0
    turn: int = 0
    index: int = 0
    log: list[Roll] = field(default_factory=list)

    def _rng(self, label: str) -> tuple[random.Random, str]:
        stream = f"{self.seed}:{self.turn}:{self.index}:{label}"
        digest = hashlib.blake2b(stream.encode(), digest_size=8).digest()
        self.index += 1
        return random.Random(int.from_bytes(digest, "big")), stream

    def start_turn(self, turn: int) -> None:
        """Reset the per-turn stream. Called once by the turn loop."""
        self.turn = turn
        self.index = 0

    def roll(self, notation: str, *, purpose: str = "", advantage: Advantage = "normal") -> Roll:
        count, sides, keep, keep_n, modifier = parse(notation)
        rng, stream = self._rng(f"{notation}|{purpose}|{advantage}")

        if advantage != "normal" and (count, sides) == (1, 20):
            raw = [rng.randint(1, 20), rng.randint(1, 20)]
            kept = [max(raw)] if advantage == "advantage" else [min(raw)]
        else:
            raw = [rng.randint(1, sides) for _ in range(count)]
            if keep == "kh":
                kept = sorted(raw, reverse=True)[:keep_n]
            elif keep == "kl":
                kept = sorted(raw)[:keep_n]
            else:
                kept = list(raw)

        result = Roll(
            notation=notation,
            die=sides,
            raw=raw,
            kept=kept,
            modifier=modifier,
            total=sum(kept) + modifier,
            stream=stream,
            advantage=advantage,
            purpose=purpose,
        )
        self.log.append(result)
        return result

    def d20(
        self, modifier: int = 0, *, purpose: str = "", advantage: Advantage = "normal"
    ) -> Roll:
        sign = "+" if modifier >= 0 else "-"
        notation = f"1d20{sign}{abs(modifier)}" if modifier else "1d20"
        return self.roll(notation, purpose=purpose, advantage=advantage)

    def damage(self, notation: str, *, critical: bool = False, purpose: str = "") -> Roll:
        """A crit doubles the dice, not the modifier — 5e RAW."""
        if not critical:
            return self.roll(notation, purpose=purpose)
        count, sides, keep, keep_n, modifier = parse(notation)
        doubled = f"{count * 2}d{sides}"
        if keep:
            doubled += f"{keep}{keep_n * 2}"
        if modifier:
            doubled += f"{'+' if modifier >= 0 else '-'}{abs(modifier)}"
        roll = self.roll(doubled, purpose=purpose or "critical damage")
        return roll


def campaign_seed(campaign_id: str, salt: str = "") -> int:
    """Stable 32-bit seed from a campaign id, so seeds survive process restarts."""
    digest = hashlib.blake2b(f"{campaign_id}:{salt}".encode(), digest_size=4).digest()
    return int.from_bytes(digest, "big")
