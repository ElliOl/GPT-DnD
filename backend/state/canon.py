"""
Canon facts: what the world has committed to, and how to ask about it.

The Auditor's whole job is comparing a draft against this. Its cardinal rule —
*absence of evidence is not contradiction* — is a prompt concern, but the query
surface here is what makes it answerable: ``facts_about(entities)`` returns only
what has actually been established, never a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CanonFactRow

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "was", "it", "at",
    "on", "for", "with", "that", "this", "as", "by", "from", "but", "they",
}


@dataclass
class Fact:
    id: int
    text: str
    entities: list[str]
    established_turn: int
    source: str

    @classmethod
    def from_row(cls, row: CanonFactRow) -> "Fact":
        return cls(
            id=row.id,
            text=row.text,
            entities=list(row.entities or []),
            established_turn=row.established_turn,
            source=row.source,
        )


def add_fact(
    session: Session,
    campaign_id: str,
    text: str,
    *,
    entities: Sequence[str] = (),
    turn: int = 0,
    source: str = "play",
) -> CanonFactRow:
    """Write a fact directly. Prefer a ``canon_established`` event in normal play —
    this exists for the migration and for module import."""
    row = CanonFactRow(
        campaign_id=campaign_id,
        text=text,
        entities=list(entities),
        established_turn=turn,
        source=source,
    )
    session.add(row)
    session.flush()
    return row


def contradict(session: Session, fact_id: int, by_fact_id: int) -> None:
    """Mark a fact superseded rather than deleting it. History stays inspectable."""
    row = session.get(CanonFactRow, fact_id)
    if row is not None:
        row.contradicted_by = by_fact_id


def _live(stmt):
    return stmt.where(CanonFactRow.contradicted_by.is_(None))


def all_facts(session: Session, campaign_id: str, include_contradicted: bool = False) -> list[Fact]:
    stmt = select(CanonFactRow).where(CanonFactRow.campaign_id == campaign_id)
    if not include_contradicted:
        stmt = _live(stmt)
    return [Fact.from_row(r) for r in session.scalars(stmt.order_by(CanonFactRow.id))]


def facts_about(
    session: Session, campaign_id: str, entities: Iterable[str], limit: int = 20
) -> list[Fact]:
    """Facts tagged with, or textually mentioning, any of ``entities``."""
    wanted = {e.lower() for e in entities if e}
    if not wanted:
        return []
    out: list[Fact] = []
    for row in session.scalars(
        _live(select(CanonFactRow).where(CanonFactRow.campaign_id == campaign_id)).order_by(
            CanonFactRow.established_turn.desc()
        )
    ):
        tagged = {str(e).lower() for e in (row.entities or [])}
        text = row.text.lower()
        if tagged & wanted or any(w in text for w in wanted):
            out.append(Fact.from_row(row))
        if len(out) >= limit:
            break
    return out


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9']+", text.lower()) if t not in _STOPWORDS and len(t) > 2}


def relevant_facts(session: Session, campaign_id: str, query: str, top_k: int = 5) -> list[Fact]:
    """Keyword relevance over canon.

    Deliberately dumb: token overlap, recency as the tiebreak. Phase 5 swaps the
    scorer for embeddings behind this same signature, so callers don't change.
    """
    q = _tokens(query)
    if not q:
        return []
    scored: list[tuple[float, int, Fact]] = []
    for row in session.scalars(
        _live(select(CanonFactRow).where(CanonFactRow.campaign_id == campaign_id))
    ):
        overlap = len(q & _tokens(row.text))
        if overlap == 0:
            continue
        entity_bonus = 2 * len(q & {str(e).lower() for e in (row.entities or [])})
        scored.append((overlap + entity_bonus, row.established_turn, Fact.from_row(row)))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [f for _, _, f in scored[:top_k]]
