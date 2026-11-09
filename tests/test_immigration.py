"""Immigration adapters against genuine ONS and Home Office files (source contracts C1-C5, #13)."""

import io
from pathlib import Path

import openpyxl
import pytest

from ukdash.compare import latest
from ukdash.project import Project
from ukdash.sources import ADAPTERS, ons_ltim
from ukdash.sources import homeoffice as ho

FX = Path(__file__).parent / "fixtures"
FILES = {
    "ons_ltim": FX / "ons/ltim_ye_dec2025.xlsx",
    "Vis_01": FX / "homeoffice/visas_summary_jun2026.ods",
    "Asy_00a": FX / "homeoffice/asylum_summary_jun2026.ods",
    "IER_01": FX / "homeoffice/illegal_entry_summary_jun2026.ods",
}
# Published figures, as printed in the source files.
EXPECTED = {
    "net_migration": ("2025-12", 171_000),
    "immigration_long_term": ("2025-12", 813_000),
    "emigration_long_term": ("2025-12", 642_000),
    "asylum_claims": ("2026-06", 85_891),
    "asylum_initial_decisions": ("2026-06", 115_872),
    "asylum_awaiting_decision": ("2026-06", 40_168),
    "small_boat_arrivals": ("2026-06", 33_374),
    "visas_granted": ("2026-06", 2_932_329 - 2_185_158 - 19_684),  # total minus visitor, transit
}


@pytest.fixture(scope="module")
def project():
    return Project.load()


def parse(project, ind_id):
    d = project.indicators[ind_id]
    f = FILES["ons_ltim"] if d.source.adapter == "ons_ltim" else FILES[d.source.query["sheet"]]
    return ADAPTERS[d.source.adapter].parse(d, f.read_bytes(), project.geographies)


@pytest.mark.parametrize("ind_id", sorted(EXPECTED))
def test_latest_matches_published(project, ind_id):
    rows = parse(project, ind_id)
    obs = latest(rows, "iso:GBR")
    assert (obs.period, obs.value) == EXPECTED[ind_id]
    assert all(o.geography_id == "iso:GBR" for o in rows)
    d = project.indicators[ind_id]
    assert all(o.frequency == d.frequency for o in rows)
    assert {o.breakdown for o in rows} <= {"total", *d.breakdowns}


def test_ons_breakdowns_and_status(project):
    rows = {(o.breakdown, o.period): o for o in parse(project, "net_migration")}
    assert rows[("non_eu_plus", "2025-12")].value == 350_000
    assert rows[("british", "2025-12")].value == -136_000
    assert rows[("total", "2025-12")].status == "provisional"
    assert rows[("total", "2025-06")].status == "provisional, revised"
    assert rows[("total", "2024-12")].status == "revised"


def test_asylum_decisions_split(project):
    rows = {(o.breakdown, o.period): o.value for o in parse(project, "asylum_initial_decisions")}
    assert rows[("grants", "2026-06")] + rows[("refusals", "2026-06")] == rows[("total", "2026-06")]


def test_visa_total_is_marked_calculated(project):
    tot = [o for o in parse(project, "visas_granted") if o.breakdown == "total"]
    assert all(o.status in ("calculated", "not available") for o in tot)


# --- fail closed --------------------------------------------------------------


def ons_workbook(rows, header=None) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "1"
    ws.append(["Table 1 (TEST INPUT, not real data)"])
    ws.append(header or ons_ltim.HEADER)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


GOOD = [
    ["Immigration", "YE Dec 25 P", 800, 100, 100, 600],
    ["Emigration", "YE Dec 25 P", 600, 200, 100, 300],
    ["Net migration", "YE Dec 25 P", 200, -100, 0, 300],
]


def test_ons_synthetic_good_table_parses():
    assert len(ons_ltim.parse_table(ons_workbook(GOOD))) == 12


