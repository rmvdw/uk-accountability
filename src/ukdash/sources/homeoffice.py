"""Home Office immigration system statistics: summary tables. Contracts C3-C5 (#13).

Indicator YAML `source.query`:

    attachment_title: "Asylum summary tables, year ending"   # newest edition is chosen
    sheet: Asy_00a
    header_first_cell: "Date / As at the end of..."
    rows:                              # publisher row label -> our breakdown slug
      People claiming asylum: total
    sum_checks:                        # optional: parent row must equal the sum of children
      - parent: Family visas
        children: [Family: Child, Family: Other, Family: Partner, Refugee Family Reunion]
    calculated_total: [Work visas, Study visas, ...]   # optional: total = sum of these rows

Columns: a four-digit year is a calendar year, stored as the year (or stock) ending
December; "Year ending June 2026" and "June 2026" are stored as 2026-06. Change
columns are ignored. ':' (not available) is missing; 'z' (not applicable) is missing
but counts as 0 in a calculated total (the category did not exist).
"""

from __future__ import annotations

import json
import re

from ..schema import Geography, IndicatorDefinition, Observation
from .base import Adapter, Fetched, register
from .http import get as _get
from .spreadsheet import find_row, first_line, read_spreadsheet

COLLECTION_API = (
    "https://www.gov.uk/api/content/government/statistical-data-sets/"
    "immigration-system-statistics-data-tables"
)
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]  # fmt: skip
YEAR = re.compile(r"^\d{4}$")
_MONTH_ALT = "|".join(MONTHS)
YEAR_ENDING = re.compile(r"^(?:Year ending )?(" + _MONTH_ALT + r") (\d{4})$")
TITLE_DATE = re.compile(r"year ending (" + _MONTH_ALT + r") (\d{4})\s*$", re.I)
NOT_AVAILABLE = {":", "[x]", "x"}
NOT_APPLICABLE = {"z", "[z]"}
UK = "iso:GBR"


def pick_attachment(attachments: list[dict], title_prefix: str) -> tuple[str, str]:
    """(url, vintage) of the newest attachment whose title starts with `title_prefix`."""
    found = []
    for a in attachments:
        title = a.get("title", "")
        if not title.lower().startswith(title_prefix.lower()):
            continue
        m = TITLE_DATE.search(title)
        if not m:
            continue
        month, year = m.group(1).capitalize(), int(m.group(2))
        found.append(((year, MONTHS.index(month)), a["url"], f"year ending {month} {year}"))
    if not found:
        raise ValueError(f"no Home Office attachment titled {title_prefix!r}… with a date")
    _, url, vintage = max(found)
    return url, vintage


def column_period(header: str) -> str | None:
    """Our YYYY-MM period for a column header, or None for columns we ignore."""
    h = first_line(header)
    if YEAR.match(h):
        return f"{h}-12"
    m = YEAR_ENDING.match(h)
    if m:
        return f"{m.group(2)}-{MONTHS.index(m.group(1)) + 1:02d}"
    return None


def parse_rows(raw: bytes, q: dict) -> dict[str, dict[str, tuple[float | None, str]]]:
    """{row label: {period: (value, status)}} for every requested or checked row."""
    sheets = read_spreadsheet(raw)
    sheet = q["sheet"]
    if sheet not in sheets:
        raise ValueError(f"workbook has no sheet {sheet!r}")
    rows = sheets[sheet]
    h = find_row(rows, q["header_first_cell"])
    periods = {i: column_period(c) for i, c in enumerate(rows[h]) if i > 0}
    periods = {i: p for i, p in periods.items() if p}
    if not periods:
        raise ValueError(f"{sheet}: no period columns in header {rows[h]}")
    if len(set(periods.values())) != len(periods):
        raise ValueError(f"{sheet}: duplicate period columns {sorted(periods.values())}")

    wanted = set(q["rows"])
    for check in q.get("sum_checks", []):
        wanted |= {check["parent"], *check["children"]}
    wanted |= set(q.get("calculated_total", []))

    table: dict[str, dict[str, tuple[float | None, str]]] = {}
    for r in rows[h + 1 :]:
        if not r or not r[0]:
            continue
        label = first_line(r[0])
        if label not in wanted:
            continue
        if label in table:
            raise ValueError(f"{sheet}: row {label!r} appears twice")
        vals = {}
        for i, p in periods.items():
            cell = r[i].strip() if i < len(r) else ""
            if cell in NOT_AVAILABLE or cell == "":
                vals[p] = (None, "not available")
            elif cell in NOT_APPLICABLE:
                vals[p] = (None, "not applicable")
            else:
                vals[p] = (float(cell), "")
        table[label] = vals
    missing = wanted - set(table)
    if missing:
        raise ValueError(f"{sheet}: expected rows not found: {sorted(missing)}")

    for check in q.get("sum_checks", []):
        parent = table[check["parent"]]
        for p, (pv, _) in parent.items():
            parts = [table[c][p] for c in check["children"]]
            if pv is None or any(v is None and s != "not applicable" for v, s in parts):
                continue
            total = sum(v or 0 for v, _ in parts)
            if abs(total - pv) > 0.5:
                raise ValueError(
                    f"{sheet} {p}: {check['parent']} {pv:.0f} != sum of parts {total:.0f}"
                )
    return table


@register
class HomeOfficeSummary(Adapter):
    name = "homeoffice_summary"

    def fetch(self, d: IndicatorDefinition) -> Fetched:
        meta = json.loads(_get(COLLECTION_API))
        attachments = meta.get("details", {}).get("attachments", [])
        url, vintage = pick_attachment(attachments, d.source.query["attachment_title"])
        ext = url.rsplit(".", 1)[-1].lower()
        return Fetched(raw=_get(url), filename=f"tables.{ext}", request=url, vintage=vintage)

    def parse(
        self, d: IndicatorDefinition, raw: bytes, geographies: dict[str, Geography]
    ) -> list[Observation]:
        q = d.source.query
        table = parse_rows(raw, q)
        freq = d.frequency
        if freq not in ("Y12", "AT"):
            raise ValueError("Home Office summary indicators use frequency Y12 (flows) or AT")
        out = []
        for label, slug in q["rows"].items():
            for p, (v, s) in sorted(table[label].items()):
                out.append(
                    Observation(
                        indicator_id=d.id,
                        geography_id=UK,
                        breakdown=slug,
                        period=p,
                        frequency=freq,
                        value=v,
                        status=s,
                    )  # fmt: skip
                )
        calc = q.get("calculated_total")
        if calc:
            if "total" in q["rows"].values():
                raise ValueError("calculated_total conflicts with a row mapped to total")
            periods = sorted(table[calc[0]])
            for p in periods:
                parts = [table[c][p] for c in calc]
                if any(v is None and s != "not applicable" for v, s in parts):
                    out.append(
                        Observation(
                            indicator_id=d.id,
                            geography_id=UK,
                            period=p,
                            frequency=freq,
                            value=None,
                            status="not available",
                        )  # fmt: skip
                    )
                    continue
                out.append(
                    Observation(
                        indicator_id=d.id,
                        geography_id=UK,
                        period=p,
                        frequency=freq,
                        value=sum(v or 0 for v, _ in parts),
                        status="calculated",
                    )  # fmt: skip
                )
        return out
