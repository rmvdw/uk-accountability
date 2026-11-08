from pathlib import Path

import pytest

from ukdash.compare import peer_comparison
from ukdash.project import Project
from ukdash.sources import ADAPTERS
from ukdash.sources.oecd import request_url

EXCERPT = Path(__file__).parent / "fixtures/oecd/unemployment_excerpt.csv"


@pytest.fixture
def setup():
    project = Project.load()
    return project, project.indicators["unemployment_rate"], ADAPTERS["oecd_sdmx"]


def test_request_url(setup):
    _, d, _ = setup
    assert request_url(d) == (
        "https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0/"
        "CAN+DEU+FRA+GBR+ITA+JPN+USA.UNE_LF_M.PT_LF_SUB._Z.Y._T.Y_GE15._Z.M"
        "?format=csvfile&startPeriod=2015-01"
    )


def test_key_covers_peer_group(setup):
    project, d, _ = setup
    areas = set(d.source.query["key"].split(".")[0].split("+"))
    members = {project.geographies[g].codes["iso3"] for g in project.peer_groups["g7"].members}
    assert areas == members


def test_parses_real_excerpt(setup):
    project, d, adapter = setup
    rows = adapter.parse(d, EXCERPT.read_bytes(), project.geographies)
    uk = {o.period: o.value for o in rows if o.geography_id == "iso:GBR"}
    assert uk["2026-07"] == 4.7  # as published by OECD, fetched 2026-11-08
    assert max(uk) == "2026-07"  # UK data lag other countries
    assert all(o.frequency == "M" and o.status == "" for o in rows)
    assert {o.geography_id for o in rows} == set(project.peer_groups["g7"].members)


def test_comparison_uses_latest_month_uk_has(setup):
    project, d, adapter = setup
    rows = adapter.parse(d, EXCERPT.read_bytes(), project.geographies)
    comp = peer_comparison(d, project.peer_groups["g7"], rows)
    assert comp.period == "2026-07"
    assert len(comp.values) == 7


@pytest.mark.parametrize(
    "old,new", [(b",Y,_T,", b",N,_T,"), (b",Y_GE15,", b",Y15T24,"), (b",PT_LF_SUB,", b",PS,")]
)
def test_definition_drift_fails_loudly(setup, old, new):
    project, d, adapter = setup
    with pytest.raises(ValueError, match="definition drift"):
        adapter.parse(d, EXCERPT.read_bytes().replace(old, new, 1), project.geographies)


def test_unknown_area_fails(setup):
    project, d, adapter = setup
    bad = EXCERPT.read_bytes().replace(b",GBR,", b",XKX,", 1)
    with pytest.raises(ValueError, match="no canonical geography"):
        adapter.parse(d, bad, project.geographies)


def test_status_codes_map(setup):
    project, d, adapter = setup
    lines = EXCERPT.read_bytes().split(b"\n")
    lines[1] = lines[1].replace(b",A,0,1", b",P,0,1")
    rows = adapter.parse(d, b"\n".join(lines), project.geographies)
    assert rows[0].status == "provisional"
