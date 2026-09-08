"""
The intent vocabulary.

The engine owns this list, not the Intent agent. The agent's job is to map free
text onto these verbs; if it can't, it says ``unknown`` and the turn falls
through to narrative resolution rather than the model inventing a mechanic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Verbs the rules engine can resolve mechanically.
MECHANICAL_VERBS = {
    "attack",
    "cast",
    "check",
    "save",
    "move",
    "use_item",
    "rest",
    "death_save",
}

#: Verbs that are real intents but have no dice behind them. The Narrator handles
#: these freely — this is where improvisation lives, safely fenced.
NARRATIVE_VERBS = {"talk", "look", "wait", "narrate", "ooc"}

ALL_VERBS = MECHANICAL_VERBS | NARRATIVE_VERBS | {"unknown"}


@dataclass
class Intent:
    """Structured player intent. One turn of input, parsed."""

    verb: str = "narrate"
    actor_id: str = ""
    targets: list[str] = field(default_factory=list)
    skill: str | None = None
    ability: str | None = None
    spell: str | None = None
    spell_level: int | None = None
    item: str | None = None
    dialogue: str | None = None
    dc: int | None = None
    advantage: bool = False
    disadvantage: bool = False
    rest_type: str | None = None  # short | long
    ooc: bool = False
    #: Set by the Intent agent when the text could mean several things. The turn
    #: loop stops and has the Narrator ask, rather than guessing.
    ambiguous: bool = False
    clarification: str | None = None
    raw_text: str = ""
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in vars(self).items()}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Intent":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    @property
    def is_mechanical(self) -> bool:
        return self.verb in MECHANICAL_VERBS


#: Tool schema handed to the Intent agent. Kept beside the dataclass so the two
#: can't drift.
INTENT_TOOL_SCHEMA: dict[str, Any] = {
    "name": "record_intent",
    "description": (
        "Classify the player's message into a structured intent. Use 'unknown' if "
        "no verb fits; never invent a mechanic that isn't listed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "verb": {"type": "string", "enum": sorted(ALL_VERBS)},
            "actor_id": {"type": "string", "description": "Which character is acting."},
            "targets": {"type": "array", "items": {"type": "string"}},
            "skill": {"type": "string", "description": "5e skill name, if a check is implied."},
            "ability": {"type": "string", "enum": ["STR", "DEX", "CON", "INT", "WIS", "CHA"]},
            "spell": {"type": "string"},
            "spell_level": {"type": "integer", "minimum": 0, "maximum": 9},
            "item": {"type": "string"},
            "dialogue": {"type": "string", "description": "What the player says in character."},
            "advantage": {"type": "boolean"},
            "disadvantage": {"type": "boolean"},
            "rest_type": {"type": "string", "enum": ["short", "long"]},
            "ooc": {"type": "boolean", "description": "Out-of-character question about rules or the game."},
            "ambiguous": {"type": "boolean"},
            "clarification": {
                "type": "string",
                "description": "If ambiguous, the question the DM should ask back.",
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["verb"],
    },
}
