from pathlib import Path

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


def test_site_needs_a_contact_address_and_lists_corrections(fixture_root, tmp_path):
    import yaml

    from ukdash.build import build as build_site
    from ukdash.project import Project as P

    cfg = fixture_root / "config" / "site.yml"
    site = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    site["contact_email"] = "not-an-address"
    cfg.write_text(yaml.safe_dump(site), encoding="utf-8")
    assert any("contact_email" in e for e in build_site(P.load(fixture_root), tmp_path / "a"))

    # Until Ross supplies an address, readers are sent to GitHub, never to a placeholder.
    site["contact_email"] = ""
    cfg.write_text(yaml.safe_dump(site), encoding="utf-8")
    assert build_site(P.load(fixture_root), tmp_path / "gh") == []
    about = (tmp_path / "gh/about/index.html").read_text(encoding="utf-8")
    assert "issues/new" in about and "mailto:" not in about
    assert "UK Insights" in (tmp_path / "gh/index.html").read_text(encoding="utf-8")

    site["contact_email"] = "errors@example.org"  # test address only
    cfg.write_text(yaml.safe_dump(site), encoding="utf-8")
    out = tmp_path / "b"
    assert build_site(P.load(fixture_root), out) == []
    about = (out / "about/index.html").read_text(encoding="utf-8")
    assert "mailto:errors@example.org" in about and site["owner"] in about
    assert "It is independent." in about and "within" not in about  # no reply promise
    assert "the MIT licence does not cover them" in about
    assert "No corrections yet." in (out / "corrections/index.html").read_text(encoding="utf-8")
    home = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="/corrections/"' in home and "mailto:errors@example.org" in home


def _log(root, entry: str) -> None:
    (root / "corrections").mkdir(exist_ok=True)
    (root / "corrections" / "log.yml").write_text("entries:\n" + entry, encoding="utf-8")


def test_corrections_link_only_to_real_public_pages_and_editions(
    fixture_root, tmp_path, monkeypatch
):
    """#34 review: a valid briefing correction, a rejected unapproved edition, and an
    indicator correction with no edition archive."""
    from datetime import UTC, datetime

    from test_briefing import set_latest_value, write_brief

    from ukdash import briefing
    from ukdash.build import build as build_site
    from ukdash.build import period_label
    from ukdash.project import Project as P

    class Clock(datetime):
        t = datetime(2026, 5, 21, 9, 30, tzinfo=UTC)

        @classmethod
        def now(cls, tz=None):
            return cls.t

    monkeypatch.setattr(briefing, "datetime", Clock)
    write_brief(fixture_root)
    b = briefing.load_all(fixture_root)["test_brief"]
    first = briefing.freeze(fixture_root, P.load(fixture_root), b, period_label).stem
    set_latest_value(fixture_root, "4.0")
    Clock.t = datetime(2026, 5, 22, 9, 30, tzinfo=UTC)
    second = briefing.freeze(fixture_root, P.load(fixture_root), b, period_label).stem
    Clock.t = datetime(2026, 5, 23, 9, 30, tzinfo=UTC)
    unapproved = briefing.freeze(fixture_root, P.load(fixture_root), b, period_label).stem
    write_brief(fixture_root, status="published",
                extra=f"published_edition: {second}\nearlier_editions: [{first}]\n")  # fmt: skip

    # 1. A valid correction to a published briefing: both editions are public.
    entry = f"page: /briefings/test_brief/, edition: '{first}', corrected_in: '{second}'"
    _log(fixture_root, f"  - {{date: 2026-05-22, {entry}, summary: Fixture correction.}}\n")
    out = tmp_path / "ok"
    assert build_site(P.load(fixture_root), out) == []
    log = (out / "corrections/index.html").read_text(encoding="utf-8")
    for ed in (first, second):
        assert f"/briefings/test_brief/editions/{ed}/" in log
        assert (out / "briefings/test_brief/editions" / ed / "index.html").exists()

    # 2. Rejected: an edition that was frozen but never approved, or does not exist.
    for bad in (unapproved, "never-published"):
        entry = f"page: /briefings/test_brief/, edition: '{first}', corrected_in: '{bad}'"
        _log(fixture_root, f"  - {{date: 2026-05-22, {entry}, summary: Fixture.}}\n")
        errors = build_site(P.load(fixture_root), tmp_path / f"bad-{bad}")
        assert any("published editions" in e for e in errors)

    # 3. An indicator page: a dated record against the page, no edition links.
    ind = next(iter(P.load(fixture_root).published())).id
    _log(fixture_root, f"  - {{date: 2026-05-22, page: /{ind}/, summary: Fixture.}}\n")
    out = tmp_path / "ind"
    assert build_site(P.load(fixture_root), out) == []
    log = (out / "corrections/index.html").read_text(encoding="utf-8")
    assert "no edition archive" in log and "editions/" not in log
    _log(fixture_root, f"  - {{date: 2026-05-22, page: /{ind}/, edition: x, corrected_in: y, "
         "summary: Fixture.}\n")  # fmt: skip
    assert any("no edition archive" in e for e in build_site(P.load(fixture_root), tmp_path / "x"))
    _log(fixture_root, "  - {date: 2026-05-22, page: /nowhere/, summary: Fixture.}\n")
    assert any("not on the site" in e for e in build_site(P.load(fixture_root), tmp_path / "y"))


def test_site_config_and_corrections_are_gated():
    """#34 review: public facts in these files need Ross's approval."""
    import importlib.util

    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location(
        "gate", root / ".github/scripts/editorial_gate.py"
    )
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    patterns = gate.owned_patterns((root / ".github/CODEOWNERS").read_text(encoding="utf-8"))
    assert gate.is_owned("config/site.yml", patterns)
    assert gate.is_owned("corrections/log.yml", patterns)
    assert not gate.is_owned("config/geographies.yml", patterns)  # unchanged
