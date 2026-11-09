"""Briefings: candidates, frozen editions and the publication rules (strategy 4c, #13)."""

import csv

import pytest

from ukdash import briefing
from ukdash.build import build, period_label
from ukdash.project import Project
from ukdash.validate import validate

BRIEF = """---
id: test_brief
title: "TEST FIXTURE: is unemployment changing?"
status: {status}
standfirst: "Synthetic test briefing."
indicators: [test_unemployment]
{extra}---
{{% set c = change("test_unemployment", since="2025-01") %}}
The rate was **{{{{ num("test_unemployment") }}}}%** in {{{{ when("test_unemployment") }}}}.
It {{{{ c.verb }}}}.
{body}
"""


def write_brief(root, status="draft", extra="", body=""):
    d = root / "briefings"
    d.mkdir(exist_ok=True)
    (d / "test_brief.md").write_text(
        BRIEF.format(status=status, extra=extra, body=body), encoding="utf-8"
    )
    return Project.load(root)


def set_latest_value(root, value):
    p = root / "data/observations/test_unemployment.csv"
    rows = list(csv.reader(p.open(encoding="utf-8")))
    for r in rows[1:]:
        if r[1] == "iso:GBR" and r[3] == "2025-06":
            r[5] = value
    with p.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh, lineterminator="\n").writerows(rows)


def test_real_immigration_briefing_renders_with_live_data():
    p = Project.load()
    b = briefing.load_all(p.root)["immigration"]
    html, facts, sources = briefing.render_candidate(p, b, period_label)
    latest = max(o.period for o in p.read_observations("net_migration"))
    assert f"net_migration.total.{latest}" in facts
    assert "TO VERIFY" not in html  # fiscal cards verified on #13 (Codex, 2026-11-09)
    assert {s["publisher"] for s in sources} == {
        "Office for National Statistics",
        "Home Office",
        "OECD and World Bank",
        "UNHCR and World Bank",
    }


def test_front_matter_rules(fixture_root):
    write_brief(fixture_root)
    path = fixture_root / "briefings/test_brief.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("status: draft", "status: draft\nstatus: published"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="exactly one status"):
        briefing.parse(path)
    path.write_text(text.replace("id: test_brief", "id: other"), encoding="utf-8")
    with pytest.raises(ValueError, match="id must match"):
        briefing.parse(path)
    path.write_text("No front matter\n", encoding="utf-8")
    with pytest.raises(ValueError, match="front matter"):
        briefing.parse(path)


def test_numbers_and_verbs_come_from_data(fixture_root):
    p = write_brief(fixture_root)
    b = briefing.load_all(fixture_root)["test_brief"]
    html, facts, _ = briefing.render_candidate(p, b, period_label)
    assert "<strong>4.8%</strong>" in html and "June 2025" in html and "rose" in html
    assert facts["test_unemployment.total.2025-06"]["value"] == 4.8
    set_latest_value(fixture_root, "4.0")
    html, _, _ = briefing.render_candidate(Project.load(fixture_root), b, period_label)
    assert "<strong>4.0%</strong>" in html and "fell" in html


def test_unlisted_indicator_is_an_error(fixture_root):
    p = write_brief(fixture_root, body='{{ num("unemployment_rate") }}')
    errors = validate(p)
    assert any("not listed in the briefing" in e for e in errors)


def test_to_verify_blocks_freezing(fixture_root):
    p = write_brief(fixture_root, body="Cost: [TO VERIFY the figure]")
    b = briefing.load_all(fixture_root)["test_brief"]
    with pytest.raises(ValueError, match="TO VERIFY"):
        briefing.freeze(fixture_root, p, b, period_label)


def test_published_edition_is_frozen_against_data_changes(fixture_root, tmp_path):
    p = write_brief(fixture_root)
    b = briefing.load_all(fixture_root)["test_brief"]
    edition = briefing.freeze(fixture_root, p, b, period_label).stem
    p = write_brief(fixture_root, status="published", extra=f"published_edition: {edition}\n")
    assert validate(p) == []

    assert build(p, tmp_path / "prod") == []
    prod = (tmp_path / "prod/briefings/test_brief/index.html").read_text(encoding="utf-8")
    assert "<strong>4.8%</strong>" in prod and f"Edition {edition}" in prod

    set_latest_value(fixture_root, "4.0")  # a refresh changes the data
    p = Project.load(fixture_root)
    assert build(p, tmp_path / "prod2") == []
    prod2 = (tmp_path / "prod2/briefings/test_brief/index.html").read_text(encoding="utf-8")
    assert "<strong>4.8%</strong>" in prod2  # published wording unchanged

    assert build(p, tmp_path / "prev", include_drafts=True) == []
    prev = (tmp_path / "prev/briefings/test_brief/index.html").read_text(encoding="utf-8")
    assert "<strong>4.0%</strong>" in prev and "What a new edition would change" in prev
    assert "4.8" in prev and "4.0" in prev  # the change list shows old and new


