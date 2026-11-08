"""Build the static site from saved, validated data. Never touches the network."""

from __future__ import annotations

import json
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


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _period_label(period: str, frequency: str) -> str:
    if frequency in ("M", "M3"):
        y, m = period.split("-")
        month = datetime(int(y), int(m), 1).strftime("%B %Y")
        return PERIOD_WORDS[frequency] + month
    if frequency == "Q":
        y, q = period.split("-")
        return f"{q} {y}"
    return period


def indicator_context(project: Project, ind_id: str) -> dict:
    d = project.indicators[ind_id]
    rows = project.read_observations(ind_id)
    labels = {g: geo.short_label for g, geo in project.geographies.items()}
    group = project.peer_groups[d.peers.group]
    uk_series = series(rows, UK)
    uk_latest = latest(rows, UK)
    comp = peer_comparison(d, group, rows)
    check = project.read_checks().get(ind_id)
    manifest = [e for e in project.read_manifest() if e.indicator_id == ind_id]
    retrieval = max(manifest, key=lambda e: e.retrieved_at) if manifest else None

    return {
        "d": d,
        "geo": project.geographies,
        "group": group,
        "uk_latest": uk_latest,
        "uk_latest_label": _period_label(uk_latest.period, d.frequency) if uk_latest else None,
        "trend_svg": chart.line_chart(uk_series, "United Kingdom", d.unit, d.decimals),
        "uk_table": [o for o in uk_series],
        "comp": comp,
        "comp_label": _period_label(comp.period, d.frequency) if comp.period else None,
        "comp_svg": chart.bar_chart(comp.values, labels, UK, d.unit, d.decimals, comp.period or ""),
        "check": check,
        "retrieval": retrieval,
        "period_label": lambda p: _period_label(p, d.frequency),
    }


def build(project: Project, out: Path) -> list[str]:
    errors = validate(project)
    if errors:
        return errors

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    env = _env()
    built_at = datetime.now(UTC).replace(microsecond=0)
    common = {"built_at": built_at.isoformat()}

    published = project.published()
    cards = []
    for d in published:
        ctx = indicator_context(project, d.id)
        page = out / d.id / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text(env.get_template("indicator.html").render(**common, **ctx))
        shutil.copy(project.observations_path(d.id), out / d.id / f"{d.id}.csv")
        cards.append(ctx)

    (out / "index.html").write_text(env.get_template("index.html").render(**common, cards=cards))
    (out / "about").mkdir()
    (out / "about" / "index.html").write_text(env.get_template("about.html").render(**common))
    (out / "build-info.json").write_text(
        json.dumps(
            {"built_at": common["built_at"], "indicators": [d.id for d in published]}, indent=2
        )
        + "\n"
    )
    return []
