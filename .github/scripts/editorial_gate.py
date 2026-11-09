"""Fail a pull request that changes Ross-owned paths unless it has the `ross-approved` label.

Ross-owned paths are read from .github/CODEOWNERS (lines owned by @rmvdw).
Decision 17 in docs/decisions.md: Ross adds the label, or an agent adds it
quoting his explicit approval verbatim.

Decision 18: draft indicators and briefings don't need Ross. A file under one of
DRAFT_EXEMPT_PREFIXES is exempt when it is `status: draft` on both sides of the
change (or new as a draft, or a deleted draft). Publishing it, or changing anything
already published, still needs the label. Unreadable status counts as published.

All agents currently act through Ross's GitHub account, so this is a guard
against mistakes, not a security boundary.

    python .github/scripts/editorial_gate.py [--codeowners PATH]
        [--base-dir DIR --head-dir DIR] <changed_files.txt> <labels.txt>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LABEL = "ross-approved"
OWNER = "@rmvdw"
DRAFT_EXEMPT_PREFIXES = ("indicators/", "briefings/")
STATUS = re.compile(r"^status:\s*['\"]?([A-Za-z_]+)", re.MULTILINE)


def status_of(root: Path | None, path: str) -> str | None:
    """'draft', 'published', other text, 'absent' if the file doesn't exist, None if unreadable."""
    if root is None:
        return None
    f = root / path
    if not f.exists():
        return "absent"
    text = f.read_text(errors="replace")
    if path.endswith(".md"):  # briefings: only the front matter counts
        parts = text.split("\n---", 1)
        if not text.startswith("---") or len(parts) < 2:
            return None
        text = parts[0]
    found = STATUS.findall(text)
    # Exactly one top-level status line. Duplicates are ambiguous (a YAML loader keeps
    # the last one), so they count as unreadable and stay gated.
    return found[0] if len(found) == 1 else None


def draft_only(path: str, base_dir: Path | None, head_dir: Path | None) -> bool:
    if not path.startswith(DRAFT_EXEMPT_PREFIXES):
        return False
    before, after = status_of(base_dir, path), status_of(head_dir, path)
    sides = {before, after}
    return "draft" in sides and sides <= {"draft", "absent"}


def owned_patterns(codeowners: str) -> list[str]:
    out = []
    for line in codeowners.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pattern, *owners = line.split()
        if OWNER in owners:
            out.append(pattern.lstrip("/"))
    return out


def is_owned(path: str, patterns: list[str]) -> bool:
    for p in patterns:
        if p.endswith("/"):
            if path.startswith(p):
                return True
        elif path == p:
            return True
    return False


def main(
    changed_file: str,
    labels_file: str,
    codeowners: str = ".github/CODEOWNERS",
    base_dir: str | None = None,
    head_dir: str | None = None,
) -> int:
    patterns = owned_patterns(Path(codeowners).read_text())
    changed = [x for x in Path(changed_file).read_text().splitlines() if x.strip()]
    labels = {x.strip() for x in Path(labels_file).read_text().splitlines() if x.strip()}
    base = Path(base_dir) if base_dir else None
    head = Path(head_dir) if head_dir else None
    owned = [f for f in changed if is_owned(f, patterns)]
    drafts = [f for f in owned if draft_only(f, base, head)]
    if drafts:
        print("Draft-only changes, no approval needed (decision 18):\n  " + "\n  ".join(drafts))
    owned = [f for f in owned if f not in drafts]
    if not owned:
        print("Editorial gate: no Ross-owned paths changed.")
        return 0
    print("Ross-owned paths changed:\n  " + "\n  ".join(owned))
    if LABEL in labels:
        print(f"Editorial gate: passed ('{LABEL}' label present).")
        return 0
    print(f"Editorial gate: BLOCKED until Ross adds the '{LABEL}' label.")
    return 1


if __name__ == "__main__":
    args = sys.argv[1:]
    opts = {"--codeowners": ".github/CODEOWNERS", "--base-dir": None, "--head-dir": None}
    while args and args[0] in opts:
        opts[args[0]], args = args[1], args[2:]
    sys.exit(main(args[0], args[1], opts["--codeowners"], opts["--base-dir"], opts["--head-dir"]))
