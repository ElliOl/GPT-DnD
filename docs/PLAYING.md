# Playing a session

There are two DM stacks in this repo right now, and they are played differently.

| | Legacy stack | Multi-agent stack |
|---|---|---|
| Endpoint | `POST /api/action` | `POST /api/session/{id}/action` |
| Client | the web UI | `scripts/play.py` (terminal) |
| State | `adventure.json` + browser storage | the database |
| Dice | rolled by the model via tools | rolled by the engine, seeded |
| Voice / TTS | yes | not yet |
| Quest log, levelling | yes | not yet |

The web UI still talks to the legacy stack, unchanged. Nothing below breaks it.

## Setup (once)

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt          # SQLAlchemy and pytest-asyncio are new
cd .. && cp .env.example .env            # add ANTHROPIC_API_KEY
```

Check your party sheets in `data/characters/`. Those are what get seeded as PCs —
their HP, AC, abilities and proficiencies become the numbers the engine enforces,
so a wrong sheet is a wrong game.

## Playing the multi-agent stack

```bash
python scripts/play.py --module lost_mines_of_phandelver --campaign-id lmop
```

First run seeds the campaign; later runs with the same `--campaign-id` resume it.
Then just type what you do.

```
> I shove the slab aside
  🎲 1d20+5 [14] -> 19  Athletics check

Stone grinds on stone, and the slab gives...
```

Slash commands while you play:

| Command | |
|---|---|
| `/state` | party HP, who's present, clocks |
| `/rolls` | every die this session, with the stream key that reproduces it |
| `/canon [query]` | what the world has committed to |
| `/cost` | spend per agent, and what the budget has dropped |
| `/events [n]` | the raw event log |
| `/rewind N` | replay to the end of turn N — dice reproduce exactly |
| `/export [path]` | write the session out as an eval fixture |
| `/quit` | |

And, for the phase 4 eval set:

| Command | |
|---|---|
| `/flag [n] note` | the DM contradicted something — the last turn, or turn `n` |
| `/soft [n] note` | a smaller slip; log it, but not worth regenerating |
| `/ok [n] note` | that looked like a contradiction but was legitimate |
| `/labels` | how many labelled cases you have |

`--verbose` shows the parsed intent and running spend after each turn, which is
the fastest way to see when the Intent agent is misreading you.

### Over HTTP instead

If you'd rather drive it from the API (or point a client at it):

```bash
cd backend && python3 main.py

curl -X POST localhost:8000/api/session \
  -d '{"module":"lost_mines_of_phandelver","campaign_id":"lmop"}' \
  -H 'Content-Type: application/json'

curl -X POST localhost:8000/api/session/lmop/action \
  -d '{"message":"I shove the slab aside"}' -H 'Content-Type: application/json'
```

`/api/admin/*` gives you the same inspection surface as the slash commands, plus
`/api/admin/traces` — the full prompt and output of every agent call, which is
where you look when a turn goes strange.

## Models and cost

Each agent runs on its own model (`backend/orchestrator/budget.py`):

| Agent | Model | Every turn? |
|---|---|---|
| Intent | `claude-haiku-4-5` | yes |
| Narrator | `claude-sonnet-5` | yes |
| Scribe | `claude-haiku-4-5` | yes, after the response |
| Architect | `claude-opus-5` | phase 6, background |

This routing only applies when `AI_MODEL` is an Anthropic model; point
`AI_PROVIDER` at Ollama or LM Studio and every agent uses that one local model
instead. `AGENT_MODEL_ROUTING=off` forces single-model behaviour either way.

Expect a few cents per turn. `/cost` shows the running total and per-turn
average; `SessionBudget` defaults to a $1.00 ceiling per session and starts
dropping background agents at 60% — the Narrator and Intent are never dropped.

## Collecting the phase 4 eval set

**Playing alone does not produce an Auditor eval set.** It produces a Scribe
fixture — turns, dice, deltas, all derivable from the logs. The Auditor needs one
thing the logs cannot derive: *whether the DM was actually wrong*. That has to
come from you, while you play.

So label as you go:

```
> I leave to the east
You take the eastern path out of the clearing.

> /flag canon says the clearing has one exit, north
  turn 12 flagged (hard) — canon says the clearing has one exit, north
```

Three verdicts, and you want all three:

* **`/flag`** — a hard contradiction. The turn should have been regenerated.
* **`/soft`** — a slip worth logging but not worth a retry.
* **`/ok`** — *this is the one people skip.* A turn that looked like a
  contradiction and wasn't. The Auditor's known failure mode is false positives:
  flagging legitimate surprises. Negative examples are what tune that out, and
  they are the hardest kind to invent afterwards.

Notice something two turns late? `/flag 12 the innkeeper died in session two`
labels turn 12. Labelling the same turn again replaces the earlier verdict.

`/labels` shows where you are against the plan's rough target of fifty.

### What an export contains

```
> /export transcripts/session-01.json
wrote 34 turns to transcripts/session-01.json
  9 labelled (6 violations, 3 legitimate) — the plan wants about 50
```

Each turn carries what a reproducible eval case needs:

| Field | Why it's there |
|---|---|
| `player`, `narration` | the exchange |
| `context` | **exactly what the Narrator was shown** — scene, present NPCs, the canon facts retrieval actually returned. Reconstructing this later is guesswork; retrieval is lossy and canon moves |
| `canon_at_turn` | canon as it stood *entering* that turn — what a continuity check judges against |
| `label` | your verdict and note |
| `rolls`, `resolution`, `deltas` | what the engine decided |
| `traces` | the full prompt and output of every agent call on that turn |
| `extraction_issues` | where the Narrator's footer and the Scribe disagreed |

Top-level `canon_facts` includes **superseded** facts with their
`contradicted_by` pointer. A fact the world walked back is the most interesting
case for continuity checking, so it is kept rather than filtered out.

If you export a session with nothing labelled, the tool says so — that file is a
Scribe fixture, not an Auditor one.

## "scribe skipped" / "intent fell back to keywords"

You'll see these in the terminal:

```
⚠️  scribe skipped: scribe failed after 2 attempts: scribe: expected a record_changes tool call
⚠️  intent fell back to keywords: intent failed after 2 attempts: intent: expected a record_intent tool call
```

This means the model responded with plain conversational text instead of
calling the required tool — most often on a compound or unusual turn (stating
something and asking a question in the same message, an OOC aside mixed into
in-character text). It's rarer now: the client forces tool use for any agent
whose only valid output is structured data (Intent, Scribe), so this should
mostly show up on genuinely ambiguous input rather than routinely.

It's not silent failure. Intent falls back to a conservative keyword parser —
worse at nuance, but it keeps the turn moving rather than guessing a mechanic.
Scribe skipping means canon/deltas from *that turn* aren't extracted; the
engine's own deltas (HP, dice, etc.) are unaffected, since those never went
through the Scribe. If you're seeing it often, `--verbose` shows the parsed
intent per turn so you can see what it fell back to.

## What will feel missing

Being straight about it, since you'll notice within a turn or two:

* **No voice.** TTS lives on the legacy path only.
* **No streaming.** The turn returns as one block. Buffered streaming comes with
  the Auditor in phase 4, since the two decisions are coupled.
* **No continuity checking yet.** Nothing is watching the Narrator for
  contradictions — that is precisely what phase 4 adds, and what your transcripts
  will tune.
* **Quest log and levelling** are still legacy-only.
* **Combat is turn-by-turn, not initiative-driven.** The engine has initiative,
  turn order and death saves, and the loop does not yet drive an encounter
  through them — you can attack and be attacked, but nothing is tracking whose
  turn it is.
