# Engine audit — 2026-09-09

Written after a long play-test session of the phase-3 turn loop against
campaign `lmop` (Lost Mine of Phandelver), 88 turns, during which the player
flagged **18 hard violations, 6 soft, 1 legitimate**. Sixteen distinct bugs
were found and fixed. This is the handover for whoever picks it up next.

The session's question was: *is this whole thing built incorrectly?*

## The short answer

**No — but the way it was verified is, and there is one real design flaw.**

The architecture is sound and, in places, unusually well thought through. The
layering holds (`engine/` is pure — no DB, no LLM; `state/` is event-sourced;
agents propose, code disposes). The **delta wall works**: it correctly refused
the Scribe's hallucinated "the goblin is dead" and its invented locations.
Those rejections were the system doing its job.

What failed is not the design. It is that **"done" was defined as "unit tests
pass," and the tests never played the game.** 229 tests were green for the
entire session, while a player could not complete a single combat.

## Three findings

### 1. The test suite verifies plumbing, never play

Phases 2 (rules engine) and 3 (turn loop) are both marked done in
[`MULTI_AGENT_STATUS.md`](MULTI_AGENT_STATUS.md). Both have real tests. Neither
catches any bug found this session, because:

- `engine/` tests call pure functions with hand-built inputs. `roll_initiative`
  is tested and correct — and had **zero call sites** in the entire codebase.
- `test_turn_loop.py` drives a `ScriptedClient` that returns canned intents. It
  proves the wiring between agents carries data. It never asks whether the
  resulting game is playable.
- **No test loads the shipped module and the shipped character sheets and plays
  turns.** That single missing test would have caught most of this.

The dominant bug shape was *built but never called*:

| Primitive | State before this session |
|---|---|
| `roll_initiative`, `advance_turn`, `remove_combatant` | 0 call sites — combat never started, enemies never acted |
| `passive_score` | 0 call sites — still unused |
| `Intent.ooc` field + `"ooc"` verb | Parsed and stored, nothing ever branched on it; OOC questions crashed the turn |
| `campaign.day` / `.hour` | Columns exist, delta-whitelisted, nothing ever advanced them |
| `long_rest(slot_table=...)` | Parameter existed; the one caller never passed it, so slots never came back |
| `NPCRow` | Every module NPC seeded into it — and `load_game_state` never read that table, so **no NPC was attackable at all** |

### 2. Tests and shipped content were written to different contracts

`test_an_unknown_module_seeds_a_playable_campaign` writes its own character
sheet — flat keys, no `spellcasting` block — which is exactly the shape
`migrate_state.character_rows()` reads. The **actually shipped** sheet
([`data/characters/elara_moonwhisper.json`](../data/characters/elara_moonwhisper.json))
uses a different shape: slots nested under `spellcasting.spell_slots`, keyed by
ordinal (`"1st"`) where the engine indexes by digit (`"1"`).

Nothing ever compared the two. Every spellcaster started every campaign with
zero spell slots, and the test named "seeds a playable campaign" passed
throughout.

The same gap exists one level up: `locations/cragmaw_hideout.json` authors
eight rooms with enemies and connections in an `areas` block that
`module.locations` never reads, so none of it becomes state.

### 3. Silent degradation turns missing mechanics into hallucinated fiction

This is the actual design flaw, and it is why the failures were so hard to see.

The turn loop's stated policy is *degrade rather than fail*. In practice, when a
mechanic doesn't fire, `resolve()` returns `kind="narrative"` with no facts, the
Narrator is told "nothing mechanical happened — narrate freely within canon,"
and it improvises. The Scribe then records the improvisation as canon.

So **"the engine did nothing" and "the engine worked" are indistinguishable from
the player's seat.** Concretely, this session: a player cast Fire Bolt at a
goblin across three turns. No attack roll existed for spells, so nothing
resolved. The Narrator described a kill. The Scribe wrote "Goblin 1 was killed
by Elara's firebolt" into canon. The goblin was at full HP the whole time.

