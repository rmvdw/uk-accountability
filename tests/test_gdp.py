"""ONS GDP (YBHA) adapter and shares of GDP, on the genuine saved response."""

import json
from pathlib import Path

import pytest

from ukdash import briefing
from ukdash.build import period_label
from ukdash.project import Project
from ukdash.sources.ons_timeseries import OnsTimeseriesAdapter

FIX = Path(__file__).parent / "fixtures" / "ons" / "ybha_qna.json"


def parse(raw):
    p = Project.load()
    return OnsTimeseriesAdapter().parse(p.indicators["gdp_current_prices"], raw, p.geographies)


def test_quarters_parse_with_unit_and_title_checks():
    obs = parse(FIX.read_bytes())
    assert all(o.frequency == "Q" and o.geography_id == "iso:GBR" for o in obs)
    q = {o.period: o.value for o in obs}
    assert q["2025-Q2"] > 700_000  # £ million per quarter


@pytest.mark.parametrize(
    "field,bad", [("unit", "bn"), ("preUnit", "$"), ("title", "Chained volume measure")]
)
def test_series_drift_fails(field, bad):
    data = json.loads(FIX.read_text(encoding="utf-8"))
    data["description"][field] = bad
    with pytest.raises(ValueError, match="drift"):
        parse(json.dumps(data).encode())


def test_share_of_gdp_uses_the_four_quarters_of_the_financial_year():
    p = Project.load()
    f = briefing.Facts(p, ["gdp_current_prices"], period_label)
    s = f.gdp_share("home_office_asylum_support_2025_26")
    gdp = {o.period: o.value for o in p.read_observations("gdp_current_prices")}
    fy = gdp["2025-Q2"] + gdp["2025-Q3"] + gdp["2025-Q4"] + gdp["2026-Q1"]
    assert s["pct"] == f"{100 * 4_181_193 / 1000 / fy:.2f}%"
    assert {k for k in f.used if k.startswith("gdp_current_prices")} == {
        f"gdp_current_prices.total.{q}" for q in ("2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1")
    }


def test_share_of_gdp_refuses_a_missing_quarter():
    p = Project.load()
    real = p.read_observations
    p.read_observations = lambda i: (
        [o for o in real(i) if o.period != "2026-Q1"] if i == "gdp_current_prices" else real(i)
    )
    f = briefing.Facts(p, ["gdp_current_prices"], period_label)
    with pytest.raises(ValueError, match="2026-Q1"):
        f.gdp_share("home_office_asylum_support_2025_26")
