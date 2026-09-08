#!/usr/bin/env python3
"""
Play a session through the multi-agent turn loop, from a terminal.

The web UI still talks to the legacy DM agent on ``/api/action``. This is how you
play the new stack — no server, no frontend, just the loop — which makes it the
fastest way to put real turns through it and collect transcripts to test against.

    python scripts/play.py --module lost_mines_of_phandelver --campaign-id lmop

Type an action and press enter. Slash commands:

    /state          the party, who's present, active clocks
    /rolls          every die rolled this session, with its stream key
    /canon [query]  what the world has committed to
    /cost           spend per agent, and what the budget has dropped
    /events [n]     the last n events
    /rewind N       replay to the end of turn N (dice reproduce exactly)
    /export [path]  write the session as a transcript fixture
    /help  /quit
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"
CYAN, YELLOW, RED, GREEN = "\033[36m", "\033[33m", "\033[31m", "\033[32m"


def _c(text: str, colour: str) -> str:
    return text if os.getenv("NO_COLOR") else f"{colour}{text}{RESET}"


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(REPO_ROOT / ".env", override=False)


# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

def ensure_campaign(module_ref: str, campaign_id: str, party_dir: Path) -> str:
    """Seed the campaign if it doesn't exist yet. Returns the module reference."""
    from backend.state.db import init_db, session_scope
    from backend.state.models import Campaign

    init_db()
    with session_scope() as session:
        existing = session.get(Campaign, campaign_id)
        if existing is not None:
            return existing.module_path or existing.adventure_id

    from scripts.migrate_state import migrate

    payload = migrate(module_ref, campaign_id, party_dir=party_dir)
    counts = {k: len(v) for k, v in payload.items() if isinstance(v, list)}
    print(_c(f"seeded {campaign_id}: " + ", ".join(f"{v} {k}" for k, v in counts.items()), DIM))
    if not counts.get("characters"):
        print(_c(f"warning: no PCs found in {party_dir} — add a character sheet first", YELLOW))
    return payload["campaign"]["module_path"]


def build_loop(module_ref: str, campaign_id: str):
    from backend.content.module import Module
    from backend.orchestrator.turn_loop import TurnLoop
    from backend.services.ai_factory import AIClientFactory

    provider = os.getenv("AI_PROVIDER", "anthropic")
    ai_client = AIClientFactory.from_env(provider=provider, model=os.getenv("AI_MODEL"))
    module = Module.load(module_ref, campaign_id=campaign_id)

    rules_path = REPO_ROOT / "data" / "additional_rules.txt"
    house_rules = rules_path.read_text(encoding="utf-8") if rules_path.exists() else ""

    print(_c(f"provider {provider} · model {getattr(ai_client, 'model', '?')} "
             f"· module {module.name}", DIM))
    return TurnLoop(ai_client, module, house_rules=house_rules)


# --------------------------------------------------------------------------
# Slash commands
# --------------------------------------------------------------------------

def show_state(campaign_id: str) -> None:
    from sqlalchemy import select

    from backend.orchestrator.context_builder import party_location, present_npcs
    from backend.state.db import session_scope
    from backend.state.models import Campaign, CharacterRow, ClockRow

    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        location = party_location(session, campaign_id)
        print(_c(f"\nturn {campaign.turn_no} · day {campaign.day} {campaign.hour:02d}:00 "
                 f"· {location or 'nowhere'}", BOLD))
        for c in session.scalars(
            select(CharacterRow).where(
                CharacterRow.campaign_id == campaign_id, CharacterRow.is_pc.is_(True)
            )
        ):
            conditions = f"  [{', '.join(c.conditions)}]" if c.conditions else ""
            slots = (c.resources or {}).get("spell_slots") or {}
            slot_text = f"  slots {slots}" if slots else ""
            print(f"  {c.name:<22} {c.hp:>3}/{c.max_hp:<3} HP  AC {c.ac}{slot_text}{conditions}")

        npcs = present_npcs(session, campaign_id, location)
        if npcs:
            print(_c("  present: " + ", ".join(
                f"{n.name} ({n.attitude_to_party:+d})" for n in npcs), DIM))
        clocks = list(session.scalars(
            select(ClockRow).where(ClockRow.campaign_id == campaign_id)))
        for clock in clocks:
            hidden = " (hidden)" if clock.hidden else ""
            print(_c(f"  clock {clock.name}: {clock.filled}/{clock.size}{hidden}", DIM))
        print()


