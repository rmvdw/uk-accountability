"""Briefings: candidates, frozen editions and the publication rules (strategy 4c, #13)."""

import csv
from pathlib import Path

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


def test_question_led_layout_keeps_every_block(tmp_path):
    p = Project.load()
    b = briefing.load_all(p.root)["immigration"]
    html, _, _ = briefing.render_candidate(p, b, period_label)
    blocks = briefing.split_blocks(html)
    assert blocks["answer"].startswith('<div class="answer')
    ids = [s["id"] for s in blocks["sections"]]
    assert "what-these-figures-cant-tell-you" in ids and len(ids) == len(set(ids))
    assert blocks["lead"]["chart"].startswith('<div class="chart-block">')

    assert build(p, tmp_path / "prev", include_drafts=True) == []
    page = (tmp_path / "prev/briefings/immigration/index.html").read_text(encoding="utf-8")
    # Question-led (10 Nov): stamp, then the answer cards, then the lead chart, and
    # nothing is dropped. Each card has a question, an answer and a limitation.
    assert page.index('class="stamp"') < page.index('class="answer')
    assert page.index('class="answer') < page.index('class="chart-block"')
    assert page.count('class="qcard"') == 5 and page.count('class="limit"') == 5
    assert 'class="hook"' in page
    assert 'href="evidence/bf_tracker_2026_net_direction/"' in page  # relative: stays with page
    assert blocks["answer"] in page
    for s in blocks["sections"]:
        assert f'id="{s["id"]}"' in page
    assert not (tmp_path / "prev/briefings/immigration/visual").exists()


