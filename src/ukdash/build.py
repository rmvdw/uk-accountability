"""Build the static site from saved, validated data. Never touches the network."""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from . import chart
from .compare import UK, latest, peer_comparison, series
from .project import REPO_ROOT, Project
from .validate import validate

TEMPLATES = REPO_ROOT / "templates"
PERIOD_WORDS = {"A": "", "Q": "", "M": "", "M3": "3 months to "}
# Fixed English names: strftime's %B depends on the machine's locale, and %-d fails on Windows.
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]  # fmt: skip


def long_date(dt: datetime) -> str:
    """'1 July 2026' on every platform."""
    return f"{dt.day} {MONTHS[dt.month - 1]} {dt.year}"


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["long_date"] = long_date
    return env


def _period_label(period: str, frequency: str, short: bool = False) -> str:
    if frequency in ("M", "M3"):
        y, m = period.split("-")
        month = MONTHS[int(m) - 1]
        if short:
            return f"{month[:3]} {y}"
        return f"{PERIOD_WORDS[frequency]}{month} {y}"
    if frequency == "Q":
        y, q = period.split("-")
        return f"{q} {y}"
    if frequency in ("Y12", "AT"):
        y, m = period.split("-")
        month = MONTHS[int(m) - 1]
        if short:
            return f"YE {month[:3]} {y}" if frequency == "Y12" else f"{month[:3]} {y}"
        if frequency == "Y12":
            return f"year ending {month} {y}"
        return f"end of {month} {y}"
    return period


def period_label(period: str, frequency: str, short: bool = False) -> str:
    """Public name for _period_label, used by briefings."""
    return _period_label(period, frequency, short)


def _month_offset(period: str, k: int) -> tuple[int, int]:
    y, m = (int(x) for x in period.split("-"))
    n = y * 12 + (m - 1) + k
    return n // 12, n % 12


def _geo_period_label(d, geography_id: str, period: str, short: bool = False) -> str:
    """Label a period as it applies to one geography (see IndicatorDefinition.period_basis)."""
    if d.period_basis.get(geography_id) != "centred_3m":
        return _period_label(period, d.frequency, short)
    (y0, m0), (y1, m1) = _month_offset(period, -1), _month_offset(period, 1)
    if short:
        a, b = MONTHS[m0][:3], MONTHS[m1][:3]
        return f"{a}–{b} {y1}" if y0 == y1 else f"{a} {y0}–{b} {y1}"
    if y0 == y1:
        return f"{MONTHS[m0]} to {MONTHS[m1]} {y1}"
    return f"{MONTHS[m0]} {y0} to {MONTHS[m1]} {y1}"


def indicator_context(project: Project, ind_id: str) -> dict:
    d = project.indicators[ind_id]
    rows = project.read_observations(ind_id)
    labels = {g: geo.short_label for g, geo in project.geographies.items()}
    group = project.peer_groups[d.peers.group] if d.peers else None
    uk_series = series(rows, UK)
    uk_latest = latest(rows, UK)
    comp = peer_comparison(d, group, rows) if group else None
    check = project.read_checks().get(ind_id)
    manifest = [e for e in project.read_manifest() if e.indicator_id == ind_id]
    retrieval = max(manifest, key=lambda e: e.retrieved_at) if manifest else None

    return {
        "d": d,
        "geo": project.geographies,
        "group": group,
        "uk_latest": uk_latest,
        "uk_latest_label": _geo_period_label(d, UK, uk_latest.period) if uk_latest else None,
        "trend_svg": chart.line_chart(
            uk_series,
            "United Kingdom",
            d.unit,
            d.decimals,
            period_label=lambda p: _geo_period_label(d, UK, p, short=True),
        ),
        "uk_table": [o for o in uk_series],
        "comp": comp,
        "comp_label": _period_label(comp.period, d.frequency) if comp and comp.period else None,
        "comp_svg": chart.bar_chart(comp.values, labels, UK, d.unit, d.decimals, comp.period or "")
        if comp
        else "",
        "check": check,
        "retrieval": retrieval,
        "period_label": lambda p: _period_label(p, d.frequency),
        "uk_period_label": lambda p: _geo_period_label(d, UK, p, short=True),
        "has_data": bool(rows),
        "comp_basis_note": _comparison_basis_note(project, d, comp),
    }


