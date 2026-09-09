"""
The Intent agent — free text in, structured intent out.

Cheap and fast: this runs on every turn before anything else, so it gets a small
model, a tight prompt, and a closed verb list it cannot escape. Its most
important output is often ``ambiguous: true`` — the turn then ends with the
Narrator asking a question, which is far better than the engine resolving the
wrong action confidently.

It never decides outcomes. It does not set DCs. It reads what the player meant.
"""

from __future__ import annotations

from typing import Any

from ..engine.intent import ALL_VERBS, INTENT_TOOL_SCHEMA, Intent
from ..services.ai_client_base import Message
from .base import Agent, AgentFailed

SYSTEM = """
You convert a player's message at a D&D table into a structured intent. You are a
parser, not a Dungeon Master.

Rules:
- Choose exactly one verb from the allowed list. If nothing fits, use "unknown" —
  never invent a mechanic.
- `actor_id` and every entry in `targets` MUST be an id from the ROSTER. If the
  player names someone not on the roster, set ambiguous and ask about it.
- Set `ambiguous: true` when the message could reasonably mean two different
  mechanical things, when a target is unclear ("attack him" with three enemies
  present), or when you would otherwise be guessing. Put the question a DM would
  ask in `clarification`. Ambiguity is a correct answer, not a failure.
- Do not set a DC. Do not decide whether anything succeeds. Do not roll.
- `talk` covers speech and social approaches; put the player's actual words in
  `dialogue`. `look` covers examining and searching without a stated skill.
- A rules question about the game rather than an action in it is `ooc: true`.
- Prefer `narrate` over `unknown` when the player is describing something their
  character does that simply has no mechanics ("I sit down and drink").
""".strip()


class IntentAgent(Agent[dict]):
    """Player text -> :class:`Intent`."""

    name = "intent"
    max_tokens = 400
    temperature = 0.0  # parsing, not writing
    tool_schema = INTENT_TOOL_SCHEMA
    hot_path = True
    max_retries = 1

    def system_prompt(self) -> str:
        return SYSTEM

    def build_messages(  # type: ignore[override]
        self,
        *,
        player_message: str,
        roster: dict[str, str] | None = None,
        roster_status: dict[str, str] | None = None,
        default_actor: str = "",
        in_combat: bool = False,
        **_: Any,
    ) -> list[Message]:
        roster = roster or {}
        roster_status = roster_status or {}
        lines = [
            "ROSTER (use these ids — HP shown so you can resolve \"the injured "
            "one\", \"the wounded goblin\" etc. yourself, without asking)",
            *(
                f"  {rid}: {name}" + (f" ({roster_status[rid]})" if rid in roster_status else "")
                for rid, name in roster.items()
            ),
            "",
            f"VERBS: {', '.join(sorted(ALL_VERBS))}",
            f"IN COMBAT: {'yes' if in_combat else 'no'}",
        ]
        if default_actor:
            lines.append(f"DEFAULT ACTOR: {default_actor} (use unless the player names another)")
        lines += ["", "PLAYER MESSAGE", player_message]
        return [Message(role="user", content="\n".join(lines))]

    def validate(self, result: dict) -> dict:
        verb = result.get("verb")
        if verb not in ALL_VERBS:
            raise AgentFailed(f"intent returned an unknown verb {verb!r}")
        return result

    def trace_meta(self, **kwargs: Any) -> dict[str, Any]:
        return {"in_combat": bool(kwargs.get("in_combat"))}


def to_intent(
    raw: dict[str, Any], *, player_message: str, default_actor: str = "", roster: dict | None = None
) -> Intent:
    """Build an :class:`Intent`, clamping anything the model got loose about.

    Targets that aren't on the roster are dropped rather than passed through —
    the engine would reject them anyway, but dropping them here turns a confident
    wrong action into an honest "there is no such thing here".
    """
    intent = Intent.from_dict(raw)
    intent.raw_text = player_message

    if roster is not None:
        if intent.actor_id not in roster:
            intent.actor_id = default_actor
        # The roster is characters and present NPCs — a valid target namespace
        # for attack/cast, but "move"'s target is a location id, a different
        # namespace entirely. Clamping it against the wrong list would drop
        # every legitimate destination.
        if intent.verb != "move":
            unknown = [t for t in intent.targets if t not in roster]
            intent.targets = [t for t in intent.targets if t in roster]
            if unknown and not intent.targets and intent.verb in ("attack", "cast"):
                intent.ambiguous = True
                intent.clarification = (
                    intent.clarification or f"There's no {unknown[0]!r} here — who do you mean?"
                )
    elif not intent.actor_id:
        intent.actor_id = default_actor

    _catch_missed_rest(intent, player_message)
    return intent


def _catch_missed_rest(intent: Intent, player_message: str) -> None:
    """A resting party has already told the Narrator it's resting, in a message
    that usually also carries dialogue or scene-setting the model weighs more
    heavily — "Thorin says X ... the party takes the long rest" reads as `talk`
    to a classifier looking for the dominant clause. Getting this wrong is worse
    than getting most verbs wrong: the Narrator still writes a recovery scene
    from the player's own words, so the party *believes* they rested while HP,
    hit dice, and spell slots silently never move. An explicit "long rest" /
    "short rest" in the text overrides whatever verb the model chose."""
    if intent.verb == "rest":
        return
    lowered = player_message.lower()
    if "long rest" in lowered:
        intent.verb, intent.rest_type = "rest", "long"
    elif "short rest" in lowered:
        intent.verb, intent.rest_type = "rest", "short"


def heuristic_intent(player_message: str, default_actor: str = "") -> Intent:
    """A keyword fallback for when the Intent agent is unavailable.

    Deliberately conservative: it only claims a verb it is confident about, and
    falls back to ``narrate`` so the Narrator handles the turn rather than the
    engine resolving something the player didn't ask for.
    """
    text = player_message.lower()

    def any_of(*words: str) -> bool:
        return any(w in text for w in words)

    if any_of("i attack", "attack the", "swing at", "shoot the", "stab", "strike at"):
        verb = "attack"
    elif any_of("i cast", "casts "):
        verb = "cast"
    elif any_of("long rest", "short rest", "we rest", "i rest"):
        verb = "rest"
    elif any_of("i say", "i tell", "i ask", "i greet", '"'):
        verb = "talk"
    elif any_of("i search", "i examine", "i look", "i inspect", "i investigate"):
        verb = "look"
    else:
        verb = "narrate"

    return Intent(
        verb=verb,
        actor_id=default_actor,
        raw_text=player_message,
        rest_type="long" if "long rest" in text else ("short" if "short rest" in text else None),
        confidence=0.3,
    )
