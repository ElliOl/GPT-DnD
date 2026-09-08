"""
The module contract.

An adventure module is a directory of JSON. The runtime makes almost no demands
on what is inside it: an ``adventure.json`` with an ``id`` and a ``name``, and
optionally directories of chapters, locations, NPCs, encounters and items. Every
key the runtime doesn't recognise is *preserved*, never dropped — a module can
carry whatever bespoke structure it likes and still load.

That is the whole point. Nothing in this package knows about any particular
adventure. Where a module needs its own state understood mechanically (which of
its NPCs is captive, which of its clocks is running), it says so declaratively in
an optional ``state_bindings`` block, and the code below reads the binding rather
than the adventure.

Directory shape::

    my_module/
    ├── adventure.json      # required: id, name; everything else optional
    ├── chapters/*.json     # optional
    ├── locations/*.json    # optional
    ├── npcs/*.json         # optional
    ├── encounters/*.json   # optional
    └── items/*.json        # optional

Entity files need an ``id`` (the filename stem is used if absent) and ideally a
``name``. Everything else is yours.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Directories searched for modules, in order.
SEARCH_PATHS = [
    REPO_ROOT / "backend" / "adventures",
    REPO_ROOT / "frontend" / "public" / "data",
]

#: Where the Story Architect writes generated content (phase 6). Generated packs
#: use the same schema and overlay the canonical module.
GENERATED_ROOT = REPO_ROOT / "backend" / "content" / "generated"

ENTITY_DIRS = {
    "chapters": "chapter",
    "locations": "location",
    "npcs": "npc",
    "encounters": "encounter",
    "items": "item",
}

#: Keys in ``adventure.json`` the runtime interprets. Anything else is carried
#: through untouched as a world flag.
KNOWN_METADATA_KEYS = {
    "id", "name", "description", "setting", "level_range", "player_count",
    "estimated_sessions", "current_state", "campaign_summary", "active_quests",
    "discovered_locations", "met_npcs", "important_events", "state_bindings",
    "clocks", "starting_party",
}

#: Free-text status values normalised to the vocabulary the world tick uses.
STATUS_ALIASES = {
    "alive": "alive", "well": "alive", "active": "alive", "free": "alive",
    "dead": "dead", "deceased": "dead", "killed": "dead", "slain": "dead",
    "fled": "fled", "escaped": "fled", "missing": "fled",
    "captured": "captured", "captive": "captured", "prisoner": "captured",
    "imprisoned": "captured", "held": "captured",
}


class ModuleError(ValueError):
    """The module directory does not satisfy the contract."""


@dataclass
class Entity:
    """One content file, normalised just enough to index it."""

    id: str
    kind: str
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    source: str = "module"  # module | generated

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


def normalize_status(value: Any) -> str:
    """Map whatever a module wrote into the status vocabulary, defaulting to alive."""
    return STATUS_ALIASES.get(str(value or "").strip().lower(), "alive")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ModuleError(f"{path}: invalid JSON — {exc}") from exc
    if not isinstance(data, dict):
        raise ModuleError(f"{path}: expected a JSON object at the top level")
    return data


def dig(data: dict[str, Any], path: str) -> Any:
    """Read a dotted path out of nested dicts. Missing anywhere -> ``None``."""
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


@dataclass
class Module:
    """A loaded adventure module. Read-only — this is content, not state."""

    id: str
    name: str
    root: Path
    metadata: dict[str, Any] = field(default_factory=dict)
    entities: dict[str, dict[str, Entity]] = field(default_factory=dict)

    # ---- loading ----------------------------------------------------------

    @classmethod
    def find(cls, module_id: str) -> Path:
        """Resolve a module id, or a path to one, to its directory."""
        direct = Path(module_id)
        if (direct / "adventure.json").exists():
            return direct
        for base in SEARCH_PATHS:
            candidate = base / module_id
            if (candidate / "adventure.json").exists():
                return candidate
        searched = "\n".join(f"  - {b / module_id}" for b in SEARCH_PATHS)
        raise ModuleError(f"No module {module_id!r}. Looked in:\n  - {direct}\n{searched}")

    @classmethod
    def load(cls, module_id: str, *, campaign_id: str | None = None) -> "Module":
        """Load a module, overlaying generated content for ``campaign_id`` if any."""
        root = cls.find(module_id)
        metadata = _read_json(root / "adventure.json")
        module = cls(
            id=metadata.get("id") or module_id,
            name=metadata.get("name") or module_id,
            root=root,
            metadata=metadata,
            entities={kind: {} for kind in ENTITY_DIRS.values()},
        )
        module._load_entities(root, source="module")

        if campaign_id:
            generated = GENERATED_ROOT / campaign_id
            if generated.exists():
                # Generated content overlays canonical: same schema, later wins.
                module._load_entities(generated, source="generated")
        return module

    def _load_entities(self, root: Path, *, source: str) -> None:
        for dirname, kind in ENTITY_DIRS.items():
            directory = root / dirname
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.json")):
                data = _read_json(path)
                entity_id = str(data.get("id") or path.stem)
                self.entities.setdefault(kind, {})[entity_id] = Entity(
                    id=entity_id,
                    kind=kind,
                    name=str(data.get("name") or entity_id.replace("_", " ").title()),
                    data=data,
                    source=source,
                )

    # ---- access -----------------------------------------------------------

    def of_kind(self, kind: str) -> dict[str, Entity]:
        return self.entities.get(kind, {})

    @property
    def locations(self) -> dict[str, Entity]:
        return self.of_kind("location")

    @property
    def npcs(self) -> dict[str, Entity]:
        return self.of_kind("npc")

    @property
    def chapters(self) -> dict[str, Entity]:
        return self.of_kind("chapter")

    def entity(self, entity_id: str, kind: str | None = None) -> Entity | None:
        kinds = [kind] if kind else list(self.entities)
        for k in kinds:
            found = self.entities.get(k, {}).get(entity_id)
            if found is not None:
                return found
        return None

    def __iter__(self) -> Iterator[Entity]:
        for bucket in self.entities.values():
            yield from bucket.values()

    # ---- the state the module ships with ----------------------------------

    @property
    def bindings(self) -> dict[str, Any]:
        """Optional declarative mapping from a module's own flags onto mechanics."""
        return self.metadata.get("state_bindings") or {}

    @property
    def start_location(self) -> str | None:
        current = self.metadata.get("current_state") or {}
        return current.get("location") or next(iter(self.locations), None)

    @property
    def start_chapter(self) -> str | None:
        current = self.metadata.get("current_state") or {}
        return current.get("chapter") or next(iter(self.chapters), None)

    def world_flags(self) -> dict[str, Any]:
        """Everything in ``adventure.json`` the runtime doesn't interpret.

        Kept verbatim on the campaign so a module never loses state just because
        the engine didn't recognise its shape.
        """
        return {k: v for k, v in self.metadata.items() if k not in KNOWN_METADATA_KEYS}

    def bound_npc_states(self) -> dict[str, dict[str, Any]]:
        """Resolve ``state_bindings.npcs`` against the module's own flags.

        Each binding is ``{"npc": id, "field": name, "flag": "dotted.path"}``
        with an optional ``map`` from raw values to the value to store. This is
        how a module tells the runtime "my `black_spider_plot.gundren_status`
        means Gundren's status" without a line of adventure-specific code.
        """
        out: dict[str, dict[str, Any]] = {}
        for binding in self.bindings.get("npcs", []) or []:
            npc_id, field_name = binding.get("npc"), binding.get("field")
            if not npc_id or not field_name:
                continue
            value = dig(self.metadata, binding.get("flag", ""))
            if value is None:
                value = binding.get("default")
            if value is None:
                continue
            value = (binding.get("map") or {}).get(str(value), value)
            if field_name == "status":
                value = normalize_status(value)
            out.setdefault(npc_id, {})[field_name] = value
        return out

    def bound_clocks(self) -> list[dict[str, Any]]:
        """``state_bindings.clocks`` plus any plain ``clocks`` list in metadata."""
        clocks: list[dict[str, Any]] = []
        for spec in (self.metadata.get("clocks") or []) + (self.bindings.get("clocks") or []):
            name = spec.get("name")
            if not name:
                continue
            filled = spec.get("filled")
            if filled is None and spec.get("flag"):
                filled = dig(self.metadata, spec["flag"])
            clocks.append(
                {
                    "id": spec.get("id") or _slug(name),
                    "name": name,
                    "size": int(spec.get("size", 4)),
                    "filled": int(filled or 0),
                    "owner_faction": spec.get("owner_faction"),
                    "on_complete": spec.get("on_complete") or {},
                    "hidden": bool(spec.get("hidden", True)),
                }
            )
        return clocks

    def bound_canon(self) -> list[dict[str, Any]]:
        """``state_bindings.canon`` — flags a module wants stated as canon facts.

        ``{"flag": "plot.villain_name", "text": "The villain is {value}."}``
        """
        facts: list[dict[str, Any]] = []
        for spec in self.bindings.get("canon", []) or []:
            template = spec.get("text")
            if not template:
                continue
            value = dig(self.metadata, spec.get("flag", "")) if spec.get("flag") else None
            if spec.get("flag") and value in (None, "", False):
                continue
            facts.append(
                {
                    "text": template.format(value=value),
                    "entities": spec.get("entities", []),
                    "source": "module",
                }
            )
        return facts


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in str(text).lower()).strip("_")


def available_modules() -> list[dict[str, Any]]:
    """Every module the runtime can see, across all search paths."""
    found: dict[str, dict[str, Any]] = {}
    for base in SEARCH_PATHS:
        if not base.is_dir():
            continue
        for candidate in sorted(base.iterdir()):
            if not (candidate / "adventure.json").exists() or candidate.name in found:
                continue
            try:
                meta = _read_json(candidate / "adventure.json")
            except ModuleError:
                continue
            found[candidate.name] = {
                "id": meta.get("id", candidate.name),
                "name": meta.get("name", candidate.name),
                "path": str(candidate),
                "level_range": meta.get("level_range"),
            }
    return list(found.values())