def show_rolls(campaign_id: str, limit: int = 20) -> None:
    from backend.state.db import session_scope
    from backend.state.events import EventType, events_for

    with session_scope() as session:
        rolls = events_for(session, campaign_id, types=[EventType.ROLL])[-limit:]
    if not rolls:
        print(_c("no rolls yet\n", DIM))
        return
    print()
    for event in rolls:
        roll = event.payload.get("roll") or {}
        if not roll:
            continue
        adv = "" if roll.get("advantage") == "normal" else f" [{roll.get('advantage')}]"
        print(f"  t{event.turn_no:<3} {roll.get('notation', ''):<10} "
              f"raw {roll.get('raw')} -> {_c(str(roll.get('total')), BOLD)}{adv}"
              f"  {_c(roll.get('purpose', ''), DIM)}")
    print()


def show_canon(campaign_id: str, query: str = "") -> None:
    from backend.state.canon import all_facts, relevant_facts
    from backend.state.db import session_scope

    with session_scope() as session:
        facts = (
            relevant_facts(session, campaign_id, query, top_k=10)
            if query else all_facts(session, campaign_id)
        )
    print()
    for fact in facts:
        print(f"  {_c(f't{fact.established_turn}', DIM)} [{fact.source}] {fact.text}")
    if not facts:
        print(_c("  nothing established yet", DIM))
    print()


def show_cost(campaign_id: str, loop) -> None:
    from sqlalchemy import select

    from backend.state.db import session_scope
    from backend.state.models import TraceRow

    with session_scope() as session:
        traces = list(session.scalars(
            select(TraceRow).where(TraceRow.campaign_id == campaign_id)))

    per_agent: dict[str, dict] = {}
    for t in traces:
        bucket = per_agent.setdefault(t.agent, {"n": 0, "usd": 0.0, "ms": 0, "model": t.model})
        bucket["n"] += 1
        bucket["usd"] += t.cost_usd
        bucket["ms"] += t.latency_ms
    print()
    for agent, b in sorted(per_agent.items()):
        print(f"  {agent:<12} {b['n']:>3} calls  ${b['usd']:.4f}  "
              f"{b['ms'] // max(1, b['n']):>5}ms avg  {_c(b['model'], DIM)}")
    total = sum(b["usd"] for b in per_agent.values())
    turns = max(1, len({t.turn_no for t in traces}))
    print(_c(f"  total ${total:.4f} over {turns} turns  (${total / turns:.4f}/turn)", BOLD))
    budget = loop.budgets.get(campaign_id)
    if budget and budget.dropped_agents():
        print(_c(f"  dropped for budget: {', '.join(budget.dropped_agents())}", YELLOW))
    print()


def show_events(campaign_id: str, limit: int = 15) -> None:
    from backend.state.db import session_scope
    from backend.state.events import events_for

    with session_scope() as session:
        events = events_for(session, campaign_id)[-limit:]
    print()
    for e in events:
        detail = e.payload.get("text") or e.payload.get("kind") or ""
        print(f"  {e.id:>4} t{e.turn_no:<3} {e.type:<22} {_c(str(detail)[:70], DIM)}")
    print()


def do_rewind(campaign_id: str, turn_no: int, loop) -> None:
    from backend.state.db import session_scope
    from backend.state.events import replay_to

    with session_scope() as session:
        replayed = replay_to(session, campaign_id, turn_no)
    loop.budgets.pop(campaign_id, None)
    print(_c(f"replayed {replayed} events; back at the end of turn {turn_no}\n", GREEN))