READER_ELEMENTS = [
    '<h2 id="sources">Sources</h2>',
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
    # Relative to whatever data/ holds, so a routine refresh can't break it.
    p = Project.load()
    ind = "asylum_applications_per_1000"
    f = briefing.Facts(p, [ind, "permanent_immigration_per_1000"], period_label)
    rows = p.read_observations(ind)
    g7 = p.peer_groups["g7"].members
    complete = [
        y for y in {o.period for o in rows}
        if all(any(o.geography_id == g and o.period == y and o.value is not None for o in rows)
               for g in g7)
    ]  # fmt: skip
    assert f.peers(ind)["when"] == max(complete)
    f.peers("permanent_immigration_per_1000")
    for key, fact in f.used.items():
        obs = next(
            o for o in p.read_observations(fact["indicator"])
            if o.geography_id == fact["geography"] and o.period == fact["period"]
        )  # fmt: skip
        assert fact["status"] == obs.status, key


def test_edition_frozen_before_files_field_keeps_its_file_links(fixture_root, tmp_path):
    import json as _json

    p = write_brief(fixture_root)
    b = briefing.load_all(fixture_root)["test_brief"]
    path = briefing.freeze(fixture_root, p, b, period_label)
    data = _json.loads(path.read_text(encoding="utf-8"))
    for s in data["sources"]:
        s.pop("files", None)  # the schema of editions frozen before "files" existed
        s["file"] = "https://example.org/test-fixture/raw.csv?a=1&b=2"  # fixture URL
    path.write_text(_json.dumps(data), encoding="utf-8")
    p = write_brief(fixture_root, status="published", extra=f"published_edition: {path.stem}\n")
    assert build(p, tmp_path / "prod") == []
    page = (tmp_path / "prod/briefings/test_brief/index.html").read_text(encoding="utf-8")
    raw = data["sources"][0]["file"]
    assert f'<a href="{raw.replace("&", "&amp;")}">file</a>' in page


ONS_FIX = Path(__file__).parent / "fixtures" / "ons"
FLOWS = {"immigration_long_term": "Immigration", "emigration_long_term": "Emigration",
         "net_migration": "Net migration"}  # fmt: skip


def _project_on_may26_fixture():
    """The real project, with the three ONS flows read from the May 2026 fixture."""
    from ukdash.sources import ADAPTERS

    p = Project.load()
    raw = (ONS_FIX / "ltim_ye_dec2025.xlsx").read_bytes()
    obs = {i: ADAPTERS["ons_ltim"].parse(p.indicators[i], raw, p.geographies) for i in FLOWS}
    real_read, real_manifest = p.read_observations, p.read_manifest
    p.read_observations = lambda i: obs[i] if i in obs else real_read(i)
    p.read_manifest = lambda: [
        e.model_copy(update={"path": "tests/fixtures/ons/ltim_ye_dec2025.xlsx"})
        if e.indicator_id in FLOWS else e
        for e in real_manifest()
    ]  # fmt: skip
    return p


def test_release_changes_match_a_genuine_pair_of_ons_releases():
    from ukdash.sources.ons_ltim import parse_table

    p = _project_on_may26_fixture()
    f = briefing.Facts(p, list(FLOWS), period_label)
    rc = f.release_changes()
    assert (rc["previous"], rc["current"]) == ("November 2025", "May 2026")

    old = parse_table((ONS_FIX / "ltim_ye_jun2025.xlsx").read_bytes())
    new = parse_table((ONS_FIX / "ltim_ye_dec2025.xlsx").read_bytes())
    old_net = {k[2]: v[0] for k, v in old.items() if k[:2] == ("Net migration", "total")}
    new_net = {k[2]: v[0] for k, v in new.items() if k[:2] == ("Net migration", "total")}
    # New = periods the November 2025 release did not have.
    assert [r["when"] for r in rc["new"]] == [
        period_label(q, "Y12") for q in sorted(set(new_net) - set(old_net))
    ]
    # Revised = periods whose estimate differs between the two releases, with the
    # November 2025 workbook's own figure as "was".
    revised = {
        q for q in old_net for flow in FLOWS.values()
        if old.get((flow, "total", q), (None,))[0] != new.get((flow, "total", q), (None,))[0]
    }  # fmt: skip
    assert [r["when"] for r in rc["revised"]] == [period_label(q, "Y12") for q in sorted(revised)]
    for r in rc["revised"]:
        q = next(q for q in revised if period_label(q, "Y12") == r["when"])
        assert r["figures"]["net_migration"]["before"] == f"{old_net[q]:,.0f}"
        assert r["figures"]["net_migration"]["after"] == f"{new_net[q]:,.0f}"


def test_two_editions_older_one_stays_retrievable(fixture_root, tmp_path, monkeypatch):
    from datetime import UTC, datetime

    class Clock(datetime):
        t = datetime(2026, 5, 21, 9, 30, tzinfo=UTC)

        @classmethod
        def now(cls, tz=None):
            return cls.t

    monkeypatch.setattr(briefing, "datetime", Clock)
    p = write_brief(fixture_root)
    b = briefing.load_all(fixture_root)["test_brief"]
    first = briefing.freeze(fixture_root, p, b, period_label).stem
    p = write_brief(fixture_root, status="published", extra=f"published_edition: {first}\n")
    assert build(p, tmp_path / "one") == []

    set_latest_value(fixture_root, "4.0")  # the next release
    Clock.t = datetime(2026, 11, 26, 9, 45, tzinfo=UTC)
    p = Project.load(fixture_root)
    second = briefing.freeze(fixture_root, p, b, period_label).stem
    p = write_brief(
        fixture_root,
        status="published",
        extra=f"published_edition: {second}\nearlier_editions: [{first}]\n",
    )
    out = tmp_path / "two"
    assert build(p, out) == []

    site = out / "briefings/test_brief"
    old = (site / "editions" / first / "index.html").read_text(encoding="utf-8")
    cur = (site / "index.html").read_text(encoding="utf-8")
    assert "<strong>4.8%</strong>" in old and "This is an earlier edition" in old
    assert f"editions/{first}/" in old and f"/briefings/test_brief/editions/{second}/" in old
    assert "<strong>4.0%</strong>" in cur and "earlier edition" not in cur
    assert f"editions/{second}/figures.csv" in cur  # current download link
    # Each edition's download holds exactly its frozen figures.
    for ed, value in ((first, "4.8"), (second, "4.0")):
        rows = list(csv.DictReader((site / "editions" / ed / "figures.csv").open(encoding="utf-8")))
        latest = next(r for r in rows if r["period"] == "2025-06" and r["geography"] == "iso:GBR")
        assert float(latest["value"]) == float(value)
        frozen = briefing.read_edition(fixture_root, "test_brief", ed)["facts"]
        assert {r["key"] for r in rows} == set(frozen)
    # An edition newer than the published one (awaiting approval) is not public.
    p = write_brief(fixture_root, status="published", extra=f"published_edition: {first}\n")
    assert build(p, tmp_path / "three") == []
    assert not (tmp_path / "three/briefings/test_brief/editions" / second).exists()


def test_frozen_but_never_approved_edition_is_never_public(fixture_root, tmp_path, monkeypatch):
    """Codex P1 on #31: an older frozen candidate that was rejected must not appear in
    production just because a later edition was published."""
    from datetime import UTC, datetime

    class Clock(datetime):
        t = datetime(2026, 5, 21, 9, 30, tzinfo=UTC)

        @classmethod
        def now(cls, tz=None):
            return cls.t

    monkeypatch.setattr(briefing, "datetime", Clock)
    p = write_brief(fixture_root)
    b = briefing.load_all(fixture_root)["test_brief"]
    rejected = briefing.freeze(fixture_root, p, b, period_label).stem  # never approved
    set_latest_value(fixture_root, "4.0")
    Clock.t = datetime(2026, 5, 22, 9, 30, tzinfo=UTC)
    approved = briefing.freeze(fixture_root, Project.load(fixture_root), b, period_label).stem
    p = write_brief(fixture_root, status="published", extra=f"published_edition: {approved}\n")
    out = tmp_path / "prod"
    assert build(p, out) == []
    site = out / "briefings/test_brief"
    assert not (site / "editions" / rejected).exists()
    assert rejected not in (site / "index.html").read_text(encoding="utf-8")
    assert (site / "editions" / approved / "figures.csv").exists()
    # In a preview the rejected file is visible for review, never labelled as published.
    assert build(p, tmp_path / "prev", include_drafts=True) == []
    prev = (tmp_path / "prev/briefings/test_brief/editions" / rejected / "index.html").read_text(
        encoding="utf-8"
    )
    assert "not approved for publication" in prev and "reviewed before publication" not in prev
    assert "This is an earlier edition" not in prev


def test_earlier_editions_must_be_older_and_ordered(fixture_root):
    write_brief(
        fixture_root,
        status="published",
        extra="published_edition: 2026-05-21-0930\nearlier_editions: [2026-06-01-0000]\n",
    )
    with pytest.raises(ValueError, match="earlier_editions"):
        briefing.load_all(fixture_root)


def test_archive_holds_exactly_the_approved_editions(fixture_root, tmp_path, monkeypatch):
    """Codex on #31: approved A, rejected B, approved current C, newer unapproved D."""
    from datetime import UTC, datetime

    class Clock(datetime):
        t = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)

        @classmethod
        def now(cls, tz=None):
            return cls.t

    monkeypatch.setattr(briefing, "datetime", Clock)
    write_brief(fixture_root)
    b = briefing.load_all(fixture_root)["test_brief"]
    ids = {}
    for name, day, value in (("A", 1, "4.8"), ("B", 2, "4.5"), ("C", 3, "4.0"), ("D", 4, "3.9")):
        set_latest_value(fixture_root, value)
        Clock.t = datetime(2026, 5, day, 9, 0, tzinfo=UTC)
        ids[name] = briefing.freeze(fixture_root, Project.load(fixture_root), b, period_label).stem
    p = write_brief(
        fixture_root,
        status="published",
        extra=f"published_edition: {ids['C']}\nearlier_editions: [{ids['A']}]\n",
    )
    out = tmp_path / "prod"
    assert build(p, out) == []
    site = out / "briefings/test_brief"
    for name in "AC":
        ed = ids[name]
        rows = list(csv.DictReader((site / "editions" / ed / "figures.csv").open(encoding="utf-8")))
        assert {r["key"] for r in rows} == set(
            briefing.read_edition(fixture_root, "test_brief", ed)["facts"]
        )
    for name in "BD":
        assert not (site / "editions" / ids[name]).exists()
    pages = [f.read_text(encoding="utf-8") for f in site.rglob("*.html")]
    for page in pages:
        assert ids["B"] not in page and ids["D"] not in page
    a = (site / "editions" / ids["A"] / "index.html").read_text(encoding="utf-8")
    assert "This is an earlier edition" in a and f"/editions/{ids['C']}/" in a


