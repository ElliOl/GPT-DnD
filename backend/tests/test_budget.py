"""
Cost accounting.

There were no tests here at all, which is how `/cost` came to under-report a
session by roughly a third: the Anthropic API bills cached input and reports
it in fields separate from `input_tokens`, and nothing carried them.
"""

from __future__ import annotations

from backend.orchestrator.budget import PRICING, SessionBudget, estimate_cost


def test_plain_input_and_output_are_priced_off_the_table():
    rate_in, rate_out = PRICING["claude-sonnet-5"]
    cost = estimate_cost("claude-sonnet-5", 1_000_000, 1_000_000)
    assert cost == rate_in + rate_out


def test_an_unknown_model_costs_zero_rather_than_guessing():
    assert estimate_cost("some-model-we-have-never-heard-of", 1_000_000, 1_000_000) == 0.0


def test_cached_input_is_billed_not_free():
    """The bug: cache tokens were dropped, so the agent with the largest
    prompt — the only one caching applied to — looked nearly free."""
    uncached = estimate_cost("claude-sonnet-5", 1000, 100)
    with_cache = estimate_cost("claude-sonnet-5", 1000, 100, cache_read_tokens=500_000)
    assert with_cache > uncached


def test_writing_the_cache_costs_more_than_reading_it():
    write = estimate_cost("claude-sonnet-5", 0, 0, cache_write_tokens=1_000_000)
    read = estimate_cost("claude-sonnet-5", 0, 0, cache_read_tokens=1_000_000)
    plain = estimate_cost("claude-sonnet-5", 1_000_000, 0)
    assert write > plain > read > 0


def test_the_budget_counts_cached_tokens_against_the_ceiling():
    budget = SessionBudget()
    spent = budget.record("narrator", "claude-sonnet-5", 100, 10, cache_write_tokens=200_000)
    assert spent > 0
    assert budget.spent_usd == spent
    assert budget.per_agent["narrator"] == spent
