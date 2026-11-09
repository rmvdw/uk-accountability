"""Briefings: question-led explainers built from the indicator data (decision 15, #13).

A briefing is `briefings/<id>.md`: YAML front matter, then a Markdown body in which
numbers are written as template calls (`{{ num("net_migration") }}`), never typed.

Editions keep data and wording together (strategy review 4c):
- A **candidate** is rendered from the current data and the current text. Review
  previews show candidates.
- `ukdash edition <id>` freezes a candidate into `briefings/editions/<id>/<edition>.json`:
  the rendered page, every fact used, and the source vintages. Publishing means setting
  `status: published` and `published_edition: <edition>` in the front matter, which
  needs Ross (decision 18). Production renders only the frozen edition, so a data
  refresh never changes published wording; it produces a new candidate for review.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import markdown as md
import yaml
from jinja2 import Environment, StrictUndefined
from markupsafe import Markup

from . import chart
from .compare import UK, series
from .project import Project
from .schema import TOTAL, Observation, period_ordinal

FRONT = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
STATUS_LINE = re.compile(r"^status:", re.M)
TO_VERIFY = "[TO VERIFY"
REQUIRED = ("id", "title", "status", "standfirst", "indicators")


@dataclass
class Briefing:
    id: str
    title: str
    status: str
    standfirst: str
    indicators: list[str]
    body: str
    path: Path
    published_edition: str | None = None
    front: dict = field(default_factory=dict)


def parse(path: Path) -> Briefing:
    text = path.read_text(encoding="utf-8")
    m = FRONT.match(text)
    if not m:
        raise ValueError(f"{path.name}: must start with '---' front matter")
    front_text, body = m.groups()
    if len(STATUS_LINE.findall(front_text)) != 1:
        raise ValueError(f"{path.name}: front matter needs exactly one status line")
    front = yaml.safe_load(front_text) or {}
    missing = [k for k in REQUIRED if k not in front]
    if missing:
        raise ValueError(f"{path.name}: front matter missing {missing}")
    if front["status"] not in ("draft", "published"):
        raise ValueError(f"{path.name}: status must be draft or published")
    if front["id"] != path.stem:
        raise ValueError(f"{path.name}: id must match the file name")
    if front["status"] == "published" and not front.get("published_edition"):
        raise ValueError(f"{path.name}: published briefings need published_edition")
    return Briefing(
        id=front["id"],
        title=front["title"],
        status=front["status"],
        standfirst=front["standfirst"],
        indicators=list(front["indicators"]),
        body=body,
        path=path,
        published_edition=front.get("published_edition"),
        front=front,
    )


def load_all(root: Path) -> dict[str, Briefing]:
    d = root / "briefings"
    if not d.exists():
        return {}
    return {b.id: b for b in (parse(p) for p in sorted(d.glob("*.md")))}


def edition_path(root: Path, briefing_id: str, edition: str) -> Path:
    return root / "briefings" / "editions" / briefing_id / f"{edition}.json"


# --- facts --------------------------------------------------------------------


def _fmt(v: float, decimals: int = 0) -> str:
    """Thousands separators and a true minus sign (−), which reads better than a hyphen."""
    return f"{v:,.{decimals}f}".replace("-", "\u2212")


class Facts:
    """Template functions for briefing text. Every number used is recorded, so an edition
    can show where each came from and a later refresh can say what would change."""

    def __init__(self, project: Project, allowed: list[str], period_label):
        self.p = project
        self.allowed = set(allowed)
        self.period_label = period_label
        self.used: dict[str, dict] = {}
        self._rows: dict[str, list[Observation]] = {}

    def _series(self, ind: str, breakdown: str = TOTAL) -> list[Observation]:
        if ind not in self.allowed:
            raise ValueError(f"indicator {ind!r} is not listed in the briefing's front matter")
        if ind not in self._rows:
            self._rows[ind] = self.p.read_observations(ind)
        s = [o for o in series(self._rows[ind], UK, breakdown) if o.value is not None]
        if not s:
            raise ValueError(f"{ind}/{breakdown}: no data")
        return s

    def obs(self, ind: str, period: str = "latest", breakdown: str = TOTAL) -> Observation:
        s = self._series(ind, breakdown)
        if period == "latest":
            o = s[-1]
        elif period == "year_earlier":
            o = self._offset(s, s[-1], 12)
        else:
            matches = [x for x in s if x.period == period]
            if not matches:
                raise ValueError(f"{ind}/{breakdown}: no value for {period}")
            o = matches[0]
        key = f"{ind}.{breakdown}.{o.period}"
        self.used[key] = {
            "indicator": ind,
            "breakdown": breakdown,
            "period": o.period,
            "value": o.value,
            "status": o.status,
        }
        return o

    def _offset(self, s: list[Observation], o: Observation, months: int) -> Observation:
        target = period_ordinal(o.period, o.frequency) - months
        for x in s:
            if period_ordinal(x.period, x.frequency) == target:
                return x
        raise ValueError(f"no value {months} months before {o.period}")

    # Functions available in briefing text --------------------------------------

    def num(self, ind, period="latest", breakdown=TOTAL, abs_value=False) -> str:
        o = self.obs(ind, period, breakdown)
        d = self.p.indicators[ind].decimals
        return _fmt(abs(o.value) if abs_value else o.value, d)

    def when(self, ind, period="latest", breakdown=TOTAL) -> str:
        o = self.obs(ind, period, breakdown)
        return self.period_label(o.period, o.frequency)

    def change(self, ind, breakdown=TOTAL, since="year_earlier") -> dict:
        new = self.obs(ind, "latest", breakdown)
        old = self.obs(ind, since, breakdown)
        diff = new.value - old.value
        d = self.p.indicators[ind].decimals
        verb = "rose" if diff > 0 else "fell" if diff < 0 else "was unchanged"
        pct = (diff / abs(old.value) * 100) if old.value else None
        return {
            "verb": verb,
            "by": _fmt(abs(diff), d),
            "from": _fmt(old.value, d),
            "from_when": self.period_label(old.period, old.frequency),
            "pct": f"{abs(pct):.0f}%" if pct is not None else "n/a",
            "up": diff > 0,
        }

    def peak(self, ind, breakdown=TOTAL) -> dict:
        s = self._series(ind, breakdown)
        o = max(s, key=lambda x: x.value)
        self.obs(ind, o.period, breakdown)  # record it
        d = self.p.indicators[ind].decimals
        return {"value": _fmt(o.value, d), "when": self.period_label(o.period, o.frequency)}

    def revisions(self, ind: str = "net_migration", flow: str = "Net migration") -> list[dict]:
        """ONS's own revision history for each period it has re-estimated (Table 5 of the
        saved workbook): first published estimate versus the latest."""
        from .sources.ons_ltim import parse_revisions

        if ind not in self.allowed:
            raise ValueError(f"indicator {ind!r} is not listed in the briefing's front matter")
        entry = next((e for e in self.p.read_manifest() if e.indicator_id == ind), None)
        if entry is None:
            raise ValueError(f"{ind}: no saved source file")
        rows = parse_revisions((self.p.root / entry.path).read_bytes())
        by_period: dict[str, list[dict]] = {}
        for r in rows:
            by_period.setdefault(r["period"], []).append(r)
        out = []
        d = self.p.indicators[ind].decimals
        for period, ests in sorted(by_period.items()):
            if len(ests) < 2:
                continue
            first, last = ests[0], ests[-1]
            a, b = first["values"][(flow, TOTAL)], last["values"][(flow, TOTAL)]
            if a is None or b is None:
                continue
            self.used[f"revision.{ind}.{period}"] = {
                "indicator": ind, "breakdown": TOTAL, "period": period, "value": b,
                "status": f"first {a:.0f} ({first['publication']}), now {last['publication']}",
            }  # fmt: skip
            out.append(
                {
                    "when": self.period_label(period, "Y12"),
                    "first": _fmt(a, d),
                    "first_pub": first["publication"],
                    "latest": _fmt(b, d),
                    "latest_pub": last["publication"],
                    "change": ("+" if b > a else "−" if b < a else "±") + _fmt(abs(b - a), d),
                    "abs_change": abs(b - a),
                }
            )
        return out

    def largest_revision(self, ind: str = "net_migration") -> str:
        revs = self.revisions(ind)
        if not revs:
            raise ValueError(f"{ind}: no revisions to describe")
        return _fmt(max(r["abs_change"] for r in revs), self.p.indicators[ind].decimals)

    def lines(self, specs: list[list[str]], unit: str = "people") -> Markup:
        """specs: [[indicator, breakdown, label, css class], ...] drawn on one chart."""
        parts = []
        for ind, bd, label, cls in specs:
            s = self._series(ind, bd)
            for o in s:
                self.used.setdefault(
                    f"{ind}.{bd}.{o.period}",
                    {
                        "indicator": ind,
                        "breakdown": bd,
                        "period": o.period,
                        "value": o.value,
                        "status": o.status,
                        "chart": True,
                    },  # fmt: skip
                )
            parts.append((label, s, cls))
        svg = chart.multi_line_chart(
            parts,
            unit,
            0,
            period_label=lambda p: self.period_label(p, parts[0][1][0].frequency, True),
        )
        return Markup(f'\n<div class="chart-block">{svg}</div>\n')

    def bars(self, ind: str, breakdowns: dict[str, str], period: str = "latest") -> Markup:
        vals = []
        for bd in breakdowns:
            o = self.obs(ind, period, bd)
            vals.append((bd, o.value))
        vals.sort(key=lambda kv: kv[1], reverse=True)
        o = self.obs(ind, period)
        svg = chart.bar_chart(
            vals, breakdowns, "", self.p.indicators[ind].unit, 0,
            self.period_label(o.period, o.frequency),
        )  # fmt: skip
        return Markup(f'\n<div class="chart-block">{svg}</div>\n')


# --- rendering ------------------------------------------------------------------


def sources_for(project: Project, b: Briefing) -> list[dict]:
    manifest = {e.indicator_id: e for e in project.read_manifest()}
    out, seen = [], set()
    for ind in b.indicators:
        d = project.indicators[ind]
        e = manifest.get(ind)
        key = (d.source.publisher, d.source.dataset, e.request if e else None)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "publisher": d.source.publisher,
                "dataset": d.source.dataset,
                "url": d.source.url,
                "file": e.request if e else None,
                "vintage": _vintage(e.vintage) if e else None,
                "released": e.publisher_release_date if e else None,
                "retrieved": e.retrieved_at.isoformat() if e else None,
                "sha256": e.sha256 if e else None,
                "licence": d.source.licence,
                "attribution": d.source.attribution,
            }
        )
    return out


def _vintage(v: str | None) -> str | None:
    """Readers see 'year ending', never the 'YE' shorthand older manifests stored."""
    return re.sub(r"^YE ", "year ending ", v) if v else v


def attribution_lines(sources: list[dict]) -> list[str]:
    """Each required attribution once, e.g. 'Source: Home Office, ... (OGL v3.0)'."""
    out = []
    for s in sources:
        line = f"{s['attribution']} ({s['licence']})"
        if line not in out:
            out.append(line)
    return out


def source_summary(sources: list[dict]) -> list[str]:
    """One line per publisher edition, e.g. 'Home Office, year ending June 2026'."""
    seen, out = set(), []
    for s in sources:
        line = s["publisher"] + (f", {s['vintage']}" if s.get("vintage") else "")
        if s.get("released"):
            line += f" (published {s['released']})"
        if line not in seen:
            seen.add(line)
            out.append(line)
    return out


def render_candidate(project: Project, b: Briefing, period_label, extra: dict | None = None):
    """(body HTML, facts used, sources) from current data and current text."""
    facts = Facts(project, b.indicators, period_label)
    env = Environment(undefined=StrictUndefined, autoescape=False)
    ctx = {
        "num": facts.num,
        "when": facts.when,
        "change": facts.change,
        "peak": facts.peak,
        "lines": facts.lines,
        "bars": facts.bars,
        "revisions": facts.revisions,
        "largest_revision": facts.largest_revision,
        **(extra or {}),
    }
    text = env.from_string(b.body).render(**ctx)
    html = md.markdown(text, extensions=["tables", "md_in_html"])
    return html, facts.used, sources_for(project, b)


def freeze(root: Path, project: Project, b: Briefing, period_label, extra=None) -> Path:
    html, facts, sources = render_candidate(project, b, period_label, extra)
    if TO_VERIFY in html:
        raise ValueError(f"{b.id}: remove every {TO_VERIFY} marker before freezing an edition")
    now = datetime.now(UTC).replace(microsecond=0)
    edition = now.strftime("%Y-%m-%d-%H%M")
    path = edition_path(root, b.id, edition)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "briefing": b.id,
        "edition": edition,
        "frozen_at": now.isoformat(),
        "title": b.title,
        "standfirst": b.standfirst,
        "body_html": html,
        "facts": facts,
        "sources": sources,
    }
    try:  # "x": never replace an existing edition, even one frozen a moment ago
        with path.open("x", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, indent=2) + "\n")
    except FileExistsError:
        raise ValueError(
            f"{b.id}: edition {edition} already exists; editions are never replaced. "
            "Wait a minute and run it again."
        ) from None
    return path


def load_edition(root: Path, b: Briefing) -> dict:
    path = edition_path(root, b.id, b.published_edition or "")
    if not path.exists():
        raise ValueError(f"{b.id}: published edition {b.published_edition!r} not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("briefing") != b.id:
        raise ValueError(f"{path.name}: edition belongs to {data.get('briefing')!r}")
    if TO_VERIFY in data.get("body_html", ""):
        raise ValueError(f"{path.name}: contains {TO_VERIFY} markers")
    return data


def _show(v) -> str:
    """Exact enough to see any change: 171000 -> '171,000', 4.8 -> '4.8'."""
    if v is None:
        return "missing"
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.4g}"


def diff_facts(published: dict, candidate: dict) -> list[str]:
    """Plain-English list of what a new candidate would change versus the published edition."""
    changes = []
    charted = []
    for k, new in sorted(candidate.items()):
        old = published.get(k)
        if new.get("chart"):
            if old is None or old["value"] != new["value"] or old["status"] != new["status"]:
                charted.append(k)
            continue
        if old is None:
            changes.append(f"new figure used: {k} = {_show(new['value'])}")
        elif old["value"] != new["value"] or old["status"] != new["status"]:
            changes.append(
                f"{k}: {_show(old['value'])} ({old['status'] or 'final'}) → "
                f"{_show(new['value'])} ({new['status'] or 'final'})"
            )
    for k in sorted(set(published) - set(candidate)):
        if published[k].get("chart"):
            charted.append(k)
        else:
            changes.append(f"figure no longer used: {k}")
    if charted:
        sample = ", ".join(sorted(charted)[:3]) + (", ..." if len(charted) > 3 else "")
        n = len(charted)
        changes.append(f"charts: {n} plotted point(s) new, revised or dropped ({sample})")
    return changes