def test_ons_net_must_reconcile():
    bad = [r[:] for r in GOOD]
    bad[0][2:] = [800_000, 100_000, 100_000, 600_000]
    bad[1][2:] = [600_000, 200_000, 100_000, 300_000]
    bad[2][2:] = [205_000, -100_000, 0, 300_000]
    with pytest.raises(ValueError, match="immigration .* != net"):
        ons_ltim.parse_table(ons_workbook(bad))


def test_ons_groups_must_sum_to_all():
    bad = [r[:] for r in GOOD]
    bad[0][2:] = [810_000, 100_000, 100_000, 600_000]
    bad[1][2:] = [600_000, 200_000, 100_000, 300_000]
    bad[2][2:] = [210_000, -100_000, 0, 300_000]
    with pytest.raises(ValueError, match="sum of groups"):
        ons_ltim.parse_table(ons_workbook(bad))


def test_ons_header_drift_fails():
    with pytest.raises(ValueError, match="header changed"):
        ons_ltim.parse_table(ons_workbook(GOOD, header=["Flow", "Period", "All", "British"]))


def test_ons_unknown_period_label_fails():
    bad = [r[:] for r in GOOD]
    bad[0][1] = "2025"
    with pytest.raises(ValueError, match="unexpected Period"):
        ons_ltim.parse_table(ons_workbook(bad))


def test_ons_edition_choice_uses_path_not_filename():
    page = (
        '<a href="/file?uri=/x/yearendingjune2025/zzz.xlsx">'
        '<a href="/file?uri=/x/yearendingdecember2025/aaa.xlsx">'
        '<a href="/file?uri=/x/yearendingdecember2024/yyy.xlsx">'
    )
    url, vintage = ons_ltim.latest_edition(page)
    assert url.endswith("yearendingdecember2025/aaa.xlsx")
    assert vintage == "year ending December 2025"


def test_homeoffice_missing_row_fails():
    q = {"sheet": "Asy_00a", "header_first_cell": "Date / As at the end of...",
         "rows": {"People claiming asylum (renamed)": "total"}}  # fmt: skip
    with pytest.raises(ValueError, match="expected rows not found"):
        ho.parse_rows(FILES["Asy_00a"].read_bytes(), q)


def test_homeoffice_sum_check_fails_when_parts_do_not_add_up():
    q = {
        "sheet": "Asy_00a",
        "header_first_cell": "Date / As at the end of...",
        "rows": {"People claiming asylum": "total"},
        "sum_checks": [{"parent": "People claiming asylum", "children": ["Refusals"]}],
    }
    with pytest.raises(ValueError, match="sum of parts"):
        ho.parse_rows(FILES["Asy_00a"].read_bytes(), q)


def test_homeoffice_symbols_are_missing_not_zero():
    q = {"sheet": "Asy_00a", "header_first_cell": "Date / As at the end of...",
         "rows": {"Appeals lodged": "total"}}  # fmt: skip
    t = ho.parse_rows(FILES["Asy_00a"].read_bytes(), q)
    assert t["Appeals lodged"]["2026-06"] == (None, "not available")


def test_homeoffice_column_periods():
    assert ho.column_period("2025") == "2025-12"
    assert ho.column_period("Year ending June 2026") == "2026-06"
    assert ho.column_period("June 2026") == "2026-06"
    assert ho.column_period("Change in the latest year") is None


def test_homeoffice_picks_newest_attachment():
    atts = [
        {"title": "Asylum summary tables, year ending March 2026", "url": "a.ods"},
        {"title": "Asylum summary tables, year ending June 2026", "url": "b.ods"},
        {"title": "Asylum summary tables, year ending December 2025", "url": "c.ods"},
        {"title": "Asylum claims detailed datasets, year ending September 2026", "url": "d.xlsx"},
    ]
    assert ho.pick_attachment(atts, "Asylum summary tables, year ending") == (
        "b.ods",
        "year ending June 2026",
    )


def test_ons_publication_date_from_cover_sheet():
    assert ons_ltim.publication_date(FILES["ons_ltim"].read_bytes()) == "21 May 2026"
