"""
Self-healing temperature/top_p/top_k handling.

Claude Sonnet 5 / Opus 5 reject sampling params outright (400); Haiku 4.5
accepts them. Rather than trust a hand-maintained model list to stay current —
the user's exact worry: "I could easily use another model in future, or maybe
Haiku rejects it in a future release" — the client reacts to what the API
actually says on the first call to any given model, and remembers.

These tests exercise that behavior directly. No network, no real API key: the
error objects are constructed by hand (bypassing __init__, since the SDK's
constructor shape isn't stable across major versions and isn't what's under
test here — only `.message`/`.body`, base `APIError` attributes, are read).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import anthropic
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.anthropic_client import (  # noqa: E402
    AnthropicClient,
    _KNOWN_NO_SAMPLING_MODELS,
    _learned_no_sampling_models,
    _rejected_sampling_param,
    _supports_temperature,
    _without_sampling_params,
)


def bad_request(message: str, body: dict | None = None) -> anthropic.BadRequestError:
    """A BadRequestError carrying just `.message`/`.body` — the two attributes
    every version of the SDK's base APIError exposes, and the only ones this
    code reads. Skips the real constructor since its required arguments
    (a live httpx/httpx2 Response) aren't stable across SDK major versions."""
    exc = anthropic.BadRequestError.__new__(anthropic.BadRequestError)
    exc.message = message
    exc.body = body
    return exc


@pytest.fixture(autouse=True)
def _reset_learned_models():
    """The learned set is process-lifetime by design — reset it around each
    test so one test's discovery can't leak into another's assertions."""
    _learned_no_sampling_models.clear()
    yield
    _learned_no_sampling_models.clear()


def make_client(model: str = "claude-sonnet-5") -> AnthropicClient:
    """No network I/O happens during construction — safe with no real key."""
    return AnthropicClient(api_key="test-key", model=model)


def fake_response(content=(), stop_reason="end_turn", input_tokens=10, output_tokens=5):
    return Mock(
        content=list(content),
        stop_reason=stop_reason,
        usage=Mock(input_tokens=input_tokens, output_tokens=output_tokens),
    )


# --------------------------------------------------------------------------
# Detecting a sampling-param rejection from the error itself
# --------------------------------------------------------------------------

def test_recognizes_temperature_named_in_the_message():
    assert _rejected_sampling_param(
        bad_request("temperature: Extra inputs are not permitted")
    )


def test_recognizes_top_p_and_top_k_too():
    assert _rejected_sampling_param(bad_request("top_p is not supported by this model"))
    assert _rejected_sampling_param(bad_request("Unrecognized request argument: top_k"))


def test_falls_back_to_the_structured_body_when_message_is_generic():
    exc = bad_request("Bad request", body={"error": {"message": "temperature not allowed here"}})
    assert _rejected_sampling_param(exc)


def test_an_unrelated_400_is_not_mistaken_for_a_sampling_rejection():
    """The whole point of reading the message rather than assuming: a 400 for
    an unrelated reason must never be silently retried as if it were this."""
    assert not _rejected_sampling_param(bad_request("max_tokens must be greater than 0"))
    assert not _rejected_sampling_param(bad_request("model: not found"))


def test_without_sampling_params_strips_only_those_three_keys():
    kwargs = {"model": "x", "max_tokens": 10, "temperature": 0.7, "top_p": 0.9, "messages": []}
    cleaned = _without_sampling_params(kwargs)
    assert cleaned == {"model": "x", "max_tokens": 10, "messages": []}


# --------------------------------------------------------------------------
# The fast-path check: known models, and models learned at runtime
# --------------------------------------------------------------------------

def test_known_models_are_excluded_up_front():
    assert not _supports_temperature("claude-opus-5")
    assert not _supports_temperature("claude-sonnet-5")


def test_an_unknown_model_is_assumed_to_support_it_until_proven_otherwise():
    assert _supports_temperature("some-brand-new-model")


def test_a_model_learned_at_runtime_is_excluded_afterward():
    """This is the mechanism that answers 'what if I switch models' or 'what if
    Haiku rejects it later': no code change, no list to update."""
    assert _supports_temperature("claude-haiku-4-5")
    _learned_no_sampling_models.add("claude-haiku-4-5")
    assert not _supports_temperature("claude-haiku-4-5")


