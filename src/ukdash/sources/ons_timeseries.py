"""ONS time series (the /timeseries/<cdid>/<dataset>/data JSON), quarterly values.

Used for GDP at current market prices (CDID YBHA, dataset QNA), the denominator when a
briefing expresses spending as a share of GDP. The response states its CDID, unit and
release date; the parser checks them against the indicator's `expect` block so a
changed series fails instead of publishing.

    query:
      cdid: YBHA
      dataset: qna
      expect: {pre_unit: "£", unit: "m", seasonal_adjustment: "SA"}
"""

from __future__ import annotations

import json

from ..schema import Geography, IndicatorDefinition, Observation
from . import http
from .base import Adapter, Fetched, register

URL = "https://www.ons.gov.uk/economy/grossdomesticproductgdp/timeseries/{cdid}/{dataset}/data"
UK = "iso:GBR"


@register
class OnsTimeseriesAdapter(Adapter):
    name = "ons_timeseries"

    def fetch(self, d: IndicatorDefinition) -> Fetched:
        q = d.source.query
        url = URL.format(cdid=q["cdid"].lower(), dataset=q["dataset"].lower())
        raw = http.get(url)
        meta = json.loads(raw.decode("utf-8")).get("description", {})
        return Fetched(raw=raw, filename="series.json", request=url,
                       vintage=meta.get("releaseDate", "")[:10] or None)  # fmt: skip

    def parse(
        self, d: IndicatorDefinition, raw: bytes, geographies: dict[str, Geography]
    ) -> list[Observation]:
        q = d.source.query
        if d.frequency != "Q":
            raise ValueError(f"{d.id}: ons_timeseries supports quarterly series only")
        data = json.loads(raw.decode("utf-8"))
        desc = data.get("description", {})
        if str(desc.get("cdid", "")).upper() != q["cdid"].upper():
            raise ValueError(f"{d.id}: response is series {desc.get('cdid')!r}, not {q['cdid']}")
        for key, want in (q.get("expect") or {}).items():
            field = {"unit": "unit", "pre_unit": "preUnit",
                     "seasonal_adjustment": "seasonalAdjustment"}[key]  # fmt: skip
            if str(desc.get(field, "")) != str(want):
                raise ValueError(
                    f"{d.id}: {field} is {desc.get(field)!r}, expected {want!r} (drift?)"
                )
        if UK not in geographies:
            raise ValueError("no canonical UK geography")
        out = []
        for row in data.get("quarters") or []:
            year, quarter = str(row["year"]), str(row["quarter"]).upper()
            if quarter not in ("Q1", "Q2", "Q3", "Q4"):
                raise ValueError(f"{d.id}: unexpected quarter {row['quarter']!r}")
            value = row.get("value")
            out.append(Observation(
                indicator_id=d.id, geography_id=UK, period=f"{year}-{quarter}",
                frequency="Q", value=float(value) if value not in (None, "") else None,
                status="" if value not in (None, "") else "missing",
            ))  # fmt: skip
        if not out:
            raise ValueError(f"{d.id}: no quarterly values in response")
        return out
