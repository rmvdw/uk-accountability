"""Command line entry points used by the Makefile.

python -m ukdash check                       validate config, registry and saved data (offline)
python -m ukdash build                       build the static site into site/ (offline)
python -m ukdash refresh                     fetch all published indicators, promote if all pass
python -m ukdash refresh --indicator ID      fetch named indicators, drafts included
python -m ukdash import-manual --indicator ID --file PATH --request "URL"
                                             seed an indicator from a hand-downloaded official file
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .build import build
from .project import REPO_ROOT, Project
from .validate import validate


def _report(r, verb: str) -> int:
    for ind, outcome in sorted(r.results.items()):
        print(f"{ind}: {outcome}")
    for w in r.warnings:
        print(f"WARNING {w}", file=sys.stderr)
    for e in r.errors:
        print(f"ERROR {e}", file=sys.stderr)
    if r.ok:
        print(f"{verb}: promoted")
    elif r.data_intact:
        print(f"{verb}: FAILED, saved data unchanged")
    else:
        print(f"{verb}: FAILED and data/ may be inconsistent: see errors above")
    return 0 if r.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ukdash")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    b = sub.add_parser("build")
    b.add_argument("--out", type=Path, default=REPO_ROOT / "site")
    b.add_argument("--drafts", action="store_true", help="include drafts (review previews only)")
    r = sub.add_parser("refresh")
    r.add_argument("--indicator", action="append", help="limit to this indicator (drafts allowed)")
    m = sub.add_parser("import-manual")
    m.add_argument("--indicator", required=True)
    m.add_argument("--file", type=Path, required=True)
    m.add_argument(
        "--request", required=True, help="URL or description of where the file came from"
    )
    m.add_argument("--release-date", help="publisher release date, if known (YYYY-MM-DD)")
    args = parser.parse_args(argv)

    if args.cmd == "refresh":
        from .refresh import refresh

        return _report(refresh(only=args.indicator), "refresh")

    if args.cmd == "import-manual":
        from .refresh import import_manual

        result = import_manual(
            args.indicator, args.file, args.request, publisher_release_date=args.release_date
        )
        return _report(result, "import-manual")

    project = Project.load()
    if args.cmd == "check":
        errors = validate(project)
        n = len(project.indicators)
        if not errors:
            print(f"check: OK ({n} indicator(s), {len(project.published())} published)")
    else:
        errors = build(project, args.out, include_drafts=args.drafts)
        if not errors:
            print(f"build: OK -> {args.out}")

    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
