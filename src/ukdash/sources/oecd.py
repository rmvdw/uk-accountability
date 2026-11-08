"""OECD Data Explorer, SDMX REST API (sdmx.oecd.org), CSV format.

Indicator YAML `source.query`:

    dataflow: OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0
    key: CAN+DEU+FRA+GBR+ITA+JPN+USA.UNE_LF_M.PT_LF_SUB._Z.Y._T.Y_GE15._Z.M
    start_period: 2015-01
    expect:            # every row must match these columns exactly, or parsing fails
      MEASURE: UNE_LF_M
      ...

`expect` is the guard against definition drift: if OECD ever returns a
different measure, adjustment or age band, the refresh fails loudly instead
of publishing a different statistic under the same name.
"""

from __future__ import annotations

import csv
import io
import time
import urllib.error
import urllib.parse
import urllib.request

from ..schema import Geography, IndicatorDefinition, Observation
from .base import Adapter, Fetched, geo_lookup, register

BASE_URL = "https://sdmx.oecd.org/public/rest/data"
USER_AGENT = "uk-accountability (+https://github.com/rmvdw/uk-accountability)"

# SDMX OBS_STATUS codes -> our status flags. "A" (normal value) is no flag.
STATUS = {
    "A": "",
    "P": "provisional",
    "E": "estimated",
    "B": "break",
    "M": "missing",
    "F": "forecast",
}


def request_url(d: IndicatorDefinition) -> str:
    q = d.source.query
    params = {"format": "csvfile"}
    if q.get("start_period"):
        params["startPeriod"] = str(q["start_period"])
    return f"{BASE_URL}/{q['dataflow']}/{q['key']}?{urllib.parse.urlencode(params)}"


@register
class OECDAdapter(Adapter):
    name = "oecd_sdmx"

    def fetch(self, d: IndicatorDefinition) -> Fetched:
        url = request_url(d)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        for attempt in (1, 2):
            try:
                with urllib.request.urlopen(req, timeout=90) as resp:
                    return Fetched(raw=resp.read(), filename="response.csv", request=url)
            except urllib.error.HTTPError as exc:
                # One polite retry on rate limiting or a server error.
                if attempt == 1 and (exc.code == 429 or exc.code >= 500):
                    time.sleep(20)
                    continue
                raise
        raise RuntimeError("unreachable")

    def parse(
        self, d: IndicatorDefinition, raw: bytes, geographies: dict[str, Geography]
    ) -> list[Observation]:
        expect: dict[str, str] = {k: str(v) for k, v in d.source.query.get("expect", {}).items()}
        to_geo = geo_lookup(geographies, "iso3")
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        required = {"REF_AREA", "TIME_PERIOD", "OBS_VALUE", *expect}
        missing_cols = required - set(reader.fieldnames or [])
        if missing_cols:
            raise ValueError(f"OECD response lacks columns {sorted(missing_cols)}")

        out: list[Observation] = []
        for i, row in enumerate(reader, start=2):
            for col, want in expect.items():
                if row[col] != want:
                    raise ValueError(
                        f"line {i}: {col}={row[col]!r}, expected {want!r} (definition drift?)"
                    )
            if row.get("UNIT_MULT", "0") not in ("", "0"):
                raise ValueError(f"line {i}: unexpected UNIT_MULT {row['UNIT_MULT']!r}")
            area = row["REF_AREA"]
            if area not in to_geo:
                raise ValueError(f"line {i}: REF_AREA {area!r} has no canonical geography")
            code = row.get("OBS_STATUS", "A") or "A"
            status = STATUS.get(code, f"source-status-{code}")
            value = float(row["OBS_VALUE"]) if row["OBS_VALUE"] != "" else None
            if value is None and not status:
                status = "missing"
            out.append(
                Observation(
                    indicator_id=d.id,
                    geography_id=to_geo[area],
                    period=row["TIME_PERIOD"],
                    frequency=d.frequency,
                    value=value,
                    status=status,
                )
            )
        return out
