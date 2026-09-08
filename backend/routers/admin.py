"""
Admin / debug endpoints.

Built now rather than in the polish phase: with several agents sharing a turn,
"why did it say that" is unanswerable without the event timeline and the traces
in front of you. Everything here is read-only except ``/rewind``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from backend.orchestrator import trace as trace_module
from backend.state.canon import all_facts
from backend.state.db import session_scope
from backend.state.events import events_for, replay_to
from backend.state.models import (
    Campaign,
    CharacterRow,
    ClockRow,
    LocationRow,
    NPCRow,
    QuestRow,
    TraceRow,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/campaigns")
async def list_campaigns() -> list[dict[str, Any]]:
    with session_scope() as session:
        return [
            {
                "id": c.id,
                "adventure_id": c.adventure_id,
                "name": c.name,
                "turn_no": c.turn_no,
                "session_no": c.session_no,
                "day": c.day,
                "hour": c.hour,
            }
            for c in session.scalars(select(Campaign))
        ]


@router.get("/campaigns/{campaign_id}/state")
async def campaign_state(campaign_id: str) -> dict[str, Any]:
    """The whole mechanical picture, for the state inspector."""
    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail=f"No campaign {campaign_id!r}")

        def rows(model, **fields):
            out = []
            for row in session.scalars(select(model).where(model.campaign_id == campaign_id)):
                out.append({name: getattr(row, attr) for name, attr in fields.items()})
            return out

        return {
            "campaign": {
                "id": campaign.id, "turn_no": campaign.turn_no,
                "day": campaign.day, "hour": campaign.hour,
                "session_no": campaign.session_no, "rng_seed": campaign.rng_seed,
            },
            "characters": rows(
                CharacterRow, id="id", name="name", is_pc="is_pc", hp="hp",
                max_hp="max_hp", ac="ac", conditions="conditions",
                resources="resources", location_id="location_id",
            ),
            "npcs": rows(
                NPCRow, id="id", name="name", status="status", location_id="location_id",
                attitude="attitude_to_party", importance="importance", goals="goals",
            ),
            "quests": rows(QuestRow, id="id", title="title", status="status", hidden="hidden"),
            "clocks": rows(ClockRow, id="id", name="name", filled="filled", size="size"),
            "locations": rows(LocationRow, id="id", name="name", discovered="discovered",
                              visited="visited"),
            "canon_facts": [
                {"id": f.id, "text": f.text, "turn": f.established_turn, "source": f.source}
                for f in all_facts(session, campaign_id)
            ],
        }


@router.get("/campaigns/{campaign_id}/events")
async def event_timeline(
    campaign_id: str,
    since_turn: int = Query(0, ge=0),
    types: str | None = Query(None, description="comma-separated event types"),
    limit: int = Query(200, ge=1, le=2000),
) -> list[dict[str, Any]]:
    type_list = [t.strip() for t in types.split(",")] if types else None
    with session_scope() as session:
        events = events_for(session, campaign_id, since_turn=since_turn, types=type_list)
        return [
            {
                "id": e.id, "turn_no": e.turn_no, "ts": e.ts.isoformat(),
                "type": e.type, "actor": e.actor, "source": e.source, "payload": e.payload,
            }
            for e in events[-limit:]
        ]


@router.get("/traces")
async def list_traces(
    campaign_id: str | None = None,
    agent: str | None = None,
    limit: int = Query(50, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Every agent call: prompt, output, latency, cost."""
    with session_scope() as session:
        stmt = select(TraceRow).order_by(TraceRow.id.desc()).limit(limit)
        if campaign_id:
            stmt = stmt.where(TraceRow.campaign_id == campaign_id)
        if agent:
            stmt = stmt.where(TraceRow.agent == agent)
        return [
            {
                "id": t.id, "ts": t.ts.isoformat(), "agent": t.agent, "model": t.model,
                "turn_no": t.turn_no, "latency_ms": t.latency_ms,
                "input_tokens": t.input_tokens, "output_tokens": t.output_tokens,
                "cost_usd": round(t.cost_usd, 6), "error": t.error,
                "prompt": t.prompt, "output": t.output, "meta": t.meta,
            }
            for t in session.scalars(stmt)
        ]


@router.get("/traces/live")
async def live_traces(limit: int = Query(20, ge=1, le=200)) -> list[dict[str, Any]]:
    """In-memory tail, for watching a turn as it happens."""
    return [
        {
            "agent": r.agent, "model": r.model, "turn_no": r.turn_no,
            "latency_ms": r.latency_ms, "cost_usd": round(r.cost_usd, 6), "error": r.error,
        }
        for r in trace_module.recent(limit)
    ]


@router.get("/campaigns/{campaign_id}/cost")
async def cost_summary(campaign_id: str) -> dict[str, Any]:
    with session_scope() as session:
        traces = list(
            session.scalars(select(TraceRow).where(TraceRow.campaign_id == campaign_id))
        )
    per_agent: dict[str, dict[str, Any]] = {}
    for t in traces:
        bucket = per_agent.setdefault(t.agent, {"calls": 0, "cost_usd": 0.0, "latency_ms": 0})
        bucket["calls"] += 1
        bucket["cost_usd"] += t.cost_usd
        bucket["latency_ms"] += t.latency_ms
    for bucket in per_agent.values():
        bucket["cost_usd"] = round(bucket["cost_usd"], 6)
        bucket["avg_latency_ms"] = bucket.pop("latency_ms") // max(1, bucket["calls"])
    return {
        "total_usd": round(sum(b["cost_usd"] for b in per_agent.values()), 6),
        "calls": len(traces),
        "per_agent": per_agent,
    }


class RewindRequest(BaseModel):
    turn_no: int


@router.post("/campaigns/{campaign_id}/rewind")
async def rewind(campaign_id: str, request: RewindRequest) -> dict[str, Any]:
    """Replay the campaign to the end of ``turn_no``.

    Destructive: events after the cut are discarded, and so are the futures they
    described. Dice are reproduced exactly, because the RNG is seeded per turn.
    """
    if request.turn_no < 0:
        raise HTTPException(status_code=400, detail="turn_no must be >= 0")
    with session_scope() as session:
        if session.get(Campaign, campaign_id) is None:
            raise HTTPException(status_code=404, detail=f"No campaign {campaign_id!r}")
        replayed = replay_to(session, campaign_id, request.turn_no)
    return {"campaign_id": campaign_id, "turn_no": request.turn_no, "events_replayed": replayed}
