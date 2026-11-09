"""Counts per 1,000 residents: a count from one publisher divided by the same year's
population from the World Bank.

Both responses are saved together as one JSON bundle (raw file), so the published rate
can always be recomputed from exactly what was downloaded:

    {"numerator": {"kind": ..., "parts": [{"request": url, "body": text}, ...]},
     "population": {"request": url, "body": text}}

Indicator YAML `source.query`:

    numerator: oecd_permanent      # or unhcr_asylum_new
    countries: [GBR, CAN, FRA, DEU, ITA, JPN, USA]   # ISO3
    start_year: 2015

Never substitutes: a country-year without a count or a population is recorded as
missing, so the peer comparison drops to a year every country has.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict

from ..schema import Geography, IndicatorDefinition, Observation
from . import http
from .base import Adapter, Fetched, geo_lookup, register

OECD_PERMANENT = (
    "https://sdmx.oecd.org/public/rest/data/"
    "OECD.ELS.IMD,DSD_MIG_INT@DF_MIG_INT_PER,1.0/all?startPeriod={start}&format=csvfile"
)
# Entry categories in the OECD standardised permanent-type series. Free movement (FR)
# and other (OT) are legitimately empty for some countries (e.g. the UK after 2020);
# the others must be present or the country-year is missing.
OECD_REQUIRED = {"WO", "FA", "AC", "HU"}
OECD_ALL = OECD_REQUIRED | {"FR", "OT"}
OECD_STATUS = {"A": "", "P": "provisional", "E": "estimated"}

UNHCR_ASYLUM = (
    "https://api.unhcr.org/population/v1/asylum-applications/"
    "?coa={code}&yearFrom={start}&limit=1000"
)
# UNHCR uses its own country codes where they differ from ISO3.
UNHCR_CODE = {"DEU": "GFR"}

WORLD_BANK_POP = (
    "https://api.worldbank.org/v2/country/{countries}/indicator/SP.POP.TOTL"
    "?date={start}:2100&format=json&per_page=1000"
)


def _query(d: IndicatorDefinition) -> tuple[str, list[str], int]:
    q = d.source.query
    kind = q["numerator"]
    if kind not in PARSERS:
        raise ValueError(f"unknown numerator {kind!r}")
    return kind, [str(c) for c in q["countries"]], int(q.get("start_year", 2015))


# --- numerators: return {(iso3, year): (count, status)} -------------------------------


def parse_oecd_permanent(parts: list[dict], countries: list[str]) -> dict:
    rows = csv.DictReader(io.StringIO(parts[0]["body"]))
    need = {"REF_AREA", "TIME_PERIOD", "OBS_VALUE", "MEASURE", "MIGRATION_TYPE", "UNIT_MEASURE"}
    if not need <= set(rows.fieldnames or []):
        raise ValueError(f"OECD response lacks columns {sorted(need - set(rows.fieldnames or []))}")
    cats: dict = defaultdict(dict)
    flags: dict = defaultdict(set)
    for i, r in enumerate(rows, start=2):
        if r["REF_AREA"] not in countries:
            continue
        if r["MEASURE"] != "MIG_FLW" or r["UNIT_MEASURE"] != "PS":
            raise ValueError(f"line {i}: unexpected measure or unit (definition drift?)")
        if r["MIGRATION_TYPE"] not in OECD_ALL:
            raise ValueError(f"line {i}: unknown entry category {r['MIGRATION_TYPE']!r}")
        if r.get("UNIT_MULT", "0") not in ("", "0"):
            raise ValueError(f"line {i}: unexpected UNIT_MULT {r['UNIT_MULT']!r}")
        key = (r["REF_AREA"], int(r["TIME_PERIOD"]))
        if r["OBS_VALUE"] != "":
            cats[key][r["MIGRATION_TYPE"]] = float(r["OBS_VALUE"])
            code = r.get("OBS_STATUS") or "A"
            if code not in OECD_STATUS:
                raise ValueError(f"line {i}: unknown status {code!r}")
            if OECD_STATUS[code]:
                flags[key].add(OECD_STATUS[code])
    out = {}
    for key, c in cats.items():
        if OECD_REQUIRED <= set(c):
            # "estimated" outranks "provisional" when categories differ.
            status = "estimated" if "estimated" in flags[key] else "".join(sorted(flags[key]))
            out[key] = (sum(c.values()), status)
    return out


def parse_unhcr_asylum_new(parts: list[dict], countries: list[str]) -> dict:
    """New applications (app_type N), counted as persons (app_pc P), all procedures.
    Repeat applications, appeals, re-examinations and counts of cases are excluded; a
    country-year reported only as cases is missing, never converted."""
    out: dict = {}
    for part in parts:
        items = json.loads(part["body"]).get("items", [])
        totals: dict = defaultdict(float)
        for it in items:
            iso = it.get("coa_iso")
            if iso not in countries:
                raise ValueError(f"UNHCR row for unexpected country {iso!r}")
            if it.get("app_type") == "N" and it.get("app_pc") == "P":
                totals[(iso, int(it["year"]))] += float(it.get("applied") or 0)
        out.update({k: (v, "") for k, v in totals.items()})
    return out


PARSERS = {"oecd_permanent": parse_oecd_permanent, "unhcr_asylum_new": parse_unhcr_asylum_new}


def parse_population(body: str) -> dict:
    data = json.loads(body)
    if not isinstance(data, list) or len(data) < 2:
        raise ValueError("World Bank response has no data page")
    meta = data[0]
    if int(meta.get("pages", 1)) != 1:
        raise ValueError("World Bank response is paginated; raise per_page")
    out = {}
    for r in data[1] or []:
        if r["indicator"]["id"] != "SP.POP.TOTL":
            raise ValueError("World Bank response is not SP.POP.TOTL")
        if r["value"] is not None:
            out[(r["countryiso3code"], int(r["date"]))] = float(r["value"])
    return out


@register
class Per1000Adapter(Adapter):
    name = "per_1000"

    def fetch(self, d: IndicatorDefinition) -> Fetched:
        kind, countries, start = _query(d)
        if kind == "oecd_permanent":
            urls = [OECD_PERMANENT.format(start=start)]
        else:
            urls = [UNHCR_ASYLUM.format(code=UNHCR_CODE.get(c, c), start=start) for c in countries]
        parts = [{"request": u, "body": http.get(u).decode("utf-8-sig")} for u in urls]
        pop_url = WORLD_BANK_POP.format(countries=";".join(countries), start=start)
        bundle = {
            "numerator": {"kind": kind, "parts": parts},
            "population": {"request": pop_url, "body": http.get(pop_url).decode("utf-8")},
        }
        raw = json.dumps(bundle, indent=1, ensure_ascii=False).encode("utf-8")
        return Fetched(raw=raw, filename="bundle.json", request=" ; ".join([*urls, pop_url]))

    def parse(
        self, d: IndicatorDefinition, raw: bytes, geographies: dict[str, Geography]
    ) -> list[Observation]:
        kind, countries, start = _query(d)
        bundle = json.loads(raw.decode("utf-8"))
        if bundle["numerator"]["kind"] != kind:
            raise ValueError("saved bundle is for a different numerator")
        counts = PARSERS[kind](bundle["numerator"]["parts"], countries)
        pop = parse_population(bundle["population"]["body"])
        to_geo = geo_lookup(geographies, "iso3")
        missing_geo = [c for c in countries if c not in to_geo]
        if missing_geo:
            raise ValueError(f"no canonical geography for {missing_geo}")
        # Only years the publisher reported for at least one country; a population-only
        # year (e.g. before the count is released) is not a missing count.
        years = sorted({y for _, y in counts if y >= start})
        out = []
        for c in countries:
            for y in years:
                n, p = counts.get((c, y)), pop.get((c, y))
                if n is None and p is None:
                    continue
                value = 1000 * n[0] / p if n is not None and p else None
                status = n[1] if value is not None else "missing"
                out.append(
                    Observation(
                        indicator_id=d.id,
                        geography_id=to_geo[c],
                        period=str(y),
                        frequency=d.frequency,
                        value=value,
                        status=status,
                    )
                )
        return out
