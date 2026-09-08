# Multi-Agent DM — Build Plan

Fork target: current single-`DMAgent` repo (Python backend, Anthropic SDK, `services/adventure_context.py`, JSON adventure files).

**Assumptions** — adjust if wrong: Python 3.11+, FastAPI backend, JSON-on-disk state today, a web frontend talking to a `/action` endpoint. Everything below keeps your existing adventure JSON format intact; it becomes one of several content sources rather than the only one.

---

## 0. Guiding principles

1. **One voice.** Only the Narrator speaks to players. Every other agent produces structured data.
2. **LLMs never own mechanical truth.** HP, slots, gold, position live in a database that only code writes.
3. **Hot path stays cheap.** Background agents may be slow and expensive; the turn loop must not be.
4. **Generated content becomes canon files.** The Story Architect writes into the same schema your loader already reads, so improvisation costs nothing extra at runtime.
5. **Everything is an event.** One append-only event log is the source of truth for replay, debugging, and recap.

---

## 1. Target repo structure

```
backend/
├── api/
│   ├── routes_game.py            # POST /session/{id}/action  (SSE stream out)
│   └── routes_admin.py           # inspect state, force world tick, rewind
├── orchestrator/
│   ├── turn_loop.py              # the hot path state machine
│   ├── world_loop.py             # background tick scheduler
│   ├── context_builder.py        # assembles the Narrator packet (ex-adventure_context)
│   └── budget.py                 # token/latency guards per agent
├── agents/
│   ├── base.py                   # Agent ABC: model, system prompt, schema, retry, trace
│   ├── narrator.py               # hot  — prose out
│   ├── intent.py                 # hot  — player text -> structured intent
│   ├── auditor.py                # hot  — continuity check on draft
│   ├── scribe.py                 # hot  — turn -> state deltas
│   ├── architect.py              # bg   — scouts ahead, writes content packs
│   ├── npc_sim.py                # bg   — offscreen NPC agency (batched)
│   ├── faction.py                # bg   — clocks, fronts, world pressure
│   └── loremaster.py             # on-demand retrieval
├── engine/                       # NO LLM CALLS IN HERE
│   ├── dice.py                   # seeded RNG, advantage, crits
│   ├── rules_5e.py               # checks, saves, attacks, damage types
│   ├── combat.py                 # initiative, turns, conditions, death saves
│   ├── character.py              # PC/NPC sheets, resources, rest
│   └── resolve.py                # single entry: resolve(intent, state) -> Resolution
├── state/
│   ├── db.py                     # SQLite (SQLAlchemy) — start here, Postgres later
│   ├── models.py                 # tables below
│   ├── canon.py                  # append-only fact log + query
│   ├── memory.py                 # vector store (sqlite-vec or Chroma)
│   └── events.py                 # event log + reducers
├── content/
│   ├── adventures/               # your existing module JSON — unchanged
│   ├── generated/{campaign_id}/  # Architect output, same schema
│   └── loader.py                 # merged view: generated overlays canonical
└── tests/
    ├── test_rules.py             # deterministic, no API keys needed
    ├── test_scribe_extraction.py # golden transcripts -> expected deltas
    └── test_auditor.py           # known contradictions must be caught
```

---

## 2. State layer (build this first)

Three stores, deliberately separate.

**A. Mechanical state — SQLite tables**

| Table | Key columns |
|---|---|
| `campaigns` | id, adventure_id, day, hour, session_no |
| `characters` | id, campaign_id, is_pc, hp/max_hp, ac, stats, conditions(json), resources(json), location_id |
| `inventory` | character_id, item_id, qty, equipped, attuned |
| `npcs` | id, campaign_id, template_id, status(alive/dead/fled), location_id, attitude_to_party(-5..5), goals(json), schedule(json) |
| `quests` | id, status, giver_npc, location, hidden(bool) |
| `clocks` | id, name, filled, size, owner_faction, on_complete(json) |
| `locations` | id, discovered, state_overrides(json) |
| `events` | id, campaign_id, turn_no, ts, type, payload(json) — **append only** |
| `canon_facts` | id, text, entities(json), established_turn, source(module/play/architect), contradicted_by |

**B. Canon log** — `canon_facts`. Every fact the world has committed to, with provenance. The Auditor queries this. The Scribe writes to it.

**C. Vector memory** — embed each scene summary + each canon fact. Used by Loremaster for "what did the innkeeper say three sessions ago" and for callbacks.

**Migration from today:** write `scripts/migrate_state.py` that reads your existing `adventure.json` metadata block and populates the tables. Keep `adventure.json` as *content*, drop it as *state*.

---

## 3. The rules engine (no LLM)

This is the highest-value early work and it's pure Python you can unit test.