The failures the player experienced as *"the DM is hallucinating"* were not the
model misbehaving. They were the engine doing nothing and the system being
designed to paper over it quietly.

Note the phase plan does not close this: the phase-4 Auditor as specced checks
narration against **canon**. It would not have caught one bug from this session.
The missing check is narration against **mechanical state** — specifically, that
a mechanical claim in prose has a `Resolution` behind it.

## What was fixed this session

Five commits, `afbedd5..6fcde70`, ~1300 lines. Every fix has a test.

**Made real (things that could not previously exist as state)**
- Ad hoc NPCs — new `create` delta op; the Scribe flags hostiles it sees in
  narration (`new_hostiles`), they get roster entries, and `ensure_combat_stats`
  lazily backs *any* present NPC with a real combatant the first time it's
  fought. Named module NPCs (Klarg et al.) had no stat block either;
  `engine/monsters.py` supplies one.
- Ad hoc locations — same pattern (`new_locations`), nested under where they
  were found, with bidirectional `exits`. Plus `location_id` validation, which
  is what had let the party silently drift onto invented, nonexistent rooms.
- Spell attacks — `engine/spells.py` + an attack-roll branch. Previously any
  attack cantrip was pure narration.

**Wired up (things that existed but were never called)**
- Combat: initiative rolls on first attack, enemies take their turns, fights end.
- Rest restores spell slots; rests advance `day`/`hour`.
- OOC questions get answered from real facts instead of crashing the turn.

**Corrected rules and defaults**
- Monsters die at 0 HP; PCs go unconscious and roll death saves.
- Foe means *hostile*, not *not-a-PC* — an ally in the room was joining fights
  and attacking the party, and was also keeping finished fights alive forever.
- Unnamed actions default to whoever's turn it is, not whichever PC id sorts
  first alphabetically.
- Intent sees roster HP (so "the injured goblin" resolves) and is told that a
  message can carry both dialogue and an action.

## What the session cost, and what that bought

**~$1.20–1.60** of API spend across 221 agent calls and 88 turns. `/cost`
reported `$0.87`; it was under-reporting, for reasons below.

Where the 88 turns actually went:

| Outcome | Turns | Share |
|---|---|---|
| Narrative only | 30 | 34% |
| Clarification loops | 23 | 26% |
| **Actually mechanical** (a roll, real state change) | **15** | **17%** |
| OOC (the player asking the DM to explain itself) | 9 | 10% |
| Invalid | 6 | 7% |
| Crashed / empty | 5 | 6% |

**Fifteen of 88 turns did anything mechanical.** A quarter of the session was
the DM asking "which goblin?". The `narrative_only` bucket is contaminated too
— the hallucinated Fire Bolt kills live there, turns that looked productive
while the engine did nothing. For that money the party crossed one cave and
killed two goblins.

As *play* that is terrible value. As *QA* it is cheap: it bought 16 reproducible
bugs and 24 labelled cases toward phase 4's ~50 target.

### The cost accounting was itself broken

Fixed in this session, and worth understanding because it is the same shape as
every other bug here — a number that looked authoritative, was displayed to the
user, and had never been checked against reality. **There were no tests for cost
at all** (`test_budget.py` is new).

`create_message` recorded only `input_tokens` and `output_tokens`. When prompt
caching is on, the API bills cached input and reports it in *separate* fields
(`cache_creation_input_tokens`, `cache_read_input_tokens`) which were dropped.
Verified against the live API: a call reporting `input_tokens=6` had billed
4,504. Caching applied to exactly one agent — the Narrator, the one with the
largest prompt — so the largest cost was the least visible. A measured
post-fix call went from `$0.0047` under the old accounting to `$0.0134`.

There was a corroborating tell in the data that should have been caught sooner:
the Narrator reported ~1,228 input tokens/call while Intent reported ~1,777 —
impossible, since the Narrator receives scene, canon, six turns of transcript
and the resolution, while Intent gets a roster and a verb list.

Two smaller fixes alongside it: cached tokens are now priced (writes 1.25×,
reads 0.10× the base input rate), and the client no longer appends the D&D
rules to agents that supplied their own system prompt — a parser had no use for
combat rules, and it was both spend and contradictory instruction.

