"""
Agent tracing.

Built in phase 0 rather than phase 8, deliberately: once several agents share a
turn, "why did it say that" cannot be answered from the prose alone. Every agent
call lands here with its prompt, its output, its latency, and its cost.

Traces are written on a best-effort basis — a tracing failure must never take
down a turn.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from ..state.db import session_scope
from ..state.models import TraceRow
from .budget import estimate_cost


@dataclass
class TraceRecord:
    agent: str
    model: str = ""
    campaign_id: str | None = None
    turn_no: int = 0
    prompt: str = ""
    output: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def cost_usd(self) -> float:
        return estimate_cost(self.model, self.input_tokens, self.output_tokens)


#: Kept in memory as well as on disk so the admin UI can show a live turn without
#: a round trip. Bounded — this is a debugging aid, not a log store.
_RECENT: list[TraceRecord] = []
_RECENT_LIMIT = 200


def recent(limit: int = 50, agent: str | None = None) -> list[TraceRecord]:
    records = [r for r in _RECENT if agent is None or r.agent == agent]
    return records[-limit:]


def write(record: TraceRecord, *, persist: bool = True) -> None:
    _RECENT.append(record)
    del _RECENT[:-_RECENT_LIMIT]
    if not persist:
        return
    try:
        with session_scope() as session:
            session.add(
                TraceRow(
                    campaign_id=record.campaign_id,
                    turn_no=record.turn_no,
                    agent=record.agent,
                    model=record.model,
                    latency_ms=record.latency_ms,
                    input_tokens=record.input_tokens,
                    output_tokens=record.output_tokens,
                    cost_usd=record.cost_usd,
                    prompt=record.prompt[:20000],
                    output=record.output[:20000],
                    error=record.error,
                    meta=record.meta,
                )
            )
    except Exception as exc:  # pragma: no cover - tracing must never break a turn
        print(f"⚠️  trace write failed for {record.agent}: {exc}")


@contextmanager
def trace(
    agent: str,
    model: str = "",
    *,
    campaign_id: str | None = None,
    turn_no: int = 0,
    persist: bool = True,
) -> Iterator[TraceRecord]:
    """Time an agent call and record it, whether or not it raises.

    ::

        with trace("narrator", model, campaign_id=cid, turn_no=n) as t:
            t.prompt = packet
            response = await client.create_message(...)
            t.output = response.text
            t.input_tokens = response.usage["input_tokens"]
    """
    record = TraceRecord(agent=agent, model=model, campaign_id=campaign_id, turn_no=turn_no)
    started = time.perf_counter()
    try:
        yield record
    except Exception as exc:
        record.error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        record.latency_ms = int((time.perf_counter() - started) * 1000)
        write(record, persist=persist)
