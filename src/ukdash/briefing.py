"""Briefings: question-led explainers built from the indicator data (decision 15, #13).

A briefing is `briefings/<id>.md`: YAML front matter, then a Markdown body in which
numbers are written as template calls (`{{ num("net_migration") }}`), never typed.

Editions keep data and wording together (strategy review 4c):
- A **candidate** is rendered from the current data and the current text. Review
  previews show candidates.
- `ukdash edition <id>` freezes a candidate into `briefings/editions/<id>/<edition>.json`:
  the rendered page, every fact used, and the source vintages. Publishing means setting
  `status: published` and `published_edition: <edition>` (plus `earlier_editions: [...]`,
  every edition approved before it) in the front matter, which
  needs Ross (decision 18). Production renders only the frozen edition, so a data
  refresh never changes published wording; it produces a new candidate for review.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import markdown as md
import yaml
from jinja2 import Environment, StrictUndefined
from markupsafe import Markup

from . import chart
from .compare import UK, peer_comparison, series
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
    # Editions Ross approved and published before the current one, oldest first. Only
    # these, plus published_edition, are ever public: a frozen file proves nothing
    # about approval (a candidate can be frozen and then rejected).
    earlier_editions: list[str] = field(default_factory=list)
    front: dict = field(default_factory=dict)

    @property
    def public_editions(self) -> list[str]:
        """Every edition approved for publication, oldest first; empty for drafts."""
        if self.status != "published" or not self.published_edition:
            return []
        return [*self.earlier_editions, self.published_edition]


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
    earlier = [str(e) for e in front.get("earlier_editions") or []]
    current = str(front.get("published_edition") or "")
    if earlier and (front["status"] != "published" or earlier != sorted(set(earlier))
                    or any(e >= current for e in earlier)):  # fmt: skip
        raise ValueError(
            f"{path.name}: earlier_editions must be unique, oldest first, older than "
            "published_edition, and only on a published briefing"
        )
    return Briefing(
        id=front["id"],
        title=front["title"],
        status=front["status"],
        standfirst=front["standfirst"],
        indicators=list(front["indicators"]),
        body=body,
        path=path,
        published_edition=front.get("published_edition"),
        earlier_editions=earlier,
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


def latest_entries(project: Project) -> dict:
    """The most recently retrieved manifest entry per indicator. Older files can remain
    in the manifest (entries are keyed by path), so never take the first match."""
    out: dict = {}
    for e in project.read_manifest():
        if e.indicator_id not in out or e.retrieved_at > out[e.indicator_id].retrieved_at:
            out[e.indicator_id] = e
    return out


def _month_year(d) -> str:
    months = ("January February March April May June July August September October "
              "November December").split()  # fmt: skip
    return f"{months[d.month - 1]} {d.year}"


def _pub_order(label: str) -> tuple[int, int]:
    """ONS edition labels such as 'Nov 25' in date order."""
    mon, yy = label.split()
    return 2000 + int(yy), "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split().index(mon)


def _pub_long(label: str) -> str:
    """'Nov 25' -> 'November 2025'."""
    y, m = _pub_order(label)
    months = ("January February March April May June July August September October "
              "November December").split()  # fmt: skip
    return f"{months[m]} {y}"


class Facts:
    """Template functions for briefing text. Every number used is recorded, so an edition
    can show where each came from and a later refresh can say what would change."""

    def __init__(self, project: Project, allowed: list[str], period_label):
        self.p = project
        self.allowed = set(allowed)
        self.period_label = period_label
        self.used: dict[str, dict] = {}
        self._rows: dict[str, list[Observation]] = {}

    def _series(self, ind: str, breakdown: str = TOTAL, keep_missing=False) -> list[Observation]:
        """UK rows for one breakdown. Charts keep explicitly missing rows (keep_missing)
        so the line breaks there; everything else sees only real values."""
        if ind not in self.allowed:
            raise ValueError(f"indicator {ind!r} is not listed in the briefing's front matter")
        if ind not in self._rows:
            self._rows[ind] = self.p.read_observations(ind)
        s = series(self._rows[ind], UK, breakdown)
        if not any(o.value is not None for o in s):
            s = []
        elif not keep_missing:
            s = [o for o in s if o.value is not None]
        if not s:
            raise ValueError(f"{ind}/{breakdown}: no data")
        return s

    def latest(self, ind: str) -> Observation:
        """The indicator's latest period, from all UK rows including missing ones, so
        every breakdown is read at the same period (never silently an older one)."""
        if ind not in self.allowed:
            raise ValueError(f"indicator {ind!r} is not listed in the briefing's front matter")
        if ind not in self._rows:
            self._rows[ind] = self.p.read_observations(ind)
        rows = [o for o in self._rows[ind] if o.geography_id == UK]
        if not rows:
            raise ValueError(f"{ind}: no data")
        return max(rows, key=lambda o: period_ordinal(o.period, o.frequency))

    def obs(self, ind: str, period: str = "latest", breakdown: str = TOTAL) -> Observation:
        s = self._series(ind, breakdown)
        if period in ("latest", "year_earlier"):
            top = self.latest(ind)
            k = period_ordinal(top.period, top.frequency) - (12 if period == "year_earlier" else 0)
            matches = [x for x in s if period_ordinal(x.period, x.frequency) == k]
            if not matches:
                which = top.period if period == "latest" else f"12 months before {top.period}"
                raise ValueError(
                    f"{ind}/{breakdown}: no value for {which}, the indicator's "
                    f"{period.replace('_', ' ')} period (missing or suppressed); "
                    "an older value is never substituted"
                )
            o = matches[0]
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

    def shares(self, ind: str, labels: dict[str, str]) -> list[dict]:
        """Each named breakdown's share of the total at the latest period, largest
        first. Shares use the published total, so unlisted breakdowns stay counted."""
        total = self.obs(ind).value
        out = []
        for bd, label in labels.items():
            o = self.obs(ind, "latest", bd)
            share = 100 * o.value / total
            out.append({"label": label, "share": share, "pct": f"{share:.0f}%",
                        "value": _fmt(o.value, 0)})  # fmt: skip
        return sorted(out, key=lambda r: r["share"], reverse=True)

    def between(self, ind: str, period: str, base: str, breakdown: str = TOTAL) -> dict:
        """A change between two named periods, independent of what is latest: for
        comparisons pinned to what a survey asked about."""
        new, old = self.obs(ind, period, breakdown), self.obs(ind, base, breakdown)
        d = self.p.indicators[ind].decimals
        diff = new.value - old.value
        return {
            "verb": "rose" if diff > 0 else "fell" if diff < 0 else "was unchanged",
            "word": "higher" if diff > 0 else "lower" if diff < 0 else "the same",
            "value": _fmt(new.value, d), "from": _fmt(old.value, d),
            "when": self.period_label(new.period, new.frequency),
            "from_when": self.period_label(old.period, old.frequency),
        }  # fmt: skip

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
        entry = latest_entries(self.p).get(ind)
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
            s = self._series(ind, bd, keep_missing=True)
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

    def release_changes(self, ind: str = "net_migration") -> dict:
        """What the latest ONS edition added and revised, versus the edition before it.

        From the saved workbook alone: Table 5 holds each re-estimated period's value in
        every edition, so the previous edition's figures are its 'previous publication'
        estimates. Verified against a genuine pair (Nov 2025 vs May 2026 workbooks: the
        Table 5 'Nov 25' estimates equal the Nov 2025 Table 1). New periods are those later
        than anything the previous edition published; revised periods are those whose
        estimate changed. Annual change (versus a year earlier) is a different question.
        """
        from .sources.ons_ltim import parse_revisions

        if ind not in self.allowed:
            raise ValueError(f"indicator {ind!r} is not listed in the briefing's front matter")
        entry = latest_entries(self.p).get(ind)
        if entry is None:
            raise ValueError(f"{ind}: no saved source file")
        rows = parse_revisions((self.p.root / entry.path).read_bytes())
        pubs = sorted({r["publication"] for r in rows}, key=_pub_order)
        if len(pubs) < 2:
            raise ValueError(f"{ind}: revision table has fewer than two editions")
        current, previous = pubs[-1], pubs[-2]
        before = {r["period"]: r for r in rows if r["publication"] == previous}
        after = {r["period"]: r for r in rows if r["publication"] == current}
        flows = [
            ("immigration_long_term", "Immigration"),
            ("emigration_long_term", "Emigration"),
            ("net_migration", "Net migration"),
        ]
        last_previous = max(before)
        latest = self.latest(ind)
        new = []
        for o in self._series(ind):
            if period_ordinal(o.period, o.frequency) > period_ordinal(last_previous, "Y12"):
                vals = {}
                for fid, _label in flows:
                    if fid in self.allowed:
                        vals[fid] = self.num(fid, o.period)
                new.append({"when": self.period_label(o.period, o.frequency), "figures": vals})
        d = self.p.indicators[ind].decimals
        revised = []
        for period in sorted(before):
            if period not in after:
                continue
            row = {"when": self.period_label(period, "Y12"), "figures": {}}
            changed = False
            for fid, label in flows:
                a = before[period]["values"].get((label, TOTAL))
                b = after[period]["values"].get((label, TOTAL))
                if a is None or b is None:
                    continue
                changed |= a != b
                row["figures"][fid] = {
                    "before": _fmt(a, d), "after": _fmt(b, d),
                    "change": ("+" if b > a else "") + _fmt(b - a, d) if a != b else "no change",
                }  # fmt: skip
                self.used[f"release.{fid}.{period}"] = {
                    "indicator": fid, "breakdown": TOTAL, "period": period, "value": b,
                    "status": f"{_pub_long(previous)} {a:.0f}, {_pub_long(current)} {b:.0f}",
                }  # fmt: skip
            if changed:
                revised.append(row)
        if latest.period != self._series(ind)[-1].period:
            raise ValueError(f"{ind}: latest period has no value")
        return {
            "current": _pub_long(current),
            "previous": _pub_long(previous),
            "new": new,
            "revised": revised,
        }

    # --- evidence records (decision 20) ------------------------------------------

    def _evidence(self, rid: str, kind: str) -> dict:
        from . import evidence

        if not hasattr(self, "_ev"):
            self._ev = evidence.load_all(self.p.root)
        rec = self._ev.get(rid)
        if rec is None or rec["kind"] != kind:
            raise ValueError(f"no {kind} evidence record {rid!r}")
        return json.loads(json.dumps(rec, default=str))  # dates as text, freezable

    def survey(self, rid: str, answer: str) -> dict:
        """One answer from a survey record: what people said, when, and who was asked."""
        rec = self._evidence(rid, "survey")
        r = next((r for r in rec["results"] if r["answer"] == answer), None)
        if r is None or r["percent"] is None:
            raise ValueError(f"{rid}: no reported percentage for {answer!r}")
        self.used[f"evidence.{rid}.{answer}"] = {
            "indicator": f"evidence:{rid}", "breakdown": answer,
            "period": f"{rec['fieldwork_start']}/{rec['fieldwork_end']}",
            "value": r["percent"], "status": "survey",
            "geography": rec["population"], "unit": "% of respondents",
            "publisher": rec["pollster"] + " for " + rec["commissioner"], "record": rec,
        }  # fmt: skip
        return {
            "pct": f"{r['percent']}%",
            "when": _month_year(date.fromisoformat(rec["fieldwork_end"])),
            "who": rec["population"],
            "by": f"{rec['pollster']} for {rec['commissioner']}",
            "url": f"evidence/{rid}/",
        }

    def cited(self, rid: str) -> dict:
        """A single figure from a document, with its exact scope."""
        from .evidence import money

        rec = self._evidence(rid, "cited_figure")
        self.used[f"evidence.{rid}"] = {
            "indicator": f"evidence:{rid}", "breakdown": TOTAL, "period": rec["period"],
            "value": rec["value"], "status": rec["status"], "geography": UK,
            "unit": rec["unit"], "publisher": rec["source"], "record": rec,
        }  # fmt: skip
        return {"value": money(rec["value"], rec["unit"]), "period": rec["period"],
                "period_short": rec.get("period_short") or rec["period"],
                "url": f"evidence/{rid}/"}  # fmt: skip

    def gdp_share(self, rid: str, gdp: str = "gdp_current_prices") -> dict:
        """A cited spending figure as a share of GDP for the same financial year.

        Contract (Ross, 10 Nov: amounts should be shown as a share of GDP): numerator
        from the cited record (nominal pounds, its financial year); denominator ONS GDP
        at current market prices (YBHA, seasonally adjusted, nominal), summed over the
        four quarters April to March of that year, from the saved release. All four
        quarters must be present: no missing quarter is imputed. (ONS GDP is itself an
        estimate and is revised; the derivation, inputs and release are frozen with the
        edition and shown on the evidence page.)
        """
        from .evidence import money

        rec = self._evidence(rid, "cited_figure")
        fy = int(rec["financial_year_start"])
        quarters = [f"{fy}-Q2", f"{fy}-Q3", f"{fy}-Q4", f"{fy + 1}-Q1"]
        gdp_m = sum(self.obs(gdp, q).value for q in quarters)  # obs records each quarter
        scale = {"GBP thousand": 1e-3, "GBP million": 1.0}
        if rec["unit"] not in scale:
            raise ValueError(f"{rid}: cannot express {rec['unit']} as a share of GDP")
        numerator_m = rec["value"] * scale[rec["unit"]]
        share = 100 * numerator_m / gdp_m
        self.cited(rid)  # record the numerator too
        entry = latest_entries(self.p).get(gdp)
        d = self.p.indicators[gdp]
        # The derivation travels with the cited record, so the evidence page (and every
        # frozen edition) shows the denominator, aggregation, formula and caveat.
        self.used[f"evidence.{rid}"]["record"]["share_of_gdp"] = {
            "quarters": [{"period": q, "value": self.obs(gdp, q).value} for q in quarters],
            "gdp_total_m": gdp_m,
            "numerator_m": numerator_m,
            "share_pct": share,
            "shown": f"{share:.2f}%" if share < 1 else f"{share:.1f}%",
            "denominator": d.source.dataset,
            "denominator_url": d.source.url,
            "release": entry.vintage if entry else None,
            "aggregation": f"Sum of the four quarters April {fy} to March {fy + 1}",
        }  # fmt: skip
        return {
            "pct": f"{share:.2f}%" if share < 1 else f"{share:.1f}%",
            "amount": money(rec["value"], rec["unit"]),
            "gdp": f"£{gdp_m / 1e6:.2f} trillion",
            "period": rec.get("period_short") or rec["period"],
        }

    def peers(self, ind: str) -> dict:
        """The indicator's peer group at the latest year every member has (never mixed
        years): a bar chart with the UK highlighted, the UK value and its position."""
        if ind not in self.allowed:
            raise ValueError(f"indicator {ind!r} is not listed in the briefing's front matter")
        d = self.p.indicators[ind]
        if not d.peers:
            raise ValueError(f"{ind}: no peer group")
        group = self.p.peer_groups[d.peers.group]
        if ind not in self._rows:
            self._rows[ind] = self.p.read_observations(ind)
        comp = peer_comparison(d, group, self._rows[ind])
        if comp.period is None:
            raise ValueError(f"{ind}: no year that every peer has")
        if comp.excluded:
            raise ValueError(f"{ind}: peers without data {sorted(comp.excluded)}; say so first")
        status = {
            o.geography_id: o.status
            for o in self._rows[ind]
            if o.period == comp.period and o.breakdown == TOTAL
        }
        for g, v in comp.values:
            self.used[f"{ind}.{g}.{comp.period}"] = {
                "indicator": ind, "breakdown": TOTAL, "geography": g, "period": comp.period,
                "value": v, "status": status.get(g, ""),
            }  # fmt: skip
        ranked = sorted(comp.values, key=lambda gv: gv[1], reverse=True)
        pos = next(i + 1 for i, (g, _) in enumerate(ranked) if g == UK)
        labels = {g: self.p.geographies[g].short_label for g, _ in comp.values}
        when = self.period_label(comp.period, d.frequency)
        svg = chart.bar_chart(ranked, labels, UK, d.unit, d.decimals, when)
        ordinal = {1: "highest", len(ranked): "lowest"}.get(
            pos, f"{pos}{'nd' if pos == 2 else 'rd' if pos == 3 else 'th'} highest"
        )
        return {
            "when": when,
            "uk": _fmt(dict(comp.values)[UK], d.decimals),
            "position": f"the {ordinal} of the {len(ranked)} {group.label} countries",
            "group": group.label,
            "chart": Markup(f'\n<div class="chart-block">{svg}</div>\n'),
        }

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
    manifest = latest_entries(project)
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
                # A bundle (per_1000) records several requests separated by " ; ".
                "files": [u for u in (e.request.split(" ; ") if e else []) if u.startswith("http")],
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
        "peers": facts.peers,
        "revisions": facts.revisions,
        "release_changes": facts.release_changes,
        "survey": facts.survey,
        "between": facts.between,
        "shares": facts.shares,
        "gdp_share": facts.gdp_share,
        "cited": facts.cited,
        "largest_revision": facts.largest_revision,
        **(extra or {}),
    }
    text = env.from_string(b.body).render(**ctx)
    html = md.markdown(text, extensions=["tables", "md_in_html"])
    for fact in facts.used.values():  # frozen with the edition, so downloads match it
        if fact["indicator"].startswith("evidence:"):
            fact.setdefault("indicator_title", fact["indicator"])
            continue
        d = project.indicators.get(fact["indicator"])
        if d:
            fact.setdefault("geography", UK)
            fact["indicator_title"] = d.title
            fact["unit"] = d.unit
            fact["publisher"] = d.source.publisher
    return html, facts.used, sources_for(project, b)


CSV_COLUMNS = ["key", "indicator", "indicator_title", "geography", "breakdown", "period",
               "value", "status", "unit", "publisher", "in_chart_only"]  # fmt: skip


def facts_csv(facts: dict) -> str:
    """Every figure an edition uses, exactly as frozen, for download."""
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for key, f in sorted(facts.items()):
        w.writerow([key] + [
            ("yes" if f.get("chart") else "no") if c == "in_chart_only"
            else ("" if f.get(c) is None else f.get(c))
            for c in CSV_COLUMNS[1:]
        ])  # fmt: skip
    return buf.getvalue()


def editions(root: Path, briefing_id: str) -> list[str]:
    """All frozen edition ids for a briefing, oldest first."""
    d = root / "briefings" / "editions" / briefing_id
    return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []


def read_edition(root: Path, briefing_id: str, edition: str) -> dict:
    path = edition_path(root, briefing_id, edition)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("briefing") != briefing_id or data.get("edition") != edition:
        raise ValueError(f"{path.name}: edition file does not match its name")
    return data


def slug(text: str) -> str:
    text = re.sub(r"&#39;|&rsquo;|['\u2019]", "", text)  # "can't" -> "cant"
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


H2 = re.compile(r"<h2>(.*?)</h2>", re.S)
CHART_BLOCK = re.compile(r'<div class="chart-block">.*?</svg>\s*</div>', re.S)


def _balanced_div(html: str, opening: str) -> str:
    """The whole <div> starting with `opening`, including nested divs (answer cards)."""
    start = html.find(opening)
    if start < 0:
        return ""
    depth, i = 0, start
    for m in re.finditer(r"<div\b|</div>", html[start:]):
        depth += 1 if m.group(0) == "<div" else -1
        if depth == 0:
            i = start + m.end()
            return html[start:i]
    raise ValueError(f"unclosed {opening}")


def split_blocks(html: str) -> dict:
    """Named blocks from one rendered briefing, so layouts can arrange the same content
    differently without copying any wording or numbers:
    answer (the short-answer box), sections [{id, title, html}] split at each <h2>,
    and lead (the first section with a chart, for the visual-led layout)."""
    answer = _balanced_div(html, '<div class="answer')
    rest = html.replace(answer, "", 1) if answer else html
    parts = H2.split(rest)
    sections = []
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        sections.append({"id": slug(re.sub(r"<[^>]+>", "", title)), "title": title,
                         "html": parts[i + 1]})  # fmt: skip
    lead = next((s for s in sections if 'class="chart-block"' in s["html"]), None)
    if lead:  # the visual-led layout shows the chart before the section's text
        c = CHART_BLOCK.search(lead["html"])
        lead = {**lead, "chart": c.group(0), "text": lead["html"].replace(c.group(0), "", 1)}
    # The whole page with linkable headings, for the editorial layout.
    full = H2.sub(lambda m: f'<h2 id="{slug(re.sub(r"<[^>]+>", "", m.group(1)))}">'
                            f"{m.group(1)}</h2>", html)  # fmt: skip
    # Anything before the first heading other than the answer box, so no text is lost.
    return {"answer": answer, "intro": parts[0], "sections": sections, "lead": lead,
            "html": full}  # fmt: skip


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
