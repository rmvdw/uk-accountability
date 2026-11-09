"""ONS long-term international migration (provisional), Table 1. Source contract C1 (#13).

Indicator YAML `source.query`:

    dataset_page: https://www.ons.gov.uk/.../longterminternationalimmigrationemigrationandnetmigrationflowsprovisional
    flow: Net migration            # or Immigration, Emigration

All nationality columns are returned: All Nationalities as `total`, and
British / EU+ / Non-EU+ as breakdowns. Every parse checks the whole table:
Immigration - Emigration = Net, and All = British + EU+ + Non-EU+ (all figures
are individually rounded to the nearest 1,000, hence the tolerances).
"""

from __future__ import annotations

import html
import re
import urllib.request

from ..schema import Geography, IndicatorDefinition, Observation
from .base import Adapter, Fetched, register
from .spreadsheet import find_row, first_line, read_spreadsheet

USER_AGENT = "uk-accountability (+https://github.com/rmvdw/uk-accountability)"
SHEET = "1"
HEADER = ["Flow", "Period", "All Nationalities", "British", "EU+", "Non-EU+"]
COLUMNS = {
    "All Nationalities": "total",
    "British": "british",
    "EU+": "eu_plus",
    "Non-EU+": "non_eu_plus",
}
FLOWS = ("Immigration", "Emigration", "Net migration")
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
MONTHS_LONG = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]  # fmt: skip
PERIOD = re.compile(r"^YE (" + "|".join(MONTHS) + r") (\d{2})((?: [PR])*)$")
EDITION = re.compile(
    r'href="(/file\?uri=[^"]*/yearending(' + "|".join(MONTHS_LONG) + r')(\d{4})/[^"]+\.xlsx)"'
)
NET_TOLERANCE = 1_000
SUM_TOLERANCE = 3_000
UK = "iso:GBR"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def latest_edition(page_html: str) -> tuple[str, str]:
    """(file URL, vintage label) for the newest edition linked from the dataset page.

    Chosen by the 'yearending<month><year>' path segment, never by file name, which
    changes every edition.
    """
    found = []
    for href, month, year in EDITION.findall(page_html):
        found.append(((int(year), MONTHS_LONG.index(month)), html.unescape(href), month, year))
    if not found:
        raise ValueError("no LTIM edition links found on the ONS dataset page")
    _, href, month, year = max(found)
    return "https://www.ons.gov.uk" + href, f"YE {month.capitalize()} {year}"


def parse_table(raw: bytes) -> dict[tuple[str, str, str], tuple[float | None, str]]:
    """{(flow, column slug, period): (value, status)} with contract and reconciliation checks."""
    sheets = read_spreadsheet(raw)
    if SHEET not in sheets:
        raise ValueError(f"workbook has no sheet {SHEET!r} (contract C1)")
    rows = sheets[SHEET]
    h = find_row(rows, "Flow")
    header = [first_line(c) for c in rows[h]]
    if header[: len(HEADER)] != HEADER:
        raise ValueError(f"sheet {SHEET} header changed: {header} (contract C1)")

    out: dict[tuple[str, str, str], tuple[float | None, str]] = {}
    for r in rows[h + 1 :]:
        if not r or not r[0]:
            continue
        flow, label = r[0].strip(), r[1].strip()
        if flow not in FLOWS:
            raise ValueError(f"unexpected Flow {flow!r} (contract C1)")
        m = PERIOD.match(label)
        if not m:
            raise ValueError(f"unexpected Period {label!r} (contract C1)")
        mon, yy, flags = m.groups()
        period = f"{2000 + int(yy)}-{MONTHS.index(mon) + 1:02d}"
        status = ", ".join({"P": "provisional", "R": "revised"}[f] for f in flags.split() if f)
        for i, col in enumerate(HEADER[2:], start=2):
            cell = r[i].strip() if i < len(r) else ""
            if cell in ("", ":", "x", "[x]", "z", "[z]"):
                value, st = None, "not available"
            else:
                value, st = float(cell), status
            key = (flow, COLUMNS[col], period)
            if key in out:
                raise ValueError(f"duplicate row {key} (contract C1)")
            out[key] = (value, st)
    if not out:
        raise ValueError("no data rows found (contract C1)")
    _reconcile(out)
    return out


def _reconcile(t: dict[tuple[str, str, str], tuple[float | None, str]]) -> None:
    periods = {p for (_, _, p) in t}
    for p in periods:
        for col in COLUMNS.values():
            imm, emi, net = (t.get((f, col, p), (None, ""))[0] for f in FLOWS)
            if None not in (imm, emi, net) and abs(imm - emi - net) > NET_TOLERANCE:
                raise ValueError(
                    f"{col} {p}: immigration {imm:.0f} - emigration {emi:.0f} != net {net:.0f}"
                )
        for f in FLOWS:
            parts = [t.get((f, c, p), (None, ""))[0] for c in ("british", "eu_plus", "non_eu_plus")]
            total = t.get((f, "total", p), (None, ""))[0]
            if total is not None and None not in parts and abs(total - sum(parts)) > SUM_TOLERANCE:
                raise ValueError(f"{f} {p}: All {total:.0f} != sum of groups {sum(parts):.0f}")


def publication_date(raw: bytes) -> str | None:
    """Release date from the cover sheet, e.g. '21 May 2026', or None if not stated."""
    for r in read_spreadsheet(raw).get("Cover Sheet", []):
        m = re.search(r"originally published at .*? on (\d{1,2} [A-Z][a-z]+ \d{4})", " ".join(r))
        if m:
            return m.group(1)
    return None


@register
class ONSLongTermMigration(Adapter):
    name = "ons_ltim"

    def fetch(self, d: IndicatorDefinition) -> Fetched:
        page = _get(d.source.query["dataset_page"]).decode("utf-8", "replace")
        url, vintage = latest_edition(page)
        raw = _get(url)
        release = publication_date(raw)
        return Fetched(
            raw=raw,
            filename="ltim.xlsx",
            request=url,
            publisher_release_date=release,
            vintage=vintage,
        )

    def parse(
        self, d: IndicatorDefinition, raw: bytes, geographies: dict[str, Geography]
    ) -> list[Observation]:
        if d.frequency != "Y12":
            raise ValueError(
                "ONS LTIM estimates are rolling years: indicator frequency must be Y12"
            )
        flow = d.source.query["flow"]
        if flow not in FLOWS:
            raise ValueError(f"query.flow must be one of {FLOWS}")
        table = parse_table(raw)
        return [
            Observation(
                indicator_id=d.id,
                geography_id=UK,
                breakdown=col,
                period=period,
                frequency="Y12",
                value=value,
                status=status,
            )
            for (f, col, period), (value, status) in sorted(table.items())
            if f == flow
        ]