def test_draft_briefing_absent_from_production(fixture_root, tmp_path):
    p = write_brief(fixture_root)
    assert build(p, tmp_path / "prod") == []
    assert not (tmp_path / "prod/briefings").exists()
    assert build(p, tmp_path / "prev", include_drafts=True) == []
    assert (tmp_path / "prev/briefings/test_brief/index.html").exists()


def test_published_briefing_needs_existing_edition(fixture_root):
    p = write_brief(fixture_root, status="published", extra="published_edition: nope\n")
    assert any("not found" in e for e in validate(p))


def test_diff_facts_reports_changes():
    old = {"a.total.2025": {"value": 1.0, "status": "provisional"}}
    new = {
        "a.total.2025": {"value": 2.0, "status": "revised"},
        "b.total.2025": {"value": 3.0, "status": ""},
    }
    changes = briefing.diff_facts(old, new)
    assert any("1 (provisional) → 2 (revised)" in c for c in changes)
    assert any("new figure used: b.total.2025" in c for c in changes)


def test_diff_facts_reports_chart_revisions_in_summary():
    old = {"a.total.2020": {"value": 1.0, "status": "", "chart": True}}
    new = {"a.total.2020": {"value": 1.5, "status": "", "chart": True}}
    assert briefing.diff_facts(old, new) == [
        "charts: 1 plotted point(s) new, revised or dropped (a.total.2020)"
    ]
    assert briefing.diff_facts(old, old) == []


def test_edition_is_never_replaced(fixture_root, monkeypatch):
    from datetime import UTC, datetime

    class Frozen(datetime):  # both runs fall in the same minute
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 26, 9, 31, tzinfo=UTC)

    monkeypatch.setattr(briefing, "datetime", Frozen)
    p = write_brief(fixture_root)
    b = briefing.load_all(fixture_root)["test_brief"]
    path = briefing.freeze(fixture_root, p, b, period_label)
    before = path.read_text(encoding="utf-8")
    set_latest_value(fixture_root, "4.0")  # same minute, different data
    with pytest.raises(ValueError, match="never replaced"):
        briefing.freeze(fixture_root, Project.load(fixture_root), b, period_label)
    assert path.read_text(encoding="utf-8") == before


def test_production_build_does_not_render_candidates(fixture_root, tmp_path, monkeypatch):
    p = write_brief(fixture_root)
    b = briefing.load_all(fixture_root)["test_brief"]
    edition = briefing.freeze(fixture_root, p, b, period_label).stem
    p = write_brief(fixture_root, status="published", extra=f"published_edition: {edition}\n")

    def broken(*args, **kwargs):  # e.g. a source table the candidate needs changed shape
        raise ValueError("candidate cannot render")

    monkeypatch.setattr(briefing, "render_candidate", broken)
    assert any("cannot render" in e for e in validate(p))  # make check still reports it
    assert build(p, tmp_path / "prod") == []  # but production serves the frozen edition
    prod = (tmp_path / "prod/briefings/test_brief/index.html").read_text(encoding="utf-8")
    assert f"Edition {edition}" in prod


def test_latest_manifest_entry_wins(fixture_root):
    from datetime import timedelta

    p = Project.load(fixture_root)
    entries = p.read_manifest()
    e = next(x for x in entries if x.indicator_id == "test_unemployment")
    newer = e.model_copy(update={"path": "data/raw/newer.json", "vintage": "newer",
                                 "retrieved_at": e.retrieved_at + timedelta(days=1)})  # fmt: skip
    older = e.model_copy(update={"vintage": "older"})
    p.read_manifest = lambda: [older, newer]  # old file listed first, as after a manual import
    assert briefing.latest_entries(p)["test_unemployment"].vintage == "newer"
    b = briefing.Briefing(
        id="t", title="t", status="draft", standfirst="s", indicators=["test_unemployment"],
        body="", path=fixture_root / "t.md",
    )  # fmt: skip
    assert briefing.sources_for(p, b)[0]["vintage"] == "newer"


def _with_missing(p, ind, breakdown, period):
    """The real observations, with one cell set to missing in memory."""
    real = p.read_observations

    def read(i):
        rows = real(i)
        if i != ind:
            return rows
        return [
            o.model_copy(update={"value": None, "status": "missing"})
            if o.breakdown == breakdown and o.period == period and o.geography_id == "iso:GBR"
            else o
            for o in rows
        ]

    p.read_observations = read
    return p


