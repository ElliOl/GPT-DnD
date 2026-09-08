"""
Orchestration: what runs when, what it costs, and what it did.

The turn loop and the world tick land here in later phases; tracing and budgets
are here from the start because seven agents are undebuggable without them.
"""

from .budget import AGENT_MODELS, BudgetExceeded, SessionBudget, estimate_cost
from .trace import TraceRecord, trace

__all__ = [
    "AGENT_MODELS",
    "BudgetExceeded",
    "SessionBudget",
    "TraceRecord",
    "estimate_cost",
    "trace",
]
