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

from .build import build, cloudflare_preview_branch
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
    e = sub.add_parser("edition", help="freeze a briefing's current candidate as an edition")
    e.add_argument("briefing")
    bd = sub.add_parser("briefing-diff", help="what a new candidate would change")
    bd.add_argument("briefing")
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

    if args.cmd in ("edition", "briefing-diff"):
        from . import briefing
        from .build import period_label

        project = Project.load()
        b = briefing.load_all(project.root).get(args.briefing)
        if b is None:
            print(f"ERROR no briefing {args.briefing!r}", file=sys.stderr)
            return 1
        if args.cmd == "edition":
            path = briefing.freeze(project.root, project, b, period_label)
            print(f"edition: wrote {path.relative_to(project.root)}")
            print("To publish: set status: published and published_edition in the front matter.")
            return 0
        if not b.published_edition:
            print("briefing-diff: no published edition yet")
            return 0
        _, facts, _ = briefing.render_candidate(project, b, period_label)
        changes = briefing.diff_facts(briefing.load_edition(project.root, b)["facts"], facts)
        print("\n".join(changes) if changes else "briefing-diff: no changes")
        return 0

    project = Project.load()
    if args.cmd == "check":
        errors = validate(project)
        n = len(project.indicators)
        if not errors:
            print(f"check: OK ({n} indicator(s), {len(project.published())} published)")
    else:
        drafts = args.drafts
        preview_branch = cloudflare_preview_branch()
        if preview_branch and not drafts:
            print(f"build: Cloudflare preview of branch {preview_branch!r}: including drafts")
            drafts = True
        errors = build(project, args.out, include_drafts=drafts)
        if not errors:
            print(f"build: OK -> {args.out}")

    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
