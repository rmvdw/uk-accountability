from ukdash.build import build
from ukdash.project import Project


def test_repository_builds_published_indicators_only(tmp_path):
    project = Project.load()
    assert build(project, tmp_path / "site") == []
    home = (tmp_path / "site/index.html").read_text()
    for d in project.indicators.values():
        assert (tmp_path / "site" / d.id).exists() == (d.status == "published")
        if d.status == "published":
            assert (
                "Draft: awaiting approval"
                not in (tmp_path / "site" / d.id / "index.html").read_text()
            )
    if not project.published():
        assert "No indicators published yet" in home


def test_empty_state_when_nothing_is_published(fixture_root, tmp_path):
    p = fixture_root / "indicators/test_unemployment.yml"
    p.write_text(p.read_text().replace("status: published", "status: draft"))
    assert build(Project.load(fixture_root), tmp_path / "site") == []
    assert "No indicators published yet" in (tmp_path / "site/index.html").read_text()


def test_fixture_builds_indicator_page(fixture_project, tmp_path):
    out = tmp_path / "site"
    assert build(fixture_project, out) == []
    page = (out / "test_unemployment/index.html").read_text()
    assert "TEST FIXTURE" in page
    assert "United Kingdom, June 2025" in page
    assert "May 2025: the latest period with data for every country shown" in page
    assert "<strong>4 of 7</strong>" in page
    assert "Great Britain" not in page  # UK data must never be labelled GB
    assert (out / "test_unemployment/test_unemployment.csv").exists()
    assert (out / "build-info.json").exists()


def test_build_refuses_invalid_data(fixture_root, tmp_path):
    csv = fixture_root / "data/observations/test_unemployment.csv"
    csv.write_text(csv.read_text().replace("2025-05", "2025-Q2", 1))
    errors = build(Project.load(fixture_root), tmp_path / "site")
    assert errors
    assert not (tmp_path / "site").exists()


def test_long_date_is_portable():
    from datetime import datetime

    from ukdash.build import long_date

    assert long_date(datetime(2026, 7, 1)) == "1 July 2026"


def test_drafts_only_in_preview(fixture_root, tmp_path):
    p = fixture_root / "indicators/test_unemployment.yml"
    p.write_text(p.read_text().replace("status: published", "status: draft"))
    project = Project.load(fixture_root)
    assert build(project, tmp_path / "prod") == []
    assert not (tmp_path / "prod/test_unemployment").exists()
    assert build(project, tmp_path / "prev", include_drafts=True) == []
    page = (tmp_path / "prev/test_unemployment/index.html").read_text()
    assert "Draft: awaiting approval" in page and "Review preview" in page


def test_draft_without_data_renders_in_preview(fixture_root, tmp_path):
    src = (fixture_root / "indicators/test_unemployment.yml").read_text()
    new = src.replace("id: test_unemployment", "id: not_fetched_yet").replace(
        "status: published", "status: draft"
    )
    (fixture_root / "indicators/not_fetched_yet.yml").write_text(new)
    project = Project.load(fixture_root)
    assert build(project, tmp_path / "prev", include_drafts=True) == []
    page = (tmp_path / "prev/not_fetched_yet/index.html").read_text()
    assert "No data fetched yet" in page
    assert "Download all countries" not in page
    assert not (tmp_path / "prev/not_fetched_yet/not_fetched_yet.csv").exists()


def test_centred_three_month_labels():
    from ukdash.build import _geo_period_label

    d = Project.load().indicators["unemployment_rate"]
    assert _geo_period_label(d, "iso:GBR", "2026-07") == "June to August 2026"
    assert _geo_period_label(d, "iso:GBR", "2026-01") == "December 2025 to February 2026"
    assert _geo_period_label(d, "iso:GBR", "2026-07", short=True) == "Jun–Aug 2026"
    assert _geo_period_label(d, "iso:USA", "2026-07") == "July 2026"


def test_real_indicator_preview_explains_uk_window(tmp_path):
    assert build(Project.load(), tmp_path / "prev", include_drafts=True) == []
    page = (tmp_path / "prev/unemployment_rate/index.html").read_text()
    assert "United Kingdom, June to August 2026" in page
    assert "average of June to August 2026, which the source records as July 2026" in page
