"""
Per-session token and cost budgets.

With seven agents in play, cost failure is quiet: nothing errors, the bill just
grows. The budget is a hard ceiling with a *graceful* degradation order — the
background world stops before the turn loop does, and the Auditor is the last
LLM to be cut, because shipping unchecked prose is worse than a static world.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: USD per 1M tokens, as published for the Anthropic API. Providers configured
#: through ``services/ai_factory`` that aren't listed here cost 0 by this table —
#: add a row rather than guessing.
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

#: Model assignment per agent. Hot-path agents are cheap by design; the
#: background ones may be slow and expensive because nobody is waiting.
AGENT_MODELS: dict[str, str] = {
    "intent": "claude-haiku-4-5",
    "narrator": "claude-sonnet-5",
    "auditor": "claude-haiku-4-5",
    "scribe": "claude-haiku-4-5",
    "loremaster": "claude-haiku-4-5",
    "npc_sim": "claude-sonnet-5",
    "faction": "claude-haiku-4-5",
    "architect": "claude-opus-5",
}

#: Cheapest to lose first. The turn loop's agents are at the end on purpose.
DEGRADATION_ORDER = ["architect", "npc_sim", "faction", "loremaster", "scribe", "auditor"]


def route_model(agent: str, client_model: str | None) -> str | None:
    """Which model this agent should actually run on.

    Per-agent routing only makes sense when the configured provider is one whose
    model names we know. Point the app at Ollama or LM Studio and every agent
    keeps the client's own model — sending ``claude-haiku-4-5`` to a local
    llama.cpp server would just fail. Set ``AGENT_MODEL_ROUTING=off`` to run
    everything on one model regardless.
    """
    import os

    if os.getenv("AGENT_MODEL_ROUTING", "on").lower() in ("off", "0", "false"):
        return client_model
    if client_model and not client_model.startswith("claude"):
        return client_model
    return AGENT_MODELS.get(agent, client_model)


#: Cached input is billed off the base input rate: writing the cache costs a
#: premium, reading it is cheap. Ignoring both made a cached call look nearly
#: free, which is exactly backwards for the agent with the largest prompt.
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    rate_in, rate_out = PRICING.get(model, (0.0, 0.0))
    return (
        input_tokens * rate_in
        + output_tokens * rate_out
        + cache_write_tokens * rate_in * CACHE_WRITE_MULTIPLIER
        + cache_read_tokens * rate_in * CACHE_READ_MULTIPLIER
    ) / 1_000_000


class BudgetExceeded(RuntimeError):
    """Raised when an agent is asked to run past a hard ceiling."""


@dataclass
class SessionBudget:
    """Tracks spend for one play session and decides what still gets to run."""

    limit_usd: float = 1.00
    spent_usd: float = 0.0
    #: Latency ceiling per agent, in milliseconds. Advisory — the turn loop uses
    #: it to decide whether to wait on a background result or ship without it.
    latency_budget_ms: dict[str, int] = field(
        default_factory=lambda: {
            "intent": 1500,
            "narrator": 8000,
            "auditor": 2000,
            "scribe": 4000,
            "loremaster": 2000,
        }
    )
    per_agent: dict[str, float] = field(default_factory=dict)

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.limit_usd - self.spent_usd)

    @property
    def fraction_used(self) -> float:
        return self.spent_usd / self.limit_usd if self.limit_usd else 1.0

    def record(
        self,
        agent: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_write_tokens: int = 0,
        cache_read_tokens: int = 0,
    ) -> float:
        cost = estimate_cost(
            model, input_tokens, output_tokens, cache_write_tokens, cache_read_tokens
        )
        self.spent_usd += cost
        self.per_agent[agent] = self.per_agent.get(agent, 0.0) + cost
        return cost

    def allows(self, agent: str) -> bool:
        """Whether ``agent`` may still run.

        Agents are dropped in :data:`DEGRADATION_ORDER` as the budget fills, so a
        session that overspends loses its world simulation before it loses its
        continuity checking, and never loses the Narrator.
        """
        if self.remaining_usd <= 0:
            return agent in ("intent", "narrator")
        used = self.fraction_used
        for i, name in enumerate(DEGRADATION_ORDER):
            # Cut the first background agent at 60% used, the next at ~67%, etc.
            threshold = 0.6 + i * (0.35 / len(DEGRADATION_ORDER))
            if agent == name:
                return used < threshold
        return True

    def dropped_agents(self) -> list[str]:
        return [a for a in DEGRADATION_ORDER if not self.allows(a)]

    def snapshot(self) -> dict:
        return {
            "limit_usd": round(self.limit_usd, 4),
            "spent_usd": round(self.spent_usd, 6),
            "remaining_usd": round(self.remaining_usd, 6),
            "per_agent": {k: round(v, 6) for k, v in self.per_agent.items()},
            "dropped": self.dropped_agents(),
        }
