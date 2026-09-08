# The module contract

The runtime plays **any** module that satisfies the contract below. Nothing in
`backend/engine/`, `backend/state/`, `backend/orchestrator/` or `backend/agents/`
knows that Phandelver exists — that module is data, and so is the next one.

Getting a module *into* this shape from a PDF or a wiki is a separate problem
(a parser), deliberately out of scope here. This document is the target that
parser would aim at.

## Required

```
my_module/
└── adventure.json     # { "id": "my_module", "name": "My Module" }
```

That is the whole hard requirement. A module with nothing but a manifest loads
and plays; the Narrator improvises everything, which is a legitimate mode.

## Optional

```
my_module/
├── chapters/*.json
├── locations/*.json
├── npcs/*.json
├── encounters/*.json
└── items/*.json
```

Each file wants an `id` (the filename stem is used if absent) and a `name`.
**Every other key is yours.** The loader keeps entity files verbatim, and the
context builder reads whichever of `description`, `atmosphere`, `overview`,
`summary` or `current_problem` happen to be present. A module that describes its
rooms under `vibe` simply doesn't contribute scene text from that field — it
never breaks.

`items/*.json` doubles as the weapon and spell catalogue. An item with
`{"damage": "1d8", "damage_type": "slashing", "finesse": true}` resolves attacks
properly; one without falls back to default dice. The engine never invents a stat
block and never refuses for lack of one.

## Interpreted manifest keys

These are the only keys in `adventure.json` the runtime reads:

| Key | Meaning |
|---|---|
| `id`, `name` | required identity |
| `description`, `setting`, `level_range`, `player_count`, `estimated_sessions` | shown when listing modules |
| `current_state.location` / `.chapter` / `.session_number` | where play starts |
| `campaign_summary` | seeded as a canon fact |
| `active_quests[]` | seeded as quests (`id` or `name`, plus `status`, `giver`, `location`, `hidden`) |
| `discovered_locations[]`, `met_npcs[]` | seeded state |
| `important_events[]` | seeded as canon facts with `source: "play"` |
| `clocks[]` | seeded as progress clocks |
| `state_bindings` | see below |

**Everything else is preserved verbatim** as `campaign.world_flags`. A module
never loses state because the engine didn't recognise its shape.

## `state_bindings` — module state, understood mechanically

Preserved-but-inert is fine for colour and wrong for things the world tick needs
to act on. If your module tracks "is the villain still at large" in its own
bespoke structure, bind it — declaratively, in the manifest, with no code:

```json
"state_bindings": {
  "npcs": [
    {"npc": "sanbalet", "field": "status", "flag": "smuggler_ring.leader_status"},
    {"npc": "sanbalet", "field": "location_id", "flag": "smuggler_ring.leader_hideout"},
    {"npc": "oceanus", "field": "importance", "default": 3}
  ],
  "clocks": [
    {"name": "The spring tide", "size": 3, "flag": "tidal_charts.spring_tide_in_days"}
  ],
  "canon": [
    {"flag": "tidal_charts.moon_phase", "text": "The moon is {value}.", "entities": ["moon"]}
  ]
}
```

* `flag` is a dotted path into your own manifest. Missing paths are skipped, not
  errors.
* `field` on an NPC is one of `status`, `location_id`, `attitude_to_party`,
  `importance`, `goals`, `knowledge`, `resources`, `schedule`.
* `map` optionally translates your vocabulary to the runtime's.
* `default` supplies a value when there is no flag to read.

Status strings are normalised generically — `slain`/`killed`/`deceased` → `dead`,
`prisoner`/`captive`/`held` → `captured`, `escaped`/`missing` → `fled`, anything
unrecognised → `alive`. Add a `map` if your module's vocabulary is stranger than
that.

Lost Mine of Phandelver's own bindings live in its `adventure.json` and are the
worked example.

## Validating

```bash
python scripts/validate_module.py                    # every installed module
python scripts/validate_module.py my_module          # by id
python scripts/validate_module.py path/to/my_module  # by path
```

Errors block seeding; warnings (a `discovered_locations` entry with no file, an
NPC with no `name`) do not. Exits non-zero on errors, so it drops into CI as is.

`GET /api/session/modules` returns the same information over HTTP.

## Installing and playing

Modules are found in `backend/adventures/` and `frontend/public/data/`, and can
also be referenced by path from anywhere:

```bash
python scripts/migrate_state.py --module /srv/modules/the_barrow --campaign-id barrow-1
```

```http
POST /api/session                  {"module": "the_barrow", "campaign_id": "barrow-1"}
POST /api/session/barrow-1/action  {"message": "I sneak up the mound"}
```

The campaign records the path it was seeded from, so a module outside the search
paths still loads on the next boot; if it has moved, the runtime falls back to
looking the id up.

## Generated content

The Story Architect (phase 6) writes into
`backend/content/generated/{campaign_id}/` using this exact schema, and
`Module.load(..., campaign_id=...)` overlays it on the canonical module — later
wins. Generating content in the format the loader already reads is what makes
improvisation cost nothing extra at runtime.
