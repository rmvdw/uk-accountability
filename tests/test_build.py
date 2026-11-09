from ukdash.build import build
from ukdash.project import Project


def test_repository_builds_published_indicators_only(tmp_path):
    project = Project.load()
    assert build(project, tmp_path / "site") == []
    home = (tmp_path / "site/index.html").read_text(encoding="utf-8")
    for d in project.indicators.values():
        assert (tmp_path / "site" / d.id).exists() == (d.status == "published")
        if d.status == "published":
            assert "Draft: awaiting approval" not in (
                tmp_path / "site" / d.id / "index.html"
            ).read_text(encoding="utf-8")
    if not project.published():
        assert "No indicators published yet" in home


def test_empty_state_when_nothing_is_published(fixture_root, tmp_path):
    p = fixture_root / "indicators/test_unemployment.yml"
    p.write_text(
        p.read_text(encoding="utf-8").replace("status: published", "status: draft"),
        encoding="utf-8",
    )
    assert build(Project.load(fixture_root), tmp_path / "site") == []
    assert "No indicators published yet" in (tmp_path / "site/index.html").read_text(
        encoding="utf-8"
    )


def test_fixture_builds_indicator_page(fixture_project, tmp_path):
    out = tmp_path / "site"
    assert build(fixture_project, out) == []
    page = (out / "test_unemployment/index.html").read_text(encoding="utf-8")
    assert "TEST FIXTURE" in page
    assert "United Kingdom, June 2025" in page
    assert "May 2025: the latest period with data for every country shown" in page
    assert "<strong>4 of 7</strong>" in page
    assert "Great Britain" not in page  # UK data must never be labelled GB
    assert (out / "test_unemployment/test_unemployment.csv").exists()
    assert (out / "build-info.json").exists()


def test_build_refuses_invalid_data(fixture_root, tmp_path):
    csv = fixture_root / "data/observations/test_unemployment.csv"
    csv.write_text(
        csv.read_text(encoding="utf-8").replace("2025-05", "2025-Q2", 1), encoding="utf-8"
    )
    errors = build(Project.load(fixture_root), tmp_path / "site")
    assert errors
    assert not (tmp_path / "site").exists()


def test_long_date_is_portable():
    from datetime import datetime

    from ukdash.build import long_date

    assert long_date(datetime(2026, 7, 1)) == "1 July 2026"


def test_drafts_only_in_preview(fixture_root, tmp_path):
    p = fixture_root / "indicators/test_unemployment.yml"
    p.write_text(
        p.read_text(encoding="utf-8").replace("status: published", "status: draft"),
        encoding="utf-8",
    )
    project = Project.load(fixture_root)
    assert build(project, tmp_path / "prod") == []
    assert not (tmp_path / "prod/test_unemployment").exists()
    assert build(project, tmp_path / "prev", include_drafts=True) == []
    page = (tmp_path / "prev/test_unemployment/index.html").read_text(encoding="utf-8")
    assert "Draft: awaiting approval" in page and "Review preview" in page


def test_draft_without_data_renders_in_preview(fixture_root, tmp_path):
    src = (fixture_root / "indicators/test_unemployment.yml").read_text(encoding="utf-8")
    new = src.replace("id: test_unemployment", "id: not_fetched_yet").replace(
        "status: published", "status: draft"
    )
    (fixture_root / "indicators/not_fetched_yet.yml").write_text(new, encoding="utf-8")
    project = Project.load(fixture_root)
    assert build(project, tmp_path / "prev", include_drafts=True) == []
    page = (tmp_path / "prev/not_fetched_yet/index.html").read_text(encoding="utf-8")
    assert "No data fetched yet" in page
    assert "Download the data" not in page
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
    page = (tmp_path / "prev/unemployment_rate/index.html").read_text(encoding="utf-8")
    assert "United Kingdom, June to August 2026" in page
    assert "average of June to August 2026, which the source records as July 2026" in page


def test_cloudflare_branch_aware_drafts(monkeypatch):
    from ukdash.build import cloudflare_preview_branch

    for var in ("CF_PAGES", "CF_PAGES_BRANCH"):
        monkeypatch.delenv(var, raising=False)
    assert cloudflare_preview_branch() is None  # local / CI / agents: production rules

    monkeypatch.setenv("CF_PAGES", "1")
    monkeypatch.setenv("CF_PAGES_BRANCH", "main")
    assert cloudflare_preview_branch() is None  # production deploy never shows drafts

    monkeypatch.setenv("CF_PAGES_BRANCH", "life-expectancy")
    assert cloudflare_preview_branch() == "life-expectancy"

    monkeypatch.delenv("CF_PAGES")
    assert cloudflare_preview_branch() is None  # branch var alone is not enough


def test_cli_build_includes_drafts_only_on_cloudflare_preview(monkeypatch, tmp_path):
    import json

    from ukdash.cli import main

    monkeypatch.setenv("CF_PAGES", "1")
    monkeypatch.setenv("CF_PAGES_COMMIT_SHA", "abc123")
    for branch, expected in (("main", False), ("feature-x", True)):
        monkeypatch.setenv("CF_PAGES_BRANCH", branch)
        out = tmp_path / branch
        assert main(["build", "--out", str(out)]) == 0
        info = json.loads((out / "build-info.json").read_text(encoding="utf-8"))
        assert info["preview_with_drafts"] is expected
        assert info["source_commit"] == "abc123" and info["branch"] == branch
        assert ("Review preview" in (out / "index.html").read_text(encoding="utf-8")) is expected


def test_uk_only_indicator_has_no_comparison(fixture_root, tmp_path):
    p = fixture_root / "indicators/test_unemployment.yml"
    text = p.read_text(encoding="utf-8")
    start = text.index("peers:")
    end = text.index("caveats:")
    p.write_text(text[:start] + text[end:], encoding="utf-8")
    project = Project.load(fixture_root)
    assert project.indicators["test_unemployment"].peers is None
    assert build(project, tmp_path / "site") == []
    page = (tmp_path / "site/test_unemployment/index.html").read_text(encoding="utf-8")
    assert "no reliable international comparison" in page
    assert "Compared with the" not in page


def test_rolling_and_stock_period_labels():
    from ukdash.build import _period_label

    assert _period_label("2025-12", "Y12") == "year ending December 2025"
    assert _period_label("2026-06", "Y12", short=True) == "YE Jun 2026"
    assert _period_label("2026-06", "AT") == "end of June 2026"


def test_undeclared_breakdown_is_rejected(fixture_root):
    from ukdash.validate import validate

    csv = fixture_root / "data/observations/test_unemployment.csv"
    lines = csv.read_text(encoding="utf-8").splitlines()
    lines.append(lines[1].replace(",total,", ",british,"))
    csv.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert any("undeclared breakdown" in e for e in validate(Project.load(fixture_root)))
