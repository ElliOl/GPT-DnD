"""
The Scribe — turn transcript in, structured deltas out.

It is the only agent that proposes state changes, and everything it proposes goes
through the same validator as engine deltas. If it decides the party found 500
gold, the validator refuses, because no event authorized it.

Scribe drift is the known failure mode: small models under-extract. The mitigation
is here rather than in a bigger model — the Narrator emits a hidden
``<state_delta>`` footer alongside its prose, stripped before display, and the
Scribe extracts independently. Two extractions that agree are much stronger
evidence than one, and where they disagree, we log it and trust the engine.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from ..services.ai_client_base import Message
from ..state.events import ALLOWED_FIELDS, Delta
from .base import Agent

FOOTER_RE = re.compile(r"<state_delta>(.*?)</state_delta>", re.DOTALL | re.IGNORECASE)

SYSTEM = """
You read one turn of a D&D session and extract what changed in the world. You do
not narrate, judge, or invent.

Extract only what the text states or plainly implies:
- `deltas`: mechanical changes not already handled by the rules engine — someone
  moved somewhere, an NPC's attitude shifted, a quest changed status, a clock
  advanced, a location became discovered.
- `facts`: new canon. Things the world has now committed to that a later scene
  must not contradict — a name given, a promise made, a door left open, a
  description of something the module didn't specify. One sentence each, stated
  as fact, no hedging.
- `summary`: one or two sentences of what happened, for the session recap.

Hard rules:
- Never propose a change to HP, spell slots, gold, XP or level. Those come from
  the rules engine, and yours would be rejected.
- If nothing changed, return empty lists. An empty extraction is a correct
  answer; inventing a change to look useful is not.
- Only reference ids that appear in the ENTITIES list.
""".strip()

SCRIBE_TOOL_SCHEMA: dict[str, Any] = {
    "name": "record_changes",
    "description": "Record what changed in the world during this turn.",
    "input_schema": {
        "type": "object",
        "properties": {
            "deltas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "enum": ["character", "npc", "quest", "clock", "location", "campaign"],
                        },
                        "id": {"type": "string", "description": "an id from ENTITIES"},
                        "op": {"type": "string", "enum": ["set", "inc", "append", "remove"]},
                        "field": {"type": "string"},
                        "value": {
                            "description": "string, number, or boolean as the field requires"
                        },
                    },
                    "required": ["target", "id", "op", "field"],
                },
            },
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "entities": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["text"],
                },
            },
            "summary": {"type": "string"},
        },
        "required": ["deltas", "facts", "summary"],
    },
}


@dataclass
class Extraction:
    """What one extractor believed changed."""

    deltas: list[Delta] = field(default_factory=list)
    facts: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""


def _delta_key(delta: Delta) -> tuple:
    return (delta.target, delta.id, delta.op, delta.field, json.dumps(delta.value, default=str))


def parse_extraction(raw: dict[str, Any]) -> Extraction:
    deltas: list[Delta] = []
    for entry in raw.get("deltas", []) or []:
        try:
            deltas.append(Delta.from_dict(entry))
        except (KeyError, TypeError):
            continue  # malformed entries are dropped, not fatal
    facts = [f for f in (raw.get("facts") or []) if isinstance(f, dict) and f.get("text")]
    return Extraction(deltas=deltas, facts=facts, summary=str(raw.get("summary", "")))


def strip_footer(prose: str) -> tuple[str, Extraction]:
    """Split the Narrator's hidden ``<state_delta>`` footer off its prose.

    Returns the text to show the player and whatever the footer claimed. A
    malformed footer costs us the cross-check, never the turn.
    """
    match = FOOTER_RE.search(prose)
    if match is None:
        return prose.strip(), Extraction()

    display = FOOTER_RE.sub("", prose).strip()
    try:
        payload = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return display, Extraction()
    if not isinstance(payload, dict):
        return display, Extraction()
    return display, parse_extraction(payload)


def reconcile(
    narrator: Extraction, scribe: Extraction
) -> tuple[list[Delta], list[dict[str, Any]], list[str]]:
    """Merge two independent extractions.

    Deltas both agree on are corroborated; deltas only one saw still apply — the
    validator is the real gate — but the disagreement is returned so it can be
    logged and the prompts tuned against real cases.
    """
    by_key: dict[tuple, Delta] = {}
    narrator_keys = {_delta_key(d) for d in narrator.deltas}
    scribe_keys = {_delta_key(d) for d in scribe.deltas}

    for delta in list(narrator.deltas) + list(scribe.deltas):
        by_key.setdefault(_delta_key(delta), delta)

    disagreements = [
        f"only {'narrator' if key in narrator_keys else 'scribe'} saw "
        f"{by_key[key].target}.{by_key[key].field} on {by_key[key].id}"
        for key in (narrator_keys ^ scribe_keys)
    ]

    facts: list[dict[str, Any]] = []
    seen_text: set[str] = set()
    for fact in narrator.facts + scribe.facts:
        text = fact["text"].strip()
        if text.lower() not in seen_text:
            seen_text.add(text.lower())
            facts.append(fact)

    return list(by_key.values()), facts, disagreements


class ScribeAgent(Agent[dict]):
    """Runs after the response is sent — the player is never waiting on it."""

    name = "scribe"
    max_tokens = 700
    temperature = 0.0
    tool_schema = SCRIBE_TOOL_SCHEMA
    max_retries = 1

    def system_prompt(self) -> str:
        writable = "\n".join(
            f"  {target}: {', '.join(sorted(fields))}"
            for target, fields in sorted(ALLOWED_FIELDS.items())
        )
        return f"{SYSTEM}\n\nWritable fields:\n{writable}"

    def build_messages(  # type: ignore[override]
        self,
        *,
        player_message: str,
        narration: str,
        resolution_facts: list[str] | None = None,
        entities: dict[str, str] | None = None,
        **_: Any,
    ) -> list[Message]:
        handled = [f"  - {f}" for f in (resolution_facts or [])] or ["  (nothing)"]
        blocks = [
            "ENTITIES",
            *(f"  {eid}: {name}" for eid, name in (entities or {}).items()),
            "",
            "ALREADY HANDLED BY THE ENGINE (do not re-extract)",
            *handled,
            "",
            f"PLAYER\n{player_message}",
            "",
            f"DM\n{narration}",
        ]
        return [Message(role="user", content="\n".join(blocks))]