```python
# engine/resolve.py
@dataclass
class Resolution:
    kind: str                    # "check" | "attack" | "save" | "narrative" | "invalid"
    rolls: list[Roll]            # each: die, raw, modifiers, total, seed
    dc: int | None
    success: bool | None
    degree: str | None           # crit_fail | fail | partial | success | crit_success
    state_deltas: list[Delta]    # already applied, or staged
    facts: list[str]             # mechanically true statements for the Narrator
    invalid_reason: str | None   # "you have no rope", "spell slot expended"

def resolve(intent: Intent, state: GameState) -> Resolution: ...
```

The Narrator receives `Resolution.facts` and *describes* them. It cannot alter numbers. When a player attempts something the rules don't cover, `kind="narrative"` and the Narrator is free — that's where the improvisation lives, safely fenced.

Seed the RNG per campaign and log every roll into `events` so sessions are replayable.

---

## 4. Hot loop — the turn

Target: first token to the player in under ~2s, total under ~6s.

```
player text
  │
  ├─ 1. Intent  (Haiku, ~300 tok)  ──> {verb, targets, skill, spell, dialogue, ooc?}
  │        └─ ambiguous? Narrator asks a clarifying question, turn ends
  │
  ├─ 2. Engine.resolve()  (pure code, ~0ms)
  │        └─ if intent references unknown entity -> Loremaster lookup (cached)
  │
  ├─ 3. Context builder: assemble packet
  │        system (cached) + rules primer (cached)
  │        + scene card + present NPCs + active clocks
  │        + last 6 turns + top-5 relevant canon facts + Resolution.facts
  │        ≈ 3-5k tokens
  │
  ├─ 4. Narrator  (Sonnet, streams)  ──> prose
  │
  ├─ 5. Auditor  (Haiku, runs on the completed draft, ~200 tok out)
  │        ──> {ok} | {violations:[...], severity}
  │        severity=hard  -> regenerate with violations appended (max 1 retry)
  │        severity=soft  -> ship it, log for tuning
  │
  └─ 6. Scribe  (Haiku, async after send) ──> deltas + new canon facts + scene summary
```

**Streaming vs auditing tension.** You cannot audit text you've already streamed. Three options, pick per your taste:
- *Ship it:* stream immediately, Auditor runs post-hoc and issues a quiet in-fiction correction next turn. Fastest, occasionally jarring.
- *Buffer:* hold the draft, audit, then stream. ~800ms penalty. **Recommended default.**
- *Hybrid:* stream the first paragraph (usually pure atmosphere, low risk), buffer the rest.

**Scribe as the only writer.** It emits typed deltas which go through the same validation as engine deltas. If the Scribe hallucinates "party gains 500gp", the validator rejects it because no event authorized it. Scribe proposes; code disposes.

---

## 5. Background loop — the world

Runs on a scheduler, not in the request path. `world_loop.py` polls for triggers.

### Story Architect

**Triggers:** party leaves a location, a quest changes status, a clock fills, session ends, or the party goes somewhere with no prepped content.

**Reads:** current state, canon facts, the module's remaining content, player behaviour signals (what they've engaged with, what they've ignored).

**Writes:** content packs into `content/generated/{campaign_id}/`, same schema as your module JSON, plus a small `arc.json`:

```json
{
  "arc_id": "redbrand_revenge",
  "premise": "Party humiliated the Redbrands publicly; Glasstaff needs a demonstration.",
  "why_now": "Party spent 3 sessions in Phandalin; clock 'Redbrand pressure' at 4/6.",
  "branches": [
    {
      "id": "hostage",
      "likelihood": 0.5,
      "trigger": "party returns to Phandalin after any absence",
      "opens_with": "The Stonehill common room is empty. Toblen's apron is on the floor.",
      "prepped_content": ["locations/stonehill_ransacked.json", "encounters/ransom_drop.json"],
      "clocks": [{"name": "Toblen's life", "size": 4}]
    },
    { "id": "bribe_sildar", "likelihood": 0.3, "...": "..." },
    { "id": "party_ignores", "likelihood": 0.2, "...": "..." }
  ],
  "respects_canon": ["Glasstaff is alive", "Sildar trusts the party"],
  "budget": "one session"
}
```

Give the Architect **module-awareness**: pass it the remaining chapter outlines so its inventions converge back onto Wave Echo Cave rather than wandering off. Its system prompt should say plainly: *you are prepping, not railroading — every branch must be skippable.*

### NPC agents

Not one process per NPC. One batched call per world tick over the ~10 NPCs whose `status='active'` and `importance>=2`.

Each NPC record carries `goals`, `resources`, `knowledge` (what they know and how they learned it), `schedule`, `attitude_to_party`. The tick asks: given what happened, what does each of these people do next, offscreen?