def test_missing_latest_breakdown_is_never_replaced_by_an_older_value():
    p = Project.load()
    latest = max(o.period for o in p.read_observations("visas_granted"))
    p = _with_missing(p, "visas_granted", "study", latest)
    f = briefing.Facts(p, ["visas_granted"], period_label)
    with pytest.raises(ValueError, match="never substituted"):
        f.bars("visas_granted", {"study": "Study", "work": "Work"})
    with pytest.raises(ValueError, match="never substituted"):
        f.num("visas_granted", breakdown="study")
    assert f.num("visas_granted", breakdown="work")  # other breakdowns still at `latest`
    b = briefing.load_all(p.root)["immigration"]
    with pytest.raises(ValueError, match="never substituted"):  # the candidate fails
        briefing.render_candidate(p, b, period_label)


def test_missing_year_earlier_value_is_never_replaced():
    p = Project.load()
    rows = p.read_observations("asylum_claims")
    top = max(rows, key=lambda o: o.period)
    f0 = briefing.Facts(p, ["asylum_claims"], period_label)
    earlier = f0.obs("asylum_claims", "year_earlier").period
    p = _with_missing(p, "asylum_claims", "total", earlier)
    f = briefing.Facts(p, ["asylum_claims"], period_label)
    with pytest.raises(ValueError, match="12 months before " + top.period):
        f.change("asylum_claims")


def test_chart_first_layout_keeps_every_block(tmp_path):
    p = Project.load()
    b = briefing.load_all(p.root)["immigration"]
    html, _, _ = briefing.render_candidate(p, b, period_label)
    blocks = briefing.split_blocks(html)
    assert 'class="answer"' in blocks["answer"]
    ids = [s["id"] for s in blocks["sections"]]
    assert "what-these-figures-cant-tell-you" in ids and len(ids) == len(set(ids))
    assert blocks["lead"]["chart"].startswith('<div class="chart-block">')

    assert build(p, tmp_path / "prev", include_drafts=True) == []
    page = (tmp_path / "prev/briefings/immigration/index.html").read_text(encoding="utf-8")
    # The lead chart comes before the stamp and the short answer, and nothing is dropped.
    assert page.index('class="chart-block"') < page.index('class="stamp"')
    assert page.index('class="stamp"') < page.index('class="answer"')
    assert blocks["answer"] in page
    for s in blocks["sections"]:
        assert f'id="{s["id"]}"' in page
    assert not (tmp_path / "prev/briefings/immigration/visual").exists()


READER_ELEMENTS = [
    "<h2>Sources</h2>",
    "Open Government Licence v3.0",
    "<h2>Cite this</h2>",
    'class="cite"',
    "Corrections are logged publicly",
]


def test_sources_citation_and_corrections_on_candidate_and_published(fixture_root, tmp_path):
    p = write_brief(fixture_root)
    assert build(p, tmp_path / "prev", include_drafts=True) == []
    cand = (tmp_path / "prev/briefings/test_brief/index.html").read_text(encoding="utf-8")
    b = briefing.load_all(fixture_root)["test_brief"]
    edition = briefing.freeze(fixture_root, p, b, period_label).stem
    p = write_brief(fixture_root, status="published", extra=f"published_edition: {edition}\n")
    assert build(p, tmp_path / "prod") == []
    pub = (tmp_path / "prod/briefings/test_brief/index.html").read_text(encoding="utf-8")
    src = p.indicators["test_unemployment"].source
    for page in (cand, pub):
        for el in [*READER_ELEMENTS[0:1], *READER_ELEMENTS[2:]]:
            assert el in page
        assert src.url.replace("&", "&amp;") in page or src.url in page  # source link
        assert src.attribution in page
    assert f"edition {edition}" in pub


def test_real_briefing_page_has_reader_elements(tmp_path):
    assert build(Project.load(), tmp_path / "prev", include_drafts=True) == []
    page = (tmp_path / "prev/briefings/immigration/index.html").read_text(encoding="utf-8")
    for el in READER_ELEMENTS:
        assert el in page


def test_peers_use_one_common_year_and_record_every_country():
    p = Project.load()
    f = briefing.Facts(p, ["permanent_immigration_per_1000"], period_label)
    pp = f.peers("permanent_immigration_per_1000")
    years = {v["period"] for v in f.used.values()}
    assert years == {"2024"} and pp["when"] == "2024"
    assert len(f.used) == 7 and "iso:GBR" in "".join(f.used)
    assert pp["position"].endswith("of the 7 G7 countries")


def test_peer_facts_keep_source_status_and_skip_incomplete_years():
    p = Project.load()
    f = briefing.Facts(p, ["permanent_immigration_per_1000", "asylum_applications_per_1000"],
                       period_label)  # fmt: skip
    f.peers("permanent_immigration_per_1000")
    assert f.used["permanent_immigration_per_1000.iso:GBR.2024"]["status"] == "estimated"
    pa = f.peers("asylum_applications_per_1000")
    assert pa["when"] == "2024"  # 2025 lacks a comparable US total
