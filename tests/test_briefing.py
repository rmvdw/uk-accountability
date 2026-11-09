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
    assert "TO VERIFY" in html  # fiscal claims still need checking, so it can't be frozen yet
    assert {s["publisher"] for s in sources} == {"Office for National Statistics", "Home Office"}


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
