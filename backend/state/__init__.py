"""
State layer: mechanical truth, the event log, and canon.

Nothing in here calls an LLM. Nothing outside here writes to a state table.
"""

from .db import get_session, init_db, session_scope
from .events import Delta, DeltaRejected, EventType, record_event, replay_to

__all__ = [
    "Delta",
    "DeltaRejected",
    "EventType",
    "get_session",
    "init_db",
    "record_event",
    "replay_to",
    "session_scope",
]