def test_evidence_records_are_complete_and_rendered(tmp_path):
    from ukdash import evidence

    recs = evidence.load_all(Project.load().root)
    s = recs["bf_tracker_2026_net_direction"]
    assert s["population"].startswith("Adults aged 18 and over in Great Britain")
    assert {r["answer"]: r["percent"] for r in s["results"]}["Higher"] == 49
    assert evidence.money(4181193, "GBP thousand") == "£4.18 billion"
    assert build(Project.load(), tmp_path / "prev", include_drafts=True) == []
    ev = tmp_path / "prev/briefings/immigration/evidence"
    page = (ev / "bf_tracker_2026_net_direction/index.html").read_text(encoding="utf-8")
    for field in ("3,003 respondents", "2026-03-19 to 2026-03-30", "Number Cruncher Politics",
                  "not reported", "Reuse"):  # fmt: skip
        assert field in page
    fig = (ev / "home_office_asylum_support_2025_26/index.html").read_text(encoding="utf-8")
    assert "£4.18 billion" in fig and "4,181,193 (GBP thousand)" in fig and "not the total" in fig


def test_survey_record_rejects_missing_fields(fixture_root):
    from ukdash import evidence

    (fixture_root / "evidence").mkdir()
    (fixture_root / "evidence" / "x.yml").write_text(
        "id: x\nkind: survey\ntitle: t\nsource: s\nsource_url: u\nchecked: c\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing"):
        evidence.load_all(fixture_root)


