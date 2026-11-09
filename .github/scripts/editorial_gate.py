"""Fail a pull request that changes Ross-owned paths unless it has the `ross-approved` label.

Ross-owned paths are read from .github/CODEOWNERS (lines owned by @rmvdw).
Decision 17 in docs/decisions.md: Ross adds the label, or an agent adds it quoting his explicit approval verbatim.

All agents currently act through Ross's GitHub account, so this is a guard
against mistakes, not a security boundary.

    python .github/scripts/editorial_gate.py [--codeowners PATH] <changed_files.txt> <labels.txt>
"""

from __future__ import annotations

import sys
from pathlib import Path

LABEL = "ross-approved"
OWNER = "@rmvdw"


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


def main(changed_file: str, labels_file: str, codeowners: str = ".github/CODEOWNERS") -> int:
    patterns = owned_patterns(Path(codeowners).read_text())
    changed = [x for x in Path(changed_file).read_text().splitlines() if x.strip()]
    labels = {x.strip() for x in Path(labels_file).read_text().splitlines() if x.strip()}
    owned = [f for f in changed if is_owned(f, patterns)]
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
    codeowners = ".github/CODEOWNERS"
    if args[:1] == ["--codeowners"]:
        codeowners, args = args[1], args[2:]
    sys.exit(main(args[0], args[1], codeowners))
