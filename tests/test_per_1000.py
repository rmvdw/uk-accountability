"""Peer migration rates: genuine OECD, UNHCR and World Bank responses (tests/fixtures/peer)."""

import json
from pathlib import Path

import pytest

from ukdash.project import Project
from ukdash.sources.per_1000 import Per1000Adapter

FIX = Path(__file__).parent / "fixtures" / "peer"


def parse(ind, bundle):
    p = Project.load()
    raw = (FIX / bundle).read_bytes() if isinstance(bundle, str) else bundle
    return Per1000Adapter().parse(p.indicators[ind], raw, p.geographies)


def value(obs, geo, year):
    return next(o for o in obs if o.geography_id == geo and o.period == year)


def test_permanent_rate_sums_categories_over_population():
    obs = parse("permanent_immigration_per_1000", "oecd_permanent_bundle.json")
    uk = value(obs, "iso:GBR", "2024")
    # UK 2024: five categories, free movement empty; World Bank population.
    assert uk.value == pytest.approx(6.3, abs=0.05) and uk.status == "estimated"
    assert value(obs, "iso:CAN", "2024").value == pytest.approx(11.7, abs=0.05)
    assert {o.geography_id for o in obs} == {
        "iso:GBR",
        "iso:CAN",
        "iso:FRA",
        "iso:DEU",
        "iso:ITA",
        "iso:JPN",
        "iso:USA",
    }  # fmt: skip  (Australia in the response is ignored)
    assert max(o.period for o in obs) == "2024"  # population-only 2025 is not a gap


def test_asylum_rate_counts_new_applications_by_persons():
    obs = parse("asylum_applications_per_1000", "unhcr_asylum_bundle.json")
    uk = value(obs, "iso:GBR", "2024")
    # 108,136 new applications (persons), matching the Home Office's 108,138.
    bundle = json.loads((FIX / "unhcr_asylum_bundle.json").read_text(encoding="utf-8"))
    pop = {
        (r["countryiso3code"], r["date"]): r["value"]
        for r in json.loads(bundle["population"]["body"])[1]
    }
    assert uk.value == pytest.approx(1000 * 108_136 / pop[("GBR", "2024")])
    assert value(obs, "iso:DEU", "2025").value == pytest.approx(1.36, abs=0.01)  # GFR code


def test_cases_are_never_converted_to_persons():
    bundle = json.loads((FIX / "unhcr_asylum_bundle.json").read_text(encoding="utf-8"))
    part = next(p for p in bundle["numerator"]["parts"] if "coa=JPN" in p["request"])
    body = json.loads(part["body"])
    for it in body["items"]:
        if it["year"] == 2025:
            it["app_pc"] = "C"  # Japan reports 2025 only as cases
    part["body"] = json.dumps(body)
    obs = parse("asylum_applications_per_1000", json.dumps(bundle).encode())
    jp = value(obs, "iso:JPN", "2025")
    assert jp.value is None and jp.status == "missing"


def test_missing_required_category_makes_the_year_missing():
    bundle = json.loads((FIX / "oecd_permanent_bundle.json").read_text(encoding="utf-8"))
    body = bundle["numerator"]["parts"][0]["body"].splitlines()
    head = body[0].split(",")
    i, t, c = head.index("REF_AREA"), head.index("TIME_PERIOD"), head.index("MIGRATION_TYPE")
    keep = [ln for ln in body if not (
        ln.split(",")[i] == "FRA" and ln.split(",")[t] == "2024" and ln.split(",")[c] == "HU"
    )]  # fmt: skip
    bundle["numerator"]["parts"][0]["body"] = "\n".join(keep)
    obs = parse("permanent_immigration_per_1000", json.dumps(bundle).encode())
    fr = value(obs, "iso:FRA", "2024")
    assert fr.value is None and fr.status == "missing"


def test_measure_drift_fails():
    bundle = json.loads((FIX / "oecd_permanent_bundle.json").read_text(encoding="utf-8"))
    bundle["numerator"]["parts"][0]["body"] = bundle["numerator"]["parts"][0]["body"].replace(
        ",PS,Persons,", ",PT_POP,Per cent,"
    )
    with pytest.raises(ValueError, match="definition drift"):
        parse("permanent_immigration_per_1000", json.dumps(bundle).encode())


def test_mixed_persons_and_cases_make_the_year_missing():
    # Genuine: the US reports 2025 immigration-court filings as persons and USCIS
    # filings as cases. A persons-only sum would understate the national total.
    obs = parse("asylum_applications_per_1000", "unhcr_asylum_bundle.json")
    us = value(obs, "iso:USA", "2025")
    assert us.value is None and us.status == "missing"
    assert value(obs, "iso:USA", "2024").value == pytest.approx(2.14, abs=0.01)
