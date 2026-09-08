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
- Speak only as the DM and the NPCs present. Never write the players' actions,
  dialogue, or feelings for them.

Length: match the moment. Combat beats are one or two sentences. A new location
gets three to five. Never pad.
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
        **_: Any,
    ) -> list[Message]:
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

    def validate(self, result: str) -> str:
        from .base import AgentFailed

        if not result.strip():
            raise AgentFailed("narrator returned empty prose")
        return result.strip()

    def trace_meta(self, **kwargs: Any) -> dict[str, Any]:
        return {"had_resolution": bool(kwargs.get("resolution_facts"))}
