"""
Module validation.

The contract is deliberately thin, so most of what this reports is *warnings* —
things that will load but will play badly (a location nothing links to, an NPC
referenced by a quest that doesn't exist). Only a handful of things are errors.

Run it before dropping a new module in:

    python scripts/validate_module.py my_module
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .module import ENTITY_DIRS, Module, ModuleError, _read_json


@dataclass
class Report:
    module_id: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        lines = [f"module: {self.module_id}"]
        lines += [f"  {kind:<12} {n}" for kind, n in sorted(self.counts.items())]
        for e in self.errors:
            lines.append(f"  ERROR   {e}")
        for w in self.warnings:
            lines.append(f"  warning {w}")
        lines.append("  OK" if self.ok else f"  {len(self.errors)} error(s)")
        return "\n".join(lines)


def validate_path(root: Path) -> Report:
    """Validate a module directory without loading it into the runtime."""
    report = Report(module_id=root.name)

    manifest = root / "adventure.json"
    if not manifest.exists():
        report.errors.append(f"missing {manifest.name} — a module must have one")
        return report

    try:
        metadata = _read_json(manifest)
    except ModuleError as exc:
        report.errors.append(str(exc))
        return report

    for required in ("id", "name"):
        if not metadata.get(required):
            report.errors.append(f"adventure.json: {required!r} is required")

    ids: dict[str, set[str]] = {}
    for dirname, kind in ENTITY_DIRS.items():
        directory = root / dirname
        seen: set[str] = set()
        if not directory.is_dir():
            ids[kind] = seen
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                data = _read_json(path)
            except ModuleError as exc:
                report.errors.append(str(exc))
                continue
            entity_id = str(data.get("id") or path.stem)
            if entity_id in seen:
                report.errors.append(f"{dirname}/: duplicate id {entity_id!r}")
            seen.add(entity_id)
            if not data.get("id"):
                report.warnings.append(f"{path.name}: no 'id', using the filename {entity_id!r}")
            if not data.get("name"):
                report.warnings.append(f"{dirname}/{entity_id}: no 'name'")
        ids[kind] = seen
        report.counts[kind] = len(seen)

    _check_references(metadata, ids, report)
    _check_bindings(metadata, ids, report)
    return report


def _check_references(metadata: dict[str, Any], ids: dict[str, set[str]], report: Report) -> None:
    current = metadata.get("current_state") or {}
    start = current.get("location")
    if start and ids["location"] and start not in ids["location"]:
        report.warnings.append(f"current_state.location {start!r} has no locations/ file")
    chapter = current.get("chapter")
    if chapter and ids["chapter"] and chapter not in ids["chapter"]:
        report.warnings.append(f"current_state.chapter {chapter!r} has no chapters/ file")

    for loc in metadata.get("discovered_locations", []) or []:
        if ids["location"] and loc not in ids["location"]:
            report.warnings.append(f"discovered_locations: {loc!r} has no locations/ file")
    for npc in metadata.get("met_npcs", []) or []:
        if ids["npc"] and npc not in ids["npc"]:
            report.warnings.append(f"met_npcs: {npc!r} has no npcs/ file")

    for quest in metadata.get("active_quests", []) or []:
        if not quest.get("id") and not quest.get("name"):
            report.errors.append("active_quests: every quest needs an 'id' or a 'name'")


def _check_bindings(metadata: dict[str, Any], ids: dict[str, set[str]], report: Report) -> None:
    bindings = metadata.get("state_bindings") or {}
    if not isinstance(bindings, dict):
        report.errors.append("state_bindings must be an object")
        return

    for binding in bindings.get("npcs", []) or []:
        npc_id = binding.get("npc")
        if not npc_id:
            report.errors.append("state_bindings.npcs: each entry needs 'npc'")
        elif ids["npc"] and npc_id not in ids["npc"]:
            report.warnings.append(f"state_bindings.npcs: {npc_id!r} has no npcs/ file")
        if not binding.get("field"):
            report.errors.append(f"state_bindings.npcs[{npc_id}]: needs 'field'")
        if not binding.get("flag") and binding.get("default") is None:
            report.errors.append(f"state_bindings.npcs[{npc_id}]: needs 'flag' or 'default'")

    for spec in bindings.get("clocks", []) or []:
        if not spec.get("name"):
            report.errors.append("state_bindings.clocks: each clock needs a 'name'")
        if int(spec.get("size", 4)) < 1:
            report.errors.append(f"state_bindings.clocks[{spec.get('name')}]: size must be >= 1")

    for spec in bindings.get("canon", []) or []:
        if not spec.get("text"):
            report.errors.append("state_bindings.canon: each entry needs 'text'")

    clocks = bindings.get("clocks", []) or []
    if len(clocks) > 6:
        report.warnings.append(
            f"{len(clocks)} clocks — more than about six reads as noise rather than pressure"
        )


def validate(module_id: str) -> Report:
    return validate_path(Module.find(module_id))
