"""
The Narrator — the only agent that speaks to players.

It receives a context packet and mechanically-true facts, and *describes* them.
It never rolls, never decides an outcome, and never states a number that did not
come out of the engine.

Status: this wraps the existing DM prompt behind the :class:`Agent` contract so
the turn loop has something to call. ``/api/action`` still runs the legacy
``services.dm_agent.DMAgent`` — it moves over when the turn loop lands (phase 3).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..services.ai_client_base import Message
from .base import Agent

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

VOICE_RULES = """
You are the Dungeon Master's voice. You describe; you do not adjudicate.

Ignore the TOOLS section above — it describes a different agent's setup. You
have no tools in this call: never emit a tool call, function-call syntax, or
JSON describing one (e.g. {"name": "skill_check", ...}). If a mechanic needs
resolving, it has already happened by the time you see this prompt — read the
result off the RESOLUTION block below, in prose, instead.

Hard rules:
- The RESOLUTION block below is mechanical truth from the rules engine. Every
  number in it is already final. Never contradict it, never re-roll, never
  invent a roll, and never state HP, damage, gold, or a check result that isn't
  in it.
- If the resolution is `invalid`, tell the player why in character, and do not
  narrate the attempt succeeding.
- If there is no resolution, nothing mechanical happened: narrate freely within
  established canon.
- Never contradict a CANON fact. Facts absent from canon are not contradictions —
  you may invent colour, and what you invent becomes canon.
- The module's rooms and exits are reference material, not a script. When the
  party commits real, sustained effort to something it doesn't describe — a
  second entrance it never authored, a plan it didn't anticipate — let the
  effort pay off with something that moves the story forward, in proportion to
  what they put in. A dead end that erases several turns of searching is a
  worse table experience than a passage the module didn't draw, and a human DM
  would improvise the latter. What you invent this way becomes canon exactly
  like any other detail — the world can't un-discover it later.
- Speak only as the DM and the NPCs present. Never write the players' actions,
  dialogue, or feelings for them.

Length: match the moment. Combat beats are one or two sentences. A new location
gets three to five. Never pad.

After your prose, and only if something in the world changed that the RESOLUTION
block did not already cover, append a hidden footer. It is stripped before the
player sees it, so write it for the machine, not for them:

<state_delta>{"deltas": [{"target": "location", "id": "cellar", "op": "set",
"field": "discovered", "value": true}], "facts": [{"text": "The cellar door is
unlocked.", "entities": ["cellar"]}], "summary": "The party opened the cellar."}</state_delta>

Never put HP, gold, XP, or spell slots in the footer — those are the engine's.
If nothing changed, omit the footer entirely.
""".strip()


class NarratorAgent(Agent[str]):
    """Prose out. No tools, no schema — the one agent whose output is text."""

    name = "narrator"
    max_tokens = 900
    temperature = 0.8
    hot_path = True

    def __init__(self, ai_client, model: str | None = None, house_rules: str = ""):
        super().__init__(ai_client, model)
        self.house_rules = house_rules
        self._base_prompt = self._load_base_prompt()

    @staticmethod
    def _load_base_prompt() -> str:
        path = PROMPTS_DIR / "dm_system_prompt.txt"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def system_prompt(self) -> str:
        """Stable across a session so the prompt cache actually hits — everything
        that changes per turn goes in the user message."""
        parts = [self._base_prompt.strip(), VOICE_RULES]
        if self.house_rules:
            parts.append(f"House rules:\n{self.house_rules.strip()}")
        return "\n\n".join(p for p in parts if p)

    def build_messages(  # type: ignore[override]
        self,
        *,
        player_message: str,
        scene: str = "",
        resolution_facts: list[str] | None = None,
        invalid_reason: str | None = None,
        canon_facts: list[str] | None = None,
        recent_turns: list[dict[str, Any]] | None = None,
        present_npcs: list[str] | None = None,
        ooc: bool = False,
        ooc_facts: list[str] | None = None,
        **_: Any,
    ) -> list[Message]:
        if ooc:
            return self._ooc_messages(player_message, ooc_facts or [])

        blocks: list[str] = []
        if scene:
            blocks.append(f"SCENE\n{scene}")
        if present_npcs:
            blocks.append("PRESENT\n" + ", ".join(present_npcs))
        if canon_facts:
            blocks.append("CANON\n" + "\n".join(f"- {f}" for f in canon_facts))
        for turn in recent_turns or []:
            blocks.append(f"[{turn.get('role', 'player')}] {turn.get('text', '')}")
        if invalid_reason:
            blocks.append(f"RESOLUTION\ninvalid: {invalid_reason}")
        elif resolution_facts:
            blocks.append("RESOLUTION\n" + "\n".join(f"- {f}" for f in resolution_facts))
        else:
            blocks.append("RESOLUTION\n(nothing mechanical happened this turn)")
        blocks.append(f"PLAYER\n{player_message}")

        return [Message(role="user", content="\n\n".join(blocks))]

    @staticmethod
    def _ooc_messages(player_message: str, ooc_facts: list[str]) -> list[Message]:
        """A player broke the fourth wall — a rules question, not an action.

        Kept out of ``system_prompt`` so the cached prefix (the expensive,
        stable part) is untouched by a path most turns never take.
        """
        blocks = [
            "OUT OF CHARACTER\n"
            "The player is asking you directly, not describing an action their "
            "character takes. Drop the in-fiction voice and answer as the game "
            "system itself — plainly, briefly, like a DM pausing to explain a "
            "ruling at the table.\n"
            "Answer only from the FACTS below; they are the actual current game "
            "state, not flavor. If they don't cover what's being asked, say so "
            "and ask a clarifying question rather than inventing a number or a "
            "rule. Do not resume narrating the scene — the player's next message "
            "will be their next action.",
        ]
        if ooc_facts:
            blocks.append("FACTS\n" + "\n".join(f"- {f}" for f in ooc_facts))
        else:
            blocks.append("FACTS\n(none available)")
        blocks.append(f"PLAYER\n{player_message}")
        return [Message(role="user", content="\n\n".join(blocks))]

    def validate(self, result: str) -> str:
        from .base import AgentFailed

        if not result.strip():
            raise AgentFailed("narrator returned empty prose")
        return result.strip()

    def trace_meta(self, **kwargs: Any) -> dict[str, Any]:
        return {"had_resolution": bool(kwargs.get("resolution_facts")), "ooc": bool(kwargs.get("ooc"))}