def test_survey_row_stays_on_the_years_asked_about():
    """Codex P2 on #33: a later net-migration period must not change the comparison
    with what respondents were asked (2025 vs 2024)."""
    p = Project.load()
    real = p.read_observations
    flows = ("net_migration", "immigration_long_term", "emigration_long_term")

    def read(i):
        rows = real(i)
        if i not in flows:
            return rows
        later = [o.model_copy(update={"period": "2026-03", "value": 999_000.0})
                 for o in rows if o.period == "2025-12"]  # fmt: skip
        return rows + later

    p.read_observations = read
    b = briefing.load_all(p.root)["immigration"]
    html, _, _ = briefing.render_candidate(p, b, period_label)
    row = html[html.index("Was net migration in 2025 higher or lower") :]
    row = row[: row.index("</tr>")]
    assert "year ending December 2025" in row and "year ending December 2024" in row
    assert "999,000" not in row
    hook = html[html.index('class="hook"') :]
    assert "999,000" not in hook[: hook.index("</p>")]


def test_edition_keeps_the_evidence_record_it_was_published_with(fixture_root, tmp_path):
    """Codex P2 on #33: correcting a record later must not change an archived edition."""
    import shutil

    shutil.copytree(Path(__file__).parents[1] / "evidence", fixture_root / "evidence")
    p = write_brief(
        fixture_root,
        body='{{ survey("bf_tracker_2026_net_direction", "Higher").pct }} '
        '[s]({{ survey("bf_tracker_2026_net_direction", "Higher").url }})',
    )
    b = briefing.load_all(fixture_root)["test_brief"]
    ed = briefing.freeze(fixture_root, p, b, period_label).stem
    rec = fixture_root / "evidence" / "bf_tracker_2026_net_direction.yml"
    rec.write_text(
        rec.read_text(encoding="utf-8").replace("Online", "Telephone (corrected later)"),
        encoding="utf-8",
    )
    p = write_brief(fixture_root, status="published", extra=f"published_edition: {ed}\n")
    out = tmp_path / "prod"
    assert build(p, out) == []
    for page_dir in (out / "briefings/test_brief", out / "briefings/test_brief/editions" / ed):
        page = (page_dir / "evidence/bf_tracker_2026_net_direction/index.html").read_text(
            encoding="utf-8"
        )
        assert "(Online)" in page and "corrected later" not in page
