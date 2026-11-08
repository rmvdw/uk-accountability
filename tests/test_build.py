from ukdash.build import build
from ukdash.project import Project


def test_empty_repository_builds(tmp_path):
    assert build(Project.load(), tmp_path / "site") == []
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
