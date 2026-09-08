# Multi-Agent DM — implementation status

Tracks [`MULTI_AGENT_BUILD_PLAN.md`](MULTI_AGENT_BUILD_PLAN.md) against what is actually in
the repo. Phases 0–2 are done; the game still runs exactly as before while they settle in.

| Phase | Status | Where |
|---|---|---|
| 0 — Fork & scaffold, tracing | done | `backend/agents/`, `backend/orchestrator/` |
| 1 — State layer | done | `backend/state/`, `scripts/migrate_state.py` |
| 2 — Rules engine | done | `backend/engine/`, `backend/tests/` |
| 3 — Intent + Scribe | not started | intent *schema* exists in `engine/intent.py` |
| 4 — Auditor | not started | `canon_facts` + `relevant_facts()` are the substrate |
| 5 — Loremaster + vectors | not started | `state/canon.py` has the query surface to swap |
| 6 — Story Architect | not started | — |
| 7 — NPC sim + clocks | not started | `npcs`/`clocks` tables and their events exist |

## What changed for the running game

Nothing on the request path. `/api/action` still goes through
`services/dm_agent.py`. Two things are additive:

* the state database is created on startup (`data/campaigns.db`, override with `GAME_DB_URL`);
* `/api/admin/*` exposes the state inspector, event timeline, traces, cost, and rewind.

## The three stores

**Mechanical state** — SQLite via SQLAlchemy (`state/models.py`). HP, slots, gold,
position, clocks. Only `state/events.apply_delta` writes to it, and it is only
reachable through `record_event`, so the log is a complete account of how the
world got here.

**Canon** — `canon_facts`, every fact the world has committed to, with provenance
(`module` / `play` / `architect`) and a `contradicted_by` pointer rather than
deletion. `canon.relevant_facts()` is keyword-scored today; phase 5 swaps the
scorer for embeddings behind the same signature.

**Content** — unchanged. `backend/adventures/**` is still the module JSON your
loader reads. `scripts/migrate_state.py` pulls the *state* out of
`adventure.json` (quest status, met NPCs, discovered locations, who is captured)
and leaves the *content* alone.

```bash
python scripts/migrate_state.py --campaign-id my-campaign --dry-run   # inspect
python scripts/migrate_state.py --campaign-id my-campaign             # write
```

## Rewind actually works

State is rebuilt by replaying events, not by undoing them, and the dice come from
a per-campaign seeded stream keyed on `(seed, turn, index)` — so replaying turn 7
reproduces turn 7's crit rather than rerolling it.

```
POST /api/admin/campaigns/{id}/rewind  {"turn_no": 12}
```

The one rule that keeps this true: **never write to a state table outside an
event.** Anything that bypasses `record_event` is invisible to replay.

## The delta wall

Every mutation is a typed `Delta(target, id, op, field, value)`, validated before
it lands. Fields are whitelisted per table, and the ones that carry real
consequence — `hp`, `resources`, `level`, `npc.status`, `clock.filled` — are
*guarded*: an agent proposing one needs an engine-authored event authorizing it.

So when the Scribe hallucinates "the party gains 500gp", validation drops that
delta, logs an `audit_violation` event, and the rest of the turn proceeds. Scribe
proposes; code disposes.

## The engine

`engine/resolve.py` is the single door into the rules: `resolve(intent, state) -> Resolution`.
The Narrator gets `Resolution.facts` — mechanically true sentences — and describes
them. It cannot alter a number because by the time it runs, the dice are rolled
and the deltas computed.

Three outcomes matter:

* `kind="invalid"` — the player tried something they can't do (no slot, no rope,
  target already down). `invalid_reason` is phrased for the Narrator to relay.
* `kind="narrative"` — the rules don't cover it. The Narrator is free. This is
  where improvisation lives, safely fenced.
* everything else — rolls, a DC, a degree of success, and deltas.

`engine/` has no LLM calls and no database access, which is why
`backend/tests/` runs with no API key in about two seconds.

```bash
python -m pytest backend/tests -q
```

The legacy `game_engine/` package is untouched and still serves the running DM
agent. It gets retired when the turn loop moves `/api/action` over in phase 3.

## Tracing and budget

Every agent call goes through `agents/base.Agent`, which buys a trace (prompt,
output, latency, tokens, cost) and a budget check for free. Traces land in the
`traces` table and a bounded in-memory tail:

```
GET /api/admin/traces?agent=narrator&limit=20
GET /api/admin/traces/live
GET /api/admin/campaigns/{id}/cost
```

`orchestrator/budget.py` holds the model assignment and a per-session ceiling
that degrades in a fixed order — the Architect goes first, the Auditor nearly
last, and Intent and the Narrator are never dropped. A world that stops moving is
better than prose nobody checked.

## Next

Phase 3: the Intent agent (`engine/intent.py` already holds the verb vocabulary
and the tool schema it fills in), then the Scribe and the turn loop that moves
`/api/action` onto this stack. Both need a golden-transcript test set built from
real play logs — worth collecting those now.