def _comparison_basis_note(project: Project, d, comp) -> str | None:
    """Explain when geographies in the comparison measure the period differently."""
    if not comp or not comp.period:
        return None
    centred = [g for g in comp.included if d.period_basis.get(g) == "centred_3m"]
    if not centred:
        return None
    parts = [
        f"The {project.geographies[g].short_label} figure is an average of "
        f"{_geo_period_label(d, g, comp.period)}, which the source records as "
        f"{_period_label(comp.period, d.frequency)}"
        for g in centred
    ]
    return (
        "; ".join(parts)
        + ". Other countries' figures are monthly estimates, so the windows differ slightly."
    )


def build_briefings(project: Project, out: Path, env, common: dict, include_drafts: bool):
    """Production renders only frozen, published editions. Previews render candidates."""
    from . import briefing

    cards = []
    for b in briefing.load_all(project.root).values():
        if include_drafts:
            if not all(project.read_observations(i) for i in b.indicators):
                continue
            html, facts, sources = briefing.render_candidate(project, b, period_label)
            changes = None
            if b.published_edition:
                published = briefing.load_edition(project.root, b)
                changes = briefing.diff_facts(published["facts"], facts)
            page = {
                "id": b.id, "title": b.title, "standfirst": b.standfirst, "body_html": html,
                "sources": sources, "edition": None, "frozen_at": None, "candidate": True,
                "status": b.status, "changes": changes,
            }  # fmt: skip
        elif b.status == "published":
            ed = briefing.load_edition(project.root, b)
            page = {**ed, "id": b.id, "candidate": False, "status": b.status, "changes": None}
        else:
            continue
        page["source_lines"] = briefing.source_summary(page["sources"])
        page["attribution_lines"] = briefing.attribution_lines(page["sources"])
        page["blocks"] = briefing.split_blocks(page["body_html"])
        target = out / "briefings" / b.id / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            env.get_template("briefing.html").render(**common, b=page), encoding="utf-8"
        )
        cards.append(page)
    return cards


PRODUCTION_BRANCH = "main"


def cloudflare_preview_branch() -> str | None:
    """The branch name when running in a Cloudflare Pages build for a non-production branch.

    Cloudflare sets CF_PAGES=1 and CF_PAGES_BRANCH in its build environment. Production
    (main) is never treated as a preview, and nothing outside Cloudflare is either.
    """
    branch = os.environ.get("CF_PAGES_BRANCH")
    if os.environ.get("CF_PAGES") == "1" and branch and branch != PRODUCTION_BRANCH:
        return branch
    return None


def build(project: Project, out: Path, include_drafts: bool = False) -> list[str]:
    """Build the site. include_drafts is for review previews only, never production."""
    errors = validate(project, render_candidates=include_drafts)
    if errors:
        return errors

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    env = _env()
    built_at = datetime.now(UTC).replace(microsecond=0)
    common = {"built_at": built_at.isoformat(), "preview": include_drafts}

    published = [
        d for d in project.indicators.values() if d.status == "published" or include_drafts
    ]
    cards = []
    for d in published:
        ctx = indicator_context(project, d.id)
        page = out / d.id / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text(
            env.get_template("indicator.html").render(**common, **ctx), encoding="utf-8"
        )
        if ctx["has_data"]:  # a draft may not have been fetched yet
            shutil.copy(project.observations_path(d.id), out / d.id / f"{d.id}.csv")
        cards.append(ctx)

    briefing_cards = build_briefings(project, out, env, common, include_drafts)
    (out / "index.html").write_text(
        env.get_template("index.html").render(**common, cards=cards, briefings=briefing_cards),
        encoding="utf-8",
    )
    (out / "about").mkdir()
    (out / "about" / "index.html").write_text(
        env.get_template("about.html").render(**common), encoding="utf-8"
    )
    (out / "build-info.json").write_text(
        json.dumps(
            {
                "built_at": common["built_at"],
                "preview_with_drafts": include_drafts,
                # From Cloudflare Pages or GitHub Actions: lets checks see which commit is live.
                "source_commit": os.environ.get("CF_PAGES_COMMIT_SHA")
                or os.environ.get("GITHUB_SHA"),
                "branch": os.environ.get("CF_PAGES_BRANCH"),
                "indicators": [d.id for d in published],
                "briefings": [c["id"] for c in briefing_cards],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return []
