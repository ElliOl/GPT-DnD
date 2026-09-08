"""
The hot path.

One player message in, one piece of prose out, with the world updated along the
way::

    player text
      1. Intent      -> structured intent (ambiguous? ask, and stop here)
      2. resolve()   -> mechanical truth, deltas applied, rolls logged
      3. packet      -> scene, present NPCs, relevant canon, the resolution
      4. Narrator    -> prose
      5. Scribe      -> deltas + canon, scheduled after the response is sent

The Auditor slots in between 4 and 5 in phase 4; the shape here leaves room for
it without rework.

Degradation is deliberate at every step. No Intent agent, or a failing one? Fall
back to the keyword parser. Scribe over budget? Skip it — the engine already
wrote everything mechanical. The only agent this loop cannot proceed without is
the Narrator.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from ..agents.base import AgentContext, AgentFailed, AgentSkipped
from ..agents.intent import IntentAgent, heuristic_intent, to_intent
from ..agents.narrator import NarratorAgent
from ..agents.scribe import ScribeAgent, parse_extraction, reconcile, strip_footer
from ..content.module import Module
from ..engine.intent import Intent
from ..engine.resolve import Resolution, resolve
from ..services.ai_client_base import BaseAIClient
from ..state.db import session_scope
from ..state.events import EventType, record_event
from ..state.models import Campaign, CharacterRow
from ..state.snapshot import apply_proposed_deltas, commit_resolution, load_game_state
from . import context_builder
from .budget import SessionBudget


def label_turn(
    campaign_id: str, turn_no: int, verdict: str, note: str = "", severity: str = "hard"
) -> None:
    """Record a human judgement about a turn.

    This is the only thing in the system that cannot be derived from the logs:
    whether the DM actually got it wrong. The Auditor's known failure mode is
    false positives — flagging legitimate surprises as contradictions — so the
    ``ok`` verdict matters as much as ``violation``. A turn that *looked* like a
    contradiction and wasn't is the hardest negative example to synthesise and
    the most valuable one to have.

    Verdicts: ``violation`` (the DM contradicted established canon or state) or
    ``ok`` (it looked wrong but was legitimate). Severity is ``hard`` — the turn
    should have been regenerated — or ``soft``, worth logging and shipping.
    """
    if verdict not in ("violation", "ok"):
        raise ValueError(f"verdict must be 'violation' or 'ok', got {verdict!r}")
    with session_scope() as session:
        record_event(
            session, campaign_id, EventType.TURN_LABEL,
            {"verdict": verdict, "note": note, "severity": severity, "labels_turn": turn_no},
            source="admin", turn_no=turn_no,
        )


@dataclass
class TurnResult:
    """What the turn produced. ``narration`` is the only part players see."""

    campaign_id: str
    turn_no: int
    narration: str
    intent: dict[str, Any] = field(default_factory=dict)
    resolution: dict[str, Any] | None = None
    rolls: list[dict[str, Any]] = field(default_factory=list)
    needs_clarification: bool = False
    budget: dict[str, Any] = field(default_factory=dict)
    #: The Scribe runs after the response is sent. Awaited by tests; ignored in play.
    scribe_task: asyncio.Task | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "turn_no": self.turn_no,
            "narration": self.narration,
            "intent": self.intent,
            "resolution": self.resolution,
            "rolls": self.rolls,
            "needs_clarification": self.needs_clarification,
            "budget": self.budget,
        }


class TurnLoop:
    """Owns the per-turn state machine for one campaign's module."""

    def __init__(
        self,
        ai_client: BaseAIClient,
        module: Module,
        *,
        house_rules: str = "",
        use_intent_agent: bool = True,
    ):
        self.module = module
        self.narrator = NarratorAgent(ai_client, house_rules=house_rules)
        self.intent_agent = IntentAgent(ai_client) if use_intent_agent else None
        self.scribe = ScribeAgent(ai_client)
        self.budgets: dict[str, SessionBudget] = {}

    def budget_for(self, campaign_id: str) -> SessionBudget:
        return self.budgets.setdefault(campaign_id, SessionBudget())

    # ---- steps ------------------------------------------------------------

    def _begin_turn(self, campaign_id: str, player_message: str) -> tuple[int, str, dict[str, str]]:
        """Advance the turn counter and log the input. Returns turn, actor, roster."""
        with session_scope() as session:
            campaign = session.get(Campaign, campaign_id)
            if campaign is None:
                raise LookupError(f"No campaign {campaign_id!r}")
            campaign.turn_no += 1
            turn_no = campaign.turn_no
            session.flush()

            record_event(
                session, campaign_id, EventType.PLAYER_INPUT,
                {"text": player_message}, source="engine", turn_no=turn_no,
            )
            roster = context_builder.scene_roster(session, campaign_id)
            first_pc = session.query(CharacterRow).filter_by(
                campaign_id=campaign_id, is_pc=True
            ).order_by(CharacterRow.id).first()
            default_actor = first_pc.id if first_pc else ""
        return turn_no, default_actor, roster

    async def _read_intent(
        self,
        player_message: str,
        roster: dict[str, str],
        default_actor: str,
        context: AgentContext,
        in_combat: bool,
    ) -> Intent:
        if self.intent_agent is None:
            return heuristic_intent(player_message, default_actor)
        try:
            raw = await self.intent_agent.run(
                context,
                player_message=player_message,
                roster=roster,
                default_actor=default_actor,
                in_combat=in_combat,
            )
        except (AgentFailed, AgentSkipped, Exception) as exc:
            # The turn is still playable without a parse — the Narrator handles
            # a `narrate` intent perfectly well.
            print(f"⚠️  intent fell back to keywords: {exc}")
            return heuristic_intent(player_message, default_actor)
        return to_intent(
            raw, player_message=player_message, default_actor=default_actor, roster=roster
        )

    def _resolve(self, campaign_id: str, intent: Intent) -> tuple[Resolution | None, list[dict]]:
        """Run the engine and persist everything it decided."""
        if not intent.is_mechanical:
            return None, []
        with session_scope() as session:
            state = load_game_state(session, campaign_id, catalog=self._catalog())
            resolution = resolve(intent, state)
            commit_resolution(session, state, resolution)
            rolls = [r.to_dict() for r in resolution.rolls]
        return resolution, rolls

    def _catalog(self) -> dict[str, dict[str, Any]]:
        """Weapon and spell stat blocks the module ships, keyed by lowercase name.

        Modules that carry none simply resolve attacks with default dice — the
        engine never invents a stat block, and never refuses for lack of one.
        """
        catalog: dict[str, dict[str, Any]] = {}
        for entity in self.module.of_kind("item").values():
            catalog[entity.name.lower()] = entity.data
        return catalog

    async def _narrate(self, campaign_id: str, packet, context: AgentContext) -> str:
        return await self.narrator.run(context, **packet.as_kwargs())

    async def _run_scribe(
        self,
        campaign_id: str,
        turn_no: int,
        player_message: str,
        narration: str,
        narrator_footer,
        resolution_facts: list[str],
        roster: dict[str, str],
        context: AgentContext,
    ) -> None:
        """Extract state changes and write them. Runs after the player has read
        the prose, so its latency is invisible."""
        scribe_extraction = parse_extraction({})
        try:
            raw = await self.scribe.run(
                context,
                player_message=player_message,
                narration=narration,
                resolution_facts=resolution_facts,
                entities=roster,
            )
            scribe_extraction = parse_extraction(raw)
        except (AgentFailed, AgentSkipped) as exc:
            print(f"⚠️  scribe skipped: {exc}")

        deltas, facts, disagreements = reconcile(narrator_footer, scribe_extraction)
        if not (deltas or facts or disagreements or scribe_extraction.summary):
            return

        with session_scope() as session:
            if deltas:
                apply_proposed_deltas(
                    session, campaign_id, [d.to_dict() for d in deltas],
                    source="scribe", turn_no=turn_no,
                )
            if facts:
                record_event(
                    session, campaign_id, EventType.CANON_ESTABLISHED,
                    {"facts": facts}, source="scribe", turn_no=turn_no,
                )
            summary = scribe_extraction.summary or narrator_footer.summary
            if summary:
                record_event(
                    session, campaign_id, EventType.SCENE_SUMMARY,
                    {"text": summary}, source="scribe", turn_no=turn_no,
                )
            if disagreements:
                # Not an error — the two extractors seeing different things is
                # the signal that tunes both prompts. Logged, never acted on.
                record_event(
                    session, campaign_id, EventType.AUDIT_VIOLATION,
                    {"stage": "extraction_disagreement", "details": disagreements},
                    source="engine", turn_no=turn_no,
                )

    # ---- the turn ---------------------------------------------------------

    async def take_turn(
        self,
        campaign_id: str,
        player_message: str,
        *,
        actor_id: str | None = None,
        defer_scribe: bool = True,
    ) -> TurnResult:
        budget = self.budget_for(campaign_id)
        turn_no, default_actor, roster = self._begin_turn(campaign_id, player_message)
        context = AgentContext(campaign_id=campaign_id, turn_no=turn_no, budget=budget)

        with session_scope() as session:
            from ..state.snapshot import load_combat_state

            in_combat = load_combat_state(session, campaign_id).active

        intent = await self._read_intent(
            player_message, roster, actor_id or default_actor, context, in_combat
        )

        # An honest question beats a confident wrong action. The turn ends here.
        if intent.ambiguous:
            question = intent.clarification or "Can you say a little more about what you mean?"
            with session_scope() as session:
                record_event(
                    session, campaign_id, EventType.NARRATION,
                    {"text": question, "clarifying": True}, source="engine", turn_no=turn_no,
                )
            return TurnResult(
                campaign_id=campaign_id, turn_no=turn_no, narration=question,
                intent=intent.to_dict(), needs_clarification=True, budget=budget.snapshot(),
            )

        resolution, rolls = self._resolve(campaign_id, intent)

        with session_scope() as session:
            packet = context_builder.build_packet(
                session, campaign_id, self.module, player_message, resolution
            )
            record_event(
                session, campaign_id, EventType.CONTEXT_PACKET,
                packet.to_record(), source="engine", turn_no=turn_no,
            )

        raw_prose = await self.narrator.run(context, **packet.as_kwargs())
        narration, footer = strip_footer(raw_prose)

        with session_scope() as session:
            record_event(
                session, campaign_id, EventType.NARRATION,
                {"text": narration}, source="engine", turn_no=turn_no,
            )

        result = TurnResult(
            campaign_id=campaign_id,
            turn_no=turn_no,
            narration=narration,
            intent=intent.to_dict(),
            resolution=resolution.to_dict() if resolution else None,
            rolls=rolls,
            budget=budget.snapshot(),
        )

        scribe_args = (
            campaign_id, turn_no, player_message, narration, footer,
            packet.resolution_facts, roster, context,
        )
        if defer_scribe:
            result.scribe_task = asyncio.create_task(self._run_scribe(*scribe_args))
        else:
            await self._run_scribe(*scribe_args)
        return result