One claim I made during the session and had to retract: that enabling caching
for tool-using agents would cut cost. Caching does work alongside tools
(verified), and the stale `not anthropic_tools` guard is gone, but Intent's and
Scribe's prompts are far below the model's minimum cacheable size, so it
changes nothing for them today. Measure before promising a saving.

**Rates verified** against the published pricing page on 2026-09-09: Opus 5
$5/$25, Sonnet 5 $2/$10, Haiku 4.5 $1/$5 — all three match `PRICING` exactly,
and the cache multipliers match the published cache columns (1.25x write at the
five-minute tier, 0.10x read). Two things to keep in view: the write premium
rises to 2x for a one-hour cache TTL, so changing the `cache_control` TTL means
changing the multiplier; and Fable 5 / Mythos 5 are absent from the table, so
anything routed to them would report as free.

### The real cost lever is the bug list

39% of turns — clarifications, invalids, crashes — are spend a working engine
would never have generated. The fixes in this session, plus the golden-playthrough
test recommended below, are worth more than any prompt-level optimisation.

## Honest disclosures

Read these before trusting anything in the `lmop` campaign:

- **I hand-patched live DB state roughly six times.** Several used raw ORM
  writes that bypassed `record_event` — violating this project's own stated
  invariant ("never write to a state table outside an event; anything that
  bypasses `record_event` is invisible to replay"). **`/rewind` on `lmop` will
  not faithfully reproduce current state.** Treat that campaign as a useful
  play-test corpus, not a clean fixture.
- **I shipped a bug live before catching it**: the first version of the combat
  wiring treated every non-PC as hostile, so an ally attacked the party. Fixed,
  but it is the same conflation that already existed in `check_combat_end`, and
  I only found that second instance later.
- One correction had real in-game consequence: resolving an enemy turn that had
  been wrongly skipped knocked a PC unconscious.
- `test_session_api.py` (7 errors) is a **pre-existing** `httpx`/`starlette`
  TestClient incompatibility, unrelated to any of this, and still unfixed.
- I asserted a caching cost-saving that measurement then contradicted (see
  above). The retraction is in the doc because the wrong claim is instructive.

## What to do next

In priority order. **Do not rewrite — the foundations are good.**

1. **Build the missing verification layer first.** A golden-playthrough test:
   seed the real module with the real sheets, drive scripted turns through a
   full encounter, and assert on *mechanical state* — HP, slots, initiative
   order, day/hour — not on prose. Everything in finding #1 dies to this one
   test.
2. **Validate the content contract at seed time, loudly.** A shipped sheet whose
   `spellcasting` block the loader silently ignores should fail the module
   validator, not produce a slotless wizard.
3. **Add a mechanics/narration divergence check.** When prose asserts damage, a
   death, or movement with no `Resolution` behind it, that is the highest-signal
   error this system can emit. It is also the phase-4 eval set's most valuable
   labelled case, and the Auditor as currently specced will not produce it.
4. **Reconsider silent degradation.** At minimum a missing mechanic should be
   visible in the transcript. Right now the loop's most dangerous failure is
   also its quietest.
5. **Known-remaining gaps**, both same shape as what was fixed:
   - **Loot cannot be picked up.** There is no verb for acquiring an item
     (`use_item` only consumes what you already have), and `character.resources`
     is a guarded field the Scribe may not write. Treasure the Narrator
     describes finding can never become inventory.
   - `passive_score` is still unused; the module's per-room `areas` content is
     still never migrated.

## Where to look

- Phase status and intent: [`MULTI_AGENT_STATUS.md`](MULTI_AGENT_STATUS.md)
- The one-way door into the rules: `backend/engine/resolve.py`
- The delta wall (this is good, read it): `backend/state/events.py`
- Turn sequencing: `backend/orchestrator/turn_loop.py`
- Play it: `python scripts/play.py --module lost_mines_of_phandelver --campaign-id <new-id>`
