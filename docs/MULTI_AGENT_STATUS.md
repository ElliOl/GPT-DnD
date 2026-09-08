# Multi-Agent DM — implementation status

Tracks [`MULTI_AGENT_BUILD_PLAN.md`](MULTI_AGENT_BUILD_PLAN.md) against what is actually in
the repo. Phases 0–3 are done. The legacy game still runs unchanged alongside them.

| Phase | Status | Where |
|---|---|---|
| 0 — Fork & scaffold, tracing | done | `backend/agents/`, `backend/orchestrator/` |
| 1 — State layer | done | `backend/state/`, `scripts/migrate_state.py` |
| 2 — Rules engine | done | `backend/engine/`, `backend/tests/` |
| 3 — Intent + Scribe + turn loop | done | `agents/intent.py`, `agents/scribe.py`, `orchestrator/turn_loop.py` |
| 4 — Auditor | not started | `canon_facts` + `relevant_facts()` are the substrate |
| 5 — Loremaster + vectors | not started | `state/canon.py` has the query surface to swap |
| 6 — Story Architect | not started | `content/generated/` overlay already loads |
| 7 — NPC sim + clocks | not started | `npcs`/`clocks` tables and their events exist |

Not in the plan, added because the runtime needed it: a **module contract**, so
this plays any adventure rather than one. See
[`MODULE_CONTRACT.md`](MODULE_CONTRACT.md).

## What changed for the running game

Nothing on the old request path. `/api/action` still goes through
`services/dm_agent.py` and the legacy `game_engine/`. Everything new is additive:

* the state database is created on startup (`data/campaigns.db`, override with `GAME_DB_URL`);
* `/api/admin/*` exposes the state inspector, event timeline, traces, cost, and rewind;
* `/api/session/*` is the new turn loop, running in parallel with the old one.

Two DM stacks coexist on purpose. The new one is proven turn by turn against real
play before the old one is retired; when `/api/session/{id}/action` is doing
everything `/api/action` does, `services/dm_agent.py` and `game_engine/` go, in
one deletion rather than a long half-migration.

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

## The turn loop

```
player text
  1. Intent      -> structured intent   (ambiguous? ask, and the turn ends)
  2. resolve()   -> mechanical truth, deltas applied, rolls logged
  3. packet      -> scene, present NPCs, visible clocks, top-5 canon, resolution
  4. Narrator    -> prose
  5. Scribe      -> deltas + canon, scheduled after the response is sent
```

Every step degrades rather than fails. No Intent agent, or a failing one, falls
back to a keyword parser. A Scribe over budget is skipped — the engine has
already written everything mechanical. The Narrator is the only agent the loop
cannot proceed without.

**Ambiguity is a first-class outcome.** When the Intent agent isn't sure, or names
a target that isn't in the scene, the turn ends with the DM asking a question. An
honest question beats a confident wrong action, and it costs one cheap call.

**Scribe drift** is mitigated the way the plan suggests: the Narrator emits a
hidden `<state_delta>` footer alongside its prose, stripped before display, and
the Scribe extracts independently. Both go through the same validator. Where the
two disagree, the disagreement is logged as an `audit_violation` event — not
acted on, but kept, because that log is what tunes both prompts against real
cases.

## Next

Phase 4, the Auditor, slots between steps 4 and 5 — the loop is shaped for it.
Then buffered streaming (~800ms, the plan's recommended default) on the way out.

The thing worth starting now regardless: a golden-transcript set from real play.
`GET /api/admin/campaigns/{id}/events` already gives you turns as structured
data, so a session played through `/api/session` is a test fixture.
