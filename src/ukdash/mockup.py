"""DRAFT MOCK-UP for #35: one static page on Greater Manchester's buses.

Preview builds only (never production). Reads the frozen DfT workbooks saved in
mockups/gm-transport/, checks their hashes, and sums local-authority rows into today's
mayoral areas. Rates are summed counts over summed populations, never averaged rates.
No fetching, no adapter: if this becomes a product it moves into the pipeline.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from . import chart
from .schema import Observation
from .sources.spreadsheet import read_ods

BASE_YEAR = 2019  # year ending March 2019: the last full year before the pandemic


def _table(sheets: dict, name: str, by_type: bool = False) -> dict[str, dict[int, float]]:
    """{row code: {year ending March: value}} from a DfT LA table."""
    rows = sheets[name]
    head_i = next(
        i
        for i, r in enumerate(rows)
        if r and r[0].strip().startswith(("Local Authority", "LA Code"))
    )
    head = rows[head_i]
    first = 3 if by_type else 2
    years = {j: int(h) for j, h in enumerate(head) if j >= first and h.strip().isdigit()}
    out: dict = {}
    for r in rows[head_i + 1 :]:
        if not r or not r[0].strip():
            continue
        if by_type and r[2].strip() != "Total":
            continue
        vals = {}
        for j, y in years.items():
            cell = r[j].strip() if j < len(r) else ""
            if cell and not cell.startswith("["):
                vals[y] = float(cell)
        out[r[0].strip()] = vals
    return out


def load(root: Path) -> dict:
    d = root / "mockups" / "gm-transport"
    cfg = yaml.safe_load((d / "areas.yml").read_text(encoding="utf-8"))
    sheets = {}
    for fname, meta in cfg["source"]["files"].items():
        raw = (d / fname).read_bytes()
        if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
            raise ValueError(f"{fname} is not the frozen DfT release recorded in areas.yml")
        sheets[fname] = read_ods(raw)
    j = _table(sheets["bus01.ods"], "BUS01e")
    ph = _table(sheets["bus01.ods"], "BUS01f")
    km = _table(sheets["bus02_km.ods"], "BUS02d_km", by_type=True)

    def area_sum(table, codes, year):
        vals = [table.get(c, {}).get(year) for c in codes]
        return None if any(v is None for v in vals) else sum(vals)

    def pop(codes, year):
        # The population DfT itself used: journeys (millions) / journeys per head.
        vals = [
            j[c][year] * 1e6 / ph[c][year]
            if j.get(c, {}).get(year) and ph.get(c, {}).get(year)
            else None
            for c in codes
        ]
        return None if any(v is None for v in vals) else sum(vals)

    years = sorted(j["E11000001"])
    areas = {}
    for aid, a in cfg["areas"].items():
        rows = []
        for y in years:
            jy, ky, py = area_sum(j, a["rows"], y), area_sum(km, a["rows"], y), pop(a["rows"], y)
            rows.append(
                {
                    "year": y,
                    "journeys_m": jy,
                    "km_m": ky,
                    "pop": py,
                    "jph": jy * 1e6 / py if jy and py else None,
                    "kmph": ky * 1e6 / py if ky and py else None,
                }
            )
        areas[aid] = {"id": aid, "name": a["name"], "rows": {r["year"]: r for r in rows}}
    latest = max(years)
    for a in areas.values():
        now, base = a["rows"][latest], a["rows"][BASE_YEAR]
        a["latest"] = now
        a["j_change"] = 100 * (now["journeys_m"] / base["journeys_m"] - 1)
        a["km_change"] = 100 * (now["km_m"] / base["km_m"] - 1)
    return {
        "cfg": cfg,
        "areas": areas,
        "years": years,
        "latest": latest,
        "base": BASE_YEAR,
        "public_km": km_public(sheets),
    }


def km_public(sheets) -> dict[int, float]:
    """Share of Greater Manchester bus kilometres that DfT counts as publicly controlled."""
    rows = sheets["bus02_km.ods"]["BUS02d_km"]
    head_i = next(i for i, r in enumerate(rows) if r and r[0].strip() == "LA Code")
    years = {k: int(h) for k, h in enumerate(rows[head_i]) if k >= 3 and h.strip().isdigit()}
    vals: dict = {}
    for r in rows[head_i + 1 :]:
        if r and r[0].strip() == "E11000001" and r[2].strip() in ("Publicly controlled", "Total"):
            vals[r[2].strip()] = {y: float(r[k]) for k, y in years.items()}
    return {y: 100 * vals["Publicly controlled"][y] / vals["Total"][y] for y in years.values()}


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _ranked(areas: dict, key, exclude=()) -> list[dict]:
    items = [a for a in areas.values() if a["id"] not in exclude]
    return sorted(items, key=key, reverse=True)


def context(root: Path, period_label) -> dict:
    data = load(root)
    areas, latest, base = data["areas"], data["latest"], data["base"]
    focus = data["cfg"]["focus"]
    gm = areas[focus]
    others = [a for a in areas.values() if a["id"] not in (focus, "london")]

    def combined(key_num):
        out = {}
        for y in data["years"]:
            n = sum(a["rows"][y][key_num] for a in others)
            p = sum(a["rows"][y]["pop"] for a in others)
            out[y] = n * 1e6 / p
        return out

    def obs(series: dict[int, float]) -> list[Observation]:
        # geography_id is not rendered; the chart needs only period and value.
        return [
            Observation(
                indicator_id="mockup",
                geography_id="gss:E47000001",
                period=f"{y}-03",
                frequency="Y12",
                value=v,
            )
            for y, v in series.items()
        ]

    gm_jph = {y: r["jph"] for y, r in gm["rows"].items()}
    label = lambda p: period_label(p, "Y12", short=True)  # noqa: E731
    journeys_chart = chart.multi_line_chart(
        [
            ("Greater Manchester", obs(gm_jph), "net"),
            ("Other mayoral areas outside London, combined", obs(combined("journeys_m")), "imm"),
        ],
        "journeys per resident",
        0,
        label,
    )
    rank_j = _ranked(areas, lambda a: a["latest"]["jph"])
    rank_k = _ranked(areas, lambda a: a["latest"]["kmph"])
    rank_jc = _ranked(areas, lambda a: a["j_change"])
    labels = {a["id"]: a["name"] for a in areas.values()}
    bars = chart.bar_chart(
        [(a["id"], a["latest"]["jph"]) for a in rank_j if a["id"] != "london"],
        labels,
        focus,
        "bus journeys per resident",
        0,
        period_label(f"{latest}-03", "Y12"),
    )
    pos = lambda ranked: next(i for i, a in enumerate(ranked, 1) if a["id"] == focus)  # noqa: E731
    larger_falls = sum(1 for a in areas.values() if a["j_change"] < gm["j_change"])
    return {
        "ordinal": ordinal,
        "larger_falls": larger_falls,
        "src": data["cfg"]["source"],
        "gm": gm,
        "areas": rank_j,
        "n": len(areas),
        "latest_label": period_label(f"{latest}-03", "Y12"),
        "base_label": period_label(f"{base}-03", "Y12"),
        "latest": latest,
        "base": base,
        "pos_j": pos(rank_j),
        "pos_k": pos(rank_k),
        "pos_jc": pos(rank_jc),
        "public_share": data["public_km"],
        "journeys_chart": journeys_chart,
        "bars": bars,
        "london": areas["london"],
    }
