"""Command line entry points used by the Makefile.

python -m ukdash check     validate config, registry and saved data (offline)
python -m ukdash build     build the static site into site/ (offline)
python -m ukdash refresh   fetch live data, validate, build, promote if all pass
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .build import build
from .project import REPO_ROOT, Project
from .validate import validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ukdash")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    b = sub.add_parser("build")
    b.add_argument("--out", type=Path, default=REPO_ROOT / "site")
    sub.add_parser("refresh")
    args = parser.parse_args(argv)

    if args.cmd == "refresh":
        from .refresh import refresh

        r = refresh()
        for ind, outcome in sorted(r.results.items()):
            print(f"{ind}: {outcome}")
        for e in r.errors:
            print(f"ERROR {e}", file=sys.stderr)
        print("refresh: promoted" if r.ok else "refresh: FAILED, published data unchanged")
        return 0 if r.ok else 1

    project = Project.load()
    if args.cmd == "check":
        errors = validate(project)
        n = len(project.indicators)
        if not errors:
            print(f"check: OK ({n} indicator(s), {len(project.published())} published)")
    else:
        errors = build(project, args.out)
        if not errors:
            print(f"build: OK -> {args.out}")

    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
