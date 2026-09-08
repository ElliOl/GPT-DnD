#!/usr/bin/env python3
"""
Check an adventure module against the runtime's contract.

    python scripts/validate_module.py                     # every module found
    python scripts/validate_module.py my_module           # one by id
    python scripts/validate_module.py path/to/my_module   # one by path

Exits non-zero if any module has errors, so it drops into CI unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.content.module import Module, ModuleError, available_modules  # noqa: E402
from backend.content.schema import validate_path  # noqa: E402


def main() -> int:
    targets: list[Path] = []
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            path = Path(arg)
            if not path.is_dir():
                try:
                    path = Module.find(arg)
                except ModuleError as exc:
                    print(exc)
                    return 2
            targets.append(path)
    else:
        targets = [Path(m["path"]) for m in available_modules()]
        if not targets:
            print("No modules found.")
            return 1

    failed = False
    for path in targets:
        report = validate_path(path)
        print(report.render())
        print()
        failed = failed or not report.ok
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
