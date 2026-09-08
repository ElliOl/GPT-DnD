"""
The agent contract.

Every LLM call in the system goes through an :class:`Agent`. That buys three
things uniformly: a trace, a budget check, and — for the agents that must return
data rather than prose — a schema the output is validated against before anyone
downstream trusts it.

Agents are provider-neutral: they take the repo's existing ``BaseAIClient``, so
Anthropic, OpenAI, and Ollama all work unchanged.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from ..orchestrator.budget import AGENT_MODELS, SessionBudget
from ..orchestrator.trace import trace
from ..services.ai_client_base import AIResponse, BaseAIClient, Message, ToolDefinition

T = TypeVar("T")


class AgentSkipped(RuntimeError):
    """The budget declined to run this agent. Callers degrade, they don't crash."""


class AgentFailed(RuntimeError):
    """The agent could not produce a valid result within its retry budget."""


@dataclass
class AgentContext:
    """Everything an agent needs to know about *when* it is running."""

    campaign_id: str | None = None
    turn_no: int = 0
    budget: SessionBudget | None = None


class Agent(ABC, Generic[T]):
    """Base class for every agent in the system.

    Subclasses declare a name, a system prompt, and how to read a result out of
    the model's response. Retry, tracing, cost accounting, and budget enforcement
    are handled here so no subclass has to remember them.
    """

    #: Short name, used for tracing, the budget table, and the model assignment.
    name: str = "agent"
    #: Overrides the model from ``AGENT_MODELS`` when set.
    model: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.7
    #: Tool the model must call to return structured data. ``None`` means prose.
    tool_schema: dict[str, Any] | None = None
    max_retries: int = 1
    #: Agents on the hot path are never dropped for budget; see ``budget.py``.
    hot_path: bool = False

    def __init__(self, ai_client: BaseAIClient, model: str | None = None):
        self.ai_client = ai_client
        if model:
            self.model = model

    # ---- subclass surface -------------------------------------------------

    @abstractmethod
    def system_prompt(self) -> str:
        """Stable across calls — put volatile content in the user message so the
        prompt cache actually hits."""

    @abstractmethod
    def build_messages(self, **kwargs: Any) -> list[Message]:
        """Assemble the per-call messages from whatever the caller passed."""

    def parse(self, response: AIResponse) -> T:
        """Turn a raw response into the agent's result type.

        The default reads the structured tool call when a schema is declared, and
        falls back to the text body otherwise.
        """
        if self.tool_schema is not None:
            for call in response.tool_calls:
                if call.name == self.tool_schema["name"]:
                    return call.parameters  # type: ignore[return-value]
            # Some providers emit JSON in the text body instead of a tool call.
            text = (response.text or "").strip()
            if text.startswith("{"):
                try:
                    return json.loads(text)  # type: ignore[return-value]
                except json.JSONDecodeError as exc:
                    raise AgentFailed(f"{self.name}: unparseable JSON output: {exc}") from exc
            raise AgentFailed(f"{self.name}: expected a {self.tool_schema['name']} tool call")
        return (response.text or "").strip()  # type: ignore[return-value]

    def validate(self, result: T) -> T:
        """Hook for agents that need more than schema conformance. Raise
        :class:`AgentFailed` to trigger a retry."""
        return result

    # ---- the call ---------------------------------------------------------

    @property
    def resolved_model(self) -> str:
        return self.model or AGENT_MODELS.get(self.name, "claude-haiku-4-5")

    async def run(self, context: AgentContext | None = None, **kwargs: Any) -> T:
        """Call the model, validate the result, trace everything.

        Raises :class:`AgentSkipped` when the session budget has degraded past
        this agent, and :class:`AgentFailed` when retries are exhausted.
        """
        context = context or AgentContext()
        if (
            context.budget is not None
            and not self.hot_path
            and not context.budget.allows(self.name)
        ):
            raise AgentSkipped(f"{self.name} dropped: session budget at {context.budget.fraction_used:.0%}")

        messages = self.build_messages(**kwargs)
        system = self.system_prompt()
        tools = (
            [ToolDefinition(**self.tool_schema)] if self.tool_schema is not None else None
        )

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            with trace(
                self.name,
                self.resolved_model,
                campaign_id=context.campaign_id,
                turn_no=context.turn_no,
            ) as record:
                record.prompt = _render_prompt(system, messages)
                record.meta = {"attempt": attempt, **self.trace_meta(**kwargs)}
                try:
                    response = await self.ai_client.create_message(
                        messages=messages,
                        tools=tools,
                        system_prompt=system,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                    )
                except Exception as exc:
                    last_error = exc
                    continue

                usage = response.usage or {}
                record.input_tokens = int(usage.get("input_tokens", 0))
                record.output_tokens = int(usage.get("output_tokens", 0))
                record.output = response.text or json.dumps(
                    [c.parameters for c in response.tool_calls], default=str
                )
                if context.budget is not None:
                    context.budget.record(
                        self.name, self.resolved_model, record.input_tokens, record.output_tokens
                    )

                try:
                    return self.validate(self.parse(response))
                except AgentFailed as exc:
                    last_error = exc
                    record.error = str(exc)
                    continue

        raise AgentFailed(f"{self.name} failed after {self.max_retries + 1} attempts: {last_error}")

    async def run_or_none(self, context: AgentContext | None = None, **kwargs: Any) -> T | None:
        """Best-effort variant for agents whose absence the turn can survive."""
        try:
            return await self.run(context, **kwargs)
        except (AgentSkipped, AgentFailed) as exc:
            print(f"⚠️  {self.name}: {exc}")
            return None

    def trace_meta(self, **kwargs: Any) -> dict[str, Any]:
        """Extra fields worth having in the trace. Keep it small."""
        return {}


def _render_prompt(system: str, messages: list[Message]) -> str:
    parts = [f"[system]\n{system}"]
    for m in messages:
        content = m.content if isinstance(m.content, str) else json.dumps(m.content, default=str)
        parts.append(f"[{m.role}]\n{content}")
    return "\n\n".join(parts)


async def gather_agents(*coros: Any) -> list[Any]:
    """Run background agents concurrently, returning exceptions rather than raising."""
    return await asyncio.gather(*coros, return_exceptions=True)
