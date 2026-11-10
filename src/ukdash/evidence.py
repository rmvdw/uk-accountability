"""Evidence records: dated survey results and cited figures (decision 20).

Survey results are what people said at a date, never presented as fact. A cited figure
is a single number taken from a document that is not a statistical series (for example
one line of a department's accounts), with its exact scope. Both live as reviewed YAML
in evidence/<id>.yml so briefing prose never types a number, and each displayed value
links to its full record at /evidence/<id>/.
"""

from __future__ import annotations

from pathlib import Path

import yaml

COMMON = ["id", "kind", "title", "source", "source_url", "checked"]
REQUIRED = {
    # Codex's minimum survey record (#13): pollster, commissioner, fieldwork and
    # publication dates, population, mode, base, wording, weighting, statistic,
    # don't-knows, page, reuse.
    "survey": COMMON + [
        "pollster", "commissioner", "fieldwork_start", "fieldwork_end", "published",
        "population", "mode", "sample_size", "question_base", "question", "results",
        "statistic", "dont_know", "weighting", "pages", "reuse",
    ],
    "cited_figure": COMMON + ["value", "unit", "period", "scope", "status", "location",
                              "licence"],
}  # fmt: skip


def load_all(root: Path) -> dict[str, dict]:
    d = root / "evidence"
    out = {}
    for f in sorted(d.glob("*.yml")) if d.exists() else []:
        rec = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        kind = rec.get("kind")
        if kind not in REQUIRED:
            raise ValueError(f"{f.name}: kind must be one of {sorted(REQUIRED)}")
        missing = [k for k in REQUIRED[kind] if rec.get(k) in (None, "")]
        if missing:
            raise ValueError(f"{f.name}: missing {missing}")
        if rec["id"] != f.stem:
            raise ValueError(f"{f.name}: id must match the file name")
        if kind == "survey":
            if rec["fieldwork_end"] < rec["fieldwork_start"]:
                raise ValueError(f"{f.name}: fieldwork ends before it starts")
            for r in rec["results"]:
                if "answer" not in r or "percent" not in r:
                    raise ValueError(f"{f.name}: each result needs answer and percent")
                if r["percent"] is None and not r.get("note"):
                    raise ValueError(f"{f.name}: unreported percent needs a note")
        out[rec["id"]] = rec
    return out


def money(value: float, unit: str) -> str:
    """'£4.18 billion' from 4181193 GBP thousand."""
    scale = {"GBP": 1, "GBP thousand": 1e3, "GBP million": 1e6}
    if unit not in scale:
        raise ValueError(f"unsupported unit {unit!r}")
    pounds = value * scale[unit]
    if pounds >= 1e9:
        return f"£{pounds / 1e9:.2f} billion"
    if pounds >= 1e6:
        return f"£{pounds / 1e6:.0f} million"
    return f"£{pounds:,.0f}"
