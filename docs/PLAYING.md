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
| `/export [path]` | write the session out as a transcript fixture |
| `/quit` | |

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

## Collecting transcripts

Phases 4 and 5 need real play to tune against — roughly fifty labelled cases for
the Auditor. Every session already produces them:

```
> /export transcripts/session-01.json
```

That writes each turn with the player's words, the narration, the dice, what the
engine resolved, and the deltas that were applied — which is exactly the shape a
Scribe or Auditor test set wants. Play a few sessions, export each one, and the
next two phases have something honest to be measured against.

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