Output is constrained to a small verb set so it can't rewrite the world:
`move`, `send_message`, `spend_resource`, `change_attitude`, `advance_clock`, `spread_rumor`, `prepare_defense`, `recruit`, `flee`, `die`.

Each action becomes an event; some become visible to players only when they'd plausibly notice. That's what makes the world feel alive — the party comes back and the Redbrands have *moved*.

**Knowledge propagation** is the cheap trick that sells realism: when the party does something public, run an information-spread step (who was present → who they talk to → attitude shifts). NPCs reacting to reputation the party earned two towns ago is the single most "alive" thing this system can do.

### Faction / clock manager

Deterministic where possible. Clocks tick from events; when one fills, it fires a scripted or Architect-authored consequence. Keep 3–6 clocks max — more is noise.

---

## 6. Model assignment and cost

| Agent | Model | Frequency | ~Tokens |
|---|---|---|---|
| Intent | Haiku | every turn | 800 in / 100 out |
| Narrator | Sonnet | every turn | 4k in / 500 out |
| Auditor | Haiku | every turn | 1.5k in / 100 out |
| Scribe | Haiku | every turn | 2k in / 300 out |
| Architect | Opus/Sonnet | ~5×/session | 15k in / 3k out |
| NPC sim | Sonnet | ~10×/session | 4k in / 800 out |
| Loremaster | Haiku + vectors | on demand | 2k in / 200 out |

Use prompt caching aggressively on system prompts and the rules primer. Rough order of magnitude: a few cents per turn, well under a dollar per session — an increase over your current ~$0.01, but the background work is where the value is. Put a hard per-session budget in `budget.py` that degrades gracefully (skip NPC ticks before you skip the Auditor).

---

## 7. Phased delivery

Each phase ends with something playable. Don't skip ahead — phase 2 is what makes the rest safe.

**Phase 0 — Fork & scaffold (½ day)**
Fork, add `agents/`, `engine/`, `state/`, `orchestrator/`. Wrap the existing DMAgent as `agents/narrator.py` so the game still runs. Add tracing (every agent call logged with prompt, output, latency, cost).

**Phase 1 — State layer (2–3 days)**
SQLite schema, event log, reducers, migration script. Game unchanged externally, but state now lives in the DB.

**Phase 2 — Rules engine (3–5 days)**
`dice`, `rules_5e`, `combat`, `resolve`. Unit tests with no API calls. Narrator stops rolling dice. **This alone fixes most of your consistency problems.**

**Phase 3 — Intent + Scribe (2–3 days)**
Structured intent in, structured deltas out. Build a golden-transcript test set from real play logs.

**Phase 4 — Auditor (1–2 days)**
Continuity checking with buffered streaming. Log every violation caught — this tells you where the Narrator is weakest.

**Phase 5 — Loremaster + vector memory (2 days)**
Embeddings over canon facts and scene summaries. Callbacks and long-campaign recall start working.

**Phase 6 — Story Architect (3–5 days)**
Trigger logic, content-pack generation, merged loader. Validate generated JSON against a schema before it's allowed into `generated/`. This is the fun one; it needs the previous phases to be safe.

**Phase 7 — NPC sim + clocks (3–4 days)**
World tick, batched NPC agency, knowledge propagation, faction clocks.

**Phase 8 — Polish (ongoing)**
Admin/debug UI (state inspector, event timeline, force-tick, rewind-to-turn), session recap generation, cost dashboard.

Roughly 3–5 weeks of solid part-time work to Phase 7.

---

## 8. Things that will bite you

- **Scribe drift.** Small models under-extract. Mitigate: have the Narrator emit a hidden structured footer alongside its prose (a `<state_delta>` block stripped before display) and use the Scribe only to cross-check it. Two independent extractions agreeing is much stronger than one.
- **Architect railroading.** It will write content that assumes the party does X. Enforce in the schema: every branch needs a `skippable: true` and an `if_ignored` consequence.
- **Auditor false positives.** It'll flag legitimate surprises as contradictions. Give it explicit permission to allow anything not contradicted by `canon_facts` — absence of evidence is not contradiction. Tune with a labelled set of ~50 real cases.
- **NPC soup.** Ten NPCs with agency generates more world events than players can perceive. Gate visibility hard; most offscreen action should surface as rumor, not narration.
- **Debuggability.** With seven agents, "why did it say that" becomes impossible without traces. Build the trace viewer in Phase 0, not Phase 8.
- **Rewind.** Players will want to undo. Event-sourced state makes this a replay-to-turn-N operation — design for it from Phase 1 or you'll never retrofit it.

---

## 9. First commit

```bash
git checkout -b multi-agent
mkdir -p backend/{agents,engine,state,orchestrator,content}
touch backend/agents/base.py backend/engine/resolve.py backend/state/models.py
```

Then Phase 1. The state layer is the foundation everything else stands on — build it before writing a single new prompt.