def test_the_known_set_and_the_learned_set_are_independent():
    """Clearing the learned cache must never un-teach the hand-maintained fast
    path — they're two separate reasons a model might be excluded."""
    _learned_no_sampling_models.clear()
    assert not _supports_temperature("claude-opus-5")
    assert _KNOWN_NO_SAMPLING_MODELS  # sanity: the fast path still has entries


# --------------------------------------------------------------------------
# The retry itself
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retries_without_sampling_params_on_rejection():
    client = make_client("some-future-model")
    calls: list[dict] = []

    async def fake_create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise bad_request("temperature: extra fields not permitted")
        return "second call succeeded"

    client.client.messages.create = AsyncMock(side_effect=fake_create)

    result = await client._create_with_sampling_fallback(
        {"model": "some-future-model", "max_tokens": 10, "messages": [], "temperature": 0.5}
    )

    assert result == "second call succeeded"
    assert len(calls) == 2
    assert "temperature" in calls[0]
    assert "temperature" not in calls[1]


@pytest.mark.asyncio
async def test_a_successful_rejection_teaches_the_learned_set():
    client = make_client("some-future-model")

    async def fake_create(**kwargs):
        if "temperature" in kwargs:
            raise bad_request("temperature is not supported")
        return "ok"

    client.client.messages.create = AsyncMock(side_effect=fake_create)
    await client._create_with_sampling_fallback(
        {"model": "some-future-model", "max_tokens": 10, "messages": [], "temperature": 0.5}
    )

    assert "some-future-model" in _learned_no_sampling_models


@pytest.mark.asyncio
async def test_an_unrelated_400_propagates_and_is_not_retried():
    client = make_client()
    call_count = 0

    async def fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        raise bad_request("max_tokens must be greater than 0")

    client.client.messages.create = AsyncMock(side_effect=fake_create)

    with pytest.raises(anthropic.BadRequestError):
        await client._create_with_sampling_fallback({"model": "x", "max_tokens": 0, "messages": []})

    assert call_count == 1, "an unrelated 400 must not trigger a retry"


# --------------------------------------------------------------------------
# End to end through create_message: the fast path actually engages next time
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_learning_from_one_call_prevents_the_wasted_round_trip_on_the_next():
    """First turn: send temperature, get rejected, retry without it, and
    remember. Second turn, same model: never send temperature at all — proving
    the learned set actually feeds back into the pre-check, not just the retry."""
    client = make_client("some-future-model-2")
    seen_kwargs: list[dict] = []

    async def fake_create(**kwargs):
        seen_kwargs.append(kwargs)
        if "temperature" in kwargs:
            raise bad_request("temperature is not supported")
        return fake_response()

    client.client.messages.create = AsyncMock(side_effect=fake_create)

    await client.create_message(messages=[], max_tokens=10)
    assert [("temperature" in k) for k in seen_kwargs] == [True, False]

    seen_kwargs.clear()
    await client.create_message(messages=[], max_tokens=10)
    assert len(seen_kwargs) == 1, "no wasted round trip the second time"
    assert "temperature" not in seen_kwargs[0]


@pytest.mark.asyncio
async def test_a_known_model_never_sends_temperature_in_the_first_place():
    client = make_client("claude-opus-5")
    seen_kwargs: list[dict] = []

    async def fake_create(**kwargs):
        seen_kwargs.append(kwargs)
        return fake_response()

    client.client.messages.create = AsyncMock(side_effect=fake_create)
    await client.create_message(messages=[], max_tokens=10)

    assert len(seen_kwargs) == 1
    assert "temperature" not in seen_kwargs[0]


@pytest.mark.asyncio
async def test_a_model_that_genuinely_supports_it_keeps_getting_it():
    client = make_client("claude-haiku-4-5")
    seen_kwargs: list[dict] = []

    async def fake_create(**kwargs):
        seen_kwargs.append(kwargs)
        return fake_response()

    client.client.messages.create = AsyncMock(side_effect=fake_create)
    await client.create_message(messages=[], max_tokens=10, temperature=0.6)

    assert seen_kwargs[0]["temperature"] == 0.6