def export_transcript(campaign_id: str, path: Path) -> None:
    """Write the session as a fixture: turns in, deltas and facts out.

    This is the shape the Scribe and Auditor test sets want — a real transcript
    with what the engine actually decided beside it.
    """
    from backend.state.canon import all_facts
    from backend.state.db import session_scope
    from backend.state.events import EventType, events_for

    with session_scope() as session:
        events = events_for(session, campaign_id)
        facts = [
            {"text": f.text, "turn": f.established_turn, "source": f.source}
            for f in all_facts(session, campaign_id)
        ]

    turns: dict[int, dict] = {}
    for e in events:
        turn = turns.setdefault(
            e.turn_no, {"turn_no": e.turn_no, "player": "", "narration": "",
                        "rolls": [], "resolution": None, "deltas": []}
        )
        if e.type == EventType.PLAYER_INPUT:
            turn["player"] = e.payload.get("text", "")
        elif e.type == EventType.NARRATION:
            turn["narration"] = e.payload.get("text", "")
        elif e.type == EventType.ROLL and e.payload.get("roll"):
            turn["rolls"].append(e.payload["roll"])
        elif e.type == EventType.RESOLUTION:
            turn["resolution"] = {k: v for k, v in e.payload.items() if k != "deltas"}
        turn["deltas"].extend(e.payload.get("deltas", []))

    payload = {
        "campaign_id": campaign_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "turns": [turns[k] for k in sorted(turns)],
        "canon_facts": facts,
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(_c(f"wrote {len(payload['turns'])} turns to {path}\n", GREEN))


HELP = __doc__.split("Slash commands:")[1].strip()


# --------------------------------------------------------------------------
# The loop
# --------------------------------------------------------------------------

async def play(args: argparse.Namespace) -> int:
    module_ref = ensure_campaign(args.module, args.campaign_id, Path(args.party))
    loop = build_loop(module_ref, args.campaign_id)

    print(_c("\nType an action, or /help. Ctrl-D to leave.\n", DIM))
    show_state(args.campaign_id)

    pending: list[asyncio.Task] = []
    while True:
        try:
            line = input(_c("> ", CYAN)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue

        if line.startswith("/"):
            command, _, rest = line[1:].partition(" ")
            rest = rest.strip()
            try:
                if command in ("quit", "q", "exit"):
                    break
                elif command in ("help", "h", "?"):
                    print(f"\n{HELP}\n")
                elif command == "state":
                    show_state(args.campaign_id)
                elif command == "rolls":
                    show_rolls(args.campaign_id, int(rest) if rest.isdigit() else 20)
                elif command == "canon":
                    show_canon(args.campaign_id, rest)
                elif command == "cost":
                    show_cost(args.campaign_id, loop)
                elif command == "events":
                    show_events(args.campaign_id, int(rest) if rest.isdigit() else 15)
                elif command == "rewind":
                    if not rest.isdigit():
                        print(_c("usage: /rewind <turn number>\n", YELLOW))
                    else:
                        do_rewind(args.campaign_id, int(rest), loop)
                elif command == "export":
                    export_transcript(
                        args.campaign_id,
                        Path(rest or f"transcripts/{args.campaign_id}.json"),
                    )
                else:
                    print(_c(f"unknown command /{command} — try /help\n", YELLOW))
            except Exception as exc:
                print(_c(f"{type(exc).__name__}: {exc}\n", RED))
            continue

        try:
            result = await loop.take_turn(args.campaign_id, line)
        except Exception as exc:
            print(_c(f"\nturn failed — {type(exc).__name__}: {exc}\n", RED))
            if args.debug:
                import traceback

                traceback.print_exc()
            continue

        if result.scribe_task is not None:
            pending.append(result.scribe_task)

        print()
        for roll in result.rolls:
            adv = "" if roll.get("advantage") == "normal" else f" [{roll['advantage']}]"
            print(_c(f"  🎲 {roll['notation']} {roll['raw']} -> {roll['total']}{adv}"
                     f"  {roll.get('purpose', '')}", DIM))
        if result.needs_clarification:
            print(_c(f"\n  {result.narration}\n", YELLOW))
        else:
            print(f"\n{result.narration}\n")
        if args.verbose:
            print(_c(f"  intent {result.intent.get('verb')} "
                     f"· spent ${result.budget.get('spent_usd', 0):.4f}\n", DIM))

    # Let any in-flight Scribe finish before the process goes away, or the last
    # turn's canon is silently lost.
    pending = [t for t in pending if not t.done()]
    if pending:
        print(_c(f"finishing {len(pending)} background extraction(s)…", DIM))
        await asyncio.gather(*pending, return_exceptions=True)
    print(_c(f"session saved. resume with the same --campaign-id {args.campaign_id}", DIM))
    return 0


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Play a session through the turn loop.")
    parser.add_argument("--module", default="lost_mines_of_phandelver",
                        help="module id, or a path to a module directory")
    parser.add_argument("--campaign-id", default=None,
                        help="new or existing campaign (defaults to the module id)")
    parser.add_argument("--party", default=str(REPO_ROOT / "data" / "characters"),
                        help="directory of PC sheets, used only when seeding")
    parser.add_argument("--verbose", action="store_true", help="show intent and spend per turn")
    parser.add_argument("--debug", action="store_true", help="full tracebacks on failure")
    args = parser.parse_args()
    args.campaign_id = args.campaign_id or Path(args.module.rstrip("/")).name

    if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
            or os.getenv("AI_PROVIDER", "").lower() in ("ollama", "lm_studio")):
        print(_c("No API key found. Copy .env.example to .env and add one, "
                 "or set AI_PROVIDER=ollama for a local model.", RED))
        return 2

    try:
        return asyncio.run(play(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
